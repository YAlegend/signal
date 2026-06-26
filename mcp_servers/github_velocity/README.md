# github-velocity MCP server

A custom MCP server that surfaces GitHub repos by **star-acquisition velocity** — the
signal that caught projects like OpenClaw before they trended. Velocity isn't a GitHub
endpoint, so this server computes it from snapshots it stores in SQLite over time.

## Tools
- `trending_by_velocity(keywords, since_days, min_stars, limit)` — ranked list by stars/day.
- `repo_velocity(owner, repo)` — current stars + velocity for one repo.
- `snapshot(owner, repo)` — record a star snapshot now (so future reads are true deltas).

## Run
```bash
pip install "mcp[cli]" httpx
export GITHUB_TOKEN=ghp_...        # optional, higher rate limits
python mcp_servers/github_velocity/server.py
```

## Use in Claude Code
It's registered in the repo's `.mcp.json`. Once loaded, ask Claude Code things like
*"use trending_by_velocity to find agent-infra repos from the last 10 days."*

> First reads fall back to `stars / age` because there's no history yet; every call
> snapshots, so velocity becomes a true delta over subsequent runs.
