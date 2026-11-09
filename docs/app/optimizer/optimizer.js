// Lineup builder for Cash and Tournament (GPP) modes.
//
// Usage:
//   const solver = await loadSolver({...});
//   const result = buildLineups(players, { mode: "gpp", count: 20 }, solver, onProgress);
//   result.lineups -> [{ ids: [8 IDs in slot order], salary, proj, ceiling, own }]
//
// Cash: maximize projection (+ optional floor weight); each next lineup is the next best.
// GPP: for every lineup, each player gets a random "simulated" score drawn from his
//      range (projection +/- SD), plus a ceiling bonus, minus an ownership penalty.
//      Uniqueness, exposure caps and optional game stacks shape the set of lineups.
// Locks, excludes and projection overrides always win.
import { buildModel, lineupFromSelection } from "./model.js";
import { validateLineup, SALARY_CAP, ROSTER_SIZE } from "./rules.js";

export const DEFAULTS = {
  mode: "cash", // "cash" | "gpp"
  count: 1, // number of lineups
  minUnique: 1, // each lineup differs from every earlier one by at least this many players
  salaryCap: SALARY_CAP,
  floorWeight: 0, // cash: extra credit for a player's floor
  maxExposure: 1, // 0-1: no player in more than this share of lineups (locks exempt)
  playerExposure: {}, // id -> { min?: 0-1, max?: 0-1 } (overrides maxExposure for that player)
  randomness: 1, // gpp: 0 = no randomness, 1 = draw from the player's full range
  ceilingWeight: 0, // gpp: bonus = weight * (ceiling - projection)
  ownershipPenalty: 0, // gpp: points subtracted per 1% estimated ownership
  stack: null, // gpp: { minPlayers, bringBack, games: ["AWAY@HOME", ...] }
  seed: null, // gpp: random seed (null = different every build)
  locks: [], // DK IDs that must be in every lineup
  excludes: [], // DK IDs never used
  overrides: {}, // id -> projection that replaces ours
  includeOut: false, // allow players marked OUT
};

/** Small seeded random generator (mulberry32) and a normal draw. */
export function makeRng(seed) {
  let a = (seed ?? Math.floor(Math.random() * 2 ** 32)) >>> 0;
  const next = () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const normal = () => {
    let u = 0;
    while (u === 0) u = next();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * next());
  };
  return { next, normal };
}

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
      if (p.sd) p.sd *= ratio;
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

/** A player's standard deviation: from the slate, else from the ceiling, else 30% of projection. */
export function playerSd(p) {
  if (Number.isFinite(p.sd) && p.sd > 0) return p.sd;
  if (Number.isFinite(p.ceiling) && p.ceiling > p.proj) return (p.ceiling - p.proj) / 1.28;
  return 0.3 * Math.max(p.proj, 0);
}

function lineupValues(pool, opts, rng) {
  if (opts.mode === "cash") return pool.map((p) => p.proj + opts.floorWeight * (p.floor ?? p.proj));
  return pool.map((p) => {
    const sim = Math.max(0, p.proj + opts.randomness * playerSd(p) * rng.normal());
    const ceilBonus = opts.ceilingWeight * Math.max(0, (p.ceiling ?? p.proj) - p.proj);
    return sim + ceilBonus - opts.ownershipPenalty * (p.own ?? 0);
  });
}

/** Game-stack rule as extra variables/constraints: at least X from one allowed game (+ bring-back). */
function stackRules(pool, stack) {
  if (!stack || !(stack.minPlayers >= 2)) return { extraVars: [], extra: [] };
  // The 2-game rule means at most 7 players can come from one game.
  if (stack.minPlayers > ROSTER_SIZE - 1) return { extraVars: [], extra: [], impossible: true };
  const games = (stack.games?.length ? stack.games : [...new Set(pool.map((p) => p.game))]);
  const extraVars = [];
  const extra = [];
  games.forEach((g, gi) => {
    const inGame = pool.filter((p) => p.game === g);
    if (inGame.length < stack.minPlayers) return;
    const s = `s${gi}`;
    extraVars.push({ name: s });
    extra.push({ name: `stack_${gi}`, terms: [[s, -stack.minPlayers]], ids: inGame.map((p) => [p.id, 1]), op: ">=", rhs: 0 });
    if (stack.bringBack) {
      const [away, home] = g.split("@");
      for (const team of [away, home]) {
        const ids = inGame.filter((p) => p.team === team).map((p) => [p.id, 1]);
        extra.push({ name: `bb_${gi}_${team}`, terms: [[s, -1]], ids, op: ">=", rhs: 0 });
      }
    }
  });
  if (!extraVars.length) return { extraVars: [], extra: [], impossible: true };
  extra.push({ name: "stack_any", terms: extraVars.map((v) => [v.name, 1]), op: ">=", rhs: 1 });
  return { extraVars, extra };
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
  const N = opts.count;
  const rng = makeRng(opts.seed);

  // Exposure limits as lineup counts.
  const capFor = (share) => (share >= 1 ? N : share <= 0 ? 0 : Math.max(1, Math.floor(share * N + 1e-9)));
  const maxCount = new Map();
  const minShare = new Map();
  for (const p of pool) {
    const pe = opts.playerExposure[p.id] || {};
    const minNeed = pe.min > 0 ? Math.ceil(Math.min(pe.min, 1) * N - 1e-9) : 0;
    // A player's own minimum wins over the global maximum.
    maxCount.set(p.id, locks.has(p.id) ? N : Math.max(capFor(pe.max ?? opts.maxExposure), minNeed));
    if (pe.min > 0) minShare.set(p.id, Math.min(pe.min, 1));
  }

  const stack = opts.mode === "gpp" ? stackRules(pool, opts.stack) : { extraVars: [], extra: [] };
  if (stack.impossible) warnings.push("No game has enough players for the stack setting; stacking was skipped.");

  const used = new Map();
  const lineups = [];
  let stopReason = null;
  let lastObjective = null;

  for (let k = 0; k < N; k++) {
    // Players at their exposure cap sit out the rest of the build (locks are exempt).
    const available = pool.filter((p) => (used.get(p.id) ?? 0) < maxCount.get(p.id));
    const values = lineupValues(available, opts, rng);
    const scored = available.map((p, i) => ({ ...p, value: values[i] }));

    // Minimum exposure: force players who are behind schedule (share * lineups so far).
    const forced = new Set(locks);
    for (const [id, share] of minShare) {
      if ((used.get(id) ?? 0) < Math.ceil(share * (k + 1) - 1e-9) && byId.has(id)) forced.add(id);
    }

    const extra = [...stack.extra];
    // Cash values never change between lineups, so the next lineup can't beat the
    // previous one. Telling the solver that up front roughly halves solve time.
    if (opts.mode === "cash" && lastObjective !== null) {
      extra.push({ name: "objcap", ids: scored.map((p) => [p.id, p.value]), op: "<=", rhs: lastObjective + 1e-6 });
    }
    const solve = (lockSet) => {
      const model = buildModel(scored, {
        salaryCap: opts.salaryCap, locks: lockSet, previous: lineups.map((l) => l.ids),
        minUnique: opts.minUnique, extraVars: stack.extraVars, extra,
      });
      // GPP scores are random draws anyway, so stop within 0.2% of the best (about 10% faster).
      if (opts.mode === "gpp") model.solverOptions = { mip_rel_gap: 0.002 };
      return { model, r: solver.solve(model) };
    };
    let { model, r } = solve(forced);
    if (r.status !== "optimal" && forced.size > locks.size) {
      // The minimum-exposure players don't all fit in this lineup; try without forcing them.
      ({ model, r } = solve(locks));
      if (r.status === "optimal" && !warnings.some((w) => w.startsWith("Some minimum")))
        warnings.push("Some minimum exposures couldn't all fit together; they may come up short.");
    }
    if (r.status !== "optimal") {
      stopReason = k === 0
        ? "No legal lineup fits these settings (check locks, excludes, stacking and salary)."
        : `Only ${k} lineups fit these settings (uniqueness, exposure or stacking too strict).`;
      break;
    }
    lastObjective = r.objective;
    const ids = lineupFromSelection(model, r.chosen);
    if (!ids) throw new Error("Optimizer picked 8 players that can't fill the slots (bug)");
    const check = validateLineup(ids, byId, { salaryCap: opts.salaryCap });
    if (!check.valid) throw new Error(`Optimizer produced an invalid lineup: ${check.errors.join("; ")}`);
    const sum = (f) => Math.round(ids.reduce((s, id) => s + (f(byId.get(id)) ?? 0), 0) * 10) / 10;
    lineups.push({ ids, salary: check.salary, proj: check.proj, ceiling: sum((p) => p.ceiling ?? p.proj), own: sum((p) => p.own ?? 0) });
    ids.forEach((id) => used.set(id, (used.get(id) ?? 0) + 1));
    onProgress?.(k + 1, N);
  }

  // Report minimum exposures that came up short.
  for (const [id, share] of minShare) {
    const need = Math.ceil(share * lineups.length - 1e-9);
    if ((used.get(id) ?? 0) < need) warnings.push(`${byId.get(id).name} is in ${used.get(id) ?? 0} lineups, short of the ${Math.round(share * 100)}% minimum.`);
  }
  const exposure = [...used.entries()]
    .map(([id, n]) => ({ id, name: byId.get(id).name, count: n, pct: (100 * n) / Math.max(lineups.length, 1), own: byId.get(id).own ?? null }))
    .sort((a, b) => b.count - a.count);
  return { lineups, exposure, warnings, stopReason, solver: solver.name, poolSize: pool.length, mode: opts.mode };
}

export { ROSTER_SIZE };
