"""Slate review: after a main slate is final, find the best lineup in hindsight and
see how our pre-lock projections stacked up.

For every slate in data/slates/ whose games all have final box scores and that has
no review yet (backfill), this writes:
  data/review/<gameDate>.json           the review (also docs/data/review_<gameDate>.json)
  data/review/<gameDate>_players.csv    every player: pre-lock features + actual result
  docs/data/review_latest.json          newest review (the app opens this first)
  docs/data/review_index.json           list of reviewed dates

Projections used: projections_prelock.csv (saved by the last pipeline run before lock).
If a slate has none, projections are rebuilt with the backtest replay (only games
before that day) and the review is marked "rebuilt projections".

Lineups (ours and the hindsight optimum) come from the app's own optimizer, run in
Node (web/scripts/review_lineups.mjs). Every lineup passes validateLineup().

Usage:
  python -m pipeline.review                 # review every finished slate without a review
  python -m pipeline.review --date 2026-11-07 --force
All tunables are under `review:` in config/settings.yaml.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import tempfile
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline import fetch_espn
from pipeline.config import REPO_ROOT, load_name_overrides, load_settings
from pipeline.names import Matcher
from pipeline.ownership import estimate_ownership

SLATES = REPO_ROOT / "data" / "slates"
REVIEW_DIR = REPO_ROOT / "data" / "review"
DOCS_DATA = REPO_ROOT / "docs" / "data"
WEB_DIR = REPO_ROOT / "web"
PRELOCK_FILE = "projections_prelock.csv"
SCHEMA_VERSION = 1
SLOTS = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]


# ---------- small helpers ----------

def _num(v, digits=2):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else round(f, digits)


def _str(v) -> str:
    return "" if v is None or (isinstance(v, float) and math.isnan(v)) else str(v)


def game_date_of(games: dict) -> str:
    """The day the games are played (the salary file is often saved the day before)."""
    locks = sorted(g["lock_time"] for g in games["games"])
    return locks[0][:10] if locks else games["slate_date"]


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype={"dk_id": str, "espn_id": str})


def load_logs(seasons) -> pd.DataFrame:
    frames = []
    for s in seasons:
        p = fetch_espn.GAMELOG_DIR / f"gamelogs_{s}.csv"
        if p.exists():
            frames.append(pd.read_csv(p, dtype={"espn_id": str, "event_id": str}))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["season", "event_id", "date", "team", "opp", "espn_id", "dnp", "min", "dk_pts"])


# ---------- which slates are ready ----------

def final_games(games: dict, logs_day: pd.DataFrame) -> tuple[list[str], list[str]]:
    """(games with box scores for both teams, games still missing)."""
    teams = set(logs_day["team"]) if len(logs_day) else set()
    done, missing = [], []
    for g in games["games"]:
        away, home = g["game"].split("@")
        (done if away in teams and home in teams else missing).append(g["game"])
    return done, missing


def slate_status(gdate: str, done: list, missing: list, cfg: dict, today: date) -> str:
    """'ready', or 'waiting' while box scores are still coming in.

    A game that still has no box score `postponed_after_days` after its date is
    treated as postponed, and the slate is reviewed without it.
    """
    if not missing:
        return "ready"
    if done and date.fromisoformat(gdate) + timedelta(days=cfg["postponed_after_days"]) <= today:
        return "ready"
    return "waiting"


# ---------- projections used ----------

def projection_frame(slate_dir: Path, gdate: str, settings: dict) -> tuple[pd.DataFrame, dict]:
    """Our projections for the slate plus where they came from."""
    pre = slate_dir / PRELOCK_FILE
    if pre.exists():
        df = read_csv(pre)
        info = {"source": "prelock", "snapshotAt": _str(df["snapshot_at"].iloc[0]) if "snapshot_at" in df else "",
                "note": "Pre-lock projections from the last pipeline run before the first game locked."}
        return df, info
    return rebuild_projections(slate_dir, gdate, settings), {
        "source": "rebuilt", "snapshotAt": "",
        "note": ("Rebuilt projections: no pre-lock snapshot was saved for this slate, so projections were "
                 "rebuilt with the backtest replay from games before this day. The replay knows who sat, so "
                 "minutes bumps are sharper than they were before lock and there are no late scratches.")}


def rebuild_projections(slate_dir: Path, gdate: str, settings: dict) -> pd.DataFrame:
    from scripts.backtest import load_lines, load_logs as bt_logs, replay_day  # noqa: PLC0415

    cfg = settings["projections"]
    season, prior = settings["data"]["current_season"], settings["data"]["prior_season"]
    players = read_csv(slate_dir / "players.csv")
    logs = bt_logs([prior, season])
    rep = replay_day(gdate, logs, load_lines(season), settings, season, prior)
    keep = ["espn_id", "proj", "sd", "floor", "ceiling", "minutes", "minutes_bump", "vegas_factor"]
    rep = rep[keep].drop_duplicates("espn_id") if len(rep) else pd.DataFrame(columns=keep)
    df = players.merge(rep, on="espn_id", how="left")

    # Players the replay has no model for: DK's average if they played that day (rookies
    # and players with no history), otherwise treated as OUT.
    played_today = set(logs[(logs["date"] == gdate) & (logs["dnp"] == 0) & (logs["min"] > 0)]["espn_id"])
    no_model = df["proj"].isna()
    fallback = no_model & df["espn_id"].isin(played_today)
    df.loc[fallback, "proj"] = pd.to_numeric(df.loc[fallback, "avg_ppg"], errors="coerce")
    sd = settings["review"]["fallback_sd_pct"] * df["proj"]
    df.loc[fallback, "sd"] = sd[fallback]
    df.loc[fallback, "ceiling"] = (df["proj"] + cfg["ceiling_z"] * sd)[fallback]
    df.loc[fallback, "floor"] = (df["proj"] - cfg["floor_z"] * sd).clip(lower=0)[fallback]
    df["proj_source"] = np.where(fallback, "dk_avg", np.where(no_model, "none", "model"))
    df["proj"] = df["proj"].fillna(0.0)
    df["minutes_bump"] = df["minutes_bump"].fillna(0.0)
    df["out"] = df["proj"] <= 0
    df["own"] = estimate_ownership(df, settings["ownership"], cfg["ownership_total_pct"])
    return df


# ---------- actual results ----------

def join_actuals(proj: pd.DataFrame, logs_day: pd.DataFrame, missing_games: list[str] = ()) -> pd.DataFrame:
    """Add actual DK points and how each player's night went.

    result:  played | dnp (in the box score, 0 minutes) | not_in_box (inactive) |
             unmatched (no ESPN id, so no result) | postponed (game never finished)
    Did not play = 0 points. late_scratch = projected to play but 0 minutes.
    """
    df = proj.copy()
    df["espn_id"] = df["espn_id"].fillna("").astype(str).replace("nan", "")
    box = logs_day.drop_duplicates("espn_id").set_index("espn_id") if len(logs_day) else pd.DataFrame()
    results, actual, minutes = [], [], []
    for _, r in df.iterrows():
        eid = r["espn_id"]
        if r["game"] in missing_games:
            res, pts, mins = "postponed", 0.0, 0.0
        elif not eid:
            res, pts, mins = "unmatched", 0.0, np.nan
        elif eid in box.index:
            b = box.loc[eid]
            played = int(b["dnp"]) == 0 and pd.notna(b["min"]) and float(b["min"]) > 0
            res = "played" if played else "dnp"
            pts, mins = (float(b["dk_pts"]), float(b["min"])) if played else (0.0, 0.0)
        else:
            res, pts, mins = "not_in_box", 0.0, 0.0
        results.append(res)
        actual.append(pts)
        minutes.append(mins)
    df["result"] = results
    df["actual"] = actual
    df["actual_min"] = minutes
    df["out"] = df["out"].astype(str).str.lower().isin(["true", "1", "1.0"])
    df["proj"] = pd.to_numeric(df["proj"], errors="coerce").fillna(0.0)
    df["projected_to_play"] = ~df["out"] & (df["proj"] > 0)
    df["late_scratch"] = df["projected_to_play"] & df["result"].isin(["dnp", "not_in_box"])
    return df


def rematch_unmatched(proj: pd.DataFrame, logs_day: pd.DataFrame, overrides: dict | None = None) -> pd.DataFrame:
    """Players with no ESPN id before lock (often rookies with no games yet) may have
    played tonight: try to match them against tonight's box scores by team + name."""
    df = proj.copy()
    df["espn_id"] = df["espn_id"].fillna("").astype(str).replace("nan", "")
    if not len(logs_day):
        return df
    roster = logs_day[["espn_id", "name", "team"]].drop_duplicates("espn_id").to_dict("records")
    m = Matcher(roster, overrides or {})
    for i, r in df[df["espn_id"] == ""].iterrows():
        hit, _ = m.match(r["name"], r["team"])
        if hit:
            df.at[i, "espn_id"] = hit["espn_id"]
    return df


def accuracy(df: pd.DataFrame) -> dict:
    """Projection accuracy on players we projected to play who did play (late scratches excluded)."""
    d = df[df["projected_to_play"] & (df["result"] == "played")]
    if d.empty:
        return {"players": 0, "mae": None, "bias": None, "overCeilingPct": None, "insideRangePct": None}
    err = d["proj"] - d["actual"]
    return {
        "players": int(len(d)),
        "mae": _num(err.abs().mean()),
        "bias": _num(err.mean()),
        "overCeilingPct": _num(100 * (d["actual"] > d["ceiling"]).mean(), 1),
        "insideRangePct": _num(100 * ((d["actual"] >= d["floor"]) & (d["actual"] <= d["ceiling"])).mean(), 1),
        "lateScratches": int(df["late_scratch"].sum()),
        "playedButProjectedOut": int((~df["projected_to_play"] & (df["result"] == "played")).sum()),
    }


# ---------- lineups through the app's optimizer ----------

def app_player(r) -> dict:
    return {
        "id": str(r["dk_id"]), "name": r["name"], "team": r["team"], "opp": r["opp"], "game": r["game"],
        "salary": int(r["salary"]), "slots": str(r["roster_positions"]).split("/"),
        "status": _str(r.get("status")), "proj": _num(r["proj"]) or 0.0, "floor": _num(r.get("floor")),
        "ceiling": _num(r.get("ceiling")), "sd": _num(r.get("sd")), "own": _num(r.get("own"), 1) or 0.0,
        "actual": _num(r["actual"]) or 0.0,
    }


def run_optimizer(players: list[dict], jobs: list[dict]) -> dict:
    """Run web/scripts/review_lineups.mjs (the app's buildLineups) and return its output."""
    if not (WEB_DIR / "node_modules" / "highs").exists():
        raise RuntimeError("web/node_modules is missing: run `npm ci` in web/ first.")
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp) / "in.json", Path(tmp) / "out.json"
        src.write_text(json.dumps({"players": players, "jobs": jobs}))
        subprocess.run(["node", "scripts/review_lineups.mjs", str(src), str(dst)], cwd=WEB_DIR, check=True)
        return json.loads(dst.read_text())


# ---------- composition ----------

def composition(ids: list[str], by_id: dict, game_totals: dict, cfg: dict) -> dict:
    ps = [by_id[i] for i in ids]
    per_game = Counter(p["game"] for p in ps)
    top_game, top_n = per_game.most_common(1)[0]
    best_total = max((t for t in game_totals.values() if t is not None), default=None)
    teams = sorted({p["team"] for p in ps})
    return {
        "salary": int(sum(p["salary"] for p in ps)),
        "stars": sum(p["salary"] >= cfg["star_salary"] for p in ps),
        "values": sum(p["salary"] < cfg["value_salary"] for p in ps),
        "maxFromOneGame": top_n,
        "maxGame": top_game,
        "maxGameIsHighestTotal": (None if best_total is None or game_totals.get(top_game) is None
                                  else bool(game_totals[top_game] >= best_total)),
        "teams": teams,
        "teamCount": len(teams),
        "games": len(per_game),
        "ownSum": _num(sum(p["own"] or 0 for p in ps), 1),
        "proj": _num(sum(p["proj"] for p in ps), 1),
        "actual": _num(sum(p["actual"] for p in ps), 1),
    }


def summarize_compositions(comps: list[dict]) -> dict:
    if not comps:
        return {}
    mean = lambda k: _num(np.mean([c[k] for c in comps]), 2)  # noqa: E731
    flags = [c["maxGameIsHighestTotal"] for c in comps if c["maxGameIsHighestTotal"] is not None]
    teams = Counter(t for c in comps for t in c["teams"])
    return {
        "lineups": len(comps),
        "avgSalary": mean("salary"), "avgStars": mean("stars"), "avgValues": mean("values"),
        "avgMaxFromOneGame": mean("maxFromOneGame"), "avgTeamCount": mean("teamCount"),
        "avgOwnSum": mean("ownSum"), "avgActual": mean("actual"),
        "maxFromOneGameCounts": {str(k): v for k, v in sorted(Counter(c["maxFromOneGame"] for c in comps).items())},
        "starsCounts": {str(k): v for k, v in sorted(Counter(c["stars"] for c in comps).items())},
        "pctMaxGameIsHighestTotal": _num(100 * np.mean(flags), 1) if flags else None,
        "teamUsage": dict(teams.most_common()),
    }


def classify_miss(p: dict, in_ours: bool, cfg: dict) -> str:
    """Why an optimal player was (or wasn't) in our lineup.

    in our lineup     - we had him
    projection miss   - he scored far above our ceiling (we couldn't have seen it)
    settings miss     - our range covered his score, but he ranked low in our value ranking
    close call        - ranked well by us, but the optimizer used someone else
    """
    if in_ours:
        return "in our lineup"
    if p["ceiling"] is None or p["actual"] > p["ceiling"] + cfg["projection_miss_margin"]:
        return "projection miss"
    if p["valueRank"] is None or p["valueRank"] > cfg["settings_miss_value_rank"]:
        return "settings miss"
    return "close call"


# ---------- the review ----------

def build_review(slate_dir: Path, settings: dict, logs: pd.DataFrame, today: date | None = None,
                 optimizer=run_optimizer) -> tuple[dict | None, pd.DataFrame | None, str]:
    """Returns (review, players table, status message). review is None if not ready."""
    cfg = settings["review"]
    today = today or fetch_espn.today_et()
    games = json.loads((slate_dir / "games.json").read_text())
    gdate = game_date_of(games)
    logs_day = logs[logs["date"] == gdate] if len(logs) else logs
    done, missing = final_games(games, logs_day)
    if slate_status(gdate, done, missing, cfg, today) != "ready":
        return None, None, f"{gdate}: waiting for box scores ({len(done)}/{len(done) + len(missing)} games final)"

    proj, proj_info = projection_frame(slate_dir, gdate, settings)
    df = join_actuals(rematch_unmatched(proj, logs_day, load_name_overrides()), logs_day, missing)
    df["value"] = df["proj"] / (df["salary"] / 1000)
    ranked = df[df["projected_to_play"]]
    df["value_rank"] = ranked["value"].rank(ascending=False, method="min")
    df["proj_rank"] = ranked["proj"].rank(ascending=False, method="min")

    players = [app_player(r) for _, r in df.iterrows()]
    by_id = {p["id"]: p for p in players}
    for p, (_, r) in zip(players, df.iterrows()):
        p["valueRank"] = None if pd.isna(r["value_rank"]) else int(r["value_rank"])
        p["projRank"] = None if pd.isna(r["proj_rank"]) else int(r["proj_rank"])

    opt_cfg = settings["optimizer"]
    jobs = [
        {"key": "hindsight", "projField": "actual",
         "options": {"mode": "cash", "count": cfg["hindsight_top_n"], "minUnique": cfg["hindsight_min_unique"],
                     "salaryCap": opt_cfg["salary_cap"], "includeOut": True}},
        {"key": "ours", "projField": "proj",
         "options": {"mode": "cash", "count": 1, "salaryCap": opt_cfg["salary_cap"],
                     "floorWeight": opt_cfg["cash_floor_weight"]}},
    ]
    res = optimizer(players, jobs)
    hind = res["jobs"]["hindsight"]["lineups"]
    ours_l = res["jobs"]["ours"]["lineups"]
    if not hind or not ours_l:
        raise RuntimeError(f"{gdate}: optimizer found no lineup")
    best_ids, our_ids = hind[0]["ids"], ours_l[0]["ids"]
    game_totals = {g["game"]: g.get("total") for g in games["games"]}

    def lineup_detail(ids, with_miss=False):
        rows = []
        for slot, pid in zip(SLOTS, ids):
            p = by_id[pid]
            row = {"slot": slot, "id": pid, "name": p["name"], "team": p["team"], "game": p["game"],
                   "salary": p["salary"], "proj": p["proj"], "ceiling": p["ceiling"], "own": p["own"],
                   "actual": p["actual"], "valueRank": p["valueRank"], "projRank": p["projRank"]}
            if with_miss:
                row["missType"] = classify_miss(p, pid in our_ids, cfg)
            rows.append(row)
        return rows

    sum_of = lambda ids, k: round(sum(by_id[i][k] for i in ids), 2)  # noqa: E731
    optimal_actual, our_actual = sum_of(best_ids, "actual"), sum_of(our_ids, "actual")
    optimal_ourproj, our_proj = sum_of(best_ids, "proj"), sum_of(our_ids, "proj")

    df["smash"] = df["actual"] >= cfg["smash_multiplier"] * df["salary"] / 1000
    smash = []
    for _, r in df[df["smash"] & (df["actual"] > 0)].sort_values("actual", ascending=False).iterrows():
        smash.append({
            "id": str(r["dk_id"]), "name": r["name"], "team": r["team"], "pos": r["positions"],
            "salary": int(r["salary"]), "actual": _num(r["actual"]),
            "multiple": _num(r["actual"] / (r["salary"] / 1000), 2),
            # pre-lock features only
            "minutesBump": _num(r.get("minutes_bump"), 1), "teamImplied": _num(r.get("team_implied"), 1),
            "spread": _num(r.get("team_spread"), 1), "proj": _num(r["proj"]), "ceiling": _num(r.get("ceiling")),
            "own": _num(r.get("own"), 1), "projectedToPlay": bool(r["projected_to_play"]),
        })

    in_top = Counter(i for lu in hind for i in lu["ids"])
    df["in_optimal"] = df["dk_id"].astype(str).isin(best_ids)
    df["in_top_n"] = df["dk_id"].astype(str).map(lambda i: in_top.get(i, 0))
    df["in_our_lineup"] = df["dk_id"].astype(str).isin(our_ids)

    no_result = [{"id": str(r["dk_id"]), "name": r["name"], "team": r["team"], "salary": int(r["salary"]),
                  "status": _str(r.get("status")), "reason": r["result"]}
                 for _, r in df.iterrows()
                 if r["result"] in ("unmatched", "postponed")
                 or (r["result"] == "not_in_box" and r["projected_to_play"])]
    late = [{"id": str(r["dk_id"]), "name": r["name"], "team": r["team"], "salary": int(r["salary"]),
             "proj": _num(r["proj"]), "status": _str(r.get("status"))}
            for _, r in df[df["late_scratch"]].iterrows()]

    review = {
        "schema": SCHEMA_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "gameDate": gdate,
        "fileDate": games["slate_date"],
        "draftGroupId": games.get("draft_group_id"),
        "salaryFile": games.get("salary_file"),
        "projections": proj_info,
        "games": [{"game": g["game"], "lock": g["lock_time"], "total": _num(g.get("total"), 1),
                   "homeSpread": _num(g.get("home_spread"), 1), "final": g["game"] in done} for g in games["games"]],
        "accuracy": accuracy(df),
        "lateScratches": late,
        "noResult": no_result,
        "optimal": {"actual": optimal_actual, "ourProj": optimal_ourproj, "players": lineup_detail(best_ids, True),
                    "composition": composition(best_ids, by_id, game_totals, cfg)},
        "ours": {"actual": our_actual, "proj": our_proj, "players": lineup_detail(our_ids),
                 "composition": composition(our_ids, by_id, game_totals, cfg)},
        "standing": {
            "ourActual": our_actual, "optimalActual": optimal_actual,
            "pctOfOptimal": _num(100 * our_actual / optimal_actual, 1) if optimal_actual else None,
            "optimalOurProj": optimal_ourproj, "ourProj": our_proj,
            "projGap": _num(our_proj - optimal_ourproj),
            "overlap": len(set(best_ids) & set(our_ids)),
        },
        "topN": {
            "count": len(hind), "minUnique": cfg["hindsight_min_unique"],
            "scores": [lu["proj"] for lu in hind],
            "composition": summarize_compositions([composition(lu["ids"], by_id, game_totals, cfg) for lu in hind]),
            "playerCounts": [{"id": i, "name": by_id[i]["name"], "count": n} for i, n in in_top.most_common(15)],
        },
        "smash": smash,
        "settings": {k: cfg[k] for k in ("hindsight_top_n", "hindsight_min_unique", "smash_multiplier",
                                          "star_salary", "value_salary", "projection_miss_margin",
                                          "settings_miss_value_rank")},
        "solver": res.get("solver"),
    }
    errs = validate_review(review)
    if errs:
        raise RuntimeError(f"{gdate}: review failed its schema check: {errs}")
    return review, df, f"{gdate}: reviewed ({proj_info['source']} projections)"


# ---------- schema ----------

REQUIRED = {
    "": ["schema", "generatedAt", "gameDate", "fileDate", "projections", "games", "accuracy", "lateScratches",
         "noResult", "optimal", "ours", "standing", "topN", "smash", "settings"],
    "projections": ["source", "snapshotAt", "note"],
    "optimal": ["actual", "ourProj", "players", "composition"],
    "ours": ["actual", "proj", "players", "composition"],
    "standing": ["ourActual", "optimalActual", "pctOfOptimal", "optimalOurProj", "ourProj", "projGap"],
    "topN": ["count", "scores", "composition", "playerCounts"],
}
PLAYER_KEYS = ["slot", "id", "name", "team", "salary", "proj", "ceiling", "own", "actual"]
COMP_KEYS = ["salary", "stars", "values", "maxFromOneGame", "maxGameIsHighestTotal", "teams", "ownSum"]
SMASH_KEYS = ["id", "name", "salary", "pos", "actual", "minutesBump", "teamImplied", "spread", "proj", "ceiling", "own"]


def validate_review(doc: dict) -> list[str]:
    """Light schema check (no extra dependency). Returns a list of problems."""
    errs = []
    for section, keys in REQUIRED.items():
        obj = doc.get(section) if section else doc
        if not isinstance(obj, dict):
            errs.append(f"missing section {section}")
            continue
        errs += [f"{section or 'root'}.{k} missing" for k in keys if k not in obj]
    if errs:
        return errs
    if doc["schema"] != SCHEMA_VERSION:
        errs.append("wrong schema version")
    if doc["projections"]["source"] not in ("prelock", "rebuilt"):
        errs.append("projections.source must be prelock or rebuilt")
    for key in ("optimal", "ours"):
        ps = doc[key]["players"]
        if [p.get("slot") for p in ps] != SLOTS:
            errs.append(f"{key}.players must be 8 players in slot order")
        errs += [f"{key}.players[].{k} missing" for k in PLAYER_KEYS if any(k not in p for p in ps)]
        errs += [f"{key}.composition.{k} missing" for k in COMP_KEYS if k not in doc[key]["composition"]]
    if any("missType" not in p for p in doc["optimal"]["players"]):
        errs.append("optimal.players[].missType missing")
    for s in doc["smash"]:
        errs += [f"smash[].{k} missing" for k in SMASH_KEYS if k not in s]
    if doc["topN"]["scores"] and abs(doc["topN"]["scores"][0] - doc["optimal"]["actual"]) > 0.05:
        errs.append("topN.scores[0] must equal optimal.actual")
    if doc["ours"]["actual"] > doc["optimal"]["actual"] + 0.05:
        errs.append("our lineup cannot beat the hindsight optimum")
    return sorted(set(errs))


# ---------- writing ----------

PLAYER_CSV_COLUMNS = [
    "dk_id", "name", "team", "opp", "game", "positions", "roster_positions", "salary", "status", "espn_id",
    "matched", "out", "projected_to_play", "proj", "ceiling", "floor", "sd", "own", "minutes", "minutes_bump",
    "team_implied", "team_spread", "game_total", "value", "value_rank", "proj_rank",
    "result", "actual", "actual_min", "late_scratch", "smash", "in_optimal", "in_top_n", "in_our_lineup",
]


def write_review(review: dict, players: pd.DataFrame, review_dir: Path = REVIEW_DIR,
                 docs_dir: Path = DOCS_DATA) -> list[Path]:
    review_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)
    gdate = review["gameDate"]
    text = json.dumps(review, indent=1)
    paths = [review_dir / f"{gdate}.json", docs_dir / f"review_{gdate}.json"]
    for p in paths:
        p.write_text(text, encoding="utf-8")
    csv_path = review_dir / f"{gdate}_players.csv"
    players.reindex(columns=PLAYER_CSV_COLUMNS).to_csv(csv_path, index=False)
    return paths + [csv_path] + write_index(review_dir, docs_dir)


def write_index(review_dir: Path = REVIEW_DIR, docs_dir: Path = DOCS_DATA) -> list[Path]:
    """docs/data/review_index.json (newest first) and review_latest.json."""
    entries = []
    for f in sorted(review_dir.glob("????-??-??.json"), reverse=True):
        r = json.loads(f.read_text())
        entries.append({"date": r["gameDate"], "optimal": r["standing"]["optimalActual"],
                        "ours": r["standing"]["ourActual"], "pctOfOptimal": r["standing"]["pctOfOptimal"],
                        "projections": r["projections"]["source"]})
    index = {"generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "dates": entries}
    out = [docs_dir / "review_index.json"]
    out[0].write_text(json.dumps(index, indent=1), encoding="utf-8")
    if entries:
        latest = review_dir / f"{entries[0]['date']}.json"
        out.append(docs_dir / "review_latest.json")
        out[1].write_text(latest.read_text(), encoding="utf-8")
    return out


def summary_text(r: dict) -> str:
    s, a = r["standing"], r["accuracy"]
    lines = [f"## Slate review {r['gameDate']}" + (" (rebuilt projections)" if r["projections"]["source"] == "rebuilt" else ""),
             "",
             f"Hindsight-optimal lineup: **{s['optimalActual']:.1f}** DK points "
             f"(our projections had it at {s['optimalOurProj']:.1f}).",
             f"Our best projected lineup scored **{s['ourActual']:.1f}** ({s['pctOfOptimal']}% of optimal; "
             f"projected {s['ourProj']:.1f}, {s['overlap']}/8 players shared with the optimum).",
             f"Projection accuracy: MAE {a['mae']}, bias {a['bias']:+} on {a['players']} players; "
             f"{a['overCeilingPct']}% beat their ceiling. Late scratches: {a['lateScratches']}.",
             "", "| Slot | Player | Salary | Proj | Ceiling | Own % | Actual | Why |", "|---|---|---|---|---|---|---|---|"]
    for p in r["optimal"]["players"]:
        lines.append(f"| {p['slot']} | {p['name']} | ${p['salary']:,} | {p['proj']} | {p['ceiling']} | {p['own']} "
                     f"| {p['actual']} | {p['missType']} |")
    if r["smash"]:
        lines += ["", "Smash plays: " + ", ".join(f"{x['name']} ({x['actual']} at ${x['salary']:,})" for x in r["smash"])]
    if r["noResult"]:
        lines += ["", "No actual result: " + ", ".join(f"{x['name']} ({x['reason']})" for x in r["noResult"])]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Review finished slates (hindsight-optimal lineups).")
    ap.add_argument("--date", help="only review the slate played on this day (YYYY-MM-DD)")
    ap.add_argument("--force", action="store_true", help="redo reviews that already exist")
    args = ap.parse_args(argv)

    settings = load_settings()
    logs = load_logs([settings["data"]["current_season"], settings["data"]["prior_season"]])
    done_any = False
    for slate_dir in sorted(p for p in SLATES.iterdir() if (p / "games.json").exists() and (p / "players.csv").exists()):
        gdate = game_date_of(json.loads((slate_dir / "games.json").read_text()))
        if args.date and gdate != args.date:
            continue
        if (REVIEW_DIR / f"{gdate}.json").exists() and not args.force:
            continue
        review, players, msg = build_review(slate_dir, settings, logs)
        print(msg)
        if review is None:
            continue
        for p in write_review(review, players):
            print(f"  wrote {p.relative_to(REPO_ROOT)}")
        text = summary_text(review)
        print(text)
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
                f.write(text)
        done_any = True
    if not done_any:
        print("No new slates to review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
