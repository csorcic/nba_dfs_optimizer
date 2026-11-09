import json

import pandas as pd

from pipeline import publish
from pipeline.config import load_settings


def _proj():
    return pd.DataFrame([{
        "dk_id": "44847053", "name": "Victor Wembanyama", "team": "SAS", "opp": "PHX", "game": "SAS@PHX",
        "lock_time": "2026-11-09T21:00:00-05:00", "positions": "C", "roster_positions": "C/UTIL",
        "salary": 11300, "status": float("nan"), "proj": 50.03, "floor": 25.86, "ceiling": 74.21, "sd": 18.9,
        "minutes": 26.4, "minutes_bump": 0.0, "fppm": 1.92, "vegas_factor": float("nan"), "proj_source": "model",
        "matched": 1, "avg_ppg": 59.7, "games_current": 10, "team_implied": float("nan"),
    }])


def test_payload_shape_and_slate_date_from_games(tmp_path):
    games = [{"game": "SAS@PHX", "lock_time": "2026-11-09T21:00:00-05:00", "total": 226.5,
              "home_spread": 8.5, "home_implied": 109.0, "away_implied": 117.5, "source": "espn"},
             {"game": "LAL@ATL", "lock_time": "2026-11-09T19:00:00-05:00"}]
    meta = {"slate_date": "2026-11-08", "draft_group_id": "156358", "salary_file": "x.csv"}
    payload = publish.build_payload(_proj(), games, meta, load_settings())
    # the file was saved on the 8th but the games are on the 9th: the app shows the 9th
    assert payload["slateDate"] == "2026-11-09" and payload["fileDate"] == "2026-11-08"
    p = payload["players"][0]
    assert p["id"] == "44847053" and p["slots"] == ["C", "UTIL"] and p["status"] == ""
    assert p["vegas"] is None and p["teamTotal"] is None  # NaN becomes null, not invalid JSON
    assert payload["games"][1]["total"] is None
    assert payload["defaults"]["salary_cap"] == 50000
    paths = publish.publish(payload, tmp_path)
    assert {x.name for x in paths} == {"slate_latest.json", "slate_2026-11-09.json"}
    assert json.loads(paths[0].read_text())["players"][0]["name"] == "Victor Wembanyama"
