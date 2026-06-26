"""Offline check for WatchlistSource (no keys, no network).

Asserts that a hand-found lead in a watchlist YAML becomes a scored Candidate that flows
through the same scorer as any other source — and that pass-through raw fields (the
pre_public "kept shipping" gate) reach the sub-score.

    PYTHONPATH=src python evals/watchlist_check.py
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml  # noqa: E402

from signalfund.sources.watchlist import load_watchlist, _to_candidate, WatchlistSource  # noqa: E402
from signalfund.scoring import HeuristicScorer  # noqa: E402


def main() -> int:
    fixture = ROOT / "data" / "fixtures" / "watchlist_sample.yaml"
    entries = load_watchlist(fixture)
    assert len(entries) == 2, f"expected 2 fixture entries, got {len(entries)}"

    cands = [_to_candidate(e) for e in entries]
    onthesis, offthesis = cands[0], cands[1]

    # pass-through: source tag, repo -> url, raw signal fields preserved
    assert onthesis.source == "watchlist", onthesis.source
    assert onthesis.url == "https://github.com/example-org/policy-guard", onthesis.url
    assert onthesis.raw.get("github_repo") == "example-org/policy-guard"
    assert onthesis.raw.get("hackathon_win") is True and onthesis.raw.get("post_event_active") is True

    # scores through the SAME deterministic scorer; on-thesis ranks above the off-thesis toy
    thesis = yaml.safe_load((ROOT / "config" / "thesis.yaml").read_text())
    scorer = HeuristicScorer(thesis)
    s_on = scorer.score(onthesis)
    s_off = scorer.score(offthesis)
    assert s_on.score > 0, f"on-thesis watchlist lead should score > 0, got {s_on.score}"
    assert s_on.score > s_off.score, f"on-thesis ({s_on.score}) should beat off-thesis ({s_off.score})"
    assert "pre_public" in s_on.subscores and s_on.subscores["pre_public"] > 0, \
        f"hackathon+kept-shipping should give pre_public bonus, got {s_on.subscores.get('pre_public')}"

    # graceful: missing file -> []
    assert WatchlistSource().fetch.__self__ is not None  # sanity
    assert load_watchlist(ROOT / "config" / "does_not_exist.yaml") == []

    print(f"watchlist check: PASS  (PolicyGuard score={s_on.score} "
          f"[pre_public +{s_on.subscores['pre_public']}] > toy {s_off.score}; missing file -> [])")
    return 0


if __name__ == "__main__":
    sys.exit(main())
