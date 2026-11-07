"""Team names and abbreviations. DraftKings abbreviations are the canonical form."""
from __future__ import annotations

# DK abbreviation -> full name (as The Odds API spells it)
TEAMS = {
    "ATL": "Atlanta Hawks", "BKN": "Brooklyn Nets", "BOS": "Boston Celtics",
    "CHA": "Charlotte Hornets", "CHI": "Chicago Bulls", "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks", "DEN": "Denver Nuggets", "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors", "HOU": "Houston Rockets", "IND": "Indiana Pacers",
    "LAC": "Los Angeles Clippers", "LAL": "Los Angeles Lakers", "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat", "MIL": "Milwaukee Bucks", "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans", "NYK": "New York Knicks", "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers", "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers", "SAC": "Sacramento Kings", "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors", "UTA": "Utah Jazz", "WAS": "Washington Wizards",
}

# Other spellings seen from ESPN / DraftKings -> canonical
_ALIASES = {
    "WSH": "WAS", "GS": "GSW", "NY": "NYK", "SA": "SAS", "NO": "NOP", "UTAH": "UTA",
    "PHO": "PHX", "BRK": "BKN", "BK": "BKN", "CHO": "CHA", "LA": "LAC",
    "LOS ANGELES CLIPPERS": "LAC", "LA CLIPPERS": "LAC",
}
_BY_NAME = {name.upper(): abbr for abbr, name in TEAMS.items()}


def canon(team: str) -> str:
    """Return the canonical (DK) abbreviation for an abbreviation or full name."""
    t = (team or "").strip().upper()
    if t in TEAMS:
        return t
    if t in _ALIASES:
        return _ALIASES[t]
    if t in _BY_NAME:
        return _BY_NAME[t]
    raise KeyError(f"Unknown team: {team!r}")
