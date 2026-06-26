"""network_radar — partially digitize the relationship signal.

Surfaces obscure Farcaster accounts that a CURATED set of credible "smart accounts" (VCs /
founders / researchers the fund trusts, in config/smart_accounts.yaml) NEWLY converge on.
When >= MIN_CONVERGENCE distinct smart accounts start following the same target *between
runs*, that target is emitted as a Candidate and scored via the existing `social` sub-score
(smart-follower convergence + reputation).

How it works: each run snapshots every smart account's `following` set into the Store, diffs
it against the prior run, and counts how many distinct smart accounts NEWLY follow each
target. Reputation-weighted — smart accounts below an OpenRank floor don't count, and
convergence is weighted by the followers' reputation. The FIRST run only establishes the
baseline (no convergence emitted); subsequent runs detect new convergence.

Needs NEYNAR_API_KEY; returns [] without it, without a smart-accounts list, or without a
Store to diff against (no crash).

NOTE: no NEYNAR_API_KEY was available to verify the exact `/v2/farcaster/following` +
`/user/bulk` response shapes — parsing here is defensive on purpose (mirrors
sources/social_farcaster.py). Confirm against a live key before trusting it in production.
"""
from __future__ import annotations

import os
import pathlib
import re

from .base import Source
from ..models import Candidate

ROOT = pathlib.Path(__file__).resolve().parents[3]
SMART_ACCOUNTS_PATH = ROOT / "config" / "smart_accounts.yaml"
NEYNAR_API = "https://api.neynar.com"
OPENRANK_API = "https://graph.cast.k3l.io"

MIN_CONVERGENCE = int(os.getenv("SIGNAL_RADAR_MIN_CONVERGENCE", "2"))
MIN_SMART_OPENRANK = float(os.getenv("SIGNAL_RADAR_MIN_OPENRANK", "0.0"))  # 0..1 percentile floor


# ---- config -----------------------------------------------------------------

def load_smart_accounts(path=None) -> list:
    """[{fid, label}] of trusted accounts from config/smart_accounts.yaml. [] if missing/empty."""
    p = pathlib.Path(path) if path else SMART_ACCOUNTS_PATH
    if not p.exists():
        return []
    try:
        import yaml
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or []
        accts = data.get("smart_accounts") if isinstance(data, dict) else data
        out = []
        for a in (accts or []):
            fid = a.get("fid") if isinstance(a, dict) else a
            if fid is None:
                continue
            label = (a.get("label") if isinstance(a, dict) else "") or str(fid)
            out.append({"fid": str(fid), "label": str(label)})
        return out
    except Exception:
        return []


# ---- pure diff / convergence (OFFLINE-TESTABLE, no network) ------------------

def _new_follow_convergence(prev: dict, now: dict, reps: dict = None,
                            min_openrank: float = 0.0) -> dict:
    """Convergence over NEW follows. prev/now: {smart_fid: set(following_fids)}.
    reps: {smart_fid: openrank_pct in 0..1}. Returns
        {target_fid: {"count": int, "weight": float, "by": [smart_fids]}}
    counting, per target, how many distinct smart accounts NEWLY follow it (in `now`, not
    in `prev`). Smart accounts whose known reputation is below `min_openrank` are excluded;
    each contribution is weighted by its reputation (1.0 if unknown)."""
    conv = {}
    for sfid, now_set in now.items():
        rep = (reps or {}).get(sfid)
        if rep is not None and rep < min_openrank:        # reputation gate (only when known)
            continue
        weight = float(rep) if isinstance(rep, (int, float)) else 1.0
        for t in set(now_set) - set(prev.get(sfid) or set()):
            d = conv.setdefault(str(t), {"count": 0, "weight": 0.0, "by": []})
            d["count"] += 1
            d["weight"] = round(d["weight"] + weight, 3)
            d["by"].append(str(sfid))
    return conv


# ---- live Neynar / OpenRank helpers (defensive) -----------------------------

def _client(key: str):
    import httpx
    return httpx.Client(base_url=NEYNAR_API,
                        headers={"accept": "application/json", "api_key": key, "x-api-key": key},
                        timeout=30)


def _following_fids(cx, fid, max_pages: int = 3) -> set:
    """Set of FIDs that `fid` currently follows (Neynar v2 /following, paged + capped)."""
    out, cursor = set(), None
    for _ in range(max_pages):
        params = {"fid": fid, "limit": 100}
        if cursor:
            params["cursor"] = cursor
        r = cx.get("/v2/farcaster/following", params=params)
        if r.status_code != 200:
            break
        body = r.json()
        for item in (body.get("users") or []):
            u = item.get("user") or item                  # shape: {object, user:{fid}} or {fid}
            f = u.get("fid") if isinstance(u, dict) else None
            if f is not None:
                out.add(str(f))
        cursor = (body.get("next") or {}).get("cursor")
        if not cursor:
            break
    return out


def _profile(cx, fid) -> dict:
    r = cx.get("/v2/farcaster/user/bulk", params={"fids": fid})
    if r.status_code != 200:
        return {}
    users = r.json().get("users") or []
    return users[0] if users else {}


def _openrank_pcts(fids) -> dict:
    """OpenRank percentile (0..1) per fid via k3l (no key). {} on any failure (best-effort)."""
    fids = [f for f in fids if f]
    if not fids:
        return {}
    try:
        import httpx
        with httpx.Client(base_url=OPENRANK_API, timeout=20) as ox:
            r = ox.post("/scores/global/following/fids", json=[int(f) for f in fids])
            if r.status_code != 200:
                return {}
            rows = r.json().get("result") if isinstance(r.json(), dict) else r.json()
            out = {}
            for x in (rows or []):
                if not isinstance(x, dict) or x.get("fid") is None:
                    continue
                pct = x.get("percentile")
                rank = x.get("rank")
                val = (float(pct) / 100.0) if isinstance(pct, (int, float)) else (
                    float(rank) if isinstance(rank, (int, float)) else None)
                if val is not None:
                    out[str(x["fid"])] = round(max(0.0, min(1.0, val)), 3)
            return out
    except Exception:
        return {}


def _extract_url(text: str) -> str:
    m = re.search(r"https?://[^\s)]+", text or "")
    return m.group(0) if m else ""


def _tags_from(bio: str) -> list:
    """Cheap keyword hints from a bio so the thesis-fit scorer has something to match."""
    stop = {"the", "and", "for", "with", "building", "builder", "prev", "now", "ceo", "co"}
    out = []
    for w in re.findall(r"[a-z0-9][a-z0-9-]{2,}", (bio or "").lower()):
        if w not in stop and w not in out:
            out.append(w)
        if len(out) >= 6:
            break
    return out


# ---- source -----------------------------------------------------------------

class NetworkRadarSource(Source):
    """Sourcing source: surface accounts a curated set of smart accounts newly converge on."""
    name = "network_radar"

    def fetch(self, limit: int = 25, store=None) -> list:
        key = os.getenv("NEYNAR_API_KEY")
        smart = load_smart_accounts()
        if not key:
            print("[signal] NEYNAR_API_KEY not set — skipping network_radar")
            return []
        if not smart:
            print("[signal] no accounts in config/smart_accounts.yaml — skipping network_radar")
            return []
        if store is None:
            print("[signal] network_radar needs a Store to diff snapshots — skipping")
            return []
        try:
            with _client(key) as cx:
                reps = _openrank_pcts([a["fid"] for a in smart])    # reputation gate/weight
                prev, now = {}, {}
                for a in smart:
                    fid = a["fid"]
                    prior = store.previous_following(fid)
                    cur = _following_fids(cx, fid)
                    if cur:
                        store.snapshot_following(fid, cur)
                    now[fid] = cur
                    # First observation: establish the baseline, emit no convergence this run.
                    prev[fid] = prior if prior is not None else cur

                conv = _new_follow_convergence(prev, now, reps, MIN_SMART_OPENRANK)
                smart_fids = {a["fid"] for a in smart}
                targets = sorted(
                    ((t, d) for t, d in conv.items()
                     if d["count"] >= MIN_CONVERGENCE and t not in smart_fids),
                    key=lambda kv: (kv[1]["count"], kv[1]["weight"]), reverse=True)[:limit]
                if not targets:
                    return []

                tgt_reps = _openrank_pcts([t for t, _ in targets])
                labels = {a["fid"]: a["label"] for a in smart}
                out = []
                for t, d in targets:
                    out.append(self._candidate(cx, t, d, tgt_reps.get(t), labels))
                return out
        except Exception as e:
            print(f"[signal][warn] network_radar failed: {e}")
            return []

    def _candidate(self, cx, fid, conv, openrank, labels) -> Candidate:
        from .social_farcaster import _account_age_days
        user = _profile(cx, fid)
        prof = user.get("profile") or {}
        bio = ((prof.get("bio") or {}).get("text")) or ""
        username = user.get("username") or f"fid:{fid}"
        display = user.get("display_name") or username
        url = _extract_url(bio) or (user.get("verified_addresses") or {}).get("primary", {}).get("eth_address", "") or ""
        nscore = user.get("experimental", {}).get("neynar_user_score") or user.get("neynar_user_score")
        age = _account_age_days(user)
        by = ", ".join(labels.get(b, b) for b in conv["by"][:4])

        raw = {"fid": str(fid), "farcaster": str(fid), "smart_followers": conv["count"]}
        if isinstance(openrank, (int, float)):
            raw["openrank_pct"] = round(float(openrank), 3)
        if isinstance(nscore, (int, float)):
            raw["neynar_score"] = round(float(nscore), 3)
        if age is not None:
            raw["account_age_days"] = age

        return Candidate(
            name=display, source="network_radar",
            url=url if url.startswith("http") else "",
            summary=bio[:240] or f"Farcaster account @{username} newly followed by {conv['count']} smart accounts.",
            signal_metric=f"{conv['count']} smart accounts converged ({by})",
            tags=_tags_from(bio), raw=raw)
