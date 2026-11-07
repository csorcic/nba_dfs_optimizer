# nba_dfs_optimizer

DraftKings NBA Classic lineup builder (cash and tournaments) that runs as a phone app.
See `CLAUDE.md` for the full design and build plan.

- **First-time setup:** [docs/SETUP.md](docs/SETUP.md)
- **Settings:** [config/settings.yaml](config/settings.yaml) (every line explained)
- **Name fixes:** [config/name_overrides.yaml](config/name_overrides.yaml)
- **App:** <https://csorcic.github.io/nba_dfs_optimizer/>

## Layout

```
config/            settings and name overrides
pipeline/          Python data pipeline (runs in GitHub Actions)
scripts/           backtest and helper scripts
web/               phone app source (optimizer in web/src/optimizer/)
docs/              GitHub Pages output (built app + docs/data/*.json)
.github/workflows/ tests, setup check, and (later) the scheduled pipeline
tests/             automated tests
```

## Data the pipeline keeps (in `data/`)

```
raw/salaries/                 copy of every DK salary CSV (for backtests)
raw/espn/boxscores/<season>/  one small file per finished game (downloaded once)
raw/espn/scoreboard/          one file per finished day
raw/odds/                     betting-line snapshot from each run
gamelogs/gamelogs_<season>.csv  every player's stat line + DK points, per game
slates/<date>/players.csv     joined player table for that day's slate
slates/<date>/games.json      games, lock times, totals, spreads, implied team totals
slates/<date>/unmatched.txt   DK players not found on ESPN (fix in config/name_overrides.yaml)
```

ESPN seasons are labeled by the year they end: 2027 = 2026-27, 2026 = 2025-26.

Run the pipeline locally: `python -m pipeline.run` (needs `DK_SALARY_TOKEN`, or `DK_SALARY_DIR`
pointing at a folder of salary CSVs).

Run tests locally: `pip install -r requirements.txt && python -m pytest`
