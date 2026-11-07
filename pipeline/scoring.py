"""DraftKings NBA Classic scoring."""
from __future__ import annotations

# Fixed by DraftKings rules (not tunable).
PTS, FG3M, REB, AST, STL, BLK, TOV = 1.0, 0.5, 1.25, 1.5, 2.0, 2.0, -0.5
DOUBLE_DOUBLE, TRIPLE_DOUBLE = 1.5, 3.0  # triple-double bonus is on top of the double-double bonus


def dk_points(pts: float, fg3m: float, reb: float, ast: float, stl: float, blk: float, tov: float) -> float:
    score = PTS * pts + FG3M * fg3m + REB * reb + AST * ast + STL * stl + BLK * blk + TOV * tov
    doubles = sum(1 for v in (pts, reb, ast, stl, blk) if v >= 10)
    if doubles >= 2:
        score += DOUBLE_DOUBLE
    if doubles >= 3:
        score += TRIPLE_DOUBLE
    return round(score, 2)
