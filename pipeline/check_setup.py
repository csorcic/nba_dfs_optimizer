"""Setup check: confirms the secrets and free data sources all work.

Run by the "Setup check" GitHub Action. Prints a plain-English report and
exits non-zero if anything required is broken.

Checks:
  1. DK_SALARY_TOKEN can read the private salary repo and find CSV files.
  2. ODDS_API_KEY works (uses the free /sports endpoint, which costs no quota).
  3. ESPN's public scoreboard answers.
"""
from __future__ import annotations

import os
import sys

import requests

from pipeline.config import load_settings

TIMEOUT = 20
OK, WARN, FAIL = "OK  ", "WARN", "FAIL"


def check_salary_repo(token: str | None, repo: str, folder: str) -> tuple[str, str]:
    if not token:
        return FAIL, "DK_SALARY_TOKEN secret is missing. See docs/SETUP.md step 1."
    url = f"https://api.github.com/repos/{repo}/contents/{folder}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    try:
        r = requests.get(url, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        return FAIL, f"Could not reach GitHub: {e}"
    if r.status_code in (401, 403):
        return FAIL, "DK_SALARY_TOKEN was rejected. It may be expired or lack 'Contents: read' on dk_salary."
    if r.status_code == 404:
        return FAIL, f"Could not see {repo}/{folder}. Check the token has access to the dk_salary repo."
    if r.status_code != 200:
        return FAIL, f"GitHub returned HTTP {r.status_code}."
    csvs = sorted(i["name"] for i in r.json() if i.get("name", "").endswith(".csv"))
    if not csvs:
        return WARN, f"Token works, but no CSV files found in {repo}/{folder} yet."
    return OK, f"Token works. {len(csvs)} salary files; latest is {csvs[-1]}."


def check_odds_api(key: str | None) -> tuple[str, str]:
    if not key:
        return WARN, "ODDS_API_KEY secret is missing. Lines will fall back to ESPN. See docs/SETUP.md step 2."
    try:
        r = requests.get("https://api.the-odds-api.com/v4/sports",
                         params={"apiKey": key}, timeout=TIMEOUT)
    except requests.RequestException as e:
        return WARN, f"Could not reach The Odds API: {e}"
    if r.status_code == 401:
        return FAIL, "ODDS_API_KEY was rejected. Double-check you pasted the whole key."
    if r.status_code != 200:
        return WARN, f"The Odds API returned HTTP {r.status_code}."
    remaining = r.headers.get("x-requests-remaining", "?")
    nba = any(s.get("key") == "basketball_nba" for s in r.json())
    note = "" if nba else " (NBA not listed as in-season right now)"
    return OK, f"Key works. {remaining} requests left this month{note}."


def check_espn() -> tuple[str, str]:
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
    try:
        r = requests.get(url, timeout=TIMEOUT)
    except requests.RequestException as e:
        return FAIL, f"Could not reach ESPN: {e}"
    if r.status_code != 200:
        return FAIL, f"ESPN returned HTTP {r.status_code}."
    games = len(r.json().get("events", []))
    return OK, f"ESPN scoreboard answers ({games} games listed today)."


def main() -> int:
    settings = load_settings()
    data = settings["data"]
    results = [
        ("Salary repo (DK_SALARY_TOKEN)",
         check_salary_repo(os.environ.get("DK_SALARY_TOKEN"), data["salary_repo"], data["salary_folder"])),
        ("Betting lines (ODDS_API_KEY)", check_odds_api(os.environ.get("ODDS_API_KEY"))),
        ("ESPN box scores", check_espn()),
    ]
    print("Setup check\n")
    for name, (status, msg) in results:
        print(f"[{status}] {name}: {msg}")
    failed = any(status == FAIL for _, (status, _) in results)
    print("\nAll required pieces work." if not failed else "\nSomething needs fixing (see FAIL lines above).")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("## Setup check\n\n| Status | Check | Detail |\n|---|---|---|\n")
            for name, (status, msg) in results:
                f.write(f"| {status.strip()} | {name} | {msg} |\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
