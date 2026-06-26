"""Phase 0 backtest engine.

Answers the kill-shot question: would Signal have surfaced the deals that matter,
early enough to act? Scores each ground-truth company on its *point-in-time*
reconstructed signal (never today's data), then computes recall / lead time /
precision and applies a pre-registered decision rule (GREEN / YELLOW / RED).

Deterministic and offline: reconstruction (slow, networked) is a separate step
(reconstruct.py) that fills each company's `windows`; this engine only consumes them.

    PYTHONPATH=src python -m signalfund.backtest --demo
    PYTHONPATH=src python -m signalfund.backtest --ground-truth data/backtest/ground_truth.filled.json
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import statistics

import yaml

from . import scoring
from .models import Candidate

ROOT = pathlib.Path(__file__).resolve().parents[2]

# Score at/above which a window counts as "surfaced". Rescaled 50 -> 30 when the
# composite became a weighted blend (scoring.composite): backtest windows are
# fit-dominated (traction-only signal), so they compress by ~the fit weight (0.6),
# i.e. 50 * 0.6 = 30. This reproduces the prior decision (the same deals surface at
# the same leads). Override via SIGNAL_SURFACE_THRESHOLD; fix it *before* a real run.
SURFACE_THRESHOLD = float(os.getenv("SIGNAL_SURFACE_THRESHOLD", "30"))
LEAD_REQ_DAYS = int(os.getenv("SIGNAL_LEAD_REQ_DAYS", "14"))


def _window_days(key: str) -> int:
    """'-30d' -> 30."""
    return int(key.strip().lower().lstrip("-").rstrip("d"))


# Reconstructed sub-signal fields a window may carry (from reconstruct.py); passed
# through to the scorer so every signal is point-in-time backtest-able. Absent for the
# bundled sample, so this is a no-op there.
_SIGNAL_KEYS = (
    "commit_accel", "contributor_gini", "contributors",
    "stablecoin_inflow_30d", "real_tvl", "tvl_retention", "holder_gini",
    "prior_exit", "exit_size_usd", "repeat_founder_count", "same_domain",
    "technical_ceo", "frontier_lab_alum", "team_size",
    "smart_followers", "openrank_pct", "neynar_score", "power_badge", "account_age_days",
    "grant_program", "retro_grant", "hackathon_win", "post_event_active",
    "research_exit", "incorp_days",
)


def _candidate_from_window(company: str, w: dict) -> Candidate:
    raw = {}
    stars, prev, dd = w.get("stars"), w.get("stars_prev"), w.get("delta_days") or 7
    if isinstance(stars, (int, float)) and isinstance(prev, (int, float)) and dd:
        raw["velocity_per_day"] = round((stars - prev) / dd, 1)
        raw["stars"] = stars
    for k in _SIGNAL_KEYS:
        if k in w:
            raw[k] = w[k]
    return Candidate(name=company, source="backtest", url=w.get("url", ""),
                     summary=w.get("summary", ""), tags=w.get("tags", []), raw=raw)


def _evaluate_company(scorer, row: dict, threshold: float) -> dict:
    windows = row.get("windows", {})
    any_signal = False
    earliest_lead = None
    scores = {}
    for key in sorted(windows, key=_window_days, reverse=True):  # -60d before -14d
        w = windows[key]
        has = bool(w.get("has_signal"))
        any_signal = any_signal or has
        sc = scorer.score(_candidate_from_window(row["company"], w)).score if has else 0.0
        scores[key] = round(sc, 1)
        if has and sc >= threshold and earliest_lead is None:
            earliest_lead = _window_days(key)
    surfaced = earliest_lead is not None and earliest_lead >= LEAD_REQ_DAYS
    return {
        "company": row["company"],
        "label": row.get("label", "positive"),
        "outcome": row.get("outcome", ""),
        "channel": row.get("sourcing_channel", "unknown"),
        "segment": row.get("segment", "unknown"),
        "any_signal": any_signal,
        "surfaced": surfaced,
        "lead_days": earliest_lead,
        "best_score": max(scores.values()) if scores else 0.0,
        "scores": scores,
    }


def _decide(recall, median_lead, precision, no_signal_rate):
    if recall < 0.25 or no_signal_rate > 0.70:
        return "RED", ("Public signal is largely absent or lagging for these deals — "
                       "stop investing in sourcing; redirect to Memo (synthesis) + Pulse.")
    if recall >= 0.50 and median_lead >= LEAD_REQ_DAYS and precision >= 0.50:
        return "GREEN", "Sourcing surfaces the deals that matter, early and at workable precision — fund it."
    return "YELLOW", ("Sourcing works in part (segment- or channel-specific). Narrow it to where it "
                      "demonstrably works; build Memo + Pulse for the rest.")


def _rate_table(results, key):
    """recall broken down by a categorical field (channel/segment), positives only."""
    out = {}
    for r in [x for x in results if x["label"] == "positive"]:
        b = out.setdefault(r[key], [0, 0])
        b[1] += 1
        b[0] += int(r["surfaced"])
    return out


def run(ground_truth_path: str, thesis_path: str = None, out_dir: str = None,
        threshold: float = SURFACE_THRESHOLD) -> dict:
    thesis_path = thesis_path or str(ROOT / "config" / "thesis.yaml")
    out_dir = out_dir or os.getenv("SIGNAL_OUT_DIR", "out")
    thesis = yaml.safe_load(pathlib.Path(thesis_path).read_text(encoding="utf-8"))
    gt = json.loads(pathlib.Path(ground_truth_path).read_text(encoding="utf-8"))
    scorer = scoring.get_scorer(thesis)

    results = [_evaluate_company(scorer, row, threshold) for row in gt]
    pos = [r for r in results if r["label"] == "positive"]
    neg = [r for r in results if r["label"] == "negative"]
    surf_pos = [r for r in pos if r["surfaced"]]
    surf_neg = [r for r in neg if r["surfaced"]]

    recall = len(surf_pos) / len(pos) if pos else 0.0
    leads = [r["lead_days"] for r in surf_pos if r["lead_days"]]
    median_lead = statistics.median(leads) if leads else 0
    precision = len(surf_pos) / ((len(surf_pos) + len(surf_neg)) or 1)
    no_signal_rate = sum(1 for r in pos if not r["any_signal"]) / len(pos) if pos else 0.0

    decision, reason = _decide(recall, median_lead, precision, no_signal_rate)
    metrics = {"recall": round(recall, 2), "median_lead_days": median_lead,
               "precision_proxy": round(precision, 2),
               "no_signal_rate": round(no_signal_rate, 2),
               "n_positive": len(pos), "n_negative": len(neg),
               "threshold": threshold, "lead_req_days": LEAD_REQ_DAYS}

    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    md = _render(metrics, decision, reason, results,
                 _rate_table(results, "channel"), _rate_table(results, "segment"))
    (out / "backtest_report.md").write_text(md, encoding="utf-8")
    (out / "backtest_report.json").write_text(
        json.dumps({"decision": decision, "reason": reason,
                    "metrics": metrics, "companies": results}, indent=2), encoding="utf-8")

    print(f"[backtest] decision: {decision}  |  recall={metrics['recall']} "
          f"median_lead={median_lead}d precision~={metrics['precision_proxy']} "
          f"no_signal={metrics['no_signal_rate']}")
    print(f"[backtest] wrote {out/'backtest_report.md'}")
    return {"decision": decision, "metrics": metrics, "results": results}


def _render(m, decision, reason, results, by_channel, by_segment) -> str:
    emoji = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}[decision]
    L = [f"# Signal — Phase 0 Backtest Report",
         f"_Point-in-time backtest · surface threshold {m['threshold']} · "
         f"lead requirement ≥ {m['lead_req_days']}d_", "",
         f"## Decision: {emoji} {decision}", "", f"> {reason}", "",
         "## Scorecard", "",
         "| Metric | Value | Read |",
         "|---|---|---|",
         f"| Recall @≥{m['lead_req_days']}d lead | **{m['recall']}** | of {m['n_positive']} positives surfaced early |",
         f"| Median lead time | **{m['median_lead_days']}d** | how early, for the ones we caught |",
         f"| Precision proxy | **{m['precision_proxy']}** | surfaced positives vs. surfaced fizzles |",
         f"| No-signal rate | **{m['no_signal_rate']}** | positives with *no* public footprint at the window (F6) |",
         ""]

    L += ["## Per-company", "",
          "| Company | Label | Channel | Any signal? | Surfaced | Lead | Best score |",
          "|---|---|---|---|---|---|---|"]
    for r in sorted(results, key=lambda x: (x["label"], -x["best_score"])):
        lead = f"{r['lead_days']}d" if r["lead_days"] else "—"
        L.append(f"| {r['company']} | {r['label']} | {r['channel']} | "
                 f"{'yes' if r['any_signal'] else 'no'} | {'✅' if r['surfaced'] else '—'} | "
                 f"{lead} | {r['best_score']} |")
    L.append("")

    def cov(title, table):
        rows = [f"### {title}", "", "| Group | Recall (surfaced / positives) |", "|---|---|"]
        for g, (s, n) in sorted(table.items()):
            rows.append(f"| {g} | {s}/{n} ({round(100*s/n) if n else 0}%) |")
        return rows + [""]

    L += ["## Coverage", ""] + cov("By sourcing channel", by_channel) + cov("By segment", by_segment)

    L += ["## Caveats", "",
          "- Directional, not statistically significant at this N — read with the no-signal rate.",
          "- Recall is scoped to *reconstructable* sources (GitHub via GH Archive, web via Wayback, "
          "Harmonic first-seen). X/Farcaster history is excluded — a known blind spot.",
          "- Scored with the current `thesis.yaml`; early-stage thesis may have differed.", ""]
    return "\n".join(L)


def main():
    p = argparse.ArgumentParser(description="Signal Phase 0 backtest")
    p.add_argument("--demo", action="store_true", help="use the bundled sample ground truth")
    p.add_argument("--ground-truth", default=None, help="path to a filled ground_truth.json")
    p.add_argument("--out", default=None)
    p.add_argument("--threshold", type=float, default=SURFACE_THRESHOLD)
    args = p.parse_args()
    gt = args.ground_truth
    if args.demo or not gt:
        gt = str(ROOT / "data" / "backtest" / "ground_truth.sample.json")
    run(gt, out_dir=args.out, threshold=args.threshold)


if __name__ == "__main__":
    main()
