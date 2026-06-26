# Signal — Phase 0 Backtest Report
_Point-in-time backtest · surface threshold 30.0 · lead requirement ≥ 14d_

## Decision: 🟡 YELLOW

> Sourcing works in part (segment- or channel-specific). Narrow it to where it demonstrably works; build Memo + Pulse for the rest.

## Scorecard

| Metric | Value | Read |
|---|---|---|
| Recall @≥14d lead | **0.4** | of 5 positives surfaced early |
| Median lead time | **45.0d** | how early, for the ones we caught |
| Precision proxy | **0.67** | surfaced positives vs. surfaced fizzles |
| No-signal rate | **0.2** | positives with *no* public footprint at the window (F6) |

## Per-company

| Company | Label | Channel | Any signal? | Surfaced | Lead | Best score |
|---|---|---|---|---|---|---|
| hypezk | negative | public | yes | ✅ | 30d | 68.3 |
| yieldvault | negative | public | yes | — | — | 24.9 |
| moonrocket | negative | public | yes | — | — | 0.0 |
| mandate-labs | positive | public | yes | ✅ | 60d | 49.6 |
| veritas-zk | positive | public | yes | ✅ | 30d | 37.4 |
| latticevault | positive | public | yes | — | — | 25.9 |
| ledgerlytics | positive | inbound | yes | — | — | 15.6 |
| payrail | positive | warm_intro | no | — | — | 0.0 |

## Coverage

### By sourcing channel

| Group | Recall (surfaced / positives) |
|---|---|
| inbound | 0/1 (0%) |
| public | 2/3 (67%) |
| warm_intro | 0/1 (0%) |

### By segment

| Group | Recall (surfaced / positives) |
|---|---|
| agent_control_planes | 1/2 (50%) |
| crypto_infra | 1/1 (100%) |
| defi_infra | 0/1 (0%) |
| post_quantum | 0/1 (0%) |

## Caveats

- Directional, not statistically significant at this N — read with the no-signal rate.
- Recall is scoped to *reconstructable* sources (GitHub via GH Archive, web via Wayback, Harmonic first-seen). X/Farcaster history is excluded — a known blind spot.
- Scored with the current `thesis.yaml`; early-stage thesis may have differed.
