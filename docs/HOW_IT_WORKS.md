# Signal — how it's built, and where the gaps are

A plain-language walkthrough of what Signal is, how it was put together, and — just as
importantly — what it *doesn't* do. The honest limits are part of the pitch: a fund needs a
tool that knows the edge of its own reliability.

> **Two versions below.** Part A is for a **non-technical reader** (with the tech stack named at
> the end). Part B is the **technical detail**. Skip to whichever you need.

---

# Part A · The plain-English version

## The problem it solves
A pre-seed fund's edge is finding great crypto/AI companies *before they're obvious* — while
they're still a GitHub repo, a hackathon project, or a handful of respected people quietly paying
attention. Doing that by hand is slow and easy to miss. **Signal is an AI research assistant** that
does the first pass automatically.

## What it actually does
Every day it can:
1. **Go looking** across public places where early companies leave footprints (code, on-chain
   activity, research, social).
2. **Grade each company against the fund's specific taste** — written down once as a "thesis" the
   fund can edit anytime.
3. **Hand back a ranked shortlist** with the reasoning and clickable sources for every claim, plus
   a one-page investment memo on demand.

Think of it as a **tireless junior analyst**: it reads everything, ranks it against the partner's
playbook, shows its work — and then a human makes the actual call. It never pretends to be the
decision-maker.

## Why it's trustworthy (the unusual part)
Most "AI tools" ask you to just believe the output. Signal does the opposite:
- Every claim links to its **source** — if the AI can't prove where a fact came from, that fact is
  thrown away.
- It's **honest about weak companies** instead of hiding flaws — early-stage risks are shown as
  notes, not swept under a high score.
- Most importantly, it comes with its **own report card**: a "backtest" that measures whether the
  tool would actually have caught real deals in time. That's the difference between a demo and a
  tool a fund can rely on.

## How you can see it
There's a live, always-on demo you can click through (the ranked deals, the scoring breakdown, the
thesis, the memos), and a full version that runs on a laptop where the "Run" button actually goes
and fetches fresh data.

## The honest gap (a feature, not an excuse)
The tool's own report card came back **"works in part," and it says so out loud:**
- It **reliably catches companies that leave a public trail** — open-source projects, on-chain
  activity, research. Roughly **2 out of 3** of those, typically **~45 days before they became
  obvious**. Early enough to matter.
- It is **essentially blind to "warm intro" deals** — the ones that come through a partner's
  personal network and have no public footprint yet. **Near zero** of those.

So the honest positioning is: Signal is a powerful **widener of the top of the funnel for public
dealflow**, not a replacement for a partner's relationships. A few other limits, stated plainly:
the premium data sources are wired up but not yet validated against paid live feeds; the
"popularity" signal leans toward developer tools over stealth infrastructure; and the always-on
demo is view-only (the live "go fetch data" button runs on a laptop, not the public site). The
point of naming all this is that **a fund should trust a tool that knows the edge of its own
reliability** — and this one measures it.

## The tech stack (for whoever asks)
- **Language & core:** **Python**, standard-library-first — the whole demo runs with essentially
  one dependency (`pyyaml`), so it works offline with no setup.
- **AI models:** provider-agnostic — **Anthropic Claude** for high-quality write-ups, with
  cheaper/local fallbacks (**Groq, Gemini, OpenRouter, Ollama**); a plain deterministic scorer
  runs when no AI key is present.
- **Data sources:** **GitHub** (code activity), **DefiLlama + Blockscout** (on-chain),
  **OpenRank / Farcaster** (social reputation), **arXiv / IACR** (research) on the free tier;
  **Harmonic, Neynar, Messari, Nansen** on the premium tier.
- **Web app:** a lightweight **single-page app (vanilla HTML/CSS/JavaScript)** served by Python's
  built-in web server — no heavy frameworks.
- **Storage:** **SQLite** for tracking momentum over time.
- **Integrations:** a custom **MCP server** (so it plugs into Claude / AI assistants), exposing its
  logic to the fund's own tools.
- **Automation & hosting:** **GitHub Actions** runs it in the cloud on a button-press and keeps the
  demo fresh; the public demo is hosted **free on GitHub Pages**.
- **Quality control:** an automated **evaluation suite gates every change** (it can't ship if
  accuracy drops), plus the point-in-time **backtest** using historical GitHub archives and the
  Wayback Machine.

---

# Part B · The technical detail

## 1 · What it is

**Signal is a thesis-driven dealflow sourcing + diligence agent for a crypto/AI pre-seed fund.**
It gathers candidate companies, scores each against an *encoded thesis* (`config/thesis.yaml`),
and ships a ranked, source-cited digest — plus a **Phase 0 backtest** that measures whether the
sourcing signal is actually reliable before anyone trusts it.

The guiding idea: **scores triage, humans decide.** It's a high-recall funnel that cheaply
surfaces what a partner would otherwise miss and filters obvious noise — not an autonomous
"good deal" oracle.

---

## 2 · How it's created

### The pipeline
One orchestrator runs five stages: **gather → dedup → enrich → score → digest**
(`src/signalfund/orchestrator.py`).

1. **Gather** — each source pulls candidate companies.
2. **Dedup** — exact + fuzzy near-duplicate removal (`dedup.py`).
3. **Enrich** — each signal's `enrich()` pass writes evidence onto the candidate.
4. **Score** — the composite scorer turns thesis-fit + signals + credibility into a 0–100 number.
5. **Digest** — renders `out/digest.md` / `.json` and a visual `out/dashboard.html`.

### The signals (why these, and how they're kept honest)
Every signal is reputation-weighted and shown in the breakdown so a human can see *why*.
**Guiding principle: raw counts are worthless** — weight by reputation (bot swarms self-cancel),
prefer hard-to-fake actions, gate on account age, score ratios not totals.

| Signal | Free source | Premium upgrade |
|---|---|---|
| `fit` · `traction` · `code_health` | GitHub REST (+ a custom star-velocity MCP) | — |
| `team` | GitHub (technical-founder, frontier-lab pedigree) | Harmonic (exits, talent-flow) |
| `onchain` | DefiLlama + Blockscout (real TVL, holders) | Nansen (Smart-Money inflow + convergence) |
| `social` | OpenRank (Farcaster reputation) | Neynar (smart-follower convergence) |
| `pre_public` | arXiv / IACR / grants / ETHGlobal | Evertrace |
| stage-gate | — | Messari (down-ranks already-funded rounds) |
| `network_radar` | Neynar + curated smart accounts | (on-chain twin lives in Nansen) |
| `watchlist` | hand-found leads (`config/watchlist.yaml`) | — |

### The scoring
A **weighted blend**, not a sum (a sum saturated every strong deal at 100):
`score = fit·0.6 + signal_strength·0.4 + credibility_adj`, where `signal_strength` collapses the
quality signals onto a 0–100 scale. Thesis-**fit dominates**, so a hyped but off-thesis company
still ranks low. **Credibility** splits *hard* anti-signals (ponzi/presale — screen out) from
*soft* notes (early-stage, few commits — shown as **risks**, no penalty), so a strong early team
isn't zeroed out. Every weight is tunable from `config/thesis.yaml` without touching code.

### The engineering choices that matter
- **Offline-first.** The demo, evals, and backtest need only `pyyaml`; heavy deps (httpx,
  model SDKs, BigQuery) are lazily imported, so nothing blocks a keyless demo.
- **Graceful absence.** Any signal whose key is missing contributes **0** — it never penalises a
  good company. The system runs at whatever tier your keys allow; switching tiers needs no code.
- **Model routing** (`llm.py`) — heuristic by default; local/cheap **triage** → frontier
  **synthesis**; provider-agnostic (Claude / Groq / Gemini / OpenRouter / Ollama). A client-side
  throttle + 429-retry keeps batch runs from silently falling back mid-run.
- **Verifiability over trust.** LLM-cited URLs that aren't in a candidate's provided sources are
  dropped — the fund's own thesis (verifiable, permissionless) applied to the tool itself.
- **Evals, not vibes.** `evals/` holds a labeled set and is **CI-gated**: a scorer change ships
  only if precision/recall hold, alongside per-feature offline checks.

### The interfaces
- **CLI** — `python -m signalfund --demo` (offline) / `--limit N` (live).
- **Interactive web UI** — `python -m signalfund.webapp` (stdlib SPA: Run, signal toggles,
  scorer picker, digest, memos, sectioned thesis editor, backtest).
- **Custom MCP server** — star-velocity computed from SQLite snapshots, usable inside Claude Code.
- **Cloud run** — a GitHub Actions "Run" button executes the pipeline with zero secrets.
- **Memo agent** — turns a company into a source-cited investment memo.

### The two diligence products
- **Sourcing digest** — the ranked dealflow.
- **Phase 0 backtest** — reconstructs *point-in-time* signal (GitHub via GH Archive, sites via the
  Wayback Machine — no look-ahead) and asks: *would Signal have surfaced real deals early enough to
  matter?* Emits a 🟢/🟡/🔴 go/no-go.

### The public demo
The interactive UI can't run as-is on a static host (its `/api/*` routes need a Python backend),
so the always-on public demo (`docs/` → GitHub Pages) is a **static snapshot of the real SPA**:
data is baked into JSON, browsing/toggles/viewing work client-side, and compute actions show a
"runs locally" note. A weekly GitHub Action rebuilds it. Zero servers, zero secrets, no cold starts.

---

## 3 · The gap (said plainly)

### 3a · The core finding — sourcing works *in part*
The backtest verdict on the labeled set is **🟡 YELLOW**, and this is the most important honest
result in the whole project:

| Slice | Recall | What it means |
|---|---|---|
| **Public-channel** deals (OSS / repos / sites) | **~67%** | the slice public signal genuinely covers |
| **Warm-intro / inbound** deals | **~0%** | relationship-sourced deals have ~no public footprint |
| Median **lead time** (caught deals) | **~45 days early** | early enough to act on |

So Signal is a strong funnel **for the public slice of dealflow** and **blind to warm-intro
deals** — which is exactly why it's positioned as *triage with a human in the loop*, not a
replacement for a partner's network. The finding drives the design: lean on sourcing where it
demonstrably works (public / OSS / hackathon / research), and put the higher-leverage bet on the
**synthesis side** (the Memo agent). *(Directional at small N.)*

### 3b · Validation gaps
- **Premium signals are scaffolded, not validated.** Harmonic, Neynar, Messari, and Nansen are
  built with fixture tests and defensive parsing, but their **live field mappings are unverified**
  without paid keys — they must be validated against real responses before production.
- **Small-N backtest.** The verdict is directional; it needs a larger labeled set (and ideally
  internal first-touch dates) to harden.

### 3c · Signal-quality gaps
- **Star velocity is a lead, not a verdict** — biased toward dev-tooling / OSS over stealth infra.
- **The heuristic scorer misses *semantic* fit** — it's the deterministic offline baseline; the
  LLM scorer improves rationales but needs a key.
- **On-chain / convergence signals need an on-chain footprint** — so they're diligence and
  corroboration, **not earliest discovery** (they confirm conviction on something already on-chain).
- **Coverage is bounded by API rate limits** and the public-footprint blind spot above.

### 3d · Product gaps
- **The public demo is read-only.** GitHub Pages can't run the backend, so live "click Run →
  fresh results", memo generation, and thesis-save work **only locally** (`python -m
  signalfund.webapp`) — or via the GitHub Actions run.
- **Human-in-the-loop is required, by design.** Signal surfaces and filters; a person makes the call.

### The path to more reliable signal
Deepen **triangulation** (independent signals that must agree), **calibrate don't guess** (grow the
eval set, hold precision@k), keep the **human-in-the-loop** loop writing labels back on every
review, and add **semantic dedup** (embeddings + pgvector). Reliability here is a *process* — the
eval loop — not a property of any single heuristic.
