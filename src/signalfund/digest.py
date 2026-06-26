from __future__ import annotations

import datetime
import json
import pathlib
from typing import List

from .models import ScoredCandidate


def _short(url: str) -> str:
    return url.replace("https://", "").replace("http://", "").rstrip("/")[:48]


def _fired_signals(ss: dict) -> list:
    """The quality signals that actually contributed, for 'see why' transparency."""
    fired = []
    if ss.get("traction") is not None and ss.get("traction_bonus"):
        fired.append(f"traction {ss['traction_bonus']}")
    for k in ("code_health", "onchain", "team", "social", "pre_public"):
        if ss.get(k):
            fired.append(f"{k} {ss[k]}")
    return fired


def _breakdown(s) -> str:
    # Weighted blend (see scoring.composite): fit and signal_strength are blended, then
    # credibility applied — not summed. Show the blend, then which signals fired.
    ss = s.subscores or {}
    if not ss:
        return ""
    parts = [f"fit {ss.get('fit', '?')}"]
    if ss.get("signal_strength") is not None:
        parts.append(f"signals {ss['signal_strength']}/100")
    adj = ss.get("credibility_adj") or 0
    if adj:
        parts.append(f"credibility {adj:+g}")
    fired = _fired_signals(ss)
    tail = f"  [{' · '.join(fired)}]" if fired else ""
    return "Blend: " + " · ".join(parts) + tail + f" → {s.score}"


def render_markdown(scored: List[ScoredCandidate], generated_at: str = None,
                    top: int = None) -> str:
    generated_at = generated_at or datetime.date.today().isoformat()
    items = scored[:top] if top else scored
    lines = ["# Signal — dealflow digest",
             f"_{generated_at} · {len(items)} candidates, ranked by thesis fit_", ""]
    for i, s in enumerate(items, 1):
        c = s.candidate
        lines.append(f"## {i}. {c.name}  ·  {s.score}/100")
        meta = [f"**Source:** {c.source}"]
        if c.signal_metric:
            meta.append(f"**Signal:** {c.signal_metric}")
        if s.matched_themes:
            meta.append(f"**Themes:** {', '.join(s.matched_themes)}")
        lines.append("  ·  ".join(meta))
        bd = _breakdown(s)
        if bd:
            lines.append(f"_{bd}_")
        lines += ["", s.thesis_fit]
        if s.flags:
            lines += ["", f"> ⚠️ {', '.join(s.flags)}"]
        risks = [str(r) for r in getattr(s, "risks", []) if not str(r).lower().startswith("llm_fallback")]
        if risks:
            lines += ["", f"_Risks / notes: {', '.join(risks)}_"]
        if s.citations:
            lines += ["", "Sources: " + " · ".join(f"[{_short(u)}]({u})" for u in s.citations)]
        lines += ["", "---", ""]
    return "\n".join(lines)


def write(scored, out_dir: str = "out", top: int = None) -> dict:
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    md_path, json_path = out / "digest.md", out / "digest.json"
    md_path.write_text(render_markdown(scored, top=top), encoding="utf-8")
    json_path.write_text(json.dumps([s.to_dict() for s in scored], indent=2), encoding="utf-8")
    return {"markdown": str(md_path), "json": str(json_path)}
