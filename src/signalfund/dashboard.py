"""Dashboard — render the digest as a clean, self-contained HTML page.

Pre-renders out/digest.json into out/dashboard.html (no server, no CDN, opens with
file://). The orchestrator calls this every run; you can also run it standalone:

    PYTHONPATH=src python -m signalfund.dashboard
"""
from __future__ import annotations

import datetime
import html
import json
import pathlib


def _esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def _accent(score: float, flags) -> str:
    if flags:
        return "#dc2626"        # red — screened
    if score >= 70:
        return "#22c55e"        # green — strong
    if score >= 45:
        return "#f59e0b"        # amber — moderate
    return "#9ca3af"            # gray — watch


def _card(rank: int, s: dict) -> str:
    c = s.get("candidate", {})
    score = s.get("score", 0)
    flags = s.get("flags", [])
    ss = s.get("subscores", {}) or {}
    accent = _accent(score, flags)

    chips = "".join(f'<span class="chip">{_esc(t)}</span>' for t in s.get("matched_themes", []))
    sources = " · ".join(
        f'<a href="{_esc(u)}" target="_blank" rel="noopener">{_esc(u.split("//")[-1][:42])}</a>'
        for u in s.get("citations", []) if u)
    flag_html = (f'<div class="flags">⚠️ {_esc(", ".join(flags))}</div>') if flags else ""

    breakdown = ""
    if ss:
        # Weighted blend (fit + signal_strength, then credibility), not a sum.
        parts = [f'fit {_esc(ss.get("fit", "?"))}']
        if ss.get("signal_strength") is not None:
            parts.append(f'signals {_esc(ss.get("signal_strength"))}/100')
        if ss.get("credibility_adj"):
            parts.append(f'credibility {ss.get("credibility_adj"):+g}')
        fired = []
        if ss.get("traction") is not None and ss.get("traction_bonus"):
            fired.append(f'traction {_esc(ss.get("traction_bonus"))}')
        for k in ("code_health", "onchain", "team", "social", "pre_public"):
            if ss.get(k):
                fired.append(f'{k} {_esc(ss.get(k))}')
        tail = f' &nbsp;[{" &middot; ".join(fired)}]' if fired else ""
        breakdown = f'<div class="breakdown">{" &middot; ".join(parts)}{tail}</div>'

    metric = f'<div class="metric">{_esc(c.get("signal_metric"))}</div>' if c.get("signal_metric") else ""

    return f"""
    <article class="card" style="--accent:{accent}">
      <div class="rank">{rank}</div>
      <div class="body">
        <div class="top">
          <h2>{_esc(c.get("name"))}</h2>
          <div class="score" style="background:{accent}">{_esc(score)}</div>
        </div>
        <div class="src">{_esc(c.get("source"))}</div>
        {metric}
        <div class="chips">{chips}</div>
        <p class="fit">{_esc(s.get("thesis_fit"))}</p>
        {breakdown}
        {flag_html}
        <div class="sources">{sources}</div>
      </div>
    </article>"""


def generate(out_dir: str = "out") -> str:
    out = pathlib.Path(out_dir)
    digest_json = out / "digest.json"
    if not digest_json.exists():
        raise FileNotFoundError(f"{digest_json} not found — run the digest first.")
    data = json.loads(digest_json.read_text(encoding="utf-8"))

    n = len(data)
    strong = sum(1 for s in data if s.get("score", 0) >= 70 and not s.get("flags"))
    screened = sum(1 for s in data if s.get("flags"))
    memos = []
    mdir = out / "memos"
    if mdir.exists():
        memos = [p.name for p in sorted(mdir.glob("*.md"))]
    memo_note = (f'<span class="stat"><b>{len(memos)}</b> memo(s) in out/memos/</span>'
                 if memos else "")

    cards = "".join(_card(i, s) for i, s in enumerate(data, 1))
    date = datetime.date.today().isoformat()

    return _write(out, f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Signal — dealflow</title>
<style>
:root {{ color-scheme: dark; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:#0b0f17; color:#e5e7eb;
  font:15px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; }}
.wrap {{ max-width:880px; margin:0 auto; padding:32px 20px 64px; }}
header h1 {{ font-size:22px; margin:0 0 4px; letter-spacing:.2px; }}
header .sub {{ color:#9ca3af; font-size:13px; }}
.stats {{ display:flex; gap:18px; margin:16px 0 26px; flex-wrap:wrap; font-size:13px; color:#cbd5e1; }}
.stat b {{ color:#fff; font-size:15px; }}
.card {{ display:flex; gap:16px; background:#121826; border:1px solid #1f2937;
  border-left:4px solid var(--accent); border-radius:12px; padding:18px 20px; margin:0 0 14px; }}
.rank {{ color:#4b5563; font-weight:700; font-size:15px; min-width:20px; padding-top:2px; }}
.body {{ flex:1; min-width:0; }}
.top {{ display:flex; align-items:center; justify-content:space-between; gap:12px; }}
.top h2 {{ font-size:17px; margin:0; word-break:break-word; }}
.score {{ color:#04140a; font-weight:800; font-size:14px; padding:3px 10px; border-radius:999px; }}
.src {{ color:#6b7280; font-size:12px; text-transform:uppercase; letter-spacing:.5px; margin-top:2px; }}
.metric {{ color:#a5b4fc; font-size:13px; margin-top:6px; }}
.chips {{ margin:8px 0 2px; }}
.chip {{ display:inline-block; background:#1e293b; color:#93c5fd; font-size:11px;
  padding:2px 8px; border-radius:999px; margin:0 6px 6px 0; }}
.fit {{ margin:8px 0 6px; color:#d1d5db; }}
.breakdown {{ color:#9ca3af; font-size:12px; font-variant-numeric:tabular-nums; }}
.flags {{ color:#fca5a5; font-size:13px; margin-top:6px; }}
.sources {{ margin-top:8px; font-size:12px; }}
.sources a {{ color:#60a5fa; text-decoration:none; margin-right:4px; }}
.sources a:hover {{ text-decoration:underline; }}
footer {{ color:#4b5563; font-size:12px; margin-top:30px; text-align:center; }}
</style></head><body><div class="wrap">
<header>
  <h1>Signal — dealflow digest</h1>
  <div class="sub">{date} · ranked by thesis fit · generated by the Signal pipeline</div>
</header>
<div class="stats">
  <span class="stat"><b>{n}</b> candidates</span>
  <span class="stat"><b>{strong}</b> strong (&ge;70)</span>
  <span class="stat"><b>{screened}</b> screened out</span>
  {memo_note}
</div>
{cards}
<footer>Signal · thesis-driven sourcing · scores are a triage aid, not a verdict — a human makes the call.</footer>
</div></body></html>""")


def _write(out: pathlib.Path, doc: str) -> str:
    path = out / "dashboard.html"
    path.write_text(doc, encoding="utf-8")
    return str(path)


def main():
    print(f"[dashboard] wrote {generate()}")


if __name__ == "__main__":
    main()
