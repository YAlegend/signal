from __future__ import annotations

import argparse
import json
import os
import pathlib

import yaml

from . import dedup as dedup_mod
from . import digest
from . import env
from . import scoring
from .models import Candidate
from .store import Store

ROOT = pathlib.Path(__file__).resolve().parents[2]


def load_thesis(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_fixtures(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return [Candidate(**item) for item in json.load(f)]


def build_sources():
    """Live data sources. Each degrades gracefully when its key is missing."""
    from .sources.github_velocity import GitHubVelocitySource
    from .sources.harmonic import HarmonicSource
    from .sources.messari import MessariSource
    from .sources.nansen import NansenSource
    from .sources.network_radar import NetworkRadarSource
    from .sources.pre_public import PrePublicSource
    from .sources.social_farcaster import SocialSource
    from .sources.team import TeamSource
    from .sources.watchlist import WatchlistSource
    return [GitHubVelocitySource(), HarmonicSource(), TeamSource(),
            SocialSource(), PrePublicSource(), NetworkRadarSource(),
            WatchlistSource(), MessariSource(), NansenSource()]


def enrich(candidates: list, enabled=None) -> None:
    """Networked signal enrichment (live only): each module writes signal fields
    onto candidate.raw, which the scorer turns into sub-scores. No-op per candidate
    on any error, so a flaky API never blocks a run. Demo fixtures are pre-enriched.
    `enabled` (a set of signal names, or None=all) skips disabled signals' enrich pass."""
    from .sources import messari, nansen, onchain, pre_public, social_farcaster, team
    from .sources.github_velocity import enrich_code_health
    passes = (("code_health", enrich_code_health),            # Ticket 1
              ("onchain", onchain.enrich),                    # Ticket 4 — free (DefiLlama/Blockscout)
              ("nansen", nansen.enrich),                      # Tier-2 — upgrades onchain (after free)
              ("team_github", team.enrich_team_github),       # Ticket 2 — free (GitHub)
              ("team_harmonic", team.enrich_team_harmonic),   # Ticket 2 — premium (Harmonic)
              ("social", social_farcaster.enrich),            # Ticket 3
              ("pre_public", pre_public.enrich),              # Ticket 5
              ("messari", messari.enrich))                    # Tier-2 funding / stage gate
    for c in candidates:
        for name, fn in passes:
            if enabled is not None and name not in enabled:
                continue  # user turned this signal off — skip the (networked) enrich
            try:
                fn(c)
            except Exception as e:
                print(f"[signal][warn] enrich({name}) failed for {c.name}: {e}")


def run(demo: bool = False, limit: int = 25, out_dir: str = None,
        thesis_path: str = None, fixtures: str = None, enabled_signals=None) -> list:
    env.load_env()
    thesis_path = thesis_path or str(ROOT / "config" / "thesis.yaml")
    fixtures = fixtures or str(ROOT / "data" / "fixtures" / "sample_candidates.json")
    out_dir = out_dir or os.getenv("SIGNAL_OUT_DIR", "out")

    thesis = load_thesis(thesis_path)
    # The store (star-velocity snapshots) is only needed for live sources.
    store = None if demo else Store(os.getenv("SIGNAL_DB", "signal.db"))

    if demo:
        candidates = load_fixtures(fixtures)
        print(f"[signal] demo mode — loaded {len(candidates)} fixture candidates")
    else:
        candidates = []
        for s in build_sources():
            try:
                got = s.fetch(limit=limit, store=store)
                print(f"[signal] {s.name}: {len(got)} candidates")
                candidates += got
            except Exception as e:
                print(f"[signal][warn] {s.name} failed: {e}")

    candidates = dedup_mod.dedup(candidates)
    if not demo:
        enrich(candidates, enabled_signals)  # networked sub-signals; demo fixtures pre-baked
    scorer = scoring.get_scorer(thesis, enabled_signals=enabled_signals)
    if enabled_signals is not None:
        print(f"[signal] signals enabled: {sorted(enabled_signals) or '(none)'}")
    print(f"[signal] scoring {len(candidates)} candidates with {type(scorer).__name__}")
    scored = sorted((scorer.score(c) for c in candidates),
                    key=lambda s: s.score, reverse=True)

    paths = digest.write(scored, out_dir=out_dir)
    print(f"[signal] wrote {paths['markdown']} and {paths['json']}")
    try:
        from . import dashboard
        print(f"[signal] dashboard → {dashboard.generate(out_dir)}")
    except Exception as e:
        print(f"[signal][warn] dashboard skipped: {e}")
    if scored:
        top = scored[0]
        print(f"[signal] top: {top.candidate.name} ({top.score}/100)")
    return scored


def main():
    p = argparse.ArgumentParser(description="Signal — dealflow sourcing agent")
    p.add_argument("--demo", action="store_true", help="use bundled fixtures, fully offline")
    p.add_argument("--limit", type=int, default=25, help="max candidates per source (live)")
    p.add_argument("--out", default=None, help="output directory (default: out/)")
    p.add_argument("--thesis", default=None, help="path to thesis.yaml")
    args = p.parse_args()
    run(demo=args.demo, limit=args.limit, out_dir=args.out, thesis_path=args.thesis)


if __name__ == "__main__":
    main()
