"""Blockscout on-chain enrichment (public REST, no key required).

Not a discovery source — an enrichment helper used by Memo/Pulse/Diligence to add
on-chain context (verification status, tx counts) to a candidate contract address.
"""
from __future__ import annotations

import os

from .base import Source

DEFAULT_BASE = "https://eth.blockscout.com"


def enrich_contract(address: str, base_url: str = None) -> dict:
    import httpx

    base = base_url or os.getenv("BLOCKSCOUT_BASE_URL", DEFAULT_BASE)
    out = {"address": address}
    try:
        with httpx.Client(base_url=base, timeout=30) as cx:
            info = cx.get(f"/api/v2/addresses/{address}").json()
            out.update({
                "name": info.get("name"),
                "is_contract": info.get("is_contract"),
                "is_verified": info.get("is_verified"),
                "has_proxy_impl": bool(info.get("implementations")),
            })
            counters = cx.get(f"/api/v2/addresses/{address}/counters").json()
            out["tx_count"] = counters.get("transactions_count")
    except Exception as e:
        out["error"] = str(e)
    return out


def token_holders(address: str, base_url: str = None, top: int = 100) -> list:
    """Top token-holder balances (floats) for a token contract, via Blockscout's
    public REST. Used for holder-concentration (Gini) in onchain enrichment.
    Returns [] on any error / unknown token (no raise)."""
    import httpx

    base = base_url or os.getenv("BLOCKSCOUT_BASE_URL", DEFAULT_BASE)
    try:
        with httpx.Client(base_url=base, timeout=30) as cx:
            items = cx.get(f"/api/v2/tokens/{address}/holders",
                           params={"limit": top}).json().get("items", [])
        out = []
        for it in items:
            v = it.get("value") or it.get("balance")
            try:
                out.append(float(v))
            except (TypeError, ValueError):
                continue
        return out
    except Exception:
        return []


class BlockscoutSource(Source):
    """Enrichment-only; returns no discovery candidates."""
    name = "blockscout"

    def fetch(self, limit: int = 25, store=None) -> list:
        return []
