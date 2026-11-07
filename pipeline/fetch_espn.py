"""Fetch NBA scoreboards and box scores from ESPN's public site API.

ESPN game summaries are ~400 KB each, too big to keep in git for 1,500 games,
so we save a compact copy of each finished game (teams, score, every player's
stat line) in data/raw/espn/boxscores/<season>/<event_id>.json. A game is only
ever downloaded once. Scoreboards for finished days are cached the same way.
"""
from __future__ import annotations

import csv
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from pipeline import http
from pipeline.config import REPO_ROOT
from pipeline.scoring import dk_points
from pipeline.teams import canon

BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
RAW = REPO_ROOT / "data" / "raw" / "espn"
GAMELOG_DIR = REPO_ROOT / "data" / "gamelogs"
REGULAR_SEASON = 2
SETTLED = {"STATUS_FINAL", "STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_FORFEIT"}
ET = ZoneInfo("America/New_York")
PAUSE = 0.2  # seconds between ESPN requests

STAT_FIELDS = ["min", "pts", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta",
               "reb", "oreb", "dreb", "ast", "stl", "blk", "tov", "pf", "pm"]


def today_et() -> date:
    return datetime.now(ET).date()


# ---------- scoreboard ----------

def compact_scoreboard(sb: dict) -> list[dict]:
    games = []
    for ev in sb.get("events", []):
        comp = ev["competitions"][0]
        teams = {c["homeAway"]: c for c in comp["competitors"]}
        if not all(_safe_canon(teams.get(s, {}).get("team", {}).get("abbreviation", "")) for s in ("home", "away")):
            continue  # All-Star, international or exhibition opponents
        games.append({
            "event_id": ev["id"],
            "start": ev["date"],
            "season": ev["season"]["year"],
            "season_type": ev["season"]["type"],
            "status": ev["status"]["type"]["name"],
            "home": canon(teams["home"]["team"]["abbreviation"]),
            "away": canon(teams["away"]["team"]["abbreviation"]),
            "home_score": _int(teams["home"].get("score")),
            "away_score": _int(teams["away"].get("score")),
            "odds": parse_espn_odds(comp.get("odds"), canon(teams["home"]["team"]["abbreviation"]),
                                    canon(teams["away"]["team"]["abbreviation"])),
        })
    return games


def parse_espn_odds(odds: list | None, home: str, away: str) -> dict | None:
    """ESPN odds -> {'total', 'home_spread'} (home_spread negative when home is favored)."""
    if not odds:
        return None
    o = odds[0]
    total = o.get("overUnder")
    spread = o.get("spread")
    if total is None or spread is None:
        return None
    spread = abs(float(spread))
    home_fav = (o.get("homeTeamOdds") or {}).get("favorite")
    if home_fav is None:  # fall back to the "DEN -7.5" text
        details = (o.get("details") or "").split()
        home_fav = bool(details) and _safe_canon(details[0]) == home
    return {"total": float(total), "home_spread": -spread if home_fav else spread,
            "source": "espn", "book": (o.get("provider") or {}).get("name")}


def fetch_scoreboard(day: date, *, use_cache: bool = True) -> list[dict]:
    """Games on an ET calendar day. Finished days are cached and never re-fetched."""
    path = RAW / "scoreboard" / f"{day:%Y%m%d}.json"
    if use_cache and path.exists():
        return json.loads(path.read_text())
    r = http.get(f"{BASE}/scoreboard", params={"dates": f"{day:%Y%m%d}"}, pause=PAUSE)
    r.raise_for_status()
    games = compact_scoreboard(r.json())
    old = day < today_et() - timedelta(days=3)
    if day < today_et() and (old or all(g["status"] in SETTLED for g in games)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(games, indent=0))
    return games


def season_days(season: int) -> list[date]:
    """Every regular-season calendar day for an ESPN season label (2027 = 2026-27)."""
    path = RAW / "calendar" / f"{season}.json"
    if path.exists():
        return [date.fromisoformat(d) for d in json.loads(path.read_text())]
    probe = date(season, 1, 15)  # mid-January is always inside the regular season
    r = http.get(f"{BASE}/scoreboard", params={"dates": f"{probe:%Y%m%d}"}, pause=PAUSE)
    r.raise_for_status()
    league = r.json()["leagues"][0]
    days = sorted({c[:10] for c in league.get("calendar", []) if isinstance(c, str)})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(days))
    return [date.fromisoformat(d) for d in days]


# ---------- box scores ----------

def compact_boxscore(summary: dict, game: dict) -> dict:
    players = []
    for team_block in summary["boxscore"].get("players", []):
        team = canon(team_block["team"]["abbreviation"])
        for stat_group in team_block.get("statistics", []):
            keys = stat_group.get("keys", [])
            for a in stat_group.get("athletes", []):
                ath = a.get("athlete") or {}
                if not ath.get("id"):
                    continue  # ESPN occasionally lists a player with no ID; can't use the row
                stats = dict(zip(keys, a.get("stats") or []))
                line = parse_stat_line(stats)
                players.append({
                    "espn_id": ath["id"],
                    "name": ath.get("displayName") or ath.get("shortName", ""),
                    "team": team,
                    "pos": (ath.get("position") or {}).get("abbreviation", ""),
                    "starter": bool(a.get("starter")),
                    "dnp": bool(a.get("didNotPlay")) or not a.get("stats"),
                    **line,
                })
    return {k: game[k] for k in ("event_id", "start", "season", "season_type", "home", "away",
                                  "home_score", "away_score")} | {"players": players}


def parse_stat_line(stats: dict) -> dict:
    def made_att(key):
        v = stats.get(key, "")
        if "-" in v:
            m, a = v.split("-", 1)
            return _int(m) or 0, _int(a) or 0
        return 0, 0

    fgm, fga = made_att("fieldGoalsMade-fieldGoalsAttempted")
    fg3m, fg3a = made_att("threePointFieldGoalsMade-threePointFieldGoalsAttempted")
    ftm, fta = made_att("freeThrowsMade-freeThrowsAttempted")
    g = lambda k: _int(stats.get(k)) or 0  # noqa: E731
    return {"min": g("minutes"), "pts": g("points"), "fgm": fgm, "fga": fga, "fg3m": fg3m, "fg3a": fg3a,
            "ftm": ftm, "fta": fta, "reb": g("rebounds"), "oreb": g("offensiveRebounds"),
            "dreb": g("defensiveRebounds"), "ast": g("assists"), "stl": g("steals"), "blk": g("blocks"),
            "tov": g("turnovers"), "pf": g("fouls"), "pm": g("plusMinus")}


def boxscore_path(season: int, event_id: str) -> Path:
    return RAW / "boxscores" / str(season) / f"{event_id}.json"


def fetch_boxscore(game: dict) -> dict:
    path = boxscore_path(game["season"], game["event_id"])
    if path.exists():
        return json.loads(path.read_text())
    r = http.get(f"{BASE}/summary", params={"event": game["event_id"]}, pause=PAUSE)
    r.raise_for_status()
    box = compact_boxscore(r.json(), game)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(box, separators=(",", ":")))
    return box


def backfill_season(season: int, *, max_new: int | None = None) -> dict:
    """Download every finished regular-season game of a season that we don't have yet."""
    yesterday = today_et() - timedelta(days=1)
    days = [d for d in season_days(season) if d <= yesterday]
    new = skipped = 0
    for day in days:
        try:
            day_games = fetch_scoreboard(day)
        except Exception as e:  # one bad day shouldn't stop the run
            print(f"  WARNING: scoreboard {day} failed: {e}")
            continue
        for g in day_games:
            if g["season"] != season or g["season_type"] != REGULAR_SEASON or g["status"] != "STATUS_FINAL":
                continue
            if boxscore_path(season, g["event_id"]).exists():
                continue
            if max_new is not None and new >= max_new:
                skipped += 1
                continue
            try:
                fetch_boxscore(g)
                new += 1
            except Exception as e:  # one bad game shouldn't stop the run
                print(f"  WARNING: box score {g['event_id']} ({g['away']}@{g['home']} {day}) failed: {e}")
    have = len(list((RAW / "boxscores" / str(season)).glob("*.json")))
    return {"season": season, "days": len(days), "new_games": new, "deferred": skipped, "games_cached": have}


# ---------- game logs ----------

GAMELOG_COLUMNS = ["season", "event_id", "date", "team", "opp", "home", "espn_id", "name", "pos",
                   "starter", "dnp", *STAT_FIELDS, "dk_pts", "team_score", "opp_score"]


def build_gamelogs(season: int) -> Path:
    """Flatten every cached box score of a season into data/gamelogs/gamelogs_<season>.csv."""
    rows = []
    for f in sorted((RAW / "boxscores" / str(season)).glob("*.json")):
        box = json.loads(f.read_text())
        day = datetime.fromisoformat(box["start"].replace("Z", "+00:00")).astimezone(ET).date().isoformat()
        for p in box["players"]:
            home = p["team"] == box["home"]
            rows.append({
                "season": season, "event_id": box["event_id"], "date": day, "team": p["team"],
                "opp": box["away"] if home else box["home"], "home": int(home),
                "espn_id": p["espn_id"], "name": p["name"], "pos": p["pos"],
                "starter": int(p["starter"]), "dnp": int(p["dnp"]),
                **{k: p[k] for k in STAT_FIELDS},
                "dk_pts": 0.0 if p["dnp"] else dk_points(p["pts"], p["fg3m"], p["reb"], p["ast"],
                                                         p["stl"], p["blk"], p["tov"]),
                "team_score": box["home_score"] if home else box["away_score"],
                "opp_score": box["away_score"] if home else box["home_score"],
            })
    rows.sort(key=lambda r: (r["date"], r["event_id"], r["team"], -r["min"]))
    GAMELOG_DIR.mkdir(parents=True, exist_ok=True)
    out = GAMELOG_DIR / f"gamelogs_{season}.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=GAMELOG_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return out


def _int(v) -> int | None:
    try:
        return int(str(v).replace("+", ""))
    except (TypeError, ValueError):
        return None


def _safe_canon(t: str) -> str | None:
    try:
        return canon(t)
    except KeyError:
        return None
