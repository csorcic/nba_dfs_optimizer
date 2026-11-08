// Node helpers (tests and command-line checks). The browser uses its own loader in Phase 5.
import { createRequire } from "node:module";
import { loadSolver, highsSolver, jsLpSolver } from "./solvers.js";

const require = createRequire(import.meta.url);

export const loadHighs = async () => require("highs")();
export const loadJsLp = async () => require("javascript-lp-solver");

export const nodeSolver = () => loadSolver({ highs: loadHighs, jsLp: loadJsLp });
export const nodeHighs = async () => highsSolver(await loadHighs());
export const nodeJsLp = async () => jsLpSolver(await loadJsLp());
