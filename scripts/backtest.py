"""Backtest: replay past days and compare projections with actual DK points.

For each game day, projections are rebuilt using only games played BEFORE that
day, then compared with what players actually scored. Players who didn't play
that day are treated as OUT (their teammates get the minutes bump), and the
Vegas adjustment uses that game's closing line from ESPN.

When a DK salary file exists for the day, results are also grouped by salary
tier; otherwise by projection tier.

Usage:
  python scripts/backtest.py                    # current season to date
  python scripts/backtest.py --season 2026      # replay 2025-26 (no earlier season to blend in)
  python scripts/backtest.py --start 2026-11-01 --end 2026-11-06
Writes data/backtest/report_<season>.md and results_<season>.csv.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import yaml
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import fetch_espn, fetch_salaries  # noqa: E402
from pipeline.config import REPO_ROOT, load_name_overrides, load_settings  # noqa: E402
from pipeline.names import Matcher  # noqa: E402
from pipeline.project import played_only, pos_groups, project  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "backtest"


def load_logs(seasons) -> pd.DataFrame:
    frames = []
    for s in seasons:
        p = fetch_espn.GAMELOG_DIR / f"gamelogs_{s}.csv"
        if p.exists():
            frames.append(pd.read_csv(p, dtype={"espn_id": str, "event_id": str}))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def load_lines(season: int) -> dict[str, dict]:
    """event_id -> closing line {'total', 'home_spread', home, away}."""
    out = {}
    for f in (fetch_espn.RAW / "boxscores" / str(season)).glob("*.json"):
        box = json.loads(f.read_text())
        if box.get("odds"):
            out[box["event_id"]] = {**box["odds"], "home": box["home"], "away": box["away"]}
    return out


def salary_by_espn(day: str, logs_day: pd.DataFrame) -> dict[str, int]:
    """DK salaries for that day (if we have the file), keyed by ESPN id."""
    files = [f for f in fetch_salaries.RAW_DIR.glob(f"DKSalaries_NBA_{day}_*.csv")]
    if not files:
        return {}
    roster = (logs_day[["espn_id", "name", "team"]].drop_duplicates("espn_id")
              .to_dict("records"))
    m = Matcher(roster, load_name_overrides())
    out = {}
    for p in fetch_salaries.load_salary_file(files[0]):
        hit, _ = m.match(p["name"], p["team"])
        if hit:
            out[hit["espn_id"]] = p["salary"]
    return out


def replay_day(day: str, logs: pd.DataFrame, lines_by_event: dict, settings: dict,
               season: int, prior: int) -> pd.DataFrame:
    cfg = settings["projections"]
    hist = logs[logs["date"] < day]
    today = logs[(logs["date"] == day) & (logs["season"] == season)]
    if today.empty or played_only(hist[hist["season"] == season]).empty:
        return pd.DataFrame()
    played_today = played_only(today)

    # Lines for each team playing today.
    lines = {}
    for ev in today["event_id"].unique():
        ln = lines_by_event.get(ev)
        if not ln:
            continue
        hs, t = ln["home_spread"], ln["total"]
        lines[ln["home"]] = {"implied": t / 2 - hs / 2, "spread": hs}
        lines[ln["away"]] = {"implied": t / 2 + hs / 2, "spread": -hs}

    # Pool: everyone who played today, plus recent rotation players who sat (= OUT).
    hp = played_only(hist[hist["season"] == season])
    rows = []
    for team in today["team"].unique():
        opp = today[today["team"] == team]["opp"].iloc[0]
        recent_games = (hp[hp["team"] == team].drop_duplicates("event_id")
                        .sort_values("date", ascending=False)["event_id"].head(cfg["minutes_lookback_games"]))
        recent = set(hp[hp["event_id"].isin(recent_games) & (hp["team"] == team)]["espn_id"])
        playing = set(played_today[played_today["team"] == team]["espn_id"])
        for pid in recent | playing:
            src = pd.concat([today[today["espn_id"] == pid], hist[hist["espn_id"] == pid]])
            pos = src["pos"].dropna().iloc[0] if src["pos"].notna().any() else ""
            rows.append({"key": pid, "espn_id": pid, "team": team, "opp": opp,
                         "pos_group": pos_groups(pos), "out": pid not in playing, "fallback": np.nan})
    if not rows:
        return pd.DataFrame()
    proj = project(pd.DataFrame(rows), hist, lines, settings, season, prior)
    proj = proj[~proj["out"] & (proj["proj_source"] == "model")]

    actual = played_today.set_index("espn_id")
    proj["date"] = day
    proj["name"] = proj["espn_id"].map(actual["name"])
    proj["actual"] = proj["espn_id"].map(actual["dk_pts"])
    proj["actual_min"] = proj["espn_id"].map(actual["min"])
    proj["had_line"] = proj["team"].isin(lines.keys())

    # Naive baseline: season average DK points to date (last season's if none yet).
    hpl = played_only(hist)
    cur_avg = hpl[hpl["season"] == season].groupby("espn_id")["dk_pts"].mean()
    pri_avg = hpl[hpl["season"] == prior].groupby("espn_id")["dk_pts"].mean()
    proj["baseline"] = proj["espn_id"].map(cur_avg).fillna(proj["espn_id"].map(pri_avg))

    sal = salary_by_espn(day, today)
    proj["salary"] = proj["espn_id"].map(sal) if sal else np.nan
    return proj[["date", "espn_id", "name", "team", "salary", "proj", "actual", "baseline", "minutes",
                 "actual_min", "minutes_bump", "vegas_factor", "sd", "floor", "ceiling", "had_line"]]


def metrics(df: pd.DataFrame) -> dict:
    err = df["proj"] - df["actual"]
    b = df.dropna(subset=["baseline"])
    return {
        "players": len(df),
        "MAE": err.abs().mean(),
        "bias": err.mean(),
        "baseline MAE": (b["baseline"] - b["actual"]).abs().mean() if len(b) else np.nan,
        "minutes MAE": (df["minutes"] - df["actual_min"]).abs().mean(),
        "in floor-ceiling %": 100 * ((df["actual"] >= df["floor"]) & (df["actual"] <= df["ceiling"])).mean(),
        "over ceiling %": 100 * (df["actual"] > df["ceiling"]).mean(),
    }


def tier_labels(values: pd.Series, cuts: list, money: bool) -> pd.Series:
    def fmt(v):
        return f"${v / 1000:g}K" if money else f"{v:g}"
    edges = [-np.inf, *cuts, np.inf]
    labels = [f"under {fmt(cuts[0])}"] + [f"{fmt(a)}-{fmt(b)}" for a, b in zip(cuts, cuts[1:])] + \
             [f"{fmt(cuts[-1])}+"]
    return pd.cut(values, edges, labels=labels, right=False)


def report(res: pd.DataFrame, settings: dict, title: str) -> str:
    bt = settings["backtest"]
    lines = [f"# {title}", "",
             f"{res['date'].nunique()} days, {res['date'].min()} to {res['date'].max()}. "
             "Error = projection minus actual DK points (positive bias = we projected too high).", "",
             "| Group | Players | MAE | Bias | Baseline MAE | Minutes MAE | Inside floor-ceiling | Over ceiling |",
             "|---|---|---|---|---|---|---|---|"]

    def row(name, d):
        m = metrics(d)
        lines.append(f"| {name} | {m['players']} | {m['MAE']:.2f} | {m['bias']:+.2f} | {m['baseline MAE']:.2f} "
                     f"| {m['minutes MAE']:.2f} | {m['in floor-ceiling %']:.0f}% | {m['over ceiling %']:.0f}% |")

    row("**All**", res)
    sal = res.dropna(subset=["salary"])
    if len(sal):
        for label, d in sal.groupby(tier_labels(sal["salary"], bt["salary_tiers"], True), observed=True):
            row(f"Salary {label}", d)
    for label, d in res.groupby(tier_labels(res["proj"], bt["projection_tiers"], False), observed=True):
        row(f"Projected {label} pts", d)
    row("Games with a Vegas line", res[res["had_line"]])
    if (~res["had_line"]).any():
        row("Games without a line", res[~res["had_line"]])
    lines += ["", "Baseline = player's season average DK points to date (what a naive projection would say).",
              "Inside floor-ceiling should be about 80% and over ceiling about 10% if the spread is right."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    settings = load_settings()
    ap = argparse.ArgumentParser(description="Replay past days and score the projections.")
    ap.add_argument("--season", type=int, default=settings["data"]["current_season"])
    ap.add_argument("--start", help="first day (YYYY-MM-DD)")
    ap.add_argument("--end", help="last day (YYYY-MM-DD)")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                    help="try a different projections setting, e.g. --set vegas_exponent=0")
    args = ap.parse_args(argv)
    for kv in args.set:
        k, v = kv.split("=", 1)
        settings["projections"][k] = yaml.safe_load(v)

    season, prior = args.season, args.season - 1
    logs = load_logs([prior, season])
    if logs.empty:
        print("No game logs. Run the pipeline first.")
        return 1
    lines_by_event = load_lines(season)
    days = sorted(logs[logs["season"] == season]["date"].unique())
    days = [d for d in days if (not args.start or d >= args.start) and (not args.end or d <= args.end)]

    results = []
    for day in days:
        r = replay_day(day, logs, lines_by_event, settings, season, prior)
        if not r.empty:
            results.append(r)
    if not results:
        print("Nothing to backtest in that range.")
        return 1
    res = pd.concat(results, ignore_index=True)
    label = f"{season - 1}-{str(season)[2:]}"
    tweaks = f" ({', '.join(args.set)})" if args.set else ""
    text = report(res, settings, f"Backtest {label}{tweaks}")
    print(text)
    if not args.set:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / f"report_{season}.md").write_text(text)
        res.to_csv(OUT_DIR / f"results_{season}.csv", index=False)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
