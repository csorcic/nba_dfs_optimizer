import test from "node:test";
import assert from "node:assert/strict";

// Minimal localStorage for Node
const mem = new Map();
globalThis.localStorage = {
  getItem: (k) => (mem.has(k) ? mem.get(k) : null),
  setItem: (k, v) => mem.set(k, String(v)),
  removeItem: (k) => mem.delete(k),
};
Object.defineProperty(globalThis.localStorage, "keys", { value: () => [...mem.keys()] });
const S = await import("../app/state.js");
// store.keys() uses Object.keys(localStorage); emulate it
S.store.keys = () => [...mem.keys()];

const P = (id, proj, minutes, extra = {}) => ({ id, name: id, salary: 5000, proj, floor: proj / 2, ceiling: proj * 1.5, minutes, ...extra });

test("lock and exclude are mutually exclusive", () => {
  let e = S.emptyEdits();
  e = S.toggleLock(e, "a");
  assert.deepEqual(e.locks, ["a"]);
  e = S.toggleExclude(e, "a");
  assert.deepEqual(e.locks, []);
  assert.deepEqual(e.excludes, ["a"]);
  e = S.toggleExclude(e, "a");
  assert.deepEqual(e.excludes, []);
});

test("minutes override scales projection, floor and ceiling", () => {
  const e = S.setOverride(S.emptyEdits(), "minutes", "a", "30");
  const [p] = S.effectivePlayers([P("a", 20, 20)], e);
  assert.equal(p.proj, 30);
  assert.equal(p.floor, 15);
  assert.equal(p.ceiling, 45);
  assert.equal(p.minutesShown, 30);
  assert.equal(p.edited, true);
  assert.equal(p.value, 6);
});

test("projection override beats minutes override; blank clears it", () => {
  let e = S.setOverride(S.emptyEdits(), "minutes", "a", 30);
  e = S.setOverride(e, "proj", "a", 40);
  assert.equal(S.effectivePlayers([P("a", 20, 20)], e)[0].proj, 40);
  e = S.setOverride(e, "proj", "a", "");
  assert.equal(S.effectivePlayers([P("a", 20, 20)], e)[0].proj, 30);
});

test("edits persist per slate and old slates are cleared", () => {
  S.saveEdits("2026-11-08", { ...S.emptyEdits(), locks: ["x"] });
  S.saveResults("2026-11-08", { lineups: [] });
  assert.deepEqual(S.loadEdits("2026-11-08").locks, ["x"]);
  assert.deepEqual(S.loadEdits("2026-11-09").locks, []); // new slate starts clean...
  assert.equal(mem.has("dfs.edits.2026-11-08"), false); // ...and the old one is dropped
  assert.equal(S.loadResults("2026-11-08"), null);
});

test("settings keep only changes from defaults, and reset", () => {
  const d = { cash_lineups: 1, cash_min_unique: 1, cash_floor_weight: 0 };
  const st = S.loadSettings(d);
  st.cash_lineups = 5;
  S.saveSettings(st, d);
  assert.deepEqual(JSON.parse(mem.get("dfs.settings")), { cash_lineups: 5 });
  assert.equal(S.loadSettings(d).cash_lineups, 5);
  S.resetSettings();
  assert.equal(S.loadSettings(d).cash_lineups, 1);
});
