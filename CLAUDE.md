# NBA DFS Lineup Optimizer (DraftKings Classic)

Personal tool for Chris (csorcic). It builds DraftKings NBA **Classic** lineups for both **cash games and tournaments (GPPs)**, many lineups at a time, and exports DK's bulk-upload CSV. It runs as a **web app installed to the home screen of an Android phone (PWA)**. Everything must stay **free**: no paid APIs, no paid hosting.

## Working with Chris

- Chris is **not a coder**. Do all the coding, testing and git work yourself. Do not ask him to edit code or run terminal commands unless there is truly no other way. If you must, give one copy-paste step at a time.
- Every tunable value belongs in the app's Settings screen, or in `config/settings.yaml` with a plain-English comment on each line. Never bury magic numbers in code.
- Explain results in plain language: what changed, what he will see on his phone, and anything he needs to do.
- Work in small phases (see the Build plan below). Finish each one with tests passing and a short summary before starting the next.

## Repositories

- **`csorcic/dk_salary`** (private, already working; don't rewrite it). A GitHub Action runs daily at 13:47 UTC (about 7:47 AM CT) and commits the DK main-slate salary CSV to `salaries/DKSalaries_NBA_<YYYY-MM-DD>_<draftGroupId>.csv`. Columns:
  `Position, Name + ID, Name, ID, Roster Position, Salary, Game Info, TeamAbbrev, AvgPointsPerGame, Status, Starting`
  - `Roster Position` (e.g. `PG/G/UTIL`, `PF/C/F/UTIL`) is the source of truth for slot eligibility.
  - `Status` is `OUT`, `Q` or blank. `OUT` players are excluded by default.
  - `Game Info` looks like `WAS@OKC 11/07/2026 08:00PM ET` and gives the game and lock time.
  - The file starts with a UTF-8 BOM, so strip it when parsing.
- **This repo** (public, so GitHub Pages hosting is free). It holds the data pipeline, the projections, the optimizer and the PWA.
  - It reads `dk_salary` through a fine-grained GitHub token (read-only Contents on `dk_salary` only), stored as the Actions secret `DK_SALARY_TOKEN`.

## Architecture

```
GitHub Actions (this repo, scheduled, Python)
  1. fetch salaries   <- private dk_salary repo (latest CSV)
  2. fetch box scores <- ESPN public JSON (2026-27 season, plus 2025-26 for priors)
  3. fetch game lines <- The Odds API free tier (spreads + totals); ESPN scoreboard as fallback
  4. build projections (mean, std dev, ceiling, floor, estimated ownership)
  5. publish docs/data/slate_latest.json (+ dated copy)  -> GitHub Pages
PWA on the phone (static HTML/JS on GitHub Pages)
  - loads slate_latest.json, lets Chris edit, lock or exclude players
  - runs the optimizer in the browser (integer programming via HiGHS WebAssembly)
  - exports DK bulk-upload CSV (download or share sheet)
```

### Data source rules (verified Nov 2026)

- **Do not use `nba_api` / stats.nba.com from GitHub Actions.** It blocks cloud IPs and requests time out. Use ESPN's public site API (scoreboard and game summary/box score JSON) instead. Cache raw responses in `data/raw/` so each game is fetched only once.
- **Betting lines:** The Odds API free plan (500 requests/month, no card). Use the `basketball_nba` sport, markets `spreads,totals`, region `us`, and API key secret `ODDS_API_KEY`. Two pulls a day uses well under the quota. Log the remaining-requests header every run, and fall back to ESPN scoreboard odds if the key is missing or out of quota.
- **No player props.** They are paid-only. Don't add a props dependency.
- **No paid ownership data.** Ownership is estimated (see below).
- **Name matching:** DK names won't always match ESPN names (accents, Jr./III, nicknames). Normalize names, then match on team + name. Keep a hand-editable override file at `config/name_overrides.yaml`. Every run must print unmatched players, and unmatched players must still appear in the app with a flag and a fallback projection (DK `AvgPointsPerGame`).

### Schedule

- Pipeline at 14:15 UTC (after salaries land) and again at 22:00 UTC (about 4 PM CT, for line moves). Both runs are also manually triggerable.
- Optionally later: add a second afternoon run to `dk_salary` so `Status` picks up late injury news. Ask Chris first, since that changes his other repo.

## DraftKings NBA Classic rules (enforce in code and in tests)

- 8 roster slots: **PG, SG, SF, PF, C, G (PG or SG), F (SF or PF), UTIL (any)**. Use the CSV `Roster Position` field for eligibility.
- Salary cap **$50,000** (total must be at most the cap).
- Players from **at least 2 different games**.
- No player more than once in a lineup.
- Scoring: Point +1, 3PM +0.5, Rebound +1.25, Assist +1.5, Steal +2, Block +2, Turnover −0.5, Double-double +1.5, Triple-double +3 (on top of the double-double bonus, so a triple-double earns +4.5 total).
- Write a `validateLineup()` function used on every lineup the optimizer returns, and in tests. Any rule failure is a bug.
- Bulk upload CSV: header row `PG,SG,SF,PF,C,G,F,UTIL`, one lineup per row, cells are DK player **IDs**. Check the format against a DK-downloaded upload template before calling it done. Up to 150 lineups.

## Projections

Build in Python, with every weight in `config/settings.yaml`.

1. **Fantasy points per minute (FPPM)** for each player, from 2026-27 game logs, weighting recent games more (exponential decay).
   - Early in the season, blend with the 2025-26 rate: `weight_current = games / (games + K)`, with K configurable (default 10). Set `use_prior_season: false` to switch it off.
   - Rookies and players with no prior data fall back to DK `AvgPointsPerGame`.
2. **Minutes:** recent average minutes, then:
   - Redistribute minutes from teammates who are `OUT` (by position and depth), and show this as "minutes bump" in the app.
   - Trim starters' minutes when the spread is large (blowout risk).
   - Chris can override minutes in the app.
3. **Vegas adjustment:**
   - Implied team total = total / 2 − spread / 2, using the team's own spread (negative for the favorite).
   - Scale each team's projected output by implied total ÷ that team's season-average points, raised to a configurable exponent (start at 1.0).
4. **Projection** = minutes × FPPM × Vegas factor.
5. **Variance:** standard deviation from the player's game-log spread of DK points (shrink toward a positional prior for small samples). Ceiling = mean + 1.28·SD (about the 90th percentile). Floor = mean − 1.28·SD.
6. **Estimated ownership:** logistic model on value (points per $1K), salary, projection rank, minutes bump, and implied team total. Normalize so slate ownership sums to 800%. Keep it simple and documented.
7. **Backtest:** `scripts/backtest.py` replays past slates (dates where we have the salary CSV plus actual box scores). It reports MAE and bias of projections vs actual DK points, overall and by salary tier. Run it after any projection change and report the numbers to Chris.

## Optimizer

JavaScript, running in the browser. Use HiGHS compiled to WebAssembly (`highs` npm package), with `javascript-lp-solver` as a fallback if HiGHS gives trouble on mobile.

- Integer program over player × slot variables, enforcing all DK rules above.
- **Cash mode:** maximize projected points (optional small floor weight). Default 1 lineup, allow up to about 20 with a min-uniqueness of 1.
- **GPP mode:**
  - Generate N lineups (1–150). For each lineup, draw a randomized "simulated" projection per player from their distribution, then add a ceiling weight and an ownership penalty (all weights adjustable).
  - **Uniqueness:** each new lineup shares at most `8 − U` players with every earlier lineup (U default 3).
  - **Exposure caps:** global max % (default 50%) plus per-player min/max set in the app, enforced as lineups are generated.
  - **Optional game-stack rule:** at least X players from one high-total game, optionally with a "bring-back" from the opponent.
- Locks, excludes and per-player projection overrides always win.
- Target speed: 150 GPP lineups in under about 30 seconds on a mid-range Android phone. Run the solver in a Web Worker and show progress.
- Unit tests in Node: rules, uniqueness, exposure, locks/excludes, the 2-game rule, and CSV export format.

## PWA (phone app)

Mobile-first, works in Chrome on Android, installable (manifest + service worker), with the last-loaded slate cached for offline viewing.

Screens:
1. **Slate:** date, games, lock times, Vegas totals and spreads, data freshness ("projections updated 9:16 AM").
2. **Players:** searchable and sortable list with salary, positions, projection, ceiling, ownership estimate, value, status badges (OUT/Q), minutes bump and unmatched flag. Tap a player to lock, exclude, edit projection or edit minutes, or set min/max exposure.
3. **Build:** choose Cash or GPP, number of lineups, uniqueness, exposure, stacking and weights. Big "Build lineups" button.
4. **Results:** lineups with salary used and projection, a player exposure summary, export of DK upload CSV via download or the Android share sheet, and "copy IDs".
5. **Settings:** all tunables with plain-English help text, plus reset to defaults.

Chris's edits (locks, excludes, overrides, settings) are saved in browser storage on the phone and survive a refresh. They reset per slate date, except settings.

## Repo layout (target)

```
config/settings.yaml, config/name_overrides.yaml
pipeline/            # Python: fetch_salaries, fetch_espn, fetch_odds, project, publish
scripts/backtest.py
web/                 # PWA source (optimizer in web/src/optimizer/)
docs/                # GitHub Pages output (built app + docs/data/*.json)
.github/workflows/   # pipeline.yml (scheduled), deploy.yml (build web -> docs/)
tests/               # pytest (pipeline) + node tests (optimizer)
```

## Build plan (do in order; report after each)

1. **Setup:** repo skeleton, secrets checklist for Chris (`DK_SALARY_TOKEN`, `ODDS_API_KEY`), GitHub Pages on.
2. **Data pipeline:** salaries + ESPN box scores (2026-27 backfill and 2025-26 priors) + odds, name matching, raw caching. Output is a joined player table.
3. **Projections v1 + backtest.** Report MAE and bias.
4. **Optimizer core (cash) + DK rule validator + tests.**
5. **PWA v1:** Slate/Players/Build/Results with cash mode, CSV export, deployed to Pages. Chris installs it on his phone.
6. **GPP mode:** randomization, ceiling, ownership estimate, uniqueness, exposure, stacking.
7. **Polish:** offline cache, speed on phone, settings help text, error states (no slate today, missing odds, unmatched players).
8. **Later / optional:** late swap, re-running on injury news, more slates than the main slate.

## Definition of done for any change

Tests pass, the pipeline runs green in Actions, every generated lineup passes `validateLineup()`, and Chris gets a 2–4 sentence plain-English summary.
