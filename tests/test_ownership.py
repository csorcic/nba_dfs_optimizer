import numpy as np
import pandas as pd

from pipeline.config import load_settings
from pipeline.ownership import estimate_ownership


def _slate(n=60, seed=1):
    rng = np.random.default_rng(seed)
    salary = rng.integers(30, 120, n) * 100
    proj = salary / 1000 * rng.uniform(3.0, 5.5, n)
    return pd.DataFrame({"proj": proj, "salary": salary, "minutes_bump": 0.0,
                         "team_implied": rng.uniform(105, 122, n), "out": False})


def test_sums_to_800_and_respects_cap():
    cfg = load_settings()["ownership"]
    own = estimate_ownership(_slate(), cfg)
    assert abs(own.sum() - 800) < 1
    assert own.max() <= cfg["max_pct"] + 1e-6
    assert (own >= 0).all()


def test_out_and_zero_projection_players_get_zero():
    df = _slate()
    df.loc[0, "out"] = True
    df.loc[1, "proj"] = 0
    own = estimate_ownership(df, load_settings()["ownership"])
    assert own[0] == 0 and own[1] == 0
    assert abs(own.sum() - 800) < 1


def test_better_value_and_minutes_bump_raise_ownership():
    cfg = load_settings()["ownership"]
    df = _slate()
    base = estimate_ownership(df, cfg)
    df2 = df.copy()
    df2.loc[5, "proj"] *= 1.3  # same salary, better value
    df2.loc[6, "minutes_bump"] = 8
    own = estimate_ownership(df2, cfg)
    assert own[5] > base[5]
    assert own[6] > base[6]


def test_missing_team_totals_still_work():
    df = _slate()
    df["team_implied"] = np.nan
    assert abs(estimate_ownership(df, load_settings()["ownership"]).sum() - 800) < 1
