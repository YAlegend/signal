"""Pre-public enrichment — proof that code/social signals miss.

Grants (EF ESP / Optimism RetroPGF), hackathon wins that kept building (ETHGlobal),
and research with an affiliation exit (arXiv / IACR) — the earliest provable signal a
team is real, before stars or followers exist. Writes onto candidate.raw: grant_program,
retro_grant, hackathon_win, post_event_active, research_exit, incorp_days.
scoring.pre_public_bonus turns these into the `pre_public` sub-score.

Mostly a *buy*: Evertrace (EVERTRACE_API_KEY) bundles grants/hackathons/research, so
enrich() prefers it. Networked; the orchestrator runs enrich() in LIVE mode only.
No-op (no raise) without a key / resolvable company, or on any failure. Pre-baked raw
fields are left untouched.

Guardrail: retroactive grants >> proposal grants; count a hackathon only if the team
kept shipping. NOTE: confirm Evertrace's exact shape for your account — parsing is defensive.
"""
from __future__ import annotations

import os
import re

EVERTRACE_API = "https://api.evertrace.xyz"
_PRE_PUBLIC_KEYS = ("grant_program", "retro_grant", "hackathon_win",
                    "post_event_active", "research_exit", "incorp_days")


def _domain(url: str) -> str:
    m = re.search(r"https?://([^/]+)", url or "")
    return m.group(1).replace("www.", "").lower() if m else ""


def _map_fields(rec: dict) -> dict:
    """Best-effort mapping of an Evertrace record onto our raw fields (defensive)."""
    grants = rec.get("grants") or []
    retro = any("retro" in str(g.get("type") or g.get("program") or "").lower() for g in grants)
    hack = rec.get("hackathons") or rec.get("hackathon_wins") or []
    out = {
        "grant_program": (grants[0].get("program") if grants else None) or rec.get("grant_program"),
        "retro_grant": retro or bool(rec.get("retro_grant")),
        "hackathon_win": bool(hack) or bool(rec.get("hackathon_win")),
        "post_event_active": bool(rec.get("post_event_active")
                                  or (hack and hack[0].get("still_active"))),
        "research_exit": bool(rec.get("research_exit") or rec.get("papers")),
        "incorp_days": rec.get("incorp_days") or rec.get("company_age_days"),
    }
    return {k: v for k, v in out.items() if v is not None}


def enrich(candidate) -> None:
    key = os.getenv("EVERTRACE_API_KEY")
    if not key or any(k in candidate.raw for k in _PRE_PUBLIC_KEYS):  # no key, or pre-baked
        return
    domain = _domain(candidate.url)
    if not domain:
        return
    try:
        import httpx

        with httpx.Client(base_url=EVERTRACE_API, headers={"x-api-key": key}, timeout=30) as cx:
            r = cx.get("/v1/company", params={"domain": domain})
            if r.status_code != 200:
                return
            rec = r.json()
        for k, v in _map_fields(rec).items():
            if k not in candidate.raw:
                candidate.raw[k] = v
    except Exception:
        return


class PrePublicSource:
    """Optional discovery: surface teams from grant/hackathon recipient lists (via
    Evertrace). Returns [] unless EVERTRACE_API_KEY is set."""
    name = "pre_public"

    def fetch(self, limit: int = 25, store=None) -> list:
        key = os.getenv("EVERTRACE_API_KEY")
        if not key:
            return []
        try:
            import httpx

            from ..models import Candidate
            with httpx.Client(base_url=EVERTRACE_API, headers={"x-api-key": key}, timeout=30) as cx:
                r = cx.get("/v1/recipients", params={"limit": limit})
                r.raise_for_status()
                recs = r.json().get("results") or r.json().get("companies") or []
        except Exception as e:
            print(f"[signal][warn] pre_public discovery failed: {e}")
            return []
        out = []
        for rec in recs[:limit]:
            cand = Candidate(
                name=rec.get("name") or "grant recipient",
                source="pre_public", url=(rec.get("website") or ""),
                summary=rec.get("description") or "",
                signal_metric="grant / hackathon recipient (Evertrace)",
                tags=rec.get("tags") or [], raw=_map_fields(rec))
            out.append(cand)
        return out
