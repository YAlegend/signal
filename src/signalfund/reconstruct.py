"""Point-in-time signal reconstruction (the live, networked step).

Fills each ground-truth company's `windows` with the signal that existed *as of*
a past date — so the backtest never sees look-ahead data.

Two ways to get historical GitHub stars:
  1. GitHub stargazer timestamps (DEFAULT) — needs only GITHUB_TOKEN. Pages the
     `stargazers` API (oldest-first) and counts stars dated on/before the window.
     Cheap for early windows; capped for very large repos.
  2. GH Archive on BigQuery (fallback) — needs google-cloud-bigquery + GCP creds.
     Better for huge repos, but heavier to set up.

    PYTHONPATH=src python -m signalfund.reconstruct in.json out.json
"""
from __future__ import annotations

import datetime
import json
import os
import pathlib
import sys

WINDOWS_DAYS = [60, 30, 14]
DELTA = 7  # velocity window: stars at T minus stars at T-7d


def gh_stars_as_of_api(repo: str, as_of: str, token: str = None, max_pages: int = 80) -> int | None:
    """Stars for 'owner/repo' as of an ISO date, via GitHub stargazer timestamps.
    Needs only GITHUB_TOKEN. Returns None on error (missing repo / rate limit)."""
    import httpx

    token = token or os.getenv("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github.star+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    cutoff = as_of[:10]
    count, seen_after = 0, False
    try:
        with httpx.Client(base_url="https://api.github.com", headers=headers, timeout=30) as cx:
            for page in range(1, max_pages + 1):
                r = cx.get(f"/repos/{repo}/stargazers", params={"per_page": 100, "page": page})
                if r.status_code != 200:
                    return None if page == 1 else count
                batch = r.json()
                if not batch:
                    break
                page_all_after = True
                for item in batch:
                    ts = (item.get("starred_at") or "")[:10]
                    if ts and ts <= cutoff:
                        count += 1
                        page_all_after = False
                    else:
                        seen_after = True
                if seen_after and page_all_after:
                    break  # stargazers are oldest-first; we're past the cutoff
    except Exception as e:
        print(f"[reconstruct] stargazer API failed for {repo}: {e}")
        return None
    return count


def gh_stars_as_of_bq(repo: str, as_of: str) -> int | None:
    """Stars as of a date from GH Archive (BigQuery). Needs google-cloud-bigquery + creds."""
    try:
        from google.cloud import bigquery
    except Exception:
        return None
    sql = """
        SELECT COUNT(*) AS stars
        FROM `githubarchive.day.{year}*`
        WHERE type = 'WatchEvent' AND repo.name = @repo AND created_at <= TIMESTAMP(@as_of)
    """.format(year=as_of[:4])
    try:
        client = bigquery.Client()
        cfg = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("repo", "STRING", repo),
            bigquery.ScalarQueryParameter("as_of", "STRING", f"{as_of} 23:59:59"),
        ])
        return int(list(client.query(sql, job_config=cfg).result())[0]["stars"])
    except Exception as e:
        print(f"[reconstruct] GH Archive query failed for {repo}: {e}")
        return None


def gh_stars_as_of(repo: str, as_of: str, token: str = None) -> int | None:
    """Token-only API first; fall back to BigQuery if available."""
    n = gh_stars_as_of_api(repo, as_of, token)
    if n is not None:
        return n
    return gh_stars_as_of_bq(repo, as_of)


def wayback_has_snapshot(url: str, as_of: str) -> bool:
    """Did a Wayback snapshot of `url` exist at/before `as_of`? Public API, no auth."""
    if not url:
        return False
    try:
        import httpx
        ts = as_of.replace("-", "")
        r = httpx.get("https://archive.org/wayback/available",
                      params={"url": url, "timestamp": ts}, timeout=20)
        snap = r.json().get("archived_snapshots", {}).get("closest", {})
        return bool(snap) and snap.get("timestamp", "99999999")[:8] <= ts
    except Exception as e:
        print(f"[reconstruct] wayback lookup failed for {url}: {e}")
        return False


def farcaster_signals_as_of(fid, as_of: str) -> dict:
    """Point-in-time Farcaster social signal (smart_followers / openrank_pct) as of a
    past date, via Dune's Farcaster tables. Needs DUNE_API_KEY + dune-client; returns
    {} without them (graceful) so reconstruction never blocks. The query should count
    credible followers acquired on/before `as_of` and the OpenRank percentile at T.

    Hooked here so the `social` sub-score is Phase-0 backtest-able (Ticket 3)."""
    if not (fid and os.getenv("DUNE_API_KEY")):
        return {}
    try:  # pragma: no cover - networked, optional
        from dune_client.client import DuneClient  # noqa: F401
        # Wire a saved Dune query (followers_as_of / openrank_as_of) for your account here.
        return {}
    except Exception:
        return {}


def reconstruct_company(row: dict) -> dict:
    """Populate row['windows'] for each lookback. Leaves has_signal=False where nothing
    is found — that absence is itself the finding (the F6 test)."""
    handles = row.get("public_handles", {})
    repo = handles.get("github_repo") or handles.get("github")
    site = handles.get("site")
    fid = handles.get("farcaster") or handles.get("fid")
    obvious = datetime.date.fromisoformat(row["obvious_date"])
    windows = row.setdefault("windows", {})
    for d in WINDOWS_DAYS:
        key = f"-{d}d"
        w = windows.setdefault(key, {})
        as_of = (obvious - datetime.timedelta(days=d)).isoformat()
        as_of_prev = (obvious - datetime.timedelta(days=d + DELTA)).isoformat()
        if repo and "/" in repo:
            s_t = gh_stars_as_of(repo, as_of)
            if s_t is not None:
                s_p = gh_stars_as_of(repo, as_of_prev)
                w.update({"stars": s_t, "stars_prev": s_p if s_p is not None else s_t,
                          "delta_days": DELTA, "has_signal": True})
        if site and wayback_has_snapshot(site, as_of):
            w["has_signal"] = True
        social = farcaster_signals_as_of(fid, as_of)   # {} unless DUNE_API_KEY set
        if social:
            w.update(social)
            w["has_signal"] = True
        w.setdefault("has_signal", False)
        w.setdefault("summary", row.get("summary_at_T", ""))
        w.setdefault("tags", row.get("tags_at_T", []))
    return row


def main():
    if len(sys.argv) < 3:
        print("usage: python -m signalfund.reconstruct in.json out.json")
        raise SystemExit(2)
    from . import env
    env.load_env()  # so GITHUB_TOKEN from .env authenticates (5000/hr, not 60/hr)
    src, dst = sys.argv[1], sys.argv[2]
    rows = json.loads(pathlib.Path(src).read_text(encoding="utf-8"))
    out = []
    for r in rows:
        print(f"[reconstruct] {r['company']} …", flush=True)
        out.append(reconstruct_company(r))
    pathlib.Path(dst).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"[reconstruct] wrote {dst} ({len(out)} companies)")


if __name__ == "__main__":
    main()
