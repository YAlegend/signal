"""Offline eval: does the scorer rank on-thesis companies above the bar?

Evals, not vibes. Run:  PYTHONPATH=src python evals/run_evals.py
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml  # noqa: E402

from signalfund.models import Candidate  # noqa: E402
from signalfund.scoring import HeuristicScorer  # noqa: E402

# Surface threshold on the composite. Re-tuned 40 -> 20 when composite() moved from
# additive-then-clamp to a weighted blend (fit*0.6 + signal_strength*0.4 + credibility):
# the blend compresses scores ~0.5x, so 20 is the equivalent cut. It sits in the natural
# gap between off-thesis (tops out ~10) and on-thesis (~24+) in eval_set.jsonl, preserving
# the exact same pass/fail classifications as the old 40 (precision/recall/accuracy floors
# below are unchanged). See scoring.py composite() and config/thesis.yaml composite_weights.
THRESHOLD = 20.0

# CI regression floors — run_evals exits non-zero if the scorer drops below any.
# Anchored at/under the documented baseline so legit eval additions pass but a real
# regression fails. Override per-metric via env (e.g. SIGNAL_EVAL_MIN_RECALL=0.90).
FLOORS = {
    "precision": float(os.getenv("SIGNAL_EVAL_MIN_PRECISION", "1.00")),
    "recall": float(os.getenv("SIGNAL_EVAL_MIN_RECALL", "0.88")),
    "accuracy": float(os.getenv("SIGNAL_EVAL_MIN_ACCURACY", "0.90")),
}


def main():
    thesis = yaml.safe_load((ROOT / "config" / "thesis.yaml").read_text(encoding="utf-8"))
    scorer = HeuristicScorer(thesis)
    rows = [json.loads(line) for line in
            (ROOT / "evals" / "eval_set.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]

    tp = fp = tn = fn = 0
    print(f"{'company':30} {'score':>6}  {'pred':>5}  {'label':>5}  result")
    print("-" * 60)
    for row in rows:
        c = Candidate(name=row["name"], source="eval", url=row.get("url", ""),
                      summary=row.get("summary", ""), tags=row.get("tags", []),
                      raw=row.get("raw", {}))
        s = scorer.score(c)
        pred, label = s.score >= THRESHOLD, bool(row["label"])
        tp += int(pred and label)
        fp += int(pred and not label)
        tn += int((not pred) and (not label))
        fn += int((not pred) and label)
        print(f"{row['name'][:30]:30} {s.score:6.1f}  {str(pred):>5}  {str(label):>5}  "
              f"{'ok' if pred == label else 'MISS'}")

    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    acc = (tp + tn) / len(rows) if rows else 0.0
    print("-" * 60)
    print(f"precision={prec:.2f}  recall={rec:.2f}  accuracy={acc:.2f}  "
          f"(threshold={THRESHOLD}, n={len(rows)})")

    # ---- regression gate (CI) ----
    got = {"precision": prec, "recall": rec, "accuracy": acc}
    failures = [(m, got[m], FLOORS[m]) for m in FLOORS if got[m] + 1e-9 < FLOORS[m]]
    if failures:
        print("\nFAIL — scorer regressed below floor:")
        for m, g, f in failures:
            print(f"  {m}={g:.2f} < min {f:.2f}")
        return 1
    print("\nPASS — meets floors  "
          f"(precision>={FLOORS['precision']:.2f}  recall>={FLOORS['recall']:.2f}  "
          f"accuracy>={FLOORS['accuracy']:.2f}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
