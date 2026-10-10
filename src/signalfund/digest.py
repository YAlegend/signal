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


def _source_health_summary(source_health: List[dict]) -> List[str]:
    """Compact 'live vs skipped vs failed' line + a collapsible per-source table, for
    the digest.md header and the GitHub Actions run summary (both read this file)."""
    if not source_health:
        return []
    live = sum(1 for r in source_health if r.get("state") == "live")
    skipped = sum(1 for r in source_health if r.get("state") == "skipped")
    failed = sum(1 for r in source_health if r.get("state") == "failed")
    lines = [f"_Sources: {live} live · {skipped} skipped · {failed} failed_", "",
             "<details><summary>source health</summary>", "",
             "| source | state | reason |", "|---|---|---|"]
    for r in source_health:
        reason = r.get("reason") or "—"
        count = r.get("count")
        state = r.get("state", "?") + (f" ({count})" if count is not None else "")
        lines.append(f"| {r.get('name')} | {state} | {reason} |")
    lines += ["", "</details>", ""]
    return lines


def render_markdown(scored: List[ScoredCandidate], generated_at: str = None,
                    top: int = None, source_health: List[dict] = None) -> str:
    generated_at = generated_at or datetime.date.today().isoformat()
    items = scored[:top] if top else scored
    lines = ["# Signal — dealflow digest",
             f"_{generated_at} · {len(items)} candidates, ranked by thesis fit_", ""]
    lines += _source_health_summary(source_health)
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


def write(scored, out_dir: str = "out", top: int = None, source_health: List[dict] = None) -> dict:
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    md_path, json_path = out / "digest.md", out / "digest.json"
    md_path.write_text(render_markdown(scored, top=top, source_health=source_health), encoding="utf-8")
    json_path.write_text(json.dumps([s.to_dict() for s in scored], indent=2), encoding="utf-8")
    paths = {"markdown": str(md_path), "json": str(json_path)}
    if source_health is not None:
        health_path = out / "source_health.json"
        health_path.write_text(json.dumps(source_health, indent=2), encoding="utf-8")
        paths["source_health"] = str(health_path)
    return paths
