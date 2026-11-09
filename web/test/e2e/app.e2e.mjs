// End-to-end check of the built app in a phone-sized Chromium.
//   node test/e2e/app.e2e.mjs [--shots DIR]
// Serves docs/ locally, walks every screen, builds cash lineups, downloads the CSV
// and checks it against the DK upload format and the rule validator.
import { createServer } from "node:http";
import { readFileSync, mkdirSync, existsSync } from "node:fs";
import { extname, join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { validateLineup } from "../../src/optimizer/rules.js";

const require = createRequire(import.meta.url);
const { chromium, devices } = require("playwright");

const DOCS = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "docs");
const shotsArg = process.argv.indexOf("--shots");
const SHOTS = shotsArg > 0 ? process.argv[shotsArg + 1] : null;
if (SHOTS) mkdirSync(SHOTS, { recursive: true });

const TYPES = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css",
  ".json": "application/json", ".wasm": "application/wasm", ".png": "image/png", ".webmanifest": "application/manifest+json" };
const server = createServer((req, res) => {
  let p = decodeURIComponent(new URL(req.url, "http://x").pathname);
  if (p.endsWith("/")) p += "index.html";
  const f = join(DOCS, p);
  if (!f.startsWith(DOCS) || !existsSync(f)) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { "content-type": TYPES[extname(f)] || "application/octet-stream" });
  res.end(readFileSync(f));
}).listen(0);
const base = `http://127.0.0.1:${server.address().port}/`;

const browser = await chromium.launch();
const ctx = await browser.newContext({ ...devices["Pixel 7"], acceptDownloads: true, timezoneId: "America/Chicago" });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
const shot = async (name) => SHOTS && page.screenshot({ path: join(SHOTS, `${name}.png`) });
const slate = JSON.parse(readFileSync(join(DOCS, "data", "slate_latest.json"), "utf8"));
const byId = new Map(slate.players.map((p) => [p.id, p]));

try {
  // Slate
  await page.goto(base);
  await page.waitForSelector(".game");
  assert.equal(await page.locator(".game").count(), slate.games.length);
  await shot("1-slate");

  // Players: search, lock one, exclude one, override one
  await page.click('a[data-view="players"]');
  await page.waitForSelector(".prow");
  const total = await page.locator(".prow").count();
  assert.ok(total > 50, `only ${total} players listed`);
  await shot("2-players");
  const top = slate.players.filter((p) => p.status !== "OUT").sort((a, b) => b.proj - a.proj);
  const toExclude = top[0];
  const toLock = top.find((p) => p.salary <= 5000 && p.proj > 10);
  await page.fill("#q", toLock.name.split(" ")[1]);
  await page.click(`.prow[data-id="${toLock.id}"]`);
  await page.waitForSelector("#sheet[open]");
  await shot("3-player-sheet");
  await page.click('[data-act="lock"]');
  await page.click("#sheet [data-close].btn");
  await page.fill("#q", toExclude.name.split(" ").slice(-1)[0]);
  await page.click(`.prow[data-id="${toExclude.id}"]`);
  await page.click('[data-act="exclude"]');
  await page.click("#sheet [data-close].btn");
  await page.fill("#q", "");
  assert.equal(await page.locator(".badge.lock").count(), 1);

  // Edits survive a reload
  await page.reload();
  await page.click('a[data-view="players"]');
  await page.waitForSelector(".badge.lock");

  // Build 3 cash lineups
  await page.click('a[data-view="build"]');
  await page.fill("#opt_cash_lineups", "3");
  
  await page.locator("#opt_cash_lineups").blur();
  await shot("4-build");
  const t0 = Date.now();
  await page.click("#buildBtn");
  await page.waitForSelector(".lineup", { timeout: 60000 });
  console.log(`built 3 lineups in the browser in ${Date.now() - t0} ms`);
  assert.equal(await page.locator(".lineup").count(), 3);
  await shot("5-results");

  // Download CSV and check it
  const [download] = await Promise.all([page.waitForEvent("download"), page.click("#dlCsv")]);
  const csv = readFileSync(await download.path(), "utf8");
  const rows = csv.trimEnd().split("\r\n");
  assert.equal(rows[0], "PG,SG,SF,PF,C,G,F,UTIL");
  assert.equal(rows.length, 4);
  for (const row of rows.slice(1)) {
    const ids = row.split(",");
    const v = validateLineup(ids, byId);
    assert.ok(v.valid, v.errors.join("; "));
    assert.ok(ids.includes(toLock.id), "locked player missing");
    assert.ok(!ids.includes(toExclude.id), "excluded player used");
  }
  console.log(`CSV ok: ${download.suggestedFilename()}`);

  // Tournament: 20 lineups, 3-player stack with bring-back, a minimum exposure on one player
  await page.click('a[data-view="players"]');
  await page.click('.chip[data-pos="ALL"]');
  await page.fill("#q", "");
  const minPlayer = slate.players.filter((p) => p.status !== "OUT" && p.salary <= 4500 && p.proj > 12)
    .find((p) => p.id !== toLock.id && p.id !== toExclude.id);
  await page.fill("#q", minPlayer.name.split(" ").slice(-1)[0]);
  await page.click(`.prow[data-id="${minPlayer.id}"]`);
  await page.fill("#expMin", "60");
  await page.locator("#expMin").blur();
  await page.click("#sheet [data-close].btn");
  await page.fill("#q", "");
  await page.click('a[data-view="build"]');
  await page.click('[data-mode="gpp"]');
  await page.fill("#opt_gpp_lineups", "20");
  await page.locator("#opt_gpp_lineups").blur();
  await page.fill("#opt_stack_min_players", "3");
  await page.locator("#opt_stack_min_players").blur();
  await page.check("#bringBack");
  await shot("7-build-gpp");
  await page.click("#buildBtn");
  await page.waitForFunction(() => document.querySelectorAll(".lineup").length === 20, null, { timeout: 120000 });
  await shot("8-results-gpp");
  const [dl2] = await Promise.all([page.waitForEvent("download"), page.click("#dlCsv")]);
  const rows2 = readFileSync(await dl2.path(), "utf8").trimEnd().split("\r\n").slice(1).map((r) => r.split(","));
  assert.equal(rows2.length, 20);
  const count = new Map();
  for (const ids of rows2) {
    const v = validateLineup(ids, byId);
    assert.ok(v.valid, v.errors.join("; "));
    assert.ok(ids.includes(toLock.id) && !ids.includes(toExclude.id));
    ids.forEach((id) => count.set(id, (count.get(id) || 0) + 1));
    const games = new Map();
    ids.forEach((id) => { const g = byId.get(id).game; games.set(g, (games.get(g) || 0) + 1); });
    assert.ok(Math.max(...games.values()) >= 3, "no 3-player stack");
  }
  for (const [id, c] of count) if (id !== toLock.id && id !== minPlayer.id) assert.ok(c <= 10, `${byId.get(id).name} in ${c}/20`);
  assert.ok((count.get(minPlayer.id) || 0) >= 12, `min-exposure player in ${count.get(minPlayer.id) || 0}/20`);
  for (let i = 0; i < rows2.length; i++) for (let j = 0; j < i; j++)
    assert.ok(rows2[i].filter((id) => rows2[j].includes(id)).length <= 5, "uniqueness");
  console.log("GPP CSV ok: 20 lineups, stack, exposure, uniqueness");

  // Speed: 150 tournament lineups with the CPU slowed 4x (roughly a mid-range Android phone)
  if (process.argv.includes("--bench")) {
    await page.click('a[data-view="build"]');
    await page.fill("#opt_stack_min_players", "0");
    await page.locator("#opt_stack_min_players").blur();
    await page.fill("#opt_gpp_lineups", "150");
    await page.locator("#opt_gpp_lineups").blur();
    const cdp = await ctx.newCDPSession(page);
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
    const t1 = Date.now();
    await page.click("#buildBtn");
    await page.waitForFunction(() => document.querySelectorAll(".lineup").length === 150, null, { timeout: 600000 });
    console.log(`150 GPP lineups with 4x CPU slowdown: ${((Date.now() - t1) / 1000).toFixed(1)} s`);
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 });
  }

  // Settings
  await page.click('a[data-view="settings"]');
  await page.waitForSelector("#resetSettings");
  await shot("6-settings");

  // Review: newest review opens, with the hindsight-optimal lineup, ours, smash list and make-up
  {
    const index = JSON.parse(readFileSync(join(DOCS, "data", "review_index.json"), "utf8"));
    const latest = JSON.parse(readFileSync(join(DOCS, "data", "review_latest.json"), "utf8"));
    await page.click('a[data-view="review"]');
    await page.waitForSelector("text=Best possible lineup");
    assert.equal(await page.locator("#reviewDate option").count(), index.dates.length);
    assert.equal(await page.locator("#reviewDate").inputValue(), latest.gameDate);
    await page.waitForSelector(`text=${latest.optimal.players[0].name}`);
    assert.ok(await page.locator(".rtable").count() >= 3);
    await page.waitForSelector("text=Lineup make-up");
    await shot("11-review");
    const box = await page.locator("main").boundingBox();
    const width = await page.evaluate(() => document.documentElement.scrollWidth);
    assert.ok(width <= Math.ceil(box.width + 32), `review is wider than the phone (${width}px)`);
    console.log(`Review tab ok (${index.dates.length} dates, latest ${latest.gameDate})`);
  }

  // ---- Phase 7 checks, each in a fresh phone context ----

  // Started games + avoid-Q: pretend it's 5 minutes after the first tip-off.
  {
    const first = Math.min(...slate.games.map((g) => Date.parse(g.lock)));
    const startedGames = new Set(slate.games.filter((g) => Date.parse(g.lock) <= first + 5 * 60000).map((g) => g.game));
    const c2 = await browser.newContext({ ...devices["Pixel 7"], acceptDownloads: true, timezoneId: "America/Chicago", serviceWorkers: "block" });
    const p2 = await c2.newPage();
    p2.on("pageerror", (e) => errors.push(e.message));
    await p2.clock.install({ time: new Date(first + 5 * 60000) });
    await p2.goto(base);
    await p2.waitForSelector(".game");
    assert.ok(await p2.locator(".game .lock", { hasText: "Started" }).count() === startedGames.size);
    await p2.waitForSelector("text=have started");
    if (SHOTS) await p2.screenshot({ path: join(SHOTS, "9-started.png") });
    await p2.click('a[data-view="build"]');
    await p2.check("#excludeQ");
    await p2.click("#buildBtn");
    await p2.waitForSelector(".lineup", { timeout: 60000 });
    const [d3] = await Promise.all([p2.waitForEvent("download"), p2.click("#dlCsv")]);
    for (const row of readFileSync(await d3.path(), "utf8").trimEnd().split("\r\n").slice(1)) {
      for (const id of row.split(",")) {
        const pl = byId.get(id);
        assert.ok(!startedGames.has(pl.game), `${pl.name} is in a started game`);
        assert.notEqual(pl.status, "Q", `${pl.name} is Q`);
      }
    }
    console.log(`Started games (${[...startedGames].join(", ")}) and Q players left out`);

    // Stop a long build and keep what's done
    await p2.click('a[data-view="build"]');
    await p2.click('[data-mode="gpp"]');
    await p2.fill("#opt_gpp_lineups", "150");
    await p2.locator("#opt_gpp_lineups").blur();
    await p2.click("#buildBtn");
    await p2.waitForFunction(() => /Building… ([5-9]|\d\d)\//.test(document.querySelector("#buildBtn")?.textContent || ""), null, { timeout: 60000 });
    await p2.click("#stopBtn");
    await p2.waitForSelector("text=Stopped after");
    const kept = await p2.locator(".lineup").count();
    assert.ok(kept >= 5 && kept < 150, `kept ${kept}`);
    console.log(`Stop kept ${kept} lineups`);
    await c2.close();
  }

  // Offline: load once online (service worker caches the app and slate), then reload offline.
  {
    const c3 = await browser.newContext({ ...devices["Pixel 7"], timezoneId: "America/Chicago" });
    const p3 = await c3.newPage();
    await p3.goto(base);
    await p3.evaluate(() => navigator.serviceWorker.ready);
    await p3.reload(); // now controlled by the service worker, which caches the slate
    await p3.waitForSelector(".game");
    await c3.setOffline(true);
    await p3.reload();
    await p3.waitForSelector(".game");
    await p3.waitForSelector("text=You're offline");
    if (SHOTS) await p3.screenshot({ path: join(SHOTS, "10-offline.png") });
    console.log("Offline reload shows the cached slate");
    // A review viewed once online still opens offline
    await c3.setOffline(false);
    await p3.click('a[data-view="review"]');
    await p3.waitForSelector("text=Best possible lineup");
    await c3.setOffline(true);
    await p3.reload();
    await p3.waitForSelector("text=Best possible lineup");
    console.log("Offline reload shows the cached review");
    await c3.close();
  }

  assert.deepEqual(errors, [], "browser errors");
  console.log("E2E PASSED");
} finally {
  await browser.close();
  server.close();
}
