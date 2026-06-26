"""Custom MCP server: surface GitHub repos by star-acquisition velocity.

Velocity is not a GitHub endpoint — we compute it from snapshots stored in SQLite,
which is exactly why it's worth owning. Register it in Claude Code via .mcp.json,
or run standalone:  python mcp_servers/github_velocity/server.py

Requires: pip install "mcp[cli]" httpx
"""
from __future__ import annotations

import os
import pathlib
import sys

# Make the shared package importable when run as a standalone script.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from signalfund.sources.github_velocity import (  # noqa: E402
    _client, compute_velocity, search_recent_repos,
)
from signalfund.store import Store  # noqa: E402

mcp = FastMCP("github-velocity")
_store = Store(os.getenv("SIGNAL_DB", "signal.db"))


@mcp.tool()
def trending_by_velocity(keywords: str = "crypto OR web3 OR onchain OR agent",
                         since_days: int = 14, min_stars: int = 25,
                         limit: int = 25) -> list:
    """Recently-created repos ranked by star-acquisition velocity (stars/day).
    Surfaces projects gaining traction before they trend."""
    repos = search_recent_repos(keywords, since_days=since_days,
                                min_stars=min_stars, limit=limit)
    res = []
    for r in repos:
        v = compute_velocity(r, _store)
        res.append({"repo": r.get("full_name"), "url": r.get("html_url"),
                    "stars": r.get("stargazers_count"), "velocity_per_day": round(v, 1),
                    "language": r.get("language"), "description": r.get("description")})
    res.sort(key=lambda x: x["velocity_per_day"], reverse=True)
    return res


@mcp.tool()
def repo_velocity(owner: str, repo: str) -> dict:
    """Current stars + velocity for a single repo (accuracy improves as snapshots build)."""
    with _client() as cx:
        r = cx.get(f"/repos/{owner}/{repo}")
        r.raise_for_status()
        data = r.json()
    v = compute_velocity(data, _store)
    return {"repo": data.get("full_name"), "stars": data.get("stargazers_count"),
            "velocity_per_day": round(v, 1), "url": data.get("html_url")}


@mcp.tool()
def snapshot(owner: str, repo: str) -> dict:
    """Record a star snapshot now, so future velocity reads are true deltas."""
    with _client() as cx:
        r = cx.get(f"/repos/{owner}/{repo}")
        r.raise_for_status()
        data = r.json()
    _store.snapshot_stars(data["full_name"], int(data.get("stargazers_count", 0)))
    return {"repo": data.get("full_name"), "snapshotted_stars": data.get("stargazers_count")}


if __name__ == "__main__":
    mcp.run()
