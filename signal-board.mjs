#!/usr/bin/env node
// Signal project board — zero-dependency CLI over backlog.json.
// Both you and Claude Code use this to view and update project status.
//
//   node signal-board.mjs stats
//   node signal-board.mjs list [--status ready] [--sprint "Sprint 1"] [--epic E1] [--blocked]
//   node signal-board.mjs next
//   node signal-board.mjs show S-02
//   node signal-board.mjs move S-02 inprogress
//   node signal-board.mjs check S-02 3          # toggle subtask 3
//   node signal-board.mjs check S-02 3 done     # or: todo
//   node signal-board.mjs note S-02 "blocked on Neynar key"
//   node signal-board.mjs render [board.html]
//
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const TTY = process.stdout.isTTY;
const c = (code, s) => (TTY ? `\x1b[${code}m${s}\x1b[0m` : s);
const bold = s => c("1", s), dim = s => c("2", s), red = s => c("31", s),
      grn = s => c("32", s), yel = s => c("33", s), blu = s => c("36", s);

function findBacklog() {
  for (const p of [join(process.cwd(), "backlog.json"), join(HERE, "backlog.json")])
    if (existsSync(p)) return p;
  die(`backlog.json not found (looked in ${process.cwd()} and ${HERE}).`);
}
const FILE = findBacklog();
function load() { try { return JSON.parse(readFileSync(FILE, "utf8")); } catch (e) { die(`Could not parse ${FILE}: ${e.message}`); } }
function save(db) {
  db.updated = new Date().toISOString().slice(0, 10);
  writeFileSync(FILE, JSON.stringify(db, null, 2) + "\n");
}
function die(msg) { console.error(red("✗ " + msg)); process.exit(1); }

function parseFlags(args) {
  const flags = {}, pos = [];
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a.startsWith("--")) {
      const k = a.slice(2);
      if (i + 1 < args.length && !args[i + 1].startsWith("--")) { flags[k] = args[++i]; }
      else flags[k] = true;
    } else pos.push(a);
  }
  return { flags, pos };
}

const db = load();
const items = db.items;
const STATUSES = db.meta.statuses;
const WIP = db.meta.wip || {};
const MOS = db.meta.mosOrder || ["Must", "Should", "Could"];
const byId = id => items.find(i => i.id.toLowerCase() === String(id).toLowerCase());
const isDone = it => it.status === "done";
const isBlocked = it => (it.blockedBy || []).some(b => { const d = byId(b); return d && d.status !== "done"; });
const subDone = it => it.subtasks.filter(s => s.done).length;
const statusRank = s => STATUSES.indexOf(s);
const mosRank = m => { const i = MOS.indexOf(m); return i < 0 ? 99 : i; };

const STCOL = { backlog: dim, ready: blu, inprogress: yel, review: yel, done: grn };
const stTag = s => (STCOL[s] || (x => x))(s);
const mosTag = m => (m === "Must" ? red : m === "Should" ? yel : dim)(m);

function fmtLine(it) {
  const blk = isBlocked(it) ? red(" ⛔blocked") : "";
  const prog = it.subtasks.length ? dim(` [${subDone(it)}/${it.subtasks.length}]`) : "";
  return `  ${bold(it.id.padEnd(6))} ${stTag(it.status.padEnd(10))} ${mosTag(it.mos.padEnd(6))} ${String(it.points).padStart(2)}pt  ${it.title}${prog}${blk}`;
}

function cmdList({ flags }) {
  let list = items.slice();
  if (flags.status) list = list.filter(i => i.status === flags.status);
  if (flags.sprint) list = list.filter(i => i.sprint === flags.sprint);
  if (flags.epic) list = list.filter(i => i.epic === String(flags.epic).toUpperCase());
  if (flags.blocked) list = list.filter(isBlocked);
  if (list.length === 0) { console.log(dim("  (no matching items)")); return; }
  list.sort((a, b) => statusRank(a.status) - statusRank(b.status) || mosRank(a.mos) - mosRank(b.mos) || a.points - b.points);
  console.log("");
  list.forEach(i => console.log(fmtLine(i)));
  console.log("");
}

function cmdNext() {
  const pool = items.filter(it => !isDone(it) && it.status !== "review" && !isBlocked(it));
  if (pool.length === 0) { console.log(grn("Nothing actionable — everything is blocked, in review, or done.")); return; }
  pool.sort((a, b) => {
    const rank = s => (s === "inprogress" ? 0 : s === "ready" ? 1 : 2);
    return rank(a.status) - rank(b.status) || mosRank(a.mos) - mosRank(b.mos) || a.points - b.points || a.id.localeCompare(b.id);
  });
  const it = pool[0];
  console.log(bold("\nNext up:"));
  cmdShow({ pos: [it.id] });
}

function cmdShow({ pos }) {
  const it = byId(pos[0]); if (!it) die(`No item '${pos[0]}'.`);
  const ep = db.meta.epics[it.epic];
  console.log("");
  console.log(`${bold(it.id)}  ${bold(it.title)}`);
  console.log(`  ${stTag(it.status)}  ·  ${mosTag(it.mos)}  ·  ${it.points} pts  ·  ${it.sprint}  ·  ${it.epic} ${dim(ep ? ep.name : "")}`);
  if ((it.blockedBy || []).length) {
    const parts = it.blockedBy.map(b => { const d = byId(b); return d && d.status !== "done" ? red(b) : grn(b + "✓"); });
    console.log(`  blocked by: ${parts.join(", ")}${isBlocked(it) ? red("  (BLOCKED)") : grn("  (clear)")}`);
  }
  console.log(bold("\n  Acceptance criteria — done when:"));
  it.criteria.forEach(x => console.log(`    • ${x}`));
  console.log(bold("\n  Action items:"));
  it.subtasks.forEach((s, i) => console.log(`    ${String(i + 1).padStart(2)}. [${s.done ? grn("x") : " "}] ${s.done ? dim(s.text) : s.text}`));
  console.log(dim(`\n  (${subDone(it)}/${it.subtasks.length} done)`));
  if (it.notes) console.log(`\n  ${bold("Notes:")} ${it.notes}`);
  console.log("");
}

function cmdMove({ pos }) {
  const it = byId(pos[0]); if (!it) die(`No item '${pos[0]}'.`);
  const to = pos[1]; if (!STATUSES.includes(to)) die(`Status must be one of: ${STATUSES.join(", ")}`);
  const from = it.status; it.status = to; save(db);
  console.log(`${grn("✓")} ${it.id} ${dim(from)} → ${stTag(to)}`);
  if (WIP[to] !== undefined) {
    const n = items.filter(i => i.status === to).length;
    if (n > WIP[to]) console.log(red(`  ⚠ WIP limit: ${n} items in '${to}' (limit ${WIP[to]}). Finish something before starting more.`));
  }
  if (to === "done" && subDone(it) < it.subtasks.length)
    console.log(yel(`  ⚠ ${it.subtasks.length - subDone(it)} action item(s) still unchecked — is it really done?`));
}

function cmdCheck({ pos }) {
  const it = byId(pos[0]); if (!it) die(`No item '${pos[0]}'.`);
  const n = parseInt(pos[1], 10);
  if (!n || n < 1 || n > it.subtasks.length) die(`Subtask number must be 1..${it.subtasks.length} (see: show ${it.id}).`);
  const sub = it.subtasks[n - 1];
  sub.done = pos[2] ? (pos[2] === "done" || pos[2] === "x" || pos[2] === "true") : !sub.done;
  save(db);
  console.log(`${grn("✓")} ${it.id} · [${sub.done ? grn("x") : " "}] ${sub.text}  ${dim(`(${subDone(it)}/${it.subtasks.length})`)}`);
  if (subDone(it) === it.subtasks.length && it.status !== "done" && it.status !== "review")
    console.log(blu(`  → all action items done. Consider: node signal-board.mjs move ${it.id} review`));
}

function cmdNote({ pos, flags }) {
  const it = byId(pos[0]); if (!it) die(`No item '${pos[0]}'.`);
  const text = pos.slice(1).join(" ");
  if (!text) die(`Provide note text: note ${it.id} "…"`);
  it.notes = flags.append && it.notes ? `${it.notes} | ${text}` : text;
  save(db);
  console.log(`${grn("✓")} ${it.id} note set.`);
}

function cmdStats() {
  const tot = items.length, done = items.filter(isDone).length;
  const ptot = items.reduce((a, i) => a + i.points, 0), pdone = items.filter(isDone).reduce((a, i) => a + i.points, 0);
  const pct = ptot ? Math.round(pdone / ptot * 100) : 0;
  console.log(bold(`\n${db.project} — ${done}/${tot} stories · ${pdone}/${ptot} pts · ${pct}% complete\n`));
  const bar = STATUSES.map(s => {
    const n = items.filter(i => i.status === s).length;
    const cap = WIP[s] !== undefined ? `/${WIP[s]}` : "";
    const over = WIP[s] !== undefined && n > WIP[s];
    return `${stTag(s)} ${over ? red(n + cap) : n + cap}`;
  }).join("   ");
  console.log("  " + bar);
  const blocked = items.filter(isBlocked);
  if (blocked.length) console.log("\n  " + red(`⛔ blocked: ${blocked.map(i => i.id).join(", ")}`));
  console.log("");
}

function cmdRender({ pos }) {
  const out = pos[0] ? resolve(pos[0]) : join(process.cwd(), "board.html");
  writeFileSync(out, renderHTML(db));
  console.log(`${grn("✓")} wrote ${out}  ${dim("(open in a browser; regenerate after edits)")}`);
}

function renderHTML(db) {
  const data = JSON.stringify(db).replace(/</g, "\\u003c");
  return `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>${db.project} — Board (generated)</title>
<style>
:root{--bg:#f6f7f9;--sf:#fff;--sf2:#fbfcfd;--ink:#111418;--mut:#5b6572;--ln:#e4e7ec;--ac:#2563eb;--acb:#eef4ff;--dn:#16a34a;--dg:#be123c;--wn:#b45309;--sh:0 1px 2px rgba(16,24,40,.08)}
@media(prefers-color-scheme:dark){:root{--bg:#0f1216;--sf:#171b21;--sf2:#1c2128;--ink:#e8ebef;--mut:#9aa4b2;--ln:#2a2f37;--ac:#5b8dff;--acb:#182238;--dn:#4ade80;--dg:#fb7185;--wn:#e0a458}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}
.wrap{max-width:1400px;margin:0 auto;padding:18px 18px 60px}h1{font-size:20px;margin:0}.sub{color:var(--mut);font-size:13px;margin:3px 0 0}
.banner{background:var(--acb);border:1px solid var(--ac);color:var(--ink);border-radius:10px;padding:8px 12px;font-size:12.5px;margin:12px 0}
.stats{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.stat{background:var(--sf);border:1px solid var(--ln);border-radius:10px;padding:7px 11px;box-shadow:var(--sh)}
.stat .n{font-size:16px;font-weight:650}.stat .l{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.03em}
.bar{height:7px;border-radius:5px;background:var(--ln);overflow:hidden;margin-top:8px}.bar>i{display:block;height:100%;background:var(--dn)}
.tb{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:10px 0}select,input{font:inherit;color:var(--ink);background:var(--sf);border:1px solid var(--ln);border-radius:8px;padding:6px 9px}
.board{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(230px,1fr);gap:12px;overflow-x:auto;padding:6px 2px 14px;align-items:start}
.col{background:var(--sf2);border:1px solid var(--ln);border-radius:12px;padding:9px;min-height:70px}
.col h2{font-size:12px;margin:2px 4px 9px;display:flex;gap:8px;text-transform:uppercase;letter-spacing:.03em;color:var(--mut)}.col h2 .ct{margin-left:auto;color:var(--ink);font-weight:600}.col.over h2 .ct{color:var(--dg)}
.card{background:var(--sf);border:1px solid var(--ln);border-radius:10px;padding:9px 10px;margin-bottom:9px;box-shadow:var(--sh);cursor:pointer}.card:hover{border-color:var(--ac)}
.r1{display:flex;gap:6px;align-items:center;margin-bottom:3px}.id{font-size:11px;color:var(--mut);font-weight:600}.pts{margin-left:auto;font-size:11px;font-weight:650;background:var(--acb);color:var(--ac);border-radius:6px;padding:1px 6px}
.ti{font-size:13px;font-weight:550;line-height:1.35}.r2{display:flex;gap:6px;align-items:center;margin-top:7px;flex-wrap:wrap}
.mos{font-size:10px;font-weight:700;padding:1px 6px;border-radius:6px;border:1px solid var(--ln)}.mos.Must{color:var(--dg);border-color:var(--dg)}.mos.Should{color:var(--wn);border-color:var(--wn)}.mos.Could{color:var(--mut)}
.chip{font-size:10px;padding:1px 6px;border-radius:999px;border:1px solid var(--ln);background:var(--sf2)}.blk{color:var(--dg);font-size:10px;font-weight:600}.prog{margin-left:auto;font-size:11px;color:var(--mut)}.prog.done{color:var(--dn);font-weight:600}
.dot{width:8px;height:8px;border-radius:50%}.detail{background:var(--sf);border:1px solid var(--ac);border-radius:12px;box-shadow:var(--sh);margin:6px 0 14px;overflow:hidden}
.dh{background:var(--sf2);border-bottom:1px solid var(--ln);padding:13px 15px}.dh h3{margin:0;font-size:15px}.meta{display:flex;gap:6px;flex-wrap:wrap;margin-top:7px}
.db{padding:13px 15px;display:grid;grid-template-columns:1fr 280px;gap:18px}@media(max-width:720px){.db{grid-template-columns:1fr}}
.st{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--mut);font-weight:700;margin:0 0 7px}ul.cr{margin:0 0 14px;padding-left:18px}ul.cr li{margin-bottom:4px}
.subs{list-style:none;margin:0;padding:0}.subs li{display:flex;gap:8px;padding:5px 0;border-bottom:1px dashed var(--ln)}.subs li.d label{color:var(--mut);text-decoration:line-through}
.subs input{width:15px;height:15px;margin-top:3px;accent-color:var(--dn)}.note{background:var(--sf2);border:1px solid var(--ln);border-radius:8px;padding:8px 9px;font-size:13px;white-space:pre-wrap}
.x{margin-left:auto;background:none;border:none;font-size:18px;color:var(--mut);cursor:pointer}.legend{display:flex;gap:8px;flex-wrap:wrap;margin:4px 0}
</style></head><body><div class="wrap">
<h1>${db.project} — Project Board</h1><p class="sub">${db.description || ""}</p>
<div class="banner"><b>Read-only view</b> generated from <code>backlog.json</code> on ${db.updated}. Update via the CLI or Claude Code, then re-run <code>node signal-board.mjs render</code>.</div>
<div class="legend" id="lg"></div><div class="stats" id="stats"></div>
<div class="tb"><label>Sprint <select id="fS"></select></label><label>Epic <select id="fE"></select></label><label>Status <select id="fT"></select></label><input id="fQ" placeholder="Search…"></div>
<div id="detail"></div><div class="board" id="board"></div></div>
<script>const DB=${data};(function(){
const EP=DB.meta.epics,ST=DB.meta.statuses,WIP=DB.meta.wip||{},L={backlog:"Backlog",ready:"Ready",inprogress:"In progress",review:"Review",done:"Done"};
let sel=null,f={s:"",e:"",t:"",q:""};const $=id=>document.getElementById(id);const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const byId=id=>DB.items.find(i=>i.id===id);const blk=it=>(it.blockedBy||[]).some(b=>{const d=byId(b);return d&&d.status!=="done";});const sd=it=>it.subtasks.filter(s=>s.done).length;
function stats(){let t=DB.items.length,d=DB.items.filter(i=>i.status==="done").length,pt=0,pd=0;DB.items.forEach(i=>{pt+=i.points;if(i.status==="done")pd+=i.points;});let pc=pt?Math.round(pd/pt*100):0;
$("stats").innerHTML="<div class='stat'><div class='n'>"+d+"/"+t+"</div><div class='l'>Stories</div></div><div class='stat'><div class='n'>"+pd+"/"+pt+"</div><div class='l'>Points</div></div><div class='stat' style='min-width:150px'><div class='n'>"+pc+"%</div><div class='l'>Complete</div><div class='bar'><i style='width:"+pc+"%'></i></div></div>";}
function legend(){$("lg").innerHTML=Object.keys(EP).map(k=>"<span class='chip'><span class='dot' style='display:inline-block;background:"+EP[k].color+"'></span> "+k+" · "+esc(EP[k].name)+"</span>").join("");}
function match(it){if(f.s&&it.sprint!==f.s)return 0;if(f.e&&it.epic!==f.e)return 0;if(f.t&&it.status!==f.t)return 0;if(f.q&&(it.id+" "+it.title).toLowerCase().indexOf(f.q.toLowerCase())<0)return 0;return 1;}
function card(it){const done=it.subtasks.length&&sd(it)===it.subtasks.length;return "<div class='card' data-id='"+it.id+"'><div class='r1'><span class='id'>"+it.id+"</span><span class='dot' style='background:"+EP[it.epic].color+"'></span><span class='pts'>"+it.points+" pt</span></div><div class='ti'>"+esc(it.title)+"</div><div class='r2'><span class='mos "+it.mos+"'>"+it.mos+"</span><span class='chip'>"+esc(it.sprint)+"</span>"+(blk(it)?"<span class='blk'>⛔ blocked</span>":"")+"<span class='prog"+(done?" done":"")+"'>"+(it.subtasks.length?("✓ "+sd(it)+"/"+it.subtasks.length):"")+"</span></div></div>";}
function board(){$("board").innerHTML=ST.map(s=>{const list=DB.items.filter(i=>i.status===s&&match(i));const over=WIP[s]!==undefined&&list.length>WIP[s];const cap=WIP[s]!==undefined?" / "+WIP[s]:"";return "<div class='col"+(over?" over":"")+"'><h2>"+L[s]+"<span class='ct'>"+list.length+cap+"</span></h2>"+(list.length?list.map(card).join(""):"<div style='color:var(--mut);text-align:center;font-size:12px'>—</div>")+"</div>";}).join("");}
function detail(){const el=$("detail");if(!sel){el.innerHTML="";return;}const it=byId(sel),ep=EP[it.epic];const cr=it.criteria.map(x=>"<li>"+esc(x)+"</li>").join("");const su=it.subtasks.map(s=>"<li class='"+(s.done?"d":"")+"'><input type='checkbox' disabled "+(s.done?"checked":"")+"><label>"+esc(s.text)+"</label></li>").join("");const bb=(it.blockedBy||[]).length?"<span class='chip'>blocked by "+it.blockedBy.join(", ")+"</span>":"";
el.innerHTML="<div class='detail'><div class='dh'><div style='display:flex;align-items:center'><h3>"+it.id+" · "+esc(it.title)+"</h3><button class='x' onclick='__c()'>×</button></div><div class='meta'><span class='chip'><span class='dot' style='display:inline-block;background:"+ep.color+"'></span> "+it.epic+" · "+esc(ep.name)+"</span><span class='chip'>"+esc(it.sprint)+"</span><span class='mos "+it.mos+"'>"+it.mos+"</span><span class='chip'>"+it.points+" pts</span><span class='chip'>"+it.status+"</span>"+bb+"</div></div><div class='db'><div><p class='st'>Acceptance criteria</p><ul class='cr'>"+cr+"</ul><p class='st'>Action items ("+sd(it)+"/"+it.subtasks.length+")</p><ul class='subs'>"+su+"</ul></div><div><p class='st'>Notes</p><div class='note'>"+(it.notes?esc(it.notes):"<span style='color:var(--mut)'>—</span>")+"</div><p class='st' style='margin-top:14px'>Update from terminal</p><div class='note' style='font-family:ui-monospace,Menlo,monospace;font-size:12px'>node signal-board.mjs move "+it.id+" inprogress</div></div></div></div>";if(el.scrollIntoView)el.scrollIntoView({behavior:"smooth",block:"nearest"});}
window.__c=()=>{sel=null;detail();};
document.addEventListener("click",e=>{const cd=e.target.closest(".card");if(cd){sel=cd.getAttribute("data-id");detail();document.querySelectorAll(".card").forEach(x=>x.style.outline="");cd.style.outline="2px solid var(--ac)";}});
function fill(){const sp=[...new Set(DB.items.map(i=>i.sprint))];$("fS").innerHTML="<option value=''>All</option>"+sp.map(s=>"<option>"+esc(s)+"</option>").join("");$("fE").innerHTML="<option value=''>All</option>"+Object.keys(EP).map(k=>"<option value='"+k+"'>"+k+"</option>").join("");$("fT").innerHTML="<option value=''>All</option>"+ST.map(s=>"<option value='"+s+"'>"+L[s]+"</option>").join("");$("fS").onchange=e=>{f.s=e.target.value;board();};$("fE").onchange=e=>{f.e=e.target.value;board();};$("fT").onchange=e=>{f.t=e.target.value;board();};$("fQ").oninput=e=>{f.q=e.target.value;board();};}
legend();stats();fill();board();})();</script></body></html>`;
}

const [cmd, ...rest] = process.argv.slice(2);
const parsed = parseFlags(rest);
const cmds = { list: cmdList, ls: cmdList, next: cmdNext, show: cmdShow, view: cmdShow, move: cmdMove, mv: cmdMove,
  check: cmdCheck, note: cmdNote, stats: cmdStats, status: cmdStats, render: cmdRender };
if (!cmd || cmd === "help" || cmd === "-h" || cmd === "--help") {
  console.log(`${bold("Signal board")} — file-based project tracker over backlog.json

  ${bold("stats")}                     summary + column counts
  ${bold("list")} [--status s] [--sprint x] [--epic E1] [--blocked]
  ${bold("next")}                      the recommended next item to work on
  ${bold("show")} <id>                 full detail (criteria + action items)
  ${bold("move")} <id> <status>        status: ${STATUSES.join(" | ")}
  ${bold("check")} <id> <n> [done|todo] tick action item n (toggle if omitted)
  ${bold("note")} <id> "text" [--append]
  ${bold("render")} [out.html]         regenerate the visual board from the file
`);
  process.exit(0);
}
if (!cmds[cmd]) die(`Unknown command '${cmd}'. Run 'help'.`);
cmds[cmd](parsed);
