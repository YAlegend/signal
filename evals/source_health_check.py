"""Offline check for the source-health registry/tracker (no keys, no network).

Asserts the guardrail behind S-01: a missing API key reports 'skipped (no key: …)' —
never an error or a raised exception — and that an actual exception is captured as
'failed' with a reason rather than propagating. Also checks a full demo run (which
never has live sources) reports every registered source as 'skipped', and — via fake
sources swapped in for orchestrator.build_sources (no real network) — that a live run
correctly separates a source that returned data ('live'), one that raised ('failed'),
and everything it never touched (falls back to the key-presence probe).

    PYTHONPATH=src python evals/source_health_check.py
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from signalfund import orchestrator, source_health  # noqa: E402
from signalfund.models import Candidate  # noqa: E402
from signalfund.sources.base import Source  # noqa: E402


class _FakeSource(Source):
    """Stands in for a live source with no network — either returns candidates or raises."""

    def __init__(self, name, result=None, error=None):
        self.name = name
        self._result = result if result is not None else []
        self._error = error

    def fetch(self, limit=25, store=None):
        if self._error is not None:
            raise self._error
        return self._result

# Every key this suite must guarantee is UNSET so "missing key" behaviour is real,
# not an accident of the developer's own .env.
_ALL_ENV = sorted({v for e in source_health.REGISTRY for v in e["env"]})


def main() -> int:
    saved = {k: os.environ.pop(k, None) for k in _ALL_ENV}
    try:
        # 1) static_probe: no key -> 'skipped (no key: ...)', never raises.
        for entry in source_health.REGISTRY:
            row = source_health.static_probe(entry["name"])
            if entry["env"]:
                assert row["state"] == "skipped", row
                assert row["reason"] and "no key" in row["reason"], row
            else:
                assert row["state"] == "live", row

        # 2) key present -> 'live'.
        os.environ["NEYNAR_API_KEY"] = "test-key"
        row = source_health.static_probe("social")
        assert row["state"] == "live" and row["reason"] is None, row
        os.environ.pop("NEYNAR_API_KEY")

        # 3) an exception is captured as 'failed' + reason, never re-raised.
        tracker = source_health.Tracker()
        tracker.record_result("github", error=RuntimeError("boom"))
        row = next(r for r in tracker.finalize() if r["name"] == "github")
        assert row["state"] == "failed" and "boom" in row["reason"], row

        # 4) unrecorded sources fall back to the static probe (no crash, no gap).
        tracker2 = source_health.Tracker()
        rows = tracker2.finalize()
        assert len(rows) == len(source_health.REGISTRY), rows
        assert all(r["state"] in ("live", "skipped") for r in rows), rows

        # 5) a full demo run: no live sources ever ran -> every source 'skipped (demo mode)'.
        scored = orchestrator.run(demo=True, out_dir=str(ROOT / "out" / "_source_health_check"))
        assert scored, "demo run should still score fixture candidates"
        health = json.loads((ROOT / "out" / "_source_health_check" / "source_health.json")
                            .read_text(encoding="utf-8"))
        assert len(health) == len(source_health.REGISTRY), health
        assert all(r["state"] == "skipped" and "demo mode" in r["reason"] for r in health), health

        # 6) a live run (fake sources swapped in — no real network) never raises, and
        #    correctly separates: a source that returned data -> 'live', one that raised
        #    -> 'failed' + reason, and everything untouched -> the key-presence probe.
        fake_cand = Candidate(name="Foo", source="github", url="", summary="",
                              signal_metric="", tags=[], raw={})
        orig_build_sources = orchestrator.build_sources
        orchestrator.build_sources = lambda: [
            _FakeSource("github", result=[fake_cand]),
            _FakeSource("harmonic", error=RuntimeError("timeout")),
        ]
        try:
            scored_live = orchestrator.run(demo=False, limit=1, enabled_signals=set(),
                                           out_dir=str(ROOT / "out" / "_source_health_check"))
        finally:
            orchestrator.build_sources = orig_build_sources
        assert scored_live, "fake github candidate should still score"
        health_live = json.loads((ROOT / "out" / "_source_health_check" / "source_health.json")
                                 .read_text(encoding="utf-8"))
        by_name = {r["name"]: r for r in health_live}
        assert by_name["github"]["state"] == "live" and by_name["github"]["count"] == 1, by_name["github"]
        assert by_name["harmonic"]["state"] == "failed" and "timeout" in by_name["harmonic"]["reason"], \
            by_name["harmonic"]
        # "team" (Harmonic people-search discovery) is in neither the fake source list nor
        # the enrich passes -> untouched by this run, falls back to the static (key-presence) probe
        assert by_name["team"]["state"] == "skipped" and "no key" in by_name["team"]["reason"], \
            by_name["team"]

        print(f"source_health check: PASS  ({len(source_health.REGISTRY)} sources registered; "
              f"missing key -> skipped, never raises; demo run -> {len(health)} skipped; "
              f"fake live run -> github live, harmonic failed (caught), team skipped (untouched))")
        return 0
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
        import shutil
        shutil.rmtree(ROOT / "out" / "_source_health_check", ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
