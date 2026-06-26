# Signal — Phase 0 Backtest Plan

### Does automated public signal surface the deals that matter — early enough to act?

**Owner:** ML Engineer (execution) · **Technical PM** (ground truth + decision) · **Partners** (validate truth set) · **Production Mgr** (data access)
**Duration:** ~1 week · **Output:** a one-page go/no-go decision memo + a reusable labeled dataset

---

## Why this exists — the decision at stake

The entire roadmap rests on one assumption: that public, scrapeable signal is **additive to a partner's network** at pre-seed. If the best deals are relationship-sourced *before* any public footprint exists, then Signal-as-sourcing has structurally low recall, and we should redirect effort to synthesis (Memo) and monitoring (Pulse).

This backtest answers that **before we build more** — cheaply, using deals whose outcomes we already know. It is the cheapest possible test of the riskiest assumption.

## Hypotheses

- **H1 (the bet):** Signal would have surfaced **≥ 50%** of fundable deals **≥ 2 weeks** before they became obvious, at workable precision.
- **H0 (the kill-shot):** Public signal is absent or lagging for most relationship-sourced pre-seed deals → recall too low to justify building sourcing.

## Pre-registered decision rule

*Set before running, so we interpret the result honestly instead of rationalizing it after.*

| Outcome | Trigger | Action |
|---------|---------|--------|
| 🟢 **GREEN** | Recall ≥ 50% **and** median lead ≥ 2 wks **and** review burden ≤ ~50 candidates per real hit | Fund Signal sourcing as specced (Phase 1). |
| 🟡 **YELLOW** | Recall 25–49%, **or** strong only in one segment (e.g. OSS infra), **or** lead time < 2 wks | Narrow sourcing to the segment(s) that work; de-prioritize the rest; still build Memo + Pulse. |
| 🔴 **RED** | Recall < 25%, **or** > 70% of positives had no reconstructable public signal at the early window | Stop investing in sourcing. Reallocate to Memo (synthesis) + Pulse (monitoring). |

"Obvious" = the round closed, or the company hit a mainstream list/announcement. "Review burden" is the precision proxy (below).

---

## Ground truth (the hard part)

**Positives (~20–40 companies):** deals the fund (a) invested in, (b) seriously wanted but lost/passed and regrets, or (c) clear "ones that got away" that became winners. These are the deals that *matter*.

**Negatives / noise (~20):** projects that were *hyped then fizzled* — needed to read false-positive rate.

For each company, the PM assembles a point-in-time record (partners validate dates and channel):

| Field | Example | Why |
|-------|---------|-----|
| company | `mandate-labs` | identity |
| first_touch_date (T) | 2025-03-04 | the date the fund ideally wanted to know |
| obvious_date | 2025-06-20 | round close / mainstream moment |
| stage_at_T | pre-seed / stealth | was it even fundable yet |
| sourcing_channel | warm intro / inbound / conference / cold / **public** | the F6 test |
| outcome | invested / passed / lost / fizzled | label |
| public_handles | github org, site, founder X | reconstruction targets |

**Source of truth:** Airtable/CRM, partner memory, and — to fight hindsight bias in the dates — email/calendar timestamps for the genuine first touch.

---

## The critical method — point-in-time reconstruction (no look-ahead)

We score each company **using only data that existed as of its early window T**, never today's data. A backtest that scores a company on its *current* 10k stars is theater. This is the integrity of the whole test.

Reconstruct historical signal per source:

- **GitHub stars/velocity →** GH Archive (public BigQuery dataset of every GitHub event since 2011). Count `WatchEvent`s up to date T to get stars-as-of-T; difference over a window gives point-in-time velocity. *(Appendix A.)*
- **Site / docs →** Wayback Machine snapshot nearest to but ≤ T.
- **Funding / first-seen →** Harmonic / Crunchbase founded & first-seen dates.
- **Research →** arXiv / IACR — already timestamped.
- **Untestable (X, Farcaster):** historical state is hard to reconstruct → **exclude and report as a known blind spot**, scoping recall to reconstructable channels.

Run the current `thesis.yaml` scorer over each company's reconstructed-at-T signal, at the production threshold.

## Metrics

- **Recall@early-window** *(the number):* of positives, the fraction Signal scores ≥ threshold using data ≤ (obvious_date − 2 wks).
- **Lead time:** distribution of (date Signal would have flagged) vs. obvious_date. Flagging a deal the day it closes is worthless; we want weeks.
- **Precision proxy / review burden:** replay the same historical windows, count *total* candidates Signal would have surfaced, and have a partner rate a random sample. Yields "candidates to skim per real hit." Recall without this is meaningless — surfacing everything is 100% recall and 0 value.
- **"Any public signal at all?" cut:** of the positives, how many had *any* reconstructable footprint at T. This isolates the F6 question (is the signal even there?) from scorer quality, and is robust even at small N.
- **Coverage by segment & channel:** where Signal catches (OSS infra, dev tooling) vs. is blind (stealth, non-code, relationship-only).

---

## Workplan (1 week)

| Day | Work | Owner |
|-----|------|-------|
| 1 | Assemble + date-validate the ground-truth set (positives, fizzles) | PM + Partners |
| 2 | Build point-in-time reconstruction harness (GH Archive query, Wayback, Harmonic first-seen) | ML Eng |
| 3–4 | Score each company at its window; compute recall + lead time; sample the haystack for precision | ML Eng |
| 4 | Segment/channel cross-tabs + the "any signal at all?" cut | ML Eng + PM |
| 5 | Write up against the decision rule; recommend GREEN / YELLOW / RED | PM |

## Threats to validity & mitigations

- **Look-ahead bias** → point-in-time reconstruction (the whole method).
- **Survivorship bias** → include hyped-then-fizzled projects and passed deals, not just winners.
- **Small N** → treat as *directional*, not significant; lean on the robust "any signal?" cut; report honestly, no false precision.
- **Ground-truth date error** → cross-check first-touch dates against email/calendar, not memory alone.
- **Thesis drift** → score with today's `thesis.yaml`; note that early-stage thesis differed.
- **Reconstruction gaps (X/Farcaster)** → scope recall to reconstructable sources; state the coverage caveat explicitly.

## What each outcome means

GREEN funds sourcing; YELLOW narrows it to where it demonstrably works; RED redirects the team to synthesis and monitoring. **Either way the labeled truth set becomes the seed eval set** for the scorer's precision tracking — so even a RED result produces a durable, reusable asset. The week is never wasted.

---

## Appendix A — GH Archive point-in-time star reconstruction (sketch)

```sql
-- Stars for a repo as of a date (WatchEvent == "starred" in the GH Archive schema).
-- Run per repo, at T and T-Δ, to get point-in-time velocity = (stars_T - stars_TΔ) / Δ.
SELECT COUNT(*) AS stars_as_of_T
FROM `githubarchive.day.2025*`
WHERE type = 'WatchEvent'
  AND repo.name = 'mandate-labs/mandate'
  AND created_at <= TIMESTAMP('2025-04-01');
```

Note: GH Archive only captures events within its coverage window, which is fine for *velocity over a recent window* (what Signal actually uses). Cross-check totals against the repo's `created_at` to sanity-check.

## Appendix B — ground-truth row (JSON template)

```json
{
  "company": "mandate-labs",
  "first_touch_date": "2025-03-04",
  "obvious_date": "2025-06-20",
  "stage_at_T": "pre-seed",
  "sourcing_channel": "warm_intro",
  "outcome": "passed_regret",
  "public_handles": {"github": "mandate-labs", "site": "https://...", "founder_x": "@..."},
  "label": "positive"
}
```
