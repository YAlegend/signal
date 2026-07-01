"use strict";

const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// Reusable inline info tooltip (hover + keyboard focus; CSS-only bubble, works in the static build).
// `pos` is optional edge/position modifiers: "ta" (above), "tl" (left-anchored), "tr" (right-anchored).
function info(tip, pos) {
  return `<span class="info${pos ? " " + pos : ""}" tabindex="0" role="note" aria-label="${esc(tip)}">`
    + `ⓘ<span class="tip">${esc(tip)}</span></span>`;
}

const state = { digest: [], backtest: null, memos: [], thesisParsed: null, thesis: {}, feedback: {},
                signals: [], enabled: {}, providers: [], scorerProvider: "auto", scorer: "?", mode: "demo" };
const LS_SIGNALS = "signal.enabledSignals";
const LS_SCORER = "signal.scorerProvider";

async function api(path, opts) {
  // Static-demo mode (GitHub Pages): no Python backend. Reads are served from baked JSON
  // under data/; compute actions (run/memo/thesis-save/feedback/backtest) have no server, so
  // they surface a friendly "runs locally" message. window.SIGNAL_STATIC is set only by the
  // published docs/index.html — locally it's undefined and this branch is skipped entirely.
  if (window.SIGNAL_STATIC) return staticApi(path, opts);
  const res = await fetch(path, opts);
  const ct = res.headers.get("content-type") || "";
  const data = ct.includes("json") ? await res.json() : await res.text();
  if (!res.ok) throw new Error((data && data.error) || res.statusText);
  return data;
}

async function staticApi(path, opts) {
  const method = ((opts && opts.method) || "GET").toUpperCase();
  if (method !== "GET") {
    throw new Error("Static demo — this action runs locally. Clone the repo and run "
      + "`python -m signalfund.webapp` for live runs, thesis edits, and memo generation.");
  }
  let file;
  if (path.startsWith("/api/state")) file = "data/state.json";
  else if (path.startsWith("/api/memo")) {
    const name = new URLSearchParams(path.split("?")[1] || "").get("name") || "";
    file = "data/memos/" + name + ".json";
  } else {
    file = "data" + path.replace(/^\/api/, "") + ".json";
  }
  const res = await fetch(file);
  if (!res.ok) throw new Error("not available in the static demo");
  return await res.json();
}

function toast(msg, isErr = false) {
  let t = $("#toast");
  if (!t) { t = document.createElement("div"); t.id = "toast"; t.className = "toast"; document.body.appendChild(t); }
  t.textContent = msg;
  t.className = "toast show" + (isErr ? " err" : "");
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.className = "toast"; }, 3200);
}

const accent = (s) => {
  const sc = s.score ?? 0;
  if (s.flags && s.flags.length) return "var(--red)";
  if (sc >= 70) return "var(--green)";
  if (sc >= 45) return "var(--amber)";
  return "var(--gray)";
};

/* ---------- routing ---------- */
function show(view) {
  $$(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === "view-" + view));
  if (view === "digest") renderDigest();
  if (view === "memos") renderMemoList();
  if (view === "backtest") renderBacktest();
}
$("#nav").addEventListener("click", (e) => {
  const btn = e.target.closest(".nav-item");
  if (btn) show(btn.dataset.view);
});

/* ---------- markdown (tiny) ---------- */
function md(src) {
  const lines = String(src).split("\n");
  let html = "", inUl = false, inTable = false, tableRows = [];
  const inline = (t) => esc(t)
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/(^|[\s(])((https?:\/\/[^\s)]+))/g, '$1<a href="$2" target="_blank" rel="noopener">$2</a>');
  const flushUl = () => { if (inUl) { html += "</ul>"; inUl = false; } };
  const flushTable = () => {
    if (!inTable) return;
    const [head, , ...body] = tableRows;
    const cells = (r) => r.replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
    html += "<table><thead><tr>" + cells(head).map((c) => `<th>${inline(c)}</th>`).join("") + "</tr></thead><tbody>";
    body.forEach((r) => { html += "<tr>" + cells(r).map((c) => `<td>${inline(c)}</td>`).join("") + "</tr>"; });
    html += "</tbody></table>"; inTable = false; tableRows = [];
  };
  for (const ln of lines) {
    if (/^\s*\|.*\|\s*$/.test(ln)) { inTable = true; tableRows.push(ln); continue; }
    flushTable();
    if (/^#{1,6}\s/.test(ln)) { flushUl(); const n = ln.match(/^#+/)[0].length; html += `<h${n}>${inline(ln.replace(/^#+\s/, ""))}</h${n}>`; }
    else if (/^\s*[-*]\s+/.test(ln)) { if (!inUl) { html += "<ul>"; inUl = true; } html += `<li>${inline(ln.replace(/^\s*[-*]\s+/, ""))}</li>`; }
    else if (/^>\s?/.test(ln)) { flushUl(); html += `<blockquote>${inline(ln.replace(/^>\s?/, ""))}</blockquote>`; }
    else if (/^---+\s*$/.test(ln)) { flushUl(); html += "<hr>"; }
    else if (ln.trim() === "") { flushUl(); }
    else { flushUl(); html += `<p>${inline(ln)}</p>`; }
  }
  flushUl(); flushTable();
  return html;
}

/* ---------- run ---------- */
function setMode(mode) {
  state.mode = mode;
  $("#mode-demo").classList.toggle("active", mode === "demo");
  $("#mode-live").classList.toggle("active", mode === "live");
  $("#limit-wrap").style.opacity = mode === "live" ? "1" : ".5";
  $("#run-hint").hidden = mode !== "live";
}
$("#mode-demo").onclick = () => setMode("demo");
$("#mode-live").onclick = () => setMode("live");

/* ---------- signals panel (user-controlled) ---------- */
function loadEnabled(signals) {
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(LS_SIGNALS) || "{}"); } catch (e) { /* ignore */ }
  state.enabled = {};
  // Default: free ON, premium OFF — user opts in. A saved choice always wins.
  signals.forEach((s) => {
    state.enabled[s.name] = (s.name in saved) ? !!saved[s.name] : (s.tier === "free");
  });
}

function persistEnabled() {
  localStorage.setItem(LS_SIGNALS, JSON.stringify(state.enabled));
}

function enabledList() {
  return Object.keys(state.enabled).filter((k) => state.enabled[k]);
}

/* ---------- scorer-model picker ---------- */
function renderScorerSelect() {
  const sel = $("#scorer-select");
  if (!sel) return;
  sel.innerHTML = state.providers.map((p) => {
    // unavailable providers are still selectable — show a key hint inline
    const tag = (p.available || !p.env) ? "" : ` — add ${p.env}`;
    return `<option value="${esc(p.name)}"${p.name === state.scorerProvider ? " selected" : ""}>${esc(p.label)}${esc(tag)}</option>`;
  }).join("");
  sel.value = state.scorerProvider;
}
$("#scorer-select").addEventListener("change", (e) => {
  state.scorerProvider = e.target.value;
  localStorage.setItem(LS_SCORER, state.scorerProvider);
});

function renderSignals() {
  const box = $("#signal-rows");
  if (!box) return;
  box.innerHTML = state.signals.map((s) => {
    const on = !!state.enabled[s.name];
    const premiumNoKey = s.tier === "premium" && on && !s.key_present;
    const hint = premiumNoKey
      ? `<span class="sig-hint">no key — add <code>${esc(s.env)}</code> in .env for real data</span>` : "";
    return `<div class="signal-row">
      <label class="switch"><input type="checkbox" data-signal="${esc(s.name)}"${on ? " checked" : ""}><span class="slider"></span></label>
      <span class="sig-name">${esc(s.label || s.name)}</span>
      <span class="badge-tier ${esc(s.tier)}">${s.tier === "free" ? "Free" : "Premium"}</span>
      ${hint}
    </div>`;
  }).join("");
  const frontier = String(state.scorer).includes("frontier");
  // The free tier still runs the GitHub-derived team path — reflect it (+ token status) here.
  const ghTeam = state.signals.find((x) => x.name === "team_github");
  const ghNote = ghTeam
    ? `<span class="badge-tier free">team · GitHub free</span>` +
      `<span class="muted">GITHUB_TOKEN ${ghTeam.key_present ? "set ✓" : "absent — optional, lifts rate limits"}</span>`
    : "";
  $("#signal-scorer").innerHTML =
    `<span class="muted">LLM scorer tier (auto, by keys):</span> ` +
    `<span class="badge-tier ${frontier ? "premium" : "free"}">${esc(state.scorer)}</span>` +
    ghNote;
}

$("#signal-rows").addEventListener("change", (e) => {
  const cb = e.target.closest("input[data-signal]");
  if (!cb) return;
  state.enabled[cb.dataset.signal] = cb.checked;
  persistEnabled();
  renderSignals();  // refresh premium-without-key hints
});

$("#run-btn").onclick = async () => {
  const btn = $("#run-btn"), log = $("#run-log");
  btn.disabled = true; btn.textContent = "Running…";
  log.hidden = false; log.textContent = "[signal-web] starting run…\n";
  try {
    const r = await api("/api/run", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ demo: state.mode === "demo", limit: Number($("#limit").value) || 25,
                             enabled_signals: enabledList(), scorer_provider: state.scorerProvider }),
    });
    log.textContent = r.log || "(no output)";
    state.digest = r.digest || [];
    if (r.scorer) { state.scorer = r.scorer; $("#scorer-pill").textContent = "scorer: " + r.scorer; renderSignals(); }
    refreshCounts();
    if (r.ok) { toast(`Run complete — ${state.digest.length} candidates · ${r.scorer || ""}`); show("digest"); }
    else { toast(r.error || "run failed", true); log.textContent += "\n[error] " + r.error; }
  } catch (e) { toast(e.message, true); log.textContent += "\n[error] " + e.message; }
  finally { btn.disabled = false; btn.textContent = "Run sourcing ▶"; }
};

/* ---------- digest ---------- */
function themeOptions() {
  const set = new Set();
  state.digest.forEach((s) => (s.matched_themes || []).forEach((t) => set.add(t)));
  const sel = $("#theme-filter"), cur = sel.value;
  sel.innerHTML = '<option value="">All themes</option>' + [...set].sort().map((t) => `<option>${esc(t)}</option>`).join("");
  sel.value = cur;
}

function bars(ss) {
  if (!ss) return "";
  const rows = [];
  const bar = (label, val) => {
    if (val == null) return `<div>${label}</div><div class="bar"><span style="width:0"></span></div><div class="bar-val">—</div>`;
    return `<div>${label}</div><div class="bar"><span style="width:${Math.max(0, Math.min(100, val))}%"></span></div><div class="bar-val">${val}</div>`;
  };
  rows.push(bar("fit", ss.fit));
  rows.push(bar("signals", ss.signal_strength));
  rows.push(bar("traction", ss.traction));
  let extra = [];
  if (ss.traction_bonus) extra.push(`traction bonus +${ss.traction_bonus}`);
  if (ss.credibility_adj) extra.push(`credibility ${ss.credibility_adj > 0 ? "+" : ""}${ss.credibility_adj}`);
  if (ss.code_health) extra.push(`code_health +${ss.code_health}`);
  if (ss.onchain) extra.push(`onchain +${ss.onchain}`);
  if (ss.team) extra.push(`team +${ss.team}`);
  if (ss.social) extra.push(`social +${ss.social}`);
  if (ss.pre_public) extra.push(`pre_public +${ss.pre_public}`);
  return `<div class="bars-head">breakdown ${info("Score = thesis fit (dominant, ~60%) + quality signals (~40%) + a credibility adjustment. Fit gates; signals corroborate; traction is dampened so one spike can't carry a company.")}</div>`
    + `<div class="bars">${rows.join("")}</div>` +
    (extra.length ? `<div class="muted" style="font-size:12px;margin:-4px 0 10px">${extra.join(" · ")}</div>` : "");
}

function card(s, rank, origIdx) {
  const c = s.candidate || {};
  const ac = accent(s);
  const chips = (s.matched_themes || []).map((t) => `<span class="chip">${esc(t)}</span>`).join("");
  const metric = c.signal_metric ? `<div class="metric">${esc(c.signal_metric)}</div>` : "";
  const flags = (s.flags && s.flags.length) ? `<div class="flags">⚠️ ${esc(s.flags.join(", "))}</div>` : "";
  const sources = (s.citations || []).filter(Boolean)
    .map((u) => `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(u.replace(/^https?:\/\//, "").slice(0, 46))}</a>`).join("");
  const fb = state.feedback[c.name];
  return `<article class="card" style="border-left-color:${ac}" data-idx="${origIdx}">
    <div class="rank">${rank}</div>
    <div class="body">
      <div class="top"><h2>${esc(c.name)}</h2>
        <div class="top-right">
          <span class="feedback">
            <button class="thumb up${fb === "up" ? " active" : ""}" data-fb="up" title="On-thesis — good surface">👍</button>
            <button class="thumb down${fb === "down" ? " active" : ""}" data-fb="down" title="Off-thesis — bad surface">👎</button>
            ${info("Label a candidate — feedback is logged to help train the scorer over time.", "tr")}
          </span>
          <span class="score-pill" style="background:${ac}">${esc(s.score)}</span>
        </div>
      </div>
      <div class="src">${esc(c.source)}</div>
      ${metric}
      <div class="chips">${chips}</div>
      <p class="fit">${esc(s.thesis_fit)}</p>
      ${flags}
      <div class="detail">
        ${bars(s.subscores)}
        ${c.summary ? `<p class="muted" style="font-size:13px">${esc(c.summary)}</p>` : ""}
        <div class="sources">${sources}</div>
        <div class="detail-actions"><button class="ghost" data-memo="${origIdx}">✎ Write memo</button></div>
      </div>
    </div>
  </article>`;
}

function renderDigest() {
  themeOptions();
  const q = $("#q").value.toLowerCase().trim();
  const theme = $("#theme-filter").value;
  const minScore = Number($("#min-score").value);
  const sort = $("#sort").value;
  let rows = state.digest.map((s, i) => ({ s, i }));
  rows = rows.filter(({ s }) => {
    const c = s.candidate || {};
    if ((s.score ?? 0) < minScore) return false;
    if (theme && !(s.matched_themes || []).includes(theme)) return false;
    if (q) {
      const hay = [c.name, c.summary, (c.tags || []).join(" "), (s.matched_themes || []).join(" ")].join(" ").toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  if (sort === "name") rows.sort((a, b) => (a.s.candidate.name || "").localeCompare(b.s.candidate.name || ""));
  else if (sort === "traction") rows.sort((a, b) => (b.s.subscores?.traction ?? -1) - (a.s.subscores?.traction ?? -1));
  else rows.sort((a, b) => (b.s.score ?? 0) - (a.s.score ?? 0));

  $("#digest-empty").hidden = state.digest.length > 0;
  const total = state.digest.length;
  const strong = state.digest.filter((s) => (s.score ?? 0) >= 70 && !(s.flags || []).length).length;
  const screened = state.digest.filter((s) => (s.flags || []).length).length;
  const rated = Object.keys(state.feedback).length;
  $("#digest-stats").innerHTML = total ? `
    <span class="stat"><b>${total}</b> candidates</span>
    <span class="stat"><b>${strong}</b> strong (≥70)</span>
    <span class="stat"><b>${screened}</b> screened out</span>
    <span class="stat"><b>${rows.length}</b> shown</span>
    ${rated ? `<span class="stat"><b>${rated}</b> rated 👍/👎</span>` : ""}
    ${info("strong = score ≥ 70. screened out = hit a hard anti-signal like scam or presale. shown = passed the noise filter.")}` : "";
  $("#cards").innerHTML = rows.map(({ s, i }, n) => card(s, n + 1, i)).join("");
}

$("#cards").addEventListener("click", (e) => {
  const thumb = e.target.closest(".thumb");
  if (thumb) { e.stopPropagation(); vote(Number(thumb.closest(".card").dataset.idx), thumb.dataset.fb); return; }
  const memoBtn = e.target.closest("[data-memo]");
  if (memoBtn) { e.stopPropagation(); writeMemo(Number(memoBtn.dataset.memo)); return; }
  const c = e.target.closest(".card");
  if (c) c.classList.toggle("open");
});

async function vote(origIdx, label) {
  const name = state.digest[origIdx] && state.digest[origIdx].candidate.name;
  if (!name) return;
  const next = state.feedback[name] === label ? "clear" : label; // click again to retract
  try {
    const r = await api("/api/feedback", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ index: origIdx, label: next }),
    });
    state.feedback = r.votes || {};
    renderDigest();
    toast(next === "clear" ? "Vote cleared"
      : next === "up" ? "👍 On-thesis — logged to data/feedback.jsonl"
      : "👎 Off-thesis — logged to data/feedback.jsonl");
  } catch (e) { toast(e.message, true); }
}
["#q", "#theme-filter", "#sort"].forEach((s) => $(s).addEventListener("input", renderDigest));
$("#min-score").addEventListener("input", (e) => { $("#min-val").textContent = e.target.value; renderDigest(); });

/* ---------- memos ---------- */
async function writeMemo(idx) {
  toast("Generating memo…");
  try {
    const r = await api("/api/memo", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ index: idx, scorer_provider: state.scorerProvider }),
    });
    if (!r.ok) return toast(r.error || "memo failed", true);
    if (!state.memos.includes(r.name)) state.memos.push(r.name);
    refreshCounts();
    show("memos");
    renderMemoList();
    openMemo(r.name, r.markdown);
    toast("Memo written → out/memos/" + r.name);
  } catch (e) { toast(e.message, true); }
}

function renderMemoList() {
  const list = $("#memo-list");
  if (!state.memos.length) { list.innerHTML = '<div class="empty">No memos yet.</div>'; return; }
  list.innerHTML = state.memos.map((m) => `<button data-memo-name="${esc(m)}">${esc(m.replace(/\.md$/, ""))}</button>`).join("");
}
$("#memo-list").addEventListener("click", (e) => {
  const b = e.target.closest("[data-memo-name]");
  if (b) openMemo(b.dataset.memoName);
});
async function openMemo(name, markdown) {
  $$("#memo-list button").forEach((b) => b.classList.toggle("active", b.dataset.memoName === name));
  if (!markdown) {
    try { const r = await api("/api/memo?name=" + encodeURIComponent(name)); markdown = r.markdown; }
    catch (e) { return toast(e.message, true); }
  }
  // Annotate the "Sub-scores:" line with an inline tooltip (post-process the rendered HTML).
  const subTip = info("What actually fed this score. A sample company like this is GitHub-only, so you see fit + traction. A real company with on-chain, team, social, or funding data would show those too. Any signal with no data just counts 0 — it's never invented.");
  const html = md(markdown).replace("Sub-scores:", "Sub-scores: " + subTip);
  $("#memo-view").innerHTML = `<div class="md">${html}</div>`;
}

/* ---------- thesis (sectioned editor) ---------- */
// state.thesis is a working copy of the FULL parsed object; controls mutate only their
// own fields so unknown keys (e.g. `updated`) survive the round-trip.
const SW_SIGNALS = ["code_health", "onchain", "team", "social", "pre_public"];
let _focusAdd = null;  // chip-list key to refocus after a re-render

function arrayFor(key) {
  const t = state.thesis;
  if (key === "anti") {
    if (!t.anti_signals) t.anti_signals = { keywords: [] };
    if (!t.anti_signals.keywords) t.anti_signals.keywords = [];
    return t.anti_signals.keywords;
  }
  if (key === "prefer" || key === "avoid") {
    if (!t.stage_preference) t.stage_preference = { prefer: [], avoid: [] };
    if (!t.stage_preference[key]) t.stage_preference[key] = [];
    return t.stage_preference[key];
  }
  const m = key.match(/^theme:(\d+):keywords$/);
  if (m) { const th = t.themes[+m[1]]; if (!th.keywords) th.keywords = []; return th.keywords; }
  return null;
}

function chipList(arr, key) {
  const chips = (arr || []).map((kw, j) =>
    `<span class="chip kw">${esc(kw)}<button class="kw-x" data-rm="${esc(key)}" data-i="${j}" title="remove">×</button></span>`).join("");
  return `<span class="kw-list">${chips}<input class="kw-add" data-add="${esc(key)}" placeholder="+ add (Enter)"></span>`;
}

function themeCard(th, i) {
  return `<div class="theme-edit">
    <div class="theme-edit-top">
      <input class="theme-label" type="text" data-theme="${i}" data-field="label" value="${esc(th.label || "")}" placeholder="label">
      <button class="kw-x" data-del-theme="${i}" title="delete theme">×</button>
    </div>
    <div class="theme-weight"><span class="muted" style="min-width:54px">weight${info("How central this theme is to the fund — 1.0 = core thesis, 0.5 = wider strike zone. Higher weight = a bigger boost to a company's fit.")}</span>
      <input type="range" min="0" max="1" step="0.05" data-theme="${i}" data-field="weight" value="${th.weight ?? 0}">
      <b data-weightval="${i}">${th.weight ?? 0}</b></div>
    <div class="small muted">name: <code>${esc(th.name || "—")}</code></div>
    ${chipList(th.keywords, "theme:" + i + ":keywords")}
    <input class="t-oq" type="text" data-theme="${i}" data-field="open_question" value="${esc(th.open_question || "")}" placeholder="open question">
  </div>`;
}

function swSliders(sw) {
  return SW_SIGNALS.map((n) => `<div class="theme-weight"><span class="muted" style="min-width:96px">${n}</span>
    <input type="range" min="0" max="30" step="1" data-sw="${n}" value="${sw[n] ?? 0}">
    <b data-swval="${n}">${sw[n] ?? 0}</b></div>`).join("");
}

function renderThesis() {
  const t = state.thesis || {};
  const box = $("#thesis-sections");
  if (!box) return;
  const themes = t.themes || [];
  const sp = t.stage_preference || {};
  box.innerHTML = `
    <details class="tcard" open><summary>Summary</summary><div class="tcard-body">
      <label class="field2"><span>fund</span><input type="text" data-path="fund" value="${esc(t.fund || "")}"></label>
      <label class="field2"><span>thesis_summary</span><textarea data-path="thesis_summary" rows="4">${esc(t.thesis_summary || "")}</textarea></label>
    </div></details>

    <details class="tcard" open><summary>Themes · ${themes.length}</summary><div class="tcard-body">
      ${themes.map(themeCard).join("")}
      <button class="ghost" id="add-theme">+ Add theme</button>
    </div></details>

    <details class="tcard"><summary>Anti-signals · ${(t.anti_signals?.keywords || []).length}${info("Words that down-rank a candidate hard — scam/hype language — regardless of fit.")}</summary><div class="tcard-body">
      <div class="small muted">candidates matching these are down-ranked</div>
      ${chipList(t.anti_signals?.keywords || [], "anti")}
    </div></details>

    <details class="tcard"><summary>Stage preference${info("Prefer early stages; down-rank late/public rounds. An on-thesis company that already raised a Series B gets marked down.")}</summary><div class="tcard-body">
      <div class="small muted">prefer</div>${chipList(sp.prefer || [], "prefer")}
      <div class="small muted" style="margin-top:8px">avoid</div>${chipList(sp.avoid || [], "avoid")}
    </div></details>

    <details class="tcard"><summary>Signal weights${info("The most points each signal can add. Team is highest (founder quality is most predictive); on-chain and social are lower because they're easier to fake.")}</summary><div class="tcard-body">
      <div class="small muted">composite (fit vs signals)${info("How the final score blends thesis fit vs the quality signals. Fit dominates (~60%) so off-thesis stays low; signals (~40%) separate the strong ones.")}</div>
      <div class="small muted">max points each signal can add on top of fit + traction + credibility</div>
      ${t.signal_weights ? swSliders(t.signal_weights) : `<button class="ghost" id="sw-enable">Enable signal-weight tuning</button>`}
    </div></details>`;
  if (_focusAdd) { const el = box.querySelector(`[data-add="${CSS.escape(_focusAdd)}"]`); if (el) el.focus(); _focusAdd = null; }
}

// Mutations that don't need a re-render (typing / dragging) — keep focus.
$("#thesis-sections").addEventListener("input", (e) => {
  const el = e.target;
  if (el.dataset.path) {
    state.thesis[el.dataset.path] = el.value;
  } else if (el.dataset.theme !== undefined && el.dataset.field) {
    const th = state.thesis.themes[+el.dataset.theme];
    if (el.dataset.field === "weight") {
      th.weight = parseFloat(el.value);
      const b = $(`[data-weightval="${el.dataset.theme}"]`); if (b) b.textContent = th.weight;
    } else { th[el.dataset.field] = el.value; }
  } else if (el.dataset.sw) {
    if (!state.thesis.signal_weights) state.thesis.signal_weights = {};
    state.thesis.signal_weights[el.dataset.sw] = parseInt(el.value, 10);
    const b = $(`[data-swval="${el.dataset.sw}"]`); if (b) b.textContent = el.value;
  }
});

// Chip add: type + Enter.
$("#thesis-sections").addEventListener("keydown", (e) => {
  const el = e.target;
  if (el.classList && el.classList.contains("kw-add") && e.key === "Enter") {
    e.preventDefault();
    const val = el.value.trim();
    if (!val) return;
    const arr = arrayFor(el.dataset.add);
    if (arr && !arr.includes(val)) arr.push(val);
    _focusAdd = el.dataset.add;
    renderThesis();
  }
});

// Structural clicks: remove chip, delete/add theme, enable signal weights.
$("#thesis-sections").addEventListener("click", (e) => {
  const rm = e.target.closest("[data-rm]");
  if (rm) { const arr = arrayFor(rm.dataset.rm); if (arr) arr.splice(+rm.dataset.i, 1); return renderThesis(); }
  const del = e.target.closest("[data-del-theme]");
  if (del) { state.thesis.themes.splice(+del.dataset.delTheme, 1); return renderThesis(); }
  if (e.target.id === "add-theme") {
    if (!state.thesis.themes) state.thesis.themes = [];
    state.thesis.themes.push({ name: "new_theme_" + state.thesis.themes.length,
                               label: "New theme", weight: 0.5, keywords: [], open_question: "" });
    return renderThesis();
  }
  if (e.target.id === "sw-enable") {
    state.thesis.signal_weights = { code_health: 15, onchain: 12, team: 20, social: 12, pre_public: 15 };
    return renderThesis();
  }
});

function syncThesis(r) {
  state.thesisParsed = r.thesisParsed;
  state.thesis = JSON.parse(JSON.stringify(r.thesisParsed || {}));
  if (r.text != null) $("#thesis-text").value = r.text;
  renderThesis();
}

$("#thesis-save").onclick = async () => {
  const status = $("#thesis-status");
  state.thesis.updated = new Date().toISOString().slice(0, 10);  // bump to today
  try {
    const r = await api("/api/thesis", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ thesis: state.thesis }),
    });
    syncThesis(r);
    status.textContent = "✓ saved — re-run sourcing to apply"; status.className = "status ok";
    toast("Thesis saved");
  } catch (e) { status.textContent = "✗ " + e.message; status.className = "status err"; toast(e.message, true); }
};

$("#thesis-raw-save").onclick = async () => {
  const status = $("#thesis-raw-status");
  try {
    const r = await api("/api/thesis", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: $("#thesis-text").value }),
    });
    syncThesis(r);
    status.textContent = "✓ saved — sections updated"; status.className = "status ok";
    toast("Thesis saved (raw YAML)");
  } catch (e) { status.textContent = "✗ " + e.message; status.className = "status err"; toast(e.message, true); }
};

/* ---------- backtest ---------- */
function renderBacktest() {
  const box = $("#bt-result");
  const bt = state.backtest;
  if (!bt) { box.innerHTML = '<div class="empty">No backtest yet — run it above.</div>'; return; }
  const emoji = { GREEN: "🟢", YELLOW: "🟡", RED: "🔴" }[bt.decision] || "•";
  const m = bt.metrics || {};
  const mc = (val, label, tip) => `<div class="metric-card"><div class="m-val">${val}</div><div class="m-label">${label}${tip ? info(tip) : ""}</div></div>`;
  const companies = (bt.companies || []).map((c) => `<tr>
    <td>${esc(c.company)}</td><td>${esc(c.label)}</td><td>${esc(c.channel || "")}</td>
    <td>${c.any_signal ? "yes" : "—"}</td><td>${c.surfaced ? "✅" : "—"}</td>
    <td>${c.lead_days ? c.lead_days + "d" : "—"}</td><td>${esc(c.best_score ?? "")}</td></tr>`).join("");
  box.innerHTML = `
    <div class="decision"><span class="emoji">${emoji}</span>
      <div><div class="d-text">${esc(bt.decision)}${info("Go/no-go on whether sourcing is reliable. Green = works, Yellow = works in part, Red = doesn't. Uses point-in-time data — no look-ahead.")}</div><div class="muted">${esc(bt.reason || "")}</div></div></div>
    <div class="scorecard">
      ${mc(m.recall ?? "—", `recall @≥${m.lead_req_days ?? 14}d lead`, "Of the real deals, the fraction Signal caught at least 14 days early.")}
      ${mc((m.median_lead_days ?? "—") + "d", "median lead time", "For the deals it caught, how early on average.")}
      ${mc(m.precision_proxy ?? "—", "precision proxy", "Of everything it surfaced, the fraction that were actually good deals, not duds.")}
      ${mc(m.no_signal_rate ?? "—", "no-signal rate", "Fraction of real deals with no public footprint at all — nothing could have caught them.")}
    </div>
    <h2 style="font-size:15px">Per-company</h2>
    <table class="grid"><thead><tr><th>Company</th><th>Label${info("a good deal vs a dud")}</th><th>Channel${info("how it reached the fund: public, warm intro, or inbound")}</th><th>Signal${info("did it have any public footprint at the time?", "tr")}</th><th>Surfaced${info("scored ≥ 30 and flagged ≥ 14 days early?", "tr")}</th><th>Lead${info("how many days early", "tr")}</th><th>Best score${info("the top score it earned at the time.", "tr")}</th></tr></thead>
    <tbody>${companies}</tbody></table>`;
}
$("#bt-btn").onclick = async () => {
  const btn = $("#bt-btn"); btn.disabled = true; btn.textContent = "Running…";
  try {
    const r = await api("/api/backtest", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    state.backtest = r.backtest;
    renderBacktest();
    toast(r.backtest ? `Backtest: ${r.backtest.decision}` : "backtest done");
  } catch (e) { toast(e.message, true); }
  finally { btn.disabled = false; btn.textContent = "Run backtest (demo) ▶"; }
};

/* ---------- bootstrap ---------- */
function refreshCounts() {
  $("#nav-digest-count").textContent = state.digest.length || "";
  $("#nav-memos-count").textContent = state.memos.length || "";
}
async function boot() {
  setMode("demo");
  try {
    const s = await api("/api/state");
    state.digest = s.digest || [];
    state.backtest = s.backtest || null;
    state.memos = s.memos || [];
    state.feedback = s.feedback || {};
    state.signals = s.signals || [];
    state.scorer = s.scorer || "?";
    state.providers = s.providers || [];
    state.scorerProvider = localStorage.getItem(LS_SCORER) || "auto";
    state.thesisParsed = s.thesisParsed || null;
    state.thesis = s.thesisParsed ? JSON.parse(JSON.stringify(s.thesisParsed)) : {};
    $("#thesis-text").value = s.thesis || "";
    $("#scorer-pill").textContent = "scorer: " + (s.scorer || "?");
    loadEnabled(state.signals);
    renderSignals();
    renderScorerSelect();
    renderThesis();
    refreshCounts();
  } catch (e) { toast("Failed to load state: " + e.message, true); }
}
boot();
