// DraftKings bulk-upload CSV: header PG,SG,SF,PF,C,G,F,UTIL then one lineup per row of player IDs.
import { SLOTS } from "./rules.js";

export const MAX_UPLOAD_LINEUPS = 150;

/** @param {string[][]} lineups arrays of 8 IDs in SLOTS order */
export function toDkUploadCsv(lineups) {
  if (lineups.length > MAX_UPLOAD_LINEUPS) {
    throw new Error(`DraftKings accepts at most ${MAX_UPLOAD_LINEUPS} lineups per upload`);
  }
  const rows = [SLOTS.join(",")];
  for (const lu of lineups) {
    if (lu.length !== SLOTS.length) throw new Error("Each lineup needs 8 players");
    rows.push(lu.map(String).join(","));
  }
  return rows.join("\r\n") + "\r\n";
}

/** Plain list of IDs for "copy IDs": one lineup per line, comma separated. */
export function lineupIdsText(lineups) {
  return lineups.map((lu) => lu.join(",")).join("\n");
}
