// Slate review: hindsight lineups come from the real optimizer and are truly the best.
import test from "node:test";
import assert from "node:assert/strict";
import { runJobs, playersFor } from "../scripts/review_lineups.mjs";
import { validateLineup } from "../src/optimizer/rules.js";
import { assignSlots } from "../src/optimizer/model.js";
import { makeRng } from "../src/optimizer/optimizer.js";
import { nodeHighs } from "../src/optimizer/node.js";
import { slatePlayers, byId } from "./helpers.js";

const highs = await nodeHighs();

// Real Nov 7 slate with made-up "actual" scores (seeded, so the test is repeatable).
function slateWithActuals(seed = 7) {
  const rng = makeRng(seed);
  return slatePlayers().map((p) => ({
    ...p,
    actual: p.status === "OUT" ? 0 : Math.max(0, Math.round((p.proj + 12 * rng.normal()) * 4) / 4),
  }));
}

function randomValidLineups(players, n, seed = 1) {
  const rng = makeRng(seed);
  const map = byId(players);
  const out = [];
  for (let tries = 0; out.length < n && tries < n * 200; tries++) {
    const pick = [];
    const used = new Set();
    while (pick.length < 8) {
      const p = players[Math.floor(rng.next() * players.length)];
      if (!used.has(p.id)) { used.add(p.id); pick.push(p); }
    }
    const ids = assignSlots(pick);
    if (ids && validateLineup(ids, map).valid) out.push(ids);
  }
  return out;
}

test("hindsight lineups pass validateLineup and beat or equal any random valid lineup", () => {
  const players = slateWithActuals();
  const res = runJobs({
    players,
    jobs: [{ key: "hindsight", projField: "actual", options: { mode: "cash", count: 10, minUnique: 1, includeOut: true } }],
  }, highs);
  const lineups = res.jobs.hindsight.lineups;
  assert.equal(lineups.length, 10);
  const scored = byId(playersFor(players, "actual"));
  for (const lu of lineups) assert.equal(validateLineup(lu.ids, scored).valid, true);
  for (let i = 1; i < lineups.length; i++) assert.ok(lineups[i].proj <= lineups[i - 1].proj + 1e-6, "best first");
  assert.equal(new Set(lineups.map((l) => [...l.ids].sort().join())).size, 10, "all different");

  const actual = new Map(players.map((p) => [String(p.id), p.actual]));
  const randoms = randomValidLineups(players, 300);
  assert.ok(randoms.length >= 100, "enough random lineups to compare");
  const best = lineups[0].proj;
  for (const ids of randoms) {
    const score = ids.reduce((s, id) => s + actual.get(id), 0);
    assert.ok(score <= best + 1e-6, `random lineup ${score} beat the hindsight optimum ${best}`);
  }
});

test("'ours' job uses our projections and skips OUT players", () => {
  const players = slateWithActuals();
  const res = runJobs({ players, jobs: [{ key: "ours", projField: "proj", options: { mode: "cash", count: 1 } }] }, highs);
  const [lu] = res.jobs.ours.lineups;
  const map = byId(players);
  assert.equal(validateLineup(lu.ids, map).valid, true);
  assert.ok(lu.ids.every((id) => map.get(id).status !== "OUT"));
});
