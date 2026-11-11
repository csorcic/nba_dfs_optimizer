"""DraftKings contest standings import.

Chris drops DK standings files (.csv, or the .zip DK gives) into data/contests/ on
the GitHub website. For each new file this:
  1. parses DK's layout: left block = one row per entry (Rank, EntryId, EntryName,
     TimeRemaining, Points, Lineup); right block = one row per player (Player,
     Roster Position, %Drafted, FPTS)
  2. works out which slate it belongs to (player names vs the salary files, then
     DK points vs our box scores to break ties)
  3. saves a summary to data/contests/processed/<gameDate>/<contestId>.json and
     moves the original file next to it
  4. adds the results to that slate's review (field size, winning score and
     lineups, top 1% / top 10% / cash line, real ownership vs our estimate, and
     Chris's own entries)
A file that can't be read or matched goes to data/contests/unmatched/ with a note.
A contest file never fails the pipeline.

Usage: python -m pipeline.contests
Settings: `review:` in config/settings.yaml (dk_username, contest_* keys).
"""
from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import shutil
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline import review
from pipeline.config import REPO_ROOT, load_settings
from pipeline.names import normalize

CONTEST_DIR = REPO_ROOT / "data" / "contests"
LINEUP_SLOTS = ["C", "F", "G", "PF", "PG", "SF", "SG", "UTIL"]  # the order DK writes them
SLOTS = review.SLOTS
ID_RE = re.compile(r"contest-standings-(\d+)")
ENTRY_NAME_RE = re.compile(r"\s*\(\d+/\d+\)\s*$")


# ---------- reading ----------

def read_files(path: Path) -> list[tuple[str, str]]:
    """[(csv file name, text)] from a .csv or a .zip of CSVs."""
    if path.suffix.lower() == ".zip":
        out = []
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if name.lower().endswith(".csv") and not name.startswith("__MACOSX"):
                    out.append((Path(name).name, z.read(name).decode("utf-8-sig", errors="replace")))
        if not out:
            raise ValueError("the zip has no CSV file inside")
        return out
    return [(path.name, path.read_text(encoding="utf-8-sig", errors="replace"))]


def parse_lineup(text: str) -> list[tuple[str, str]] | None:
    """'C Jakob Poeltl F PJ Washington G Luka Doncic ...' -> [(slot, name)] in DK's order.

    DK always lists the slots in the same order (C F G PF PG SF SG UTIL), so we look
    for each slot label in turn; a name containing a word like "G" can't confuse it.
    """
    text = " " + " ".join((text or "").split()) + " "
    marks = []
    pos = 0
    for slot in LINEUP_SLOTS:
        i = text.find(f" {slot} ", pos)
        if i < 0:
            return None
        marks.append((slot, i, i + len(slot) + 2))
        pos = i + len(slot) + 1
    out = []
    for k, (slot, _, start) in enumerate(marks):
        end = marks[k + 1][1] if k + 1 < len(marks) else len(text)
        name = text[start:end].strip()
        if not name:
            return None
        out.append((slot, name))
    return out


def _float(v) -> float | None:
    try:
        return float(str(v).replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def parse_standings(text: str) -> dict:
    """Parse DK's standings CSV into entries and players."""
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    if not rows:
        raise ValueError("empty file")
    head = [h.strip() for h in rows[0]]
    need = ["Rank", "EntryId", "EntryName", "Points", "Lineup", "Player", "%Drafted", "FPTS"]
    missing = [h for h in need if h not in head]
    if missing:
        raise ValueError(f"not a DK standings file (missing columns: {', '.join(missing)})")
    col = {h: head.index(h) for h in head if h}
    get = lambda r, h: r[col[h]].strip() if col.get(h) is not None and col[h] < len(r) else ""  # noqa: E731
    entries, players = [], {}
    for r in rows[1:]:
        if get(r, "EntryId"):
            lineup = parse_lineup(get(r, "Lineup"))
            entries.append({
                "rank": int(_float(get(r, "Rank")) or 0),
                "entryId": get(r, "EntryId"),
                "entryName": get(r, "EntryName"),
                "user": ENTRY_NAME_RE.sub("", get(r, "EntryName")),
                "points": _float(get(r, "Points")) or 0.0,
                "lineup": lineup,
            })
        if get(r, "Player"):
            # DK lists a player once per roster slot he was used in (C and UTIL, say),
            # so his %Drafted is the sum of his rows.
            name = get(r, "Player")
            p = players.setdefault(name, {"name": name, "slots": [], "listedPct": 0.0,
                                          "fpts": _float(get(r, "FPTS"))})
            p["slots"].append(get(r, "Roster Position"))
            p["listedPct"] = round(p["listedPct"] + (_float(get(r, "%Drafted")) or 0.0), 2)
    if not entries:
        raise ValueError("no entries found")
    return {"entries": entries, "players": list(players.values())}


def real_ownership(parsed: dict, min_parsed_pct: float) -> tuple[dict[str, float], str]:
    """{player name: % of lineups he was in}, and where the numbers came from.

    Counted from the lineups themselves (exact). DK's player block can leave rows
    out (in a test file its %Drafted added up to 751%, not 800%), so it's only
    used when too few lineups could be read.
    """
    entries = parsed["entries"]
    readable = [e for e in entries if e["lineup"]]
    if entries and 100 * len(readable) / len(entries) >= min_parsed_pct:
        cnt = Counter(n for e in readable for _, n in e["lineup"])
        return {n: round(100 * c / len(readable), 2) for n, c in cnt.items()}, "lineups"
    return {p["name"]: p["listedPct"] for p in parsed["players"]}, "dk_player_block"


# ---------- which slate ----------

def detect_slate(parsed: dict, slates: dict[str, Path], logs: pd.DataFrame, cfg: dict) -> tuple[str | None, str]:
    """(game date, reason). Picks the slate whose salary file has the most of the
    contest's players; DK points vs our box scores break ties."""
    names = {normalize(p["name"]) for p in parsed["players"]}
    for e in parsed["entries"]:
        names |= {normalize(n) for _, n in (e["lineup"] or [])}
    fpts = {normalize(p["name"]): p["fpts"] for p in parsed["players"] if p["fpts"] is not None}
    scored = []
    for gdate, d in slates.items():
        sal = review.read_csv(d / "players.csv")
        on_slate = {normalize(n): eid for n, eid in zip(sal["name"], sal["espn_id"].fillna(""))}
        name_pct = 100 * len(names & on_slate.keys()) / max(len(names), 1)
        day = logs[logs["date"] == gdate].drop_duplicates("espn_id").set_index("espn_id")["dk_pts"] if len(logs) else {}
        checks = [abs(day[on_slate[n]] - v) <= cfg["contest_fpts_tolerance"]
                  for n, v in fpts.items() if on_slate.get(n) and on_slate[n] in day.index] if len(day) else []
        fpts_pct = 100 * sum(checks) / len(checks) if checks else 0.0
        scored.append((name_pct, fpts_pct, gdate))
    if not scored:
        return None, "no slates to match against"
    scored.sort(reverse=True)
    best = scored[0]
    if best[0] < cfg["contest_slate_min_match_pct"]:
        return None, (f"only {best[0]:.0f}% of its players are on any slate's salary file "
                      f"(closest: {best[2]}); need {cfg['contest_slate_min_match_pct']}%")
    if len(scored) > 1 and scored[1][:2] == best[:2]:
        return None, f"matches two slates equally well ({best[2]} and {scored[1][2]})"
    return best[2], f"{best[0]:.0f}% of players on the {best[2]} salary file, {best[1]:.0f}% of DK points agree"


# ---------- summary ----------

def score_at_pct(points_desc: list[float], pct: float) -> float | None:
    """Score needed to finish in the top `pct` percent of the field."""
    if not points_desc:
        return None
    k = max(1, math.ceil(pct / 100 * len(points_desc)))
    return points_desc[min(k, len(points_desc)) - 1]


def finish_percentile(rank: int, field: int) -> float:
    """Share of the field you finished ahead of (1st = 100, last = 0)."""
    return 100.0 if field <= 1 else round(100 * (field - rank) / (field - 1), 1)


def summarize(parsed: dict, contest_id: str, file_name: str, gdate: str, slate_dir: Path, cfg: dict) -> dict:
    sal = review.read_csv(slate_dir / "players.csv")
    by_name: dict[str, list[str]] = {}
    for n, i in zip(sal["name"], sal["dk_id"]):
        by_name.setdefault(normalize(n), []).append(str(i))
    fpts = {normalize(p["name"]): p["fpts"] for p in parsed["players"]}

    def lineup_ids(lu):
        """DK's slot order -> app slot order (PG, SG, SF, PF, C, G, F, UTIL) with DK IDs."""
        if not lu:
            return None
        d = dict(lu)
        out = []
        for slot in SLOTS:
            n = d[slot]
            ids = by_name.get(normalize(n), [])
            out.append({"slot": slot, "name": n, "id": ids[0] if len(ids) == 1 else None,
                        "fpts": fpts.get(normalize(n))})
        return out

    entries = sorted(parsed["entries"], key=lambda e: (e["rank"], -e["points"]))
    field = len(entries)
    pts = sorted((e["points"] for e in entries), reverse=True)
    top = pts[0]
    winners = [e for e in entries if e["points"] == top]
    me = cfg.get("dk_username") or ""
    mine = [e for e in entries if me and e["user"].lower() == me.lower()]
    mine_out = [{"rank": e["rank"], "points": e["points"], "entryName": e["entryName"],
                 "percentile": finish_percentile(e["rank"], field), "players": lineup_ids(e["lineup"])}
                for e in mine]
    own, own_source = real_ownership(parsed, cfg["contest_min_readable_lineups_pct"])
    ownership = []
    for name in sorted(set(own) | {p["name"] for p in parsed["players"]}):
        ids = by_name.get(normalize(name), [])
        ownership.append({"name": name, "id": ids[0] if len(ids) == 1 else None,
                          "drafted": own.get(name, 0.0), "fpts": fpts.get(normalize(name))})
    unknown = sorted({o["name"] for o in ownership if not o["id"]}
                     | {x["name"] for e in winners for x in (lineup_ids(e["lineup"]) or []) if not x["id"]})
    return {
        "contestId": contest_id,
        "name": f"Contest {contest_id}",
        "file": file_name,
        "gameDate": gdate,
        "importedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fieldSize": field,
        "winningScore": top,
        "winningLineups": [{"entryName": e["entryName"], "points": e["points"], "players": lineup_ids(e["lineup"])}
                           for e in winners[: cfg["contest_max_winning_lineups"]]],
        "top1Score": score_at_pct(pts, 1),
        "top10Score": score_at_pct(pts, 10),
        "cashLine": score_at_pct(pts, 100 - cfg["contest_cash_line_pct"]),
        "cashLinePct": cfg["contest_cash_line_pct"],
        "mine": {"username": me, "entries": mine_out,
                 "best": min(mine_out, key=lambda e: e["rank"]) if mine_out else None},
        "ownership": ownership,
        "ownershipSource": own_source,
        "unmatchedNames": unknown,
    }


# ---------- add to the review ----------

def load_contests(gdate: str, contest_dir: Path = CONTEST_DIR) -> list[dict]:
    folder = contest_dir / "processed" / gdate
    return [json.loads(f.read_text()) for f in sorted(folder.glob("*.json"))] if folder.exists() else []


def ownership_check(contest: dict, players: pd.DataFrame, tiers: list) -> dict:
    """Real %Drafted vs our estimate for every player who could have been drafted."""
    real = {o["id"]: o["drafted"] for o in contest["ownership"] if o["id"]}
    df = players.copy()
    df["dk_id"] = df["dk_id"].astype(str)
    df["real"] = df["dk_id"].map(real).fillna(0.0)
    df["est"] = pd.to_numeric(df["own"], errors="coerce").fillna(0.0)
    played = df["projected_to_play"].astype(str).str.lower().isin(["true", "1"])
    d = df[played | (df["real"] > 0)].copy()
    if d.empty:
        return {}
    d["err"] = d["est"] - d["real"]
    edges = [-np.inf, *tiers, np.inf]
    labels = [f"under ${tiers[0] // 1000}K"] + [f"${a // 1000}-{b // 1000}K" for a, b in zip(tiers, tiers[1:])] + \
             [f"${tiers[-1] // 1000}K+"]
    d["tier"] = pd.cut(d["salary"].astype(float), edges, labels=labels, right=False)
    by_tier = [{"tier": str(t), "players": int(len(g)), "mae": round(float(g["err"].abs().mean()), 2),
                "bias": round(float(g["err"].mean()), 2)}
               for t, g in d.groupby("tier", observed=True)]
    d = d.sort_values("real", ascending=False)
    return {
        "contestId": contest["contestId"], "fieldSize": contest["fieldSize"], "players": int(len(d)),
        "mae": round(float(d["err"].abs().mean()), 2), "bias": round(float(d["err"].mean()), 2),
        "byTier": by_tier,
        "list": [{"id": r["dk_id"], "name": r["name"], "salary": int(r["salary"]), "real": round(float(r["real"]), 2),
                  "est": round(float(r["est"]), 1)} for _, r in d.iterrows()],
    }


def attach_contests(doc: dict, players: pd.DataFrame, settings: dict, contest_dir: Path = CONTEST_DIR) -> dict:
    """Add contest results to a review (no-op when no standings were imported)."""
    contests = load_contests(doc["gameDate"], contest_dir)
    if not contests:
        doc.pop("contests", None)
        doc.pop("ownershipCheck", None)
        return doc
    optimal_ids = {p["id"] for p in doc["optimal"]["players"]}
    by_id = {str(r["dk_id"]): r for _, r in players.iterrows()}
    out = []
    for c in sorted(contests, key=lambda c: -c["fieldSize"]):
        winners = []
        for w in c["winningLineups"]:
            ids = [x["id"] for x in (w["players"] or [])]
            winners.append({**w, "sharedWithOptimal": sum(i in optimal_ids for i in ids if i),
                            "gapToOptimal": round(doc["optimal"]["actual"] - w["points"], 2),
                            "salary": int(sum(by_id[i]["salary"] for i in ids if i in by_id)),
                            "ourOwnSum": round(float(sum(float(by_id[i]["own"] or 0) for i in ids if i in by_id)), 1)})
        out.append({k: c[k] for k in ("contestId", "name", "fieldSize", "winningScore", "top1Score", "top10Score",
                                      "cashLine", "cashLinePct", "mine", "unmatchedNames")}
                   | {"winningLineups": winners,
                      "optimalBeatsWinnerBy": round(doc["optimal"]["actual"] - c["winningScore"], 2)})
    doc["contests"] = out
    # Real ownership: use the biggest field (the least noisy %Drafted).
    doc["ownershipCheck"] = ownership_check(max(contests, key=lambda c: c["fieldSize"]), players,
                                            settings["backtest"]["salary_tiers"])
    return doc


# ---------- the run ----------

def _move(src: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if dest.exists():
        dest.unlink()
    shutil.move(str(src), dest)
    return dest


def process_new(settings: dict, contest_dir: Path = CONTEST_DIR, slates: dict | None = None,
                logs: pd.DataFrame | None = None) -> dict:
    """Import every new file in data/contests/. Returns {'imported': [...], 'unmatched': [...], 'dates': set}."""
    cfg = settings["review"]
    report = {"imported": [], "unmatched": [], "dates": set()}
    files = sorted(p for p in contest_dir.glob("*") if p.is_file() and p.suffix.lower() in (".csv", ".zip"))
    if not files:
        return report
    slates = slates if slates is not None else review.slates_by_game_date()
    if logs is None:
        logs = review.load_logs([settings["data"]["current_season"], settings["data"]["prior_season"]])
    for path in files:
        try:
            results = []
            for name, text in read_files(path):
                parsed = parse_standings(text)
                gdate, why = detect_slate(parsed, slates, logs, cfg)
                if gdate is None:
                    raise ValueError(why)
                m = ID_RE.search(name) or ID_RE.search(path.name)
                cid = m.group(1) if m else Path(name).stem
                results.append((summarize(parsed, cid, path.name, gdate, slates[gdate], cfg), why))
            for summary, why in results:
                folder = contest_dir / "processed" / summary["gameDate"]
                folder.mkdir(parents=True, exist_ok=True)
                (folder / f"{summary['contestId']}.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
                report["dates"].add(summary["gameDate"])
                report["imported"].append({"file": path.name, "contestId": summary["contestId"],
                                           "gameDate": summary["gameDate"], "fieldSize": summary["fieldSize"],
                                           "why": why, "mine": len(summary["mine"]["entries"])})
            _move(path, contest_dir / "processed" / results[0][0]["gameDate"])
        except Exception as e:  # never fail the pipeline over a contest file
            dest = _move(path, contest_dir / "unmatched")
            dest.with_name(dest.name + ".txt").write_text(f"Couldn't use this file: {e}\n", encoding="utf-8")
            report["unmatched"].append({"file": path.name, "why": str(e)})
    return report


def refresh_reviews(dates, settings: dict, contest_dir: Path = CONTEST_DIR) -> list[str]:
    """Re-attach contest results to reviews that already exist."""
    done = []
    for gdate in sorted(dates):
        path = review.REVIEW_DIR / f"{gdate}.json"
        pcsv = review.REVIEW_DIR / f"{gdate}_players.csv"
        if not path.exists() or not pcsv.exists():
            continue  # the review is built later and picks the contest up then
        doc = json.loads(path.read_text())
        players = review.read_csv(pcsv)
        attach_contests(doc, players, settings, contest_dir)
        errs = review.validate_review(doc)
        if errs:
            raise RuntimeError(f"{gdate}: {errs}")
        review.write_review(doc, players)
        done.append(gdate)
    return done


def summary_text(report: dict, refreshed: list[str]) -> str:
    lines = ["## Contest standings", ""]
    for r in report["imported"]:
        lines.append(f"- Imported **{r['file']}** (contest {r['contestId']}, {r['fieldSize']} entries) "
                     f"for the {r['gameDate']} slate: {r['why']}. Your entries found: {r['mine']}.")
    for r in report["unmatched"]:
        lines.append(f"- **Could not use {r['file']}**: {r['why']}. Moved to data/contests/unmatched/.")
    if refreshed:
        lines.append(f"- Updated reviews: {', '.join(refreshed)}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    settings = load_settings()
    try:
        report = process_new(settings)
        refreshed = refresh_reviews(report["dates"], settings)
    except Exception as e:  # a contest problem must never fail the pipeline
        print(f"Contest import problem (pipeline continues): {e}")
        return 0
    if not report["imported"] and not report["unmatched"]:
        print("No new contest files.")
        return 0
    text = summary_text(report, refreshed)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
