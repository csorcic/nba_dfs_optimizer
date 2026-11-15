"""Lessons report: calibration, smash predictors, ownership refit, no leakage."""
import copy
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pipeline.config import REPO_ROOT, load_settings
from pipeline.ownership import estimate_ownership

spec = importlib.util.spec_from_file_location("lessons", REPO_ROOT / "scripts" / "lessons.py")
lessons = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lessons)

SD_TRUE_RATIO = 1.5  # actual results swing 1.5x wider than our range says


def make_slate(i: int, rng, settings, own_truth: dict | None = None, source="prelock", n=160):
    date = f"2026-12-{i + 1:02d}"
    sal = rng.integers(30, 120, n) * 100
    proj = sal / 1000 * rng.normal(5, 0.8, n)
    sd = 0.3 * proj
    z = settings["projections"]["ceiling_z"]
    bump = np.where(rng.random(n) < 0.15, rng.uniform(4, 10, n), 0.0)
    actual = np.clip(proj + bump * 1.0 + SD_TRUE_RATIO * sd * rng.normal(0, 1, n), 0, None)
    games = [f"A{g}@H{g}" for g in range(5)]
    game = [games[k % 5] for k in range(n)]
    p = pd.DataFrame({
        "dk_id": [str(10000 * (i + 1) + k) for k in range(n)], "name": [f"P{k}" for k in range(n)],
        "team": [g.split("@")[k % 2] for k, g in enumerate(game)], "game": game,
        "positions": [["PG", "SG", "SF", "PF", "C"][k % 5] for k in range(n)], "salary": sal,
        "proj": proj, "sd": sd, "ceiling": proj + z * sd, "floor": np.clip(proj - z * sd, 0, None),
        "minutes_bump": bump, "team_implied": rng.uniform(105, 125, n), "team_spread": 0.0, "game_total": 225.0,
        "projected_to_play": True, "out": False, "result": "played", "actual": actual, "late_scratch": False,
        "in_optimal": False, "in_top_n": 0, "in_our_lineup": False,
    })
    p["smash"] = p["actual"] >= 6 * p["salary"] / 1000
    p["own"] = estimate_ownership(p, settings["ownership"], 800)
    comp = {"salary": 49800, "stars": 1, "values": 2, "maxFromOneGame": 3, "maxGame": games[0],
            "maxGameIsHighestTotal": True, "teams": ["A0", "H0"], "teamCount": 5, "games": 3, "ownSum": 100.0}
    doc = {"gameDate": date, "projections": {"source": source}, "games": [{"game": g, "total": 225.0} for g in games],
           "optimal": {"composition": comp}}
    contest = None
    if own_truth is not None:
        real = estimate_ownership(p, {**settings["ownership"], **own_truth}, 800)
        real = (real + rng.normal(0, 0.5, n)).clip(lower=0)
        contest = {"contestId": str(i), "fieldSize": 5000,
                   "ownership": [{"id": pid, "drafted": float(r)} for pid, r in zip(p["dk_id"], real)],
                   "winningLineups": []}
    return date, doc, p, contest


def write_slates(tmp: Path, slates):
    rev, con = tmp / "review", tmp / "contests"
    rev.mkdir(exist_ok=True)
    for date, doc, p, contest in slates:
        (rev / f"{date}.json").write_text(json.dumps(doc))
        p.to_csv(rev / f"{date}_players.csv", index=False)
        if contest:
            (con / date).mkdir(parents=True, exist_ok=True)
            (con / date / f"{contest['contestId']}.json").write_text(json.dumps(contest))
    return rev, con


@pytest.fixture
def settings():
    s = load_settings()
    s["review"]["lessons_refit_iterations"] = 150  # keep the test quick
    return s


@pytest.fixture
def world(tmp_path, settings, monkeypatch):
    rng = np.random.default_rng(3)
    truth = {"value_weight": 2.0, "bump_weight": 0.25}
    slates = [make_slate(i, rng, settings, truth) for i in range(6)]
    rev, con = write_slates(tmp_path, slates)
    monkeypatch.setattr(lessons, "CONTESTS", con)
    return rev


def test_calibration_spots_a_range_that_is_too_narrow(world, settings):
    L = lessons.build(settings, review_dir=world)
    cal = L["calibration"]
    assert cal["overCeilingPct"] > 15  # results swing wider than our ceilings allow
    assert cal["sdScaleSuggested"] > settings["projections"]["sd_scale"] * 1.2
    h = cal["heldOut"]
    assert abs(h["overCeilingPctSuggested"] - 10) < abs(h["overCeilingPctNow"] - 10)  # fixed on held-out slates
    assert any(r["setting"] == "projections.sd_scale" for r in L["recommendations"])


def test_smash_predictors_find_minutes_bump(world, settings):
    L = lessons.build(settings, review_dir=world)
    bump = next(g for g in L["smash"]["groups"] if g["feature"] == "Minutes bump")
    rows = {r["bucket"]: r for r in bump["rows"]}
    assert rows["4 min+"]["lift"] > 1.3 > rows["under 1 min"]["lift"]
    assert all("players" in r and "smallSample" in r for r in bump["rows"])


def test_ownership_refit_beats_current_weights_on_held_out_slates(world, settings):
    L = lessons.build(settings, review_dir=world)
    r = L["ownership"]["refit"]
    assert r["heldOutMaeRefit"] < r["heldOutMaeNow"]
    assert r["weightsRefit"]["value_weight"] > settings["ownership"]["value_weight"]  # moves toward the truth (2.0)
    rec = next(x for x in L["recommendations"] if x["setting"] == "ownership.*")
    assert "before" in rec and "after" in rec


def test_too_early_label_and_report(world, settings):
    L = lessons.build(settings, review_dir=world)
    assert L["slates"] == 6 and L["tooEarly"]
    md = lessons.to_markdown(L)
    assert "Too early to act on" in md and "Recommendations only" in md
    settings["review"]["min_slates_for_lessons"] = 5
    assert not lessons.build(settings, review_dir=world)["tooEarly"]


def test_no_leakage_outcome_flags_do_not_change_lessons(world, settings, tmp_path):
    """Scrambling 'was in the optimal lineup' and friends must not change anything."""
    before = lessons.build(settings, review_dir=world)
    for f in world.glob("*_players.csv"):
        p = pd.read_csv(f)
        p["in_optimal"] = True
        p["in_top_n"] = 50
        p["in_our_lineup"] = True
        p.to_csv(f, index=False)
    after = lessons.build(settings, review_dir=world)
    for key in ("calibration", "smash", "ownership", "recommendations"):
        assert before[key] == after[key], key


def test_rebuilt_slates_are_skipped_by_default(tmp_path, settings, monkeypatch):
    rng = np.random.default_rng(1)
    rev, con = write_slates(tmp_path, [make_slate(0, rng, settings, source="rebuilt"),
                                       make_slate(1, rng, settings, source="prelock")])
    monkeypatch.setattr(lessons, "CONTESTS", con)
    L = lessons.build(settings, review_dir=rev)
    assert L["slates"] == 1 and L["skippedRebuilt"] == ["2026-12-01"]
    assert lessons.build(settings, use_rebuilt=True, review_dir=rev)["slates"] == 2


def test_never_edits_settings(world, settings):
    path = REPO_ROOT / "config" / "settings.yaml"
    before = path.read_bytes()
    lessons.build(copy.deepcopy(settings), review_dir=world)
    assert path.read_bytes() == before


def test_feature_and_outcome_lists_do_not_overlap():
    assert not set(lessons.PRELOCK_FEATURES) & set(lessons.OUTCOMES)
