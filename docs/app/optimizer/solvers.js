// Solver adapters. Each returns { status: "optimal"|"infeasible"|"error", chosen: Set<varName>, objective }.
// HiGHS (WebAssembly) is preferred; javascript-lp-solver is the pure-JS fallback.
import { toLpString, toJsLpModel } from "./model.js";

export function highsSolver(highs) {
  return {
    name: "highs",
    solve(model) {
      const r = highs.solve(toLpString(model));
      if (r.Status === "Infeasible") return { status: "infeasible", chosen: new Set(), objective: null };
      if (r.Status !== "Optimal") return { status: "error", message: r.Status, chosen: new Set(), objective: null };
      const chosen = new Set();
      for (const [name, col] of Object.entries(r.Columns)) if (col.Primal > 0.5) chosen.add(name);
      return { status: "optimal", chosen, objective: r.ObjectiveValue };
    },
  };
}

export function jsLpSolver(solverLib) {
  return {
    name: "javascript-lp-solver",
    solve(model) {
      const r = solverLib.Solve(toJsLpModel(model));
      if (!r.feasible) return { status: "infeasible", chosen: new Set(), objective: null };
      const chosen = new Set();
      for (const v of model.vars) if ((r[v.name] ?? 0) > 0.5) chosen.add(v.name);
      return { status: "optimal", chosen, objective: r.result };
    },
  };
}

/**
 * Load the best available solver. `loaders` lets the browser and Node supply their own imports:
 *   { highs: async () => highsInstance, jsLp: async () => solverLib }
 */
export async function loadSolver(loaders) {
  if (loaders.highs) {
    try {
      const highs = await loaders.highs();
      // Smoke test: HiGHS occasionally fails to initialize on some phones.
      const ok = highs.solve("Maximize\n obj: x\nSubject To\n c: x <= 1\nBinary\n x\nEnd");
      if (ok.Status === "Optimal") return highsSolver(highs);
    } catch (e) {
      console.warn("HiGHS unavailable, using javascript-lp-solver:", e);
    }
  }
  if (!loaders.jsLp) throw new Error("No solver available");
  return jsLpSolver(await loaders.jsLp());
}
