"""Signal web UI — an interactive, zero-dependency local dashboard.

Backend on Python's stdlib ``http.server`` (no Flask / FastAPI / new pip deps).
It serves a vanilla-JS single-page app and a small JSON API that drives the real
pipeline: run sourcing, browse the ranked digest, generate memos, edit the
thesis, and run the Phase 0 backtest — all from the browser.

    PYTHONPATH=src python -m signalfund.webapp              # http://127.0.0.1:8000
    PYTHONPATH=src python -m signalfund.webapp --port 8765
    PYTHONPATH=src python -m signalfund.webapp --no-open    # don't auto-open a browser

Offline-first: with no API keys it runs the demo path (bundled fixtures, heuristic
scorer), exactly like the CLI. Binds to localhost only.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import pathlib
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import yaml

from . import backtest as backtest_mod
from . import llm
from . import memo as memo_mod
from . import orchestrator
from .models import Candidate

ROOT = pathlib.Path(__file__).resolve().parents[2]
WEB = pathlib.Path(__file__).resolve().parent / "web"
THESIS_PATH = ROOT / "config" / "thesis.yaml"
# Append-only human-feedback log (👍/👎 on surfaced candidates). Rows are
# eval-compatible (name/summary/tags/label) so they can later seed eval_set.jsonl.
FEEDBACK_PATH = ROOT / "data" / "feedback.jsonl"

_STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
}


def _out_dir() -> pathlib.Path:
    return pathlib.Path(os.getenv("SIGNAL_OUT_DIR", "out"))


def _read_out_json(name: str):
    p = _out_dir() / name
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    return None


def _list_memos() -> list:
    mdir = _out_dir() / "memos"
    if not mdir.exists():
        return []
    return [p.name for p in sorted(mdir.glob("*.md"))]


# Composite signals the user can toggle in the UI. `tier`: free = no paid key needed;
# premium = needs a paid API key (the user may still enable it — it just contributes 0
# without the key, graceful absence). `env` is the API key checked for key_present.
SIGNALS = [
    {"name": "code_health",   "tier": "free",    "env": "GITHUB_TOKEN"},
    {"name": "onchain",       "tier": "free",    "env": None,
     "label": "onchain · DefiLlama", "group": "onchain"},
    {"name": "nansen",        "tier": "premium", "env": "NANSEN_API_KEY",
     "label": "onchain · Nansen (smart-money)", "group": "onchain"},
    {"name": "social",        "tier": "free",    "env": "NEYNAR_API_KEY"},
    {"name": "pre_public",    "tier": "free",    "env": "EVERTRACE_API_KEY"},
    # `team` is dual-tier — the two paths toggle independently:
    {"name": "team_github",   "tier": "free",    "env": "GITHUB_TOKEN",
     "label": "team · GitHub", "group": "team"},
    {"name": "team_harmonic", "tier": "premium", "env": "HARMONIC_API_KEY",
     "label": "team · Harmonic", "group": "team"},
    {"name": "messari",       "tier": "premium", "env": "MESSARI_API_KEY",
     "label": "funding / stage-gate · Messari"},
]


def _signals_state() -> list:
    """Per-signal tier, display label, and whether its key is present (free signals with
    no key -> True)."""
    return [{"name": s["name"], "tier": s["tier"], "env": s["env"],
             "label": s.get("label", s["name"]), "group": s.get("group"),
             "key_present": (s["env"] is None) or bool(os.getenv(s["env"]))}
            for s in SIGNALS]


# Scorer-model dropdown options for the UI. "auto" + "heuristic" are always available;
# the rest mirror llm.PROVIDERS and report whether their key/endpoint is present.
_PROVIDER_UI = [
    ("auto", "Auto (best available)", None),
    ("anthropic", "Claude", "ANTHROPIC_API_KEY"),
    ("groq", "Groq (free)", "GROQ_API_KEY"),
    ("gemini", "Gemini (free)", "GEMINI_API_KEY"),
    ("openrouter", "OpenRouter (free)", "OPENROUTER_API_KEY"),
    ("ollama", "Local (Ollama)", "OLLAMA_BASE_URL"),
    ("heuristic", "Heuristic (no LLM)", None),
]


def _providers_state() -> list:
    out = []
    for name, label, env in _PROVIDER_UI:
        always = name in ("auto", "heuristic")
        out.append({"name": name, "label": label, "env": env,
                    "available": True if always else llm._provider_available(name),
                    "model": None if always else llm.provider_model(name)})
    return out


def _scorer_label() -> str:
    """Human label for the scorer that WOULD run now (honours SIGNAL_LLM_PROVIDER)."""
    p = llm.current_provider()
    return "HeuristicScorer" if p == "heuristic" else f"LLMScorer ({p})"


def _apply_scorer_provider(body: dict) -> None:
    """Set SIGNAL_LLM_PROVIDER from a request's `scorer_provider` for this run.
    'auto' clears it (auto-order); a provider name pins it; unknown is ignored."""
    prov = body.get("scorer_provider")
    if not isinstance(prov, str) or not prov:
        return
    if prov == "auto":
        os.environ.pop("SIGNAL_LLM_PROVIDER", None)
    else:
        os.environ["SIGNAL_LLM_PROVIDER"] = prov


def _feedback_votes() -> dict:
    """Collapse the append-only feedback log to the latest vote per candidate.

    Returns {name: "up"|"down"} — entries whose latest row is a "clear" are dropped.
    """
    if not FEEDBACK_PATH.exists():
        return {}
    latest = {}
    for line in FEEDBACK_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        latest[row.get("name")] = row.get("label")
    return {name: lbl for name, lbl in latest.items() if lbl in ("up", "down")}


class Handler(BaseHTTPRequestHandler):
    server_version = "SignalWeb"

    # ---- low-level responders ---------------------------------------------
    def _send(self, body: bytes, ctype: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, status: int = 200) -> None:
        # default=str so YAML-parsed dates (e.g. thesis `updated:`) serialize cleanly
        self._send(json.dumps(obj, default=str).encode("utf-8"), "application/json", status)

    def _static(self, filename: str) -> None:
        path = (WEB / filename).resolve()
        if not str(path).startswith(str(WEB)) or not path.is_file():
            return self._json({"error": "not found"}, 404)
        ctype = _STATIC_TYPES.get(path.suffix, "application/octet-stream")
        self._send(path.read_bytes(), ctype)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return {}

    def log_message(self, fmt, *args):  # quieter console
        pass

    # ---- routing ----------------------------------------------------------
    def do_GET(self):
        route = urlparse(self.path)
        path, query = route.path, parse_qs(route.query)
        if path == "/" or path == "/index.html":
            return self._static("index.html")
        if path in ("/app.js", "/styles.css"):
            return self._static(path.lstrip("/"))
        if path == "/api/state":
            return self._json(self._state())
        if path == "/api/digest":
            return self._json(_read_out_json("digest.json") or [])
        if path == "/api/backtest":
            return self._json(_read_out_json("backtest_report.json"))
        if path == "/api/memos":
            return self._json({"memos": _list_memos()})
        if path == "/api/feedback":
            return self._json({"votes": _feedback_votes()})
        if path == "/api/memo":
            return self._get_memo(query.get("name", [""])[0])
        if path == "/api/thesis":
            return self._json({"text": THESIS_PATH.read_text(encoding="utf-8")})
        return self._json({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._body()
        if path == "/api/run":
            return self._run(body)
        if path == "/api/backtest":
            return self._backtest()
        if path == "/api/memo":
            return self._make_memo(body)
        if path == "/api/feedback":
            return self._feedback(body)
        return self._json({"error": "not found"}, 404)

    def do_PUT(self):
        if urlparse(self.path).path == "/api/thesis":
            return self._save_thesis(self._body())
        return self._json({"error": "not found"}, 404)

    # ---- handlers ---------------------------------------------------------
    def _state(self) -> dict:
        thesis_text = THESIS_PATH.read_text(encoding="utf-8")
        try:
            parsed = yaml.safe_load(thesis_text)
        except yaml.YAMLError:
            parsed = None
        return {
            "digest": _read_out_json("digest.json"),
            "backtest": _read_out_json("backtest_report.json"),
            "memos": _list_memos(),
            "thesis": thesis_text,
            "thesisParsed": parsed,
            "outDir": str(_out_dir()),
            "scorer": _scorer_label(),
            "providers": _providers_state(),
            "current": llm.current_provider(),
            "signals": _signals_state(),
            "feedback": _feedback_votes(),
        }

    def _run(self, body: dict) -> None:
        demo = bool(body.get("demo", True))
        try:
            limit = max(1, int(body.get("limit", 25)))
        except (TypeError, ValueError):
            limit = 25
        # User-selected signals. A list -> only those contribute; absent/None -> all on.
        es = body.get("enabled_signals")
        enabled = {s for s in es if isinstance(s, str)} if isinstance(es, list) else None
        _apply_scorer_provider(body)   # user-chosen LLM provider for this run
        buf = io.StringIO()
        ok, err = True, None
        try:
            with contextlib.redirect_stdout(buf):
                orchestrator.run(demo=demo, limit=limit, enabled_signals=enabled)
        except Exception as e:  # live sources may fail without keys — surface, don't crash
            ok, err = False, f"{type(e).__name__}: {e}"
        self._json({"ok": ok, "error": err, "log": buf.getvalue(),
                    "scorer": _scorer_label(),  # the scorer that actually ran
                    "digest": _read_out_json("digest.json") or []})

    def _backtest(self) -> None:
        gt = str(ROOT / "data" / "backtest" / "ground_truth.sample.json")
        buf = io.StringIO()
        ok, err = True, None
        try:
            with contextlib.redirect_stdout(buf):
                backtest_mod.run(gt)
        except Exception as e:
            ok, err = False, f"{type(e).__name__}: {e}"
        self._json({"ok": ok, "error": err, "log": buf.getvalue(),
                    "backtest": _read_out_json("backtest_report.json")})

    def _get_memo(self, name: str) -> None:
        if not name or "/" in name or ".." in name:
            return self._json({"error": "bad name"}, 400)
        path = _out_dir() / "memos" / name
        if not path.is_file():
            return self._json({"error": "not found"}, 404)
        self._json({"name": name, "markdown": path.read_text(encoding="utf-8")})

    def _make_memo(self, body: dict) -> None:
        digest = _read_out_json("digest.json") or []
        try:
            idx = int(body.get("index", 0))
        except (TypeError, ValueError):
            idx = -1
        if idx < 0 or idx >= len(digest):
            return self._json({"ok": False, "error": "no such candidate"}, 400)
        cand = digest[idx].get("candidate", {})
        try:
            c = Candidate(**cand)
        except TypeError:
            c = Candidate(name=cand.get("name", "?"), source=cand.get("source", ""),
                          url=cand.get("url", ""), summary=cand.get("summary", ""),
                          signal_metric=cand.get("signal_metric", ""),
                          tags=cand.get("tags", []), raw=cand.get("raw", {}))
        thesis = yaml.safe_load(THESIS_PATH.read_text(encoding="utf-8"))
        _apply_scorer_provider(body)   # user-chosen LLM provider for this memo
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            md = memo_mod.build_memo(c, thesis)
        out = _out_dir() / "memos"
        out.mkdir(parents=True, exist_ok=True)
        fname = f"{memo_mod._slug(c.name)}.md"
        (out / fname).write_text(md, encoding="utf-8")
        self._json({"ok": True, "name": fname, "markdown": md, "log": buf.getvalue(),
                    "scorer": _scorer_label()})

    def _feedback(self, body: dict) -> None:
        """Record a 👍/👎 (or 'clear') on a digest candidate, by digest index.

        Appends an eval-compatible row to data/feedback.jsonl. 'up' = on-thesis
        (eval label True), 'down' = off-thesis (False), 'clear' = retract.
        """
        label = body.get("label")
        if label not in ("up", "down", "clear"):
            return self._json({"ok": False, "error": "label must be up/down/clear"}, 400)
        digest = _read_out_json("digest.json") or []
        try:
            idx = int(body.get("index", -1))
        except (TypeError, ValueError):
            idx = -1
        if idx < 0 or idx >= len(digest):
            return self._json({"ok": False, "error": "no such candidate"}, 400)
        entry = digest[idx]
        cand = entry.get("candidate", {})
        eval_label = {"up": True, "down": False, "clear": None}[label]
        row = {
            "name": cand.get("name"),
            "source": cand.get("source"),
            "summary": cand.get("summary", ""),
            "tags": cand.get("tags", []),
            "label": label,            # up | down | clear (audit value)
            "eval_label": eval_label,  # True | False | None — for seeding eval_set.jsonl
            "score": entry.get("score"),
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
        with FEEDBACK_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        self._json({"ok": True, "name": row["name"], "votes": _feedback_votes()})

    def _save_thesis(self, body: dict) -> None:
        # Two ways to save: a structured object from the sectioned editor (preferred —
        # keeps unknown keys like `updated`), or raw YAML text from the Advanced fallback.
        if isinstance(body.get("thesis"), dict):
            try:
                text = yaml.safe_dump(body["thesis"], sort_keys=False, allow_unicode=True)
                parsed = yaml.safe_load(text)          # re-parse to validate the round-trip
                if not isinstance(parsed, dict):
                    raise ValueError("thesis must be a mapping")
            except (yaml.YAMLError, ValueError) as e:
                return self._json({"ok": False, "error": f"Invalid thesis: {e}"}, 400)
        else:
            text = body.get("text", "")
            try:
                parsed = yaml.safe_load(text)
                if not isinstance(parsed, dict):
                    raise ValueError("thesis must be a YAML mapping")
            except (yaml.YAMLError, ValueError) as e:
                return self._json({"ok": False, "error": f"Invalid YAML: {e}"}, 400)
        THESIS_PATH.write_text(text, encoding="utf-8")
        self._json({"ok": True, "thesisParsed": parsed, "text": text})


def serve(host: str = "127.0.0.1", port: int = 8000, open_browser: bool = True) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}"
    print(f"[signal-web] serving Signal UI at {url}  (Ctrl+C to stop)")
    print(f"[signal-web] output dir: {_out_dir()}  ·  thesis: {THESIS_PATH}")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[signal-web] stopped.")
    finally:
        httpd.server_close()


def main():
    # Defaults are env-configurable so the SAME code runs localhost-only locally and binds
    # 0.0.0.0 on a PaaS — without changing local behavior. Flags still override env.
    #   SIGNAL_WEB_HOST  local default 127.0.0.1; hosted demo sets 0.0.0.0
    #   PORT             injected by most PaaS (Render/Heroku/Fly); falls back to SIGNAL_WEB_PORT, then 8000
    default_host = os.getenv("SIGNAL_WEB_HOST", "127.0.0.1")
    default_port = int(os.getenv("PORT", os.getenv("SIGNAL_WEB_PORT", "8000")))
    p = argparse.ArgumentParser(description="Signal — interactive web UI (stdlib, zero deps)")
    p.add_argument("--host", default=default_host,
                   help="bind host (default: localhost only; env SIGNAL_WEB_HOST)")
    p.add_argument("--port", type=int, default=default_port,
                   help="bind port (default: env PORT / SIGNAL_WEB_PORT / 8000)")
    p.add_argument("--no-open", action="store_true", help="don't auto-open a browser")
    args = p.parse_args()
    serve(host=args.host, port=args.port, open_browser=not args.no_open)


if __name__ == "__main__":
    main()
