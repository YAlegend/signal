"""Post the sourcing digest to Slack — best-effort like every other Signal source: a missing
SLACK_WEBHOOK_URL is a skip (never raises), but a webhook that actually fails to deliver DOES
raise (non-zero exit), so the Actions job goes red and GitHub's own built-in failure
notification is the alert. Deliberately no separate alerting system watching this one.

Run:  PYTHONPATH=src SLACK_WEBHOOK_URL=https://hooks.slack.com/... python scripts/notify_slack.py
      add --dry-run to build + print the message without sending (works with no webhook set).
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request


def _out_dir() -> pathlib.Path:
    return pathlib.Path(os.getenv("SIGNAL_OUT_DIR", "out"))


def build_message(digest: list, top: int = 5, run_url: str = "") -> dict:
    """Build a Slack payload (plain `text`, Slack renders the mrkdwn) from digest.json's
    list of {candidate, score, matched_themes, ...} entries — top N by score."""
    ranked = sorted(digest, key=lambda d: d.get("score", 0), reverse=True)[:top]
    lines = []
    for d in ranked:
        cand = d.get("candidate", {})
        name = cand.get("name", "?")
        url = cand.get("url", "")
        score = d.get("score", 0)
        themes = ", ".join(d.get("matched_themes") or []) or "—"
        link = f"<{url}|{name}>" if url else name
        lines.append(f"*{link}* — {score:.1f}/100 · {themes}")
    body = "\n".join(lines) if lines else "_No candidates surfaced this run._"
    header = f"*Signal — daily digest* ({len(digest)} candidates scored, top {len(ranked)} shown)"
    if run_url:
        header += f"  ·  <{run_url}|full run>"
    return {"text": f"{header}\n\n{body}"}


def _run_url() -> str:
    server, repo, run_id = (os.getenv("GITHUB_SERVER_URL", ""), os.getenv("GITHUB_REPOSITORY", ""),
                            os.getenv("GITHUB_RUN_ID", ""))
    return f"{server}/{repo}/actions/runs/{run_id}" if server and repo and run_id else ""


def send(payload: dict, webhook: str, timeout: float = 15.0) -> None:
    """POST to the Slack incoming webhook. Raises on any non-2xx or transport failure —
    delivery failure must be loud, not swallowed."""
    req = urllib.request.Request(webhook, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status >= 300:
            raise RuntimeError(f"Slack webhook returned HTTP {resp.status}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=5, help="how many ranked candidates to include")
    ap.add_argument("--dry-run", action="store_true", help="build + print the message, never send")
    args = ap.parse_args()

    digest_path = _out_dir() / "digest.json"
    if not digest_path.is_file():
        print(f"[notify-slack] no digest at {digest_path} — nothing to send")
        return 0

    digest = json.loads(digest_path.read_text(encoding="utf-8"))
    payload = build_message(digest, top=args.top, run_url=_run_url())

    webhook = os.getenv("SLACK_WEBHOOK_URL")
    if args.dry_run or not webhook:
        reason = "--dry-run" if args.dry_run else "SLACK_WEBHOOK_URL not set"
        print(f"[notify-slack] {reason} — skipping send. Message would be:\n{payload['text']}")
        return 0

    try:
        send(payload, webhook)
    except (urllib.error.URLError, RuntimeError, TimeoutError) as e:
        print(f"[notify-slack] delivery failed: {e}", file=sys.stderr)
        raise SystemExit(1) from e

    print(f"[notify-slack] posted digest ({len(digest)} candidates, top {args.top}) to Slack")
    return 0


if __name__ == "__main__":
    sys.exit(main())
