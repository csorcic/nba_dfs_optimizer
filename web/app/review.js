// Review screen: how the last slates went (hindsight-optimal lineup vs ours, smash plays,
// lineup make-up, contest results and lessons once they exist). Pure HTML builders so the
// node tests can check them without a browser. Data comes from docs/data/review_*.json.

const MISS_HELP = {
  "in our lineup": "we played him",
  "projection miss": "scored far above our ceiling",
  "settings miss": "our range covered it, but we ranked him low",
  "close call": "we ranked him well; the optimizer used someone else",
};

export async function loadReviewIndex(fetchFn = fetch) {
  const r = await fetchFn("data/review_index.json", { cache: "no-cache" });
  if (!r.ok) throw new Error(r.status === 404 ? "none" : `HTTP ${r.status}`);
  return r.json();
}

export async function loadReview(date, fetchFn = fetch) {
  const r = await fetchFn(`data/review_${date}.json`, { cache: "no-cache" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function loadLessons(fetchFn = fetch) {
  try {
    const r = await fetchFn("data/lessons.json", { cache: "no-cache" });
    return r.ok ? r.json() : null;
  } catch {
    return null;
  }
}

/**
 * @param {{index:object|null, doc:object|null, lessons:object|null, error:string|null, loading:boolean}} R
 * @param {{esc:Function, money:Function, pts:Function, dayLabel:Function}} f
 */
export function reviewHtml(R, f) {
  const { esc, money, pts, dayLabel } = f;
  if (R.error === "none" || (R.index && !R.index.dates.length)) {
    return `<p class="empty">No slate reviews yet. The first one appears the morning after a slate's games finish.</p>`;
  }
  if (R.error) return `<div class="card notice bad">Couldn't load the review (${esc(R.error)}). If you're offline, open a date you've viewed before.</div>`;
  if (!R.index || !R.doc) return `<p class="empty">Loading review…</p>`;
  const d = R.doc;
  const s = d.standing;
  const opt = d.optimal;
  const pct = (n) => (n === null || n === undefined ? "–" : `${Math.round(n)}%`);

  const picker = `<label class="rpick"><span>Slate</span>
    <select id="reviewDate">${R.index.dates.map((x) =>
      `<option value="${esc(x.date)}"${x.date === d.gameDate ? " selected" : ""}>${esc(dayLabel(x.date))}${x.pctOfOptimal !== null && x.pctOfOptimal !== undefined ? ` · ours ${pct(x.pctOfOptimal)} of best` : ""}</option>`).join("")}
    </select></label>`;

  const rebuilt = d.projections.source === "rebuilt"
    ? `<div class="card notice">Rebuilt projections: no pre-lock snapshot was saved for this slate, so these numbers are a replay and look a bit better than reality.</div>` : "";

  const contestBlock = (d.contests || []).map((c) => `
    <div class="card">
      <div class="head"><b>${esc(c.name || "Contest")}</b><span class="muted small">${Number(c.fieldSize).toLocaleString("en-US")} entries</span></div>
      <div class="stats">
        <div class="stat"><b>${pts(c.winningScore)}</b><span>winning score</span></div>
        <div class="stat"><b>${pts(c.top1Score)}</b><span>top 1%</span></div>
        <div class="stat"><b>${pts(c.cashLine)}</b><span>cash line (approx.)</span></div>
        <div class="stat"><b>${c.mine && c.mine.best ? `${pct(c.mine.best.percentile)}` : "–"}</b><span>${c.mine && c.mine.best ? `my best: ${pts(c.mine.best.points)} pts, rank ${c.mine.best.rank}` : "my best finish"}</span></div>
      </div>
    </div>`).join("");

  const missCounts = {};
  opt.players.forEach((p) => (missCounts[p.missType] = (missCounts[p.missType] || 0) + 1));

  const lineupTable = (players, withWhy) => `<table class="rtable">
      <tr class="muted small"><th>Slot</th><th>Player</th><th class="r">Actual</th><th class="r">Proj</th>${withWhy ? `<th class="r">Ceil</th><th class="r">Own</th>` : ""}</tr>
      ${players.map((p) => `<tr>
        <td class="slot">${esc(p.slot)}</td>
        <td>${esc(p.name)} <span class="muted small">${esc(p.team)} ${money(p.salary)}</span>${withWhy ? `<div class="why ${esc(p.missType.replace(/ /g, "-"))}">${esc(p.missType)}</div>` : ""}</td>
        <td class="r num"><b>${pts(p.actual)}</b></td><td class="r num">${pts(p.proj)}</td>
        ${withWhy ? `<td class="r num muted">${pts(p.ceiling)}</td><td class="r num muted">${pct(p.own)}</td>` : ""}
      </tr>`).join("")}
    </table>`;

  const comps = [["Best lineup", opt.composition], ["Ours", d.ours.composition]];
  const top = d.topN.composition || {};
  const row = (label, fn, topVal) => `<tr><td>${label}</td>${comps.map(([, c]) => `<td class="r num">${fn(c)}</td>`).join("")}<td class="r num muted">${topVal ?? "–"}</td></tr>`;
  const yesNo = (v) => (v === null || v === undefined ? "–" : v ? "yes" : "no");
  const composition = `<table class="rtable">
      <tr class="muted small"><th></th>${comps.map(([n]) => `<th class="r">${n}</th>`).join("")}<th class="r">Top ${d.topN.count} avg</th></tr>
      ${row("Salary used", (c) => money(c.salary), top.avgSalary ? money(Math.round(top.avgSalary)) : null)}
      ${row(`Stars (${money(d.settings.star_salary)}+)`, (c) => c.stars, top.avgStars)}
      ${row(`Value (under ${money(d.settings.value_salary)})`, (c) => c.values, top.avgValues)}
      ${row("Most from one game", (c) => `${c.maxFromOneGame} <span class="muted small">${esc(c.maxGame)}</span>`, top.avgMaxFromOneGame)}
      ${row("…was the highest total", (c) => yesNo(c.maxGameIsHighestTotal), top.pctMaxGameIsHighestTotal !== null && top.pctMaxGameIsHighestTotal !== undefined ? pct(top.pctMaxGameIsHighestTotal) : null)}
      ${row("Teams used", (c) => c.teamCount, top.avgTeamCount)}
      ${row("Total est. ownership", (c) => pct(c.ownSum), top.avgOwnSum !== undefined ? pct(top.avgOwnSum) : null)}
    </table>`;

  const smash = d.smash.length ? `<table class="rtable">
      <tr class="muted small"><th>Player</th><th class="r">Actual</th><th class="r">Proj</th><th class="r">Own</th><th class="r">Team tot</th></tr>
      ${d.smash.map((x) => `<tr>
        <td>${esc(x.name)} <span class="muted small">${esc(x.team)} ${esc(x.pos)} ${money(x.salary)}${x.minutesBump >= 1 ? ` · +${pts(x.minutesBump)} min bump` : ""}</span></td>
        <td class="r num"><b>${pts(x.actual)}</b><div class="muted small">${pts(x.multiple)}x</div></td>
        <td class="r num">${pts(x.proj)}<div class="muted small">ceil ${pts(x.ceiling)}</div></td>
        <td class="r num muted">${pct(x.own)}</td><td class="r num muted">${pts(x.teamImplied)}</td></tr>`).join("")}
    </table>` : `<p class="muted small">Nobody reached ${d.settings.smash_multiplier}x their salary.</p>`;

  const a = d.accuracy;
  const extras = [
    d.lateScratches.length ? `<details class="card"><summary>Late scratches (${d.lateScratches.length})</summary><p class="small">${d.lateScratches.map((x) => `${esc(x.name)} (${esc(x.team)}, proj ${pts(x.proj)})`).join(", ")}</p></details>` : "",
    d.noResult.length ? `<details class="card"><summary>No result found (${d.noResult.length})</summary><p class="small">${d.noResult.map((x) => `${esc(x.name)} (${esc(x.team)})`).join(", ")}</p><p class="muted small">Usually rookies or deep bench players who didn't play. Counted as 0.</p></details>` : "",
  ].join("");

  return `
    ${picker}
    ${rebuilt}
    <div class="stats two">
      <div class="stat"><b>${pts(s.optimalActual)}</b><span>best possible</span></div>
      <div class="stat"><b>${pts(s.ourActual)}</b><span>our top lineup (${pct(s.pctOfOptimal)})</span></div>
      <div class="stat"><b>${pts(a.mae)}</b><span>avg projection miss</span></div>
      <div class="stat"><b>${a.bias === null ? "–" : Math.abs(a.bias) < 0.05 ? "0.0" : (a.bias > 0 ? "+" : "") + pts(a.bias)}</b><span>bias (+ = too high)</span></div>
    </div>
    ${contestBlock ? `<h2>Contests</h2>${contestBlock}` : ""}
    <h2>Best possible lineup</h2>
    <p class="muted small">Our projections had this lineup at ${pts(s.optimalOurProj)}, ${pts(s.projGap)} below our top lineup (${pts(s.ourProj)}). ${s.overlap ?? 0} of 8 players were in ours.</p>
    <div class="card">${lineupTable(opt.players, true)}</div>
    <p class="muted small">${Object.entries(missCounts).map(([k, n]) => `<b>${n}× ${esc(k)}</b>: ${esc(MISS_HELP[k] || "")}`).join(" · ")}</p>
    <h2>Our top projected lineup</h2>
    <div class="card">${lineupTable(d.ours.players, false)}</div>
    <h2>Smash plays (${d.settings.smash_multiplier}x salary)</h2>
    <div class="card">${smash}</div>
    <h2>Lineup make-up</h2>
    <div class="card">${composition}</div>
    ${extras}
    <p class="muted small">Projection accuracy: ${a.players} players who played · ${pct(a.overCeilingPct)} beat their ceiling (target about 10%) · ${pct(a.insideRangePct)} landed inside floor–ceiling (target about 80%).</p>
    ${lessonsHtml(R.lessons, f)}`;
}

/** Lessons across all slates (Phase D). Recommendations only; nothing is changed automatically. */
export function lessonsHtml(L, f) {
  if (!L) return "";
  const { esc } = f;
  const early = L.tooEarly ? `<div class="card notice">Too early to act on: ${L.slates} of ${L.minSlates} slates so far. Numbers are shown for interest only.</div>` : "";
  const recs = (L.recommendations || []).map((r) => `<div class="card">
      <b>${esc(r.title)}</b>
      <p class="small">${esc(r.detail)}</p>
      ${r.before !== undefined ? `<p class="small num">Before: ${esc(r.before)} → After: ${esc(r.after)}</p>` : ""}
    </div>`).join("");
  const notes = (L.highlights || []).map((h) => `<li>${esc(h)}</li>`).join("");
  return `<h2>Lessons across ${L.slates} slate${L.slates === 1 ? "" : "s"}</h2>
    ${early}
    ${notes ? `<div class="card"><ul class="small">${notes}</ul></div>` : ""}
    ${recs || `<p class="muted small">No recommended changes yet.</p>`}
    <p class="muted small">Recommendations only. Nothing changes until you approve it.</p>`;
}
