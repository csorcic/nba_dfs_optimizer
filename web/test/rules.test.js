import test from "node:test";
import assert from "node:assert/strict";
import { validateLineup, parseSlots, dkPoints, SALARY_CAP } from "../src/optimizer/rules.js";
import { player, byId } from "./helpers.js";

function legalLineup() {
  const ps = [
    player("PG", 6000, 30, "AAA@BBB"), player("SG", 6000, 30, "AAA@BBB"), player("SF", 6000, 30, "CCC@DDD"),
    player("PF", 6000, 30, "CCC@DDD"), player("C", 6000, 30, "CCC@DDD"), player("PG/SG", 6000, 30, "AAA@BBB"),
    player("SF/PF", 6000, 30, "CCC@DDD"), player("C", 6000, 30, "AAA@BBB"),
  ];
  return { ps, ids: ps.map((p) => p.id), map: byId(ps) };
}

test("parseSlots reads the DK Roster Position field", () => {
  assert.deepEqual(parseSlots("PF/C/F/UTIL"), ["PF", "C", "F", "UTIL"]);
  assert.deepEqual(parseSlots("PG/G/UTIL"), ["PG", "G", "UTIL"]);
});

test("a legal lineup passes", () => {
  const { ids, map } = legalLineup();
  const r = validateLineup(ids, map);
  assert.equal(r.valid, true, r.errors.join("; "));
  assert.equal(r.salary, 48000);
  assert.equal(r.proj, 240);
});

test("salary over the cap fails; exactly the cap passes", () => {
  const { ps, ids, map } = legalLineup();
  ps[0].salary = 8000; // total 50000
  assert.equal(validateLineup(ids, map).valid, true);
  ps[0].salary = 8100;
  const r = validateLineup(ids, map);
  assert.equal(r.valid, false);
  assert.match(r.errors.join(), /over the \$50000 cap/);
  assert.equal(SALARY_CAP, 50000);
});

test("players from only one game fail", () => {
  const { ps, ids, map } = legalLineup();
  ps.forEach((p) => (p.game = "AAA@BBB"));
  assert.match(validateLineup(ids, map).errors.join(), /at least 2 games/);
});

test("duplicate player fails", () => {
  const { ids, map } = legalLineup();
  ids[7] = ids[4]; // C used at C and UTIL
  assert.match(validateLineup(ids, map).errors.join(), /more than once/);
});

test("ineligible slot fails", () => {
  const { ids, map } = legalLineup();
  [ids[0], ids[4]] = [ids[4], ids[0]]; // center at PG
  assert.match(validateLineup(ids, map).errors.join(), /PG: .* not eligible/);
});

test("G accepts PG or SG only; F accepts SF or PF only", () => {
  const { ps, ids, map } = legalLineup();
  ps[5].slots = ["SF", "F", "UTIL"];
  assert.match(validateLineup(ids, map).errors.join(), /G: .* not eligible/);
  ps[5].slots = ["PG", "SG", "G", "UTIL"];
  ps[6].slots = ["C", "UTIL"];
  assert.match(validateLineup(ids, map).errors.join(), /F: .* not eligible/);
});

test("wrong size and unknown IDs fail", () => {
  const { ids, map } = legalLineup();
  assert.equal(validateLineup(ids.slice(0, 7), map).valid, false);
  ids[2] = "nope";
  assert.match(validateLineup(ids, map).errors.join(), /unknown player ID nope/);
});

test("DK scoring matches the rules (same cases as the Python tests)", () => {
  assert.equal(dkPoints({ pts: 20, fg3m: 2, reb: 5, ast: 4, stl: 1, blk: 0, tov: 3 }), 20 + 1 + 6.25 + 6 + 2 - 1.5);
  assert.equal(dkPoints({ pts: 10, reb: 10 }), 10 + 12.5 + 1.5);
  assert.equal(dkPoints({ pts: 10, reb: 10, ast: 10 }), 10 + 12.5 + 15 + 4.5);
});
