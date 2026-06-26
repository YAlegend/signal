"""Offline check for the free-tier rate-limit stabilisation (no live key, no real sleeping).

Asserts (1) a rate-limited call RETRIES and returns the REAL model result — not a heuristic
fallback — and only gives up after retries are exhausted (then re-raises so the caller's
graceful fallback kicks in), and (2) the throttle spaces a burst to within the configured
RPM, using a fake clock (no wall-clock sleeping).

    PYTHONPATH=src python evals/ratelimit_check.py
"""
from __future__ import annotations

import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import signalfund.llm as llm  # noqa: E402


class RateLimitError(Exception):
    """Name contains 'ratelimit' so llm._is_rate_limit treats it like a provider 429."""


def _retry_tests():
    captured = []
    llm._sleep = lambda s: captured.append(s)      # never actually sleep
    os.environ["SIGNAL_LLM_MAX_RPM"] = "0"          # disable throttle for the retry tests
    os.environ["SIGNAL_LLM_MAX_RETRIES"] = "4"

    # (a) rate-limit twice then succeed -> returns the REAL model output, not heuristic
    n = {"c": 0}
    def flaky():
        n["c"] += 1
        if n["c"] <= 2:
            raise RateLimitError("429 Too Many Requests")
        return "REAL_MODEL_OUTPUT"
    out = llm._with_retry(flaky)
    assert out == "REAL_MODEL_OUTPUT", out
    assert n["c"] == 3, f"expected 2 retries then success, got {n['c']} calls"

    # (b) exhausted -> re-raises (so caller falls back to heuristic + llm_fallback risk)
    os.environ["SIGNAL_LLM_MAX_RETRIES"] = "2"
    m = {"c": 0}
    def always():
        m["c"] += 1
        raise RateLimitError("429")
    try:
        llm._with_retry(always)
        raise AssertionError("should have re-raised after retries")
    except RateLimitError:
        pass
    assert m["c"] == 3, f"retries(2)+1 attempts expected, got {m['c']}"

    # (c) a NON-rate-limit error raises immediately, no retry
    k = {"c": 0}
    def boom():
        k["c"] += 1
        raise ValueError("bad json")
    try:
        llm._with_retry(boom)
        raise AssertionError("non-rate-limit error should raise")
    except ValueError:
        pass
    assert k["c"] == 1, f"non-rate-limit must not retry, got {k['c']}"
    return n["c"], m["c"]


def _throttle_tests():
    os.environ["SIGNAL_LLM_MAX_RPM"] = "60"   # 1 token/sec
    os.environ["SIGNAL_LLM_BURST"] = "2"
    min_interval = 60.0 / 60.0

    # fake clock: sleeping just advances it
    clock = [0.0]
    sleeps = []
    llm._monotonic = lambda: clock[0]
    def fake_sleep(s):
        sleeps.append(round(s, 4)); clock[0] += s
    llm._sleep = fake_sleep
    llm._rl_tokens, llm._rl_last = None, 0.0

    ts = []
    for _ in range(6):
        llm._throttle()
        ts.append(round(clock[0], 4))

    # burst of 2 -> first two calls immediate; remaining four spaced one interval apart
    assert sleeps == [1.0, 1.0, 1.0, 1.0], f"burst spacing wrong: {sleeps}"
    gaps = [round(ts[i] - ts[i - 1], 4) for i in range(1, 6)]
    assert gaps[0] == 0.0, f"calls within burst must not space: {gaps}"
    assert all(g >= min_interval - 1e-6 for g in gaps[2:]), f"steady-state must stay >= RPM spacing: {gaps}"

    # isolated call after a long idle -> no sleep (interactive memo must not stall)
    llm._rl_tokens, llm._rl_last = None, 0.0
    clock[0], sleeps2 = 10_000.0, []
    llm._sleep = lambda s: sleeps2.append(s)
    llm._throttle()
    assert sleeps2 == [], f"isolated call must be a no-op, slept {sleeps2}"
    return ts, gaps


def main() -> int:
    retry = _retry_tests()
    ts, gaps = _throttle_tests()
    print(f"ratelimit check: PASS  (retry: succeeds after 2x 429 -> real output; exhaust -> re-raise; "
          f"non-429 -> no retry · throttle: burst=2 then spaced {gaps[2:]} @ 60rpm, isolated call no-op)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
