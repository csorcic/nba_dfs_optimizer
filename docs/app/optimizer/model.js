// Integer program for one DK NBA Classic lineup.
//
// Variables: x(p) = 1 if player p is in the lineup; y(g) = 1 if the lineup uses game g.
// We choose 8 players and only assign slots afterwards. Position rules make sure
// the 8 can always fill PG, SG, SF, PF, C, G, F, UTIL (Hall's matching condition):
// for every group B of base positions (PG, SG, SF, PF, C), the players who can play
// at least one position in B must be at least the number of slots that only those
// players can fill. That is |B|, plus 1 for G if B has both PG and SG, plus 1 for F if
// B has both SF and PF. (UTIL takes anyone, so "exactly 8 players" covers it.)
// Choosing players instead of player-slot pairs avoids a lot of symmetry and solves
// about 10x faster.
//
// Constraints:
//   exactly 8 players                        sum x = 8
//   position coverage (31 groups)            sum_{p can play a position in B} x >= need(B)
//   salary cap                               sum salary * x <= cap
//   at least 2 games                         y(g) <= sum_{p in g} x ;  sum_g y(g) >= 2
//   locks                                    x(p) = 1
//   uniqueness vs each earlier lineup L      sum_{p in L} x <= 8 - U
//   extra rules (stacking etc.)              passed in as `extra` (terms use player IDs)
// Objective: maximize sum value(p) * x(p).
//
// The model is solver-neutral; toLpString() feeds HiGHS, toJsLpModel() feeds javascript-lp-solver.
import { SLOTS, SALARY_CAP, MIN_GAMES, ROSTER_SIZE } from "./rules.js";

const BASE = ["PG", "SG", "SF", "PF", "C"];

export function basePositions(p) {
  return BASE.filter((b) => p.slots.includes(b));
}

/** All 31 non-empty groups of base positions with how many slots they must cover. */
export const COVERAGE = (() => {
  const out = [];
  for (let mask = 1; mask < 1 << BASE.length; mask++) {
    const group = BASE.filter((_, i) => mask & (1 << i));
    const has = (b) => group.includes(b);
    const need = group.length + (has("PG") && has("SG") ? 1 : 0) + (has("SF") && has("PF") ? 1 : 0);
    out.push({ group, need });
  }
  return out;
})();

/**
 * @param {Array} pool players (already filtered) with numeric `value`
 * @param {{salaryCap?:number, locks?:Set<string>, previous?:string[][], minUnique?:number,
 *          extra?:Array<{name:string, ids?:Array<[string,number]>, terms?:Array<[string,number]>, op:string, rhs:number}>}} opts
 */
export function buildModel(pool, opts = {}) {
  const cap = opts.salaryCap ?? SALARY_CAP;
  const locks = opts.locks ?? new Set();
  const vars = []; // {name, kind:'x'|'y', player?, game?, obj}
  const constraints = [];
  const varOf = new Map(); // player id -> var name
  const byGame = new Map();

  pool.forEach((p, i) => {
    const name = `x${i}`;
    vars.push({ name, kind: "x", player: p, obj: p.value });
    varOf.set(String(p.id), name);
    if (!byGame.has(p.game)) byGame.set(p.game, []);
    byGame.get(p.game).push(name);
  });
  const xs = vars.filter((v) => v.kind === "x");

  constraints.push({ name: "roster", terms: xs.map((v) => [v.name, 1]), op: "=", rhs: ROSTER_SIZE });
  const bases = new Map(xs.map((v) => [v.name, basePositions(v.player)]));
  COVERAGE.forEach(({ group, need }, ci) => {
    const terms = xs.filter((v) => bases.get(v.name).some((b) => group.includes(b))).map((v) => [v.name, 1]);
    constraints.push({ name: `cover_${ci}`, terms, op: ">=", rhs: need });
  });
  constraints.push({ name: "salary", terms: xs.map((v) => [v.name, v.player.salary]), op: "<=", rhs: cap });
  pool.forEach((p, i) => {
    if (locks.has(String(p.id))) constraints.push({ name: `lock_${i}`, terms: [[`x${i}`, 1]], op: "=", rhs: 1 });
  });

  const gameVars = [];
  [...byGame.keys()].forEach((g, gi) => {
    const y = `y${gi}`;
    vars.push({ name: y, kind: "y", game: g, obj: 0 });
    gameVars.push(y);
    constraints.push({ name: `game_${gi}`, terms: [[y, 1], ...byGame.get(g).map((n) => [n, -1])], op: "<=", rhs: 0 });
  });
  constraints.push({ name: "min_games", terms: gameVars.map((y) => [y, 1]), op: ">=", rhs: MIN_GAMES });

  const maxShared = ROSTER_SIZE - (opts.minUnique ?? 1);
  (opts.previous ?? []).forEach((lineup, li) => {
    const terms = lineup.map(String).filter((id) => varOf.has(id)).map((id) => [varOf.get(id), 1]);
    if (terms.length > maxShared) constraints.push({ name: `uniq_${li}`, terms, op: "<=", rhs: maxShared });
  });

  // Extra rules written against player IDs (e.g. stacking) are translated to variables here.
  for (const c of opts.extra ?? []) {
    const terms = c.terms ?? (c.ids ?? []).filter(([id]) => varOf.has(String(id))).map(([id, k]) => [varOf.get(String(id)), k]);
    constraints.push({ name: c.name, terms, op: c.op, rhs: c.rhs });
  }
  return { vars, constraints, varOf, byGame, pool };
}

const fmt = (n) => {
  const r = Math.round(n * 1e4) / 1e4;
  return Object.is(r, -0) ? "0" : String(r);
};

function expr(terms) {
  const t = terms.filter(([, c]) => c !== 0);
  return t.map(([n, c], i) => `${c < 0 ? "- " : i ? "+ " : ""}${fmt(Math.abs(c))} ${n}`).join(" ");
}

/** CPLEX LP format string for HiGHS. */
export function toLpString(model) {
  const objTerms = model.vars.map((v) => [v.name, v.obj]).filter(([, c]) => c !== 0);
  const out = ["Maximize", ` obj: ${objTerms.length ? expr(objTerms) : `0 ${model.vars[0].name}`}`, "Subject To"];
  for (const c of model.constraints) {
    if (!c.terms.some(([, k]) => k !== 0)) continue;
    out.push(` ${c.name}: ${expr(c.terms)} ${c.op} ${fmt(c.rhs)}`);
  }
  out.push("Binary");
  for (let i = 0; i < model.vars.length; i += 20) {
    out.push(" " + model.vars.slice(i, i + 20).map((v) => v.name).join(" "));
  }
  out.push("End");
  return out.join("\n");
}

/** Model object for javascript-lp-solver. */
export function toJsLpModel(model) {
  const variables = {};
  const binaries = {};
  for (const v of model.vars) {
    variables[v.name] = { value: v.obj };
    binaries[v.name] = 1;
  }
  const constraints = {};
  for (const c of model.constraints) {
    if (!c.terms.length) continue;
    const key = `c_${c.name}`;
    constraints[key] = c.op === "=" ? { equal: c.rhs } : c.op === "<=" ? { max: c.rhs } : { min: c.rhs };
    for (const [n, coef] of c.terms) variables[n][key] = (variables[n][key] ?? 0) + coef;
  }
  return { optimize: "value", opType: "max", constraints, variables, binaries };
}

/**
 * Put 8 chosen players into slots (PG, SG, SF, PF, C, G, F, UTIL).
 * Fills the most restrictive slots first and backtracks; the coverage constraints
 * guarantee a fit exists. Returns 8 IDs in slot order, or null if none fits.
 */
export function assignSlots(players) {
  const order = SLOTS.map((s, i) => ({ s, i, n: players.filter((p) => p.slots.includes(s)).length }))
    .sort((a, b) => a.n - b.n);
  const result = Array(SLOTS.length);
  const used = new Set();
  const go = (k) => {
    if (k === order.length) return true;
    const { s, i } = order[k];
    for (const p of players) {
      if (used.has(p.id) || !p.slots.includes(s)) continue;
      used.add(p.id);
      result[i] = String(p.id);
      if (go(k + 1)) return true;
      used.delete(p.id);
    }
    return false;
  };
  return players.length === SLOTS.length && go(0) ? result : null;
}

/** Turn chosen variable names into 8 IDs in slot order. */
export function lineupFromSelection(model, chosen) {
  const picked = model.vars.filter((v) => v.kind === "x" && chosen.has(v.name)).map((v) => v.player);
  return assignSlots(picked);
}
