"""Model routing — provider-agnostic.

ANY OpenAI-compatible provider works, including the free HOSTED ones (no GPU):
Groq, Gemini, OpenRouter, Cerebras, local Ollama — plus Anthropic via its native SDK.

  - synthesize()  quality path the scorer/memos use. Picks a provider by: explicit arg ->
                  SIGNAL_LLM_PROVIDER env -> auto-order (anthropic -> hosted presets -> ollama).
  - triage()      cheap/high-volume path, local-first (ollama -> fast hosted -> anthropic).

`available_providers()` lists what's configured; `current_provider()` is what synthesize()
would pick now ("heuristic" if nothing is). Heavy SDKs import lazily, so the offline/demo
path needs none of them. Backward-compatible with OLLAMA_BASE_URL / ANTHROPIC_API_KEY.
"""
from __future__ import annotations

import json
import os
import random
import re
import threading
import time


class LLMUnavailable(RuntimeError):
    pass


# Provider presets. base_url None => special handling (anthropic native SDK; ollama reads
# OLLAMA_BASE_URL). key_env None => no key needed (local). Model from env, else default.
PROVIDERS = {
    "anthropic":  {"base_url": None,
                   "key_env": "ANTHROPIC_API_KEY",
                   "default_model_env": "FRONTIER_MODEL", "default_model": "claude-sonnet-4-6"},
    "groq":       {"base_url": "https://api.groq.com/openai/v1",
                   "key_env": "GROQ_API_KEY",
                   "default_model_env": "GROQ_MODEL", "default_model": "llama-3.3-70b-versatile"},
    "gemini":     {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                   "key_env": "GEMINI_API_KEY",
                   "default_model_env": "GEMINI_MODEL", "default_model": "gemini-2.0-flash"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1",
                   "key_env": "OPENROUTER_API_KEY",
                   "default_model_env": "OPENROUTER_MODEL",
                   "default_model": "meta-llama/llama-3.3-70b-instruct:free"},
    "cerebras":   {"base_url": "https://api.cerebras.ai/v1",
                   "key_env": "CEREBRAS_API_KEY",
                   "default_model_env": "CEREBRAS_MODEL", "default_model": "llama-3.3-70b"},
    "ollama":     {"base_url": None,  # base from OLLAMA_BASE_URL (local, no key)
                   "key_env": None,
                   "default_model_env": "LOCAL_MODEL", "default_model": "qwen2.5:14b"},
}

# synthesize() prefers quality (frontier first); triage() prefers local/cheap & fast.
_AUTO_ORDER = ["anthropic", "groq", "gemini", "openrouter", "cerebras", "ollama"]
_TRIAGE_ORDER = ["ollama", "groq", "cerebras", "gemini", "openrouter", "anthropic"]


# ---- availability -----------------------------------------------------------

def _provider_available(name: str) -> bool:
    cfg = PROVIDERS.get(name)
    if not cfg:
        return False
    if name == "ollama":
        return bool(os.getenv("OLLAMA_BASE_URL"))
    return bool(os.getenv(cfg["key_env"]))


def available_providers() -> list:
    """Provider names whose key/endpoint is present, plus 'heuristic' (always available)."""
    return [p for p in PROVIDERS if _provider_available(p)] + ["heuristic"]


def any_available() -> bool:
    """True if ANY LLM provider is configured (frontier, hosted, or local)."""
    return any(_provider_available(p) for p in PROVIDERS)


def frontier_available() -> bool:
    return _provider_available("anthropic")


def local_available() -> bool:
    return _provider_available("ollama")


def provider_model(name: str):
    """The model id that `name` would use right now (None for heuristic)."""
    cfg = PROVIDERS.get(name)
    if not cfg:
        return None
    return os.getenv(cfg["default_model_env"], cfg["default_model"])


def _pick(order: list, provider: str = None):
    """Resolve a provider: explicit (if available) -> SIGNAL_LLM_PROVIDER env -> auto-order.
    Returns a provider name, or None to mean 'no LLM' (use heuristic)."""
    if provider == "heuristic":
        return None
    if provider and _provider_available(provider):
        return provider
    envp = os.getenv("SIGNAL_LLM_PROVIDER")
    if envp == "heuristic":
        return None
    if envp and _provider_available(envp):
        return envp
    for p in order:
        if _provider_available(p):
            return p
    return None


def current_provider() -> str:
    """What synthesize() would pick right now ('heuristic' if nothing is configured/forced)."""
    return _pick(_AUTO_ORDER) or "heuristic"


# ---- free-tier rate-limit stabilisation -------------------------------------
# A batch run (e.g. --limit 40 -> 43 scoring calls) must not randomly rate-limit the
# last calls and silently fall back to heuristic. Two mechanisms, both lazy / no new deps:
#   * client-side THROTTLE (token bucket) keeps a burst under the provider's RPM, but an
#     isolated call or a short memo (<= burst calls) never sleeps.
#   * RETRY on 429 / RateLimitError with exponential backoff + jitter; on exhaustion it
#     re-raises so callers keep the existing graceful heuristic fallback (+ llm_fallback risk).
# `_sleep` / `_monotonic` are indirected so the offline tests can use a fake clock.
_sleep = time.sleep
_monotonic = time.monotonic
_rl_lock = threading.Lock()
_rl_tokens = None        # token bucket (lazy); None until first call
_rl_last = 0.0           # monotonic time of last refill


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return float(default)


def _int_env(name: str, default: int) -> int:
    try:
        return int(float(os.getenv(name, default)))
    except (TypeError, ValueError):
        return int(default)


def _is_rate_limit(exc) -> bool:
    """True for a provider rate-limit / 429 (across SDKs), regardless of exact class."""
    if "ratelimit" in type(exc).__name__.lower():
        return True
    for attr in ("status_code", "status", "code"):
        if getattr(exc, attr, None) == 429:
            return True
    s = str(exc).lower()
    return "429" in s or "rate limit" in s or "too many requests" in s


def _throttle() -> None:
    """Token-bucket limiter: keep a burst of LLM calls under SIGNAL_LLM_MAX_RPM (default 25,
    under Groq's ~30 free). Bucket size SIGNAL_LLM_BURST (default 3) => an isolated call or a
    short interactive memo (<= burst calls) does NOT sleep; only a long batch is spaced out.
    SIGNAL_LLM_MAX_RPM <= 0 disables throttling entirely."""
    rpm = _float_env("SIGNAL_LLM_MAX_RPM", 25.0)
    if rpm <= 0:
        return
    burst = max(1.0, _float_env("SIGNAL_LLM_BURST", 3.0))
    refill = rpm / 60.0  # tokens per second
    global _rl_tokens, _rl_last
    wait = 0.0
    with _rl_lock:
        now = _monotonic()
        if _rl_tokens is None:
            _rl_tokens, _rl_last = burst, now
        _rl_tokens = min(burst, _rl_tokens + (now - _rl_last) * refill)
        _rl_last = now
        if _rl_tokens >= 1.0:
            _rl_tokens -= 1.0                  # token available -> proceed immediately
        else:
            wait = (1.0 - _rl_tokens) / refill  # sleep until the next token
            _rl_tokens = 0.0
            _rl_last = now + wait
    if wait > 0:
        _sleep(wait)


def _with_retry(fn):
    """Throttle, then run a completion; retry on rate-limit (exp backoff + jitter) up to
    SIGNAL_LLM_MAX_RETRIES (default 4). Non-rate-limit errors raise immediately; on
    exhaustion the last rate-limit error re-raises so callers keep graceful fallback."""
    retries = _int_env("SIGNAL_LLM_MAX_RETRIES", 4)
    for attempt in range(retries + 1):
        _throttle()
        try:
            return fn()
        except Exception as e:
            if attempt >= retries or not _is_rate_limit(e):
                raise
            backoff = min(2.0 ** attempt, 20.0)
            _sleep(backoff + random.uniform(0.0, backoff * 0.5))


# ---- completion backends ----------------------------------------------------

def _frontier_complete(prompt: str, system: str, max_tokens: int) -> str:
    import anthropic

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=provider_model("anthropic"),
        max_tokens=max_tokens,
        system=system or "You are a precise crypto-VC analyst.",
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(getattr(b, "text", "") for b in msg.content)


def _openai_compatible_complete(base_url: str, api_key: str, model: str,
                                prompt: str, system: str, max_tokens: int) -> str:
    """One client for every OpenAI-compatible endpoint (groq / gemini / openrouter /
    cerebras / ollama)."""
    from openai import OpenAI

    client = OpenAI(base_url=base_url, api_key=api_key or "x")
    r = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system or "You are a precise crypto-VC analyst."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=max_tokens,
        temperature=0,
    )
    return r.choices[0].message.content or ""


def _endpoint(provider: str):
    """(base_url, api_key, model) for an OpenAI-compatible provider."""
    cfg = PROVIDERS[provider]
    if provider == "ollama":
        return os.getenv("OLLAMA_BASE_URL"), os.getenv("OPENAI_API_KEY", "ollama"), provider_model(provider)
    return cfg["base_url"], os.getenv(cfg["key_env"]), provider_model(provider)


def _complete_with(provider: str, prompt: str, system: str, max_tokens: int) -> str:
    # Wrap the actual completion in throttle + rate-limit retry (stable batch runs).
    if provider == "anthropic":
        return _with_retry(lambda: _frontier_complete(prompt, system, max_tokens))
    base_url, api_key, model = _endpoint(provider)
    return _with_retry(
        lambda: _openai_compatible_complete(base_url, api_key, model, prompt, system, max_tokens))


# ---- public API -------------------------------------------------------------

def synthesize(prompt: str, system: str = "", max_tokens: int = 1024, provider: str = None) -> str:
    """Quality path. Provider: explicit arg -> SIGNAL_LLM_PROVIDER env -> auto-order."""
    p = _pick(_AUTO_ORDER, provider)
    if p is None:
        raise LLMUnavailable(
            "No LLM provider configured. Set one of ANTHROPIC_API_KEY, GROQ_API_KEY, "
            "GEMINI_API_KEY, OPENROUTER_API_KEY, CEREBRAS_API_KEY, or OLLAMA_BASE_URL."
        )
    return _complete_with(p, prompt, system, max_tokens)


def triage(prompt: str, system: str = "", max_tokens: int = 512, provider: str = None) -> str:
    """Cheap path: local/fast first, frontier last."""
    p = _pick(_TRIAGE_ORDER, provider)
    if p is None:
        raise LLMUnavailable("No model configured (set OLLAMA_BASE_URL or any provider key).")
    return _complete_with(p, prompt, system, max_tokens)


def extract_json(text: str) -> dict:
    """Best-effort JSON extraction from a model response."""
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        raise ValueError("No JSON object found in model response.")
    return json.loads(m.group(0))
