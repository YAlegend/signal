"""Thesis-fit scoring.

The score is a *weighted blend*, not an additive sum. (Additive-then-clamp used to
saturate every strong deal at 100, so the best companies stopped ranking against each
other.) Quality signals corroborate a good thesis fit; they don't stack onto it:

    signal_strength = 100 * (traction + code_health + onchain + team + social + pre_public)
                            / (sum of their caps)                      # 0..100, missing -> 0
    composite = clamp(0..100,
                      FIT_WEIGHT    * thesis_fit          # 0..100, the DOMINANT term (~60%)
                    + SIGNAL_WEIGHT * signal_strength      # 0..100, corroboration   (~40%)
                    + credibility_adj )                    # anti-gaming, applied AFTER the blend

  - thesis_fit       0-100   "is it on-thesis" (keyword match, or LLM) — dominant.
  - signal_strength  0-100   the quality signals collapsed into one corroboration score.
                             Absent data contributes 0, so missing signals never *penalise*
                             a strong-fit company — they just don't lift it.
  - credibility_adj  -60..+5  penalise anti-signals / buzzword stuffing. Applied after the
                             blend so an anti-signal can still screen a deal down to ~0.

The fit/signal split is FIT_WEIGHT / SIGNAL_WEIGHT (DEFAULT_COMPOSITE_WEIGHTS), overridable
per-fund via thesis.yaml `composite_weights:`. Per-signal caps are tunable via
`signal_weights:`. Every sub-score (incl. signal_strength) is exposed so a human sees *why*.

Keyword matching is word-boundary aware (so 'defi' no longer matches 'defined').

HeuristicScorer  — deterministic, offline. Powers demo mode and the no-LLM fallback.
LLMScorer        — frontier model for thesis_fit, same code-driven signals/credibility.
get_scorer()     — auto-selects based on which models are configured.
"""
from __future__ import annotations

import math
import re

from .models import Candidate, ScoredCandidate
from . import llm


# ---- shared signal helpers -------------------------------------------------

def _word_hit(kw: str, text: str, tokens: set) -> bool:
    """Word-boundary aware match. Multi-word / hyphenated keywords match as a
    phrase substring; single words match a token (with light pluralisation),
    so 'defi' matches 'DeFi' but not 'defined'."""
    if " " in kw or "-" in kw:
        return kw in text
    return any(
        tok == kw or tok == kw + "s" or tok == kw + "es"
        or (tok.startswith(kw) and len(tok) - len(kw) <= 2)
        for tok in tokens
    )


def match_themes(thesis: dict, text: str, tokens: set):
    matched, labels, questions, raw = [], [], [], 0.0
    for t in thesis.get("themes", []):
        hits = [k for k in t.get("keywords", []) if _word_hit(k, text, tokens)]
        if hits:
            matched.append(t["name"])
            labels.append(t.get("label", t["name"]))
            if t.get("open_question"):
                questions.append(t["open_question"])
            raw += t.get("weight", 0) * min(len(hits), 3) / 3.0
    return matched, labels, questions, raw


def anti_flags(thesis: dict, text: str, tokens: set) -> list:
    flags = []
    for k in thesis.get("anti_signals", {}).get("keywords", []):
        if _word_hit(k, text, tokens):
            flags.append(f"anti-signal: {k}")
    return flags


def traction_score(c: Candidate):
    """0-100 from star velocity, log-scaled so hype spikes have diminishing
    returns (612/day and 95/day end up close, not 6x apart)."""
    v = c.raw.get("velocity_per_day")
    if isinstance(v, (int, float)) and v > 0:
        return round(min(100.0, 30 * math.log10(1 + v)), 1)
    return None


# Flags are split into HARD anti-signals (real screen-out: scams / off-thesis noise) and
# SOFT informational risks (early-stage, hackathon, no recent commits, unconfirmed repo,
# small team). Only HARD flags hit credibility — penalising SOFT ones double-counts what
# pre_public/code_health already measure and wrongly sinks good-fit, *unproven* leads
# (a weak/absent signal must contribute 0, never penalise). See docs/SIGNALS_BUILD_SPEC.md.
_HARD_FLAG_WORDS = ("anti-signal", "scam", "fraud", "misrepresent", "rug", "ponzi",
                    "honeypot", "phishing", "off-thesis", "off thesis", "fake token")


def classify_flags(flags):
    """(hard, soft) split. HARD = a thesis anti-signal match ('anti-signal: …') or an LLM
    flag explicitly about scam / misrepresentation / off-thesis. SOFT = everything else
    (informational risk). Deduped, order-preserving."""
    hard, soft, seen = [], [], set()
    for f in (flags or []):
        key = str(f).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        (hard if any(w in key for w in _HARD_FLAG_WORDS) else soft).append(f)
    return hard, soft


# Tier-2 Messari (premium): a curated tier-1 lead-investor list (corroboration is reputation-
# weighted, never raw counts) + the raise size past which a candidate is "past pre-seed".
_MESSARI_TIER1_INVESTORS = (
    "a16z", "andreessen", "paradigm", "polychain", "sequoia", "archetype", "dragonfly",
    "multicoin", "variant", "pantera", "union square", "founders fund", "coinbase ventures",
    "binance labs", "framework", "electric capital", "standard crypto", "haun",
)
_MESSARI_LATE_RAISE_USD = 25_000_000.0  # >= this => past pre-seed/seed -> stage-gate down-rank


def messari_adj(thesis: dict, c: Candidate):
    """Tier-2 Messari funding/stage consumed via EXISTING mechanics (no new sub-score):
      * STAGE GATE (hard, legitimate — distinct from SOFT flags): a late round (a
        stage_preference 'avoid' match, e.g. Series B/C+, or a raise >= _MESSARI_LATE_RAISE_USD)
        down-ranks — this is what correctly flags a Nava-style already-funded company.
      * CREDIBILITY corroboration: a named tier-1 LEAD investor adds a small reputation-weighted
        positive (capped, not raw counts).
    Returns (adj, stage_flags, notes). No messari data -> (0.0, [], [])."""
    m = (c.raw or {}).get("messari")
    if not isinstance(m, dict):
        return 0.0, [], []
    funding = m.get("funding") or {}
    adj, flags, notes = 0.0, [], []
    avoid = [a.lower() for a in ((thesis or {}).get("stage_preference", {}).get("avoid") or [])]
    stage = str(funding.get("stage") or "").lower()
    raised = funding.get("total_raised_usd")
    late = (bool(stage) and any(a in stage for a in avoid)) or \
           (isinstance(raised, (int, float)) and raised >= _MESSARI_LATE_RAISE_USD)
    if late:
        adj -= 40.0
        why = funding.get("stage") or (f"${raised / 1e6:.0f}M raised"
                                       if isinstance(raised, (int, float)) else "late stage")
        flags.append(f"stage gate: past pre-seed ({why}) — off the fund's stage preference")
    leads = funding.get("lead_investors") or []
    tier1 = sorted({str(l) for l in leads if any(t in str(l).lower() for t in _MESSARI_TIER1_INVESTORS)})
    if tier1:
        adj += min(6.0, 3.0 * len(tier1))   # reputation-weighted, capped — not raw counts
        notes.append(f"Tier-1 lead investor(s): {', '.join(tier1[:3])} (Messari)")
    return round(adj, 1), flags, notes


def credibility_adj(c: Candidate, matched: list, hard_flags: list):
    """Anti-gaming. Only HARD anti-signals levy the strong screen-out penalty; buzzword
    stuffing (a thin description with many theme hits) still docks. With no hard flag,
    credibility cannot pull a good-fit candidate below its fit floor — it only adds the +5
    substance bonus (a real description avoids the thin-description penalty)."""
    adj, notes = 0.0, []
    summary = c.summary or ""
    if hard_flags:
        adj -= 60.0
        notes.append("anti-signal")
    if len(summary) < 25 and len(matched) >= 2:
        adj -= 45.0
        notes.append("thin description vs. many theme matches")  # buzzword stuffing
    elif len(summary) >= 80:
        adj += 5.0
        notes.append("substantive description")
    return adj, notes


TRACTION_CAP = 15.0  # max traction_bonus; part of the signal-strength denominator
# Blend weights: fit stays dominant. Overridable per-fund via thesis `composite_weights:`.
DEFAULT_COMPOSITE_WEIGHTS = {"fit": 0.60, "signal": 0.40}


def _signal_strength(tr_bonus: float, bonuses: dict, signal_caps: dict) -> float:
    """Collapse traction + the five quality bonuses into one 0..100 "how corroborated is
    this" score, normalised against the max attainable signal points. Missing data
    contributes 0 (never negative), so absence can't penalise a strong-fit company."""
    max_signal = TRACTION_CAP + sum(signal_caps.values())
    points = tr_bonus + sum(bonuses.values())
    return 100.0 * points / max_signal if max_signal > 0 else 0.0


def composite(fit: float, traction, cred_adj: float,
              bonuses: dict = None, signal_caps: dict = None, blend: dict = None):
    """Weighted blend (NOT additive-then-clamp): FIT_WEIGHT*fit + SIGNAL_WEIGHT*
    signal_strength, then + credibility_adj, then clamp 0..100. fit dominates; the quality
    signals corroborate. Returns (total, traction_bonus, signal_strength)."""
    tr_bonus = 0.0 if traction is None else min(TRACTION_CAP, traction * 0.15)
    bonuses = bonuses or {}
    caps = signal_caps or DEFAULT_SIGNAL_WEIGHTS
    blend = blend or DEFAULT_COMPOSITE_WEIGHTS
    strength = _signal_strength(tr_bonus, bonuses, caps)
    blended = blend["fit"] * fit + blend["signal"] * strength
    total = round(max(0.0, min(100.0, blended + cred_adj)), 1)
    return total, round(tr_bonus, 1), round(strength, 1)


def resolve_signal_caps(weights: dict) -> dict:
    """The effective per-signal caps: built-in defaults with any thesis `signal_weights`
    overrides applied (used as the signal-strength denominator)."""
    caps = dict(DEFAULT_SIGNAL_WEIGHTS)
    for k, v in (weights or {}).items():
        if k in caps and isinstance(v, (int, float)) and v >= 0:
            caps[k] = float(v)
    return caps


def resolve_blend(thesis: dict) -> dict:
    """fit/signal blend weights from thesis `composite_weights:`, normalised to sum 1 (so
    `{fit: 60, signal: 40}` and `{fit: 0.6, signal: 0.4}` mean the same). Falls back to
    the default 60/40 on missing/invalid input."""
    cw = (thesis or {}).get("composite_weights") or {}
    fw, sw = cw.get("fit", DEFAULT_COMPOSITE_WEIGHTS["fit"]), cw.get("signal", DEFAULT_COMPOSITE_WEIGHTS["signal"])
    if not (isinstance(fw, (int, float)) and isinstance(sw, (int, float))) or (fw + sw) <= 0:
        return dict(DEFAULT_COMPOSITE_WEIGHTS)
    return {"fit": fw / (fw + sw), "signal": sw / (fw + sw)}


# ---- additive signal sub-scores (docs/SIGNALS_BUILD_SPEC.md) ----------------
# Each reads fields a signal *source* wrote onto Candidate.raw during enrichment.
# Absent data -> 0.0 (graceful absence, exactly like traction_bonus). Reputation-
# weighted / ratio-based, never raw counts. New signals slot into signal_bonuses().

def code_health_bonus(raw: dict) -> float:
    """0..15. Rewards commit-velocity *acceleration* AND contributor diversity,
    multiplicatively — a single-hero-dev repo scores ~0 even at high velocity.
    Needs raw['commit_accel'] and >=2 contributors (else 0)."""
    accel = raw.get("commit_accel")
    gini = raw.get("contributor_gini")
    n = raw.get("contributors", 0) or 0
    if accel is None or n < 2:
        return 0.0
    accel_pts = min(1.0, max(0.0, accel - 1.0))          # 0 at flat, 1.0 at >=2x
    if gini is None:
        gini_pts = 0.2
    elif gini < 0.30:
        gini_pts = 1.0
    elif gini < 0.45:
        gini_pts = 0.5
    else:
        gini_pts = 0.2
    return round(15.0 * accel_pts * gini_pts, 1)


def onchain_bonus(raw: dict) -> float:
    """0..12. Rewards REAL on-chain demand, not mercenary capital: external stablecoin inflow,
    non-incentivised TVL that *sticks* (retention test), and non-whale-concentrated holders.
    Absent data -> 0; incentive-only TVL (retention < 0.5) earns nothing for its TVL.

    Tier-2 AUGMENT (behind `if nansen data`): when raw['nansen'] is present (premium), PREFER
    Nansen Smart Money net inflow + smart-money holder *share* — higher-signal than raw
    stablecoin flow / holder Gini. No Nansen data -> the free DefiLlama/Blockscout path below
    runs exactly as before (no creds => 0 effect)."""
    nansen = raw.get("nansen") if isinstance(raw.get("nansen"), dict) else None
    inflow = raw.get("stablecoin_inflow_30d")
    real_tvl = raw.get("real_tvl")
    retention = raw.get("tvl_retention")
    holder_gini = raw.get("holder_gini")
    pts = 0.0

    # INFLOW — prefer Nansen smart-money net inflow (reputation-weighted) over raw stablecoin flow
    sm_inflow = nansen.get("smart_money_inflow_30d") if nansen else None
    if isinstance(sm_inflow, (int, float)) and sm_inflow > 0:
        pts += min(7.0, 2.2 * math.log10(1 + sm_inflow))   # richer cap: smart money is higher-signal
    elif isinstance(inflow, (int, float)) and inflow > 0:
        pts += min(6.0, 2.0 * math.log10(1 + inflow))

    # sticky, non-incentivised TVL (free path, unchanged)
    if (isinstance(real_tvl, (int, float)) and isinstance(retention, (int, float))
            and real_tvl > 0 and retention > 0.5):
        pts += 4.0

    # HOLDER QUALITY — prefer Nansen smart-money holder share; else the free whale-Gini check
    sm_share = nansen.get("smart_money_holder_share") if nansen else None
    if isinstance(sm_share, (int, float)) and sm_share > 0:
        pts += min(3.0, 6.0 * sm_share)        # 50% smart-money held -> +3 (capped)
    elif isinstance(holder_gini, (int, float)) and holder_gini < 0.9:
        pts += 2.0

    return round(min(12.0, pts), 1)


def _team_github_pts(raw: dict) -> float:
    """FREE GitHub-derived team points (<=9): technical-CEO proxy, frontier-lab alum, >=2 founders."""
    pts = 0.0
    if raw.get("technical_ceo"):
        pts += 4.0
    if raw.get("frontier_lab_alum"):
        pts += 3.0
    if (raw.get("team_size") or 0) >= 2:
        pts += 2.0
    return pts


def _team_harmonic_pts(raw: dict) -> float:
    """PREMIUM Harmonic-derived team points (<=13): prior exits (scaled by size) + repeat
    same-domain founder. Trust EVENTS (exits / M&A) over self-asserted titles."""
    pts = 0.0
    if raw.get("prior_exit"):
        size = raw.get("exit_size_usd")
        # +8 at a >=$100M ($1e8) exit; half-credit for a known exit of unknown size
        scale = min(1.0, math.log10(size) / 8.0) if isinstance(size, (int, float)) and size > 1 else 0.5
        pts += 8.0 * max(0.0, scale)
    if (raw.get("repeat_founder_count") or 0) >= 2 and raw.get("same_domain"):
        pts += 5.0
    return pts


def team_bonus(raw: dict, parts=None) -> float:
    """0..20. The founder signal (highest published predictive value), DUAL-TIER and
    independently toggleable:
      • GitHub (free): technical-CEO proxy, frontier-lab alum, team size       (<=9)
      • Harmonic (premium): prior exits scaled by size, repeat same-domain founder (<=13)
    `parts` selects which tiers count — a subset of {'github', 'harmonic'}; None = both.
    No data -> 0."""
    total = 0.0
    if parts is None or "github" in parts:
        total += _team_github_pts(raw)
    if parts is None or "harmonic" in parts:
        total += _team_harmonic_pts(raw)
    return round(min(20.0, total), 1)


def social_bonus(raw: dict) -> float:
    """0..12. Smart-follower convergence + OpenRank reputation, *gated* by the Neynar
    quality score and account age — all sybil-resistant by design, so cheap follows
    don't move it. neynar_score < 0.55 cuts the result to 40%; age < 30d halves it.
    No data -> 0."""
    sf = raw.get("smart_followers")
    openrank = raw.get("openrank_pct")          # 0..1 percentile (1.0 = top of graph)
    neynar = raw.get("neynar_score")            # 0..1 Neynar user quality
    age = raw.get("account_age_days")
    if not isinstance(sf, (int, float)) and not isinstance(openrank, (int, float)):
        return 0.0
    pts = 0.0
    if isinstance(sf, (int, float)) and sf >= 2:
        pts += min(8.0, 2.4 * sf)               # 2 credible follows -> +4.8, >=4 -> +8
    if isinstance(openrank, (int, float)) and openrank >= 0.90:   # top decile only
        pts += min(4.0, 40.0 * (openrank - 0.90))                # 0 at .90 -> +4 at 1.0
    if isinstance(neynar, (int, float)) and neynar < 0.55:
        pts *= 0.4
    if isinstance(age, (int, float)) and age < 30:
        pts *= 0.5
    return round(min(12.0, pts), 1)


def pre_public_bonus(raw: dict) -> float:
    """0..15. Pre-public proof that code/social miss: retroactive grants (>> proposal
    grants), hackathon wins that KEPT BUILDING, research with an affiliation exit,
    recent formation. Guardrail: a hackathon counts only with post_event_active.
    No data -> 0."""
    pts = 0.0
    if raw.get("retro_grant"):           # retroactive public-goods grant — earned, not pitched
        pts += 6.0
    elif raw.get("grant_program"):       # a (forward) proposal grant — weaker signal
        pts += 3.0
    if raw.get("hackathon_win") and raw.get("post_event_active"):
        pts += 4.0
    if raw.get("research_exit"):         # published research -> company (affiliation exit)
        pts += 3.0
    incorp = raw.get("incorp_days")
    if isinstance(incorp, (int, float)) and 0 <= incorp <= 365:   # recently formed
        pts += 2.0
    return round(min(15.0, pts), 1)


# Built-in cap (max points) for each additive signal. thesis.yaml `signal_weights:`
# overrides any of these without code changes; an absent key keeps its default.
DEFAULT_SIGNAL_WEIGHTS = {"code_health": 15.0, "onchain": 12.0, "team": 20.0,
                          "social": 12.0, "pre_public": 15.0}


def signal_bonuses(c: Candidate, weights: dict = None, enabled=None) -> dict:
    """Every additive signal sub-score, computed from c.raw — the full multi-signal
    composite (code/onchain/team/social/pre_public) on top of fit/traction/credibility.

    Each base bonus is in [0, default_cap]; `weights` (from thesis `signal_weights`)
    linearly rescales a signal to its configured cap, so partners retune the composite
    from config alone. `enabled` (a set/list of signal names) lets the *user* turn signals
    off: any signal not in it is zeroed — identical to graceful absence (contributes 0,
    never penalises). None means all signals on."""
    raw = c.raw or {}
    # `team` is dual-tier: the user toggles its GitHub (free) and Harmonic (premium) tiers
    # independently via "team_github" / "team_harmonic" in `enabled`. None -> both tiers.
    if enabled is None:
        team_parts = None
    else:
        team_parts = set()
        if "team_github" in enabled:
            team_parts.add("github")
        if "team_harmonic" in enabled:
            team_parts.add("harmonic")
    base = {"code_health": code_health_bonus(raw),
            "onchain": onchain_bonus(raw),
            "team": team_bonus(raw, team_parts),
            "social": social_bonus(raw),
            "pre_public": pre_public_bonus(raw)}
    if weights:
        for k, v in base.items():
            cap, default = weights.get(k), DEFAULT_SIGNAL_WEIGHTS[k]
            if isinstance(cap, (int, float)) and cap >= 0 and default:
                base[k] = round(v * cap / default, 1)
    if enabled is not None:  # team handled above; zero the other signals when off
        for k in ("code_health", "onchain", "social", "pre_public"):
            if k not in enabled:
                base[k] = 0.0
    return base


def verify_citations(cited, allowed) -> list:
    """Drop any cited URL not in the provided source set. Verifiability over trust."""
    allowed_set = {a for a in allowed if a}
    return [c for c in (cited or []) if c in allowed_set]


# ---- scorers ---------------------------------------------------------------

class HeuristicScorer:
    def __init__(self, thesis: dict, enabled_signals=None):
        self.t = thesis or {}
        weights = sorted((t.get("weight", 0) for t in self.t.get("themes", [])), reverse=True)
        self.ref = sum(weights[:2]) or 1.0  # strong match on the top 2 themes ~= full marks
        self.signal_weights = self.t.get("signal_weights") or {}  # tunable sub-score caps
        self.signal_caps = resolve_signal_caps(self.signal_weights)
        self.blend = resolve_blend(self.t)
        self.enabled_signals = enabled_signals  # None = all on; else user-selected set

    def score(self, c: Candidate) -> ScoredCandidate:
        text = f"{c.name} {c.summary} {' '.join(c.tags)}".lower()
        tokens = set(re.findall(r"[a-z0-9]+", text))

        matched, labels, questions, raw = match_themes(self.t, text, tokens)
        fit = round(min(100.0, 100.0 * raw / self.ref), 1)
        hard, soft = classify_flags(anti_flags(self.t, text, tokens))
        traction = traction_score(c)
        cred_adj, cred_notes = credibility_adj(c, matched, hard)
        m_adj, m_flags, m_notes = (messari_adj(self.t, c) if (c.raw or {}).get("messari")
                                   else (0.0, [], []))   # Tier-2 stage gate + investor corroboration
        cred_adj += m_adj
        bonuses = signal_bonuses(c, self.signal_weights, self.enabled_signals)
        total, tr_bonus, strength = composite(fit, traction, cred_adj,
                                              bonuses, self.signal_caps, self.blend)

        subscores = {"fit": fit, "traction": traction,
                     "traction_bonus": tr_bonus, "signal_strength": strength,
                     "credibility_adj": round(cred_adj, 1), **bonuses}
        rationale = self._rationale(c, labels, matched, questions, hard, total,
                                    subscores, cred_notes)
        return ScoredCandidate(candidate=c, score=total, thesis_fit=rationale,
                               matched_themes=matched,
                               citations=[c.url] if c.url else [],
                               flags=hard + m_flags, risks=soft + m_notes, subscores=subscores)

    @staticmethod
    def _rationale(c, labels, matched, questions, flags, score, subscores, cred_notes) -> str:
        if flags:
            return (f"Low fit ({score}/100). Triggers {', '.join(flags)} — noise, not a "
                    f"backable pre-seed team. Screen out.")
        if "thin description vs. many theme matches" in cred_notes:
            return (f"Low confidence ({score}/100). Hits theme keywords but with a thin "
                    f"description — possible buzzword stuffing; verify before triage.")
        if not labels:
            return (f"Weak fit ({score}/100). No clear overlap with the fund's themes from "
                    f"the available signal; revisit if more emerges.")
        band = "Strong" if score >= 70 else "Moderate" if score >= 45 else "Watch"
        if "agent_control_planes" in matched:
            tail = "the agent-native, control-plane positioning the fund backs"
        elif "ai_x_crypto" in matched:
            tail = "agent-native and squarely in the fund's strike zone"
        else:
            tail = "in the fund's wider strike zone, though off the core control-plane thesis"
        metric = f" Signal: {c.signal_metric}." if c.signal_metric else ""
        q = f" Open question: {questions[0]}" if questions else ""
        return f"{band} fit ({score}/100). Matches {', '.join(labels[:3])} — {tail}.{metric}{q}"


_SYS = ("You are a precise crypto-VC analyst for a thesis-driven pre-seed fund. "
        "Score how well a company fits the thesis (0-100). Be skeptical. Reward "
        "control-plane / trust-infra / agent-native crypto; penalise hype and "
        "undifferentiated wrappers. Only cite URLs from the provided sources. "
        "Respond with strict JSON.")


class LLMScorer:
    """Frontier model supplies thesis_fit; traction/credibility stay code-driven
    so the composite is comparable to the heuristic. Falls back on any error."""

    def __init__(self, thesis: dict, enabled_signals=None):
        self.t = thesis or {}
        self.fallback = HeuristicScorer(thesis, enabled_signals)
        self.signal_weights = self.t.get("signal_weights") or {}
        self.signal_caps = resolve_signal_caps(self.signal_weights)
        self.blend = resolve_blend(self.t)
        self.enabled_signals = enabled_signals

    def score(self, c: Candidate) -> ScoredCandidate:
        sources = [c.url] + list(c.raw.get("source_urls", []))
        themes = ", ".join(t.get("label", t["name"]) for t in self.t.get("themes", []))
        prompt = (
            f"THESIS:\n{self.t.get('thesis_summary', '')}\n\n"
            f"THEMES: {themes}\n\n"
            f"COMPANY:\nname: {c.name}\nsummary: {c.summary}\n"
            f"tags: {', '.join(c.tags)}\nsignal: {c.signal_metric}\n"
            f"sources: {sources}\n\n"
            "Return JSON with keys: score (0-100 integer thesis fit), thesis_fit (<=60 words), "
            "matched_themes (list), citations (list of provided source URLs), flags (list)."
        )
        try:
            data = llm.extract_json(llm.synthesize(prompt, system=_SYS, max_tokens=600))
        except Exception as e:  # network/parse/availability — degrade, don't crash
            sc = self.fallback.score(c)
            sc.risks = list(sc.risks) + [f"llm_fallback:{type(e).__name__}"]  # soft, never penalised
            return sc

        fit = round(float(data.get("score", 0)), 1)
        text = f"{c.name} {c.summary} {' '.join(c.tags)}".lower()
        tokens = set(re.findall(r"[a-z0-9]+", text))
        matched = list(data.get("matched_themes", [])) or match_themes(self.t, text, tokens)[0]
        # Combine LLM-reported flags with thesis anti-signal keyword matches, then split:
        # only HARD anti-signals hit credibility; SOFT/informational flags become `risks`.
        hard, soft = classify_flags(list(data.get("flags", [])) + anti_flags(self.t, text, tokens))
        traction = traction_score(c)
        cred_adj, _ = credibility_adj(c, matched, hard)
        m_adj, m_flags, m_notes = (messari_adj(self.t, c) if (c.raw or {}).get("messari")
                                   else (0.0, [], []))   # Tier-2 stage gate + investor corroboration
        cred_adj += m_adj
        bonuses = signal_bonuses(c, self.signal_weights, self.enabled_signals)
        total, tr_bonus, strength = composite(fit, traction, cred_adj,
                                              bonuses, self.signal_caps, self.blend)
        cites = verify_citations(data.get("citations", []), allowed=sources)
        subscores = {"fit": fit, "traction": traction,
                     "traction_bonus": tr_bonus, "signal_strength": strength,
                     "credibility_adj": round(cred_adj, 1), **bonuses}
        return ScoredCandidate(
            candidate=c, score=total,
            thesis_fit=str(data.get("thesis_fit", "")).strip(),
            matched_themes=matched,
            citations=cites or ([c.url] if c.url else []),
            flags=hard + m_flags, risks=soft + m_notes, subscores=subscores,
        )


def get_scorer(thesis: dict, prefer_llm: bool = True, enabled_signals=None):
    # LLMScorer when a provider resolves (any configured LLM, or the one chosen via
    # SIGNAL_LLM_PROVIDER); else — or when 'heuristic' is forced — the deterministic scorer.
    if prefer_llm and llm.current_provider() != "heuristic":
        return LLMScorer(thesis, enabled_signals)
    return HeuristicScorer(thesis, enabled_signals)
