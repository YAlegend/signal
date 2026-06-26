# Signal — sourcing shortlist (manual pass)

**Date:** 2026-06-25 · **Thesis:** Frachtis — agent-native crypto + the control planes agents rely on
(identity, permissions, routing, settlement, verifiability).

> This is a **manual run of Signal's methodology** (thesis-match → stage filter → reputation-weighted
> signal) over public sources, to seed live dealflow. Fit is judged against `config/thesis.yaml`.
> Stage and "kept building" are flagged as **verify-next** — exactly what the app's `code_health` /
> `pre_public` signals confirm before anything is taken seriously. Scores triage; a human decides.

---

## The early, sourceable slice — ETHGlobal Cannes 2026 finalists (Apr 2026)

Hackathon finalists are the cleanest free-tier `pre_public` signal: ecosystem-vetted, pre-equity, and
6–18 months ahead of a round — **but only count if the team kept shipping**. These three are the most
on-thesis of the 10-project slate.

### 1. ENShell — agent transaction guardrails  ·  fit: **HIGH**  ·  stage: weekend-build
- **What:** "Prevents AI agents from executing malicious transactions caused by prompt-injection." An
  ENS-aware shell that checks a proposed action against policy **before a signature hits the wallet**.
- **Thesis hit:** bullseye on `agent_control_planes` (weight 1.0) — *policy · permission · guardrail ·
  authorization · identity · attestation*. This is the trust layer itself, not an app on top of it.
- **Open question (from thesis):** is the guard defensible vs. incumbent wallets / the model providers?
- **Verify-next:** GitHub repo + commits after Apr 2026 (did it persist?); who is @CodeQuillClaim;
  is there a standalone product beyond the ENS prize integration.

### 2. DIVE — verifiable settlement for prediction markets  ·  fit: **HIGH**  ·  stage: weekend-build
- **What:** "AI swarm engine verifying real-world truth for prediction markets and autonomous on-chain
  settlement" — a multi-agent oracle that resolves disagreement before writing a settlement.
- **Thesis hit:** spans three themes — `agent_control_planes` (*settlement · verifiable*),
  `ai_x_crypto` (*autonomous · onchain agent*), `defi_infra` (*prediction market*).
- **Open question:** where's the non-incentivised demand — is swarm-oracle better than weighted feeds?
- **Verify-next:** repo persistence; 4-person team (@derek2403, @avoisavo, @cedricctf11a,
  @ilovetofupeach) — any prior shipping history (team signal).

### 3. Corpus — autonomous "agent corp" for products  ·  fit: **MED-HIGH**  ·  stage: weekend-build
- **What:** "Turn any product into an autonomous AI agent corp that runs GTM, trades, and earns" —
  composable bots sharing protocol-level wallets + on-chain reputation.
- **Thesis hit:** `ai_x_crypto` (weight 0.9 — *agentic · autonomous · trades*), touches `defi_infra`
  (*treasury*).
- **Open question (the important one):** does this *need* crypto, or is it a wrapper a frontier lab
  ships natively? More app than control-plane — rank below ENShell/DIVE until that's answered.
- **Verify-next:** is there durable usage, or is it a demo?

*(Also on-slate, lower fit: **VEIL VPN** — verifiable "no-logs" VPN via ZK attestations; hits
`crypto_infra` *verifiable · zero-knowledge* but it's DePIN/privacy, off the agent core.)*

---

## Thesis validation — the category is already minting rounds

**Nava** — raised **$8.3M seed** (Apr 2026), **co-led by Polychain + Archetype** — is building the exact
control-plane thesis: keep AI financial agents from "going off the rails," giving institutions "clarity
of **intent vs. execution**." That phrase *is* the thesis (`intent · settlement · recourse · guardrail`).

**Why this matters for sourcing:** Nava is already funded by top crypto funds → **past pre-seed, not an
opportunity** — it's proof the thesis catches winners. The lesson: the durable signal is the *category*
(agent guardrails / intent-vs-execution), and the edge is catching the **next ENShell/DIVE before the
Nava-style round**. Standards confirming the wave: x402 (~69k agents, $50M+ settled by Apr 2026),
EIP-8004, Google's AP2 intent/cart mandates, Trust Wallet Agent Kit.

---

## How to reproduce this in the app (live, free tier)

1. **OSS slice now** — your GitHub + Groq keys already work:
   `PYTHONPATH=src python -m signalfund --limit 50`
   → ranks trending GitHub repos against the thesis; review `out/digest.md` / the web UI, generate memos
   on the top on-thesis ones. (The earlier live run already surfaced real repos this way.)
2. **Hackathon slice** — feed the finalist repos in as seeds so `pre_public` + `code_health` score them
   (ENShell, DIVE, Corpus). The `pre_public` source is built to recognise ETHGlobal persistence.
3. **Curate ruthlessly** — GitHub trending is noisy (awesome-lists, wrappers). Keep only: on-thesis +
   real team + commits that *kept going*. The top score is a triage flag, not a verdict.

## Honest caveat (consistent with the Phase-0 backtest)
Public sourcing reliably catches the **OSS / hackathon / research** slice. The actual pre-seed *equity*
rounds — like Nava — are relationship-sourced and have near-zero public footprint at the time of the
deal. So this shortlist is a **top-of-funnel radar**, strongest as an input to the synthesis/memo side,
not a replacement for the partners' network.

---

### Sources
- ETHGlobal Cannes 2026 finalists — crypto.news, 2026-04-06
- Nava $8.3M seed (Polychain, Archetype) — Fortune, 2026-04-14
- x402 / agent-payments scale, EIP-8004, Google AP2 — MEXC, beincrypto, Para, eco.com (2026)
