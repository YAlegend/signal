"""Diligence agent — a bounded, tool-using ReAct loop that turns a company into a memo.

This is the "agent" in AI Agent Builder: given a company, a model DECIDES which source-tools
to call, OBSERVES the results, iterates, then the gathered evidence feeds the existing memo
synthesis. It is:

  * Portable — a plain JSON-ACTION protocol (not provider-native tool-calling), so Groq / Gemini
    / OpenRouter / local Ollama all work. Per-step decisions use the cheap llm.triage(); the final
    memo uses llm.synthesize() (via memo.build_memo) — same routing philosophy as the rest.
  * Bounded — capped at SIGNAL_AGENT_MAX_STEPS (default 6), identical repeated calls are deduped,
    and it stops on "finish" or the cap. No runaway cost.
  * Graceful — every tool wraps an EXISTING source/enrich (no reimplementation); a tool whose
    key/data is missing returns {"unavailable": true, ...} so the model learns it can't use it,
    never crashing. With NO provider configured the loop is skipped and the single-shot
    memo.build_memo runs — today's behaviour, unchanged.

The written memo gets a "Diligence trail" section (the tools chosen, in order, with reasons and
the sources they retrieved) — the visible proof it is an agent. Citation verification is preserved:
only sources the agent actually retrieved (accumulated onto candidate.raw['source_urls']) may be
cited by the frontier memo path.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import time

from . import env, llm, memo
from .models import Candidate
from .sources import github_velocity, messari, nansen, onchain, social_farcaster, team

# Bounds a step's wall-clock time (decide() call OR a single tool call) and the whole loop.
# Env-configurable so a slow provider/tool doesn't hang a memo request indefinitely.
_STEP_TIMEOUT_S = "SIGNAL_AGENT_STEP_TIMEOUT_S"
_TOTAL_TIMEOUT_S = "SIGNAL_AGENT_TOTAL_TIMEOUT_S"

# Shared pool: a timed-out call's thread is abandoned (Python can't hard-kill a thread), so a
# single long-lived pool with headroom avoids leaking one executor per call while still bounding
# how long WE wait for any one step.
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=8, thread_name_prefix="signal-agent")

# ---- tool registry (wraps existing sources; never reimplements fetch logic) -------------------

# name -> one-line doc shown to the model so it can choose. args are advisory (JSON).
TOOL_DOCS = [
    ("github_velocity", "args: owner, repo — commit-velocity acceleration, contributor count & Gini for a GitHub repo (free)"),
    ("onchain_metrics", "args: name (optional token contract) — real TVL, retention, holder concentration via DefiLlama/Blockscout (free)"),
    ("social_reputation", "args: handle — Farcaster smart-follower convergence & reputation (needs NEYNAR key)"),
    ("team_lookup", "args: owner, repo — technical-founder proxy, team size, frontier-lab pedigree from GitHub (free)"),
    ("messari_funding", "args: name — latest funding round / stage / lead investors (premium: Messari)"),
    ("nansen_smart_money", "args: token — smart-money net inflow & holder share for a token (premium: Nansen)"),
    ("web_search", "args: query — general web search (needs EXA_API_KEY)"),
]


def _merge(cand: Candidate, out: dict) -> None:
    """Copy present outputs onto the company candidate without clobbering pre-set values."""
    for k, v in out.items():
        if v is not None and k not in cand.raw:
            cand.raw[k] = v


def _present(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def _slugify(name: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")


def tool_github_velocity(args: dict, cand: Candidate) -> dict:
    owner, repo = (args.get("owner") or "").strip(), (args.get("repo") or "").strip()
    if not owner or not repo:
        return {"unavailable": True, "note": "need both owner and repo"}
    url = f"https://github.com/{owner}/{repo}"
    sub = Candidate(name=f"{owner}/{repo}", source="agent", url=url)
    github_velocity.enrich_code_health(sub, token=os.getenv("GITHUB_TOKEN"))
    out = {k: sub.raw.get(k) for k in ("commit_accel", "contributors", "contributor_gini")}
    _merge(cand, out)
    if not _present(out):
        return {"unavailable": True, "note": "no public commit stats (private/rate-limited/offline)", "sources": [url]}
    return {**_present(out), "sources": [url]}


def tool_onchain_metrics(args: dict, cand: Candidate) -> dict:
    name = args.get("name") or cand.name
    token = args.get("token") or cand.raw.get("token_address")
    sub = Candidate(name=name, source="agent", url=args.get("url", ""))
    if token:
        sub.raw["token_address"] = token
    onchain.enrich(sub)
    out = {k: sub.raw.get(k) for k in ("tvl_retention", "real_tvl", "holder_gini")}
    _merge(cand, out)
    slug = _slugify(name)
    srcs = [f"https://defillama.com/protocol/{slug}"] if slug else []
    if not _present(out):
        return {"unavailable": True, "note": "no DefiLlama/Blockscout data for this name/token", "sources": srcs}
    return {**_present(out), "sources": srcs}


def tool_social_reputation(args: dict, cand: Candidate) -> dict:
    handle = (args.get("handle") or "").strip()
    if not handle:
        return {"unavailable": True, "note": "need a farcaster handle/fid"}
    sub = Candidate(name=handle, source="agent", url="", raw={"farcaster": handle})
    social_farcaster.enrich(sub)
    out = {k: sub.raw.get(k) for k in ("smart_followers", "neynar_score", "power_badge", "account_age_days")}
    _merge(cand, out)
    src = [f"https://warpcast.com/{handle}"]
    if sub.raw.get("smart_followers") is None:
        return {"unavailable": True, "note": "needs NEYNAR_API_KEY + FARCASTER_FUND_FID", "sources": src}
    return {**_present(out), "sources": src}


def tool_team_lookup(args: dict, cand: Candidate) -> dict:
    owner, repo = (args.get("owner") or "").strip(), (args.get("repo") or "").strip()
    gh = f"{owner}/{repo}" if owner and repo else None
    sub = Candidate(name=cand.name, source="agent", url=cand.url or "", raw=dict(cand.raw))
    if gh:
        sub.raw["github_repo"] = gh
    team.enrich_team_github(sub)
    out = {k: sub.raw.get(k) for k in ("team_size", "technical_ceo", "frontier_lab_alum")}
    _merge(cand, out)
    src = ([f"https://github.com/{gh}"] if gh
           else ([cand.url] if "github.com" in (cand.url or "") else []))
    if not _present(out):
        return {"unavailable": True, "note": "no public contributor data", "sources": src}
    return {**_present(out), "sources": src}


def tool_messari_funding(args: dict, cand: Candidate) -> dict:
    if not os.getenv("MESSARI_API_KEY"):
        return {"unavailable": True, "note": "needs MESSARI_API_KEY (premium)"}
    sub = Candidate(name=args.get("name") or cand.name, source="agent", url="")
    messari.enrich(sub)
    m = sub.raw.get("messari") or {}
    if not m:
        return {"unavailable": True, "note": "no Messari coverage for this name"}
    _merge(cand, {"messari": m})
    return {"messari": m, "sources": ["https://messari.io/"]}


def tool_nansen_smart_money(args: dict, cand: Candidate) -> dict:
    if not nansen._has_access():
        return {"unavailable": True, "note": "needs NANSEN_API_KEY or SIGNAL_NANSEN_X402"}
    token = args.get("token") or cand.raw.get("nansen_token") or cand.raw.get("token_address")
    if not token:
        return {"unavailable": True, "note": "need a token contract"}
    sub = Candidate(name=cand.name, source="agent", url="", raw={"nansen_token": token})
    nansen.enrich(sub)
    n = sub.raw.get("nansen") or {}
    if not n:
        return {"unavailable": True, "note": "no Nansen data for token"}
    _merge(cand, {"nansen": n})
    return {"nansen": n, "sources": [f"https://nansen.ai/token/{token}"]}


def tool_web_search(args: dict, cand: Candidate) -> dict:
    key = os.getenv("EXA_API_KEY")
    if not key:
        return {"unavailable": True, "note": "needs EXA_API_KEY"}
    query = (args.get("query") or "").strip()
    if not query:
        return {"unavailable": True, "note": "need a query"}
    try:
        import httpx
        with httpx.Client(base_url="https://api.exa.ai", headers={"x-api-key": key}, timeout=30) as cx:
            r = cx.post("/search", json={"query": query, "numResults": 3, "type": "auto"})
            data = r.json() if r.status_code == 200 else {}
        results = data.get("results") or []
        return {"results": [x.get("title") for x in results if x.get("title")][:3],
                "sources": [x.get("url") for x in results if x.get("url")]}
    except Exception as e:  # noqa: BLE001 — network optional, degrade gracefully
        return {"unavailable": True, "note": f"search failed: {type(e).__name__}"}


def default_tools() -> dict:
    return {
        "github_velocity": tool_github_velocity,
        "onchain_metrics": tool_onchain_metrics,
        "social_reputation": tool_social_reputation,
        "team_lookup": tool_team_lookup,
        "messari_funding": tool_messari_funding,
        "nansen_smart_money": tool_nansen_smart_money,
        "web_search": tool_web_search,
    }


# ---- the loop -------------------------------------------------------------------------------

_SYS_AGENT = (
    "You are a diligence agent for a crypto/AI pre-seed fund. Working ONE STEP AT A TIME, decide "
    "which source-tool to call to gather evidence about the company against the thesis, then finish. "
    "Respond with EXACTLY ONE JSON object and nothing else — either "
    '{"action":"call_tool","tool":"<name>","args":{...},"reason":"<why>"} or '
    '{"action":"finish","reason":"<why you have enough>"}.'
)


def _decide_prompt(goal: str, thesis: dict, transcript: list) -> str:
    tools_txt = "\n".join(f"- {n}: {d}" for n, d in TOOL_DOCS)
    hist = json.dumps(transcript, default=str)[:4000]
    return (
        f"GOAL: diligence the company '{goal}'.\n"
        f"THESIS: {thesis.get('thesis_summary', '')}\n\n"
        f"TOOLS AVAILABLE:\n{tools_txt}\n\n"
        f"TRANSCRIPT SO FAR (tool calls + observations):\n{hist or '(none yet)'}\n\n"
        "Pick the next SINGLE action. Prefer free tools; do NOT repeat a call with identical args; "
        "finish once you have enough evidence for a memo. Return ONE JSON object."
    )


def _provider_order() -> list:
    """Provider order for a decision: the pinned choice (SIGNAL_LLM_PROVIDER) first, then the
    cheap-first triage order. So we honour the user's dropdown but can fall through it."""
    order = []
    envp = os.getenv("SIGNAL_LLM_PROVIDER")
    if envp and envp != "heuristic":
        order.append(envp)
    for p in llm._TRIAGE_ORDER:
        if p not in order:
            order.append(p)
    return order


def _make_decider():
    """A decide(goal, thesis, transcript) that AUTO-SKIPS dead providers: it tries each available
    provider in turn (pinned first) and uses the first that actually responds — so a
    configured-but-unreachable model (e.g. a local Ollama that isn't running) is skipped instead of
    silently ending the loop with no tools. It remembers the working provider in `.picked` so later
    steps and the final memo reuse it directly."""
    picked = {"p": None}

    def decide(goal: str, thesis: dict, transcript: list) -> dict:
        prompt = _decide_prompt(goal, thesis, transcript)
        order = ([picked["p"]] if picked["p"] else []) + [p for p in _provider_order() if p != picked["p"]]
        last = None
        for p in order:
            if not llm._provider_available(p):
                continue
            try:
                raw = llm.triage(prompt, system=_SYS_AGENT, max_tokens=300, provider=p)
            except Exception as e:  # noqa: BLE001 — dead/unreachable provider: skip to the next
                last = e
                continue
            picked["p"] = p
            try:
                return llm.extract_json(raw)
            except Exception:
                return {"action": "finish", "reason": "could not parse a decision"}
        return {"action": "finish",
                "reason": f"no working LLM provider ({type(last).__name__ if last else 'none available'})"}

    decide.picked = picked
    return decide


def _max_steps() -> int:
    try:
        return max(1, int(os.getenv("SIGNAL_AGENT_MAX_STEPS", "6")))
    except (TypeError, ValueError):
        return 6


def _step_timeout() -> float:
    try:
        return max(1.0, float(os.getenv(_STEP_TIMEOUT_S, "20")))
    except (TypeError, ValueError):
        return 20.0


def _total_timeout() -> float:
    try:
        return max(1.0, float(os.getenv(_TOTAL_TIMEOUT_S, "90")))
    except (TypeError, ValueError):
        return 90.0


def _call_with_timeout(fn, timeout, *args, **kwargs):
    """Run fn(*args, **kwargs) bounded by `timeout` seconds. Returns (result, timed_out, error).
    A timeout never raises — the underlying thread is left to finish in the background (its
    result is discarded); this bounds how long the CALLER waits, which is what a step deadline
    needs. An exception raised by fn is caught and returned rather than propagated, matching the
    existing 'a tool failure is an observation, not a crash' contract."""
    future = _EXECUTOR.submit(fn, *args, **kwargs)
    try:
        return future.result(timeout=timeout), False, None
    except concurrent.futures.TimeoutError:
        return None, True, None
    except Exception as e:  # noqa: BLE001 — surfaced to the caller as an observation
        return None, False, e


def _prepend_trail(memo_md: str, trail: list, budget: dict = None) -> str:
    """Insert the visible Diligence trail (tools chosen, in order, with reasons + sources),
    plus a budget footer (steps used vs. cap, elapsed time vs. the overall deadline) so a
    reader can see at a glance whether the run finished cleanly or was cut short by a cap."""
    lines = ["## Diligence trail",
             "*The agent chose these source-tools in order — visible proof of the tool-using loop.*",
             ""]
    n = 0
    for step in trail:
        if step.get("tool") == "finish":
            lines.append(f"- _finish_ — {step.get('reason', '')}")
            continue
        n += 1
        args = step.get("args") or {}
        arg_s = ", ".join(f"{k}={v}" for k, v in args.items())
        srcs = [s for s in (step.get("sources") or []) if s]
        src_s = ("  \n  ↳ sources: " + ", ".join(srcs)) if srcs else ""
        lines.append(f"{n}. **{step['tool']}**({arg_s}) — {step.get('reason', '')}{src_s}")
    if budget:
        lines.append("")
        lines.append(
            f"_Budget: {budget['steps_used']}/{budget['steps_max']} steps · "
            f"{budget['elapsed_s']:.1f}s elapsed (cap {budget['total_timeout_s']:.0f}s) · "
            f"status: {budget['status']}_"
        )
    trail_md = "\n".join(lines)
    if memo_md.startswith("# "):
        head, _, rest = memo_md.partition("\n")
        return f"{head}\n\n{trail_md}\n\n{rest.lstrip()}"
    return f"{trail_md}\n\n{memo_md}"


def run_diligence_events(candidate: Candidate, thesis: dict, *, tools=None, decide=None,
                         max_steps: int = None, step_timeout: float = None,
                         total_timeout: float = None):
    """Generator form of the loop — the single source of truth `run_diligence` (blocking) and
    the web UI's streaming job (live progress) both drive. Yields one dict per step as it
    happens — `{"event": "step", "tool", "reason", "args", "sources", "timed_out"}` or
    `{"event": "finish", "reason"}` — then a final `{"event": "done", "agent", "trail",
    "sources", "memo", "status", "budget"}` where status is 'complete' or 'incomplete' (cut
    short by a per-step or the overall deadline) and budget reports steps used vs.
    SIGNAL_AGENT_MAX_STEPS and elapsed time vs. SIGNAL_AGENT_TOTAL_TIMEOUT_S — the same
    numbers `_prepend_trail` renders into the memo's trail footer.

    Bounded on two axes: each step (a decide() call OR a single tool call) is wrapped in
    `_call_with_timeout` (default 20s, `SIGNAL_AGENT_STEP_TIMEOUT_S`), and the whole loop has
    an overall deadline (default 90s, `SIGNAL_AGENT_TOTAL_TIMEOUT_S`) checked before every step.
    Either kind of timeout stops the loop early (or, for a tool timeout, just records the
    observation and continues) — never hangs the caller — and still synthesises a memo from
    whatever evidence was gathered so far: no-fabrication holds unconditionally because
    memo.build_memo only ever cites `candidate.raw['source_urls']`, which just has fewer
    entries on a partial run.
    """
    if decide is None:
        env.load_env()  # so the provider gate below sees keys from .env (build_memo also loads it)
    if decide is None and not llm.any_available():
        yield {"event": "done", "agent": False, "trail": [], "sources": [],
              "memo": memo.build_memo(candidate, thesis), "status": "complete"}
        return

    tools = default_tools() if tools is None else tools
    decide = _make_decider() if decide is None else decide
    steps = _max_steps() if max_steps is None else max_steps
    step_timeout = _step_timeout() if step_timeout is None else step_timeout
    total_timeout = _total_timeout() if total_timeout is None else total_timeout
    start = time.monotonic()
    deadline = start + total_timeout

    goal = candidate.name
    transcript, trail, sources, seen = [], [], [], set()
    status = "complete"

    for _ in range(steps):
        if time.monotonic() >= deadline:
            entry = {"tool": "finish", "reason": f"overall deadline exceeded (>{total_timeout:.0f}s)"}
            trail.append(entry)
            status = "incomplete"
            yield {"event": "finish", **entry}
            break

        action, timed_out, err = _call_with_timeout(decide, step_timeout, goal, thesis, transcript)
        if timed_out:
            entry = {"tool": "finish", "reason": f"decision step timed out (>{step_timeout:.0f}s)"}
            trail.append(entry)
            status = "incomplete"
            yield {"event": "finish", **entry}
            break
        if err is not None:  # noqa: BLE001 — a broken decision must not crash the run
            entry = {"tool": "finish", "reason": f"decider error: {type(err).__name__}"}
            trail.append(entry)
            yield {"event": "finish", **entry}
            break
        if not isinstance(action, dict) or action.get("action") == "finish":
            reason = action.get("reason", "done") if isinstance(action, dict) else "done"
            entry = {"tool": "finish", "reason": reason}
            trail.append(entry)
            yield {"event": "finish", **entry}
            break

        name = action.get("tool")
        args = action.get("args") if isinstance(action.get("args"), dict) else {}
        key = f"{name}|{json.dumps(args, sort_keys=True, default=str)}"
        if key in seen:  # dedupe identical repeated calls — don't re-execute (bounded/cost)
            transcript.append({"tool": name, "args": args, "observation": {"skipped": "duplicate call"}})
            continue
        seen.add(key)

        fn = (tools or {}).get(name)
        if fn is None:
            obs, tool_timed_out = {"error": f"unknown tool: {name}"}, False
        else:
            obs, tool_timed_out, tool_err = _call_with_timeout(fn, step_timeout, args, candidate)
            if tool_timed_out:
                obs = {"error": "timeout", "note": f"tool exceeded {step_timeout:.0f}s — treated as unavailable"}
            elif tool_err is not None:  # noqa: BLE001 — a tool failure is an observation, not a crash
                obs = {"error": f"{type(tool_err).__name__}: {tool_err}"}
        if not isinstance(obs, dict):
            obs = {"result": obs}
        if tool_timed_out:
            status = "incomplete"

        step_srcs = [u for u in (obs.get("sources") or []) if u]
        for u in step_srcs:
            if u not in sources:
                sources.append(u)
        entry = {"tool": name, "reason": action.get("reason", ""), "args": args,
                "sources": step_srcs, "timed_out": tool_timed_out}
        trail.append(entry)
        yield {"event": "step", **entry}
        transcript.append({"tool": name, "args": args, "observation": obs})

    # Feed the retrieved sources to the candidate so the memo may cite ONLY these (verification
    # in memo._llm_memo drops anything else), then synthesise via the existing memo path.
    urls = list(candidate.raw.get("source_urls", []))
    for u in sources:
        if u not in urls:
            urls.append(u)
    candidate.raw["source_urls"] = urls

    # Pin the provider the loop actually got working (skipping any dead one) so the memo synthesis
    # uses it too — instead of retrying the dead pinned provider and falling back to a heuristic memo.
    picked = getattr(decide, "picked", {}).get("p") if hasattr(decide, "picked") else None
    if picked:
        os.environ["SIGNAL_LLM_PROVIDER"] = picked

    budget = {
        "steps_used": sum(1 for e in trail if e.get("tool") != "finish"),
        "steps_max": steps,
        "elapsed_s": time.monotonic() - start,
        "step_timeout_s": step_timeout,
        "total_timeout_s": total_timeout,
        "status": status,
    }
    body = memo.build_memo(candidate, thesis)
    yield {"event": "done", "agent": True, "trail": trail, "sources": sources,
          "memo": _prepend_trail(body, trail, budget), "status": status, "budget": budget}


def run_diligence(candidate: Candidate, thesis: dict, *, tools=None, decide=None,
                  max_steps: int = None, step_timeout: float = None,
                  total_timeout: float = None) -> dict:
    """Blocking wrapper: drains run_diligence_events() and returns its final 'done' payload
    (minus the 'event' key) — {agent, trail, sources, memo, status}. Callers that want live
    progress (the web UI) should iterate run_diligence_events() directly instead."""
    last = None
    for ev in run_diligence_events(candidate, thesis, tools=tools, decide=decide,
                                   max_steps=max_steps, step_timeout=step_timeout,
                                   total_timeout=total_timeout):
        last = ev
    return {k: v for k, v in last.items() if k != "event"}
