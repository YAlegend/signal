# Signal — a thesis-driven dealflow sourcing agent

Signal surfaces early-stage crypto/AI companies **before they're obvious**, scores each against a fund's thesis, and ships a ranked daily digest with source-linked rationales.

Built as a reference implementation of the "AI associate stack a modern crypto fund should have." It demonstrates the patterns that matter in production: a **custom MCP server** you own, **tiered model routing** (cheap local triage → frontier synthesis), **citation verification** (no claim survives without a source), and an **eval harness** instead of vibes.

> Runs offline in `--demo` mode with bundled fixtures, so you can see output (and record a demo) before wiring a single API key.

---

## Architecture

```
                ┌───────────────────────────────────────────┐
                │   ORCHESTRATOR  (src/signalfund/...)        │
                │   gather → dedup → score → rank → digest    │
                └───────────────────────────────────────────┘
                   │              │                 │
        ┌──────────┘     ┌────────┘        ┌────────┘
        ▼                ▼                 ▼
   SOURCES          SCORING            DIGEST
   ├ github_velocity (★ own MCP)   thesis-fit 0–100      out/digest.md
   ├ harmonic  (VC sourcing)       + rationale           out/digest.json
   └ blockscout (on-chain)         + verified citations
                          │
                   MODEL ROUTING (llm.py)
                   local triage ──→ frontier synthesis
```

The **GitHub star-velocity** logic lives once in `src/signalfund/sources/github_velocity.py` and is exposed two ways: directly to the pipeline, and as an **MCP server** (`mcp_servers/github_velocity/`) you can register in Claude Code or any agent. Star *velocity* isn't a GitHub endpoint — you compute it from snapshots — which is exactly why it's worth building yourself.

---

## Quickstart

```bash
# 1. Offline demo — no keys needed. Produces out/digest.md from bundled fixtures.
pip install pyyaml
PYTHONPATH=src python -m signalfund --demo

# 2. See the scorer's eval scores (precision/recall on a labeled set)
PYTHONPATH=src python evals/run_evals.py

# 2b. Phase 0 backtest — would Signal have surfaced past deals, early? (offline demo)
PYTHONPATH=src python -m signalfund.backtest --demo   # → out/backtest_report.md  (see BACKTEST.md)

# 2c. Memo agent — company → source-cited investment memo (offline demo)
PYTHONPATH=src python -m signalfund.memo --demo       # → out/memos/<company>.md

# Every sourcing run also writes out/dashboard.html — open it in your browser for the visual digest.

# 3. Go live (install extras + set keys in .env)
pip install -e ".[live,llm,mcp]"
cp .env.example .env        # then fill in keys
python -m signalfund --limit 30
```

Open `out/digest.md` — that's the artifact a partner reads, and the thing to screen-share in a demo.

---

## Wiring real data (optional)

| Source | Env | Notes |
|---|---|---|
| GitHub velocity | `GITHUB_TOKEN` | Works without a token (lower rate limit). Token → higher limits. |
| Harmonic (VC sourcing/enrichment) | `HARMONIC_API_KEY` | Disabled gracefully if unset. |
| Blockscout (on-chain) | none | Public REST API; `BLOCKSCOUT_BASE_URL` to switch chains. |

## Model routing

Set in `.env`:

- **Local triage** (high-volume, cheap): any OpenAI-compatible endpoint via `OLLAMA_BASE_URL` + `LOCAL_MODEL` (e.g. Ollama running `qwen2.5:14b`).
- **Frontier synthesis** (the rationale partners read): `ANTHROPIC_API_KEY` + `FRONTIER_MODEL`.

If no model is configured, Signal automatically falls back to the deterministic `HeuristicScorer` — which is also what powers offline demo mode.

## Register the custom MCP in Claude Code

`.mcp.json` is included. It registers your `github-velocity` server plus the hosted Blockscout/Harmonic MCPs so agents (and you, in Claude Code) can call them directly:

```bash
# run the MCP server standalone (stdio)
pip install "mcp[cli]" httpx
python mcp_servers/github_velocity/server.py
```

---

## What breaks in production (and what this repo does about it)

- **LLMs hallucinate sources.** `scoring.verify_citations()` drops any cited URL not in the candidate's provided sources. Verifiability over trust — the fund's own thesis, applied to the tool.
- **All-LLM is slow and expensive.** Fetch/parse/dedup is plain code; the model is reserved for judgment. Triage routes to a cheap local model; only synthesis hits a frontier model.
- **"Looks good in a demo, drifts in prod."** `evals/` keeps a labeled set and measures scorer precision so changes are checked, not vibed.
- **Cold-start velocity.** First run has no history, so velocity falls back to `stars / age`; every run snapshots to SQLite so subsequent runs compute true deltas.

## Limitations & path to reliable signal

Read this honestly: **as it stands, Signal is a high-recall triage funnel with a human in the loop — not an autonomous "good deal" oracle.** That distinction is the whole game. A fund wants a system that cheaply surfaces things it would otherwise miss and filters obvious noise; a person still makes the call.

Already hardened (v0.1):

- **Triangulated composite, not one number.** Score = thesis-fit + log-dampened traction + a credibility adjustment, with sub-scores shown so a reviewer sees *why*. A star spike alone can't carry a candidate.
- **Word-boundary matching.** No more false positives like `defi` inside `defined`; keywords match tokens/phrases, not any substring.
- **Anti-gaming penalty.** Buzzword stuffing (many theme hits, thin description) and anti-signals are penalised — see the `buzzword stuffer` case in the eval set.
- **Fuzzy dedup.** Near-duplicate names collapse (generic words like "labs"/"protocol" ignored), not just exact matches.

Still weak, and honestly so:

- **Star velocity is a lead, not a verdict.** Dampened, but still biased toward dev-tooling/consumer over stealth infra and non-code companies; treat it as one signal among several.
- **The heuristic still misses *semantic* fit.** It's the offline default and eval baseline; `LLMScorer` is the real judge and needs a real labelled set to calibrate.
- **Coverage is bounded** by single-source bias and GitHub/Harmonic API limits.

The path to signal that's actually reliable:

1. **Deepen the triangulation.** v0.1 already blends fit + traction + credibility; add contributor quality, on-chain traction, founder pedigree and funding history as further independent signals. No single metric decides; reliability comes from agreement across them.
2. **Calibrate, don't guess.** Grow the labeled eval set, measure precision / recall (and precision@k), and ship a scorer change only when it doesn't regress.
3. **Human-in-the-loop.** Every digest review writes labels back to the eval set, so the scorer improves weekly instead of drifting.
4. **Semantic dedup.** Swap exact-match for embeddings + pgvector.

In short: **reliability here is a process — the eval loop — not a property of any single heuristic.** Precision@k trending up over weeks is the metric to hold it to.

## Roadmap (what I'd build next)

Semantic dedup via embeddings + pgvector · Memo agent (company → source-cited memo) · Pulse (portfolio monitoring) · Scout (candidate triage) · push digest to Airtable/Notion.

---

*Fixtures in `data/fixtures/` are illustrative, not real companies. Thesis encoded in `config/thesis.yaml` is derived from Frachtis's public writing and is meant to be edited.*
