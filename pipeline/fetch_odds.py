"""Game lines (spread + total) for the slate.

Primary: The Odds API free tier (one request per run). Fallback: the odds ESPN
shows on its scoreboard. Each run saves a small snapshot in data/raw/odds/.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from statistics import median

from pipeline import http
from pipeline.config import REPO_ROOT
from pipeline.fetch_espn import fetch_scoreboard
from pipeline.teams import canon

RAW = REPO_ROOT / "data" / "raw" / "odds"
ODDS_URL = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds"


def consensus_from_odds_api(events: list[dict]) -> dict[str, dict]:
    """Odds API events -> {'AWAY@HOME': {'total', 'home_spread', ...}} using the median across books."""
    lines = {}
    for ev in events:
        try:
            home, away = canon(ev["home_team"]), canon(ev["away_team"])
        except KeyError:
            continue
        spreads, totals = [], []
        for book in ev.get("bookmakers", []):
            for m in book.get("markets", []):
                if m["key"] == "spreads":
                    for o in m["outcomes"]:
                        if _safe_canon(o["name"]) == home and o.get("point") is not None:
                            spreads.append(float(o["point"]))
                elif m["key"] == "totals":
                    for o in m["outcomes"]:
                        if o["name"] == "Over" and o.get("point") is not None:
                            totals.append(float(o["point"]))
        if spreads and totals:
            lines[f"{away}@{home}"] = {"total": median(totals), "home_spread": median(spreads),
                                       "source": "odds_api", "books": len(ev.get("bookmakers", [])),
                                       "commence_time": ev.get("commence_time")}
    return lines


def fetch_odds_api(regions: str, markets: str) -> tuple[dict[str, dict] | None, str]:
    key = os.environ.get("ODDS_API_KEY")
    if not key:
        return None, "ODDS_API_KEY not set"
    try:
        r = http.get(ODDS_URL, params={"apiKey": key, "regions": regions, "markets": markets,
                                       "oddsFormat": "american"})
    except Exception as e:
        return None, f"request failed: {e}"
    remaining = r.headers.get("x-requests-remaining", "?")
    used = r.headers.get("x-requests-used", "?")
    print(f"  The Odds API: HTTP {r.status_code}, requests used {used}, remaining {remaining}")
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    events = r.json()
    print(f"  The Odds API listed {len(events)} games: " + ", ".join(
        f"{e.get('away_team')} @ {e.get('home_team')} ({e.get('commence_time', '')[:16]}, "
        f"{len(e.get('bookmakers', []))} books)" for e in events))
    return consensus_from_odds_api(events), f"ok ({remaining} requests left)"


def implied_totals(line: dict) -> tuple[float, float]:
    """(home implied, away implied): total/2 - own spread/2."""
    t, hs = line["total"], line["home_spread"]
    return round(t / 2 - hs / 2, 2), round(t / 2 + hs / 2, 2)


def get_slate_lines(slate_games: list[str], game_dates, settings: dict) -> dict[str, dict]:
    """Lines for every 'AWAY@HOME' game on the slate. Missing games are simply absent.

    game_dates: the calendar days (Eastern) the games are played on, for the ESPN fallback.
    """
    data = settings["data"]
    lines, note = fetch_odds_api(data["odds_regions"], data["odds_markets"])
    lines = lines or {}
    missing = [g for g in slate_games if g not in lines]
    if missing:
        why = note if not lines else f"{len(missing)} games not on The Odds API"
        print(f"  Using ESPN odds for {len(missing)} game(s) ({why})")
        for day in sorted(set(game_dates)):
            try:
                for g in fetch_scoreboard(day, use_cache=False):
                    key = f"{g['away']}@{g['home']}"
                    if key in missing and g.get("odds"):
                        lines[key] = g["odds"]
            except Exception as e:
                print(f"  WARNING: ESPN odds fallback for {day} failed: {e}")
    out = {}
    for g in slate_games:
        if g in lines:
            line = dict(lines[g])
            line["home_implied"], line["away_implied"] = implied_totals(line)
            out[g] = line
        else:
            print(f"  WARNING: no betting line for {g}")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%MZ")
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / f"{stamp}.json").write_text(json.dumps(out, indent=1))
    return out


def _safe_canon(t: str) -> str | None:
    try:
        return canon(t)
    except KeyError:
        return None
