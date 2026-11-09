"""Run the data pipeline: salaries + ESPN box scores + odds -> joined player table.

Output for the latest slate:
  data/slates/<date>/players.csv   one row per DK player, with ESPN match + Vegas lines
  data/slates/<date>/games.json    games on the slate with lock time, total, spread, implied totals
  data/slates/<date>/unmatched.txt DK players we couldn't find on ESPN (fix in config/name_overrides.yaml)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd

from pipeline import fetch_espn, fetch_odds, fetch_salaries, publish
from pipeline.project import pos_groups, project
from pipeline.config import REPO_ROOT, load_name_overrides, load_settings
from pipeline.names import Matcher

SLATES = REPO_ROOT / "data" / "slates"

PLAYER_COLUMNS = [
    "dk_id", "name", "team", "opp", "home", "game", "lock_time", "positions", "roster_positions",
    "salary", "avg_ppg", "status", "starting",
    "espn_id", "espn_name", "match_method", "matched", "games_current", "games_prior", "last_game",
    "game_total", "team_spread", "team_implied", "opp_implied", "odds_source",
]


def read_gamelogs(season: int) -> list[dict]:
    path = fetch_espn.GAMELOG_DIR / f"gamelogs_{season}.csv"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def espn_roster(logs_by_season: dict[int, list[dict]]) -> tuple[list[dict], dict]:
    """Latest team for every ESPN player, plus games played per season."""
    latest: dict[str, dict] = {}
    played: Counter = Counter()
    for season, rows in sorted(logs_by_season.items()):
        for r in rows:  # rows are date-sorted, so later rows overwrite earlier ones
            latest[r["espn_id"]] = {"espn_id": r["espn_id"], "name": r["name"], "team": r["team"],
                                    "last_game": r["date"]}
            if r["dnp"] == "0" and int(r["min"] or 0) > 0:
                played[(season, r["espn_id"])] += 1
    return list(latest.values()), played


def build_player_table(players, matcher, played, lines, current, prior):
    table, unmatched = [], []
    for p in players:
        hit, method = matcher.match(p["name"], p["team"])
        line = lines.get(p["game"])
        row = dict(p)
        row.update({
            "espn_id": hit["espn_id"] if hit else "",
            "espn_name": hit["name"] if hit else "",
            "match_method": method,
            "matched": int(hit is not None),
            "games_current": played[(current, hit["espn_id"])] if hit else 0,
            "games_prior": played[(prior, hit["espn_id"])] if hit else 0,
            "last_game": hit["last_game"] if hit else "",
            "home": int(p["home"]),
        })
        if line:
            home_spread = line["home_spread"]
            row.update({
                "game_total": line["total"],
                "team_spread": home_spread if p["home"] else -home_spread,
                "team_implied": line["home_implied"] if p["home"] else line["away_implied"],
                "opp_implied": line["away_implied"] if p["home"] else line["home_implied"],
                "odds_source": line["source"],
            })
        table.append(row)
        if not hit:
            unmatched.append(row)
    return table, unmatched


PROJECTION_COLUMNS = ["fppm", "minutes_base", "play_rate", "minutes_bump", "blowout_cut", "minutes",
                      "vegas_factor", "proj", "proj_source", "sd", "ceiling", "floor"]


def build_projections(table, lines, settings, current, prior) -> pd.DataFrame:
    seasons = [current] + ([prior] if settings["projections"]["use_prior_season"] else [])
    frames = [pd.read_csv(fetch_espn.GAMELOG_DIR / f"gamelogs_{s}.csv", dtype={"espn_id": str, "event_id": str})
              for s in seasons if (fetch_espn.GAMELOG_DIR / f"gamelogs_{s}.csv").exists()]
    logs = pd.concat(frames, ignore_index=True)
    players = pd.DataFrame(table)
    players["key"] = players["dk_id"]
    players["pos_group"] = players["roster_positions"].map(pos_groups)
    players["out"] = players["status"] == "OUT"
    players["fallback"] = pd.to_numeric(players["avg_ppg"], errors="coerce")
    team_lines = {}
    for g, ln in lines.items():
        away, home = g.split("@")
        team_lines[home] = {"implied": ln["home_implied"], "spread": ln["home_spread"]}
        team_lines[away] = {"implied": ln["away_implied"], "spread": -ln["home_spread"]}
    df = project(players, logs, team_lines, settings, current, prior)
    # reindex: line columns are absent when no game on the slate has a betting line yet
    return df.reindex(columns=PLAYER_COLUMNS + ["out"] + PROJECTION_COLUMNS).sort_values("proj", ascending=False)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-espn", action="store_true", help="don't download new box scores")
    args = ap.parse_args(argv)

    settings = load_settings()
    data = settings["data"]
    current, prior = data["current_season"], data["prior_season"]
    use_prior = settings["projections"]["use_prior_season"]

    print("1) Salaries")
    files = fetch_salaries.sync_salary_files(data["salary_repo"], data["salary_folder"])
    if not files:
        print("No salary files found. Nothing to do.")
        return 1
    latest = files[-1]
    slate_date, group_id = fetch_salaries.slate_info(latest)
    players = fetch_salaries.load_salary_file(latest)
    games = sorted({p["game"] for p in players})
    print(f"  slate {slate_date} (draft group {group_id}): {len(players)} players, {len(games)} games")

    print("2) ESPN box scores")
    seasons = [current] + ([prior] if use_prior else [])
    if not args.skip_espn:
        for season in seasons:
            print(f"  {fetch_espn.backfill_season(season, max_new=data['espn_max_new_games_per_run'])}")
            n = fetch_espn.backfill_lines(season, max_new=data["espn_max_new_games_per_run"])
            if n:
                print(f"  added closing betting lines to {n} older {season} games")
    logs = {}
    for season in seasons:
        out = fetch_espn.build_gamelogs(season)
        logs[season] = read_gamelogs(season)
        print(f"  {out.relative_to(REPO_ROOT)}: {len(logs[season])} player-game rows")

    print("3) Betting lines")
    # The salary file can be saved the day before the games, so use the games' own dates.
    game_dates = {date.fromisoformat(p["lock_time"][:10]) for p in players}
    lines = fetch_odds.get_slate_lines(games, game_dates, settings)

    print("4) Name matching")
    roster, played = espn_roster(logs)
    matcher = Matcher(roster, load_name_overrides())
    table, unmatched = build_player_table(players, matcher, played, lines, current, prior)
    methods = Counter(r["match_method"] for r in table)
    print(f"  matched {len(table) - len(unmatched)}/{len(table)}  {dict(methods)}")
    if unmatched:
        print(f"  UNMATCHED ({len(unmatched)}) - these use DK's average as a fallback projection:")
        for r in unmatched:
            print(f"    {r['name']} ({r['team']}, ${r['salary']}, {r['status'] or 'active'})")

    out_dir = SLATES / slate_date
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "players.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=PLAYER_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(table, key=lambda r: -r["salary"]))
    game_rows = []
    for g in games:
        lock = min(p["lock_time"] for p in players if p["game"] == g)
        game_rows.append({"game": g, "lock_time": lock, **(lines.get(g) or {})})
    (out_dir / "games.json").write_text(json.dumps(
        {"slate_date": slate_date, "draft_group_id": group_id, "salary_file": latest.name,
         "games": sorted(game_rows, key=lambda r: r["lock_time"])}, indent=1))
    (out_dir / "unmatched.txt").write_text(
        "".join(f"{r['name']}\t{r['team']}\t{r['salary']}\t{r['status']}\n" for r in unmatched))
    print(f"5) Wrote {out_dir.relative_to(REPO_ROOT)}/players.csv, games.json, unmatched.txt")

    print("6) Projections")
    proj = build_projections(table, lines, settings, current, prior)
    proj.to_csv(out_dir / "projections.csv", index=False)
    active = proj[~proj["out"]].sort_values("proj", ascending=False)
    print(f"  {len(active)} active players; sources {active['proj_source'].value_counts().to_dict()}")
    for _, r in active.head(10).iterrows():
        bump = f" (+{r['minutes_bump']:.1f} min bump)" if r["minutes_bump"] >= 1 else ""
        print(f"    {r['name']:<28} {r['team']} ${r['salary']:>5}  proj {r['proj']:5.1f}  "
              f"ceil {r['ceiling']:5.1f}  {r['minutes']:4.1f} min{bump}")
    print(f"  wrote {(out_dir / 'projections.csv').relative_to(REPO_ROOT)}")

    print("7) Publish for the phone app")
    payload = publish.build_payload(proj, game_rows, {"slate_date": slate_date, "draft_group_id": group_id,
                                                      "salary_file": latest.name}, settings)
    for path in publish.publish(payload):
        print(f"  wrote {path.relative_to(REPO_ROOT)}")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(f"## Slate {slate_date}\n\n{len(players)} players, {len(games)} games, "
                    f"{len(lines)}/{len(games)} with betting lines, "
                    f"{len(table) - len(unmatched)}/{len(table)} matched to ESPN.\n\n")
            if unmatched:
                f.write("**Unmatched players:** " + ", ".join(f"{r['name']} ({r['team']})" for r in unmatched) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
