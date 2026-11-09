// App state that survives a refresh: settings (kept forever) and per-slate edits
// (locks, excludes, projection and minutes overrides), plus the last results.
// Edits are keyed by slate date, so a new slate starts clean.

const KEY_SETTINGS = "dfs.settings";
const KEY_EDITS = "dfs.edits."; // + slate date
const KEY_RESULTS = "dfs.results."; // + slate date

// Settings Chris can change in the app. Defaults come from config/settings.yaml via the slate file.
export const SETTING_FIELDS = [
  { key: "cash_lineups", label: "Cash lineups", help: "How many lineups Cash mode builds.", min: 1, max: 20, step: 1 },
  { key: "cash_min_unique", label: "Cash: players different", help: "Each Cash lineup must differ from every earlier one by at least this many players.", min: 1, max: 8, step: 1 },
  { key: "cash_floor_weight", label: "Cash: floor weight", help: "Extra credit for a safe floor. 0 = only the projection counts; 0.3 = floor counts 30% as much.", min: 0, max: 1, step: 0.05 },
];

export const FALLBACK_DEFAULTS = { cash_lineups: 1, cash_min_unique: 1, cash_floor_weight: 0, cash_max_lineups: 20 };

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

export const emptyEdits = () => ({ locks: [], excludes: [], proj: {}, minutes: {} });

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
    };
  });
}
