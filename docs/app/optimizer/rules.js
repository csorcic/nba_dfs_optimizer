// DraftKings NBA Classic rules. Used by the optimizer, the app and the tests.
//
// A lineup is an array of 8 DK player IDs in slot order: PG, SG, SF, PF, C, G, F, UTIL.
// A player looks like:
//   { id, name, team, opp, game, salary, slots: ["PG","G","UTIL"], proj, floor, ceiling, status }
// `slots` comes from the DK CSV "Roster Position" field, which is the source of truth.

export const SLOTS = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"];
export const ROSTER_SIZE = SLOTS.length;
export const SALARY_CAP = 50000;
export const MIN_GAMES = 2;

/** Parse DK "Roster Position" ("PF/C/F/UTIL") into a slot list. */
export function parseSlots(rosterPosition) {
  return String(rosterPosition || "")
    .split("/")
    .map((s) => s.trim().toUpperCase())
    .filter((s) => SLOTS.includes(s));
}

export function isEligible(player, slot) {
  return Array.isArray(player.slots) && player.slots.includes(slot);
}

/**
 * Check a lineup against every DK rule.
 * @param {string[]} lineup  8 player IDs in SLOTS order
 * @param {Map|Object} players  id -> player
 * @param {{salaryCap?: number}} opts
 * @returns {{valid: boolean, errors: string[], salary: number, proj: number}}
 */
export function validateLineup(lineup, players, opts = {}) {
  const cap = opts.salaryCap ?? SALARY_CAP;
  const get = (id) => (players instanceof Map ? players.get(String(id)) : players[String(id)]);
  const errors = [];
  let salary = 0;
  let proj = 0;

  if (!Array.isArray(lineup) || lineup.length !== ROSTER_SIZE) {
    return { valid: false, errors: [`Lineup must have exactly ${ROSTER_SIZE} players`], salary, proj };
  }
  const ids = lineup.map(String);
  if (new Set(ids).size !== ids.length) errors.push("A player appears more than once");

  const games = new Set();
  ids.forEach((id, i) => {
    const p = get(id);
    const slot = SLOTS[i];
    if (!p) {
      errors.push(`${slot}: unknown player ID ${id}`);
      return;
    }
    if (!isEligible(p, slot)) errors.push(`${slot}: ${p.name} is not eligible (${(p.slots || []).join("/")})`);
    if (!Number.isFinite(p.salary)) errors.push(`${slot}: ${p.name} has no salary`);
    salary += p.salary || 0;
    proj += p.proj || 0;
    games.add(p.game);
  });

  if (salary > cap) errors.push(`Salary $${salary} is over the $${cap} cap`);
  if (games.size < MIN_GAMES) errors.push(`Players must come from at least ${MIN_GAMES} games`);
  return { valid: errors.length === 0, errors, salary, proj: Math.round(proj * 100) / 100 };
}

/**
 * DraftKings scoring for one stat line (used for checking projections and tests).
 * Point +1, 3PM +0.5, Rebound +1.25, Assist +1.5, Steal +2, Block +2, Turnover -0.5,
 * Double-double +1.5, Triple-double +3 more (so +4.5 total).
 */
export function dkPoints({ pts = 0, fg3m = 0, reb = 0, ast = 0, stl = 0, blk = 0, tov = 0 }) {
  let s = pts + 0.5 * fg3m + 1.25 * reb + 1.5 * ast + 2 * stl + 2 * blk - 0.5 * tov;
  const doubles = [pts, reb, ast, stl, blk].filter((v) => v >= 10).length;
  if (doubles >= 2) s += 1.5;
  if (doubles >= 3) s += 3;
  return Math.round(s * 100) / 100;
}
