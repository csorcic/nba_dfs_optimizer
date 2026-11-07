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

Run tests locally: `pip install -r requirements.txt && python -m pytest`
