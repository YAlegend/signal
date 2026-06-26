# Signals Build Spec — implementing the multi-signal scorer

**For Claude Code.** Implements `CLAUDE.md` → "Signals to add" and `docs/Sourcing_Signals_Research.md`.
**Additive and incremental** — ship one ticket at a time. Nothing here changes the pipeline spine
(`gather → dedup → enrich → score → digest/dashboard/memo`). After each ticket: run the demo + evals,
confirm the new sub-score shows in `out/dashboard.html`, then move on.

```
PYTHONPATH=src python -m signalfund --demo && PYTHONPATH=src python evals/run_evals.py
```

---

## Architecture change (read once)

Today the composite (in `scoring.py`) is:

```
score = thesis_fit + traction_bonus + credibility_adj   # exposed in ScoredCandidate.subscores
```

Add five reputation-weighted sub-scores. Each is computed from fields a *signal source* writes onto
`Candidate.raw`:

```
composite = clamp(0..100,
    thesis_fit          # existing
  + traction_bonus      # existing  (0..15)
  + credibility_adj     # existing  (-60..+5)
  + code_health_bonus   # NEW (0..15)
  + team_bonus          # NEW (0..20)
  + social_bonus        # NEW (0..12)
  + onchain_bonus       # NEW (0..12)
  + pre_public_bonus )  # NEW (0..15)
```

**Rules that apply to EVERY new signal (non-negotiable):**

1. **Graceful absence** — if the data isn't on the candidate, the bonus is `0` (exactly like
   `traction_bonus` today). Partial data must never crash or penalise.
2. **Reputation-weighted, ratio-based** — never raw counts. Weight by source credibility, gate on
   account/wallet age, score ratios. (See the research doc for why.)
3. **Exposed** — add each to the `subscores` dict so `dashboard.py` / `digest.py` render it and a human
   sees *why*.
4. **Eval'd** — add ≥2 labelled cases to `evals/eval_set.jsonl`; `run_evals.py` must not regress.
5. **Backtest-able** — if point-in-time reconstructable, add a hook in `reconstruct.py`.

### New pipeline step — enrichment

Add an `enrich(candidates)` pass in `orchestrator.run()` **after dedup, before scoring**. Each
enrichment module reads a candidate (its repo / site / handles in `Candidate.url` and `Candidate.raw`)
and writes signal fields onto `candidate.raw`. Pattern:

```python
# sources/<name>.py
def enrich(candidate) -> None:
    """Populate candidate.raw with this signal's fields. No-op (and no error) if data/keys absent."""
    ...
# optionally also a Source subclass with fetch() if it DISCOVERS new candidates.
```

In `scoring.py`, add one helper `signal_bonuses(candidate) -> dict` that computes every new bonus from
`candidate.raw`; `composite()` sums them; `subscores` includes them. Keep each bonus in its own small
function so it's testable.

---

## Ticket 1 — `code_health`  ★ DO FIRST (free, highest published lift)

**Goal:** reward commit-velocity *acceleration* + contributor diversity. Research: 14-day commit
acceleration **and** contributor Gini < 0.30 ⇒ ~3.4× more likely to raise a Series A within 60 days.

- **File:** extend `sources/github_velocity.py` with `enrich_code_health(candidate)` (reuse `_client`).
- **Capture (GitHub REST, token optional):**
  - `GET /repos/{owner}/{repo}/stats/commit_activity` → 52 weekly commit counts.
    `accel = sum(weeks[-2:]) / max(sum(weeks[-4:-2]), 1)` (last 14d vs prior 14d). *(Endpoint returns 202
    on first call while GitHub computes — retry a few times.)*
  - `GET /repos/{owner}/{repo}/contributors?per_page=100` → `contributions` per contributor → compute
    **Gini** over those counts.
- **Raw fields:** `raw["commit_accel"]`, `raw["contributor_gini"]`, `raw["contributors"]` (count).
- **Sub-score** (`code_health_bonus`, 0..15) — *multiplicative* so you need BOTH conditions:
  ```python
  accel = raw.get("commit_accel"); gini = raw.get("contributor_gini"); n = raw.get("contributors", 0)
  if accel is None or n < 2: return 0.0
  accel_pts = min(1.0, max(0.0, accel - 1.0))                 # 0 at flat, 1.0 at >=2x
  gini_pts  = 1.0 if (gini is not None and gini < 0.30) else (0.5 if gini and gini < 0.45 else 0.2)
  return round(15 * accel_pts * gini_pts, 1)
  ```
- **Acceptance:** a repo with accel ≥ 1.5 and Gini < 0.30 → `code_health ≈ 12–15`; a single-hero-dev repo
  (Gini > 0.7) → near 0 even with high accel. Dashboard shows `code_health +X`. Evals don't regress.
- **Guardrail:** private repos invisible → `None`; needs ≥2 contributors.

## Ticket 2 — `team` (highest predictive value; fixes the relationship-sourced blind spot)

**Goal:** reward prior exits / repeat-founder (× exit size, × same-domain) / technical CEO /
frontier-lab alum / ≥2 founders.

- **File:** new `sources/team.py` — `enrich(candidate)` via Harmonic (`HARMONIC_API_KEY`); optional
  `fetch()` from a Harmonic people saved-search to *discover* stealth founders.
- **Capture:** Harmonic `enrich_company` / `enrich_person` → founders, prior companies + outcomes,
  prior employers.
- **Raw fields:** `prior_exit` (bool), `exit_size_usd`, `repeat_founder_count`, `same_domain` (bool),
  `technical_ceo` (bool), `frontier_lab_alum` (bool), `team_size`.
- **Sub-score** (`team_bonus`, 0..20): `prior_exit` +8 (×`min(1, log10(exit_size_usd)/8)`),
  `repeat_founder_count≥2 and same_domain` +5, `technical_ceo` +4, `frontier_lab_alum` +3,
  `team_size≥2` +2 → sum, cap 20. No data → 0.
- **Acceptance:** repeat founder with a prior ≥$100M exit + technical CEO → `team ≈ 17–20`; unknown team
  → 0. No Harmonic key → 0 (no crash).
- **Guardrail:** trust **events** (exits/M&A) over self-asserted LinkedIn titles.

## Ticket 3 — `social` (Farcaster; crypto-native, hard to game, backtest-able)

**Goal:** smart-follower convergence + OpenRank reputation, gated by Neynar quality score.

- **File:** new `sources/social_farcaster.py` — `enrich(candidate)` + optional `fetch()` (discover via
  trending feed). Needs `NEYNAR_API_KEY` + `FARCASTER_FUND_FID` (your fund's seed FID).
- **Capture:** Neynar `fetchRelevantFollowers` (viewer = `FARCASTER_FUND_FID`) → count credible follows;
  user object → `neynar_user_score`, `power_badge`; OpenRank `graph.cast.k3l.io` → percentile rank.
- **Raw fields:** `smart_followers` (count of high-rep follows in window), `neynar_score`,
  `openrank_pct`, `power_badge`, `account_age_days`.
- **Sub-score** (`social_bonus`, 0..12): start 0; `smart_followers≥2` → `+min(8, 4*smart_followers/... )`;
  `openrank_pct` top-decile → `+up to 4`; if `neynar_score < 0.55` multiply result ×0.4;
  if `account_age_days < 30` ×0.5. No data → 0.
- **Acceptance:** account with 3 credible follows + score 0.7 → `social ≈ 9–11`; brand-new low-score
  account → 0–2.
- **Guardrail:** reputation-weighted (Neynar + OpenRank are sybil-resistant by design); age-gate.
- **Backtest hook:** reconstruct point-in-time via Dune Farcaster tables in `reconstruct.py`.

## Ticket 4 — `onchain` (free via DefiLlama + Blockscout)

**Goal:** stablecoin net inflows + "real" TVL (revenue − incentives) + holder health.

- **File:** extend `sources/blockscout.py` or new `sources/onchain.py` — `enrich(candidate)`.
- **Capture:** DefiLlama `/protocol/{slug}` (TVL, fees, revenue) + stablecoin flows (no key);
  Blockscout for holder distribution.
- **Raw fields:** `stablecoin_inflow_30d`, `real_tvl` (revenue − incentives), `tvl_retention`
  (TVL now ÷ TVL at incentive peak), `holder_gini`.
- **Sub-score** (`onchain_bonus`, 0..12): `stablecoin_inflow_30d > 0` → `+min(6, 2*log10(1+inflow))`;
  `real_tvl > 0 and tvl_retention > 0.5` → +4; `holder_gini < 0.9` → +2. No data → 0.
- **Acceptance:** protocol with positive external stablecoin inflow + positive earnings → `onchain ≈ 8–10`;
  incentive-only ("mercenary") TVL with retention < 0.5 → low.
- **Guardrail:** use **real** TVL not raw; discount wash trading / mercenary capital (retention test).

## Ticket 5 — `pre_public` (catches what code/social miss; mostly buy)

**Goal:** grants + hackathon wins (+ persistence) + research (+ affiliation exit) + recent formation.

- **File:** new `sources/pre_public.py` — `fetch()` (discover from grant/hackathon lists) + `enrich()`;
  or integrate Evertrace (`EVERTRACE_API_KEY`) which bundles most of these.
- **Capture:** EF ESP / Optimism RetroPGF recipient lists, ETHGlobal showcase, arXiv / IACR ePrint APIs,
  whois / OpenCorporates.
- **Raw fields:** `grant_program`, `retro_grant` (bool), `hackathon_win`, `post_event_active`,
  `research_exit`, `incorp_days`.
- **Sub-score** (`pre_public_bonus`, 0..15): `retro_grant` +6 / proposal grant +3;
  `hackathon_win and post_event_active` +4; `research_exit` +3; recent incorporation/domain +2. No data → 0.
- **Acceptance:** an Optimism RetroPGF recipient still committing → `pre_public ≈ 10`; a dead weekend
  hackathon project → 0.
- **Guardrail:** retroactive grants ≫ proposal grants; count a hackathon only if the team **kept building**.

---

## Shared changes checklist (per ticket)

- [ ] `sources/<name>.py` — `enrich(candidate)` (+ `fetch()` if it discovers); lazy imports; no-op without keys.
- [ ] `orchestrator.py` — call the enrich pass after dedup; register any new discovery source in `build_sources()`.
- [ ] `scoring.py` — add `<name>_bonus()` + include in `signal_bonuses()` + `composite()` + `subscores`.
- [ ] `digest.py` / `dashboard.py` — `_breakdown()` already reads `subscores`; extend it to list any present new keys.
- [ ] `.env.example` — add keys (`NEYNAR_API_KEY`, `FARCASTER_FUND_FID`, `EVERTRACE_API_KEY`, optional `SORSA_API_KEY`).
- [ ] `evals/eval_set.jsonl` — ≥2 cases exercising the new signal; `run_evals.py` green.
- [ ] `config/thesis.yaml` — optional `signal_weights:` block to tune each bonus cap without code changes.

## Build order

1. **`code_health`** — free, highest lift, builds on the GitHub source you have. *(Start here.)*
2. **`onchain`** — free (DefiLlama/Blockscout).
3. **`social`** — needs `NEYNAR_API_KEY`.
4. **`team`** — needs `HARMONIC_API_KEY`.
5. **`pre_public`** — buy/integrate Evertrace, or scrape grant/hackathon lists.

Keep the composite honest: reputation-weighted, ratio-based, human-reviewed. The scorer triages; a
partner decides.
