# Sourcing Playbook

### How a top crypto fund finds early deals — and where Signal automates the data half

**The mindset.** You don't find deals one at a time; you build a system that surfaces the right ones and lets you reach them first. Sourcing is downstream of a thesis, and the best pre-seed deals are relationship-sourced *before* any public signal exists. A data radar doesn't replace the network — it's leverage: it stops you missing things, and it tells you *who to reach out to early*.

---

## The funnel — six moves

1. **Thesis first, not company first.** Market-map a category you have conviction in (stablecoin rails, agent-to-agent payments, ZK coprocessors, prediction-market infra, DePIN). Hunt the gap you already believe in.
2. **Channels, ranked by edge:** warm network / referrals → proactive outbound (reach founders *before* they raise) → programs (CSX, ETHGlobal, EF/Optimism grants, university clubs) → inbound/brand (high volume, low gem-rate; a filtering problem).
3. **Run a data radar** of hard-to-fake, reputation-weighted signals (below). Raw counts are noise.
4. **Weekly funnel:** scan radar + inbound → triage against theses → deep-dive the top few (team, tech, traction, token/market) → reach out early → bring 1–2 to partners → watchlist the rest and keep monitoring.
5. **Sell the platform to win.** At the top, the constraint is *winning* a competitive deal, not finding it — lead with capital, brand, operating team (recruiting, GTM, policy/regulatory), and research depth from first contact.
6. **Keep a human in the loop.** The radar triages; a partner decides. Be early *and patient* on a name.

---

## The radar → where each signal plugs into Signal

| Signal (reputation-weighted) | What it front-runs | Where it lives in Signal | Build / Buy |
|---|---|---|---|
| **Commit-velocity acceleration + contributor Gini < 0.30** | Series A within ~60 days (~3.4× lift) | `code_health` sub-score (extends `sources/github_velocity.py`) | **Build** (free) |
| **Farcaster smart-follower convergence + OpenRank** | imminent raise / credentialed founder | `social` source (Neynar + OpenRank) | **Build** |
| **X smart-follower convergence** (≥2–3 credible follows in a window) | undisclosed diligence by other funds | `social` source (Sorsa / Kaito) | Buy |
| **Stablecoin net inflows + "real" TVL** (revenue − incentives) | chain/protocol traction, pre-token | `onchain` source (DefiLlama / Blockscout) | **Build** |
| **Founder exits / repeat-founder / talent outflow** (DeepMind/OpenAI/top protocols → stealth) | credentialed team, 6–12 months early | `team` source (Harmonic) | Buy |
| **Grants (EF/Optimism) · hackathon wins · research (arXiv/IACR) · domain/incorporation filings** | ecosystem-vetted team, pre-equity | `pre_public` source (or Evertrace) | Buy |

---

## The one rule that makes the radar work

Reputation-weight every interaction (so sybils self-cancel), prefer "expensive" hard-to-fake actions over cheap ones, gate on account age, and score *ratios, not totals*. That's the difference between a radar that finds real teams and a dashboard that gets farmed.

**Bottom line:** Signal already automates the systematic half of this playbook — thesis-encoded scoring, a reputation-weighted radar, and a triage funnel. The network half (warm intros, reaching out early, winning the deal) stays human. The fund that wins runs both.

*See `docs/Sourcing_Signals_Research.md` for the full signal research (capture tools, gameability, ~70 sources) and `CLAUDE.md` → "Signals to add" for the build order.*
