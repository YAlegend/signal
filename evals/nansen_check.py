"""Offline check for the Nansen Tier-2 integration (no creds, no network).

Asserts: (a) a token with strong Smart Money inflow scores HIGHER on the onchain sub-score
than one without; (b) the on-chain convergence function flags a token a quorum of curated
wallets newly bought, and the reputation gate drops a low-quality wallet; (c) without
NANSEN_API_KEY (and no x402) enrich is a no-op and the free DefiLlama/Blockscout onchain path
is what runs; (d) defensive parsers handle the fixture shapes.

    PYTHONPATH=src python evals/nansen_check.py
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from signalfund.sources import nansen  # noqa: E402
from signalfund.scoring import onchain_bonus  # noqa: E402
from signalfund.models import Candidate  # noqa: E402

FX = ROOT / "data" / "fixtures"


def main() -> int:
    # (d) defensive parsers on the fixtures
    flows = nansen.parse_smart_money_flows(json.loads((FX / "nansen_flows.json").read_text()))
    assert flows["smart_money_inflow_30d"] == 5200000.0, flows
    assert flows["smart_money_holder_share"] == 0.31, flows
    assert "Polychain Capital" in (flows.get("notable_holders") or []), flows
    holders = nansen.parse_holders(json.loads((FX / "nansen_holders.json").read_text()))
    assert "Paradigm" in holders["notable_holders"] and "Jump Crypto" in holders["notable_holders"], holders

    # (a) ONCHAIN UPGRADE: strong smart-money inflow scores higher than no Nansen data
    with_sm = onchain_bonus({"nansen": {"smart_money_inflow_30d": 5_200_000.0,
                                        "smart_money_holder_share": 0.31}})
    none = onchain_bonus({})
    free_modest = onchain_bonus({"stablecoin_inflow_30d": 5_000})  # free path, small flow
    assert with_sm > none, f"smart-money inflow must boost onchain: {with_sm} vs {none}"
    assert with_sm > free_modest, f"Nansen smart-money should beat a modest free flow: {with_sm} vs {free_modest}"

    # (b) CONVERGENCE: quorum newly-bought token flagged; low-quality wallet gated out
    cv = json.loads((FX / "nansen_convergence.json").read_text())
    prev = {k: set(v) for k, v in cv["before"].items()}
    now = {k: set(v) for k, v in cv["after"].items()}
    q = cv["wallet_quality"]
    conv = nansen._new_buy_convergence(prev, now)                      # no gate
    assert conv["0xtoken_x"]["count"] == 3, conv
    assert conv["0xtoken_junk"]["count"] == 1, conv
    surfaced = {t for t, d in conv.items() if d["count"] >= 2}
    assert surfaced == {"0xtoken_x"}, surfaced
    gated = nansen._new_buy_convergence(prev, now, q, min_quality=0.5)  # drop low-quality W4
    assert gated["0xtoken_x"]["count"] == 3, gated
    assert "0xtoken_junk" not in gated, gated                          # only the 0.20-quality wallet bought it

    # (c) NO creds -> enrich no-op (contributes 0); the free onchain path still scores
    for k in ("NANSEN_API_KEY", "SIGNAL_NANSEN_X402"):
        os.environ.pop(k, None)
    assert nansen._has_access() is False
    c = Candidate(name="FreeToken", source="x", url="", summary="defi protocol",
                  tags=[], raw={"token_address": "0xabc"})
    nansen.enrich(c)
    assert "nansen" not in c.raw, "enrich must be a no-op without creds"
    free = onchain_bonus({"real_tvl": 500_000, "tvl_retention": 0.8, "holder_gini": 0.6})
    assert free > 0, "free DefiLlama/Blockscout onchain path must still score without Nansen"

    print(f"nansen check: PASS  (onchain upgrade {none} -> {with_sm} w/ smart-money; convergence: "
          f"0xtoken_x by 3 wallets, low-quality wallet gated; no creds -> enrich no-op, free path={free})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
