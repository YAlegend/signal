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

# The static page is visually IDENTICAL to the local app — no banner, no layout overrides (a
# top banner hijacked the .app grid). The "static demo" note goes into the existing sidebar
# footer (normal flow, can't disturb the grid). Compute actions still explain themselves via the
# app's own toast when clicked.
FOOT_NOTE = ('<div class="muted" style="opacity:.75">Static demo — Run / memo / thesis-save run '
             'locally (<code>python -m signalfund.webapp</code>). '
             '<a href="https://github.com/YAlegend/signal" target="_blank" rel="noopener" '
             'style="color:#7db6ff">Source ↗</a></div>')


def _write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)}  ({len(text)} bytes)")


def build_index(src_html: str, ver: str) -> str:
    """Transform the served SPA shell into a standalone static page — identical to the local
    app, plus: relative asset paths, the static-mode flag, a sidebar-footer demo note, and a
    cache-busting ?v= on the assets so browsers don't serve a stale CSS/JS."""
    html = (src_html
            # relative + cache-busted asset paths (Pages/CDN + browser caching)
            .replace('href="/styles.css"', f'href="styles.css?v={ver}"')
            .replace('src="/app.js"', f'src="app.js?v={ver}"')
            # turn on static mode before app.js loads
            .replace('<script src="app.js?v=',
                     '<script>window.SIGNAL_STATIC=true;</script>\n  <script src="app.js?v=')
            # unobtrusive demo note inside the existing sidebar footer (normal flow — can't break grid)
            .replace('      </div>\n    </aside>',
                     f'        {FOOT_NOTE}\n      </div>\n    </aside>'))
    if "window.SIGNAL_STATIC" not in html:
        raise SystemExit("build_index: failed to inject static flag — index.html markup changed?")
    if FOOT_NOTE not in html:
        raise SystemExit("build_index: failed to inject footer note — sidebar markup changed?")
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
    import hashlib
    app_js = (WEB / "app.js").read_text(encoding="utf-8")
    css = (WEB / "styles.css").read_text(encoding="utf-8")  # verbatim — page looks identical to local
    ver = hashlib.md5((app_js + css).encode()).hexdigest()[:8]  # cache-bust on any asset change
    _write(DOCS / "app.js", app_js)
    _write(DOCS / "styles.css", css)
    _write(DOCS / "index.html", build_index((WEB / "index.html").read_text(encoding="utf-8"), ver))

    # Pages: disable Jekyll so files (incl. any leading-underscore names) serve as-is.
    (DOCS / ".nojekyll").touch()

    n_memos = len(list(MEMOS.glob("*.json"))) if MEMOS.exists() else 0
    print(f"[build-static-demo] done — {len(state.get('digest') or [])} candidates, "
          f"{n_memos} memo(s). Open docs/index.html via a static server.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
