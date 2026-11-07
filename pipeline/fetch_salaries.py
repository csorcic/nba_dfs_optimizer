"""Fetch DK salary CSVs from the private dk_salary repo and parse them.

Every CSV is copied once into data/raw/salaries/ (later phases' backtest needs
past slates). For local testing, set DK_SALARY_DIR to a folder of CSVs instead
of using the GitHub token.
"""
from __future__ import annotations

import csv
import io
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pipeline import http
from pipeline.config import REPO_ROOT
from pipeline.teams import canon

RAW_DIR = REPO_ROOT / "data" / "raw" / "salaries"
FILE_RE = re.compile(r"DKSalaries_NBA_(\d{4}-\d{2}-\d{2})_(\d+)\.csv$")
GAME_INFO_RE = re.compile(r"^(\w+)@(\w+)\s+(\d{2}/\d{2}/\d{4})\s+(\d{1,2}:\d{2}[AP]M)\s+ET")
ET = ZoneInfo("America/New_York")


def _gh_headers(token: str, raw: bool = False) -> dict:
    return {"Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.raw" if raw else "application/vnd.github+json"}


def sync_salary_files(repo: str, folder: str, raw_dir: Path = RAW_DIR) -> list[Path]:
    """Copy any salary CSVs we don't have yet into raw_dir. Returns all local files, oldest first."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    local_src = os.environ.get("DK_SALARY_DIR")
    if local_src:
        for src in Path(local_src).glob("DKSalaries_NBA_*.csv"):
            dest = raw_dir / src.name
            if not dest.exists():
                dest.write_bytes(src.read_bytes())
    else:
        token = os.environ.get("DK_SALARY_TOKEN")
        if not token:
            raise RuntimeError("DK_SALARY_TOKEN is not set (or set DK_SALARY_DIR for local testing).")
        r = http.get(f"https://api.github.com/repos/{repo}/contents/{folder}", headers=_gh_headers(token))
        r.raise_for_status()
        for item in r.json():
            name = item.get("name", "")
            if FILE_RE.search(name) and not (raw_dir / name).exists():
                f = http.get(item["url"], headers=_gh_headers(token, raw=True))
                f.raise_for_status()
                (raw_dir / name).write_bytes(f.content)
                print(f"  downloaded {name}")
    return sorted(raw_dir.glob("DKSalaries_NBA_*.csv"), key=lambda p: FILE_RE.search(p.name).group(1))


def slate_info(path: Path) -> tuple[str, str]:
    """(slate date 'YYYY-MM-DD', draft group id) from the file name."""
    m = FILE_RE.search(path.name)
    if not m:
        raise ValueError(f"Not a DK salary file name: {path.name}")
    return m.group(1), m.group(2)


def parse_game_info(info: str) -> dict:
    """'WAS@OKC 11/07/2026 08:00PM ET' -> away, home, lock time (ISO, Eastern)."""
    m = GAME_INFO_RE.match(info.strip())
    if not m:
        raise ValueError(f"Unrecognized Game Info: {info!r}")
    away, home, day, clock = m.groups()
    lock = datetime.strptime(f"{day} {clock}", "%m/%d/%Y %I:%M%p").replace(tzinfo=ET)
    away, home = canon(away), canon(home)
    return {"game": f"{away}@{home}", "away": away, "home": home, "lock_time": lock.isoformat()}


def _num(s: str) -> float | None:
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def parse_salary_csv(text: str) -> list[dict]:
    """Parse DK salary CSV text (BOM tolerated) into player dicts."""
    text = text.lstrip("﻿")
    players = []
    for row in csv.DictReader(io.StringIO(text)):
        if not row.get("ID"):
            continue
        g = parse_game_info(row["Game Info"])
        team = canon(row["TeamAbbrev"])
        if team not in (g["away"], g["home"]):
            raise ValueError(f"{row['Name']}: team {team} not in game {g['game']}")
        slots = [s for s in row["Roster Position"].split("/") if s]
        players.append({
            "dk_id": row["ID"].strip(),
            "name": row["Name"].strip(),
            "team": team,
            "opp": g["home"] if team == g["away"] else g["away"],
            "home": team == g["home"],
            "game": g["game"],
            "lock_time": g["lock_time"],
            "positions": row["Position"].strip(),
            "roster_positions": "/".join(slots),
            "salary": int(row["Salary"]),
            "avg_ppg": _num(row.get("AvgPointsPerGame")),
            "status": (row.get("Status") or "").strip().upper(),
            "starting": (row.get("Starting") or "").strip(),
        })
    return players


def load_salary_file(path: Path) -> list[dict]:
    return parse_salary_csv(path.read_text(encoding="utf-8-sig"))
