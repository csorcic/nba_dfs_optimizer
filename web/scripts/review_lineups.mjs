// Build lineups for the slate review with the app's own optimizer (no second optimizer).
//
//   node scripts/review_lineups.mjs input.json output.json
//
// input.json:
//   { "players": [{ id, name, team, opp, game, salary, slots, status, proj, actual, ... }],
//     "jobs": [{ "key": "hindsight", "projField": "actual", "options": { mode: "cash", count: 50, minUnique: 1 } }] }
// For each job, every player's projection is replaced by `projField` (e.g. actual DK points
// for the hindsight lineups), then buildLineups() runs exactly as in the app.
// output.json: { solver, jobs: { <key>: { lineups: [{ ids, salary, proj, valid }], warnings, stopReason } } }
// Every lineup is checked with validateLineup(); an invalid lineup is a bug and exits non-zero.
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { buildLineups } from "../src/optimizer/optimizer.js";
import { validateLineup } from "../src/optimizer/rules.js";
import { nodeSolver } from "../src/optimizer/node.js";

export function playersFor(players, projField) {
  return players.map((p) => {
    const value = Number(p[projField] ?? 0);
    const q = { ...p, id: String(p.id), proj: Number.isFinite(value) ? value : 0 };
    if (projField !== "proj") {
      // Hindsight: the score is known, so there is no range around it.
      q.floor = q.proj;
      q.ceiling = q.proj;
      q.sd = 0;
    }
    return q;
  });
}

export function runJobs(input, solver) {
  const out = { solver: solver.name, jobs: {} };
  for (const job of input.jobs) {
    const players = playersFor(input.players, job.projField ?? "proj");
    const map = new Map(players.map((p) => [p.id, p]));
    const r = buildLineups(players, job.options ?? {}, solver);
    const lineups = r.lineups.map((lu) => {
      const check = validateLineup(lu.ids, map);
      if (!check.valid) throw new Error(`Invalid lineup in ${job.key}: ${check.errors.join("; ")}`);
      return { ids: lu.ids, salary: check.salary, proj: check.proj, valid: true };
    });
    out.jobs[job.key] = { lineups, warnings: r.warnings, stopReason: r.stopReason };
  }
  return out;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  const [inPath, outPath] = process.argv.slice(2);
  if (!inPath) {
    console.error("usage: node scripts/review_lineups.mjs input.json [output.json]");
    process.exit(2);
  }
  const input = JSON.parse(readFileSync(inPath, "utf8"));
  const result = runJobs(input, await nodeSolver());
  const text = JSON.stringify(result);
  if (outPath) writeFileSync(outPath, text);
  else process.stdout.write(text);
}
