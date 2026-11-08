import json
from pathlib import Path

import pytest

from pipeline import fetch_espn, fetch_odds, fetch_salaries
from pipeline.names import Matcher, normalize
from pipeline.scoring import dk_points
from pipeline.teams import canon

FIX = Path(__file__).parent / "fixtures"

SALARY_CSV = (
    "﻿Position,Name + ID,Name,ID,Roster Position,Salary,Game Info,TeamAbbrev,AvgPointsPerGame,Status,Starting\n"
    "PG,Shai Gilgeous-Alexander (44828358),Shai Gilgeous-Alexander,44828358,PG/G/UTIL,10400,"
    "WAS@OKC 11/07/2026 08:00PM ET,OKC,46.4,,\n"
    "PF/C,Alperen Sengun (44828364),Alperen Sengun,44828364,PF/C/F/UTIL,8900,HOU@PHX 11/07/2026 09:00PM ET,HOU,51,,\n"
    "PF,Paolo Banchero (44828368),Paolo Banchero,44828368,PF/F/UTIL,8800,ORL@GSW 11/07/2026 08:30PM ET,ORL,45.4,OUT,\n"
)


# ---------- scoring ----------

def test_dk_points_basic():
    # 20 pts, 2 3PM, 5 reb, 4 ast, 1 stl, 0 blk, 3 tov
    assert dk_points(20, 2, 5, 4, 1, 0, 3) == 20 + 1 + 6.25 + 6 + 2 - 1.5


def test_double_double_bonus():
    assert dk_points(10, 0, 10, 0, 0, 0, 0) == 10 + 12.5 + 1.5


def test_triple_double_earns_4_5_total_bonus():
    assert dk_points(10, 0, 10, 10, 0, 0, 0) == 10 + 12.5 + 15 + 4.5


# ---------- teams ----------

@pytest.mark.parametrize("raw,want", [("WSH", "WAS"), ("GS", "GSW"), ("NY", "NYK"), ("UTAH", "UTA"),
                                      ("SA", "SAS"), ("NO", "NOP"), ("PHO", "PHX"),
                                      ("Los Angeles Clippers", "LAC"), ("Oklahoma City Thunder", "OKC")])
def test_team_aliases(raw, want):
    assert canon(raw) == want


# ---------- salaries ----------

def test_parse_salary_csv_strips_bom_and_reads_fields():
    players = fetch_salaries.parse_salary_csv(SALARY_CSV)
    assert len(players) == 3
    sga = players[0]
    assert sga["dk_id"] == "44828358" and sga["salary"] == 10400
    assert sga["team"] == "OKC" and sga["opp"] == "WAS" and sga["home"] is True
    assert sga["roster_positions"] == "PG/G/UTIL"
    assert sga["lock_time"] == "2026-11-07T20:00:00-05:00"
    assert players[1]["opp"] == "PHX" and players[1]["home"] is False
    assert players[2]["status"] == "OUT"


def test_slate_info_from_file_name():
    assert fetch_salaries.slate_info(Path("DKSalaries_NBA_2026-11-07_156199.csv")) == ("2026-11-07", "156199")


def test_parse_game_info_rejects_garbage():
    with pytest.raises(ValueError):
        fetch_salaries.parse_game_info("nonsense")


def test_sync_from_local_dir(tmp_path, monkeypatch):
    src = tmp_path / "src"
    src.mkdir()
    (src / "DKSalaries_NBA_2026-11-07_156199.csv").write_text(SALARY_CSV, encoding="utf-8")
    (src / "DKSalaries_NBA_2026-11-06_156100.csv").write_text(SALARY_CSV, encoding="utf-8")
    monkeypatch.setenv("DK_SALARY_DIR", str(src))
    files = fetch_salaries.sync_salary_files("x/y", "salaries", raw_dir=tmp_path / "raw")
    assert [f.name for f in files] == ["DKSalaries_NBA_2026-11-06_156100.csv",
                                       "DKSalaries_NBA_2026-11-07_156199.csv"]


# ---------- ESPN ----------

def test_compact_scoreboard_and_espn_odds():
    sb = json.loads((FIX / "espn_scoreboard.json").read_text())
    games = fetch_espn.compact_scoreboard(sb)
    g = games[0]
    assert (g["away"], g["home"]) == ("DEN", "IND")
    assert g["season"] == 2027 and g["season_type"] == 2
    # DEN (away) is a 7.5-point favorite, so the home spread is +7.5
    assert g["odds"]["home_spread"] == 7.5 and g["odds"]["total"] == 229.5


def test_compact_scoreboard_skips_non_nba_opponents():
    sb = json.loads((FIX / "espn_scoreboard.json").read_text())
    sb["events"][0]["competitions"][0]["competitors"][0]["team"]["abbreviation"] = "LON"
    assert len(fetch_espn.compact_scoreboard(sb)) == len(sb["events"]) - 1
    del sb["events"][1]["competitions"][0]["competitors"][1]["team"]["abbreviation"]
    assert len(fetch_espn.compact_scoreboard(sb)) == 0


def test_compact_boxscore_parses_stat_lines():
    summary = json.loads((FIX / "espn_summary.json").read_text())
    game = {"event_id": "401909287", "start": "2026-11-07T00:00Z", "season": 2027, "season_type": 2,
            "home": "ATL", "away": "WAS", "home_score": 139, "away_score": 132}
    box = fetch_espn.compact_boxscore(summary, game)
    george = next(p for p in box["players"] if p["name"] == "Kyshawn George")
    assert george["team"] == "WAS" and george["starter"] and not george["dnp"]
    assert (george["min"], george["pts"], george["fgm"], george["fga"]) == (39, 33, 10, 19)
    assert (george["fg3m"], george["reb"], george["ast"], george["tov"]) == (5, 4, 8, 2)
    assert george["pm"] == -3
    dnps = [p for p in box["players"] if p["dnp"]]
    assert dnps and all(p["min"] == 0 for p in dnps)


# ---------- odds ----------

def test_odds_api_consensus_uses_median_and_home_spread():
    events = [{
        "home_team": "Oklahoma City Thunder", "away_team": "Washington Wizards", "commence_time": "x",
        "bookmakers": [
            {"markets": [{"key": "spreads", "outcomes": [{"name": "Oklahoma City Thunder", "point": -14.5},
                                                         {"name": "Washington Wizards", "point": 14.5}]},
                         {"key": "totals", "outcomes": [{"name": "Over", "point": 226.5},
                                                        {"name": "Under", "point": 226.5}]}]},
            {"markets": [{"key": "spreads", "outcomes": [{"name": "Oklahoma City Thunder", "point": -13.5}]},
                         {"key": "totals", "outcomes": [{"name": "Over", "point": 227.5}]}]},
            {"markets": [{"key": "spreads", "outcomes": [{"name": "Oklahoma City Thunder", "point": -14.5}]},
                         {"key": "totals", "outcomes": [{"name": "Over", "point": 227.5}]}]},
        ]}]
    lines = fetch_odds.consensus_from_odds_api(events)
    assert lines["WAS@OKC"]["home_spread"] == -14.5
    assert lines["WAS@OKC"]["total"] == 227.5


def test_implied_totals():
    # total 230, home favored by 10 -> home 120, away 110
    assert fetch_odds.implied_totals({"total": 230, "home_spread": -10}) == (120, 110)


# ---------- names ----------

def test_normalize_handles_accents_suffixes_punctuation():
    assert normalize("Nikola Jokić") == "nikola jokic"
    assert normalize("Jaren Jackson Jr.") == "jaren jackson"
    assert normalize("Kelly Oubre Jr") == "kelly oubre"
    assert normalize("De'Aaron Fox") == "deaaron fox"
    assert normalize("Shai Gilgeous-Alexander") == "shai gilgeous alexander"
    assert normalize("Robert Williams III") == "robert williams"


ESPN = [
    {"espn_id": "1", "name": "Nikola Jokić", "team": "DEN"},
    {"espn_id": "2", "name": "Jaren Jackson Jr.", "team": "MEM"},
    {"espn_id": "3", "name": "Nicolas Claxton", "team": "BKN"},
    {"espn_id": "4", "name": "Jalen Williams", "team": "OKC"},
    {"espn_id": "5", "name": "Jalen Williams", "team": "PHX"},  # different player, same name
    {"espn_id": "6", "name": "Traded Guy", "team": "LAL"},
    {"espn_id": "7", "name": "Cameron Thomas", "team": "BKN"},
]


@pytest.mark.parametrize("dk_name,team,want_id,method", [
    ("Nikola Jokic", "DEN", "1", "team+name"),
    ("Jaren Jackson", "MEM", "2", "team+name"),
    ("Nic Claxton", "BKN", "3", "override"),
    ("Jalen Williams", "OKC", "4", "team+name"),
    ("Jalen Williams", "PHX", "5", "team+name"),
    ("Traded Guy", "DAL", "6", "name"),
    ("Cam Thomas", "BKN", "7", "team+last"),
    ("Jalen Williams", "BOS", None, "unmatched"),  # ambiguous name, wrong team: don't guess
    ("Nobody Here", "BOS", None, "unmatched"),
])
def test_matcher(dk_name, team, want_id, method):
    m = Matcher(ESPN, {"Nic Claxton": "Nicolas Claxton"})
    hit, how = m.match(dk_name, team)
    assert how == method
    assert (hit["espn_id"] if hit else None) == want_id


def test_compact_boxscore_skips_player_without_id():
    summary = json.loads((FIX / "espn_summary.json").read_text())
    athletes = summary["boxscore"]["players"][0]["statistics"][0]["athletes"]
    athletes.append({"athlete": {"shortName": "Olbrich"}, "starter": False, "didNotPlay": False,
                     "stats": ["--", "0", "0-0", "0-0", "0-0", "0", "0", "0", "0", "0", "0", "0", "0", "0"]})
    game = {"event_id": "1", "start": "2026-11-07T00:00Z", "season": 2027, "season_type": 2,
            "home": "ATL", "away": "WAS", "home_score": 1, "away_score": 0}
    box = fetch_espn.compact_boxscore(summary, game)
    assert all(p["espn_id"] for p in box["players"])


def test_build_projections_without_any_betting_lines():
    from pipeline.config import load_settings
    from pipeline.run import PLAYER_COLUMNS, build_projections
    table = [dict(p, home=int(p["home"]), espn_id="", espn_name="", match_method="unmatched", matched=0,
                  games_current=0, games_prior=0, last_game="")
             for p in fetch_salaries.parse_salary_csv(SALARY_CSV)]
    s = load_settings()
    df = build_projections(table, {}, s, s["data"]["current_season"], s["data"]["prior_season"])
    assert set(PLAYER_COLUMNS) <= set(df.columns)
    assert df["team_implied"].isna().all()
    assert (df[~df["out"]]["proj_source"] == "dk_avg").all()
