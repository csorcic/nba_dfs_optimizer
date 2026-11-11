"""DK contest standings import (fixture: a real DK standings zip for the Nov 9 slate)."""
import json
import shutil
import zipfile
from pathlib import Path

import pytest

from pipeline import contests, review
from pipeline.config import load_settings

FIXTURE = Path(__file__).parent / "fixtures" / "contest-standings-197619862.zip"


@pytest.fixture(scope="module")
def parsed():
    (name, text), = contests.read_files(FIXTURE)
    assert name == "contest-standings-197619862.csv"
    return contests.parse_standings(text)


@pytest.fixture(scope="module")
def settings():
    return load_settings()


@pytest.fixture(scope="module")
def logs(settings):
    return review.load_logs([settings["data"]["current_season"], settings["data"]["prior_season"]])


def test_parse_real_file(parsed):
    e = parsed["entries"]
    assert len(e) == 118
    assert e[0]["rank"] == 1 and e[0]["points"] == 371.75
    assert e[0]["entryName"] == "nickfromcwe (1/3)" and e[0]["user"] == "nickfromcwe"
    assert dict(e[0]["lineup"]) == {
        "C": "Jakob Poeltl", "F": "PJ Washington", "G": "Luka Doncic", "PF": "John Collins",
        "PG": "Jamal Shead", "SF": "Kevin Durant", "SG": "Collin Sexton", "UTIL": "Daniss Jenkins"}
    assert all(x["lineup"] for x in e)
    me = [x for x in e if x["user"] == "csorcic"]
    assert len(me) == 1 and me[0]["rank"] == 80 and me[0]["points"] == 264.25


def test_player_block_rows_are_summed_per_player(parsed):
    poeltl = next(p for p in parsed["players"] if p["name"] == "Jakob Poeltl")
    assert sorted(poeltl["slots"]) == ["C", "UTIL"] and poeltl["listedPct"] == 48.31
    own, source = contests.real_ownership(parsed, 95)
    assert source == "lineups"
    assert own["Jakob Poeltl"] == 48.31 and own["Luka Doncic"] == 43.22
    assert abs(sum(own.values()) - 800) < 0.5  # 8 players per lineup


def test_lineup_parsing_edge_cases():
    lu = contests.parse_lineup("C A G F B C Jr. G C.J. Guy PF D F PG E SF F G SG G H UTIL U I")
    assert dict(lu) == {"C": "A G", "F": "B C Jr.", "G": "C.J. Guy", "PF": "D F", "PG": "E",
                        "SF": "F G", "SG": "G H", "UTIL": "U I"}
    assert contests.parse_lineup("") is None
    assert contests.parse_lineup("C A F B G C") is None  # incomplete lineup


def test_score_lines_and_percentile():
    pts = [100.0 - i for i in range(200)]
    assert contests.score_at_pct(pts, 1) == 99.0     # 2nd of 200
    assert contests.score_at_pct(pts, 10) == 81.0    # 20th of 200
    assert contests.score_at_pct(pts, 50) == 1.0     # 100th of 200
    assert contests.finish_percentile(1, 118) == 100.0
    assert contests.finish_percentile(118, 118) == 0.0
    assert contests.finish_percentile(80, 118) == 32.5


def test_detects_the_nov9_slate(parsed, settings, logs):
    slates = review.slates_by_game_date()
    gdate, why = contests.detect_slate(parsed, slates, logs, settings["review"])
    assert gdate == "2026-11-09", why


def test_not_a_slate_is_unmatched(parsed, settings, logs):
    only_nov7 = {"2026-11-07": review.SLATES / "2026-11-07"}
    gdate, why = contests.detect_slate(parsed, only_nov7, logs, settings["review"])
    assert gdate is None and "need" in why


def test_process_new_imports_and_moves(tmp_path, settings, logs):
    shutil.copy(FIXTURE, tmp_path)
    (tmp_path / "junk.csv").write_text("hello,world\n1,2\n")
    with zipfile.ZipFile(tmp_path / "empty.zip", "w") as z:
        z.writestr("readme.txt", "nothing")
    rep = contests.process_new(settings, tmp_path, logs=logs)
    assert [r["file"] for r in rep["imported"]] == ["contest-standings-197619862.zip"]
    assert sorted(r["file"] for r in rep["unmatched"]) == ["empty.zip", "junk.csv"]
    assert (tmp_path / "unmatched" / "junk.csv").exists()
    assert "not a DK standings file" in (tmp_path / "unmatched" / "junk.csv.txt").read_text()
    assert (tmp_path / "processed" / "2026-11-09" / "contest-standings-197619862.zip").exists()
    assert not list(tmp_path.glob("*.csv")) and not list(tmp_path.glob("*.zip"))
    c = json.loads((tmp_path / "processed" / "2026-11-09" / "197619862.json").read_text())
    assert c["fieldSize"] == 118 and c["winningScore"] == 371.75
    assert c["top1Score"] == 367.5 and c["top10Score"] == 339.75 and c["cashLine"] == 285.5
    assert c["mine"]["best"]["rank"] == 80 and c["mine"]["best"]["percentile"] == 32.5
    assert all(p["id"] for p in c["mine"]["best"]["players"])  # every name found on the salary file
    assert c["unmatchedNames"] == []
    assert [p["slot"] for p in c["winningLineups"][0]["players"]] == review.SLOTS


def test_contest_problem_never_fails(tmp_path, settings, monkeypatch):
    monkeypatch.setattr(contests, "process_new", lambda s: (_ for _ in ()).throw(RuntimeError("boom")))
    assert contests.main() == 0


def test_attach_to_review(tmp_path, settings, logs):
    shutil.copy(FIXTURE, tmp_path)
    contests.process_new(settings, tmp_path, logs=logs)
    doc = json.loads((review.REVIEW_DIR / "2026-11-09.json").read_text())
    players = review.read_csv(review.REVIEW_DIR / "2026-11-09_players.csv")
    contests.attach_contests(doc, players, settings, tmp_path)
    assert review.validate_review(doc) == []
    c = doc["contests"][0]
    assert c["optimalBeatsWinnerBy"] == round(doc["optimal"]["actual"] - 371.75, 2)
    assert 0 <= c["winningLineups"][0]["sharedWithOptimal"] <= 8
    oc = doc["ownershipCheck"]
    assert oc["mae"] > 0 and oc["list"][0]["real"] >= oc["list"][-1]["real"]
    assert {t["tier"] for t in oc["byTier"]} >= {"under $4K", "$8K+"}
    # no standings for that date -> no contest sections
    empty = contests.attach_contests(dict(doc), players, settings, tmp_path / "nothing")
    assert "contests" not in empty and "ownershipCheck" not in empty


def test_one_slate_folder_per_game_date(tmp_path):
    for d, lock in [("2026-11-08", "2026-11-09"), ("2026-11-09", "2026-11-09"), ("2026-11-10", "2026-11-10")]:
        (tmp_path / d).mkdir()
        (tmp_path / d / "players.csv").write_text("dk_id\n")
        (tmp_path / d / "games.json").write_text(json.dumps(
            {"slate_date": d, "games": [{"game": "A@B", "lock_time": f"{lock}T19:00:00-05:00"}]}))
    picked = review.slates_by_game_date(tmp_path)
    assert picked["2026-11-09"].name == "2026-11-09"  # newest file wins
    (tmp_path / "2026-11-08" / review.PRELOCK_FILE).write_text("x")
    assert review.slates_by_game_date(tmp_path)["2026-11-09"].name == "2026-11-08"  # snapshot wins
