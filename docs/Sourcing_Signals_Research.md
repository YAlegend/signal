# Sourcing Signals — Research Report

### What to add to Signal's scorer to spot early crypto/AI projects *before* they're obvious

Deep-research synthesis across five parallel streams — **code, team/founder, on-chain, social (Farcaster + X), and pre-public/web**. Each signal below is rated on what it measures, why it predicts success, how to capture it, and how gameable it is. The goal: turn Signal's single-signal scorer (star velocity) into a **triangulated, hard-to-game composite**.

---

## The one principle that runs through everything

Every category converged on the same rule: **raw counts are worthless; reputation-weighted, hard-to-fake actions are the signal.** Concretely:

1. **Weight every interaction by the *source's* credibility** — so sybil swarms self-cancel. OpenRank (EigenTrust) and Neynar are literally built this way; do the same for stars, follows, and holders.
2. **Prefer "expensive" actions** (a respected VC's follow, a shipped grant, a prior exit) over **cheap** ones (likes, raw members, stars).
3. **Gate on account age and cluster the funding graph** — discount <30–90-day accounts and wallets that share a funder (the sybil signature).
4. **Score ratios, not totals** — views/subscriber, earnings/TVL, contributor diversity, engagement-per-credible-account.
5. **Trust events over self-assertions** — exits, M&A, grants, commits, incorporations beat LinkedIn titles (~80% of profiles are inflated).

---

## Tier 1 — highest-value signals to add (ranked)

| # | Signal | Why it's top-tier | Gameability |
|---|--------|-------------------|-------------|
| 1 | **Contributor-health code velocity** — 14-day commit *acceleration* + low contributor concentration (Gini < 0.30) | Only signal with published lift: meeting both ⇒ **3.4× more likely to raise a Series A within 60 days**; ~3–6 weeks of lead time. Upgrades our star-velocity. | Low–Med |
| 2 | **Smart-follower convergence** (Farcaster + X) — multiple *credible* VCs/founders follow the same young account in a short window | Front-runs undisclosed diligence; you can't buy a real a16z partner's follow. Hardest social signal to fake. | Low |
| 3 | **Prior-exit / repeat-founder**, weighted by exit size + same-domain match | Most robustly quantified team signal: ~**2× median exit**, repeat-founder success ~34% vs ~18% first-timers; 2nd-time peak, domain-match ~42% vs ~24%. | Low |
| 4 | **Ecosystem/protocol grants** (EF ESP, Optimism RetroPGF, Gitcoin) | Crypto-native pre-seed stamp; flags ecosystem-vetted teams **6–18 months** before an equity round. RetroPGF rewards *shipped* impact. | Low–Med |
| 5 | **Stablecoin net inflows** (chain/protocol) | Strongest market-independent on-chain leading indicator (a factor built on it showed **1.67 Sharpe, +73.8% alpha**); needs real dollars. | Low–Med |
| 6 | **Talent outflow from frontier labs** (DeepMind/OpenAI/Palantir → stealth) | Surfaces companies **6–12 months before** funding hits Crunchbase; the genuine sourcing-timing edge. | Med |
| 7 | **OpenRank / Neynar reputation** (Farcaster) as a weighting + filter | Reputation-weighted engagement that sybils can't inflate; queryable point-in-time (works for live *and* backtest). | Low–Med |
| 8 | **"Real" TVL** = Revenue − Incentives (earnings-net-of-emissions) | Cancels mercenary capital (avg LP dwell ~14.7 days); separates product-market fit from rented liquidity. | High→Med |

---

## By category

### A. Code / developer (sharpest, cheapest, already half-built)

| Signal | Capture | Gameability |
|---|---|---|
| Commit-velocity **acceleration** + contributor **Gini < 0.30** | GitHub REST `commit_activity` + contributors; compute yourself (our `github_velocity` source) | Low–Med (private repos invisible) |
| New **GitHub org creation** with no company yet | GitHub org/repo creation events | Med |
| **On-chain dev activity** — contract deploys, verified contracts | Blockscout/Etherscan, Dune, Electric Capital, Santiment "Development Activity" (strips non-code noise) | Low–Med |

### B. Team / founder (highest predictive value; mostly buy, don't build)

| Signal | Key evidence | Capture |
|---|---|---|
| **Prior exit / repeat founder** (× exit size, × same-domain) | ~2× median exit; serial ~34% vs ~18%; 2nd-time peak | Harmonic, PitchBook/Crunchbase people, Specter |
| **Normalized founder-factory pedigree** (DeepMind/OpenAI/Palantir per-alumnus, **not** raw ex-FAANG) | Raw FAANG flag is *negative/not robust* in a 4,323-co YC study; frontier-lab clusters carry the alpha | SignalFire Beacon, Specter, Harmonic + a weighted lookup table |
| **Talent outflow / senior inflow** (prestige-delta of hires) | Headcount lost predictive power post-2023; *quality* of recent hires is the signal | Aura, Specter Talent, Harmonic, People Data Labs |
| **Team size + complementary roles**; **technical CEO** | +21% capital per co-founder; 82% of $1B+ exits had ≥2 founders; 75% of top-5% exits had technical CEO | Crunchbase/Harmonic + title/GitHub inference |

### C. On-chain (crypto-native; some already wired via Blockscout)

| Signal | Capture | Gameability |
|---|---|---|
| **Stablecoin net inflows** (external USDC/USDT, not self-minted) | Artemis, DefiLlama, Allium | Low–Med |
| **Smart-money wallet inflows** (≥2 independent funds) | Nansen (Smart Money), Arkham (entity clustering) | Med |
| **Real TVL** (Earnings = Revenue − Incentives) + retention after incentives end | DefiLlama earnings view, Token Terminal | High→Med |
| **Holder distribution / quality** (top-10 %, Gini; smart-money holders) | Nansen, Arkham, Blockscout, Bitquery | Med (cluster sybils) |
| Active-address growth, DEX volume, testnet | Dune/Artemis/DefiLlama | **High** (sybil/wash — corroborate only) |

### D. Social — Farcaster (the crypto-native edge; best reputation infra)

| Signal | Capture | Gameability |
|---|---|---|
| **Smart/notable early followers** (reputation-weighted) | Neynar `fetchRelevantFollowers` + OpenRank weighting | Low |
| **OpenRank** reputation (engagement-weighted EigenTrust; mentions/replies weighted highest) | `graph.cast.k3l.io` (global + personalized, ~2h refresh) | Low–Med |
| **Neynar user-quality score** (filter; 0.55+ baseline) | On every Neynar user object | Low–Med (weekly lag) |
| Power-badge **transition**; channel-growth velocity; quality-weighted cast engagement | Neynar + Dune Farcaster tables (also for backtest reconstruction) | Med |

### E. Social — X/Twitter (heavily farmed; only graph-structural survives)

| Signal | Capture | Gameability |
|---|---|---|
| **Smart-follower convergence** (≥2–3 credible follows in a window) | Sorsa/TweetScout "VC Activity," Kaito Smart Followers | Low–Med |
| **Bot-ratio of the account** (a *disqualifier*) | Sorsa "Bot Followers," BotBuster (OSS); **not** Botometer (archival-only post-2023) | Low (arms race) |
| **Mindshare trend** (Kaito) — verified-account-weighted | Kaito API/Pro (note: gamified "Yaps" sunset Jan 2026) | Med |
| Engagement *quality* (credible-engager-weighted) | LunarCrush API v3 (spam/bot-filtered) | Med (raw → low if weighted) |
| Curated-list memberships (owner-weighted) | X API v2 list endpoints | Low–Med |

> X API moved to **pay-per-use (Feb 2026)** — third-party resellers (Sorsa ~"3× cheaper", LunarCrush, Kaito) are now cheaper than going direct.

### F. Pre-public / founder-detection + product (catches what code/social miss)

| Signal | Capture | Gameability |
|---|---|---|
| **Grants** (EF ESP, Optimism RetroPGF, Gitcoin) | Recipient lists; Open Source Observer; Evertrace Grants | Low–Med |
| **Hackathon wins + post-event persistence** (ETHGlobal) | ETHGlobal prize pages × 30–90d GitHub/domain follow-up | Med |
| **Accelerator cohorts** (a16z CSX, Alliance, YC, Orange DAO) | Program pages/X; partner follows | Low (timing decays) |
| **Research → founder** (arXiv, IACR ePrint) + **affiliation exit** | arXiv/IACR APIs + OpenAlex citations; Evertrace Research | Low (low recall) |
| **"Founding Engineer" job posts** at stealth cos | TheirStack, Crustdata, SignalsAPI | Med |
| **Domain / incorporation / trademark** filings | WhoisXML, OpenCorporates, USPTO | Low–High (varies) |
| **Web/app traction velocity** | Similarweb, Appfigures/Sensor Tower | Med–High |

---

## Build vs. buy

A purpose-built aggregator, **Evertrace** (used by 175–200+ funds), already fuses most *pre-public* signals (domains, registries, GitHub, grants, hackathons, research, patents, web) and exposes an API + MCP server. The pragmatic stack:

- **Build (cheap, differentiating):** contributor-health code velocity (we have the base), Farcaster reputation (Neynar + OpenRank), on-chain via Blockscout/DefiLlama/Dune.
- **Buy / integrate:** team/talent (Harmonic, Specter, Aura), X graph (Sorsa/Kaito), pre-public bundle (Evertrace), premium on-chain (Nansen/Artemis).

Our edge isn't raw data collection — it's **thesis-encoded scoring + synthesis** on top of these feeds.

---

## How this plugs into Signal (recommended roadmap)

Each becomes a new `Source` subclass and/or a new **sub-score** in the composite (extending `fit + traction + credibility`). Priority order by ROI:

1. **`code_health`** sub-score — add commit-acceleration + contributor-Gini to the existing GitHub path. *(High lift, free, builds on what we have.)*
2. **`team`** source — founder exits / repeat-founder / technical-CEO via Harmonic. *(Highest predictive value; fixes the relationship-sourced blind spot.)*
3. **`social`** source — Farcaster smart-follower + OpenRank (Neynar). *(Crypto-native, hard to game, backtest-able.)*
4. **`onchain`** source — stablecoin inflows + real-TVL via DefiLlama/Blockscout. *(Already half-wired.)*
5. **`pre_public`** source — grants + hackathons + research (or integrate Evertrace).

Keep the composite honest: every new signal is *reputation-weighted*, *ratio-based*, and *human-reviewed* — the scorer triages, a partner decides.

---

## Sources

**Code/dev:** [GitDealFlow methodology](https://signals.gitdealflow.com/methodology) · [SSRN panel](https://ssrn.com/abstract=6606558) · [Electric Capital Developer Report](https://www.developerreport.com/developer-report) · [Santiment Dev Activity](https://academy.santiment.net/metrics/development-activity/)
**Team/founder:** [Outcast billion-dollar founder study](https://outcastventures.com/essays/billion-dollar-founder-study/) · [SignalFire unicorn origins](https://www.signalfire.com/blog/unicorn-founder-origins-data-report) · [YC/arXiv founder regression](https://arxiv.org/html/2512.13755v1) · [OII team-composition (Nature)](https://www.nature.com/articles/s41598-023-41980-y) · [Super Founders](https://www.superfoundersbook.com/) · [Aura talent outflows](https://blog.getaura.ai/talent-outflows-and-workforce-movement)
**On-chain:** [Artemis stablecoin factor](https://research.artemisanalytics.com/p/crypto-factor-model-analysis-launching-ae0) · [DL News State of DeFi 2025](https://www.dlnews.com/research/internal/state-of-defi-2025/) · [Nansen Smart Money](https://nansen.ai/post/who-counts-as-smart-money-in-crypto-and-how-to-track-them) · [DefiLlama metrics](https://defillama.com/metrics) · [Dune wash-trade detection](https://dune.com/blog/a-a-wash-trading-detection-on-uniswap-v2-a-new-tool-for-investors-investigators)
**Farcaster:** [Neynar user score](https://docs.neynar.com/docs/neynar-user-quality-score) · [Neynar relevant followers](https://docs.neynar.com/nodejs-sdk/follow-apis/fetchRelevantFollowers) · [OpenRank Farcaster strategies](https://docs.openrank.com/integrations/farcaster/ranking-strategies-on-farcaster) · [Dune Farcaster power badge](https://docs.dune.com/data-catalog/community/farcaster/power_badge)
**X/Twitter:** [Sorsa/TweetScout API](https://api.sorsa.io/v2/docs/) · [Kaito / InfoFi overview](https://oakresearch.io/en/reports/protocols/kaito-complete-overview-first-attention-market) · [LunarCrush API v3](https://lunarcrush.com/products/lunarcrush-api/) · [BotBuster (arXiv)](https://arxiv.org/abs/2207.13658) · [Circleboom — track VC follows](https://circleboom.com/blog/how-to-track-a-crypto-accounts-new-follows-as-early-market-signals)
**Pre-public/web:** [Evertrace](https://www.evertrace.ai/) · [OpenCorporates API](https://api.opencorporates.com/documentation/API-Reference) · [EF ESP grants](https://esp.ethereum.foundation/applicants) · [ETHGlobal](https://ethglobal.com/) · [IACR ePrint](https://eprint.iacr.org/about.html) · [Crustdata stealth-founder guide](https://crustdata.com/blog/the-complete-guide-to-tracking-and-finding-stealth-startup-founders) · [Similarweb API](https://developers.similarweb.com/docs/similarweb-web-traffic-api)

*Synthesized from five parallel research agents (≈70 sources). Predictive-lift figures are from cited studies — treat as directional. Verify a signal's current API/pricing before building on it.*
