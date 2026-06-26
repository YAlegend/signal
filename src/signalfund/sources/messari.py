"""Messari enrichment — funding / stage + investor corroboration (Tier-2 PREMIUM).

Enrichment-only (no discovery): given a resolvable asset/project, pulls the latest funding
round (stage, total raised, lead investors) and a sector tag onto candidate.raw["messari"].
scoring.messari_adj turns that into a STAGE GATE (late round / large raise -> stage_preference
'avoid' down-rank) plus a small reputation-weighted credibility nudge for a tier-1 lead
investor. memo.py can also pull a short Messari research snippet as attributed context.

Graceful: no MESSARI_API_KEY -> enrich is a no-op (contributes 0); httpx is imported only
when a key is present, so the offline path needs none of it.

NOTE: like sources/harmonic.py & social_farcaster.py, no paid Messari key was available to
verify the exact endpoints / response shapes — parsing here is DEFENSIVE on purpose (handles
several documented shapes, paged + capped). Validate against real responses before trusting
it in production. Coverage skews to known/funded assets => this is diligence + stage-gating,
NOT earliest discovery.
"""
from __future__ import annotations

import os
import re

from .base import Source
from ..models import Candidate

MESSARI_API = "https://api.messari.io"


def _client(key: str):
    import httpx
    return httpx.Client(base_url=MESSARI_API,
                        headers={"x-messari-api-key": key, "accept": "application/json"}, timeout=30)


def _slug(candidate) -> str | None:
    raw = candidate.raw or {}
    if raw.get("messari_slug"):
        return str(raw["messari_slug"])
    name = (candidate.name or "").strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    return slug or None


# ---- defensive parsers (pure -> offline-testable) ---------------------------

def parse_funding(payload) -> dict:
    """Latest funding round from a Messari funding response (several shapes). {} if none."""
    d = payload.get("data") if isinstance(payload, dict) else payload
    if isinstance(d, dict):
        rounds = d.get("fundingRounds") or d.get("funding_rounds") or d.get("rounds") or []
    elif isinstance(d, list):
        rounds = d
    else:
        rounds = []
    rounds = [r for r in rounds if isinstance(r, dict)]
    if not rounds:
        return {}

    def _date(r):
        return str(r.get("announcedDate") or r.get("announced_at") or r.get("date") or "")
    latest = max(rounds, key=_date) if any(_date(r) for r in rounds) else rounds[-1]

    stage = latest.get("stage") or latest.get("series") or latest.get("type") or latest.get("round")
    raised = (latest.get("raisedAmountUsd") or latest.get("amountUsd") or latest.get("amount_usd")
              or latest.get("raised_usd") or latest.get("amount"))
    investors = latest.get("investors") or latest.get("lead_investors") or latest.get("leadInvestors") or []
    leads, allnames = [], []
    for inv in investors:
        if isinstance(inv, dict):
            name = inv.get("name") or inv.get("investor")
            if not name:
                continue
            allnames.append(name)
            if inv.get("lead") or inv.get("is_lead") or str(inv.get("type", "")).lower() == "lead":
                leads.append(name)
        elif isinstance(inv, str):
            allnames.append(inv); leads.append(inv)
    return {
        "stage": stage,
        "total_raised_usd": raised if isinstance(raised, (int, float)) else None,
        "lead_investors": leads or allnames[:5],
        "announced": _date(latest) or None,
    }


def parse_sector(payload) -> str:
    d = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(d, dict):
        return ""
    prof = d.get("profile") or d
    sector = (prof.get("sector") or prof.get("category")
              or (prof.get("general", {}) or {}).get("category"))
    return str(sector) if sector else ""


def parse_research(payload) -> str:
    """Pull the assistant text from a Messari AI / chat-style response (several shapes)."""
    if not isinstance(payload, dict):
        return ""
    d = payload.get("data", payload)
    if isinstance(d, dict):
        if isinstance(d.get("content"), str):
            return d["content"].strip()
        msgs = d.get("messages")
        if isinstance(msgs, list) and msgs:
            return str(msgs[-1].get("content", "")).strip()
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        return str((choices[0].get("message") or {}).get("content", "")).strip()
    return ""


# ---- live enrichment (defensive) --------------------------------------------

def enrich(candidate) -> None:
    """Write candidate.raw['messari'] = {funding, sector}. No-op without MESSARI_API_KEY /
    resolvable slug / on any failure; never overwrites pre-baked data."""
    key = os.getenv("MESSARI_API_KEY")
    if not key or (candidate.raw or {}).get("messari") is not None:
        return
    slug = _slug(candidate)
    if not slug:
        return
    try:
        data = {}
        with _client(key) as cx:
            rf = cx.get(f"/funding/v1/projects/{slug}/funding-rounds", params={"limit": 20})
            if rf.status_code == 200:
                f = parse_funding(rf.json())
                if f:
                    data["funding"] = f
            rp = cx.get(f"/metrics/v1/assets/{slug}/profile")
            if rp.status_code == 200:
                sector = parse_sector(rp.json())
                if sector:
                    data["sector"] = sector
        if data:
            candidate.raw["messari"] = data
    except Exception:
        return


def research_context(candidate, thesis=None) -> str:
    """A short, attributed Messari research/Copilot snippet for the candidate's sector, to
    pressure-test the thesis open_question in a memo. '' without a key / sector / on failure."""
    key = os.getenv("MESSARI_API_KEY")
    if not key:
        return ""
    sector = ((candidate.raw or {}).get("messari") or {}).get("sector") \
        or (candidate.tags[0] if candidate.tags else "")
    if not sector:
        return ""
    try:
        q = (f"In 2-3 sentences, summarise the current funding climate and the strongest open "
             f"competitive risk in the {sector} crypto sector for an early-stage investor.")
        with _client(key) as cx:
            r = cx.post("/ai/v1/chat/completions",
                        json={"messages": [{"role": "user", "content": q}]})
            if r.status_code != 200:
                return ""
            snippet = parse_research(r.json())
        return snippet[:600] if snippet else ""
    except Exception:
        return ""


class MessariSource(Source):
    """Enrichment-only Tier-2 source; fetch() discovers nothing (returns []). The funding /
    stage signal is applied via enrich() in the orchestrator's enrich pass."""
    name = "messari"

    def fetch(self, limit: int = 25, store=None) -> list:
        return []

    @staticmethod
    def enrich(candidate) -> None:
        enrich(candidate)
