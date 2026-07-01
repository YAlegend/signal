"""Offline check for the tool-using diligence agent (no keys, no network).

Drives agent.run_diligence with a STUB decider (a scripted JSON-action sequence) and STUB tools,
and asserts the loop:
  (a) dispatches the chosen tools and accumulates observations + their source URLs,
  (b) respects SIGNAL_AGENT_MAX_STEPS,
  (c) dedupes an identical repeated tool call (executes it once),
  (d) produces a memo containing the Diligence trail and ONLY verified citations,
  (e) falls back to the single-shot memo with no provider — no crash.

    PYTHONPATH=src python evals/agent_check.py
"""
from __future__ import annotations

import pathlib
import re
import sys

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

    print("agent check: PASS  (loop dispatched 2 tools, deduped the repeat, respected max_steps=2, "
          "trail + verified-only citations in memo, graceful single-shot fallback)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
