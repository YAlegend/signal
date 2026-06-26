"""On-chain enrichment — REAL demand signals, free (DefiLlama + Blockscout, no key).

Writes onto candidate.raw:
  - real_tvl          protocol 30d revenue (the non-incentive "real earnings" proxy)
  - tvl_retention     TVL now / TVL peak — discounts mercenary / incentive-only capital
  - holder_gini       token-holder concentration (whale check) via Blockscout
  - stablecoin_inflow_30d is honoured if pre-provided (full live derivation is a TODO)

scoring.onchain_bonus turns these into the `onchain` sub-score. Networked + key-free;
the orchestrator runs it in LIVE mode only. No-op (no raise) when a candidate has no
resolvable protocol/contract or anything fails. Pre-baked raw fields are left untouched.
"""
from __future__ import annotations

import re

DEFILLAMA_API = "https://api.llama.fi"


def _slug(candidate) -> str | None:
    """DefiLlama protocol slug: explicit raw['defillama_slug'], else a kebab guess
    from the name (a hint — may not resolve, which is fine: enrich just no-ops)."""
    raw = candidate.raw or {}
    if raw.get("defillama_slug"):
        return raw["defillama_slug"]
    slug = re.sub(r"[^a-z0-9]+", "-", (candidate.name or "").strip().lower()).strip("-")
    return slug or None


def _retention(proto: dict):
    """TVL now / TVL peak from a DefiLlama /protocol payload. None if no series."""
    series = proto.get("tvl") or []
    tvls = [p.get("totalLiquidityUSD") for p in series
            if isinstance(p.get("totalLiquidityUSD"), (int, float))]
    if not tvls:
        return None
    peak = max(tvls)
    return round(tvls[-1] / peak, 3) if peak > 0 else None


def _revenue_30d(cx, slug):
    """Best-effort 30d protocol revenue (DefiLlama fees summary). None if absent."""
    try:
        r = cx.get(f"/summary/fees/{slug}", params={"dataType": "dailyRevenue"})
        if r.status_code != 200:
            return None
        data = r.json()
        if isinstance(data.get("total30d"), (int, float)):
            return float(data["total30d"])
        chart = data.get("totalDataChart") or []
        vals = [v for _, v in chart[-30:] if isinstance(v, (int, float))]
        return float(sum(vals)) if vals else None
    except Exception:
        return None


def enrich(candidate) -> None:
    raw = candidate.raw
    slug = _slug(candidate)
    if slug:
        try:
            import httpx

            with httpx.Client(base_url=DEFILLAMA_API, timeout=30) as cx:
                r = cx.get(f"/protocol/{slug}")
                if r.status_code == 200:
                    proto = r.json()
                    ret = _retention(proto)
                    if ret is not None and "tvl_retention" not in raw:
                        raw["tvl_retention"] = ret
                    rev = _revenue_30d(cx, slug)
                    if rev is not None and "real_tvl" not in raw:
                        raw["real_tvl"] = round(rev, 1)
        except Exception:
            pass
    # Holder concentration via Blockscout when a token contract is known.
    addr = raw.get("token_address")
    if addr and "holder_gini" not in raw:
        try:
            from .blockscout import token_holders
            from .github_velocity import _gini

            g = _gini(token_holders(addr))
            if g is not None:
                raw["holder_gini"] = g
        except Exception:
            pass
