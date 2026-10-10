"""Source-health registry — per-run visibility into which data sources actually ran.

Every sourcing source and enrich pass that touches an API is listed here with the env
var(s) that unlock it (empty = works with no key). `static_probe` is a no-network check:
key present -> 'live', key absent -> 'skipped (no key: ...)' — the exact same
graceful-absence contract the sources themselves already honour (never an error).

`Tracker` lets the orchestrator overlay the REAL outcome of a run (an exception ->
'failed' + reason, a user-disabled signal -> 'skipped (disabled by user)') on top of the
static probe; anything the run never touched (e.g. every source, in demo mode) falls
back to the static probe unless explicitly overridden.
"""
from __future__ import annotations

import os

# name -> required env var(s). Empty tuple = usable with no key (may still be
# rate-limited / capped). ANY var present is enough to attempt a live call.
REGISTRY = [
    {"name": "github",        "env": (),                  "desc": "GitHub REST — fit/traction/credibility sourcing"},
    {"name": "code_health",   "env": (),                  "desc": "GitHub REST — code-health enrich"},
    {"name": "onchain",       "env": (),                  "desc": "DefiLlama + Blockscout — real TVL / holder concentration"},
    {"name": "social",        "env": ("NEYNAR_API_KEY",), "desc": "Farcaster trending discovery + smart-follower enrich"},
    {"name": "network_radar", "env": ("NEYNAR_API_KEY",), "desc": "Farcaster smart-account new-follow convergence"},
    {"name": "watchlist",     "env": (),                  "desc": "config/watchlist.yaml — human-in-the-loop leads"},
    {"name": "pre_public",    "env": ("EVERTRACE_API_KEY",), "desc": "Evertrace grants/hackathons/research"},
    {"name": "team",          "env": ("HARMONIC_API_KEY",), "desc": "Harmonic people search — stealth founder discovery"},
    {"name": "team_github",   "env": (),                  "desc": "GitHub-derived team signal (technical-CEO proxy etc.)"},
    {"name": "team_harmonic", "env": ("HARMONIC_API_KEY",), "desc": "Harmonic team enrich — exits / repeat-founder"},
    {"name": "harmonic",      "env": ("HARMONIC_API_KEY",), "desc": "Harmonic saved-search company discovery"},
    {"name": "messari",       "env": ("MESSARI_API_KEY",), "desc": "funding/stage gate + lead-investor corroboration"},
    {"name": "nansen",        "env": ("NANSEN_API_KEY", "SIGNAL_NANSEN_X402"),
     "desc": "Smart-money onchain upgrade + convergence"},
]

_BY_NAME = {e["name"]: e for e in REGISTRY}


def registry_names() -> list:
    return [e["name"] for e in REGISTRY]


def key_present(env_vars) -> bool:
    if not env_vars:
        return True
    return any(os.getenv(v) for v in env_vars)


def static_probe(name: str) -> dict:
    """No-network probe: state from env-var presence alone. 'live' here means 'has
    what it needs to attempt a call', not that a call has actually happened yet."""
    entry = _BY_NAME.get(name)
    if entry is None:
        return {"name": name, "state": "skipped", "reason": "not registered", "count": None}
    if key_present(entry["env"]):
        return {"name": name, "state": "live", "reason": None, "count": None}
    missing = " or ".join(entry["env"])
    return {"name": name, "state": "skipped", "reason": f"no key ({missing})", "count": None}


def evaluate(name: str, count: int = None, error: Exception = None) -> dict:
    """Turn an actual fetch/enrich outcome into a health row. An exception always wins
    (-> 'failed'); otherwise defers to the static (key-presence) probe, with the count
    attached."""
    if error is not None:
        return {"name": name, "state": "failed", "reason": str(error)[:200], "count": count}
    row = static_probe(name)
    row["count"] = count
    return row


class Tracker:
    """Collects per-source health rows for a single run. `finalize()` returns one row
    per registered source — anything never explicitly `record`-ed falls back to the
    static (key-presence) probe, so a source that was never invoked still gets an
    accurate, non-crashing status."""

    def __init__(self):
        self._rows = {}

    def record(self, name: str, state: str, reason: str = None, count: int = None) -> None:
        self._rows[name] = {"name": name, "state": state, "reason": reason, "count": count}

    def record_result(self, name: str, count: int = None, error: Exception = None) -> None:
        self.record(**evaluate(name, count=count, error=error))

    def finalize(self) -> list:
        return [self._rows.get(name) or static_probe(name) for name in registry_names()]
