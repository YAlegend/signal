"""Offline check for the credibility HARD/SOFT flag split (no keys, no network).

Encodes the fix: SOFT/informational flags (early-stage, hackathon, no recent commits,
unconfirmed repo) must NOT penalise credibility — a weak/absent signal contributes 0 and
must never sink a good-fit company — while HARD anti-signals (ponzi / presale / scam …)
KEEP the strong screen-out penalty.

    PYTHONPATH=src python evals/credibility_check.py
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml  # noqa: E402

from signalfund.scoring import classify_flags, credibility_adj, HeuristicScorer  # noqa: E402
from signalfund.models import Candidate  # noqa: E402

_LONG = ("ENS-aware shell that checks an agent's proposed transaction against policy before "
         "signing; blocks prompt-injection-driven transactions and enforces agent permissions.")


def main() -> int:
    cand = Candidate(name="ENShell", source="watchlist", url="", summary=_LONG, tags=[])

    # 1) SOFT informational flags -> classified soft -> ZERO credibility penalty
    soft_flags = ["no recent commits", "hackathon project", "unconfirmed repository",
                  "small team", "early-stage"]
    hard, soft = classify_flags(soft_flags)
    assert hard == [], f"informational flags must not be HARD: {hard}"
    assert len(soft) == 5, soft
    adj_soft, _ = credibility_adj(cand, ["agent_control_planes", "ai_x_crypto"], hard)
    assert adj_soft >= 0, f"SOFT flags must not penalise credibility, got {adj_soft}"

    # 2) HARD anti-signals -> still classified hard -> the full -60 screen-out penalty kept
    hard2, soft2 = classify_flags(["anti-signal: ponzi", "anti-signal: presale", "scam token"])
    assert len(hard2) == 3 and soft2 == [], (hard2, soft2)
    adj_none, _ = credibility_adj(cand, ["x"], [])
    adj_hard, _ = credibility_adj(cand, ["x"], hard2)
    assert adj_none - adj_hard == 60.0, \
        f"HARD anti-signals must levy exactly -60 vs no-flag, got {adj_none - adj_hard}"

    # 3) end-to-end (deterministic heuristic): a real anti-signal candidate STILL screens to 0
    thesis = yaml.safe_load((ROOT / "config" / "thesis.yaml").read_text())
    scorer = HeuristicScorer(thesis)
    scam = Candidate(name="MoonRocket", source="x", url="",
                     summary="meme coin presale promising guaranteed 1000x returns; airdrop farming, pump.",
                     tags=["meme coin", "presale", "airdrop farming"])
    s_scam = scorer.score(scam)
    assert s_scam.score == 0.0, f"hard anti-signal should screen out, got {s_scam.score}"
    assert s_scam.flags and s_scam.subscores["credibility_adj"] <= -55, s_scam.subscores

    # 4) end-to-end: a clean on-thesis lead (no anti-signals) is NOT penalised — credibility
    #    >= 0 and it lands at/above its fit floor (0.6*fit), not zeroed.
    good = Candidate(name="ENShell", source="watchlist",
                     url="https://github.com/0xenshell/sdk", summary=_LONG,
                     tags=["agent_control_planes", "ai_x_crypto"],
                     raw={"hackathon_win": True, "post_event_active": False})
    s_good = scorer.score(good)
    fit = s_good.subscores["fit"]
    assert s_good.subscores["credibility_adj"] >= 0, \
        f"clean lead must not be penalised, got {s_good.subscores['credibility_adj']}"
    assert s_good.score >= round(0.6 * fit, 1) - 0.1, \
        f"fit-{fit} lead should land near its fit floor, got {s_good.score}"
    assert s_good.score > 0 and not s_good.flags, s_good.flags

    print(f"credibility check: PASS  (scam -> {s_scam.score} [hard kept]; "
          f"clean fit-{fit} lead -> {s_good.score}, credibility {s_good.subscores['credibility_adj']} "
          f"[SOFT flags don't penalise])")
    return 0


if __name__ == "__main__":
    sys.exit(main())
