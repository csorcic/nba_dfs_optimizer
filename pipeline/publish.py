"""Publish the slate for the phone app: docs/data/slate_latest.json (+ a dated copy).

The app reads only this file. It holds the games (lock times, Vegas lines), every
player with projections, and the optimizer defaults from config/settings.yaml.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from pipeline.config import REPO_ROOT

DOCS_DATA = REPO_ROOT / "docs" / "data"
SCHEMA_VERSION = 1


def _num(v, digits=2):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return round(float(v), digits)


def build_payload(proj: pd.DataFrame, games: list[dict], meta: dict, settings: dict) -> dict:
    players = []
    for _, r in proj.iterrows():
        status = r["status"] if isinstance(r["status"], str) else ""
        players.append({
            "id": str(r["dk_id"]),
            "name": r["name"],
            "team": r["team"],
            "opp": r["opp"],
            "game": r["game"],
            "lock": r["lock_time"],
            "pos": r["positions"],
            "slots": str(r["roster_positions"]).split("/"),
            "salary": int(r["salary"]),
            "status": status,
            "proj": _num(r["proj"]) or 0.0,
            "floor": _num(r["floor"]),
            "ceiling": _num(r["ceiling"]),
            "sd": _num(r["sd"]),
            "minutes": _num(r["minutes"], 1),
            "bump": _num(r["minutes_bump"], 1) or 0.0,
            "fppm": _num(r["fppm"], 3),
            "vegas": _num(r["vegas_factor"], 3),
            "source": r["proj_source"],
            "matched": bool(r["matched"]),
            "dkAvg": _num(r["avg_ppg"]),
            "games": int(r["games_current"]) if not pd.isna(r["games_current"]) else 0,
            "teamTotal": _num(r["team_implied"], 1),
            "own": _num(r.get("own"), 1) or 0.0,
        })
    locks = sorted(g["lock_time"] for g in games)
    return {
        "schema": SCHEMA_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "slateDate": locks[0][:10] if locks else meta["slate_date"],  # the day the games are played
        "fileDate": meta["slate_date"],
        "draftGroupId": meta["draft_group_id"],
        "salaryFile": meta["salary_file"],
        "games": [{
            "game": g["game"],
            "away": g["game"].split("@")[0],
            "home": g["game"].split("@")[1],
            "lock": g["lock_time"],
            "total": _num(g.get("total"), 1),
            "homeSpread": _num(g.get("home_spread"), 1),
            "homeTotal": _num(g.get("home_implied"), 1),
            "awayTotal": _num(g.get("away_implied"), 1),
            "oddsSource": g.get("source"),
        } for g in games],
        "players": players,
        "defaults": settings["optimizer"],
    }


def publish(payload: dict, out_dir: Path = DOCS_DATA) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, separators=(",", ":"))
    paths = [out_dir / "slate_latest.json", out_dir / f"slate_{payload['slateDate']}.json"]
    for p in paths:
        p.write_text(text, encoding="utf-8")
    return paths
