import test from "node:test";
import assert from "node:assert/strict";
import { toDkUploadCsv, lineupIdsText } from "../src/optimizer/csv.js";

const lu = ["1", "2", "3", "4", "5", "6", "7", "8"];

test("DK upload CSV: header row then one row of IDs per lineup", () => {
  const csv = toDkUploadCsv([lu, lu.map((x) => x + "0")]);
  const rows = csv.trimEnd().split("\r\n");
  assert.equal(rows[0], "PG,SG,SF,PF,C,G,F,UTIL");
  assert.equal(rows[1], "1,2,3,4,5,6,7,8");
  assert.equal(rows[2], "10,20,30,40,50,60,70,80");
  assert.equal(rows.length, 3);
});

test("DK upload CSV allows 150 lineups and rejects 151", () => {
  assert.equal(toDkUploadCsv(Array(150).fill(lu)).trimEnd().split("\r\n").length, 151);
  assert.throws(() => toDkUploadCsv(Array(151).fill(lu)), /at most 150/);
});

test("DK upload CSV rejects a lineup without 8 players", () => {
  assert.throws(() => toDkUploadCsv([lu.slice(0, 7)]), /8 players/);
});

test("copy IDs text: one lineup per line", () => {
  assert.equal(lineupIdsText([lu, lu]), "1,2,3,4,5,6,7,8\n1,2,3,4,5,6,7,8");
});
