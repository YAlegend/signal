"""Offline check for network_radar's diff + convergence logic (no keys, no network).

Loads a before/after fixture of smart-account followings and asserts the pure
convergence function surfaces the right targets — including the reputation gate and the
score that the existing `social` sub-score would produce.

    PYTHONPATH=src python evals/network_radar_check.py
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from signalfund.sources.network_radar import _new_follow_convergence, MIN_CONVERGENCE  # noqa: E402
from signalfund.scoring import social_bonus  # noqa: E402


def main() -> int:
    fx = json.loads((ROOT / "data" / "fixtures" / "network_radar_snapshots.json").read_text())
    prev = {k: set(v) for k, v in fx["before"].items()}
    now = {k: set(v) for k, v in fx["after"].items()}
    reps = fx["smart_account_reputation"]

    # 1) plain convergence: 9999 followed by all 3, 8888 by only 1
    conv = _new_follow_convergence(prev, now)
    assert conv["9999"]["count"] == 3, conv
    assert conv["8888"]["count"] == 1, conv
    surfaced = {t for t, d in conv.items() if d["count"] >= MIN_CONVERGENCE}
    assert surfaced == {"9999"}, f"expected only 9999 to converge, got {surfaced}"

    # 2) reputation gate: drop smart account 1003 (rep 0.20 < floor 0.5)
    gated = _new_follow_convergence(prev, now, reps, min_openrank=0.5)
    assert gated["9999"]["count"] == 2, gated          # 1003 excluded -> 2 of 3 remain
    assert "8888" not in gated, gated                  # only 1003 followed 8888 -> gone
    assert gated["9999"]["weight"] == round(0.92 + 0.80, 3), gated  # reputation-weighted

    # 3) the surfaced target scores via the existing social sub-score
    raw = {"smart_followers": conv["9999"]["count"], "openrank_pct": 0.95,
           "neynar_score": 0.7, "account_age_days": 400}
    sb = social_bonus(raw)
    assert sb > 0, f"social_bonus should be >0 for a 3-way convergence, got {sb}"

    print(f"network_radar convergence check: PASS  "
          f"(9999 converged 3x -> social_bonus {sb}; rep-gate drops low-rep follower)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
