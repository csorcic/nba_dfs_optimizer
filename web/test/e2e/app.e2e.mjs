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
  await page.fill("#nLineups", "3");
  await page.press("#nLineups", "Enter");
  await page.locator("#nLineups").blur();
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
