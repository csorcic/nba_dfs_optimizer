import copy

import numpy as np
import pandas as pd
import pytest

from pipeline.config import load_settings
from pipeline.project import _blend, pos_groups, project

CUR, PRI = 2027, 2026


def make_logs(players, n_games=10, season=CUR, team="AAA", start_day=1):
    """players: {espn_id: (minutes, dk_pts, pos)} -> identical game every night."""
    rows = []
    for g in range(n_games):
        for pid, (mins, pts, pos) in players.items():
            rows.append({"season": season, "event_id": f"{season}-{team}-{g}",
                         "date": f"{season - 1}-11-{start_day + g:02d}", "team": team, "opp": "BBB",
                         "espn_id": pid, "name": pid, "pos": pos, "dnp": 0 if mins > 0 else 1,
                         "min": mins, "dk_pts": pts, "team_score": 115})
    return pd.DataFrame(rows)


def players_df(ids, team="AAA", out=(), pos=None):
    return pd.DataFrame([{"key": i, "espn_id": i, "team": team, "opp": "BBB",
                          "pos_group": (pos or {}).get(i, ROSTER[i][2] if i in ROSTER else "G"), "out": i in out, "fallback": np.nan}
                         for i in ids])


@pytest.fixture
def settings():
    s = copy.deepcopy(load_settings())
    s["projections"]["use_prior_season"] = True
    return s


ROSTER = {  # 5 x 48 = 240 team minutes
    "a": (36, 36, "G"), "b": (36, 36, "G"), "c": (36, 36, "F"), "d": (36, 36, "F"), "e": (36, 36, "C"),
    "f": (20, 20, "G"), "g": (20, 20, "F"), "h": (20, 20, "C"),
}


def test_pos_groups():
    assert pos_groups("PG/SG") == "G"
    assert pos_groups("PF/C/F/UTIL") == "C/F"
    assert pos_groups("G-F") == "F/G"


def test_blend_weights_current_season_by_games():
    out = _blend(pd.Series([2.0]), pd.Series([1.0]), pd.Series([10.0]), 10)
    assert out.iloc[0] == pytest.approx(1.5)
    # no prior -> current; no current -> prior
    assert _blend(pd.Series([2.0]), pd.Series([np.nan]), pd.Series([3.0]), 10).iloc[0] == 2.0
    assert _blend(pd.Series([np.nan]), pd.Series([1.0]), pd.Series([0.0]), 10).iloc[0] == 1.0


def test_projection_is_minutes_times_rate(settings):
    logs = make_logs(ROSTER)
    df = project(players_df(ROSTER), logs, {}, settings, CUR, PRI).set_index("key")
    assert df.loc["a", "fppm"] == pytest.approx(1.0)
    assert df.loc["a", "minutes"] == pytest.approx(36)
    assert df.loc["a", "proj"] == pytest.approx(36)
    assert df.loc["a", "vegas_factor"] == 1.0
    assert df.loc["a", "ceiling"] > df.loc["a", "proj"] > df.loc["a", "floor"] >= 0


def test_team_minutes_never_exceed_240(settings):
    logs = make_logs(ROSTER)
    df = project(players_df(ROSTER), logs, {}, settings, CUR, PRI)
    assert df["minutes"].sum() <= 240 + 1e-6


def test_out_player_minutes_go_to_teammates_and_bump_is_shown(settings):
    logs = make_logs(ROSTER)
    df = project(players_df(ROSTER, out={"a"}), logs, {}, settings, CUR, PRI).set_index("key")
    assert df.loc["a", "proj"] == 0 and df.loc["a", "minutes"] == 0
    assert (df.drop("a")["minutes_bump"] > 0).all()
    # team refills to ~240 (a little less only if someone hits the max-minutes cap)
    assert 240 - 6 <= df["minutes"].sum() <= 240 + 1e-6
    # same-position bench player (G) gets more than a different-position one (C) of equal minutes
    assert df.loc["f", "minutes_bump"] > df.loc["h", "minutes_bump"]


def test_long_term_out_player_creates_no_bump(settings):
    roster = dict(ROSTER)
    logs = make_logs({k: v for k, v in roster.items()})
    # 'z' played last season only, so his minutes are already absorbed this season
    logs = pd.concat([logs, make_logs({"z": (30, 30, "G")}, season=PRI)])
    df = project(players_df(list(roster) + ["z"], out={"z"}), logs, {}, settings, CUR, PRI).set_index("key")
    assert df["minutes_bump"].sum() == pytest.approx(0)


def test_vegas_factor_scales_projection(settings):
    logs = make_logs(ROSTER)
    lines = {"AAA": {"implied": 126.5, "spread": -3}}  # 10% above the team's 115 average
    df = project(players_df(ROSTER), logs, lines, settings, CUR, PRI).set_index("key")
    assert df.loc["a", "vegas_factor"] == pytest.approx(1.1)
    assert df.loc["a", "proj"] == pytest.approx(36 * 1.1, rel=1e-3)


def test_blowout_trims_starters_only(settings):
    logs = make_logs(ROSTER)
    cfg = settings["projections"]
    spread = cfg["blowout_spread_threshold"] + 5
    lines = {"AAA": {"implied": 115, "spread": -spread}}
    df = project(players_df(ROSTER), logs, lines, settings, CUR, PRI).set_index("key")
    expected_cut = min(5 * cfg["blowout_minutes_cut_per_point"], cfg["blowout_max_minutes_cut"])
    assert df.loc["a", "blowout_cut"] == pytest.approx(36 * expected_cut)
    assert df.loc["f", "blowout_cut"] == 0


def test_rookie_without_data_uses_dk_average(settings):
    logs = make_logs(ROSTER)
    p = players_df(["rookie"])
    p["espn_id"] = ""
    p["fallback"] = 17.5
    df = project(pd.concat([players_df(ROSTER), p]), logs, {}, settings, CUR, PRI).set_index("key")
    assert df.loc["rookie", "proj"] == 17.5 and df.loc["rookie", "proj_source"] == "dk_avg"


def test_prior_season_blend_early_in_season(settings):
    logs = pd.concat([make_logs({"a": (30, 60, "G")}, n_games=2),          # 2.0 per minute, 2 games
                      make_logs({"a": (30, 30, "G")}, n_games=40, season=PRI)])  # 1.0 per minute
    k = settings["projections"]["prior_season_k"]
    df = project(players_df(["a"]), logs, {}, settings, CUR, PRI).set_index("key")
    w = 2 / (2 + k)
    assert df.loc["a", "fppm"] == pytest.approx(w * 2.0 + (1 - w) * 1.0, abs=1e-3)
    settings["projections"]["use_prior_season"] = False
    df = project(players_df(["a"]), logs, {}, settings, CUR, PRI).set_index("key")
    assert df.loc["a", "fppm"] == pytest.approx(2.0)
