# CLAUDE.md — operator guide for Signal

Signal is a thesis-driven dealflow sourcing + diligence agent for a crypto/AI fund. It gathers
candidate companies, scores them against `config/thesis.yaml`, and writes a ranked digest. It also
ships a Phase 0 backtest that checks whether the sourcing signal is actually reliable.

This file tells Claude Code (and you, in the terminal) how to run everything. Run all commands from
the repo root.

> **Context & "why":** read `docs/CONTEXT.md` first — it captures the research and every design
> decision behind this project (the fund, the role, the worldview, the product bets, the connectors,
> the quantum angle, open threads). Long-form briefs are in `docs/`, including
> `docs/Sourcing_Signals_Research.md` — the research-backed roadmap of signals to add to the scorer.

---

## Setup

```bash
# Python 3.10+
# Minimum (offline demo / evals / backtest need only pyyaml):
pip install pyyaml

# Full (live sources + models + MCP server):
pip install -e ".[live,llm,mcp]"

# Keys are optional — everything below has an offline path.
cp .env.example .env        # then fill in any keys you have
```

After `pip install -e .` the console script `signal` is available; otherwise prefix commands with
`PYTHONPATH=src`. Examples below use the `PYTHONPATH=src` form so they work with zero install.

---

## Run it

```bash
# 1) Sourcing digest — OFFLINE demo (bundled fixtures, no keys). Writes out/digest.md + out/digest.json
PYTHONPATH=src python -m signalfund --demo

# 2) Scorer evals — precision/recall on a labeled set
PYTHONPATH=src python evals/run_evals.py

# 3) Phase 0 backtest — OFFLINE demo. Writes out/backtest_report.md (+ .json), prints GREEN/YELLOW/RED
PYTHONPATH=src python -m signalfund.backtest --demo

# 3b) Memo agent — company → source-cited investment memo (offline demo). Writes out/memos/<co>.md
PYTHONPATH=src python -m signalfund.memo --demo

# Every sourcing run also writes out/dashboard.html — open it in a browser for the visual digest.

# 4) Sourcing digest — LIVE (needs keys in .env; see "Keys"). Pulls real GitHub/Harmonic data.
PYTHONPATH=src python -m signalfund --limit 30

# 5) Custom MCP server (star-velocity) — for use inside Claude Code via .mcp.json, or standalone:
python mcp_servers/github_velocity/server.py
```

Open `out/digest.md` (the ranked dealflow) or `out/backtest_report.md` (the go/no-go) to see results.

---

## Keys (all optional — each unlocks a capability)

Set in `.env`. With none set, the system runs fully offline (heuristic scorer, fixture data).

| Var | Unlocks |
|-----|---------|
| `ANTHROPIC_API_KEY` (+ `FRONTIER_MODEL`) | LLM scorer for synthesis-grade rationales (else heuristic) |
| `OLLAMA_BASE_URL` (+ `LOCAL_MODEL`) | local model for cheap, high-volume triage |
| `GITHUB_TOKEN` | higher GitHub rate limits for live sourcing |
| `HARMONIC_API_KEY` (+ `HARMONIC_SAVED_SEARCH_ID`) | Harmonic VC sourcing source |
| `BLOCKSCOUT_BASE_URL` | on-chain enrichment chain (public, default Ethereum) |
| `SIGNAL_SURFACE_THRESHOLD`, `SIGNAL_LEAD_REQ_DAYS` | backtest decision-rule thresholds |

---

## Two live workflows Claude Code can drive

### A) Daily sourcing run
1. Ensure `.env` has `GITHUB_TOKEN` (and optionally `HARMONIC_*`, `ANTHROPIC_API_KEY`).
2. `PYTHONPATH=src python -m signalfund --limit 30`
3. Review `out/digest.md`; optionally push the top items to Airtable/Notion/Slack.

### B) Phase 0 backtest (the reliability test)
Full playbook in **`BACKTEST.md`**. Short version:
1. Build `ground_truth.json` from real deals (copy `data/backtest/ground_truth.sample.json`).
2. Reconstruct point-in-time signal: `PYTHONPATH=src python -m signalfund.reconstruct ground_truth.json ground_truth.filled.json` (needs BigQuery creds for GH Archive; Claude Code can also fill stars-as-of-date via the `bq` CLI / GH Archive query, and site existence via the Wayback API).
3. `PYTHONPATH=src python -m signalfund.backtest --ground-truth ground_truth.filled.json`
4. Read `out/backtest_report.md` → 🟢/🟡/🔴 decision.

---

## Layout

```
src/signalfund/
  orchestrator.py   pipeline entrypoint (gather → dedup → score → digest); `python -m signalfund`
  scoring.py        HeuristicScorer + LLMScorer + composite (fit+traction+credibility + 5 signal sub-scores)
  llm.py            model routing: triage() local-first, synthesize() frontier
  models.py         Candidate, ScoredCandidate
  store.py          sqlite snapshots (star velocity) + dedup memory; falls back to in-memory
  dedup.py          exact + fuzzy near-duplicate dedup
  digest.py         renders out/digest.md + .json
  backtest.py       Phase 0 backtest engine + report  (`python -m signalfund.backtest`)
  reconstruct.py    point-in-time signal reconstruction (GH Archive / Wayback / Harmonic)
  sources/          github_velocity, harmonic, blockscout, onchain, team, social_farcaster, pre_public (Source + enrich())
mcp_servers/github_velocity/server.py   custom MCP (trending_by_velocity / repo_velocity / snapshot)
config/thesis.yaml    the fund thesis the scorer matches against (edit this to retune)
data/fixtures/        demo candidates;  data/backtest/  sample ground truth
evals/                run_evals.py + eval_set.jsonl
out/                  generated digests & backtest reports
.mcp.json             registers the custom MCP + Blockscout/Harmonic in Claude Code
BACKTEST.md           full backtest playbook
```

---

## Signals & tiers (free vs premium)

All five signals are **built** (see `docs/SIGNALS_BUILD_SPEC.md`). The score is a **weighted blend** (not a
sum, which used to saturate strong deals at 100): thesis `fit` stays dominant (~60%) and the quality signals
(`traction + code_health + team + social + onchain + pre_public`) are collapsed into one 0–100
`signal_strength` blended in (~40%), with `credibility` applied after. Each signal is an `enrich()` pass that
writes onto `Candidate.raw` and `scoring.py` turns it into a reputation-weighted sub-score. **Graceful
absence:** any signal whose key/API is missing contributes 0 (never penalises a good-fit company), so the
system runs at whatever tier your keys allow — switching tiers needs no code change. Tune the fit/signal
split via `config/thesis.yaml` → `composite_weights`, and each sub-score cap via `signal_weights`.

**Guiding principle:** raw counts are worthless — reputation-weight every interaction, prefer hard-to-fake
actions, gate on account age, score ratios not totals. Full report: `docs/Sourcing_Signals_Research.md`.

### Tier 1 — FREE  (default; no key, or a free key)

| Signals | Source | Key |
|---|---|---|
| `fit` · `traction` · `credibility` · `code_health` | GitHub REST | free `GITHUB_TOKEN` (rate limits only) |
| `team` (GitHub-derived: technical-CEO proxy, team size, frontier-lab alum) | GitHub REST | free `GITHUB_TOKEN` |
| `onchain` (stablecoin inflows, real TVL, holders) | DefiLlama + Blockscout | none |
| `social` (reputation) | OpenRank `graph.cast.k3l.io` | none |
| `network_radar` (sourcing: accounts a curated set of smart accounts newly converge on) | Neynar + OpenRank | free `NEYNAR_API_KEY` + `config/smart_accounts.yaml` |
| `pre_public` (research, grants) | arXiv / IACR / grant + ETHGlobal pages | none |
| LLM scorer (optional) | local Ollama | none |

### Tier 2 — PREMIUM  (paid / gated keys)

| Signal | Source | Key |
|---|---|---|
| `team` (prior exits / exit size / repeat-founder + talent-flow — augments the free GitHub team signal) | Harmonic | `HARMONIC_API_KEY` (paid) |
| `social` (smart-follower convergence + quality score) | Neynar | `NEYNAR_API_KEY` (freemium to paid) |
| `pre_public` (bundled detection) | Evertrace | `EVERTRACE_API_KEY` (paid) |
| funding/stage gate (down-rank already-funded Series B/C+) + tier-1 lead-investor corroboration + memo research context | Messari | `MESSARI_API_KEY` (paid) |
| `onchain` UPGRADE (Smart Money net inflow + holder share) + on-chain smart-money convergence (twin of network_radar) | Nansen | `NANSEN_API_KEY` (paid) or x402 `SIGNAL_NANSEN_X402=1` (~$0.01/query USDC on Base, no key) |
| LLM scorer (frontier rationales / memos) | Anthropic | `ANTHROPIC_API_KEY` (paid) |
| backtest Farcaster reconstruction | Dune | `DUNE_API_KEY` |

Run free to start; add premium keys to light up `team`, deep `social`, and `pre_public`. `.env.example`
is grouped the same way. Per-signal formulas / acceptance criteria are in `docs/SIGNALS_BUILD_SPEC.md`;
tune any sub-score cap from `config/thesis.yaml` (`signal_weights:`) without touching code.

## Conventions & gotchas
- **Package is `signalfund`, not `signal`** (avoids shadowing the stdlib `signal` module).
- **Offline-first:** demo / evals / backtest need only `pyyaml`. Heavy deps (`httpx`, `anthropic`,
  `openai`, `mcp`, `google-cloud-bigquery`) are imported lazily, so those paths never block a demo.
- **Scorer auto-selects:** `LLMScorer` if any model is configured (frontier `ANTHROPIC_API_KEY`, else local `OLLAMA_BASE_URL`), else the deterministic
  `HeuristicScorer` (also what powers demos and evals).
- **sqlite** falls back to in-memory if the filesystem can't lock it — velocity just won't persist.
- **Tune the thesis** in `config/thesis.yaml`, then re-run `evals/run_evals.py` to confirm no regression.
- **Evals are CI-gated** (`.github/workflows/evals.yml`): `run_evals.py` exits non-zero if precision/recall/accuracy
  fall below floors (default 1.00 / 0.88 / 0.90; override via `SIGNAL_EVAL_MIN_PRECISION|RECALL|ACCURACY`).
  CI also smoke-runs the demo + backtest. All offline — needs only `pyyaml`.
- Generated files land in `out/` (override with `SIGNAL_OUT_DIR`). `*.db`, `__pycache__/`, `.env` are gitignored.

## "It's working" looks like
- `python -m signalfund --demo` prints `top: veritas-zk/veritas (69.8/100)` and writes `out/digest.md`.
  (Scores are a **weighted blend** — fit·0.6 + signal_strength·0.4 + credibility — so the strong deals
  separate instead of all pinning at 100; tune the split in `config/thesis.yaml` → `composite_weights`.)
- `evals/run_evals.py` prints `precision=1.00 recall=0.92 … PASS` (surface threshold 20 on the blended scale).
- `backtest --demo` prints `decision: YELLOW …` and writes `out/backtest_report.md`.
