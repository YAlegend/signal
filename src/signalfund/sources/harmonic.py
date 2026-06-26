"""Harmonic source — VC-grade company/people discovery & enrichment.

Pulls net-new companies from a saved search. Degrades gracefully (returns [])
when HARMONIC_API_KEY / HARMONIC_SAVED_SEARCH_ID are unset, so it never breaks a run.

NOTE: confirm the exact endpoint and response shape against the Harmonic API docs
for your account. Parsing here is defensive on purpose.
"""
from __future__ import annotations

import os

from .base import Source
from ..models import Candidate

HARMONIC_API = "https://api.harmonic.ai"


class HarmonicSource(Source):
    name = "harmonic"

    def __init__(self, saved_search_id: str = None):
        self.saved_search_id = saved_search_id or os.getenv("HARMONIC_SAVED_SEARCH_ID")

    def fetch(self, limit: int = 25, store=None) -> list:
        key = os.getenv("HARMONIC_API_KEY")
        if not key:
            print("[signal] HARMONIC_API_KEY not set — skipping Harmonic source")
            return []
        if not self.saved_search_id:
            print("[signal] HARMONIC_SAVED_SEARCH_ID not set — skipping Harmonic source")
            return []

        import httpx

        headers = {"apikey": key, "accept": "application/json"}
        url = f"{HARMONIC_API}/saved_searches/{self.saved_search_id}/results"
        try:
            with httpx.Client(timeout=30) as cx:
                r = cx.get(url, headers=headers, params={"size": limit})
                r.raise_for_status()
                payload = r.json()
        except Exception as e:
            print(f"[signal][warn] harmonic request failed: {e}")
            return []

        out = []
        for item in (payload.get("results") or payload.get("companies") or []):
            name = item.get("name") or item.get("company_name") or "unknown"
            website = item.get("website")
            url_ = website.get("url") if isinstance(website, dict) else (website or "")
            url_ = url_ or item.get("harmonic_url", "")
            out.append(Candidate(
                name=name,
                source="harmonic",
                url=url_,
                summary=item.get("description") or item.get("tagline") or "",
                signal_metric=item.get("stage") or "net-new (Harmonic)",
                tags=item.get("tags") or item.get("categories") or [],
                raw={"harmonic_id": item.get("id"),
                     "source_urls": [u for u in [url_] if u]},
            ))
        return out[:limit]
