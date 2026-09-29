"""Offline check for scripts/notify_slack.py (no network — mocks urllib for the POST paths).

Asserts:
  (a) build_message ranks by score, caps at `top`, and includes name/score/themes/link.
  (b) an empty digest produces a "no candidates" message rather than crashing.
  (c) no SLACK_WEBHOOK_URL -> main() logs + exits 0 (skip, never raise — same rule as every
      other Signal source on a missing key).
  (d) a webhook that returns non-2xx -> send() raises (delivery failure must be loud).
  (e) a webhook that raises a URLError (network down) -> send() propagates it.
  (f) a successful POST -> send() returns cleanly and does not raise.

    PYTHONPATH=src python evals/notify_slack_check.py
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import urllib.error

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import notify_slack  # noqa: E402

DIGEST = [
    {"candidate": {"name": "low", "url": "https://low.xyz"}, "score": 10.0, "matched_themes": ["defi_infra"]},
    {"candidate": {"name": "high", "url": "https://high.xyz"}, "score": 90.0, "matched_themes": ["crypto_infra"]},
    {"candidate": {"name": "mid", "url": "https://mid.xyz"}, "score": 50.0, "matched_themes": []},
]


class _FakeResp:
    def __init__(self, status):
        self.status = status
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


def main() -> int:
    # (a) ranks by score desc, caps at top=2, includes name + score + themes + link.
    msg = notify_slack.build_message(DIGEST, top=2)
    text = msg["text"]
    assert "high" in text and "low" not in text, f"should rank+cap to top 2: {text}"
    assert text.index("high") < text.index("mid"), f"not ranked by score desc: {text}"
    assert "90.0/100" in text and "crypto_infra" in text and "<https://high.xyz|high>" in text, text

    # (b) empty digest -> no crash, explicit "no candidates" message.
    empty = notify_slack.build_message([], top=5)
    assert "No candidates" in empty["text"], empty["text"]

    # (c) no webhook configured -> the CLI skips cleanly (exit 0), never raises. Run as a real
    # subprocess (main() reads sys.argv + env directly) against a fixture digest.json.
    with tempfile.TemporaryDirectory() as tmp:
        (pathlib.Path(tmp) / "digest.json").write_text(json.dumps(DIGEST), encoding="utf-8")
        env = {**os.environ, "SIGNAL_OUT_DIR": tmp}
        env.pop("SLACK_WEBHOOK_URL", None)
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "notify_slack.py")],
                           env=env, capture_output=True, text=True)
        assert r.returncode == 0, f"no-webhook run should exit 0: {r.returncode} {r.stderr}"
        assert "skipping send" in r.stdout and "high" in r.stdout, r.stdout

    # (d) non-2xx response -> send() raises.
    import unittest.mock as mock
    with mock.patch("notify_slack.urllib.request.urlopen", return_value=_FakeResp(500)):
        try:
            notify_slack.send({"text": "x"}, "https://hooks.slack.example/x")
            raise AssertionError("expected RuntimeError on HTTP 500")
        except RuntimeError as e:
            assert "500" in str(e), e

    # (e) transport failure -> send() propagates URLError.
    with mock.patch("notify_slack.urllib.request.urlopen",
                    side_effect=urllib.error.URLError("connection refused")):
        try:
            notify_slack.send({"text": "x"}, "https://hooks.slack.example/x")
            raise AssertionError("expected URLError to propagate")
        except urllib.error.URLError:
            pass

    # (f) success -> send() returns cleanly, no raise.
    with mock.patch("notify_slack.urllib.request.urlopen", return_value=_FakeResp(200)):
        notify_slack.send({"text": "x"}, "https://hooks.slack.example/x")  # must not raise

    print("notify_slack check: PASS  (ranks + caps + formats correctly, empty digest handled, "
          "non-2xx and transport failures raise from send(), success does not)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
