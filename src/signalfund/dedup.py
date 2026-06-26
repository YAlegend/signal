from __future__ import annotations

import re
from typing import Iterable

from .models import Candidate

# Generic tokens that shouldn't drive a name match on their own.
_GENERIC = {"labs", "inc", "ltd", "protocol", "network", "app", "io", "xyz",
            "fi", "finance", "ai", "the", "co", "hq", "foundation", "dao", "org"}


def _sig_tokens(name: str) -> set:
    return set(re.findall(r"[a-z0-9]+", (name or "").lower())) - _GENERIC


def _same_company(a: Candidate, b: Candidate) -> bool:
    if a.key() == b.key():
        return True
    ta, tb = _sig_tokens(a.name), _sig_tokens(b.name)
    if not ta or not tb:
        return False
    # subset (e.g. {mandate} vs {mandate, labs}) or strong overlap
    if ta <= tb or tb <= ta:
        return True
    j = len(ta & tb) / len(ta | tb)
    return j >= 0.6


def dedup(candidates: Iterable[Candidate], store=None, skip_seen: bool = False) -> list:
    """Drop exact and near-duplicate candidates within a run, and optionally any
    already seen in a previous run (cross-run dedup via the store).

    Near-duplicate detection is token-overlap based (ignoring generic words like
    'labs'/'protocol'). For production scale, swap in embeddings + a vector index
    (pgvector) for semantic dedup.
    """
    kept: list = []
    for c in candidates:
        if any(_same_company(c, k) for k in kept):
            continue
        if skip_seen and store is not None and store.is_seen(c.key()):
            continue
        kept.append(c)
    return kept
