"""Build the always-on static snapshot of the FULL Signal web UI into docs/ (GitHub Pages).

The published page is the real single-page app — sidebar, signal toggles, scorer picker,
ranked digest, memos, thesis editor, backtest. There is no server on Pages: the page first
paints from baked JSON, then loads Python in the visitor's browser (Pyodide) and runs the REAL
signalfund code from docs/py/signal.zip — run / memo / agent memo / thesis-save / feedback /
backtest all execute client-side through the same webapp.dispatch() the local server uses.

What it does (all offline, heuristic scorer, zero secrets):
  1. Generate the demo digest + backtest (so out/*.json exist).
  2. Bake webapp.build_state() -> docs/data/state.json  (what /api/state would return).
  3. Bake each memo's markdown -> docs/data/memos/<name>.json  (what /api/memo returns).
  4. Bundle git-tracked src/config/data + the generated out/ -> docs/py/signal.zip (Pyodide FS).
  5. Emit docs/app.js + docs/styles.css (verbatim copies) and docs/index.html (the SPA shell
     with relative asset paths, window.SIGNAL_STATIC=true, and a sidebar demo note).

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
FOOT_NOTE = ('<div class="muted" style="opacity:.75">In-browser demo — the real Python runs on '
             'your machine (Pyodide); your edits stay in this tab. '
             '<span id="py-status">Loading Python…</span> '
             '<a href="https://github.com/YAlegend/signal" target="_blank" rel="noopener" '
             'style="color:#7db6ff">Source ↗</a></div>')

# What the in-browser Python needs. Only git-TRACKED files under these roots are bundled, so
# local-only secrets / private ground truth (.env, *.db, ground_truth.portfolio*) can't leak.
BUNDLE_ROOTS = ("src/signalfund", "config", "data/fixtures", "data/showcase",
                "data/backtest/ground_truth.sample.json")
BUNDLE_SKIP_DIRS = ("src/signalfund/web/",)  # SPA assets — served by Pages, not needed in Python


def _write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)}  ({len(text)} bytes)")


def _tracked(roots) -> list:
    """Git-tracked files under `roots` (repo-relative paths)."""
    import subprocess
    r = subprocess.run(["git", "ls-files", "-z", "--", *roots], cwd=str(ROOT),
                       capture_output=True, text=True, check=True)
    return sorted(f for f in r.stdout.split("\0") if f)


def build_bundle(out_dir: pathlib.Path, memos: dict) -> bytes:
    """Zip what the in-browser Python needs, laid out like the repo so signalfund's ROOT-relative
    paths resolve unchanged: tracked source/config/data + the freshly generated out/ (digest,
    backtest, source health, and the memos the page lists). Fixed timestamps keep it
    byte-for-byte reproducible, so the weekly refresh only commits on a real change."""
    import io
    import zipfile
    files = {f: (ROOT / f).read_bytes() for f in _tracked(BUNDLE_ROOTS)
             if not f.startswith(BUNDLE_SKIP_DIRS) and (ROOT / f).is_file()}
    for name in ("digest.json", "backtest_report.json", "source_health.json"):
        if (out_dir / name).is_file():
            files[f"out/{name}"] = (out_dir / name).read_bytes()
    for name, md in memos.items():
        files[f"out/memos/{name}"] = md.encode("utf-8")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(files):
            info = zipfile.ZipInfo(path, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, files[path])
    return buf.getvalue()


def build_index(src_html: str, ver: str) -> str:
    """Transform the served SPA shell into a standalone static page — identical to the local
    app, plus: relative asset paths, the static-mode flag, a sidebar-footer demo note, and a
    cache-busting ?v= on the assets so browsers don't serve a stale CSS/JS."""
    html = (src_html
            # relative + cache-busted asset paths (Pages/CDN + browser caching)
            .replace('href="/styles.css"', f'href="styles.css?v={ver}"')
            .replace('src="/app.js"', f'src="app.js?v={ver}"')
            # turn on static mode (+ the data cache-bust version) before app.js loads
            .replace('<script src="app.js?v=',
                     f'<script>window.SIGNAL_STATIC=true;window.SIGNAL_VER="{ver}";</script>\n  <script src="app.js?v=')
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

    # Showcase: committed agent-generated memo(s) (with their Diligence trail). The always-on demo
    # can't RUN the agent (no backend/key), so we ship a real example so visitors SEE it. Surfaced
    # first in the Memos list and PRESERVED across the keyless weekly refresh (which is single-shot).
    showcase = {}
    show_dir = ROOT / "data" / "showcase"
    for f in sorted(show_dir.glob("*.md")) if show_dir.is_dir() else []:
        showcase[f.name] = f.read_text(encoding="utf-8")
        if f.name in state["memos"]:
            state["memos"].remove(f.name)
        state["memos"].insert(0, f.name)

    state_json = json.dumps(state, default=str, indent=0)
    _write(DATA / "state.json", state_json)

    # Per-memo markdown (what /api/memo?name=… returns) — showcase first, then the demo memos.
    out_memos = webapp._out_dir() / "memos"
    baked_memos = {}
    for name in state.get("memos", []):
        if name in showcase:
            md = showcase[name]
        else:
            p = out_memos / name
            if not p.is_file():
                continue
            md = p.read_text(encoding="utf-8")
        baked_memos[name] = md
        _write(MEMOS / f"{name}.json", json.dumps({"name": name, "markdown": md}, indent=0))

    print("[build-static-demo] bundling the in-browser Python (Pyodide)…")
    bundle = build_bundle(webapp._out_dir(), baked_memos)
    (DOCS / "py").mkdir(parents=True, exist_ok=True)
    (DOCS / "py" / "signal.zip").write_bytes(bundle)
    print(f"  wrote docs/py/signal.zip  ({len(bundle)} bytes)")

    print("[build-static-demo] emitting static SPA assets…")
    import hashlib
    app_js = (WEB / "app.js").read_text(encoding="utf-8")
    css = (WEB / "styles.css").read_text(encoding="utf-8")  # verbatim — page looks identical to local
    # version covers assets AND data, so a data-only change (e.g. new memo) also busts the cache
    ver = hashlib.md5((app_js + css + state_json).encode() + bundle).hexdigest()[:8]
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
