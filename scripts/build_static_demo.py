"""Build the always-on static snapshot of the FULL Signal web UI into docs/ (GitHub Pages).

The published page is the real single-page app — sidebar, signal toggles, scorer picker,
ranked digest, memos, thesis editor, backtest — running entirely client-side against baked
JSON. There is no Python backend on Pages, so compute actions (run / memo / thesis-save /
feedback / backtest) surface a friendly "runs locally" message instead.

What it does (all offline, heuristic scorer, zero secrets):
  1. Generate the demo digest + backtest (so out/*.json exist).
  2. Bake webapp.build_state() -> docs/data/state.json  (what /api/state would return).
  3. Bake each memo's markdown -> docs/data/memos/<name>.json  (what /api/memo returns).
  4. Emit docs/app.js + docs/styles.css (verbatim copies) and docs/index.html (the SPA shell
     with relative asset paths, window.SIGNAL_STATIC=true, and a demo banner).

Run:  PYTHONPATH=src python scripts/build_static_demo.py
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

# Offline + deterministic: heuristic scorer, no network/keys.
os.environ.setdefault("SIGNAL_LLM_PROVIDER", "heuristic")

from signalfund import orchestrator, webapp  # noqa: E402

WEB = SRC / "signalfund" / "web"
DOCS = ROOT / "docs"
DATA = DOCS / "data"
MEMOS = DATA / "memos"

BANNER = (
    '<div id="demo-banner">Static demo — a read-only snapshot of the live UI. '
    "Run, memo &amp; thesis-edit work locally via <code>python -m signalfund.webapp</code>. "
    '<a href="https://github.com/YAlegend/signal" target="_blank" rel="noopener">Source&nbsp;↗</a>'
    "</div>"
)
# Static-only CSS. The banner sits ABOVE .app (not inside it — .app is a 2-col grid, so a child
# would hijack a grid cell). Body becomes a vertical flex: banner on top, .app fills the rest and
# keeps its own internal scroll.
BANNER_CSS = """
/* ---- static-demo banner + layout (GitHub Pages only) ---- */
body{display:flex;flex-direction:column;height:100vh;margin:0}
.app{height:auto;min-height:0;flex:1 1 auto}
#demo-banner{flex:0 0 auto;background:#13243b;color:#cfe3ff;font-size:13px;line-height:1.5;
  padding:9px 18px;text-align:center;border-bottom:1px solid #243b5e}
#demo-banner code{background:#0a1422;padding:1px 6px;border-radius:4px;font-size:12px}
#demo-banner a{color:#7db6ff;text-decoration:none;font-weight:600}
#demo-banner a:hover{text-decoration:underline}
"""


def _write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)}  ({len(text)} bytes)")


def build_index(src_html: str) -> str:
    """Transform the served SPA shell into a standalone static page."""
    html = (src_html
            .replace('href="/styles.css"', 'href="styles.css"')
            .replace('src="/app.js"', 'src="app.js"')
            # turn on static mode before app.js loads
            .replace('<script src="app.js"></script>',
                     '<script>window.SIGNAL_STATIC=true;</script>\n  <script src="app.js"></script>')
            # demo banner ABOVE the app shell (sibling, not a grid child)
            .replace('<div class="app">', f'{BANNER}\n  <div class="app">'))
    if "window.SIGNAL_STATIC" not in html:
        raise SystemExit("build_index: failed to inject static flag — index.html markup changed?")
    return html


def main() -> int:
    print("[build-static-demo] generating demo artifacts (offline, heuristic)…")
    orchestrator.run(demo=True, limit=25)

    # Best-effort: a memo so the Memos tab isn't empty (heuristic; ignore if it can't).
    import subprocess
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    r = subprocess.run([sys.executable, "-m", "signalfund.memo", "--demo"],
                       cwd=str(ROOT), env=env, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  (memo generation skipped: {r.stderr.strip().splitlines()[-1:] or r.stdout.strip()[-200:]})")

    print("[build-static-demo] baking API snapshots…")
    state = webapp.build_state()
    _write(DATA / "state.json", json.dumps(state, default=str, indent=0))

    # Per-memo markdown (what /api/memo?name=… returns).
    out_memos = webapp._out_dir() / "memos"
    for name in state.get("memos", []):
        p = out_memos / name
        if p.is_file():
            _write(MEMOS / f"{name}.json",
                   json.dumps({"name": name, "markdown": p.read_text(encoding="utf-8")}, indent=0))

    print("[build-static-demo] emitting static SPA assets…")
    _write(DOCS / "app.js", (WEB / "app.js").read_text(encoding="utf-8"))
    _write(DOCS / "styles.css", (WEB / "styles.css").read_text(encoding="utf-8") + BANNER_CSS)
    _write(DOCS / "index.html", build_index((WEB / "index.html").read_text(encoding="utf-8")))

    # Pages: disable Jekyll so files (incl. any leading-underscore names) serve as-is.
    (DOCS / ".nojekyll").touch()

    n_memos = len(list(MEMOS.glob("*.json"))) if MEMOS.exists() else 0
    print(f"[build-static-demo] done — {len(state.get('digest') or [])} candidates, "
          f"{n_memos} memo(s). Open docs/index.html via a static server.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
