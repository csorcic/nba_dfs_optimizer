import test from "node:test";
import assert from "node:assert/strict";
import { buildLineups } from "../src/optimizer/optimizer.js";
import { validateLineup } from "../src/optimizer/rules.js";
import { nodeHighs, nodeJsLp, nodeSolver } from "../src/optimizer/node.js";
import { slatePlayers, smallPool, player, byId, shared } from "./helpers.js";

const highs = await nodeHighs();
const jsLp = await nodeJsLp();
const solvers = [highs, jsLp];

function assertAllValid(result, players) {
  const map = byId(players);
  for (const lu of result.lineups) {
    const r = validateLineup(lu.ids, map);
    assert.equal(r.valid, true, r.errors.join("; "));
  }
}

test("loadSolver picks HiGHS in Node", async () => {
  assert.equal((await nodeSolver()).name, "highs");
});

for (const solver of solvers) {
  test(`[${solver.name}] cash lineup on the real Nov 7 slate is legal and skips OUT players`, () => {
    const players = slatePlayers();
    const r = buildLineups(players, { mode: "cash", count: 1 }, solver);
    assert.equal(r.lineups.length, 1);
    assertAllValid(r, players);
    const out = new Set(players.filter((p) => p.status === "OUT").map((p) => p.id));
    assert.ok(r.lineups[0].ids.every((id) => !out.has(id)));
    assert.ok(r.lineups[0].salary <= 50000);
  });

  test(`[${solver.name}] 2-game rule is enforced even when one game is far better`, () => {
    const pool = [];
    for (const pos of ["PG", "SG", "SF", "PF", "C", "PG", "SF", "C", "PF"]) pool.push(player(pos, 3000, 50, "AAA@BBB"));
    for (const pos of ["PG", "SG", "SF", "PF", "C"]) pool.push(player(pos, 3000, 5, "CCC@DDD"));
    const r = buildLineups(pool, { count: 1 }, solver);
    const games = new Set(r.lineups[0].ids.map((id) => pool.find((p) => p.id === id).game));
    assert.equal(games.size, 2);
    assertAllValid(r, pool);
  });

  test(`[${solver.name}] uniqueness: each lineup shares at most 8-U players with every other`, () => {
    const pool = smallPool();
    const r = buildLineups(pool, { count: 6, minUnique: 2 }, solver);
    assert.equal(r.lineups.length, 6);
    for (let i = 0; i < r.lineups.length; i++)
      for (let j = 0; j < i; j++) assert.ok(shared(r.lineups[i].ids, r.lineups[j].ids) <= 6);
    assertAllValid(r, pool);
    // lineups come out best-first
    for (let i = 1; i < r.lineups.length; i++) assert.ok(r.lineups[i].proj <= r.lineups[i - 1].proj + 1e-6);
  });

  test(`[${solver.name}] locks are in every lineup; excludes in none`, () => {
    const pool = smallPool();
    const weak = pool.reduce((a, b) => (a.proj < b.proj ? a : b));
    const best = buildLineups(pool, { count: 1 }, solver).lineups[0].ids;
    const r = buildLineups(pool, { count: 4, locks: [weak.id], excludes: [best[0]] }, solver);
    for (const lu of r.lineups) {
      assert.ok(lu.ids.includes(weak.id));
      assert.ok(!lu.ids.includes(best[0]));
    }
    assertAllValid(r, pool);
  });

  test(`[${solver.name}] a locked OUT player is still used (locks win) with a warning`, () => {
    const pool = smallPool();
    pool[0].status = "OUT";
    const r = buildLineups(pool, { count: 1, locks: [pool[0].id] }, solver);
    assert.ok(r.lineups[0].ids.includes(pool[0].id));
    assert.match(r.warnings.join(), /locked but marked OUT/);
  });

  test(`[${solver.name}] projection overrides change who gets picked`, () => {
    const pool = smallPool();
    const before = buildLineups(pool, { count: 1 }, solver).lineups[0].ids;
    const benched = pool.find((p) => !before.includes(p.id) && p.slots.includes("C"));
    const r = buildLineups(pool, { count: 1, overrides: { [benched.id]: 99 } }, solver);
    assert.ok(r.lineups[0].ids.includes(benched.id));
    const zeroed = buildLineups(pool, { count: 1, overrides: { [before[0]]: 0 } }, solver);
    assert.ok(!zeroed.lineups[0].ids.includes(before[0]));
  });

  test(`[${solver.name}] max exposure caps how often a player appears`, () => {
    const pool = smallPool();
    const r = buildLineups(pool, { count: 4, maxExposure: 0.5 }, solver);
    assert.equal(r.lineups.length, 4);
    for (const e of r.exposure) assert.ok(e.count <= 2, `${e.name} in ${e.count} lineups`);
    assertAllValid(r, pool);
  });

  test(`[${solver.name}] impossible settings stop cleanly with a reason`, () => {
    const pool = smallPool();
    const centers = pool.filter((p) => p.slots.length === 2 && p.slots.includes("C")).slice(0, 3);
    const r = buildLineups(pool, { count: 1, locks: centers.map((p) => p.id) }, solver);
    assert.equal(r.lineups.length, 0);
    assert.match(r.stopReason, /No legal lineup/);
  });
}

test("HiGHS and javascript-lp-solver agree on the best projection", () => {
  const players = slatePlayers();
  for (const opts of [{ count: 1 }, { count: 1, floorWeight: 0.3 }, { count: 3, minUnique: 3 }]) {
    const a = buildLineups(players, opts, highs).lineups.map((l) => l.proj);
    const b = buildLineups(players, opts, jsLp).lineups.map((l) => l.proj);
    assert.equal(a.length, b.length);
    a.forEach((v, i) => assert.ok(Math.abs(v - b[i]) < 0.02, `${JSON.stringify(opts)}: ${v} vs ${b[i]}`));
  }
});

test("optimal: no single legal swap improves the cash lineup", () => {
  const players = slatePlayers().filter((p) => p.status !== "OUT" && p.proj > 0);
  const map = byId(players);
  const lu = buildLineups(players, { count: 1 }, highs).lineups[0];
  for (let i = 0; i < 8; i++) {
    for (const p of players) {
      const trial = [...lu.ids];
      trial[i] = p.id;
      const r = validateLineup(trial, map);
      if (r.valid) assert.ok(r.proj <= lu.proj + 1e-6, `swapping in ${p.name} beats the optimizer`);
    }
  }
});

test("20 cash lineups on the real slate build quickly and all pass validation", () => {
  const players = slatePlayers();
  const t0 = performance.now();
  let progress = 0;
  const r = buildLineups(players, { count: 20, minUnique: 1 }, highs, (d) => (progress = d));
  const ms = performance.now() - t0;
  assert.equal(r.lineups.length, 20);
  assert.equal(progress, 20);
  assertAllValid(r, players);
  assert.equal(new Set(r.lineups.map((l) => [...l.ids].sort().join())).size, 20);
  console.log(`  20 lineups in ${ms.toFixed(0)} ms`);
});

test("matches brute force on 40 random small pools (proves the position rules are exact)", async () => {
  const { assignSlots } = await import("../src/optimizer/model.js");
  const elig = [["PG", "G", "UTIL"], ["SG", "G", "UTIL"], ["SF", "F", "UTIL"], ["PF", "F", "UTIL"], ["C", "UTIL"],
    ["PG", "SG", "G", "UTIL"], ["SF", "PF", "F", "UTIL"], ["PF", "C", "F", "UTIL"], ["SG", "SF", "G", "F", "UTIL"]];
  let seed = 7;
  const rand = () => ((seed = (seed * 1103515245 + 12345) % 2 ** 31) / 2 ** 31);
  const combos = (arr, k, start = 0, cur = [], out = []) => {
    if (cur.length === k) out.push([...cur]);
    else for (let i = start; i < arr.length; i++) { cur.push(arr[i]); combos(arr, k, i + 1, cur, out); cur.pop(); }
    return out;
  };
  for (let t = 0; t < 40; t++) {
    const pool = Array.from({ length: 13 }, (_, i) => ({
      id: `r${t}_${i}`, name: `p${i}`, game: ["A@B", "C@D", "E@F"][Math.floor(rand() * 3)],
      salary: 3000 + 100 * Math.floor(rand() * 60), slots: elig[Math.floor(rand() * elig.length)],
      proj: Math.round(rand() * 500) / 10, floor: 0, ceiling: 0, status: "",
    }));
    const map = byId(pool);
    let best = -1;
    for (const c of combos(pool, 8)) {
      const ids = assignSlots(c);
      if (ids && validateLineup(ids, map).valid) best = Math.max(best, validateLineup(ids, map).proj);
    }
    for (const solver of solvers) {
      const r = buildLineups(pool, { count: 1 }, solver);
      if (best < 0) assert.equal(r.lineups.length, 0, `pool ${t}: optimizer found a lineup brute force didn't`);
      else assert.ok(Math.abs(r.lineups[0].proj - best) < 1e-6, `pool ${t} ${solver.name}: ${r.lineups[0]?.proj} vs ${best}`);
    }
  }
});
