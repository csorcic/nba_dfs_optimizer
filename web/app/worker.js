// Runs the optimizer off the main thread so the screen stays responsive.
// Messages in:  { type: "build", players, options }
// Messages out: { type: "progress", done, total } | { type: "done", result } | { type: "error", message }
import { buildLineups } from "./optimizer/optimizer.js";
import { loadSolver } from "./optimizer/solvers.js";

let solverPromise = null;
function getSolver() {
  solverPromise ??= loadSolver({
    highs: async () => (await import("../vendor/highs.mjs")).default(),
    jsLp: async () => (await import("../vendor/lp-solver.mjs")).default,
  });
  return solverPromise;
}

self.onmessage = async (e) => {
  const { type, players, options } = e.data;
  if (type === "warmup") {
    getSolver().catch(() => {});
    return;
  }
  if (type !== "build") return;
  try {
    const solver = await getSolver();
    const t0 = performance.now();
    const result = buildLineups(players, options, solver, (done, total, lineup) =>
      self.postMessage({ type: "progress", done, total, lineup }));
    result.seconds = Math.round((performance.now() - t0) / 100) / 10;
    self.postMessage({ type: "done", result });
  } catch (err) {
    self.postMessage({ type: "error", message: String(err?.message || err) });
  }
};
