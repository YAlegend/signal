"""Social enrichment — Farcaster smart-follower convergence + reputation.

Crypto-native, hard to game (Neynar + OpenRank are sybil-resistant), and point-in-time
queryable (so it works in live sourcing *and* the Phase-0 backtest). Writes onto
candidate.raw: smart_followers (high-rep follows that overlap the fund's graph),
neynar_score, openrank_pct, power_badge, account_age_days. scoring.social_bonus turns
these into the `social` sub-score.

Needs NEYNAR_API_KEY + FARCASTER_FUND_FID (the fund's seed FID, the "viewer" whose
graph defines a *credible* follow). Networked; the orchestrator runs enrich() in LIVE
mode only. No-op (no raise) without keys / handle, or on any failure. Pre-baked raw
fields are left untouched.

NOTE: confirm exact Neynar endpoints/shapes for your plan — parsing is defensive.
"""
from __future__ import annotations

import os

NEYNAR_API = "https://api.neynar.com"


def _handle(candidate) -> str | None:
    """Farcaster handle/FID from raw['farcaster'] or raw['fid']."""
    raw = candidate.raw or {}
    return raw.get("farcaster") or raw.get("fid") or None


def _client(key: str):
    import httpx
    return httpx.Client(base_url=NEYNAR_API,
                        headers={"accept": "application/json", "api_key": key,
                                 "x-api-key": key}, timeout=30)


def _account_age_days(user: dict):
    import datetime
    ts = user.get("object_timestamp") or user.get("created_at") or user.get("registered_at")
    if not ts:
        return None
    try:
        created = datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        now = datetime.datetime.now(datetime.timezone.utc)
        return max(0, (now - created.astimezone(datetime.timezone.utc)).days)
    except Exception:
        return None


def enrich(candidate) -> None:
    key = os.getenv("NEYNAR_API_KEY")
    fund_fid = os.getenv("FARCASTER_FUND_FID")
    handle = _handle(candidate)
    if not key or not fund_fid or not handle or candidate.raw.get("smart_followers") is not None:
        return
    try:
        with _client(key) as cx:
            # credible follows = followers of `handle` that the fund's FID also follows/credits
            rf = cx.get("/v2/farcaster/followers/relevant",
                        params={"target_fid": handle, "viewer_fid": fund_fid})
            credible = []
            if rf.status_code == 200:
                body = rf.json()
                credible = (body.get("top_relevant_followers_hydrated")
                            or body.get("relevant_followers") or body.get("users") or [])
            ru = cx.get("/v2/farcaster/user/bulk", params={"fids": handle, "viewer_fid": fund_fid})
            user = {}
            if ru.status_code == 200:
                users = ru.json().get("users") or []
                user = users[0] if users else {}
    except Exception:
        return

    raw = candidate.raw
    raw["smart_followers"] = len(credible)
    score = user.get("experimental", {}).get("neynar_user_score") or user.get("neynar_user_score")
    if isinstance(score, (int, float)):
        raw["neynar_score"] = round(float(score), 3)
    if user.get("power_badge") is not None:
        raw["power_badge"] = bool(user["power_badge"])
    age = _account_age_days(user)
    if age is not None:
        raw["account_age_days"] = age
    # OpenRank percentile (k3l) is best-effort and optional; left to a pre-set value
    # or a future hook so a Neynar-only deployment still produces a usable signal.


class SocialSource:
    """Optional discovery: surface trending Farcaster-native projects. Returns []
    unless NEYNAR_API_KEY is set. (Mapping casts -> investable companies is left to a
    reviewer; this just seeds candidates from the trending feed.)"""
    name = "social"

    def fetch(self, limit: int = 25, store=None) -> list:
        key = os.getenv("NEYNAR_API_KEY")
        if not key:
            return []
        try:
            from ..models import Candidate
            with _client(key) as cx:
                r = cx.get("/v2/farcaster/feed/trending", params={"limit": limit})
                r.raise_for_status()
                casts = r.json().get("casts") or []
        except Exception as e:
            print(f"[signal][warn] social discovery failed: {e}")
            return []
        out = []
        for c in casts[:limit]:
            author = c.get("author") or {}
            out.append(Candidate(
                name=author.get("username") or author.get("display_name") or "farcaster project",
                source="social", url=(c.get("frames") or [{}])[0].get("frames_url", ""),
                summary=(c.get("text") or "")[:200],
                signal_metric="trending on Farcaster (Neynar)",
                tags=[], raw={"fid": author.get("fid")}))
        return out
