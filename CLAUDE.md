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

# 5) WEB UI — local control panel (stdlib http.server, no extra deps). Default http://127.0.0.1:8000
PYTHONPATH=src python -m signalfund.webapp                # add --port 8765 / --no-open
#   In the browser: the Run button (Live/Demo toggle), a Scorer-model picker (heuristic / any
#   configured LLM provider), per-signal on/off toggles (incl. nansen + messari), and
#   memo-from-digest (click a ranked company → generate its source-cited memo). Binds localhost only.

# 6) CLOUD run — GitHub Actions ▸ "Sourcing run" ▸ Run workflow (.github/workflows/sourcing.yml).
#   Uses the runner's built-in GITHUB_TOKEN + heuristic scorer by default → ZERO secrets needed.
#   Renders the digest in the run Summary and uploads out/{digest.md,digest.json,dashboard.html}
#   as the `signal-digest` artifact. Inputs: limit (default 40), scorer (heuristic/groq/auto).

# 7) Custom MCP server (star-velocity) — for use inside Claude Code via .mcp.json, or standalone:
python mcp_servers/github_velocity/server.py

# 8) HOSTED DEMOS — static: GitHub Pages (docs/, refresh-demo.yml) at https://yalegend.github.io/signal/
#   live: Hugging Face Docker Space built from ./Dockerfile (offline demo, heuristic, port 7860),
#   auto-deployed by .github/workflows/hf-space.yml once secret HF_TOKEN + variable HF_SPACE are set
#   (skips green until then). Local container: docker build -t signal-demo . && docker run -p 7860:7860 signal-demo
```

Open `out/digest.md` (the ranked dealflow) or `out/backtest_report.md` (the go/no-go) to see results.

### Enable premium MCP servers (opt-in)

`.mcp.json` ships only the **keyless** servers (`github-velocity`, `blockscout`) and Harmonic
(lazy OAuth via its `authenticate` tool) so a fresh clone has no failing MCP server. The **Nansen**
MCP needs a paid key (an empty bearer just 401s), so it's opt-in — set `NANSEN_API_KEY` in `.env`,
then add this entry under `mcpServers` in `.mcp.json`:

```json
"nansen": {
  "type": "http",
  "url": "https://mcp.nansen.ai/mcp",
  "headers": { "Authorization": "Bearer ${NANSEN_API_KEY}" }
}
```

(Nansen enrichment still works key-free over x402 — `SIGNAL_NANSEN_X402=1` — without this MCP entry.)

---

## Keys (all optional — each unlocks a capability)

Set in `.env`. With none set, the system runs fully offline (heuristic scorer, fixture data).

| Var | Unlocks |
|-----|---------|
| `ANTHROPIC_API_KEY` (+ `FRONTIER_MODEL`) | LLM scorer for synthesis-grade rationales (else heuristic) |
| `OLLAMA_BASE_URL` (+ `LOCAL_MODEL`) | local model for cheap, high-volume triage |
| `GITHUB_TOKEN` | higher GitHub rate limits for live sourcing |
| `HARMONIC_API_KEY` (+ `HARMONIC_SAVED_SEARCH_ID`; optional `HARMONIC_PEOPLE_SEARCH_ID` for the people/talent-flow search) | Harmonic VC sourcing source |
| `BLOCKSCOUT_BASE_URL` | on-chain enrichment chain (public, default Ethereum) |
| `MESSARI_API_KEY` | funding/stage gate (down-rank already-funded rounds) + tier-1 lead corroboration + memo research |
| `NANSEN_API_KEY` *or* `SIGNAL_NANSEN_X402=1` | Nansen onchain upgrade (Smart-Money inflow + holder share) + on-chain convergence; x402 = keyless pay-as-you-go (~$0.01/query USDC on Base) |
| `SIGNAL_NANSEN_MIN_CONVERGENCE` (default 2), `SIGNAL_NANSEN_MIN_QUALITY` (default 0.0) | smart-money convergence quorum + wallet reputation floor |
| `SIGNAL_LLM_PROVIDER` | pin the scorer LLM (`anthropic`/`groq`/`gemini`/`openrouter`/`cerebras`/`ollama`/`heuristic`); unset = auto-order |
| `SIGNAL_LLM_MAX_RPM` (25), `SIGNAL_LLM_BURST` (3), `SIGNAL_LLM_MAX_RETRIES` (4) | free-tier throttle + 429 retry-with-backoff so batch runs don't rate-limit (`MAX_RPM<=0` disables) |
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
  webapp.py         local web UI (stdlib http.server); `python -m signalfund.webapp`
  dashboard.py      renders out/dashboard.html (visual digest written on every run)
  env.py            .env loader (strips inline comments / quotes; safe to import everywhere)
  sources/          github_velocity, harmonic, blockscout, onchain, team, social_farcaster,
                    pre_public, network_radar, watchlist, messari, nansen (Source + enrich())
mcp_servers/github_velocity/server.py   custom MCP (trending_by_velocity / repo_velocity / snapshot)
config/thesis.yaml    the fund thesis the scorer matches against (edit this to retune)
config/watchlist.yaml hand-found leads (human-in-the-loop intake); config/smart_accounts.yaml,
                      config/smart_money_wallets.yaml  curated accounts/wallets for convergence
data/fixtures/        demo candidates;  data/backtest/  sample ground truth
evals/                run_evals.py + eval_set.jsonl + *_check.py acceptance checks
out/                  generated digests, dashboard.html & backtest reports
.mcp.json             registers the keyless MCPs (custom + Blockscout) + Harmonic; Nansen is opt-in (see Run it)
.github/workflows/    evals.yml (CI gate) + sourcing.yml (cloud "Run" workflow)
BACKTEST.md           full backtest playbook
```

---

## Signals & tiers (free vs premium)

All signal sub-scores are **built** (the five core ones in `docs/SIGNALS_BUILD_SPEC.md`, plus the
`network_radar`/`watchlist` sourcing sources and the Messari/Nansen Tier-2 augments). The score is a **weighted blend** (not a
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
| `watchlist` (human-in-the-loop sourcing: drop a hand-found lead into `config/watchlist.yaml` → the same pipeline diligences it) | `config/watchlist.yaml` | none |
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
- **Credibility = HARD vs SOFT flags** (`scoring.classify_flags`): only HARD anti-signals (scam / fraud /
  rug / ponzi / thesis `anti_signals` match) levy the screen-out penalty. Informational SOFT flags
  (early-stage, hackathon, no recent commits, unconfirmed repo, small team) become shown `risks` and
  cost 0 — so a good-fit early company isn't double-penalised for being early.
- **Free-tier LLM stability** (`llm.py`): a token-bucket throttle (`SIGNAL_LLM_MAX_RPM`/`_BURST`) plus
  429 retry-with-backoff (`SIGNAL_LLM_MAX_RETRIES`) keep a batch run (e.g. `--limit 40`) from randomly
  rate-limiting; on exhaustion the call falls back to heuristic rather than crashing.
- **Web-UI signal toggles → `enabled_signals`:** the UI on/off switches pass an `enabled_signals` list to
  `orchestrator.run`; only listed signals enrich (absent/None = all on). A disabled — or keyless —
  signal contributes 0, same graceful-absence rule as the CLI.
- **sqlite** falls back to in-memory if the filesystem can't lock it — velocity just won't persist.
- **Tune the thesis** in `config/thesis.yaml`, then re-run `evals/run_evals.py` to confirm no regression.
- **Evals are CI-gated** (`.github/workflows/evals.yml`): `run_evals.py` exits non-zero if precision/recall/accuracy
  fall below floors (default 1.00 / 0.88 / 0.90; override via `SIGNAL_EVAL_MIN_PRECISION|RECALL|ACCURACY`).
  CI also smoke-runs the demo + backtest and runs the per-feature acceptance checks:
  `watchlist_check`, `network_radar_check`, `credibility_check`, `ratelimit_check`, `messari_check`,
  `nansen_check` (all in `evals/`). All offline — needs only `pyyaml`.
- Generated files land in `out/` (override with `SIGNAL_OUT_DIR`). `*.db`, `__pycache__/`, `.env` are gitignored.

## "It's working" looks like
- `python -m signalfund --demo` prints `top: veritas-zk/veritas (69.8/100)` and writes `out/digest.md`.
  (Scores are a **weighted blend** — fit·0.6 + signal_strength·0.4 + credibility — so the strong deals
  separate instead of all pinning at 100; tune the split in `config/thesis.yaml` → `composite_weights`.)
- `evals/run_evals.py` prints `precision=1.00 recall=0.92 … PASS` (surface threshold 20 on the blended scale).
- `backtest --demo` prints `decision: YELLOW …` and writes `out/backtest_report.md`.


---

# Signal — project guide for Claude Code

Read this at the start of every session. It tells you what the product is, the rules
that must never break, and how we track work.

## What Signal is

Signal is a **thesis-driven dealflow sourcing & diligence agent** for early-stage crypto / AI
companies. It searches public data, scores every company it finds against a written investment
thesis, ranks them into a digest, and writes an AI diligence memo with a full audit trail. It also
watches a trusted follow-graph (Farcaster) and can be backtested against past deals.

## Non-negotiable guardrails (Definition of Done depends on these)

- **Never fabricate.** If a fact can't be verified from a source, the agent says "not found" — it
  does not invent a repo, metric, or company. Any change touching the diligence agent must keep this,
  and needs a test proving the refusal behaviour.
- **Graceful degradation.** A missing API key must never raise. The source is marked "skipped", the
  run continues. Every new data source needs a "no key → skipped, no error" test.
- **Thesis is configuration, not code.** Themes, weights, diligence questions, and stage preferences
  live in the thesis config / `config/`. Don't hard-code them.
- **Keep the demo/heuristic path and the live path in parity** so the public demo never breaks.

## Repo orientation (verify against the actual tree; update this file if it drifts)

- Python package: `signalfund` (kept under `src/`).
- Run the web app locally: `PYTHONPATH=src python -m signalfund.webapp` → http://127.0.0.1:8000
- Trusted accounts for the network radar: `config/smart_accounts.yaml`
- Cloud "run button": GitHub Actions → `.github/workflows/sourcing.yml`, produces the `signal-digest` artifact.
- Secrets live in `.env` (gitignored): `GITHUB_TOKEN`, `GROQ` (LLM). Optional, turn sources live when present:
  `NEYNAR_API_KEY` (Farcaster), `NANSEN_API_KEY`, `HARMONIC_API_KEY`, `MESSARI_API_KEY`.
- Run the tests the way this repo already does (pytest). If you add a source, add its graceful-degradation test.

## How we track work — backlog.json is the source of truth

Project status lives in **`backlog.json`** and is edited through the CLI **`signal-board.mjs`**
(zero dependencies, Node ≥ 18). Do not hand-edit `backlog.json` unless the CLI can't express the change.
Commit `backlog.json` with your code so status is versioned.

Board columns (Scrumban): `backlog → ready → inprogress → review → done`.
WIP limit: **2** in `inprogress`. Respect it — finish before starting.

CLI you will use:

```
node signal-board.mjs stats                 # summary + column counts + blocked items
node signal-board.mjs list --status ready   # filter: --status --sprint --epic --blocked
node signal-board.mjs next                   # the recommended next item
node signal-board.mjs show S-02              # criteria + numbered action items
node signal-board.mjs move S-02 inprogress   # change status
node signal-board.mjs check S-02 3 done      # tick action item 3 (or: todo, or omit to toggle)
node signal-board.mjs note S-02 "…"          # set a note (blocker, decision, link)
node signal-board.mjs render                 # regenerate board.html from the file
```

## The working loop (follow this unless I say otherwise)

1. `node signal-board.mjs next` (or I'll name an item). If it's **blocked**, stop and tell me.
2. `node signal-board.mjs move <id> inprogress`.
3. Implement the action items **in order**. After each one: `node signal-board.mjs check <id> <n> done`.
4. Satisfy the item's acceptance criteria and the guardrails above. Add/adjust tests (including the
   missing-key and no-fabrication cases) and run the suite.
5. When every action item is checked and tests pass: `node signal-board.mjs move <id> review`,
   then `node signal-board.mjs render`.
6. Summarize what changed and what I should verify. **Leave it in `review` — I move it to `done`.**
7. If blocked at any point: `node signal-board.mjs note <id> "why"` and tell me.

## Style

Small, focused commits. Prefer a thin live-capable slice over a broad demo-only feature. Match the
existing code's patterns; don't refactor unrelated code while implementing an item.
