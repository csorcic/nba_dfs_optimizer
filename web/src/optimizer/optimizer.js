// Lineup builder. Phase 4: Cash mode (GPP randomness, ownership and stacking come in Phase 6).
//
// Usage:
//   const solver = await loadSolver({...});
//   const result = buildLineups(players, { mode: "cash", count: 1 }, solver);
//   result.lineups -> [{ ids: [8 IDs in slot order], salary, proj }]
import { buildModel, lineupFromSelection } from "./model.js";
import { validateLineup, SALARY_CAP } from "./rules.js";

export const DEFAULTS = {
  mode: "cash",
  count: 1, // number of lineups
  minUnique: 1, // each lineup differs from every earlier one by at least this many players
  salaryCap: SALARY_CAP,
  floorWeight: 0, // cash: extra credit for a player's floor
  maxExposure: 1, // 0-1: no player in more than this share of lineups
  locks: [], // DK IDs that must be in every lineup
  excludes: [], // DK IDs never used
  overrides: {}, // id -> projection that replaces ours
  includeOut: false, // allow players marked OUT
};

/** Apply locks/excludes/overrides and drop unusable players. Returns { pool, warnings }. */
export function preparePool(players, opts) {
  const locks = new Set(opts.locks.map(String));
  const excludes = new Set(opts.excludes.map(String));
  const warnings = [];
  const pool = [];
  for (const raw of players) {
    const id = String(raw.id);
    const locked = locks.has(id);
    if (locked && excludes.has(id)) warnings.push(`${raw.name} is both locked and excluded; keeping the lock.`);
    if (!locked && excludes.has(id)) continue;
    if (!locked && !opts.includeOut && raw.status === "OUT") continue;
    if (locked && raw.status === "OUT") warnings.push(`${raw.name} is locked but marked OUT.`);
    const p = { ...raw, id };
    const ov = opts.overrides[id];
    if (ov !== undefined && ov !== null && ov !== "" && Number.isFinite(Number(ov))) {
      const newProj = Number(ov);
      const ratio = p.proj > 0 ? newProj / p.proj : 1;
      p.floor = (p.floor ?? p.proj) * ratio;
      p.ceiling = (p.ceiling ?? p.proj) * ratio;
      p.proj = newProj;
    }
    if (!Number.isFinite(p.proj)) p.proj = 0;
    if (!locked && p.proj <= 0) continue;
    pool.push(p);
  }
  for (const id of locks) {
    if (!pool.some((p) => p.id === id)) warnings.push(`Locked player ${id} is not on this slate.`);
  }
  return { pool, warnings };
}

function playerValue(p, opts) {
  if (opts.mode === "cash") return p.proj + opts.floorWeight * (p.floor ?? p.proj);
  return p.proj;
}

/**
 * Build lineups. Every returned lineup has passed validateLineup(); a failure throws (it is a bug).
 * @param {Array} players
 * @param {object} options see DEFAULTS
 * @param {{solve: Function, name: string}} solver
 * @param {(done:number, total:number)=>void} [onProgress]
 */
export function buildLineups(players, options, solver, onProgress) {
  const opts = { ...DEFAULTS, ...options };
  const { pool, warnings } = preparePool(players, opts);
  const byId = new Map(pool.map((p) => [p.id, p]));
  const locks = new Set(opts.locks.map(String));
  const maxCount = Math.max(1, Math.floor(opts.maxExposure * opts.count + 1e-9));
  const used = new Map();
  const lineups = [];
  let stopReason = null;
  let lastObjective = null;

  for (let k = 0; k < opts.count; k++) {
    // Players at their exposure cap sit out the rest of the build (locks are exempt).
    const available = pool
      .filter((p) => locks.has(p.id) || (used.get(p.id) ?? 0) < maxCount)
      .map((p) => ({ ...p, value: playerValue(p, opts) }));
    // Cash values never change between lineups, so the next lineup can't beat the
    // previous one. Telling the solver that up front roughly halves solve time.
    const extra = [];
    if (opts.mode === "cash" && lastObjective !== null) {
      extra.push({ name: "objcap", ids: available.map((p) => [p.id, p.value]), op: "<=", rhs: lastObjective + 1e-6 });
    }
    const model = buildModel(available, {
      salaryCap: opts.salaryCap,
      locks,
      previous: lineups.map((l) => l.ids),
      minUnique: opts.minUnique,
      extra,
    });
    const r = solver.solve(model);
    if (r.status !== "optimal") {
      stopReason =
        k === 0
          ? "No legal lineup fits these settings (check locks, excludes and salary)."
          : `Only ${k} lineups fit these settings (uniqueness or exposure too strict).`;
      break;
    }
    lastObjective = r.objective;
    const ids = lineupFromSelection(model, r.chosen);
    if (!ids) throw new Error("Optimizer picked 8 players that can't fill the slots (bug)");
    const check = validateLineup(ids, byId, { salaryCap: opts.salaryCap });
    if (!check.valid) throw new Error(`Optimizer produced an invalid lineup: ${check.errors.join("; ")}`);
    lineups.push({ ids, salary: check.salary, proj: check.proj });
    ids.forEach((id) => used.set(id, (used.get(id) ?? 0) + 1));
    onProgress?.(k + 1, opts.count);
  }

  const exposure = [...used.entries()]
    .map(([id, n]) => ({ id, name: byId.get(id).name, count: n, pct: (100 * n) / Math.max(lineups.length, 1) }))
    .sort((a, b) => b.count - a.count);
  return { lineups, exposure, warnings, stopReason, solver: solver.name, poolSize: pool.length };
}
