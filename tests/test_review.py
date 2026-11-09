"""Slate review: pre-lock snapshot, actual-points join, schema, real-slate run."""
import json
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from pipeline import review
from pipeline.config import REPO_ROOT, load_settings
from pipeline.run import PRELOCK_FILE, save_prelock

HAVE_NODE = (REPO_ROOT / "web" / "node_modules" / "highs").exists() and shutil.which("node")
needs_node = pytest.mark.skipif(not HAVE_NODE, reason="needs `npm ci` in web/")


def _proj(lock="2026-11-09T19:00:00-05:00"):
    return pd.DataFrame([{"dk_id": "1", "name": "A", "lock_time": lock, "proj": 30.0},
                         {"dk_id": "2", "name": "B", "lock_time": "2026-11-09T21:00:00-05:00", "proj": 20.0}])


# ---------- pre-lock snapshot ----------

def test_prelock_written_before_first_lock_with_timestamp(tmp_path):
    run = datetime(2026, 11, 9, 14, 15, tzinfo=timezone.utc)  # 9:15 AM ET, games at 7 PM ET
    assert save_prelock(_proj(), tmp_path, run)
    snap = pd.read_csv(tmp_path / PRELOCK_FILE)
    assert (snap["snapshot_at"] == "2026-11-09T14:15:00+00:00").all()


def test_last_prelock_run_wins_and_post_lock_never_overwrites(tmp_path):
    save_prelock(_proj(), tmp_path, datetime(2026, 11, 9, 14, 15, tzinfo=timezone.utc))
    later = _proj()
    later["proj"] = [31.0, 21.0]
    assert save_prelock(later, tmp_path, datetime(2026, 11, 9, 22, 0, tzinfo=timezone.utc))  # 5 PM ET: still before
    after_lock = _proj()
    after_lock["proj"] = [99.0, 99.0]
    # 00:00 UTC = 7 PM ET = the first lock: too late, even though game B hasn't locked yet
    assert not save_prelock(after_lock, tmp_path, datetime(2026, 11, 10, 0, 0, tzinfo=timezone.utc))
    snap = pd.read_csv(tmp_path / PRELOCK_FILE)
    assert snap["proj"].tolist() == [31.0, 21.0]
    assert snap["snapshot_at"].iloc[0] == "2026-11-09T22:00:00+00:00"


# ---------- actual points join ----------

def _players():
    base = {"team": "AAA", "opp": "BBB", "game": "BBB@AAA", "salary": 5000, "roster_positions": "PG/G/UTIL",
            "positions": "PG", "status": "", "ceiling": 40.0, "floor": 10.0}
    rows = [("1", "e1", 25.0, False),   # played
            ("2", "e2", 20.0, False),   # in box score with 0 minutes -> late scratch
            ("3", "e3", 15.0, False),   # not in box score at all -> late scratch
            ("4", "e4", 0.0, True),     # OUT, didn't play -> not a late scratch
            ("5", "", 10.0, False),     # unmatched: no result
            ("6", "e6", 0.0, True)]     # listed OUT but played anyway
    return pd.DataFrame([{**base, "dk_id": i, "name": f"P{i}", "espn_id": e, "proj": p, "out": o}
                         for i, e, p, o in rows])


def _box():
    return pd.DataFrame([
        {"espn_id": "e1", "name": "P1", "team": "AAA", "dnp": 0, "min": 30, "dk_pts": 33.5},
        {"espn_id": "e2", "name": "P2", "team": "AAA", "dnp": 1, "min": 0, "dk_pts": 0.0},
        {"espn_id": "e6", "name": "P6", "team": "AAA", "dnp": 0, "min": 12, "dk_pts": 14.0},
    ])


def test_join_actuals_dnp_late_scratch_and_unmatched():
    df = review.join_actuals(_players(), _box()).set_index("dk_id")
    assert df.loc["1", "actual"] == 33.5 and df.loc["1", "result"] == "played"
    assert df.loc["2", "actual"] == 0 and df.loc["2", "result"] == "dnp" and df.loc["2", "late_scratch"]
    assert df.loc["3", "actual"] == 0 and df.loc["3", "result"] == "not_in_box" and df.loc["3", "late_scratch"]
    assert df.loc["4", "actual"] == 0 and not df.loc["4", "late_scratch"]
    assert df.loc["5", "result"] == "unmatched" and df.loc["5", "actual"] == 0
    assert df.loc["6", "actual"] == 14.0 and not df.loc["6", "projected_to_play"]
    acc = review.accuracy(df.reset_index())
    # only player 1 counts: late scratches, OUT and unmatched players are left out
    assert acc["players"] == 1 and acc["mae"] == 8.5 and acc["bias"] == -8.5
    assert acc["lateScratches"] == 2 and acc["playedButProjectedOut"] == 1


def test_postponed_game_players_get_no_result():
    df = review.join_actuals(_players(), _box(), missing_games=["BBB@AAA"])
    assert (df["result"] == "postponed").all() and (df["actual"] == 0).all()


def test_unmatched_player_rematched_against_tonights_box():
    p = _players()
    p.loc[p["dk_id"] == "5", "name"] = "Rookie Guy"
    box = pd.concat([_box(), pd.DataFrame([{"espn_id": "e5", "name": "Rookie Guy", "team": "AAA", "dnp": 0,
                                            "min": 20, "dk_pts": 22.0}])])
    df = review.join_actuals(review.rematch_unmatched(p, box), box).set_index("dk_id")
    assert df.loc["5", "result"] == "played" and df.loc["5", "actual"] == 22.0


def test_slate_waits_for_box_scores_then_treats_missing_as_postponed():
    cfg = {"postponed_after_days": 2}
    assert review.slate_status("2026-11-07", ["A@B"], [], cfg, date(2026, 11, 8)) == "ready"
    assert review.slate_status("2026-11-07", ["A@B"], ["C@D"], cfg, date(2026, 11, 8)) == "waiting"
    assert review.slate_status("2026-11-07", ["A@B"], ["C@D"], cfg, date(2026, 11, 9)) == "ready"
    assert review.slate_status("2026-11-07", [], ["C@D"], cfg, date(2026, 11, 20)) == "waiting"


def test_miss_types():
    cfg = load_settings()["review"]
    p = {"ceiling": 40.0, "actual": 50.0, "valueRank": 3}
    assert review.classify_miss(p, True, cfg) == "in our lineup"
    assert review.classify_miss(p, False, cfg) == "projection miss"
    assert review.classify_miss({**p, "actual": 42.0, "valueRank": 60}, False, cfg) == "settings miss"
    assert review.classify_miss({**p, "actual": 42.0, "valueRank": 3}, False, cfg) == "close call"


def test_every_review_setting_has_a_comment():
    text = (REPO_ROOT / "config" / "settings.yaml").read_text()
    section = text.split("\nreview:")[1]
    for line in section.splitlines()[1:]:
        if line.startswith("  ") and ":" in line and not line.strip().startswith("#"):
            assert "#" in line, f"no plain-English comment: {line}"


# ---------- full review (uses Node + the app's optimizer) ----------

@pytest.fixture(scope="module")
def real_review():
    if not HAVE_NODE:
        pytest.skip("needs `npm ci` in web/")
    settings = load_settings()
    logs = review.load_logs([settings["data"]["current_season"], settings["data"]["prior_season"]])
    doc, players, msg = review.build_review(review.SLATES / "2026-11-07", settings, logs, today=date(2026, 11, 9))
    assert doc is not None, msg
    return doc, players


@needs_node
def test_real_nov7_review_schema_and_numbers(real_review, tmp_path):
    doc, players = real_review
    assert review.validate_review(doc) == []
    assert doc["gameDate"] == "2026-11-07"
    assert doc["projections"]["source"] == "rebuilt"  # no pre-lock snapshot for that slate
    s = doc["standing"]
    assert s["ourActual"] <= s["optimalActual"]
    assert s["ourProj"] >= s["optimalOurProj"] - 0.01  # our lineup is the best by our own numbers
    assert doc["topN"]["count"] == load_settings()["review"]["hindsight_top_n"]
    assert doc["topN"]["scores"] == sorted(doc["topN"]["scores"], reverse=True)
    c = doc["optimal"]["composition"]
    assert c["salary"] <= 50000 and c["games"] >= 2
    mult = load_settings()["review"]["smash_multiplier"]
    assert all(x["actual"] >= mult * x["salary"] / 1000 for x in doc["smash"])
    # files
    paths = review.write_review(doc, players, tmp_path / "review", tmp_path / "docs")
    names = {p.name for p in paths}
    assert {"2026-11-07.json", "review_2026-11-07.json", "2026-11-07_players.csv",
            "review_index.json", "review_latest.json"} <= names
    index = json.loads((tmp_path / "docs" / "review_index.json").read_text())
    assert index["dates"][0]["date"] == "2026-11-07"


def test_validate_review_catches_problems():
    assert "root.optimal missing" in review.validate_review({"schema": 1})
