"""Nansen enrichment — Tier-2 PREMIUM. Two things:
  (a) UPGRADES the free `onchain` signal with Smart Money net inflow + smart-money holder
      share / notable labeled holders (higher-signal than raw stablecoin flow / holder Gini).
  (b) ADDS on-chain smart-money CONVERGENCE — the on-chain twin of network_radar: tokens that
      a quorum of curated labeled wallets/funds NEWLY bought between runs.

Graceful absence is mandatory: no NANSEN_API_KEY (and no x402 config) -> enrich is a no-op
(contributes 0) and the free DefiLlama+Blockscout onchain path runs exactly as today. httpx is
imported only when creds are present.

x402 option: Nansen exposes pay-as-you-go endpoints (~$0.01/query in USDC on Base, no key) —
set SIGNAL_NANSEN_X402=1 to opt in. (Payment flow itself is out of scope here; treated as access.)

NOTE: like sources/messari.py & harmonic.py, no creds were available to verify the exact
endpoints / response shapes — parsing is DEFENSIVE on purpose (several documented shapes, capped).
Validate against real responses (or the x402 endpoint) before trusting in production. An on-chain
footprint is required => this is diligence + smart-money convergence, NOT earliest discovery.
"""
from __future__ import annotations

import os
import pathlib
import re

from .base import Source
from ..models import Candidate

ROOT = pathlib.Path(__file__).resolve().parents[3]
SMART_MONEY_PATH = ROOT / "config" / "smart_money_wallets.yaml"
NANSEN_API = "https://api.nansen.ai"

MIN_CONVERGENCE = int(os.getenv("SIGNAL_NANSEN_MIN_CONVERGENCE", "2"))
MIN_WALLET_QUALITY = float(os.getenv("SIGNAL_NANSEN_MIN_QUALITY", "0.0"))  # 0..1 reputation floor


def _has_access() -> bool:
    """Creds present: a Nansen API key, or x402 pay-as-you-go opted in."""
    return bool(os.getenv("NANSEN_API_KEY")) or \
        os.getenv("SIGNAL_NANSEN_X402", "").strip().lower() in ("1", "true", "yes")


def _client():
    import httpx
    headers = {"accept": "application/json"}
    key = os.getenv("NANSEN_API_KEY")
    if key:
        headers["apiKey"] = key
        headers["Authorization"] = f"Bearer {key}"
    return httpx.Client(base_url=NANSEN_API, headers=headers, timeout=30)


def _token(candidate) -> str | None:
    """Token/contract to query: raw['nansen_token'] or raw['token_address']."""
    raw = candidate.raw or {}
    return raw.get("nansen_token") or raw.get("token_address") or None


# ---- defensive parsers (pure -> offline-testable) ---------------------------

def parse_smart_money_flows(payload) -> dict:
    """Smart Money net inflow + holder quality from a Nansen response (several shapes)."""
    d = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(d, dict):
        return {}
    nf = d.get("netflow") or d.get("net_flow") or {}
    inflow = None
    if isinstance(nf, dict):
        inflow = nf.get("usd_30d") or nf.get("usd30d") or nf.get("usd")
    inflow = inflow if isinstance(inflow, (int, float)) else (
        d.get("smartMoneyNetflowUsd30d") if isinstance(d.get("smartMoneyNetflowUsd30d"), (int, float)) else None)
    holders = d.get("smartMoneyHolders") or d.get("smart_money_holders")
    share = d.get("smartMoneyHolderShare") or d.get("smart_money_holder_share")
    out = {}
    if isinstance(inflow, (int, float)):
        out["smart_money_inflow_30d"] = float(inflow)
    if isinstance(holders, (int, float)):
        out["smart_money_holders"] = int(holders)
    if isinstance(share, (int, float)):
        out["smart_money_holder_share"] = round(float(share), 4)
    notable = parse_holders(payload).get("notable_holders")
    if notable:
        out["notable_holders"] = notable
    return out


def parse_holders(payload) -> dict:
    """Notable labeled holders (funds/entities) from a Nansen holders response."""
    d = payload.get("data") if isinstance(payload, dict) else payload
    rows = []
    if isinstance(d, dict):
        rows = d.get("topHolders") or d.get("holders") or d.get("top_holders") or []
    elif isinstance(d, list):
        rows = d
    notable = []
    for h in rows:
        if not isinstance(h, dict):
            continue
        label = h.get("label") or h.get("entity") or h.get("name")
        if label and not str(label).lower().startswith(("0x", "unknown")):
            notable.append(str(label))
    out = {}
    if notable:
        out["notable_holders"] = notable[:8]
    return out


def _new_buy_convergence(prev: dict, now: dict, quality: dict = None,
                         min_quality: float = 0.0) -> dict:
    """On-chain analog of network_radar._new_follow_convergence. prev/now:
    {wallet: set(token_contracts_held)}. quality: {wallet: 0..1}. Returns
        {token: {"count": int, "weight": float, "by": [wallets]}}
    counting, per token, how many distinct curated wallets NEWLY hold it (in `now`, not in
    `prev`). Wallets whose known quality is below `min_quality` are excluded; each contribution
    is reputation-weighted (1.0 if unknown). PURE — no network."""
    conv = {}
    for w, now_set in now.items():
        q = (quality or {}).get(w)
        if q is not None and q < min_quality:        # reputation gate (only when known)
            continue
        weight = float(q) if isinstance(q, (int, float)) else 1.0
        for t in set(now_set) - set(prev.get(w) or set()):
            d = conv.setdefault(str(t), {"count": 0, "weight": 0.0, "by": []})
            d["count"] += 1
            d["weight"] = round(d["weight"] + weight, 3)
            d["by"].append(str(w))
    return conv


def load_smart_money_wallets(path=None) -> list:
    """[{address, label, quality}] from config/smart_money_wallets.yaml. [] if missing/empty."""
    p = pathlib.Path(path) if path else SMART_MONEY_PATH
    if not p.exists():
        return []
    try:
        import yaml
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or []
        rows = data.get("smart_money_wallets") if isinstance(data, dict) else data
        out = []
        for w in (rows or []):
            addr = (w.get("address") if isinstance(w, dict) else w)
            if not addr:
                continue
            out.append({"address": str(addr).lower(),
                        "label": (w.get("label") if isinstance(w, dict) else "") or str(addr),
                        "quality": (w.get("quality") if isinstance(w, dict) else None)})
        return out
    except Exception:
        return []


# ---- live (defensive) -------------------------------------------------------

def _wallet_holdings(cx, address) -> set:
    """Set of token contracts a wallet currently holds (Nansen wallet holdings). [] on failure."""
    try:
        r = cx.get(f"/v1/wallet/{address}/holdings", params={"chain": "ethereum"})
        if r.status_code != 200:
            return set()
        d = r.json().get("data", r.json())
        rows = d.get("holdings") if isinstance(d, dict) else (d if isinstance(d, list) else [])
        out = set()
        for h in (rows or []):
            tok = (h.get("tokenAddress") or h.get("token_address") or h.get("contract")) if isinstance(h, dict) else None
            if tok:
                out.add(str(tok).lower())
        return out
    except Exception:
        return set()


def enrich(candidate) -> None:
    """Upgrade onchain: write candidate.raw['nansen'] = {smart_money_inflow_30d,
    smart_money_holder_share, smart_money_holders, notable_holders}. No-op without creds /
    token / on failure; never overwrites pre-baked data."""
    if not _has_access() or (candidate.raw or {}).get("nansen") is not None:
        return
    token = _token(candidate)
    if not token:
        return
    try:
        data = {}
        with _client() as cx:
            rf = cx.get(f"/v1/token/{token}/smart-money-flows", params={"chain": "ethereum"})
            if rf.status_code == 200:
                data.update(parse_smart_money_flows(rf.json()))
            rh = cx.get(f"/v1/token/{token}/holders", params={"chain": "ethereum", "label": "smart_money"})
            if rh.status_code == 200:
                for k, v in parse_holders(rh.json()).items():
                    data.setdefault(k, v)
        if data:
            candidate.raw["nansen"] = data
    except Exception:
        return


class NansenSource(Source):
    """Tier-2: enrich() upgrades onchain; fetch() does smart-money convergence discovery
    (tokens a quorum of curated wallets newly bought). Both no-op gracefully without creds."""
    name = "nansen"

    @staticmethod
    def enrich(candidate) -> None:
        enrich(candidate)

    def fetch(self, limit: int = 25, store=None) -> list:
        if not _has_access():
            print("[signal] no Nansen creds — skipping smart-money convergence")
            return []
        wallets = load_smart_money_wallets()
        if not wallets:
            print("[signal] no config/smart_money_wallets.yaml — skipping smart-money convergence")
            return []
        if store is None:
            return []
        try:
            prev, now, quality = {}, {}, {}
            with _client() as cx:
                for w in wallets:
                    addr = w["address"]
                    quality[addr] = w.get("quality")
                    prior = store.previous_following(addr)
                    held = _wallet_holdings(cx, addr)
                    if held:
                        store.snapshot_following(addr, held)
                    now[addr] = held
                    prev[addr] = prior if prior is not None else held  # first run = baseline
                conv = _new_buy_convergence(prev, now, quality, MIN_WALLET_QUALITY)
                wallet_set = {w["address"] for w in wallets}
                targets = sorted(
                    ((t, d) for t, d in conv.items() if d["count"] >= MIN_CONVERGENCE and t not in wallet_set),
                    key=lambda kv: (kv[1]["count"], kv[1]["weight"]), reverse=True)[:limit]
                labels = {w["address"]: w["label"] for w in wallets}
                return [self._candidate(cx, t, d, labels) for t, d in targets]
        except Exception as e:
            print(f"[signal][warn] nansen convergence failed: {e}")
            return []

    def _candidate(self, cx, token, conv, labels) -> Candidate:
        by = ", ".join(labels.get(b, b) for b in conv["by"][:4])
        raw = {"token_address": token, "nansen_token": token,
               "nansen": {"smart_money_holders": conv["count"]}}
        try:
            rf = cx.get(f"/v1/token/{token}/smart-money-flows", params={"chain": "ethereum"})
            if rf.status_code == 200:
                raw["nansen"].update(parse_smart_money_flows(rf.json()))
        except Exception:
            pass
        return Candidate(
            name=token, source="nansen", url="",
            summary=f"Token {token} newly bought by {conv['count']} curated smart-money wallets.",
            signal_metric=f"{conv['count']} smart-money wallets converged ({by})",
            tags=[], raw=raw)
