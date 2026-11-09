// App state that survives a refresh: settings (kept forever) and per-slate edits
// (locks, excludes, projection and minutes overrides), plus the last results.
// Edits are keyed by slate date, so a new slate starts clean.

const KEY_SETTINGS = "dfs.settings";
const KEY_EDITS = "dfs.edits."; // + slate date
const KEY_RESULTS = "dfs.results."; // + slate date

// Settings Chris can change in the app. Defaults come from config/settings.yaml via the slate file.
export const SETTING_FIELDS = [
  { key: "cash_lineups", mode: "cash", label: "Lineups", help: "How many lineups Cash mode builds. Most cash players use 1.", min: 1, max: 20, step: 1 },
  { key: "cash_min_unique", mode: "cash", label: "Players different", help: "Each lineup differs from every earlier one by at least this many players.", min: 1, max: 8, step: 1 },
  { key: "cash_floor_weight", mode: "cash", label: "Floor weight", help: "Extra credit for a safe floor. 0 = only the projection counts; 0.3 = floor counts 30% as much.", min: 0, max: 1, step: 0.05 },
  { key: "gpp_lineups", mode: "gpp", label: "Lineups", help: "How many tournament lineups to build (DraftKings allows up to 150 per contest).", min: 1, max: 150, step: 1 },
  { key: "gpp_min_unique", mode: "gpp", label: "Players different", help: "Each lineup differs from every earlier one by at least this many players. 3 is a good start.", min: 1, max: 8, step: 1 },
  { key: "gpp_max_exposure_pct", mode: "gpp", label: "Max exposure %", help: "No player appears in more than this percent of lineups (locks and your own per-player settings win).", min: 1, max: 100, step: 1 },
  { key: "gpp_randomness", mode: "gpp", label: "Randomness", help: "How much projections are shuffled for each lineup. 0 = none (same as cash), 1 = each player's full boom/bust range.", min: 0, max: 2, step: 0.1 },
  { key: "gpp_ceiling_weight", mode: "gpp", label: "Ceiling weight", help: "Extra credit for upside: adds this share of (ceiling minus projection).", min: 0, max: 1, step: 0.05 },
  { key: "gpp_ownership_penalty", mode: "gpp", label: "Ownership penalty", help: "Points taken off per 1% estimated ownership, to fade popular players. 0.1 = a 40%-owned player loses 4 points.", min: 0, max: 1, step: 0.05 },
  { key: "stack_min_players", mode: "gpp", label: "Game stack size", help: "Require at least this many players from one high-total game. 0 = off; 3 or 4 is typical.", min: 0, max: 7, step: 1 },
  { key: "stack_top_games", mode: "gpp", label: "Stack from top games", help: "Stacks may only come from this many highest-total games on the slate.", min: 1, max: 15, step: 1 },
];

export const FALLBACK_DEFAULTS = {
  build_mode: "cash", cash_lineups: 1, cash_min_unique: 1, cash_floor_weight: 0, cash_max_lineups: 20,
  gpp_lineups: 20, gpp_min_unique: 3, gpp_max_exposure_pct: 50, gpp_randomness: 1, gpp_ceiling_weight: 0.3,
  gpp_ownership_penalty: 0.1, stack_min_players: 0, stack_bring_back: false, stack_top_games: 3,
};

const store = {
  get(key, fallback) {
    try {
      const v = localStorage.getItem(key);
      return v === null ? fallback : JSON.parse(v);
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* storage full or blocked: edits just won't persist */
    }
  },
  remove(key) {
    try {
      localStorage.removeItem(key);
    } catch {}
  },
  keys() {
    try {
      return Object.keys(localStorage);
    } catch {
      return [];
    }
  },
};
export { store };

export function loadSettings(defaults) {
  return { ...FALLBACK_DEFAULTS, ...(defaults || {}), ...store.get(KEY_SETTINGS, {}) };
}
export function saveSettings(settings, defaults) {
  // Only remember values that differ from the defaults, so new defaults still flow through.
  const base = { ...FALLBACK_DEFAULTS, ...(defaults || {}) };
  const diff = {};
  for (const [k, v] of Object.entries(settings)) if (base[k] !== v) diff[k] = v;
  store.set(KEY_SETTINGS, diff);
}
export function resetSettings() {
  store.remove(KEY_SETTINGS);
}

export const emptyEdits = () => ({ locks: [], excludes: [], proj: {}, minutes: {}, expMin: {}, expMax: {} });

export function loadEdits(slateDate) {
  // Old slates' edits and results are dropped: edits reset each slate.
  for (const k of store.keys()) {
    if ((k.startsWith(KEY_EDITS) || k.startsWith(KEY_RESULTS)) && !k.endsWith(slateDate)) store.remove(k);
  }
  return { ...emptyEdits(), ...store.get(KEY_EDITS + slateDate, {}) };
}
export const saveEdits = (slateDate, edits) => store.set(KEY_EDITS + slateDate, edits);
export const loadResults = (slateDate) => store.get(KEY_RESULTS + slateDate, null);
export const saveResults = (slateDate, results) => store.set(KEY_RESULTS + slateDate, results);

/** Toggle helpers keep a player from being both locked and excluded. */
export function toggleLock(edits, id) {
  const locked = edits.locks.includes(id);
  return {
    ...edits,
    locks: locked ? edits.locks.filter((x) => x !== id) : [...edits.locks, id],
    excludes: edits.excludes.filter((x) => x !== id),
  };
}
export function toggleExclude(edits, id) {
  const excluded = edits.excludes.includes(id);
  return {
    ...edits,
    excludes: excluded ? edits.excludes.filter((x) => x !== id) : [...edits.excludes, id],
    locks: edits.locks.filter((x) => x !== id),
  };
}
export function setOverride(edits, field, id, value) {
  const next = { ...edits, [field]: { ...edits[field] } };
  if (value === "" || value === null || value === undefined || !Number.isFinite(Number(value))) delete next[field][id];
  else next[field][id] = Number(value);
  return next;
}

/**
 * Players as the app shows and optimizes them, with Chris's edits applied.
 * Order of precedence: projection override > minutes override > our projection.
 * A minutes override scales projection, floor and ceiling by new minutes / our minutes.
 */
export function effectivePlayers(players, edits) {
  const locks = new Set(edits.locks);
  const excludes = new Set(edits.excludes);
  return players.map((p) => {
    let ratio = 1;
    const minOv = edits.minutes[p.id];
    const projOv = edits.proj[p.id];
    if (minOv !== undefined && p.minutes > 0) ratio = minOv / p.minutes;
    let proj = p.proj * ratio;
    if (projOv !== undefined) {
      ratio = p.proj > 0 ? projOv / p.proj : 1;
      proj = projOv;
    }
    const scale = (v) => (v === null || v === undefined ? v : Math.round(v * ratio * 100) / 100);
    return {
      ...p,
      baseProj: p.proj,
      proj: Math.round(proj * 100) / 100,
      floor: scale(p.floor),
      ceiling: scale(p.ceiling),
      minutesShown: minOv ?? p.minutes,
      value: p.salary ? Math.round((proj / (p.salary / 1000)) * 100) / 100 : 0,
      locked: locks.has(p.id),
      excluded: excludes.has(p.id),
      edited: minOv !== undefined || projOv !== undefined,
      expMin: edits.expMin?.[p.id],
      expMax: edits.expMax?.[p.id],
    };
  });
}
