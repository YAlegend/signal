"""Offline check for the tool-using diligence agent (no keys, no network).

Drives agent.run_diligence with a STUB decider (a scripted JSON-action sequence) and STUB tools,
and asserts the loop:
  (a) dispatches the chosen tools and accumulates observations + their source URLs,
  (b) respects SIGNAL_AGENT_MAX_STEPS,
  (c) dedupes an identical repeated tool call (executes it once),
  (d) produces a memo containing the Diligence trail and ONLY verified citations,
  (e) falls back to the single-shot memo with no provider — no crash.
  (f) a slow TOOL step returns within the per-step deadline (doesn't block on it) and the run
      continues, with the timeout recorded as an observation, not a crash.
  (g) a slow DECIDE step returns within the per-step deadline, ending the loop early
      ('incomplete' status) rather than hanging.
  (h) a short overall deadline cuts the loop off before the first step.
  (i) no-fabrication holds on a partial/timed-out run: the memo cites only gathered sources.

    PYTHONPATH=src python evals/agent_check.py
"""
from __future__ import annotations

import pathlib
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from signalfund import agent, llm  # noqa: E402
from signalfund.models import Candidate  # noqa: E402

# Force everything hermetic: no provider => heuristic scorer + heuristic (offline) memo, no network.
llm.any_available = lambda: False
llm.current_provider = lambda: "heuristic"

THESIS = {"thesis_summary": "control planes for agent-native crypto", "themes": []}


def scripted(actions):
    seq = iter(actions)

    def decide(goal, thesis, transcript):
        try:
            return next(seq)
        except StopIteration:
            return {"action": "finish", "reason": "end of script"}
    return decide


def main() -> int:
    calls = {"gh": 0, "oc": 0}

    def stub_github(args, cand):
        calls["gh"] += 1
        cand.raw["commit_accel"] = 1.8
        return {"commit_accel": 1.8, "contributors": 7, "sources": ["https://github.com/x/y"]}

    def stub_onchain(args, cand):
        calls["oc"] += 1
        cand.raw["real_tvl"] = 420000  # a real tool enriches candidate.raw; the stub mirrors that
        return {"real_tvl": 420000, "sources": ["https://defillama.com/protocol/x"]}

    tools = {"github_velocity": stub_github, "onchain_metrics": stub_onchain}

    # (a)+(c): call gh, call onchain, REPEAT gh with identical args (must dedupe), then finish.
    actions = [
        {"action": "call_tool", "tool": "github_velocity", "args": {"owner": "x", "repo": "y"}, "reason": "code health"},
        {"action": "call_tool", "tool": "onchain_metrics", "args": {"name": "x"}, "reason": "real usage"},
        {"action": "call_tool", "tool": "github_velocity", "args": {"owner": "x", "repo": "y"}, "reason": "dup"},
        {"action": "finish", "reason": "enough evidence"},
    ]
    c = Candidate(name="AcmeAgent", source="test", url="https://acme.xyz", summary="agent policy layer")
    res = agent.run_diligence(c, THESIS, tools=tools, decide=scripted(actions), max_steps=6)

    assert res["agent"] is True, res
    assert calls == {"gh": 1, "oc": 1}, f"dedupe failed — tool executed twice: {calls}"
    assert res["sources"] == ["https://github.com/x/y", "https://defillama.com/protocol/x"], res["sources"]
    assert c.raw.get("commit_accel") == 1.8 and c.raw.get("real_tvl") == 420000, "observations not merged onto candidate"
    tools_in_trail = [s["tool"] for s in res["trail"]]
    assert tools_in_trail == ["github_velocity", "onchain_metrics", "finish"], tools_in_trail

    memo_md = res["memo"]
    assert "## Diligence trail" in memo_md, "memo missing the Diligence trail"
    assert "github_velocity" in memo_md and "onchain_metrics" in memo_md, "trail didn't list the tools"
    # (d) only verified citations: every URL in the memo is a gathered source or the company's own url.
    allowed = set(res["sources"]) | {c.url}
    urls = re.findall(r"https?://[^\s,)\]]+", memo_md)
    unverified = [u for u in urls if u not in allowed]
    assert not unverified, f"memo contains unverified citation(s): {unverified}"
    assert set(res["sources"]).issubset(set(urls)), "gathered sources not visible in the memo"

    # (b) MAX_STEPS: a decider that never finishes must stop at max_steps tool calls.
    step_calls = {"n": 0}

    def counting_tool(args, cand):
        step_calls["n"] += 1
        return {"ok": True, "sources": []}

    never_finish = scripted([{"action": "call_tool", "tool": "t", "args": {"i": i}, "reason": "x"}
                             for i in range(50)])
    c2 = Candidate(name="Loopy", source="test", url="https://loopy.xyz")
    agent.run_diligence(c2, THESIS, tools={"t": counting_tool}, decide=never_finish, max_steps=2)
    assert step_calls["n"] == 2, f"MAX_STEPS not respected: {step_calls['n']} calls (expected 2)"

    # (e) graceful fallback: no provider + no explicit decider -> single-shot memo, no loop, no crash.
    c3 = Candidate(name="FallbackCo", source="test", url="https://fb.xyz", summary="wallet infra")
    fb = agent.run_diligence(c3, THESIS)
    assert fb["agent"] is False and fb["trail"] == [], fb
    assert "Investment Memo" in fb["memo"] and "Diligence trail" not in fb["memo"], "fallback should be single-shot"
    assert fb["status"] == "complete", fb["status"]

    # (f) a slow TOOL (sleeps 2s) with a 0.3s step deadline must not block the caller for 2s —
    # the call returns quickly, the timeout is recorded as an observation, and the loop continues
    # to the next scripted step rather than crashing or hanging.
    def slow_tool(args, cand):
        time.sleep(2.0)
        return {"ok": True, "sources": ["https://slow.example/never-cited"]}  # never reached in time

    def fast_tool(args, cand):
        return {"ok": True, "sources": ["https://fast.example/real"]}

    slow_then_fast = scripted([
        {"action": "call_tool", "tool": "slow", "args": {}, "reason": "will time out"},
        {"action": "call_tool", "tool": "fast", "args": {}, "reason": "quick follow-up"},
        {"action": "finish", "reason": "done"},
    ])
    c4 = Candidate(name="SlowToolCo", source="test", url="https://slowtoolco.xyz")
    t0 = time.perf_counter()
    res_slow = agent.run_diligence(c4, THESIS, tools={"slow": slow_tool, "fast": fast_tool},
                                   decide=slow_then_fast, max_steps=5, step_timeout=0.3)
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.5, f"slow tool should not block the caller (took {elapsed:.2f}s)"
    assert res_slow["status"] == "incomplete", res_slow["status"]
    assert res_slow["sources"] == ["https://fast.example/real"], \
        f"the timed-out tool's source must NOT be gathered: {res_slow['sources']}"
    slow_step = next(s for s in res_slow["trail"] if s.get("tool") == "slow")
    assert slow_step.get("timed_out") is True, slow_step

    # (g) a slow DECIDE (sleeps 2s) with a 0.3s step deadline ends the loop early instead of
    # hanging — the caller returns quickly with an 'incomplete' status and a 'finish' reason
    # naming the timeout.
    calls = {"n": 0}

    def slow_decide(goal, thesis, transcript):
        calls["n"] += 1
        time.sleep(2.0)
        return {"action": "call_tool", "tool": "fast", "args": {}, "reason": "never reached in time"}

    c5 = Candidate(name="SlowDecideCo", source="test", url="https://slowdecideco.xyz")
    t0 = time.perf_counter()
    res_decide = agent.run_diligence(c5, THESIS, tools={"fast": fast_tool}, decide=slow_decide,
                                     max_steps=5, step_timeout=0.3)
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.5, f"slow decide should not block the caller (took {elapsed:.2f}s)"
    assert res_decide["status"] == "incomplete", res_decide["status"]
    assert res_decide["trail"] and "timed out" in res_decide["trail"][-1]["reason"], res_decide["trail"]
    assert res_decide["sources"] == [], "no tool ever ran — nothing should be gathered"

    # (h) an OVERALL deadline that's already passed (0s) cuts the loop off before even the
    # first step — the deadline is checked before every step, not just after a slow one.
    c6 = Candidate(name="DeadlineCo", source="test", url="https://deadlineco.xyz")
    res_deadline = agent.run_diligence(
        c6, THESIS, tools={"fast": fast_tool},
        decide=scripted([{"action": "call_tool", "tool": "fast", "args": {}, "reason": "x"}] * 5),
        max_steps=5, step_timeout=5, total_timeout=0)
    assert res_deadline["status"] == "incomplete", res_deadline["status"]
    assert "deadline exceeded" in res_deadline["trail"][-1]["reason"], res_deadline["trail"]
    assert res_deadline["sources"] == [], "the overall deadline hit before any tool call"

    # (i) no-fabrication holds on a partial/timed-out run: every URL in the memo is a gathered
    # source or the candidate's own URL — same verification as (d), applied to a timed-out run.
    for partial_res, cand in ((res_slow, c4), (res_decide, c5)):
        allowed = set(partial_res["sources"]) | {cand.url}
        urls = re.findall(r"https?://[^\s,)\]]+", partial_res["memo"])
        unverified = [u for u in urls if u not in allowed]
        assert not unverified, f"partial-run memo contains unverified citation(s): {unverified}"
        assert "https://slow.example/never-cited" not in partial_res["memo"], \
            "a source from a timed-out tool call must never be cited"

    # (j) S-10: every agent run reports a budget (steps used vs. cap, elapsed vs. the overall
    # deadline) and prints it in the memo's trail footer — both on a clean finish and on a
    # capped/partial one, so a reader can see at a glance whether a run was cut short.
    assert res["budget"]["steps_used"] == 2, res["budget"]
    assert res["budget"]["steps_max"] == 6, res["budget"]
    assert res["budget"]["status"] == "complete", res["budget"]
    assert f"Budget: {res['budget']['steps_used']}/6 steps" in memo_md, memo_md

    assert res_deadline["budget"]["steps_used"] == 0, res_deadline["budget"]
    assert res_deadline["budget"]["status"] == "incomplete", res_deadline["budget"]
    assert "Budget: 0/5 steps" in res_deadline["memo"], res_deadline["memo"]
    assert "status: incomplete" in res_deadline["memo"], res_deadline["memo"]

    print("agent check: PASS  (loop dispatched 2 tools, deduped the repeat, respected max_steps=2, "
          "trail + verified-only citations in memo, graceful single-shot fallback, "
          f"slow tool bounded to {elapsed:.2f}s < its 2s sleep, slow decide + overall deadline "
          "both end the loop early with status=incomplete, budget reported + footer rendered on "
          "both clean and capped runs, and no-fabrication holds throughout)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
