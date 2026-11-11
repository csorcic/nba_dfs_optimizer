"""Estimated ownership (we have no real ownership data, so this is a simple guess).

For each active player we build a score from things that tend to make a player
popular on DraftKings, all measured relative to the rest of the slate:

  score = intercept
        + value_weight      * value z-score         (points per $1K: the biggest driver)
        + projection_weight * projection z-score    (big projections draw attention)
        + rank_weight       * log(projection rank)  (top few names get extra attention)
        + bump_weight       * minutes bump          (injury news makes chalk)
        + team_total_weight * team total z-score    (players in high-scoring games)
        + salary_weight     * salary z-score

Then ownership = logistic(score), scaled so the whole slate adds up to 800%
(8 roster spots x 100%), with no player above `max_pct`. OUT players get 0.
All weights are in config/settings.yaml under `ownership`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _z(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    sd = s.std(ddof=0)
    return (s - s.mean()) / sd if sd and not np.isnan(sd) else s * 0


WEIGHTS = ["intercept", "value_weight", "projection_weight", "rank_weight", "bump_weight",
           "team_total_weight", "salary_weight"]


def ownership_features(df: pd.DataFrame) -> tuple[pd.Index, np.ndarray]:
    """(index of active players, feature matrix with one column per weight in WEIGHTS).

    Features depend only on the slate, not on the weights, so a refit can build them once.
    """
    active = df[~df["out"].astype(bool) & (df["proj"] > 0)]
    if active.empty:
        return active.index, np.zeros((0, len(WEIGHTS)))
    value = active["proj"] / (active["salary"] / 1000)
    rank = active["proj"].rank(ascending=False, method="min")
    team_total = (active["team_implied"] if "team_implied" in active else pd.Series(np.nan, index=active.index)).astype(float)
    team_total = team_total.fillna(team_total.mean() if team_total.notna().any() else 0)
    X = np.column_stack([
        np.ones(len(active)), _z(value), _z(active["proj"]), np.log(rank),
        active["minutes_bump"].fillna(0).astype(float), _z(team_total), _z(active["salary"]),
    ])
    return active.index, X


def ownership_from_features(X: np.ndarray, cfg: dict, total_pct: float) -> np.ndarray:
    score = X @ np.array([cfg[k] for k in WEIGHTS], dtype=float)
    raw = 1 / (1 + np.exp(-score))
    return _scale_with_cap(pd.Series(raw), total_pct, cfg["max_pct"]).to_numpy()


def estimate_ownership(df: pd.DataFrame, cfg: dict, total_pct: float = 800.0) -> pd.Series:
    """df columns: proj, salary, minutes_bump, team_implied, out. Returns % owned (0-100)."""
    own = pd.Series(0.0, index=df.index)
    idx, X = ownership_features(df)
    if len(idx):
        own.loc[idx] = ownership_from_features(X, cfg, total_pct)
    return own.round(1)


def _scale_with_cap(raw: pd.Series, total: float, cap: float) -> pd.Series:
    """Scale to `total`, then repeatedly cap at `cap` and share the excess among the rest."""
    out = raw * total / raw.sum()
    for _ in range(50):
        over = out > cap
        if not over.any():
            break
        excess = (out[over] - cap).sum()
        out[over] = cap
        free = ~over & (out < cap)
        if not free.any():
            break
        out[free] += excess * out[free] / out[free].sum()
    return out
