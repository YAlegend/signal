"""Offline check for network_radar (no keys, no network).

1) Loads a before/after fixture of smart-account followings and asserts the pure
   convergence function surfaces the right targets — including the reputation gate and the
   score that the existing `social` sub-score would produce.
2) NetworkRadarSource().fetch() with no NEYNAR_API_KEY -> [] (no error).
3) NetworkRadarSource().fetch() against a MOCKED Neynar client + store -> a converged
   target is injected as a real Candidate with the expected raw signal fields.
4) The Neynar-call retry helper (_get) retries once on a 429 then succeeds, without
   sleeping for real (the retry delay is monkeypatched out).

    PYTHONPATH=src python evals/network_radar_check.py
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from signalfund.sources import network_radar as nr  # noqa: E402
from signalfund.sources.network_radar import (  # noqa: E402
    NetworkRadarSource, _new_follow_convergence, MIN_CONVERGENCE,
)
from signalfund.scoring import social_bonus  # noqa: E402


class _FakeResponse:
    def __init__(self, status_code, data=None, headers=None):
        self.status_code = status_code
        self._data = data or {}
        self.headers = headers or {}

    def json(self):
        return self._data


class _FakeClient:
    """Stands in for the httpx.Client `_client(key)` returns. `plan` maps
    (path, params['fid'] or params['fids']) -> a response, or a list of responses
    consumed in call order (for the 429-then-200 retry scenario)."""

    def __init__(self, plan):
        self._plan = plan
        self.calls = []

    def get(self, path, params=None):
        key = (path, str((params or {}).get("fid") or (params or {}).get("fids")))
        self.calls.append(key)
        resp = self._plan[key]
        if isinstance(resp, list):
            return resp.pop(0) if len(resp) > 1 else resp[0]
        return resp

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeStore:
    """Stands in for Store: previous_following/snapshot_following, in-memory only."""

    def __init__(self, prev: dict):
        self._prev = prev
        self.snapshots = {}

    def previous_following(self, fid):
        return self._prev.get(str(fid))

    def snapshot_following(self, fid, following):
        self.snapshots[str(fid)] = set(str(f) for f in following)


def _following_body(fids):
    return {"users": [{"user": {"fid": int(f)}} for f in fids]}


def check_convergence_and_scoring() -> str:
    fx = json.loads((ROOT / "data" / "fixtures" / "network_radar_snapshots.json").read_text())
    prev = {k: set(v) for k, v in fx["before"].items()}
    now = {k: set(v) for k, v in fx["after"].items()}
    reps = fx["smart_account_reputation"]

    conv = _new_follow_convergence(prev, now)
    assert conv["9999"]["count"] == 3, conv
    assert conv["8888"]["count"] == 1, conv
    surfaced = {t for t, d in conv.items() if d["count"] >= MIN_CONVERGENCE}
    assert surfaced == {"9999"}, f"expected only 9999 to converge, got {surfaced}"

    gated = _new_follow_convergence(prev, now, reps, min_openrank=0.5)
    assert gated["9999"]["count"] == 2, gated          # 1003 excluded -> 2 of 3 remain
    assert "8888" not in gated, gated                  # only 1003 followed 8888 -> gone
    assert gated["9999"]["weight"] == round(0.92 + 0.80, 3), gated  # reputation-weighted

    raw = {"smart_followers": conv["9999"]["count"], "openrank_pct": 0.95,
           "neynar_score": 0.7, "account_age_days": 400}
    sb = social_bonus(raw)
    assert sb > 0, f"social_bonus should be >0 for a 3-way convergence, got {sb}"
    return f"9999 converged 3x -> social_bonus {sb}; rep-gate drops low-rep follower"


def check_no_key_skips() -> str:
    saved = os.environ.pop("NEYNAR_API_KEY", None)
    try:
        out = NetworkRadarSource().fetch(limit=10, store=_FakeStore({}))
        assert out == [], f"no key should skip gracefully -> [], got {out}"
    finally:
        if saved is not None:
            os.environ["NEYNAR_API_KEY"] = saved
    return "no key -> [] (no error)"


def check_mocked_key_injects_candidate(monkeypatch_smart_accounts, monkeypatch_openrank) -> str:
    os.environ["NEYNAR_API_KEY"] = "test-key"
    try:
        smart = [{"fid": "1001", "label": "vc-a"}, {"fid": "1002", "label": "vc-b"},
                 {"fid": "1003", "label": "vc-c"}]
        monkeypatch_smart_accounts(lambda path=None: smart)
        monkeypatch_openrank(lambda fids: {})  # no reputation data -> default weight 1.0

        # Baseline (prior run): 1001 & 1002 already follow 555; 1003 follows only 777.
        prev = {"1001": {"555"}, "1002": {"555"}, "1003": {"777"}}
        store = _FakeStore(prev)

        # This run: 1001 & 1002 ALSO now follow 9999 (new, 2-way convergence -> surfaced).
        # 1003 is unchanged.
        plan = {
            ("/v2/farcaster/following", "1001"): _FakeResponse(200, _following_body([555, 9999])),
            ("/v2/farcaster/following", "1002"): _FakeResponse(200, _following_body([555, 9999])),
            ("/v2/farcaster/following", "1003"): _FakeResponse(200, _following_body([777])),
            ("/v2/farcaster/user/bulk", "9999"): _FakeResponse(200, {"users": [
                {"username": "newproj", "display_name": "New Project",
                 "profile": {"bio": {"text": "building agent infra https://newproj.xyz"}},
                 "experimental": {"neynar_user_score": 0.8}},
            ]}),
        }
        fake_client = _FakeClient(plan)
        orig_client = nr._client
        nr._client = lambda key: fake_client
        try:
            out = NetworkRadarSource().fetch(limit=10, store=store)
        finally:
            nr._client = orig_client

        assert len(out) == 1, f"expected exactly 1 converged candidate, got {len(out)}: {out}"
        cand = out[0]
        assert cand.name == "New Project", cand.name
        assert cand.source == "network_radar", cand.source
        assert cand.raw["smart_followers"] == 2, cand.raw
        assert cand.raw["fid"] == "9999", cand.raw
        assert cand.url == "https://newproj.xyz", cand.url
        # the baseline was persisted too, so the NEXT run can diff against it
        assert store.snapshots["1001"] == {"555", "9999"}, store.snapshots
        return f"mocked convergence -> Candidate({cand.name!r}, smart_followers={cand.raw['smart_followers']})"
    finally:
        os.environ.pop("NEYNAR_API_KEY", None)


def check_rate_limit_retry(monkeypatch_sleep) -> str:
    slept = []
    monkeypatch_sleep(lambda s: slept.append(s))
    plan = {("/x", "None"): [_FakeResponse(429, headers={"retry-after": "0.01"}), _FakeResponse(200, {"ok": True})]}
    client = _FakeClient(plan)
    r = nr._get(client, "/x", {})
    assert r.status_code == 200, r.status_code
    assert len(client.calls) == 2, client.calls          # one 429, one retry that succeeded
    assert len(slept) == 1, slept                        # backed off exactly once
    return f"429 -> retried once (slept {slept[0]}s, mocked) -> 200"


def main() -> int:
    results = [check_convergence_and_scoring(), check_no_key_skips()]

    def _patch_smart_accounts(fn):
        nr.load_smart_accounts = fn

    def _patch_openrank(fn):
        nr._openrank_pcts = fn

    orig_load, orig_openrank, orig_sleep = nr.load_smart_accounts, nr._openrank_pcts, nr._sleep
    try:
        results.append(check_mocked_key_injects_candidate(_patch_smart_accounts, _patch_openrank))
    finally:
        nr.load_smart_accounts, nr._openrank_pcts = orig_load, orig_openrank

    try:
        results.append(check_rate_limit_retry(lambda fn: setattr(nr, "_sleep", fn)))
    finally:
        nr._sleep = orig_sleep

    print("network_radar check: PASS")
    for r in results:
        print(f"  - {r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
