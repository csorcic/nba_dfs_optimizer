"""Match DraftKings players to ESPN players.

Order of attempts (first hit wins):
  1. override   - config/name_overrides.yaml maps the DK name to an ESPN name
  2. team+name  - same team, same normalized name
  3. name       - same normalized name, only one such ESPN player (traded players)
  4. team+last  - same team, same last name and first initial, only one candidate
Anything else is reported as unmatched.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict

SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def normalize(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("-", " ")
    s = re.sub(r"[^a-z ]", "", s)  # drop periods, apostrophes, etc.
    parts = [p for p in s.split() if p not in SUFFIXES]
    return " ".join(parts)


def _first_last(norm: str) -> tuple[str, str]:
    parts = norm.split()
    return (parts[0][:1] if parts else ""), (parts[-1] if parts else "")


class Matcher:
    def __init__(self, espn_players: list[dict], overrides: dict[str, str] | None = None):
        """espn_players: dicts with espn_id, name, team (latest team the player appeared for)."""
        self.by_team_name: dict[tuple, list] = defaultdict(list)
        self.by_name: dict[str, list] = defaultdict(list)
        self.by_team_last: dict[tuple, list] = defaultdict(list)
        for p in espn_players:
            n = normalize(p["name"])
            self.by_team_name[(p["team"], n)].append(p)
            self.by_name[n].append(p)
            init, last = _first_last(n)
            self.by_team_last[(p["team"], last, init)].append(p)
        self.overrides = {normalize(k): normalize(v) for k, v in (overrides or {}).items()}

    def match(self, dk_name: str, team: str) -> tuple[dict | None, str]:
        n = normalize(dk_name)
        if n in self.overrides:
            target = self.overrides[n]
            hit = self.by_team_name.get((team, target))
            if not hit and len(self.by_name.get(target, [])) == 1:
                hit = self.by_name[target]
            if hit:
                return hit[0], "override"
        hit = self.by_team_name.get((team, n))
        if hit:
            return hit[0], "team+name"
        hit = self.by_name.get(n)
        if hit and len(hit) == 1:
            return hit[0], "name"
        init, last = _first_last(n)
        hit = self.by_team_last.get((team, last, init))
        if hit and len(hit) == 1:
            return hit[0], "team+last"
        return None, "unmatched"
