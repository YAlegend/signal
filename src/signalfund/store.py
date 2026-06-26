from __future__ import annotations

import datetime
import json
import sqlite3
from typing import Optional, Tuple


class Store:
    """SQLite-backed store for star snapshots (to compute velocity over time)
    and a 'seen' set (to dedup across runs)."""

    def __init__(self, path: str = "signal.db"):
        self.path = path
        self._conn = self._connect(path)

    def _connect(self, path: str):
        try:
            conn = sqlite3.connect(path)
            self._init(conn)
            return conn
        except sqlite3.OperationalError as e:
            # Some mounted/overlay filesystems don't support sqlite file locking.
            if path != ":memory:":
                print(f"[signal][warn] sqlite at {path} unavailable ({e}); "
                      f"using in-memory store (velocity won't persist across runs)")
                self.path = ":memory:"
                conn = sqlite3.connect(":memory:")
                self._init(conn)
                return conn
            raise

    @staticmethod
    def _init(conn) -> None:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS star_snapshots "
            "(repo TEXT NOT NULL, stars INTEGER NOT NULL, ts TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS seen (key TEXT PRIMARY KEY, ts TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS following_snapshots "
            "(fid TEXT NOT NULL, following TEXT NOT NULL, ts TEXT NOT NULL)"
        )
        conn.commit()

    def snapshot_stars(self, repo: str, stars: int,
                       ts: Optional[datetime.datetime] = None) -> None:
        ts = ts or datetime.datetime.utcnow()
        self._conn.execute(
            "INSERT INTO star_snapshots (repo, stars, ts) VALUES (?, ?, ?)",
            (repo, int(stars), ts.isoformat()),
        )
        self._conn.commit()

    def previous_stars(self, repo: str, within_days: int = 30
                       ) -> Optional[Tuple[int, datetime.datetime]]:
        cutoff = (datetime.datetime.utcnow()
                  - datetime.timedelta(days=within_days)).isoformat()
        row = self._conn.execute(
            "SELECT stars, ts FROM star_snapshots "
            "WHERE repo = ? AND ts >= ? ORDER BY ts ASC LIMIT 1",
            (repo, cutoff),
        ).fetchone()
        if not row:
            return None
        return int(row[0]), datetime.datetime.fromisoformat(row[1])

    def snapshot_following(self, fid, following, ts: Optional[datetime.datetime] = None) -> None:
        """Record the set of FIDs that `fid` currently follows (for network_radar diffing)."""
        ts = ts or datetime.datetime.utcnow()
        members = json.dumps(sorted(str(x) for x in following))
        self._conn.execute(
            "INSERT INTO following_snapshots (fid, following, ts) VALUES (?, ?, ?)",
            (str(fid), members, ts.isoformat()),
        )
        self._conn.commit()

    def previous_following(self, fid) -> Optional[set]:
        """The most recent stored following-set for `fid` (the prior run's). None if none."""
        row = self._conn.execute(
            "SELECT following FROM following_snapshots WHERE fid = ? ORDER BY ts DESC LIMIT 1",
            (str(fid),),
        ).fetchone()
        if not row:
            return None
        try:
            return set(json.loads(row[0]))
        except (ValueError, TypeError):
            return None

    def is_seen(self, key: str) -> bool:
        return self._conn.execute(
            "SELECT 1 FROM seen WHERE key = ?", (key,)
        ).fetchone() is not None

    def mark_seen(self, key: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO seen (key, ts) VALUES (?, ?)",
            (key, datetime.datetime.utcnow().isoformat()),
        )
        self._conn.commit()
