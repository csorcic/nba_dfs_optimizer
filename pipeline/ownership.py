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


def estimate_ownership(df: pd.DataFrame, cfg: dict, total_pct: float = 800.0) -> pd.Series:
    """df columns: proj, salary, minutes_bump, team_implied, out. Returns % owned (0-100)."""
    own = pd.Series(0.0, index=df.index)
    active = df[~df["out"].astype(bool) & (df["proj"] > 0)]
    if active.empty:
        return own
    value = active["proj"] / (active["salary"] / 1000)
    rank = active["proj"].rank(ascending=False, method="min")
    team_total = (active["team_implied"] if "team_implied" in active else pd.Series(np.nan, index=active.index)).astype(float)
    team_total = team_total.fillna(team_total.mean() if team_total.notna().any() else 0)
    score = (cfg["intercept"]
             + cfg["value_weight"] * _z(value)
             + cfg["projection_weight"] * _z(active["proj"])
             + cfg["rank_weight"] * np.log(rank)
             + cfg["bump_weight"] * active["minutes_bump"].fillna(0)
             + cfg["team_total_weight"] * _z(team_total)
             + cfg["salary_weight"] * _z(active["salary"]))
    raw = 1 / (1 + np.exp(-score))
    own.loc[active.index] = _scale_with_cap(raw, total_pct, cfg["max_pct"])
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
