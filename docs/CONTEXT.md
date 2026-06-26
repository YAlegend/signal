# CONTEXT.md — why Signal exists, and every decision behind it

The single in-repo capture of the research and discussion behind this project, so anyone (or Claude
Code) working in the repo has the full picture. Full long-form versions are in `docs/` alongside this
file. `CLAUDE.md` covers *how to run*; this covers *why*.

---

## 1 · Who this is for — Frachtis

- **What:** a crypto-native **pre-seed** venture fund. **$20M Fund I, launched June 2025.**
- **People:** founded by **Xavier Meegan** (former CIO, Chorus One); investment partner **Brian Crain**
  (former CEO/co-founder, Chorus One); COO **Adina Fischer** (former a16z crypto). Chorus One exited to Bitwise.
- **Where they invest:** crypto infrastructure, DeFi, agent-native products, AI × crypto, fintech,
  post-quantum security, consumer/social.
- **Portfolio signals:** **Fireplace** (interface layer for prediction markets), **Lys Labs**
  (intelligence layer for AI agents).

## 2 · The role this was built for

**Investor / AI Agent Builder** — a hybrid. Three pillars they want in one person:
1. **Venture judgment** — source, scope markets, write memos, run diligence.
2. **Crypto-native research** — read primary sources; go deep technically (ZK, consensus, agent infra).
3. **AI agent building** — *"build AI agents and internal tools for dealflow triage, research
   synthesis, candidate filtering and portfolio monitoring."*

**Application requirements (the deliverables this project supports):**
- **A 2–5 min demo video of agents you've built — the centerpiece.**
- A **2-page quantum-computing investment thesis** (see §6).
- 2–3 links to other things built/written/shipped.
- A one-page CV.

## 3 · Their worldview (the north star for every design choice)

From Frachtis's own essays ("Why AI agents will use crypto rails", "When AI Can Do Everything, The Only
Thing Worth Building Is Control"):

- AI agents will run on **crypto rails** because they're neutral, always-on, programmable, verifiable.
- **Durable value accrues to the control planes** agents rely on — identity, permissions, routing,
  settlement, reputation, **verifiability**. *"Permission is the scarce resource in an age of infinite
  capability."*
- They back agent-native crypto that **abstracts complexity, collapses workflows, executes reliably,
  personalises deeply, interoperates openly, delivers trusted outcomes.**
- They explicitly screen for builders who know **what works in production vs. what breaks in a demo.**

**Design implication, applied throughout Signal:** every output is **source-verifiable**, the system is
**policy/eval-bound**, and we narrate failure modes honestly. The tool embodies their thesis.

## 4 · Why Signal, and the core strategic bet

Signal is "the AI associate stack a modern fund should have," mapped to the four workflows the role
names: **sourcing (Signal), synthesis (Memo), candidate filtering (Scout), portfolio monitoring (Pulse).**

**The contrarian bet (from the TPM brief):** sourcing has incumbents (Harmonic) and a relationship
moat we can't out-engineer; **synthesis (Memo) is the higher-leverage, more defensible wedge** because
it's universally painful and defensible via *our* thesis encoding. Signal is built first because it's
the clearest demo, but the roadmap is gated on a reliability test (§7).

## 5 · Key product decisions & rationale

| Decision | Why |
|---|---|
| **Triangulated composite score** (thesis-fit + log-dampened traction + credibility) with visible sub-scores | One signal (star velocity) is gameable; reviewability builds trust. A star spike alone can't carry a deal. |
| **Word-boundary keyword matching** | Killed false positives like `defi` inside `defined`. |
| **Anti-gaming penalty** (buzzword stuffing, anti-signals) | Public signal is noisy; the OpenClaw fallout showed hype ≠ substance. |
| **Citation verification** (drop un-sourced claims) | Embodies the fund's verifiability thesis; partners must trust outputs. |
| **Tiered model routing** — local triage → frontier synthesis | Cost at scale + privacy (sensitive decks stay local) + a *neutrality* parallel: open-weight models are the permissionless, non-revocable choice, just as Frachtis argues for crypto rails over revocable APIs. |
| **Evals, not vibes** (`evals/`) | The reliability story the role grades hardest; changes are measured, not asserted. |
| **Human-in-the-loop triage funnel, not an oracle** | Honest framing; precision improves over weeks via feedback, not magic. |

## 6 · Data sources & connectors (the recommended stack)

| Need | Pick | Role |
|---|---|---|
| VC sourcing & enrichment | **Harmonic** ⭐ | companies/people/investors, net-new searches (built for VC) |
| Agent-native web search | **Exa** (or Tavily) | gather company info |
| On-chain data | **Blockscout** ⭐ | contracts, holders, txs (public REST) |
| Crypto social & market | **LunarCrush**, CoinDesk/FMP | social signal, price/funding |
| Pipeline / CRM surface | **Airtable** (+ Notion) | where the team works |
| Code / repos | **custom GitHub star-velocity MCP** (built here) | the "build one yourself" flex |

Build-vs-buy note: integrate Harmonic rather than rebuild sourcing; our edge is **thesis-encoded
scoring + synthesis**, not raw discovery.

## 7 · The reliability question + the backtest (kill-shot assumption)

The riskiest assumption: **that public, scrapeable signal is additive to a partner's network at
pre-seed.** If the best deals are relationship-sourced before any public footprint exists, Signal's
recall on the deals that matter is structurally low. The **Phase 0 backtest** (`BACKTEST.md`,
`backtest.py`) tests this with point-in-time reconstruction and a pre-registered GREEN/YELLOW/RED rule.
*The sample run lands YELLOW: Signal catches public-channel/OSS deals early but is blind to
relationship-sourced ones — implying "narrow sourcing, build Memo + Pulse."*

## 8 · Quantum thesis angle (application deliverable, not yet written in full)

Frame quantum through the fund's lens — **verifiability/trust**. The trade is **the migration, not the
threat.** Categories over 3–5 years: (1) crypto-agility middleware ★, (2) quantum-safe wallets/signing
(ML-DSA/FN-DSA), (3) harvest-now-decrypt-later mitigation, (4) PQC × ZK, (5) quantum-safe L1s (mostly
premature — a calibrated "not yet"). Facts: NIST finalised ML-KEM/ML-DSA/SLH-DSA (Aug 2024), Falcon→
FN-DSA (FIPS 206 draft), HQC backup (Mar 2025); US NSM-10 targets ~2035; ECDSA/Schnorr are quantum-
vulnerable. *Status: **written** — `docs/Quantum_Thesis.docx` (polished 2-page) + `docs/Quantum_Thesis.md` (source).*

## 9 · Open threads / next steps
- Run the **Phase 0 backtest on ~20 real deals** (decides sourcing vs. synthesis emphasis).
- Build **Memo** (the higher-leverage bet).
- Record the **demo video** (application centerpiece). *(2-page quantum thesis: done — `docs/Quantum_Thesis.docx`.)*
- Wire the **LLM scorer** with a labeled set for semantic fit.

## 10 · Full briefs (long-form, in this folder)
- `docs/Frachtis_AI_Agent_Builder_Brief.md` — company/role/worldview, agent ideas, model strategy, connectors, application plan.
- `docs/Signal_TPM_Brief_AIxFinance.md` — brainstorm, research synthesis, PRD, metrics framework, team RACI.
- `docs/Signal_Phase0_Backtest_Plan.md` — the full backtest methodology.
