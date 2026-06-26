from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _domain(url: str) -> str:
    m = re.search(r"https?://([^/]+)", url or "")
    return m.group(1).replace("www.", "") if m else ""


@dataclass
class Candidate:
    """A potential investment surfaced by a source."""
    name: str
    source: str
    url: str
    summary: str = ""
    signal_metric: str = ""
    tags: list = field(default_factory=list)
    raw: dict = field(default_factory=dict)
    discovered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def key(self) -> str:
        """Stable dedup key: normalized name + domain."""
        return f"{_norm(self.name)}|{_domain(self.url)}"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScoredCandidate:
    candidate: Candidate
    score: float          # composite (0-100)
    thesis_fit: str       # human-readable rationale
    matched_themes: list = field(default_factory=list)
    citations: list = field(default_factory=list)
    flags: list = field(default_factory=list)      # HARD anti-signals (penalised, screen-out)
    risks: list = field(default_factory=list)       # SOFT/informational notes (shown, NOT penalised)
    subscores: dict = field(default_factory=dict)  # {fit, traction, traction_bonus, credibility_adj}

    def to_dict(self) -> dict:
        return asdict(self)
