# Frachtis — Investor / AI Agent Builder

## Brainstorm + Application Strategy Brief

*Prepared for your application to the Investor / AI Agent Builder role at Frachtis. Goal: prove you can do the job by building the AI systems the fund actually needs — and packaging them into an application that wins.*

---

## 1. The move, in one line

**Don't apply with a portfolio of random agents. Build the AI associate stack a modern crypto fund *should* have — one coherent system that sources, synthesizes, monitors and triages — and let the demo video walk them through it.**

This does three things at once: it shows venture judgment (you understood their workflow), crypto-native research instinct (the agents are tuned to *their* thesis), and real building ability (you shipped it with Claude Code). That trifecta is literally the job.

---

## 2. What Frachtis is actually testing

The job description names three pillars and says *"we want someone who excels at all three."* Decode it:

| Pillar | What they're checking | How your application proves it |
|---|---|---|
| **Venture judgment** | Can you source, scope a market, and form a defensible view? | Agents tuned to *their* thesis; the quantum thesis essay; your taste in what to build |
| **Crypto-native research** | Do you read primary sources and go deep technically (ZK, consensus, agent infra)? | On-chain / contract-reading agent; citing whitepapers & primary docs; quantum thesis depth |
| **AI agent building** | Have you *shipped* real agents, and do you know what breaks in production? | The demo video (centerpiece); eval harness & guardrails; "patterns that work vs. break" narration |

**The meta-signals they're also reading:**

- **"Surface companies before they become mainstream"** → build sourcing that catches rising signal early.
- **"Read primary sources, not summaries"** → your agents should cite whitepapers, contracts, on-chain data — not blog recaps.
- **"Opinions about which patterns work in production and which break in a demo"** → narrate failure modes and how you fixed them. This single thing separates builders from prompt-jockeys.
- **"High agency, low ego"** → ship something useful to *them*, not a vanity project.

**Their worldview (use it as your north star).** From their own essays, Frachtis believes that when AI agents run on crypto rails, the durable value is in **control planes / trust infrastructure** — identity, permissions, routing, settlement, verifiability — because *"permission is the scarce resource in an age of infinite capability."* They invest in agent-native crypto that *"abstracts complexity, collapses workflows, executes reliably, personalises deeply, interoperates openly and delivers trusted outcomes."*

> **Why this matters for your build:** make your agent system itself embody that worldview — every claim it outputs is *verifiable* (source-linked), it operates within *defined rules* (a policy/controller layer), and it *collapses a manual workflow*. When the partners notice your tool is built on their own thesis, you've won the interview before it starts.

---

## 3. The big idea: "Fund-in-a-box" — an AI associate stack

Pitch it as a single system with a controller (built in Claude Code, using its sub-agent + MCP-server patterns) orchestrating four specialist agents that map **exactly** onto the four workflows the JD names: *dealflow triage, research synthesis, candidate filtering, portfolio monitoring.*

```
                 ┌──────────────────────────────┐
                 │   ORCHESTRATOR / CONTROL PLANE │  ← policy, citation-verification, routing
                 │   (Claude Code, sub-agents)    │
                 └──────────────────────────────┘
                   │        │         │        │
        ┌──────────┘   ┌────┘    ┌────┘   └─────────┐
        ▼              ▼         ▼                  ▼
   ① SIGNAL        ② MEMO     ③ PULSE           ④ SCOUT
   sourcing      synthesis   portfolio          candidate
   (the hero)                monitoring         triage (meta)
```

Building a *system* rather than four toys is itself the judgment signal — it mirrors their thesis that *"the durable winners won't be 'an agent' but the control planes that make agents reliable."*

---

## 4. The agent concepts (prioritized)

Ranked by ROI for the application = (impact on Frachtis) × (demo wow) ÷ (build effort).

### Tier 1 — Build these for the demo

**① SIGNAL — the dealflow sourcing agent (your hero; build this deepest)**

- **What it does:** Daily, pulls "rising signal" from where crypto/AI founders emerge *before* they're obvious — GitHub star-velocity (new repos spiking), IACR ePrint / arXiv (cryptography & ZK researchers), Farcaster/X, ETHGlobal & hackathon winners, grant programs, fresh token/testnet launches. Scores each against Frachtis's published thesis with an LLM, then outputs a ranked digest: company, one-paragraph *"why this fits Frachtis,"* and links to **primary sources**.
- **Why Frachtis cares:** It's the JD line *"surface companies before they become mainstream"* turned into software. Killer detail: their own essay cites OpenClaw hitting 100k→300k GitHub stars as the signal that mattered — so a **GitHub star-velocity detector is a direct callback to their own writing.** If Signal re-surfaces one of their portfolio bets (e.g., something like Lys Labs or Fireplace) or a company they'd obviously want, that's the moment that gets you hired.
- **Build with Claude Code:** an MCP server per source (GitHub API, arXiv/IACR, an X/Farcaster reader, RPC/Etherscan for on-chain); a scoring sub-agent prompted with Frachtis's thesis; a scheduled run writing to Airtable/Notion or a tiny web dashboard.
- **Demo-ability:** 10/10. Run it live, show today's digest, click through to a primary source.

**② MEMO — company → investment memo agent**

- **What it does:** Input a company (URL / deck / name). It gathers whitepaper, docs, GitHub, token & on-chain data, team backgrounds and competitors, then produces a structured pre-seed memo in Frachtis's format: thesis-fit, what's novel, traction, risks, open questions — **every factual claim source-linked.**
- **Why Frachtis cares:** It's exactly what partners read, and the citation discipline answers *"read primary sources, not summaries."* It collapses hours into minutes.
- **Build with Claude Code:** reuse Signal's MCP data sources; a synthesis sub-agent with a fixed memo template; a **citation-verifier pass** that drops any claim it can't trace to a source (this is your "control plane" / verifiability wink).
- **Demo-ability:** 9/10. Open a polished generated memo on a real company.

### Tier 2 — Show briefly or include as roadmap

**③ PULSE — portfolio monitoring agent**

- **What it does:** Watches portfolio (and watchlist) companies — GitHub commit velocity, token price/TVL, new job postings (a hiring-velocity proxy for momentum), governance proposals, social sentiment, news — and alerts on material change, auto-drafting an LP-update snippet.
- **Why Frachtis cares:** Direct JD line ("portfolio monitoring"); turns reactive check-ins into proactive intelligence.
- **Build with Claude Code:** scheduled diff-and-alert job over the same MCP sources; LLM summarizes "what changed and why it matters."
- **Demo-ability:** 7/10 — show one good alert + the auto-drafted update.

**④ SCOUT — candidate/application triage agent (the meta closer)**

- **What it does:** Triages applicants to *this very role* — parses demo-video transcripts, the thesis PDF, portfolio links and CV against the rubric, then ranks and explains.
- **Why Frachtis cares:** It's the JD line "candidate filtering," and it's the tool they need *right now* to process applications. Closing your video with *"…and here's Scout, the tool I'd use to triage applications like mine"* is a high-agency, memorable mic-drop.
- **Risk / framing:** Could read as cocky. Frame it as service, not swagger: *"You're drowning in applications — here's how I'd help."* Don't have it score the user's own application on camera.
- **Demo-ability:** 8/10 for memorability.

### Tier 3 — Ambitious differentiators (mention as vision; build only if time)

- **DILIGENCE (technical/on-chain):** reads a protocol's smart contracts, summarizes architecture, flags audit status & fork-originality, checks token-holder concentration and wash-trading signals. Highest proof of technical depth (contracts, consensus) — build a thin slice if your crypto chops are strong.
- **THESIS COMPANION:** helps research and draft the fund's public theses, hunts proof points (the way they used OpenClaw), and keeps a living "thesis scorecard." Plays to a fund whose brand *is* its writing.

---

## 5. Architecture & the "what breaks in production" narrative

They explicitly want someone with *"opinions about which patterns actually work in production and which break in a demo."* Bake these into the build and **say them out loud in the video** — it's the strongest differentiator available to you:

- **Citation verification > raw generation.** LLMs hallucinate sources. A verifier pass that discards unciteable claims is the difference between a memo a partner trusts and one they don't. (Also your "verifiability / control plane" wink.)
- **Deterministic scaffolding, LLM only where judgment is needed.** Fetch/parse/dedupe with code; reserve the model for scoring and synthesis. Cheaper, faster, more reliable.
- **Evals, not vibes.** Keep a small labeled set ("would Frachtis want this deal? y/n") and measure Signal's precision. Showing an eval harness signals real production maturity.
- **Idempotent, scheduled, observable.** Cron + dedupe + a run log. Agents that quietly drift are worse than no agents.
- **Cost/rate-limit discipline.** Cache aggressively; batch. Mention what you'd do differently at scale.
- **Stack:** Claude Code as orchestrator (sub-agent pattern); MCP servers per data source (there's a clean MCP-builder pattern for this); Airtable/Notion or a small dashboard as the surface; everything in a public GitHub repo with a clear README.

**Model strategy — route, don't pick one model.** Treat the model as a per-task routing decision, not a single choice:

- **Local / open-weight** (self-hosted via Ollama/vLLM, *or* open models via Together/Fireworks/Groq — you don't need GPUs to get the cost/control wins): high-volume, low-judgment work — parsing, classification, thesis-triage, and embeddings for dedup/semantic search (bge/nomic/e5 → sqlite-vec/LanceDB/pgvector). Near-zero marginal cost lets Signal scan thousands of repos/papers daily.
- **Frontier** (Claude/GPT top tier): the high-stakes synthesis partners read — memos, thesis-fit reasoning, citation-verification (ideally a *different* model than the generator, so it truly cross-checks). Never demo a local model's output on camera; quality is the whole impression.
- **The funnel:** 10,000 raw signals → local triage → ~200 candidates → frontier memo on the top ~20. Filter cheap, escalate selectively.
- **Two VC-specific wins:** *privacy* (confidential decks/founder data processed locally by policy — a control-plane design that mirrors Frachtis's own thesis) and *cost* (show the number: local vs. frontier cost-per-1,000-items, % escalated, quality delta from your evals).
- **The parallel to land in the interview:** Frachtis argues agents will prefer neutral crypto rails over APIs that "can be revoked, access throttled, or automation blocked." The same neutrality argument applies one layer up — open-weight models are the permissionless, non-revocable choice for inference you don't want a revocable dependency in the critical path.

**Data sources & connectors (map each to an agent).** Two uses: connectors that speed up *your own* research/workflow, and the data layer your *agents* call. For the demo, use existing MCPs to move fast — but build **at least one custom MCP yourself** (e.g., a GitHub *star-velocity* server; velocity isn't a standard endpoint, you compute it) to show real building depth.

| Need | Connector(s) | Powers |
|---|---|---|
| **VC sourcing & enrichment** | **Harmonic** ⭐ (companies / people / investors, net-new saved searches — built for VC) | Signal, Memo, Scout |
| **Agent-native web search** | **Exa** (neural search), Tavily | Signal, Memo |
| **On-chain data** | **Blockscout** ⭐ (contract ABIs, holders, txs, multi-chain) | Diligence, Pulse, Memo |
| **Crypto social & market** | **LunarCrush** (social signal), CoinDesk / FMP (price, funding) | Signal, Pulse |
| **Pipeline / CRM surface** | **Airtable** (Frachtis's own application form lives here), **Notion** (already connected) | all four |
| **Storage / vectors** | Supabase or Postgres + pgvector (self-host) | dedup, semantic search |
| **Code / repos** | No managed GitHub MCP here → official GitHub MCP or REST/GraphQL API; build your own star-velocity MCP | Signal, Diligence |

Prefer sources you control in the critical path (same neutrality logic as the model layer). The native X API is costly/restricted — use LunarCrush for aggregated crypto social and Neynar for Farcaster.

---

## 6. How it all fits the application

The application has four parts. Here's how the stack feeds each.

### Part 1 — The 2–5 min demo video (the centerpiece — *don't skip it*)

Substance over polish (they said so). Suggested 4-minute script:

1. **0:00–0:30 — Frame the judgment.** *"A pre-seed crypto fund lives or dies on dealflow and synthesis. I built the associate stack a fund like Frachtis should have. Here it is running."*
2. **0:30–1:45 — SIGNAL, live.** Run it. Show today's ranked digest, the thesis-fit reasoning, click into a primary source. Note it caught [X] before it trended.
3. **1:45–2:45 — MEMO.** Open a generated memo on a real crypto company. Highlight that every claim is source-linked, and show the citation-verifier dropping an unsupported claim.
4. **2:45–3:30 — What broke and what you learned.** The honest part they're really grading: hallucinated sources → verifier; LLM-for-everything was slow/expensive → moved parsing to code; show your eval numbers.
5. **3:30–4:00 — PULSE + the SCOUT wink + what you'd build next.** Close with vision and ownership.

Record in one screen-share take. Talk like a builder, not a marketer.

### Part 2 — The 2-page quantum thesis

Prompt: *"Quantum computing is coming and has implications for crypto. As an early-stage investor, what's the thesis? What categories are worth investing in over the next 3–5 years, and why?"*

**Recommended angle (Frachtis-flavored):** Frame quantum through *their* lens — **verifiability and trust.** Quantum doesn't just threaten encryption; it threatens the *verifiable commitments* crypto exists to provide. The investable opportunity isn't "quantum tech," it's **the migration and crypto-agility layer** that keeps trust intact through the transition.

**A defensible 3–5 year category map:**

1. **Crypto-agility middleware** *(highest near-term conviction)* — tooling that lets chains, wallets and protocols swap signature schemes without forks. The transition is the product; bet on the picks-and-shovels.
2. **Quantum-safe wallets & signing** — migration to NIST PQC signatures (ML-DSA / FN-DSA) and account-abstraction paths that let users rotate keys. Most chains sign with ECDSA/Schnorr, which a cryptographically-relevant quantum computer would break.
3. **"Harvest-now, decrypt-later" mitigation** — exposed public keys (reused addresses, pending mempool txs) are recordable today, breakable later. Tooling to quantify and reduce this exposure.
4. **PQC × ZK intersection** — post-quantum-secure proving systems; the cryptography talent here is exactly Frachtis's hunting ground.
5. **Quantum-safe L1s / L2s** *(watch, mostly too early)* — name why most are premature, and the narrow conditions under which one becomes investable. A calibrated "not yet" shows judgment.

**Grounding facts (verify and cite the primaries yourself):** NIST finalized its first PQC standards in Aug 2024 — ML-KEM/Kyber (FIPS 203), ML-DSA/Dilithium (FIPS 204), SLH-DSA/SPHINCS+ (FIPS 205); Falcon is being standardized as FN-DSA (FIPS 206, draft); and in March 2025 NIST selected HQC as a backup KEM. US NSM-10 targets federal migration to quantum-resistant cryptography by ~2035. The live tension is **Q-Day timing** (uncertain) vs. **migration lead time** (long, multi-year). The investor's edge is acting on the *gap* between those two.

**What makes it land:** a crisp point of view ("the transition, not the threat, is the trade"), a contrarian calibrated take (most quantum-safe L1s are premature), and primary sources. Keep it to 2 pages — they prize *"compress a complicated company into a page without losing what matters."*

### Part 3 — Two or three other things you've built/written/shipped

- **Open-source the stack:** the GitHub repo for Signal/Memo + a short, sharp README. Shipped code they can read = top signal.
- **Publish one thesis post:** e.g., a piece riffing on their "control plane" idea or your quantum angle. A public body of work is explicitly a "nice to have," and it proves taste and writing.
- **One more artifact** that shows range — a market map (auto-generated by your stack is a nice flex), an essay, or a prior tool.

### Part 4 — The one-page CV

Lead with **shipped AI/agent work**, then any crypto/technical/investing signal, then the rest. Mirror their language: *agents, pipelines, evals, primary-source research.* One page.

---

## 7. Build plan (realistic sequencing)

If time is tight, build in this order — each step is independently demo-able:

1. **Signal v1** (≈ core weekend): GitHub star-velocity + one more source → LLM thesis-scoring → digest. This alone is a strong application.
2. **Memo v1**: company-in → templated, source-linked memo-out, with the citation-verifier. Reuses Signal's data layer.
3. **Eval harness + README + public repo.** Small but punches above its weight on the "production maturity" axis.
4. **Pulse** (one good alert) and **Scout** (the closer) if time allows — otherwise present them as roadmap in the video.

Then: record the video, write the quantum thesis, publish one post, tighten the CV.

---

## 8. Risks & how not to blow it

- **Don't ship a generic "ChatGPT wrapper."** Every agent must be crypto-fund-specific and thesis-aware, or it reads as undifferentiated.
- **Don't fake crypto depth.** Partners are ex-Chorus One / a16z crypto; they'll catch hand-waving. If your crypto background is light, lean into genuine primary-source reading and fast learning, and let the *building* + *judgment* carry — but read the whitepapers for real.
- **Don't over-polish the video.** They said polish doesn't matter; substance does. A slick edit with thin substance backfires.
- **Use Scout's "meta" angle as service, not swagger.**
- **Make verifiability visible.** If they remember one thing, let it be "this person's agents cite their sources and stay within rules" — that's their whole worldview reflected back.

---

## 9. What I can do next for you

- Scaffold the **Signal** repo (MCP servers + scoring + scheduler) so you can start building immediately.
- Draft the **demo-video script** to your actual build and timing.
- Write a full first draft of the **2-page quantum thesis** for you to sharpen and make your own.
- Draft the **thesis blog post** or a **market map** as a portfolio piece.
- Tighten your **one-page CV** against this JD.

Just tell me which, and your own background (coding comfort, crypto depth, any prior shipped work), so I can tune everything to you.

---

*Sources: Frachtis homepage, careers page, and essays ("Why AI agents will use crypto rails," "When AI Can Do Everything, The Only Thing Worth Building Is Control"); NIST PQC standardization updates (2024–2025). Verify all primary sources yourself before submitting — it's exactly the discipline the role rewards.*
