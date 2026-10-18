"""Offline check for the in-browser (Pyodide) demo path — S-16 (no keys, no network).

The GitHub Pages demo runs the real package in the visitor's browser and calls
webapp.dispatch_json() instead of going through http.server. This asserts:
  (a) dispatch() serves every route the SPA uses with the same payloads as the HTTP path:
      state, demo run (heuristic, no keys -> no raise), memo, backtest, 404, bad input -> 400
      (and a bad thesis never overwrites config/thesis.yaml).
  (b) with threads unavailable (Pyodide raises RuntimeError on Thread.start / submit) the
      diligence agent runs INLINE: tools still dispatch, the memo cites ONLY gathered sources
      (no fabrication), and an agent memo job via dispatch() is already 'done' when polled.
  (c) the Pages bundle (docs/py/signal.zip) carries what Python needs and never local secrets
      or private ground truth (.env, *.db, ground_truth.portfolio*).

    PYTHONPATH=src python evals/inbrowser_check.py
"""
from __future__ import annotations

import io
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile
import threading
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from signalfund import agent, llm, webapp  # noqa: E402
from signalfund.models import Candidate  # noqa: E402

# Hermetic: no provider => heuristic scorer + offline memo, exactly like the browser (no keys).
llm.any_available = lambda: False
llm.current_provider = lambda: "heuristic"


def _no_threads(*_a, **_k):
    raise RuntimeError("can't start new thread")


def main() -> int:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="signal-inbrowser-"))
    saved_out = os.environ.get("SIGNAL_OUT_DIR")
    saved_fb = webapp.FEEDBACK_PATH
    os.environ["SIGNAL_OUT_DIR"] = str(tmp / "out")
    webapp.FEEDBACK_PATH = tmp / "feedback.jsonl"
    try:
        # (a) routing parity --------------------------------------------------------------
        status, run = webapp.dispatch("POST", "/api/run", {"demo": True, "scorer_provider": "groq"})
        assert status == 200 and run["ok"] and run["error"] is None, run
        assert run["scorer"] == "HeuristicScorer", run["scorer"]   # keyless provider -> heuristic
        assert run["digest"] and run["digest"][0]["candidate"]["name"] == "veritas-zk/veritas", \
            [d["candidate"]["name"] for d in run["digest"][:3]]

        status, st = webapp.dispatch("GET", "/api/state")
        assert status == 200 and len(st["digest"]) == len(run["digest"]), st.keys()
        # the JSON bridge the browser calls wraps the same payload
        bridged = json.loads(webapp.dispatch_json("GET", "/api/state"))
        assert bridged["status"] == 200 and bridged["data"]["scorer"] == st["scorer"], bridged["status"]

        status, memo = webapp.dispatch("POST", "/api/memo", {"index": 0})
        assert status == 200 and memo["ok"] and memo["markdown"], memo
        status, got = webapp.dispatch("GET", "/api/memo?name=" + memo["name"])
        assert status == 200 and got["markdown"] == memo["markdown"]

        status, bt = webapp.dispatch("POST", "/api/backtest")
        assert status == 200 and bt["ok"] and bt["backtest"], bt

        status, fb = webapp.dispatch("POST", "/api/feedback", {"index": 0, "label": "up"})
        assert status == 200 and fb["votes"] == {"veritas-zk/veritas": "up"}, fb

        assert webapp.dispatch("GET", "/api/nope")[0] == 404
        assert webapp.dispatch("GET", "/api/memo?name=../secrets")[0] == 400
        assert webapp.dispatch("POST", "/api/memo", {"index": 999})[0] == 400
        assert webapp.dispatch("POST", "/api/feedback", {"index": 0, "label": "meh"})[0] == 400
        thesis_before = webapp.THESIS_PATH.read_text(encoding="utf-8")
        status, bad = webapp.dispatch("PUT", "/api/thesis", {"text": "not: [valid"})
        assert status == 400 and "Invalid YAML" in bad["error"], bad
        assert webapp.THESIS_PATH.read_text(encoding="utf-8") == thesis_before, "bad thesis was written"

        # (b) no threads (Pyodide) -> agent runs inline, still cites only what it gathered ----
        real_start, real_submit = threading.Thread.start, agent._EXECUTOR.submit
        threading.Thread.start = _no_threads
        agent._EXECUTOR.submit = _no_threads
        try:
            def stub_github(args, cand):
                return {"commit_accel": 1.4, "sources": ["https://github.com/acme/agent"]}

            def stub_broken(args, cand):
                raise ValueError("upstream 500")

            actions = iter([
                {"action": "call_tool", "tool": "github_velocity", "args": {}, "reason": "code"},
                {"action": "call_tool", "tool": "onchain_metrics", "args": {}, "reason": "usage"},
                {"action": "finish", "reason": "done"},
            ])
            c = Candidate(name="AcmeAgent", source="test", url="https://acme.xyz", summary="agent infra")
            res = agent.run_diligence(c, {"thesis_summary": "x", "themes": []},
                                      tools={"github_velocity": stub_github, "onchain_metrics": stub_broken},
                                      decide=lambda *a: next(actions), max_steps=4)
            assert [s["tool"] for s in res["trail"]] == ["github_velocity", "onchain_metrics", "finish"], \
                res["trail"]
            assert res["sources"] == ["https://github.com/acme/agent"], res["sources"]
            urls = re.findall(r"https?://[^\s,)\]]+", res["memo"])
            unverified = [u for u in urls if u not in set(res["sources"]) | {c.url}]
            assert not unverified, f"inline agent memo cites unverified source(s): {unverified}"

            status, job = webapp.dispatch("POST", "/api/memo", {"index": 1, "agent": True})
            assert status == 200 and job["streaming"], job
            status, prog = webapp.dispatch("GET", "/api/memo/progress?job_id=" + job["job_id"])
            assert status == 200 and prog["status"] == "done", prog   # finished inline, no thread
            assert prog["result"]["ok"] and prog["result"]["markdown"], prog
        finally:
            threading.Thread.start, agent._EXECUTOR.submit = real_start, real_submit

        # (c) bundle contents -------------------------------------------------------------
        import build_static_demo as bsd
        (tmp / "out" / "memos").mkdir(parents=True, exist_ok=True)
        blob = bsd.build_bundle(tmp / "out", {"x.md": "# x"})
        names = set(zipfile.ZipFile(io.BytesIO(blob)).namelist())
        for need in ("src/signalfund/webapp.py", "src/signalfund/orchestrator.py", "config/thesis.yaml",
                     "data/fixtures/sample_candidates.json", "data/backtest/ground_truth.sample.json",
                     "out/digest.json", "out/memos/x.md"):
            assert need in names, f"bundle missing {need}"
        leaks = [n for n in names if n.endswith((".env", ".db")) or "/.env" in n
                 or "ground_truth.portfolio" in n or n.startswith("src/signalfund/web/")]
        assert not leaks, f"bundle must not contain {leaks}"
        assert blob == bsd.build_bundle(tmp / "out", {"x.md": "# x"}), "bundle is not reproducible"

        print(f"inbrowser check: PASS  (dispatch serves state/run/memo/backtest/feedback + 404/400s, "
              f"bad thesis not written; no-thread agent ran inline with verified-only citations and "
              f"the job was done on first poll; bundle has {len(names)} files, no secrets, reproducible)")
        return 0
    finally:
        webapp.FEEDBACK_PATH = saved_fb
        if saved_out is None:
            os.environ.pop("SIGNAL_OUT_DIR", None)
        else:
            os.environ["SIGNAL_OUT_DIR"] = saved_out
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
