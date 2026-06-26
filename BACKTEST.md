# Phase 0 Backtest — Claude Code playbook

This is the kill-shot test: *would Signal have surfaced the deals that matter, early enough to act?*
Claude Code drives the whole loop. Reconstruction (networked) and scoring (deterministic) are separate
steps, so the slow part is isolated and the result is reproducible.

## See it work first (offline, no setup)

```bash
PYTHONPATH=src python -m signalfund.backtest --demo
cat out/backtest_report.md
```

This runs the bundled sample ground truth and prints a 🟢/🟡/🔴 decision. Use it to understand the
output before running on real deals.

## Run it for real — 4 steps

**Step 1 — assemble ground truth (PM + partners).**
Copy `data/backtest/ground_truth.sample.json` to `ground_truth.json` and replace with real deals:
~20–40 positives (invested / wanted-but-lost / ones-that-got-away) and ~20 fizzles. For each, fill
`first_touch_date`, `obvious_date`, `sourcing_channel`, `segment`, `outcome`, `label`, and
`public_handles` (github repo, site). Leave `windows` empty — Step 2 fills them.
Validate `first_touch_date` against email/calendar, not memory.

> A starter set built from Frachtis's *public* portfolio ships at
> `data/backtest/ground_truth.frachtis.json` — now **10 real positives** (Index Network, OyaChat, Lys
> Labs, Enclave Money, Turtle Club, Bless, Infinity Ground, Hyve, Aizel, Fireplace) **+ 7 real negatives**
> (public fizzles, repo-verified: Iron Finance, Saddle Finance, Fei/Tribe DAO, Multichain, Nomad,
> Zerebro, Showtime — see each row's `note` for the failure evidence + sources). Caveats: for positives
> `obvious_date` is the public listing date and `sourcing_channel` is unknown (so the channel cut is
> weaker than with internal data); for negatives `obvious_date` is a peak-hype proxy and
> `sourcing_channel` is `public`. **`windows` are empty for every row pending reconstruction (Step 2) —
> which needs a `GITHUB_TOKEN`** (several negatives are large repos that will exhaust the
> unauthenticated 60/hr limit).

**Step 2 — reconstruct point-in-time signal (Claude Code).**
Fill each company's `windows` with the signal that existed *as of* each lookback date.

- Default path — needs only `GITHUB_TOKEN` (uses GitHub stargazer timestamps; `pip install httpx`):
  ```bash
  PYTHONPATH=src python -m signalfund.reconstruct ground_truth.json ground_truth.filled.json
  ```
  For very large repos, optionally add BigQuery (`pip install google-cloud-bigquery` + GCP creds) as a fallback.
- Where BigQuery isn't available, Claude Code can fill a repo's stars-as-of-date directly with the
  `bq` CLI or the GH Archive query (see Appendix A of `Signal_Phase0_Backtest_Plan.md`), and check
  site existence via the Wayback availability API. Set `has_signal: false` for any company with no
  recoverable public footprint at a window — that absence is itself the finding (the F6 test).

**Step 3 — run the backtest (deterministic).**
```bash
PYTHONPATH=src python -m signalfund.backtest --ground-truth ground_truth.filled.json
```

**Step 4 — read the decision.**
`out/backtest_report.md` prints the 🟢/🟡/🔴 call against the pre-registered rule, the scorecard
(recall / lead time / precision proxy / no-signal rate), per-company detail, and coverage by channel
and segment. Claude Code should summarize it and recommend the roadmap implication.

## The pre-registered decision rule (don't change after seeing results)

| Outcome | Trigger | Action |
|---|---|---|
| 🟢 GREEN | recall ≥ 0.50 · median lead ≥ 14d · precision proxy ≥ 0.50 | fund Signal sourcing |
| 🟡 YELLOW | partial / segment-specific | narrow sourcing to where it works; build Memo + Pulse |
| 🔴 RED | recall < 0.25 **or** > 70% of positives had no public signal | stop sourcing; redirect to Memo + Pulse |

Thresholds are overridable via env (`SIGNAL_SURFACE_THRESHOLD`, `SIGNAL_LEAD_REQ_DAYS`) but should be
fixed *before* the run.

## Why this is trustworthy
- **No look-ahead:** scoring only ever sees a window's reconstructed-at-T signal.
- **Precision, not just recall:** fizzles are in the set, so surfacing everything is penalised.
- **The dataset is reusable:** the labeled companies seed the scorer's eval set — so even a RED result
  leaves a durable asset.
