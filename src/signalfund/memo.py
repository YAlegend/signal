"""Memo agent — turn a company into a source-cited investment memo.

Offline (no key): a structured, templated memo from the deterministic scorer + thesis.
Live (ANTHROPIC_API_KEY set): a frontier-model memo in the fund's voice, with every
factual claim verified against the provided sources (hallucinated citations dropped).

    PYTHONPATH=src python -m signalfund.memo --demo
    PYTHONPATH=src python -m signalfund.memo --company "Acme" --url https://acme.xyz \
        --summary "agent permission layer ..." --tags "ai agent,permission,policy"
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import re

import yaml

from . import env, llm, scoring
from .models import Candidate

ROOT = pathlib.Path(__file__).resolve().parents[2]

_LABELS = {}  # theme name -> (label, open_question), filled from thesis


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "company"


def _band(score: float) -> str:
    return "Strong" if score >= 70 else "Moderate" if score >= 45 else "Watch"


def _heuristic_memo(c: Candidate, sc, thesis: dict) -> str:
    by_name = {t["name"]: t for t in thesis.get("themes", [])}
    ss = sc.subscores or {}
    date = datetime.date.today().isoformat()
    lines = [
        f"# Investment Memo — {c.name}",
        f"*Generated {date} · thesis-fit **{sc.score}/100** ({_band(sc.score)}) · "
        f"source: {c.source}*",
        "",
        f"**One-liner.** {c.summary or '—'}",
        "",
        "## Thesis fit",
        sc.thesis_fit,
        "",
        f"Sub-scores: fit {ss.get('fit','?')} · traction +{ss.get('traction_bonus',0)} · "
        f"credibility {ss.get('credibility_adj',0):+g}.",
        "",
        "## Why it maps to the thesis",
    ]
    if sc.matched_themes:
        for name in sc.matched_themes:
            t = by_name.get(name, {})
            lines.append(f"- **{t.get('label', name)}** — matched on the thesis keywords for this theme.")
    else:
        lines.append("- No clear thesis-theme match from the available signal.")
    lines += ["", "## Signal / traction", c.signal_metric or "No public traction signal captured yet.", ""]

    lines.append("## Risks & open questions")
    qs = [by_name.get(n, {}).get("open_question") for n in sc.matched_themes]
    qs = [q for q in qs if q]
    if not qs:
        qs = ["Is the problem acute enough, and is this team the one to win it?"]
    for q in qs[:4]:
        lines.append(f"- {q}")
    for r in getattr(sc, "risks", []):          # soft/informational (e.g. "stopped shipping")
        lines.append(f"- {r}")
    for f in sc.flags:                          # hard anti-signals
        lines.append(f"- ⚠️ {f}")
    lines += ["", "## Sources"]
    for u in (sc.citations or [c.url]):
        if u:
            lines.append(f"- {u}")
    lines += ["", "---",
              "*Heuristic memo (offline). Set `ANTHROPIC_API_KEY` for a frontier-model memo "
              "with synthesised analysis.*"]
    return "\n".join(lines)


_SYS = ("You are a sharp crypto-VC analyst writing a pre-seed investment memo for a thesis-driven "
        "fund whose thesis is control planes / trust infrastructure for agent-native crypto. Be "
        "concise and skeptical. EVERY factual claim must be supported by the provided sources — do "
        "not invent facts, metrics, or URLs. Output clean markdown with these sections: One-liner, "
        "Thesis fit, Why it maps to the thesis, Signal/traction, Risks & open questions, Sources.")


def _llm_memo(c: Candidate, sc, thesis: dict, sources: list, research: str = "") -> str | None:
    research_block = ""
    if research:
        research_block = (
            "EXTERNAL RESEARCH CONTEXT (per Messari research — attribute it as such, do NOT present "
            "as our own analysis; use ONLY to pressure-test the open question):\n"
            f"{research}\n\n")
    prompt = (
        f"THESIS:\n{thesis.get('thesis_summary','')}\n\n"
        f"COMPANY:\nname: {c.name}\nsummary: {c.summary}\ntags: {', '.join(c.tags)}\n"
        f"signal: {c.signal_metric}\nthesis-fit score (our scorer): {sc.score}/100\n"
        f"risks/notes to address in Risks & open questions (do not let these dominate the verdict): "
        f"{'; '.join(str(r) for r in getattr(sc, 'risks', [])) or 'none flagged'}\n"
        f"{research_block}"
        f"PROVIDED SOURCES (cite only these): {sources}\n\n"
        "Write the memo now. If you used the external research context, attribute it to Messari in "
        "the Risks & open questions section. End with a Sources section listing only the provided URLs."
    )
    try:
        memo = llm.synthesize(prompt, system=_SYS, max_tokens=1100)
    except Exception as e:
        print(f"[memo] frontier model unavailable ({type(e).__name__}); using heuristic memo")
        return None
    # verify any URLs the model emitted are from the provided set
    used = re.findall(r"https?://[^\s)\]]+", memo)
    bad = [u for u in used if u not in set(sources)]
    if bad:
        memo += "\n\n> ⚠️ Citation check removed unverifiable link(s): " + ", ".join(bad)
        for u in bad:
            memo = memo.replace(u, "[unverified link removed]")
    return memo


def _memo_risks(c: Candidate, sc) -> list:
    """Honest informational risks for the memo's Risks section, deterministic (independent
    of which scorer ran): the scorer's SOFT risks minus internal noise, plus a persistence
    note derived from the verified pre_public 'kept shipping' fields."""
    risks = [r for r in getattr(sc, "risks", []) if not str(r).lower().startswith("llm_fallback")]
    raw = c.raw or {}
    if raw.get("hackathon_win") and raw.get("post_event_active") is False:
        note = "Hackathon project — no commits after the event (did not keep shipping)."
        if note not in risks:
            risks.append(note)
    # de-dup, preserve order
    seen, out = set(), []
    for r in risks:
        k = str(r).strip().lower()
        if k and k not in seen:
            seen.add(k); out.append(r)
    return out


def build_memo(c: Candidate, thesis: dict) -> str:
    env.load_env()
    scorer = scoring.get_scorer(thesis)
    sc = scorer.score(c)
    sc.risks = _memo_risks(c, sc)
    sources = [u for u in ([c.url] + list(c.raw.get("source_urls", []))) if u]
    research = ""
    if os.getenv("MESSARI_API_KEY"):   # Tier-2: attributed research context (no key -> "")
        try:
            from .sources import messari
            research = messari.research_context(c, thesis)
        except Exception:
            research = ""
    if llm.current_provider() != "heuristic":   # any configured LLM provider (frontier/hosted/local)
        memo = _llm_memo(c, sc, thesis, sources, research=research)
        if memo:
            return memo
    return _heuristic_memo(c, sc, thesis)


def _load_thesis() -> dict:
    return yaml.safe_load((ROOT / "config" / "thesis.yaml").read_text(encoding="utf-8"))


def main():
    p = argparse.ArgumentParser(description="Signal — Memo agent")
    p.add_argument("--demo", action="store_true", help="memo the top bundled fixture company")
    p.add_argument("--company", help="company name")
    p.add_argument("--url", default="", help="primary source URL")
    p.add_argument("--summary", default="", help="one-line description")
    p.add_argument("--tags", default="", help="comma-separated tags")
    p.add_argument("--out", default="out/memos", help="output directory")
    args = p.parse_args()

    thesis = _load_thesis()
    if args.demo or not args.company:
        fixtures = json.loads((ROOT / "data" / "fixtures" / "sample_candidates.json")
                              .read_text(encoding="utf-8"))
        c = Candidate(**fixtures[0])  # mandate-labs — the strongest fit
        print(f"[memo] demo mode — writing a memo for {c.name}")
    else:
        c = Candidate(name=args.company, source="manual", url=args.url, summary=args.summary,
                      tags=[t.strip() for t in args.tags.split(",") if t.strip()])

    memo = build_memo(c, thesis)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{_slug(c.name)}.md"
    path.write_text(memo, encoding="utf-8")
    print(f"[memo] wrote {path}")


if __name__ == "__main__":
    main()
