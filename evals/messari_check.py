"""Offline check for the Messari Tier-2 integration (no key, no network).

Asserts: (a) a late-stage fixture candidate gets the stage down-rank (and a pre-seed one does
not), and the tier-1 lead-investor corroboration applies; (b) without MESSARI_API_KEY, enrich
is a no-op (contributes 0) and a memo still generates; (c) the defensive parsers handle the
fixture shapes.

    PYTHONPATH=src python evals/messari_check.py
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml  # noqa: E402

from signalfund.sources import messari  # noqa: E402
from signalfund.scoring import messari_adj, HeuristicScorer  # noqa: E402
from signalfund.models import Candidate  # noqa: E402
from signalfund import memo as memo_mod  # noqa: E402


def main() -> int:
    thesis = yaml.safe_load((ROOT / "config" / "thesis.yaml").read_text())

    # (c) defensive parsers handle the fixture shapes
    funding = messari.parse_funding(json.loads((ROOT / "data/fixtures/messari_funding.json").read_text()))
    assert funding["stage"] == "Series B", funding
    assert funding["total_raised_usd"] == 83000000, funding
    assert "Polychain Capital" in funding["lead_investors"] and "Archetype" in funding["lead_investors"], funding
    research = messari.parse_research(json.loads((ROOT / "data/fixtures/messari_research.json").read_text()))
    assert research and "Polychain" in research, research

    # (a) STAGE GATE: late-stage candidate down-ranked; pre-seed not.
    late = Candidate(name="NavaLike", source="x", url="",
                     summary="agent guardrails: intent vs execution policy enforcement for AI financial agents.",
                     tags=["agent_control_planes"], raw={"messari": {"funding": funding}})
    adj_late, flags_late, notes_late = messari_adj(thesis, late)
    assert adj_late < 0 and flags_late, f"late stage must down-rank + flag, got {adj_late}, {flags_late}"
    assert any("stage gate" in f.lower() for f in flags_late), flags_late
    assert any("polychain" in n.lower() for n in notes_late), notes_late  # tier-1 corroboration note

    pre = Candidate(name="Stealth", source="x", url="",
                    summary="pre-seed agent permissioning layer.",
                    tags=["agent_control_planes"],
                    raw={"messari": {"funding": {"stage": "Seed", "total_raised_usd": 3_000_000,
                                                 "lead_investors": []}}})
    adj_pre, flags_pre, _ = messari_adj(thesis, pre)
    assert adj_pre == 0.0 and not flags_pre, f"pre-seed must NOT be stage-gated, got {adj_pre}, {flags_pre}"

    # end-to-end: same candidate scores LOWER with the late-stage messari data than without it
    scorer = HeuristicScorer(thesis)
    base = Candidate(name=late.name, source="x", url="", summary=late.summary, tags=late.tags, raw={})
    s_late = scorer.score(late)
    s_base = scorer.score(base)
    assert s_late.score < s_base.score, f"stage gate should lower the score: {s_late.score} vs {s_base.score}"
    assert any("stage gate" in str(f).lower() for f in s_late.flags), s_late.flags

    # (b) NO key -> enrich is a no-op (contributes 0), research is "", a memo still generates
    os.environ.pop("MESSARI_API_KEY", None)
    os.environ["SIGNAL_LLM_PROVIDER"] = "heuristic"   # deterministic offline memo
    c = Candidate(name="NoKeyCo", source="x", url="https://example.com",
                  summary="agent settlement and permission layer.", tags=["agent_control_planes"], raw={})
    messari.enrich(c)
    assert "messari" not in c.raw, "enrich must be a no-op without a key"
    assert messari.research_context(c, thesis) == "", "research_context must be '' without a key"
    md = memo_mod.build_memo(c, thesis)
    assert isinstance(md, str) and len(md) > 50, "memo must still generate without a Messari key"

    print(f"messari check: PASS  (late Series B/${funding['total_raised_usd']/1e6:.0f}M -> adj {adj_late} "
          f"[stage gate + tier-1 lead]; pre-seed adj {adj_pre}; no key -> enrich no-op + memo OK)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
