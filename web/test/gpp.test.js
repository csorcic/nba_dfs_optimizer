import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { buildLineups, makeRng, playerSd } from "../src/optimizer/optimizer.js";
import { validateLineup } from "../src/optimizer/rules.js";
import { nodeHighs } from "../src/optimizer/node.js";
import { byId, shared } from "./helpers.js";

const highs = await nodeHighs();
const slate = JSON.parse(readFileSync(new URL("./fixtures/slate_nov9_gpp.json", import.meta.url), "utf8"));
const players = slate.players;
const map = byId(players);
const gpp = (o) => ({ mode: "gpp", count: 20, minUnique: 3, maxExposure: 0.5, randomness: 1, ceilingWeight: 0.3, ownershipPenalty: 0.1, seed: 42, ...o });

function checkAll(r) {
  for (const lu of r.lineups) {
    const v = validateLineup(lu.ids, map);
    assert.equal(v.valid, true, v.errors.join("; "));
  }
}
const countOf = (r, id) => r.lineups.filter((l) => l.ids.includes(id)).length;

test("seeded random draws are repeatable and look normal", () => {
  const a = makeRng(7), b = makeRng(7);
  const xs = Array.from({ length: 20000 }, () => a.normal());
  assert.equal(xs[0], b.normal());
  const mean = xs.reduce((s, x) => s + x, 0) / xs.length;
  const sd = Math.sqrt(xs.reduce((s, x) => s + (x - mean) ** 2, 0) / xs.length);
  assert.ok(Math.abs(mean) < 0.03 && Math.abs(sd - 1) < 0.03, `mean ${mean} sd ${sd}`);
});

test("playerSd falls back to the ceiling, then 30% of projection", () => {
  assert.equal(playerSd({ proj: 20, sd: 7 }), 7);
  assert.ok(Math.abs(playerSd({ proj: 20, ceiling: 32.8 }) - 10) < 1e-9);
  assert.equal(playerSd({ proj: 20 }), 6);
});

test("GPP: 20 lineups, all legal, uniqueness 3, max exposure 50%", () => {
  const r = buildLineups(players, gpp(), highs);
  assert.equal(r.lineups.length, 20);
  checkAll(r);
  for (let i = 0; i < 20; i++) for (let j = 0; j < i; j++) assert.ok(shared(r.lineups[i].ids, r.lineups[j].ids) <= 5);
  for (const e of r.exposure) assert.ok(e.count <= 10, `${e.name} in ${e.count}/20`);
  assert.ok(r.lineups.every((l) => l.own > 0 && l.ceiling > l.proj));
});

test("GPP: same seed gives the same lineups; different seeds differ", () => {
  const a = buildLineups(players, gpp({ count: 5 }), highs).lineups.map((l) => l.ids.join());
  const b = buildLineups(players, gpp({ count: 5 }), highs).lineups.map((l) => l.ids.join());
  const c = buildLineups(players, gpp({ count: 5, seed: 99 }), highs).lineups.map((l) => l.ids.join());
  assert.deepEqual(a, b);
  assert.notDeepEqual(a, c);
});

test("GPP: randomness 0 and no penalties equals the cash optimum", () => {
  const g = buildLineups(players, gpp({ count: 1, randomness: 0, ceilingWeight: 0, ownershipPenalty: 0 }), highs);
  const c = buildLineups(players, { mode: "cash", count: 1 }, highs);
  assert.ok(Math.abs(g.lineups[0].proj - c.lineups[0].proj) < 1e-6);
});

test("GPP: a bigger ownership penalty lowers total ownership", () => {
  const lo = buildLineups(players, gpp({ ownershipPenalty: 0 }), highs);
  const hi = buildLineups(players, gpp({ ownershipPenalty: 0.5 }), highs);
  const avg = (r) => r.lineups.reduce((s, l) => s + l.own, 0) / r.lineups.length;
  assert.ok(avg(hi) < avg(lo) - 5, `${avg(hi)} vs ${avg(lo)}`);
});

test("GPP: per-player max and min exposure are honored", () => {
  const star = players.filter((p) => p.status !== "OUT").sort((a, b) => b.proj - a.proj)[0];
  const cheap = players.find((p) => p.status !== "OUT" && p.salary <= 4000 && p.proj > 12 && p.proj < 20);
  const r = buildLineups(players, gpp({ playerExposure: { [star.id]: { max: 0.2 }, [cheap.id]: { min: 0.6 } } }), highs);
  checkAll(r);
  assert.ok(countOf(r, star.id) <= 4, `star in ${countOf(r, star.id)}`);
  assert.ok(countOf(r, cheap.id) >= 12, `cheap in ${countOf(r, cheap.id)}`);
});

test("GPP: locks are in every lineup even past the exposure cap", () => {
  const lock = players.find((p) => p.status !== "OUT" && p.salary === 5000) ?? players[20];
  const r = buildLineups(players, gpp({ locks: [lock.id] }), highs);
  assert.equal(countOf(r, lock.id), 20);
});

test("GPP: game stack puts at least X players from an allowed game in every lineup, with bring-back", () => {
  const games = slate.games.filter((g) => g.total).sort((a, b) => b.total - a.total).map((g) => g.game).slice(0, 2);
  const r = buildLineups(players, gpp({ stack: { minPlayers: 4, bringBack: true, games } }), highs);
  checkAll(r);
  for (const lu of r.lineups) {
    const ok = games.some((g) => {
      const inG = lu.ids.map((id) => map.get(id)).filter((p) => p.game === g);
      const [away, home] = g.split("@");
      return inG.length >= 4 && inG.some((p) => p.team === away) && inG.some((p) => p.team === home);
    });
    assert.ok(ok, `lineup without a 4-player stack + bring-back: ${lu.ids}`);
  }
});

test("GPP: impossible stack is reported, not crashed", () => {
  const r = buildLineups(players, gpp({ count: 2, stack: { minPlayers: 9, games: [] } }), highs);
  assert.ok(r.warnings.some((w) => /stacking was skipped/.test(w)));
  assert.equal(r.lineups.length, 2);
});

test("GPP: 150 lineups (DK maximum) all legal, timed", () => {
  const t0 = performance.now();
  const r = buildLineups(players, gpp({ count: 150, seed: 1 }), highs);
  const s = (performance.now() - t0) / 1000;
  assert.equal(r.lineups.length, 150);
  checkAll(r);
  assert.equal(new Set(r.lineups.map((l) => [...l.ids].sort().join())).size, 150);
  for (const e of r.exposure) assert.ok(e.count <= 75);
  console.log(`  150 GPP lineups in ${s.toFixed(1)} s`);
});
