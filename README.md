# Signal — a thesis-driven dealflow sourcing + diligence agent

**Live demo:** **https://yalegend.github.io/signal/** (static dashboard — always on)

Signal surfaces early-stage crypto/AI companies **before they're obvious**, scores each against a
fund's *encoded thesis*, and ships a ranked, source-cited digest — plus a **Phase 0 backtest** that
checks whether the sourcing signal is actually reliable.

Built as a reference implementation of the AI associate stack a crypto pre-seed fund should have. It
embodies the fund's own worldview: every claim is **verifiable** (source-linked), the pipeline runs
within **defined rules** (a thesis/policy layer), and it **collapses a manual workflow** — sourcing,
scoring, diligence, and a go/no-go reliability test.

> Runs fully **offline** in `--demo` (bundled fixtures, no keys), so you can see output before wiring a
> single API key — and it **runs itself in the cloud** via a GitHub Actions "Run" button.

---

## The honest part first — what the backtest found

I didn't just build the sourcing tool; I built **the test of whether it works**. The Phase 0 backtest
reconstructs *point-in-time* signal (GitHub via GH Archive, websites via the Wayback Machine — no
look-ahead) and asks: *would Signal have surfaced real deals early enough to matter?*

On the labeled set the verdict is **🟡 YELLOW — sourcing works in part**:

| What it caught | Recall | Read |
|---|---|---|
| **Public-channel** deals (OSS / repos / sites) | **67%** | the slice public signal genuinely covers |
| **Warm-intro / inbound** deals | **0%** | relationship-sourced deals have ~no public footprint |
| Median **lead time** (for the ones caught) | **45 days early** | early enough to act |

That's not a failure — it's the tool being **honest about its own limits**, which is exactly the
discipline a fund needs. The finding drives the design: lean sourcing where it demonstrably works
(public / OSS / hackathon / research), and put the higher-leverage bet on the **synthesis side** (the
Memo agent). *Reliability here is a process — the eval loop — not a property of any single heuristic.*
(Directional at small N; see `BACKTEST.md` and `out/backtest_report.md`.)

---

## Run it

Three ways, cheapest first — all work with **zero API keys**:

```bash
# 1) Offline demo (needs only pyyaml). Writes out/digest.md + out/dashboard.html
pip install pyyaml
PYTHONPATH=src python -m signalfund --demo

# 2) Interactive web UI — a Run button, Live/Demo toggle, scorer picker, signal toggles
PYTHONPATH=src python -m signalfund.webapp          # opens http://127.0.0.1:8000

# 3) In the cloud — GitHub Actions ▸ "Sourcing run" ▸ Run workflow
#    Uses the runner's built-in GITHUB_TOKEN + heuristic scorer (no secrets), digest as an artifact.

# 4) The diligence AGENT — a tool-using loop writes a source-cited memo (needs an LLM key; see below)
PYTHONPATH=src python -m signalfund.memo --agent --company "elizaOS/eliza" \
    --url https://github.com/elizaOS/eliza --summary "agentic framework for crypto agents"
```

Go live (real GitHub data) by adding a free `GITHUB_TOKEN` to `.env` and running
`python -m signalfund --limit 40`. Open `out/digest.md` — that's the artifact a partner reads.

---

## It's an agent — a bounded, tool-using diligence loop

Beyond the scorer, Signal ships a real **ReAct-style agent** (`src/signalfund/agent.py`): given a
company, an LLM **decides which source-tools to call**, observes the results, iterates, then the
gathered evidence feeds the memo. Every memo carries a **Diligence trail** — the tools it chose, in
order, with reasons and the sources it pulled — so the reasoning is auditable.

```
## Diligence trail
1. github_velocity(owner=elizaOS, repo=eliza) — gauge dev activity & contributor spread
   ↳ sources: https://github.com/elizaOS/eliza
2. team_lookup(owner=elizaOS, repo=eliza)     — technical-founder proxy, team size, lab pedigree
3. web_search(query=elizaOS eliza company)    — (unavailable: no EXA key — agent moves on)
4. messari_funding(name=elizaOS)              — (unavailable: no key — agent moves on)
5. onchain_metrics()                          — TVL / retention / holder concentration
   ↳ sources: https://defillama.com/protocol/elizaos-eliza
```

Design choices that make it a *real* agent, not a prompt:
- **Portable** — a plain JSON-action protocol (not provider-native tool-calling), so Groq / Gemini /
  OpenRouter / local Ollama all work. Cheap per-step decisions use `triage()`; the memo uses `synthesize()`.
- **Tool registry wraps the existing sources** (GitHub, DefiLlama/Blockscout, Farcaster, Messari,
  Nansen, Exa) — no reimplementation. A tool with no key/data returns `{"unavailable": true}`, so the
  agent *learns* it can't use it and moves on — never crashes.
- **Bounded** — capped at `SIGNAL_AGENT_MAX_STEPS` (default 6), identical calls deduped, stops on
  `finish` or the cap. No runaway cost.
- **Honest citations** — only sources the agent actually retrieved may be cited; hallucinated links are
  dropped. With **no LLM key**, it gracefully falls back to the single-shot memo. Offline-tested in CI.

Run it with `--agent` (default when a provider is set) or force the classic single-shot with `--no-agent`.

---

## What it scores — six signals, free + premium tiers

The composite is a **weighted blend**: thesis-`fit` dominates (~60%), the quality signals corroborate
(~40%), and a credibility adjustment screens noise. **Graceful absence:** any signal whose key is
missing simply contributes 0 — it never penalises a good-fit company, so the system runs at whatever
tier your keys allow.

| Signal | Free source | Premium upgrade |
|---|---|---|
| `fit` · `traction` · `code_health` | GitHub REST | — |
| `team` | GitHub (technical-CEO proxy, frontier-lab alum) | Harmonic (exits, talent-flow) |
| `onchain` | DefiLlama + Blockscout (real TVL, holders) | **Nansen** (Smart-Money inflow + convergence) |
| `social` | OpenRank (Farcaster reputation) | Neynar (smart-follower convergence) |
| `pre_public` | arXiv / IACR / grants / ETHGlobal | Evertrace |
| stage-gate / funding | — | **Messari** (down-ranks already-funded rounds) |
| `network_radar` | Neynar + curated smart accounts | — (on-chain twin lives in Nansen) |

Two **convergence twins** sit at the core: `network_radar` (which credible *Farcaster* accounts newly
converge on) and Nansen Smart-Money (which credible *wallets* newly converge on) — the same "who
credible is early" thesis on the social and on-chain layers. Premium sources are **scaffolded and
fixture-tested**; their live field mappings need a paid key to validate (flagged in `CLAUDE.md`).

---

## Architecture

```
            ┌──────────────────────────────────────────────┐
            │   ORCHESTRATOR  (src/signalfund/orchestrator) │
            │   gather → dedup → enrich → score → digest    │
            └──────────────────────────────────────────────┘
               │              │                 │
      ┌────────┘       ┌──────┘          ┌──────┘
      ▼                ▼                 ▼
   SOURCES         SCORING            OUTPUTS
   ├ github_velocity (★ own MCP)   fit + 6 signals     out/digest.md / .json
   ├ harmonic · messari · nansen   → blended 0–100      out/dashboard.html
   ├ onchain · social · pre_public + risks (HARD/SOFT)  out/memos/<co>.md
   └ network_radar · watchlist     + verified citations
                          │
                   MODEL ROUTING (llm.py) — provider-agnostic
                   local/hosted triage ──→ frontier synthesis
                          │
   DILIGENCE AGENT (agent.py) — bounded ReAct loop: the model PICKS which of the
   source-tools above to call, observes, iterates → memo + Diligence trail
```

The **GitHub star-velocity** logic lives once in `sources/github_velocity.py` and is exposed two ways:
to the pipeline, and as an **MCP server** (`mcp_servers/github_velocity/`) you can register in Claude
Code. Velocity isn't a GitHub endpoint — you compute it from SQLite snapshots — which is exactly why
it's worth owning. `watchlist` lets you drop any hand-found lead into `config/watchlist.yaml` and have
the same signals diligence it.

---

## What breaks in production (and what this repo does about it)

- **LLMs hallucinate sources.** Cited URLs not in a candidate's provided sources are dropped.
  Verifiability over trust — the fund's own thesis, applied to the tool.
- **All-LLM is slow and expensive.** Fetch/parse/dedup is plain code; the model is reserved for
  judgment. Triage routes to a cheap/local model; only synthesis hits a frontier model — and the
  provider is swappable (Claude / Groq / Gemini / OpenRouter / Ollama).
- **Free-tier rate limits.** A client-side throttle + 429-retry keeps a batch run under the provider's
  limit instead of silently falling back mid-run (unit-tested).
- **"Informational" ≠ "disqualifying."** The credibility screen distinguishes *hard* anti-signals
  (ponzi/presale) from *soft* notes (early-stage, no recent commits) — soft notes become visible
  **risks**, not a score penalty, so a high-fit early team isn't zeroed out.
- **"Looks good in a demo, drifts in prod."** `evals/` keeps a labeled set and is **CI-gated**: a
  scorer change ships only if precision/recall hold. Eight offline checks gate every push.

---

## Limitations & path to reliable signal

Honestly: **Signal is a high-recall triage funnel with a human in the loop — not an autonomous "good
deal" oracle.** A fund wants a system that cheaply surfaces what it would otherwise miss and filters
obvious noise; a person still makes the call.

Still weak, and said plainly: star velocity is a lead, not a verdict (biased toward dev-tooling over
stealth infra); the heuristic misses *semantic* fit and is only the offline baseline; coverage is
bounded by API limits and the public-footprint blind spot the backtest exposed.

The path to reliable signal: **deepen the triangulation** (independent signals that must agree),
**calibrate don't guess** (grow the eval set, hold precision@k), **human-in-the-loop** (every digest
review writes labels back), **semantic dedup** (embeddings + pgvector).

---

## Secrets & `.env`

`.env` is **gitignored and never committed** — it holds your keys (`GITHUB_TOKEN`, `GROQ_API_KEY`, …).
`.env.example` *is* committed as the template. To run live on a fresh clone: `cp .env.example .env`
and add your keys. In the cloud, keys come from **GitHub repo Secrets**, not the file. Everything has
an offline path, so the repo runs with no secrets at all.

---

## Layout

```
src/signalfund/   orchestrator · scoring · llm · memo · agent · backtest · webapp · store · dedup · digest
  sources/        github_velocity · harmonic · messari · nansen · onchain · social · pre_public ·
                  team · network_radar · watchlist · blockscout
config/thesis.yaml   the fund thesis the scorer matches against (edit to retune)
evals/            run_evals.py + 7 acceptance checks (all CI-gated)
mcp_servers/      custom github-velocity MCP
.github/workflows/  evals.yml (CI) · sourcing.yml (cloud Run button)
BACKTEST.md · CLAUDE.md · docs/   playbook, operator guide, research
```

*Fixtures in `data/fixtures/` are illustrative, not real companies. The thesis in `config/thesis.yaml`
is derived from the fund's public writing and is meant to be edited.*
