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

  assert.deepEqual(errors, [], "browser errors");
  console.log("E2E PASSED");
} finally {
  await browser.close();
  server.close();
}
