from __future__ import annotations


class Source:
    """A data source that yields Candidates. Subclass and implement fetch()."""
    name: str = "base"

    def fetch(self, limit: int = 25, store=None) -> list:
        raise NotImplementedError
