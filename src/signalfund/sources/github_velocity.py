"""GitHub star-velocity source.

Shared core for both the pipeline (GitHubVelocitySource) and the custom MCP
server (mcp_servers/github_velocity/). Velocity is computed from snapshots, since
GitHub exposes current stars but not a clean stars-over-time series.
"""
from __future__ import annotations

import datetime
import os
import re

from .base import Source
from ..models import Candidate

GITHUB_API = "https://api.github.com"


def _client(token: str = None):
    import httpx

    headers = {"Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    token = token or os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(base_url=GITHUB_API, headers=headers, timeout=30)


def search_recent_repos(keywords: str, since_days: int = 14, min_stars: int = 25,
                        limit: int = 30, token: str = None) -> list:
    since = (datetime.date.today() - datetime.timedelta(days=since_days)).isoformat()
    q = f"{keywords} created:>={since} stars:>={min_stars}"
    with _client(token) as cx:
        r = cx.get("/search/repositories",
                   params={"q": q, "sort": "stars", "order": "desc",
                           "per_page": min(limit, 100)})
        r.raise_for_status()
        return r.json().get("items", [])


def compute_velocity(repo: dict, store=None) -> float:
    """Stars/day. Uses a stored snapshot delta when available, else stars/age.
    Always records a fresh snapshot so subsequent runs get true velocity."""
    full = repo.get("full_name", "")
    stars = int(repo.get("stargazers_count", 0))
    now = datetime.datetime.utcnow()
    if store is not None and full:
        prev = store.previous_stars(full, within_days=30)
        store.snapshot_stars(full, stars)
        if prev:
            pstars, pts = prev
            days = max((now - pts).total_seconds() / 86400.0, 0.5)
            return (stars - pstars) / days
    try:
        created = datetime.datetime.strptime(repo["created_at"], "%Y-%m-%dT%H:%M:%SZ")
        age = max((now - created).total_seconds() / 86400.0, 1.0)
    except Exception:
        age = 30.0
    return stars / age


# ---- code_health enrichment (docs/SIGNALS_BUILD_SPEC.md · Ticket 1) ---------
# Writes raw['commit_accel','contributor_gini','contributors']. Networked, so the
# orchestrator runs it in LIVE mode only; no-op on any error / non-GitHub / private
# repo. Demo fixtures carry these fields pre-baked so the sub-score still renders.

def _owner_repo(candidate) -> str | None:
    """'owner/repo' from a candidate's GitHub url, else its name if shaped that way."""
    m = re.search(r"github\.com/([^/]+/[^/#?]+)", candidate.url or "")
    if m:
        return m.group(1).removesuffix(".git")
    name = candidate.name or ""
    return name if (name.count("/") == 1 and " " not in name) else None


def _gini(values) -> float | None:
    """Gini coefficient over contribution counts. 0 = perfectly even, ~1 = one dev
    does everything. None if undefined (no contributions)."""
    xs = sorted(v for v in values if isinstance(v, (int, float)) and v >= 0)
    n, total = len(xs), sum(xs)
    if n == 0 or total == 0:
        return None
    cum = sum(i * x for i, x in enumerate(xs, 1))
    return round((2 * cum) / (n * total) - (n + 1) / n, 3)


def enrich_code_health(candidate, token: str = None) -> None:
    """Populate raw with commit-velocity acceleration + contributor Gini for a repo.
    No-op (no raise) if the candidate isn't a public GitHub repo or anything fails."""
    repo = _owner_repo(candidate)
    if not repo:
        return
    try:
        import time

        with _client(token) as cx:
            weeks = None
            for _ in range(4):  # stats endpoint returns 202 while GitHub computes
                r = cx.get(f"/repos/{repo}/stats/commit_activity")
                if r.status_code == 202:
                    time.sleep(1.0)
                    continue
                if r.status_code != 200:
                    return
                weeks = r.json()
                break
            if not isinstance(weeks, list) or len(weeks) < 4:
                return
            totals = [w.get("total", 0) for w in weeks]
            accel = round(sum(totals[-2:]) / max(sum(totals[-4:-2]), 1), 2)  # last 14d / prior 14d

            rc = cx.get(f"/repos/{repo}/contributors", params={"per_page": 100, "anon": "true"})
            if rc.status_code != 200:
                return
            contribs = [c.get("contributions", 0) for c in rc.json()]
            candidate.raw["commit_accel"] = accel
            candidate.raw["contributors"] = len(contribs)
            if len(contribs) >= 2:
                candidate.raw["contributor_gini"] = _gini(contribs)
    except Exception:
        return


class GitHubVelocitySource(Source):
    name = "github"

    def __init__(self, keywords: str = "crypto OR web3 OR onchain OR agent",
                 token: str = None):
        self.keywords = keywords
        self.token = token

    def fetch(self, limit: int = 25, store=None) -> list:
        repos = search_recent_repos(self.keywords, limit=limit, token=self.token)
        out = []
        for r in repos:
            v = compute_velocity(r, store)
            out.append(Candidate(
                name=r.get("full_name", "?"),
                source="github",
                url=r.get("html_url", ""),
                summary=r.get("description") or "",
                signal_metric=f"{v:.0f} stars/day (+{r.get('stargazers_count', 0)} total)",
                tags=r.get("topics", []) or [],
                raw={"stars": r.get("stargazers_count"),
                     "velocity_per_day": round(v, 1),
                     "language": r.get("language")},
            ))
        out.sort(key=lambda c: c.raw.get("velocity_per_day", 0), reverse=True)
        return out
