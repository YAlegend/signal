"""Watchlist — human-in-the-loop sourcing.

Reads config/watchlist.yaml (hand-found leads) and emits one Candidate per entry so they
flow through the SAME enrich -> score -> digest -> memo pipeline as GitHub-sourced
candidates, with NO scorer change. Known signal fields on each entry are passed through to
candidate.raw so the existing enrich passes (code_health, pre_public, social, onchain, team)
score them.

Graceful: a missing/empty config/watchlist.yaml -> []. fetch() needs NO network (just reads
the YAML); the live signals (repo persistence etc.) are added by the orchestrator's enrich
pass, exactly as for any other source.
"""
from __future__ import annotations

import pathlib

from .base import Source
from ..models import Candidate

ROOT = pathlib.Path(__file__).resolve().parents[3]
WATCHLIST_PATH = ROOT / "config" / "watchlist.yaml"

# Entry-level keys copied straight onto candidate.raw so the existing signal scorers read
# them (no scorer change). An explicit `raw:` block on an entry is merged in too.
_RAW_PASSTHROUGH = (
    "github_repo",
    "hackathon_win", "post_event_active", "retro_grant", "grant_program",
    "research_exit", "incorp_days",
    "prior_exit", "exit_size_usd", "repeat_founder_count", "same_domain",
    "technical_ceo", "frontier_lab_alum", "team_size",
    "smart_followers", "openrank_pct", "neynar_score", "account_age_days", "fid", "farcaster",
    "commit_accel", "contributor_gini", "contributors",
    "stablecoin_inflow_30d", "real_tvl", "tvl_retention", "holder_gini",
)


def load_watchlist(path=None) -> list:
    """[entry dicts] from config/watchlist.yaml. [] if the file is missing/empty/invalid."""
    p = pathlib.Path(path) if path else WATCHLIST_PATH
    if not p.exists():
        return []
    try:
        import yaml
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or []
        entries = data.get("watchlist") if isinstance(data, dict) else data
        return [e for e in (entries or []) if isinstance(e, dict) and e.get("name")]
    except Exception:
        return []


def _to_candidate(e: dict) -> Candidate:
    repo = (e.get("github_repo") or "").strip().strip("/")
    url = f"https://github.com/{repo}" if repo else (e.get("url") or "")
    raw = dict(e.get("raw") or {})
    if repo:
        raw.setdefault("github_repo", repo)
    for k in _RAW_PASSTHROUGH:
        if k in e and k not in raw:
            raw[k] = e[k]
    metric = e.get("source_note") or (f"watchlist · {e['stage']}" if e.get("stage") else "watchlist (manual lead)")
    return Candidate(
        name=str(e["name"]), source="watchlist", url=url,
        summary=e.get("summary", "") or "",
        signal_metric=metric,
        tags=[str(t) for t in (e.get("tags") or [])],
        raw=raw,
    )


class WatchlistSource(Source):
    """Human-curated leads from config/watchlist.yaml, diligenced like any other candidate."""
    name = "watchlist"

    def fetch(self, limit: int = 25, store=None) -> list:
        entries = load_watchlist()
        if not entries:
            return []
        return [_to_candidate(e) for e in entries[:limit]]
