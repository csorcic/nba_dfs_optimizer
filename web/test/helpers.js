import { readFileSync } from "node:fs";
import { SLOTS } from "../src/optimizer/rules.js";

export const slatePlayers = () =>
  JSON.parse(readFileSync(new URL("./fixtures/slate_players.json", import.meta.url), "utf8"));

export const byId = (players) => new Map(players.map((p) => [String(p.id), p]));

const SLOTS_FOR = {
  PG: ["PG", "G", "UTIL"], SG: ["SG", "G", "UTIL"], SF: ["SF", "F", "UTIL"], PF: ["PF", "F", "UTIL"],
  C: ["C", "UTIL"], "PG/SG": ["PG", "SG", "G", "UTIL"], "SF/PF": ["SF", "PF", "F", "UTIL"],
  "PF/C": ["PF", "C", "F", "UTIL"],
};

let nextId = 1000;
/** Small synthetic player. */
export function player(pos, salary, proj, game = "AAA@BBB", extra = {}) {
  const [away, home] = game.split("@");
  const team = extra.team ?? home;
  return {
    id: String(nextId++), name: `${pos} ${salary}`, team, opp: team === home ? away : home, game,
    salary, slots: SLOTS_FOR[pos], proj, floor: proj * 0.6, ceiling: proj * 1.4, status: "", ...extra,
  };
}

/** A pool with 3 players per position spread over 3 games. */
export function smallPool() {
  const games = ["AAA@BBB", "CCC@DDD", "EEE@FFF"];
  const out = [];
  ["PG", "SG", "SF", "PF", "C"].forEach((pos, i) => {
    games.forEach((g, j) => out.push(player(pos, 4000 + 1000 * j + 100 * i, 20 + 8 * j + i, g)));
  });
  out.push(player("PG/SG", 5200, 30, "AAA@BBB"), player("SF/PF", 5400, 31, "CCC@DDD"),
    player("PF/C", 5600, 32, "EEE@FFF"));
  return out;
}

export const shared = (a, b) => a.filter((id) => b.includes(id)).length;
export { SLOTS };
