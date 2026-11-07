"""Projections v1: minutes x fantasy points per minute x Vegas factor, plus spread.

All weights come from config/settings.yaml (section `projections`).

Inputs are plain pandas tables so the same code serves today's slate and the
backtest (which replays past days using only data from before each day).

  logs     game logs (data/gamelogs/*.csv), ONLY games before the slate date
  players  one row per player to project, columns:
             key, espn_id (may be ''), team, opp, pos_group (G/F/C, '/'-joined),
             out (bool), fallback (DK AvgPointsPerGame or NaN)
  lines    {team: {"implied": float, "spread": float}}  (team's own spread)
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

TEAM_MINUTES = 240


def pos_groups(positions: str) -> str:
    """'PG/SG' -> 'G', 'SF/PF' -> 'F', 'PF/C' -> 'F/C', ESPN 'G-F' -> 'G/F'."""
    groups = set()
    for p in str(positions or "").replace("-", "/").upper().split("/"):
        p = p.strip()
        if p in ("PG", "SG", "G"):
            groups.add("G")
        elif p in ("SF", "PF", "F"):
            groups.add("F")
        elif p == "C":
            groups.add("C")
    return "/".join(sorted(groups))


def _share_group(a: str, b: str) -> bool:
    return bool(set(a.split("/")) & set(b.split("/")) - {""})


def played_only(logs: pd.DataFrame) -> pd.DataFrame:
    return logs[(logs["dnp"] == 0) & (logs["min"] > 0)]


# ---------------------------------------------------------------- per-player rates

def player_rates(logs: pd.DataFrame, current: int, prior: int, cfg: dict) -> pd.DataFrame:
    """FPPM, minutes and DK-point spread for every ESPN player in the logs."""
    lg = played_only(logs).sort_values("date", ascending=False)
    cur = lg[lg["season"] == current].copy()
    pri = lg[lg["season"] == prior] if cfg["use_prior_season"] else lg.iloc[0:0]

    # Current season, recent games weighted more (exponential decay by games ago).
    cur["ago"] = cur.groupby("espn_id").cumcount()
    cur["w"] = 0.5 ** (cur["ago"] / cfg["recency_half_life_games"])
    cur["wpts"] = cur["w"] * cur["dk_pts"]
    cur["wmin"] = cur["w"] * cur["min"]
    recent = cur[cur["ago"] < cfg["minutes_lookback_games"]]
    c = cur.groupby("espn_id").agg(n_cur=("min", "size"), wpts=("wpts", "sum"), wmin=("wmin", "sum"))
    c["fppm_cur"] = c["wpts"] / c["wmin"].where(c["wmin"] > 0)
    c["min_cur"] = recent.groupby("espn_id")["min"].mean()

    p = pri.groupby("espn_id").agg(n_pri=("min", "size"), pts_pri=("dk_pts", "sum"),
                                   min_sum_pri=("min", "sum"), min_pri=("min", "mean"))
    p["fppm_pri"] = p["pts_pri"] / p["min_sum_pri"].where(p["min_sum_pri"] > 0)

    r = c[["n_cur", "fppm_cur", "min_cur"]].join(p[["n_pri", "fppm_pri", "min_pri"]], how="outer")
    r["n_cur"] = r["n_cur"].fillna(0)
    r["n_pri"] = r["n_pri"].fillna(0)
    r["fppm"] = _blend(r["fppm_cur"], r["fppm_pri"], r["n_cur"], cfg["prior_season_k"])
    r["minutes_base"] = _blend(r["min_cur"], r["min_pri"], r["n_cur"], cfg["prior_season_minutes_k"])

    # Boom/bust spread from the most recent games across both seasons.
    sd_src = lg[lg["season"].isin([current, prior] if cfg["use_prior_season"] else [current])]
    sd_src = sd_src[sd_src.groupby("espn_id").cumcount() < cfg["sd_lookback_games"]]
    s = sd_src.groupby("espn_id")["dk_pts"].agg(sd_n="size", sd_raw="std")
    return r.join(s, how="left")


def _blend(cur: pd.Series, pri: pd.Series, n: pd.Series, k: float) -> pd.Series:
    """Current-season value weighted games/(games + k) against last season's value."""
    w = n / (n + k) if k > 0 else (n > 0).astype(float)
    out = w * cur + (1 - w) * pri
    out = out.where(cur.notna() & pri.notna(), cur.fillna(pri))
    return out


def group_cv(logs: pd.DataFrame, min_games: int = 15) -> dict[str, float]:
    """Typical SD / mean of DK points by position group (the prior for small samples)."""
    lg = played_only(logs)
    g = lg.groupby("espn_id").agg(n=("dk_pts", "size"), m=("dk_pts", "mean"), s=("dk_pts", "std"),
                                  pos=("pos", "last"))
    g = g[(g["n"] >= min_games) & (g["m"] >= 10)]
    g["grp"] = g["pos"].map(lambda p: pos_groups(p).split("/")[0] if pos_groups(p) else "")
    g["cv"] = g["s"] / g["m"]
    cv = g.groupby("grp")["cv"].median().to_dict()
    overall = float(g["cv"].median()) if len(g) else 0.45
    out = {k: float(v) for k, v in cv.items() if k}
    out["_all"] = overall if not math.isnan(overall) else 0.45
    return out


def team_avg_points(logs: pd.DataFrame, current: int, prior: int, cfg: dict) -> tuple[dict, float]:
    """Each team's average points per game (current season, blended with last season early)."""
    games = logs.drop_duplicates(["event_id", "team"])[["season", "team", "team_score"]]
    cur = games[games["season"] == current].groupby("team")["team_score"].agg(["mean", "size"])
    pri = games[games["season"] == prior].groupby("team")["team_score"].mean() \
        if cfg["use_prior_season"] else pd.Series(dtype=float)
    league = float(games[games["season"] == current]["team_score"].mean()) if len(cur) else \
        float(games["team_score"].mean()) if len(games) else 115.0
    out = {}
    for team in set(cur.index) | set(pri.index):
        n = float(cur.loc[team, "size"]) if team in cur.index else 0.0
        c = float(cur.loc[team, "mean"]) if team in cur.index else np.nan
        p = float(pri.get(team, np.nan))
        k = cfg["team_points_prior_k"]
        if not np.isnan(c) and not np.isnan(p):
            w = n / (n + k)
            out[team] = w * c + (1 - w) * p
        else:
            out[team] = c if not np.isnan(c) else p
    return out, league


# ---------------------------------------------------------------- main entry point

def project(players: pd.DataFrame, logs: pd.DataFrame, lines: dict, settings: dict,
            current: int, prior: int) -> pd.DataFrame:
    cfg = settings["projections"]
    rates = player_rates(logs, current, prior, cfg)
    cv = group_cv(logs)
    team_pts, league_pts = team_avg_points(logs, current, prior, cfg)

    df = players.copy().reset_index(drop=True)
    df["espn_id"] = df["espn_id"].fillna("").astype(str)
    df = df.join(rates, on="espn_id")
    df["out"] = df["out"].astype(bool)

    # --- minutes
    # minutes_base = average minutes when he plays. Fringe players (under
    # `rotation_minutes`) also get DNPs, so their expected minutes are scaled by how
    # often they got in over the team's recent games. Regulars are assumed to play
    # unless marked OUT (their missed games are usually injuries).
    played = played_only(logs)
    df["play_rate"] = 1.0
    df["minutes_bump"] = 0.0
    for team, tdf in df.groupby("team"):
        team_games = (played[(played["team"] == team) & (played["season"] == current)]
                      .drop_duplicates("event_id").sort_values("date", ascending=False)
                      ["event_id"].head(cfg["minutes_lookback_games"]))
        if team_games.empty:
            continue
        recent_team = played[played["event_id"].isin(team_games) & (played["team"] == team)]
        apps = recent_team.groupby("espn_id")["event_id"].nunique() / len(team_games)
        share = tdf["espn_id"].map(apps).fillna(0.0)
        fringe = tdf["minutes_base"] < cfg["rotation_minutes"]
        df.loc[tdf.index, "play_rate"] = np.where(fringe, share, 1.0)
    df["minutes_exp"] = df["minutes_base"] * df["play_rate"]

    # Minutes bump: players who are OUT but were playing recently leave a hole.
    # Only the share of recent games they played is "new" (if he has been out for
    # weeks, teammates' recent minutes already include it). The hole is filled by
    # active teammates in proportion to their minutes, extra for the same position.
    for team, tdf in df.groupby("team"):
        team_games = (played[(played["team"] == team) & (played["season"] == current)]
                      .drop_duplicates("event_id").sort_values("date", ascending=False)
                      ["event_id"].head(cfg["minutes_lookback_games"]))
        active = tdf[~tdf["out"] & tdf["minutes_exp"].notna()]
        if active.empty or team_games.empty:
            continue
        recent_team = played[played["event_id"].isin(team_games) & (played["team"] == team)]
        apps = recent_team.groupby("espn_id")["event_id"].nunique() / len(team_games)
        bump = pd.Series(0.0, index=active.index)
        for _, o in tdf[tdf["out"] & tdf["minutes_base"].notna()].iterrows():
            pool = o["minutes_base"] * apps.get(o["espn_id"], 0.0)
            if pool <= 0:
                continue
            w = active["minutes_exp"] ** cfg["bump_minutes_power"] * active["pos_group"].map(
                lambda g: 1 + cfg["bump_same_position_weight"] * _share_group(g, o["pos_group"]))
            if w.sum() > 0:
                bump += pool * w / w.sum()
        # Never hand out more than the team has: total minutes stay at or under 240.
        room = max(TEAM_MINUTES - active["minutes_exp"].sum(), 0.0)
        if bump.sum() > room:
            bump *= room / bump.sum()
        df.loc[active.index, "minutes_bump"] = bump
        total = (active["minutes_exp"] + bump).sum()
        if total > TEAM_MINUTES:  # more listed minutes than a game has: shrink everyone evenly
            df.loc[active.index, "minutes_exp"] *= TEAM_MINUTES / total
            df.loc[active.index, "minutes_bump"] *= TEAM_MINUTES / total
    df["minutes"] = np.minimum(df["minutes_exp"] + df["minutes_bump"], cfg["max_minutes"])
    df["minutes_bump"] = (df["minutes"] - df["minutes_exp"]).clip(lower=0)

    # --- blowout risk: trim starters' minutes when the spread is big
    spread = df["team"].map(lambda t: abs((lines.get(t) or {}).get("spread", 0.0)))
    cut = ((spread - cfg["blowout_spread_threshold"]).clip(lower=0)
           * cfg["blowout_minutes_cut_per_point"]).clip(upper=cfg["blowout_max_minutes_cut"])
    starter = df["minutes"] >= cfg["starter_minutes_threshold"]
    df["blowout_cut"] = np.where(starter, df["minutes"] * cut, 0.0)
    df["minutes"] = df["minutes"] - df["blowout_cut"]

    # --- Vegas: implied team total vs the team's normal scoring
    def vegas(team):
        line = lines.get(team)
        base = team_pts.get(team, league_pts)
        if not line or not base:
            return 1.0
        return (line["implied"] / base) ** cfg["vegas_exponent"]
    df["vegas_factor"] = df["team"].map(vegas)

    # --- projection
    model = df["minutes"] * df["fppm"] * df["vegas_factor"]
    has_model = model.notna() & df["fppm"].notna()
    df["proj"] = np.where(has_model, model, df.get("fallback", np.nan))
    df["proj_source"] = np.where(has_model, "model", np.where(df["proj"].notna(), "dk_avg", "none"))
    df.loc[df["out"], ["proj", "minutes", "minutes_bump"]] = 0.0

    # --- spread: player's own SD shrunk toward the position-group prior
    grp = df["pos_group"].map(lambda g: g.split("/")[0] if g else "")
    prior_sd = grp.map(lambda g: cv.get(g, cv["_all"])) * df["proj"]
    n = df["sd_n"].fillna(0)
    n0 = cfg["sd_prior_games"]
    own = df["sd_raw"].fillna(prior_sd)
    # sd_scale widens the range to cover our own projection error, not just game-to-game swings.
    df["sd"] = cfg["sd_scale"] * (n * own + n0 * prior_sd) / (n + n0)
    df["ceiling"] = df["proj"] + cfg["ceiling_z"] * df["sd"]
    df["floor"] = (df["proj"] - cfg["floor_z"] * df["sd"]).clip(lower=0)
    for col in ("fppm", "minutes_base", "minutes_bump", "blowout_cut", "minutes", "vegas_factor",
                "proj", "sd", "ceiling", "floor"):
        df[col] = df[col].astype(float).round(3 if col in ("fppm", "vegas_factor") else 2)
    return df
