// Phone app: Slate, Players, Build, Results, Settings.
import {
  SETTING_FIELDS, loadSettings, saveSettings, resetSettings, loadEdits, saveEdits, emptyEdits,
  loadResults, saveResults, toggleLock, toggleExclude, setOverride, effectivePlayers,
} from "./state.js";
import { SLOTS } from "./optimizer/rules.js";
import { toDkUploadCsv, lineupIdsText } from "./optimizer/csv.js";

const $ = (sel, root = document) => root.querySelector(sel);
const view = $("#view");
const sheet = $("#sheet");

const S = {
  slate: null,
  settings: null,
  edits: emptyEdits(),
  results: null,
  filters: { q: "", pos: "ALL", sort: "proj", showOut: false, game: null },
  build: { running: false, done: 0, total: 0, error: null },
  loadError: null,
};

// ---------------------------------------------------------------- helpers

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const money = (n) => "$" + Number(n).toLocaleString("en-US");
const pts = (n) => (n === null || n === undefined ? "–" : Number(n).toFixed(1));
const time = (iso) => new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
const dayLabel = (ymd) =>
  new Date(ymd + "T12:00:00").toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
const todayYmd = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
function ago(iso) {
  const mins = Math.round((Date.now() - new Date(iso)) / 60000);
  if (mins < 60) return `${Math.max(mins, 0)} min ago`;
  if (mins < 48 * 60) return `${Math.round(mins / 60)} h ago`;
  return `${Math.round(mins / 1440)} days ago`;
}
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (t.hidden = true), 2600);
}
const players = () => effectivePlayers(S.slate?.players ?? [], S.edits);
const playerMap = () => new Map(players().map((p) => [p.id, p]));
function spreadText(g) {
  if (g.homeSpread === null || g.homeSpread === undefined) return "";
  if (g.homeSpread === 0) return "Pick'em";
  return g.homeSpread < 0 ? `${g.home} −${Math.abs(g.homeSpread)}` : `${g.away} −${Math.abs(g.homeSpread)}`;
}
function setEdits(next) {
  S.edits = next;
  saveEdits(S.slate.slateDate, next);
}

// ---------------------------------------------------------------- loading

async function loadSlate() {
  try {
    const r = await fetch("data/slate_latest.json", { cache: "no-cache" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    S.slate = await r.json();
  } catch (e) {
    S.loadError = String(e.message || e);
    return;
  }
  S.settings = loadSettings(S.slate.defaults);
  S.edits = loadEdits(S.slate.slateDate);
  S.results = loadResults(S.slate.slateDate);
}

// ---------------------------------------------------------------- screens

function renderSlate() {
  const sl = S.slate;
  const ps = sl.players;
  const out = ps.filter((p) => p.status === "OUT").length;
  const q = ps.filter((p) => p.status === "Q").length;
  const unmatched = ps.filter((p) => !p.matched).length;
  const noLine = sl.games.filter((g) => g.total === null).length;
  const stale = sl.slateDate < todayYmd();
  return `
    ${stale ? `<div class="card notice">This is the ${esc(dayLabel(sl.slateDate))} slate. Today's hasn't been published yet; check back after about 9:15 AM.</div>` : ""}
    ${noLine ? `<div class="card notice">${noLine} game${noLine > 1 ? "s have" : " has"} no betting line yet, so those players aren't adjusted for Vegas. The 4 PM update usually fills them in.</div>` : ""}
    <h2>${esc(dayLabel(sl.slateDate))} · ${sl.games.length} games</h2>
    <p class="muted small">Projections updated ${esc(time(sl.generatedAt))} (${esc(ago(sl.generatedAt))}) · DK contest group ${esc(sl.draftGroupId)}</p>
    <div class="stats">
      <div class="stat"><b>${ps.length}</b><span>players</span></div>
      <div class="stat"><b>${out}</b><span>OUT</span></div>
      <div class="stat"><b>${q}</b><span>questionable</span></div>
      <div class="stat"><b>${unmatched}</b><span>no stats match</span></div>
    </div>
    <h2>Games</h2>
    ${sl.games.map((g) => `
      <div class="card game" data-game="${esc(g.game)}" role="button" tabindex="0">
        <span class="teams">${esc(g.away)} @ ${esc(g.home)}</span>
        <span class="lock">${esc(time(g.lock))}</span>
        <span class="line">${g.total === null ? "No line yet" : `Total ${g.total} · ${esc(spreadText(g))}`}</span>
        <span class="line" style="text-align:right">${g.total === null ? "" : `${esc(g.away)} ${g.awayTotal} · ${esc(g.home)} ${g.homeTotal}`}</span>
      </div>`).join("")}
    <p class="muted small">Tap a game to see its players.</p>`;
}

const SORTS = {
  proj: { label: "Projection", fn: (a, b) => b.proj - a.proj },
  value: { label: "Value", fn: (a, b) => b.value - a.value },
  salary: { label: "Salary", fn: (a, b) => b.salary - a.salary },
  ceiling: { label: "Ceiling", fn: (a, b) => (b.ceiling ?? 0) - (a.ceiling ?? 0) },
  name: { label: "Name", fn: (a, b) => a.name.localeCompare(b.name) },
};

function badges(p) {
  let b = "";
  if (p.status === "OUT") b += `<span class="badge out">OUT</span>`;
  if (p.status === "Q") b += `<span class="badge q">Q</span>`;
  if (p.locked) b += `<span class="badge lock">LOCK</span>`;
  if (p.excluded) b += `<span class="badge">EXCL</span>`;
  if (p.edited) b += `<span class="badge edit">EDIT</span>`;
  if (!p.matched) b += `<span class="badge nodata" title="No ESPN stats; using DK average">NO DATA</span>`;
  return b;
}

function filteredPlayers() {
  const f = S.filters;
  const q = f.q.trim().toLowerCase();
  return players()
    .filter((p) => f.showOut || p.status !== "OUT" || p.locked)
    .filter((p) => f.pos === "ALL" || p.slots.includes(f.pos))
    .filter((p) => !f.game || p.game === f.game)
    .filter((p) => !q || p.name.toLowerCase().includes(q) || p.team.toLowerCase() === q)
    .sort(SORTS[f.sort].fn);
}

function renderPlayers() {
  const f = S.filters;
  const list = filteredPlayers();
  return `
    <div class="controls">
      <input class="search" id="q" type="search" placeholder="Search name or team" value="${esc(f.q)}" autocomplete="off">
      <div class="chips">
        ${["ALL", "PG", "SG", "SF", "PF", "C"].map((pos) =>
          `<button class="chip" data-pos="${pos}" aria-pressed="${f.pos === pos}">${pos === "ALL" ? "All" : pos}</button>`).join("")}
        <select class="chip" id="sort" aria-label="Sort by">
          ${Object.entries(SORTS).map(([k, s]) => `<option value="${k}" ${f.sort === k ? "selected" : ""}>${s.label}</option>`).join("")}
        </select>
        <button class="chip" id="showOut" aria-pressed="${f.showOut}">Show OUT</button>
        ${f.game ? `<button class="chip" id="clearGame" aria-pressed="true">${esc(f.game)} ✕</button>` : ""}
      </div>
    </div>
    <div id="plistWrap">${playerListHtml(list)}</div>`;
}

function playerListHtml(list) {
  return `
    <p class="muted small">${list.length} player${list.length === 1 ? "" : "s"} · tap one to lock, exclude or edit</p>
    <ul class="plist">
      ${list.map((p) => `
        <li class="prow ${p.status === "OUT" ? "out" : ""} ${p.excluded ? "excluded" : ""}" data-id="${esc(p.id)}">
          <span><span class="pname">${esc(p.name)}</span>${badges(p)}</span>
          <span class="pproj num">${pts(p.proj)}</span>
          <span class="pmeta">${esc(p.team)} vs ${esc(p.opp)} · ${esc(p.pos)} · ${p.minutesShown ?? "–"} min${p.bump >= 1 ? ` <span class="badge bump">+${p.bump} min</span>` : ""}</span>
          <span class="psal num">${money(p.salary)} · ${p.value.toFixed(1)}x</span>
        </li>`).join("")}
    </ul>
    ${list.length ? "" : `<p class="empty">No players match.</p>`}`;
}

function openPlayer(id) {
  const p = playerMap().get(id);
  if (!p) return;
  const projOv = S.edits.proj[id];
  const minOv = S.edits.minutes[id];
  sheet.innerHTML = `
    <button class="close" aria-label="Close" data-close>✕</button>
    <h3>${esc(p.name)}${badges(p)}</h3>
    <p class="muted">${esc(p.team)} vs ${esc(p.opp)} · ${esc(p.slots.filter((s) => s !== "UTIL").join("/"))} · ${money(p.salary)} · locks ${esc(time(p.lock))}</p>
    ${!p.matched ? `<div class="card notice small">No ESPN stats found for this player, so the projection is DraftKings' season average.</div>` : ""}
    <div class="stats">
      <div class="stat"><b>${pts(p.proj)}</b><span>projection</span></div>
      <div class="stat"><b>${pts(p.floor)}</b><span>floor</span></div>
      <div class="stat"><b>${pts(p.ceiling)}</b><span>ceiling</span></div>
      <div class="stat"><b>${p.minutesShown ?? "–"}</b><span>minutes${p.bump >= 1 ? ` (+${p.bump})` : ""}</span></div>
      <div class="stat"><b>${p.value.toFixed(2)}</b><span>pts per $1K</span></div>
      <div class="stat"><b>${pts(p.dkAvg)}</b><span>DK avg</span></div>
    </div>
    <div class="btns" style="margin-top:12px">
      <button class="btn" data-act="lock" aria-pressed="${p.locked}">${p.locked ? "Locked" : "Lock"}</button>
      <button class="btn danger" data-act="exclude" aria-pressed="${p.excluded}">${p.excluded ? "Excluded" : "Exclude"}</button>
    </div>
    <div class="field">
      <label for="ovProj">My projection</label>
      <input id="ovProj" type="number" inputmode="decimal" step="0.5" min="0" placeholder="${pts(p.baseProj)}" value="${projOv ?? ""}">
      <span class="help">Replaces our projection. Leave blank to use ours (${pts(p.baseProj)}).</span>
    </div>
    <div class="field">
      <label for="ovMin">My minutes</label>
      <input id="ovMin" type="number" inputmode="decimal" step="1" min="0" max="48" placeholder="${p.minutes ?? ""}" value="${minOv ?? ""}">
      <span class="help">Scales the projection by your minutes ÷ ours (${p.minutes ?? "–"}). A projection above overrides this.</span>
    </div>
    <div class="btns" style="margin-top:12px">
      <button class="btn" data-act="reset" ${p.edited || p.locked || p.excluded ? "" : "disabled"}>Reset this player</button>
      <button class="btn primary" data-close>Done</button>
    </div>`;
  sheet.dataset.id = id;
  if (!sheet.open) sheet.showModal();
}

function renderBuild() {
  const st = S.settings;
  const b = S.build;
  const n = st.cash_lineups;
  const ps = players();
  const locked = ps.filter((p) => p.locked).length;
  const excluded = ps.filter((p) => p.excluded).length;
  const edited = ps.filter((p) => p.edited).length;
  return `
    <h2>Mode</h2>
    <div class="seg">
      <button aria-pressed="true">Cash</button>
      <button disabled title="Coming in the next update">Tournament (soon)</button>
    </div>
    <h2>Options</h2>
    <div class="field">
      <label for="nLineups">Lineups</label>
      <input id="nLineups" type="number" inputmode="numeric" min="1" max="${st.cash_max_lineups}" step="1" value="${n}">
      <span class="help">1 to ${st.cash_max_lineups}. Most cash players use 1.</span>
    </div>
    <div class="field" ${n > 1 ? "" : "hidden"}>
      <label for="minUnique">Players different</label>
      <input id="minUnique" type="number" inputmode="numeric" min="1" max="8" step="1" value="${st.cash_min_unique}">
      <span class="help">Each lineup differs from every other by at least this many players.</span>
    </div>
    <div class="field">
      <label for="floorW">Floor weight <span class="muted num" id="floorWVal">${st.cash_floor_weight}</span></label>
      <input id="floorW" type="range" min="0" max="1" step="0.05" value="${st.cash_floor_weight}">
      <span class="help">0 = pick the highest projection. Higher = prefer safer players.</span>
    </div>
    <p class="muted small">Your edits: ${locked} locked · ${excluded} excluded · ${edited} edited. <a href="#players">Change</a></p>
    <button class="btn primary big" id="buildBtn" ${b.running ? "disabled" : ""}>${b.running ? "Building…" : `Build ${n} lineup${n > 1 ? "s" : ""}`}</button>
    <div class="progress" ${b.running ? "" : "hidden"}><div style="width:${b.total ? (100 * b.done) / b.total : 5}%"></div></div>
    ${b.error ? `<div class="card notice bad" style="margin-top:12px">${esc(b.error)}</div>` : ""}`;
}

function renderResults() {
  const r = S.results;
  if (!r) return `<p class="empty">No lineups yet. Go to <a href="#build">Build</a>.</p>`;
  const map = new Map((S.slate.players ?? []).map((p) => [p.id, p]));
  const n = r.lineups.length;
  return `
    ${r.stopReason ? `<div class="card notice">${esc(r.stopReason)}</div>` : ""}
    ${(r.warnings || []).map((w) => `<div class="card notice">${esc(w)}</div>`).join("")}
    <p class="muted small">${n} lineup${n === 1 ? "" : "s"} · built ${esc(time(r.builtAt))} in ${r.seconds}s${r.editsChanged ? " · <b>edits changed since this build</b>" : ""}</p>
    ${n ? `<div class="btns" style="margin-bottom:12px">
      <button class="btn primary" id="dlCsv">Download CSV</button>
      ${navigator.canShare ? `<button class="btn" id="shareCsv">Share</button>` : ""}
      <button class="btn" id="copyIds">Copy IDs</button>
    </div>` : ""}
    ${r.lineups.map((lu, i) => `
      <div class="card lineup">
        <div class="head"><span>#${i + 1}</span><span class="num">${pts(lu.proj)} pts · ${money(lu.salary)}</span></div>
        <table>${lu.ids.map((id, k) => {
          const p = map.get(id) || { name: id, team: "", salary: 0 };
          const lock = S.edits.locks.includes(id) ? ` <span class="badge lock">LOCK</span>` : "";
          return `<tr><td class="slot">${SLOTS[k]}</td><td>${esc(p.name)} <span class="muted small">${esc(p.team)}</span>${lock}</td>
            <td class="r num muted">${money(p.salary)}</td><td class="r num" style="width:52px">${pts(lu.projs?.[k])}</td></tr>`;
        }).join("")}</table>
      </div>`).join("")}
    ${n > 1 ? `<h2>Exposure</h2><div class="card"><table style="width:100%">${r.exposure.map((e) =>
      `<tr><td>${esc(e.name)}</td><td class="r num muted">${e.count}/${n}</td><td class="r num" style="width:52px">${Math.round(e.pct)}%</td></tr>`).join("")}</table></div>` : ""}`;
}

function renderSettings() {
  const st = S.settings;
  const d = S.slate.defaults || {};
  return `
    <h2>Lineup builder</h2>
    ${SETTING_FIELDS.map((f) => `
      <div class="field">
        <label for="set_${f.key}">${esc(f.label)}</label>
        <input id="set_${f.key}" data-key="${f.key}" type="number" inputmode="decimal" min="${f.min}" max="${f.max}" step="${f.step}" value="${st[f.key]}">
        <span class="help">${esc(f.help)} Default ${d[f.key] ?? "–"}.</span>
      </div>`).join("")}
    <div class="btns" style="margin-top:12px">
      <button class="btn" id="resetSettings">Reset to defaults</button>
      <button class="btn" id="clearEdits">Clear today's edits</button>
    </div>
    <h2>About</h2>
    <p class="muted small">Salary file ${esc(S.slate.salaryFile)}. Projections, lines and settings defaults come from the daily pipeline;
      your edits stay on this phone and reset each slate. Version b91ae172e0.</p>`;
}

// ---------------------------------------------------------------- build

let worker = null;
function getWorker() {
  if (!worker) {
    worker = new Worker(new URL("./worker.js?v=b91ae172e0", import.meta.url), { type: "module" });
    worker.onmessage = onWorkerMessage;
    worker.onerror = (e) => {
      S.build = { running: false, done: 0, total: 0, error: `The lineup builder crashed: ${e.message || "unknown error"}` };
      worker = null;
      render();
    };
  }
  return worker;
}

let buildSnapshot = null;
function startBuild() {
  const st = S.settings;
  const options = {
    mode: "cash",
    count: st.cash_lineups,
    minUnique: st.cash_min_unique,
    floorWeight: st.cash_floor_weight,
    locks: S.edits.locks,
    excludes: S.edits.excludes,
  };
  // Overrides are already folded into the players' projections.
  const ps = players().map(({ id, name, team, opp, game, salary, slots, proj, floor, ceiling, status }) =>
    ({ id, name, team, opp, game, salary, slots, proj, floor, ceiling, status }));
  buildSnapshot = { edits: JSON.stringify(S.edits), projs: new Map(ps.map((p) => [p.id, p.proj])) };
  S.build = { running: true, done: 0, total: options.count, error: null };
  render();
  getWorker().postMessage({ type: "build", players: ps, options });
}

function onWorkerMessage(e) {
  const m = e.data;
  if (m.type === "progress") {
    S.build.done = m.done;
    const bar = $(".progress > div");
    if (bar) bar.style.width = `${(100 * m.done) / m.total}%`;
    return;
  }
  if (m.type === "error") {
    S.build = { running: false, done: 0, total: 0, error: m.message };
    render();
    return;
  }
  if (m.type === "done") {
    const r = m.result;
    S.build = { running: false, done: 0, total: 0, error: r.lineups.length ? null : r.stopReason };
    if (!r.lineups.length) return render();
    S.results = {
      ...r,
      builtAt: new Date().toISOString(),
      edits: buildSnapshot.edits,
      lineups: r.lineups.map((l) => ({ ...l, projs: l.ids.map((id) => buildSnapshot.projs.get(id)) })),
    };
    saveResults(S.slate.slateDate, S.results);
    location.hash = "#results";
  }
}

// ---------------------------------------------------------------- export

function csvFile() {
  const csv = toDkUploadCsv(S.results.lineups.map((l) => l.ids));
  const name = `DK_NBA_${S.slate.slateDate}_${S.results.lineups.length}lineups.csv`;
  return { csv, name };
}
function downloadCsv() {
  const { csv, name } = csvFile();
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
  toast("CSV downloaded. Upload it on DraftKings: Lineups → Upload Lineups.");
}
async function shareCsv() {
  const { csv, name } = csvFile();
  const file = new File([csv], name, { type: "text/csv" });
  try {
    if (navigator.canShare?.({ files: [file] })) await navigator.share({ files: [file], title: name });
    else downloadCsv();
  } catch (e) {
    if (e.name !== "AbortError") toast("Couldn't share; try Download instead.");
  }
}
async function copyIds() {
  try {
    await navigator.clipboard.writeText(lineupIdsText(S.results.lineups.map((l) => l.ids)));
    toast("Player IDs copied.");
  } catch {
    toast("Couldn't copy on this browser.");
  }
}

// ---------------------------------------------------------------- render + events

const SCREENS = { slate: renderSlate, players: renderPlayers, build: renderBuild, results: renderResults, settings: renderSettings };

function currentView() {
  const v = location.hash.slice(1);
  return SCREENS[v] ? v : "slate";
}

function render() {
  const v = currentView();
  document.querySelectorAll(".tabs a").forEach((a) => a.classList.toggle("active", a.dataset.view === v));
  if (S.loadError) {
    view.innerHTML = `<div class="card notice bad">Couldn't load the slate (${esc(S.loadError)}). Check your connection and pull down to refresh.</div>`;
    return;
  }
  if (!S.slate) return;
  $("#subtitle").textContent = `${dayLabel(S.slate.slateDate)} · ${S.slate.games.length} games`;
  if (S.results) S.results.editsChanged = S.results.edits !== JSON.stringify(S.edits);
  const keepScroll = v === "players" ? window.scrollY : 0;
  view.innerHTML = SCREENS[v]();
  if (v === "players") window.scrollTo(0, keepScroll);
}

view.addEventListener("click", (e) => {
  const t = e.target.closest("[data-game],[data-id],[data-pos],#showOut,#clearGame,#buildBtn,#dlCsv,#shareCsv,#copyIds,#resetSettings,#clearEdits");
  if (!t) return;
  if (t.dataset.game) {
    S.filters.game = t.dataset.game;
    location.hash = "#players";
  } else if (t.dataset.id) openPlayer(t.dataset.id);
  else if (t.dataset.pos) { S.filters.pos = t.dataset.pos; render(); }
  else if (t.id === "showOut") { S.filters.showOut = !S.filters.showOut; render(); }
  else if (t.id === "clearGame") { S.filters.game = null; render(); }
  else if (t.id === "buildBtn") startBuild();
  else if (t.id === "dlCsv") downloadCsv();
  else if (t.id === "shareCsv") shareCsv();
  else if (t.id === "copyIds") copyIds();
  else if (t.id === "resetSettings") {
    resetSettings();
    S.settings = loadSettings(S.slate.defaults);
    render();
    toast("Settings reset to defaults.");
  } else if (t.id === "clearEdits") {
    if (confirm("Clear all locks, excludes and edits for this slate?")) {
      setEdits(emptyEdits());
      render();
      toast("Edits cleared.");
    }
  }
});

view.addEventListener("input", (e) => {
  const t = e.target;
  if (t.id === "q") {
    // Only redraw the list so the search box (and the phone keyboard) stay put.
    S.filters.q = t.value;
    $("#plistWrap").innerHTML = playerListHtml(filteredPlayers());
  }
  else if (t.id === "floorW") {
    S.settings.cash_floor_weight = Number(t.value);
    $("#floorWVal").textContent = t.value;
    saveSettings(S.settings, S.slate.defaults);
  }
});

view.addEventListener("change", (e) => {
  const t = e.target;
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, Math.round(Number(v) || lo)));
  if (t.id === "sort") { S.filters.sort = t.value; render(); }
  else if (t.id === "nLineups") {
    S.settings.cash_lineups = clamp(t.value, 1, S.settings.cash_max_lineups);
    saveSettings(S.settings, S.slate.defaults);
    render();
  } else if (t.id === "minUnique") {
    S.settings.cash_min_unique = clamp(t.value, 1, 8);
    saveSettings(S.settings, S.slate.defaults);
  } else if (t.dataset.key) {
    const f = SETTING_FIELDS.find((x) => x.key === t.dataset.key);
    const v = Math.min(f.max, Math.max(f.min, Number(t.value)));
    if (Number.isFinite(v)) S.settings[f.key] = v;
    t.value = S.settings[f.key];
    saveSettings(S.settings, S.slate.defaults);
  }
});

sheet.addEventListener("click", (e) => {
  const id = sheet.dataset.id;
  if (e.target === sheet || e.target.closest("[data-close]")) { sheet.close(); return; }
  const act = e.target.closest("[data-act]")?.dataset.act;
  if (!act) return;
  if (act === "lock") setEdits(toggleLock(S.edits, id));
  if (act === "exclude") setEdits(toggleExclude(S.edits, id));
  if (act === "reset") {
    let ed = { ...S.edits, locks: S.edits.locks.filter((x) => x !== id), excludes: S.edits.excludes.filter((x) => x !== id) };
    ed = setOverride(setOverride(ed, "proj", id, ""), "minutes", id, "");
    setEdits(ed);
  }
  openPlayer(id);
  render();
});
sheet.addEventListener("change", (e) => {
  const id = sheet.dataset.id;
  if (e.target.id === "ovProj") setEdits(setOverride(S.edits, "proj", id, e.target.value));
  if (e.target.id === "ovMin") setEdits(setOverride(S.edits, "minutes", id, e.target.value));
  openPlayer(id);
  render();
});
sheet.addEventListener("close", () => render());

window.addEventListener("hashchange", () => {
  window.scrollTo(0, 0);
  render();
});

// ---------------------------------------------------------------- start

if ("serviceWorker" in navigator && location.protocol === "https:") {
  navigator.serviceWorker.register("sw.js").catch(() => {});
}
await loadSlate();
render();
if (S.slate) getWorker().postMessage({ type: "warmup" }); // load the solver early
