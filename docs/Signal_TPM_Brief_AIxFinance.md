# Signal — Technical PM Brief

### AI × Finance · internal dealflow & diligence intelligence for an early-stage fund

**Author:** Technical PM  ·  **Team:** AI Engineer, ML Engineer, Production/MLOps Manager  ·  **Status:** draft for team review

This brief runs four PM lenses over one product: **brainstorming → research synthesis → spec (PRD) → metrics framework**, plus team ownership. The product is *Signal* — the AI-native system that sources, triages, synthesizes and monitors dealflow so a small fund punches above its weight.

> **Honesty note (read first).** The research synthesis below is *triangulated from secondary sources* — the fund's public writing, the role definition, the OpenClaw case, comparable VC-tooling, and our own build evidence — **not** a primary user-research study. Findings are tagged with confidence. The metrics section is a *proposed framework with targets to validate*, not a review of live data: we can't review metrics we haven't instrumented yet (that's Phase 0).

---

## 1 · Product Brainstorming

### Frame

- **Exploring:** how an AI system gives a 3–5 person fund the dealflow and diligence leverage of a much larger team.
- **Why now:** models are finally good enough to synthesize primary sources reliably; crypto/AI dealflow is exploding faster than any human team can track.
- **Constraints:** tiny team, no tolerance for tools that break in production, must be crypto-native, outputs are read by partners/LPs (high bar).
- **Great outcome:** a clear-eyed view of *where the real leverage is* — and the riskiest assumption we must test before building much.

### The job to be done

> *When a fundable team is forming, I want to find the best ones before they're obvious and understand them fast enough to act with conviction — so I win allocation and don't miss the one.*

Functional job: source + diligence faster. Emotional job: feel confident I'm not missing deals. Social job: look sharp to LPs and co-investors. The competitive set we're "firing": manual GitHub/X scrolling, scattered notes, gut feel, and hours lost to memo-writing.

### How Might We

1. HMW surface a fundable team weeks before it trends, without drowning the partners in noise?
2. HMW compress a company into a partner-grade memo in minutes instead of hours — without fabricating a single fact?
3. HMW encode *this fund's* thesis so the system's judgment looks like the partners', not generic VC?
4. HMW make every output verifiable (source-linked) so a partner trusts it at a glance?
5. HMW tell the difference between real traction and manufactured hype?

### Diverge — opportunity/solution tree

```
OUTCOME: more high-conviction pre-seed checks into eventual winners
├── O1 Sourcing coverage — see teams earlier
│   ├── Signal (multi-source velocity + thesis scoring)   exp: backtest recall on past deals
│   └── Buy it (Harmonic saved searches)                  exp: 2-wk trial, compare net-new hits
├── O2 Triage speed — separate signal from noise fast
│   └── Composite scorer + ranked digest                  exp: precision@20 vs partner labels
├── O3 Diligence depth — understand a team fast        ★ likely highest leverage
│   └── Memo agent (source-cited, thesis-aware)           exp: time-to-memo + partner usefulness rating
├── O4 Conviction/decision support
│   └── Risk + open-questions generator                   exp: do partners add/keep its questions?
└── O5 Portfolio early-warning
    └── Pulse (on-chain/commit/sentiment deltas)          exp: lead time vs. finding out manually
```

### Provoke — the riskiest assumptions (this is the part that matters)

- **🔴 Kill-shot assumption:** *that public, scrapeable signal is additive to a partner's network.* At pre-seed, the best deals are sourced through **warm relationships before any public footprint exists**. If so, Signal's recall on the deals that actually matter is structurally low, and we'd be building a beautifully-engineered tool for the deals we'd lose anyway. **This is the one to test first.**
  - *Cheapest test:* backtest. Take the last ~20 deals the fund did or wishes it had — would Signal have surfaced them, and how many days/weeks early? If it can't, pivot from sourcing.
- **Build-vs-buy:** Harmonic already does sourcing/enrichment well. Building our own sourcing may be reinventing a wheel; our defensible edge is **thesis-encoded scoring + synthesis**, not raw discovery.
- **Adoption:** will a busy partner actually read a daily digest? A tool nobody opens has zero recall in practice.
- **Trust ceiling:** can precision get high enough that the team stops double-checking? If not, it's a toy.

### Converge — where I'd point the team

1. **Lead bet: diligence compression (Memo), not sourcing.** Synthesis is universally painful, has no relationship moat, and is where our thesis-encoding is defensible. Sourcing has incumbents and a network moat we can't out-engineer. *Provocation for the team: we may be over-valuing Signal-as-sourcing because it's the fun build, not the high-leverage one.*
2. **Keep Signal, but as a high-recall triage funnel with a human in the loop** — explicitly not an oracle (see PRD non-goals).
3. **Pulse (portfolio monitoring) is an under-rated quick win** — narrow, low-noise, immediate value, and it sidesteps the sourcing-recall problem entirely.

**Biggest unknown → cheapest resolution:** sourcing recall → the backtest (a few days of work, before we build more). That single experiment de-risks the whole roadmap.

---

## 2 · Research Synthesis

**Methodology:** thematic triangulation across the fund's public essays, the role spec, the OpenClaw security case, comparable VC-tooling, and our build evidence. **Not** primary user interviews — confidence is tagged accordingly. Decisions this informs: what to build first and how to sequence the roadmap.

### Key findings (priority-ordered)

| # | Finding | Evidence | Confidence | Impact |
|---|---------|----------|------------|--------|
| F1 | The fund's binding constraint is **leverage, not capital** — a small team holding a high bar | Role: build agents so a "small team can punch above its weight" | High | High |
| F2 | They believe durable value lives in **control planes / verifiability**; tools that *embody* that earn trust | Two published theses on agents + crypto rails | High | High |
| F3 | Analysts lose disproportionate time to **synthesis** (memos, market maps, diligence) | Role lists these as core, recurring outputs | Med-High | High |
| F4 | "**Reliable signal**" is the explicit bar; demo-grade tools that break in prod are a screened anti-pattern | Role: opinions on "what works in prod vs. breaks in a demo" | High | High |
| F5 | Public signals (star velocity, CT hype) are **noisy & gameable** | Our build evidence + OpenClaw's malicious-add-on fallout | High | Med |
| F6 | Best pre-seed deals are **relationship-sourced before public signal** exists | VC industry pattern (assumption — must validate) | **Low-Med** | High |
| F7 | The team is **AI-native** and expects evals, guardrails, citations — not vibes | Role language; "shipped real things with frontier models" | High | Med |

### Segments (who the product serves)

- **The Partner** — decision-maker, time-poor, network-rich. Wants conviction fast; will not read a noisy feed. Success = "didn't miss a deal, looked sharp to LPs."
- **The Investor/Analyst** (the builder-operator) — sources, triages, writes memos. Lives in the tool daily; feels the synthesis pain most.
- **LP / co-investor** (downstream consumer) — reads memos/updates. Values clarity and that claims are backed.

### Opportunity areas (qualitatively sized)

1. **Diligence compression** — highest frequency pain × no moat against us × defensible via thesis encoding. *Top opportunity.*
2. **Portfolio early-warning** — narrow, low-noise, clear value; good fast win.
3. **Sourcing coverage** — large *if* F6 is false; gated on the backtest.

### Recommendations

- **R1 (from F3, F2):** make **Memo** the flagship build; bake in citation verification so it embodies the verifiability thesis. 
- **R2 (from F6):** run the **sourcing backtest before** investing further in Signal-as-sourcing.
- **R3 (from F4, F5, F7):** treat the **eval harness + precision tracking as P0**, not a nicety — it *is* the reliability story.
- **R4 (from F1):** optimize the whole system for **partner minutes saved**, the truest proxy for leverage.

### Open questions → feeds the research plan

- (Partner) What share of last year's best deals were relationship-sourced vs. discoverable? *(answers F6)*
- (Data) Which sources actually have crypto/AI coverage at the pre-seed stage?
- (Partner/Analyst) What does a memo need to contain to be trusted without rework?

---

## 3 · Product Requirements (PRD) — Signal v1

### Problem statement
A small fund cannot manually track the volume of crypto/AI teams forming, nor afford the hours each company takes to diligence into a partner-grade memo. The cost is missed deals and slow, inconsistent conviction — directly capping how much capital the team can deploy well.

### Goals (outcomes, measurable)
1. Cut **time-to-first-memo** for a surfaced company from hours to under ~15 minutes.
2. Achieve **trusted triage**: partners act on the ranked digest without re-screening from scratch (precision@20 ≥ target, set in Phase 0).
3. Save **partner/analyst minutes per week** (the leverage metric).
4. Every output is **source-verifiable** — zero un-cited factual claims in shipped memos.

### Non-goals (ruthless, to prevent scope creep)
- **Not** an autonomous "good deal" decider — human-in-the-loop by design.
- **Not** a CRM/pipeline system (it writes *into* Airtable/Notion; it doesn't replace them).
- **Not** a multi-fund SaaS product in v1 (single-tenant, our thesis).
- **Not** sourcing breadth that duplicates Harmonic — we integrate it, not rebuild it.
- **Not** consumer-facing; internal tool only.

### User stories
- *As an analyst,* I want a daily ranked digest of thesis-fit companies with source links, so I can triage in minutes instead of scrolling.
- *As an analyst,* I want to point the system at a company and get a source-cited draft memo, so I skip the blank-page hours.
- *As a partner,* I want each candidate's score broken into sub-scores (fit / traction / credibility), so I can see *why* and trust it.
- *As a partner,* I want to thumbs-up/down a candidate and have that feedback improve future ranking.
- *As an analyst,* I want portfolio companies monitored for material change, so I hear it from the tool before a founder call.

### Requirements

**P0 — can't ship without (the reliability core):**
- Ingest from ≥2 sources (custom GitHub star-velocity MCP + one of Harmonic/Exa), degrading gracefully without keys.
- Triangulated composite scorer (thesis-fit + dampened traction + credibility) with **exposed sub-scores**.
- **Citation verification** — drop any claim not traceable to a provided source.
- Daily digest delivered to the surface the team already uses (Airtable/Notion/Slack).
- **Eval harness + precision tracking** on a labeled set; CI fails a scorer change that regresses.
- Human feedback capture (thumbs up/down → labels).

*Acceptance (sample):* Given a labeled eval set, when the scorer runs, then precision@k and recall print and a regression blocks merge. Given a generated memo, when a cited URL isn't in the candidate's sources, then it is removed before delivery.

**P1 — fast follow:** Memo agent (company → source-cited memo); Pulse (portfolio monitoring + auto-drafted update); Slack delivery; market-map generation.

**P2 — design for, don't build:** semantic dedup (embeddings + pgvector); LLM-as-judge auto-labeling to grow the eval set; multi-fund tenancy.

### Success metrics
- **Leading:** digest open rate, precision@20, time-to-memo, % memos accepted with light edits.
- **Lagging:** partner-minutes saved/week, # Signal-originated deals reviewed by a partner, portfolio-alert lead time.

### Open questions
- (Partner) sourcing recall target worth funding? *(blocking — backtest)*
- (ML) precision bar for "trusted" triage?
- (Legal/Data) ToS/compliance for each scraped source?
- (Eng) build vs. buy the sourcing layer given Harmonic?

### Timeline & phasing
- **Phase 0 (week 1): de-risk.** Sourcing backtest + instrument metrics + label a seed eval set. *Gate: proceed on sourcing only if recall clears bar.*
- **Phase 1 (weeks 2–4): reliability core.** P0 scorer, citations, digest, evals. 
- **Phase 2 (weeks 5–8): leverage.** Memo + Pulse (P1).

---

## 4 · Metrics Framework & First Review

> No live data yet — this is the framework + targets to validate. **Phase 0 instruments it.**

### North Star
**Partner-reviewed qualified opportunities that Signal sourced or accelerated, per month.** It captures real value (the fund acts on good deals because of the tool), is leading for returns, and is team-influenceable.

### Metric hierarchy

| Level | Metric | Why it matters | v1 Target (validate) | Status |
|-------|--------|----------------|----------------------|--------|
| **NSM** | Partner-reviewed qualified opps via Signal / mo | The leverage outcome | TBD baseline | ⚪ instrument |
| L1 Coverage | Sourcing recall vs. known deals (backtest) | Tests the kill-shot assumption | ≥ 50% surfaced, ≥1wk early | ⚪ Phase 0 |
| L1 Triage | Precision@20 (digest) | Trust in ranking | ≥ 0.8 | ⚪ instrument |
| L1 Synthesis | Median time-to-memo | Core leverage | < 15 min | ⚪ instrument |
| L1 Adoption | Digest open rate (team) | Unused = zero value | ≥ 4/5 days | ⚪ instrument |
| L1 Quality | % memos accepted w/ light edits | Output trust | ≥ 70% | ⚪ instrument |
| L1 Portfolio | Alert lead time vs. manual | Pulse value | + days earlier | ⚪ Phase 2 |
| L2 Cost | $ per processed candidate | Unit economics of routing | trend ↓ | ⚪ instrument |

### Q1 OKR (illustrative)
**Objective:** Make Signal a tool the partners rely on weekly.
- KR1: precision@20 ≥ 0.8 on a 100-item labeled set.
- KR2: median time-to-memo < 15 min across 20 real companies.
- KR3: digest opened ≥ 4 of 5 weekdays for 3 consecutive weeks.
- KR4: ≥ 6 Signal-originated companies reach a partner review.

### Review cadence (fund-sized)
- **Weekly (15 min):** precision drift, digest opens, anything anomalous, active eval changes.
- **Monthly:** full scorecard, cohort of memos accepted/rejected, feedback-loop health.
- **Quarterly:** OKR scoring + the strategic question — *is sourcing or synthesis driving the value?*

### First-review caveats
Everything above is **target-state**; the honest first action is instrumentation. The single most important early number is the **Phase 0 backtest recall** — it decides whether sourcing deserves further investment at all.

---

## 5 · Team & Ownership

| Workstream | Owner | Scope |
|------------|-------|-------|
| Agent orchestration, MCP servers, integrations, LLM scorer | **AI Engineer** | The agentic plumbing; data-source adapters; frontier-model calls |
| Scoring model, embeddings/dedup, eval harness, calibration, ranking quality | **ML Engineer** | Does the score mean anything? Owns precision/recall and the labeled set |
| Pipeline reliability, scheduling, monitoring, cost, delivery surfaces | **Production / MLOps Manager** | Runs daily without drift; cost discipline; ships to Airtable/Notion/Slack |
| Spec, prioritization, **thesis encoding**, partner/LP interface, metrics, sequencing | **Technical PM (me)** | Keeps us building the high-leverage thing, honestly measured |

**Sequencing principle:** riskiest assumption first. Phase 0's backtest (owned by ML + PM) gates everything else — we don't scale a sourcing engine until we've proven it can surface the deals that matter.

---

## Next steps
1. Run the **Phase 0 sourcing backtest** (decides sourcing vs. synthesis emphasis).
2. Instrument the metric set so reviews are real.
3. Lock P0 scope and assign Phase 1 tickets across the three engineers.

*Want this as a slide deck for a team kickoff, or should I draft the Phase 0 backtest plan (data, method, decision rule) next?*
