# Setup checklist (one-time, about 10 minutes)

All of this is clicking around on github.com and one free sign-up. No code.
Do these after the Phase 1 changes are merged into `main`.

## 1. DK_SALARY_TOKEN: lets this repo read your salary files

Makes a key that can **only read** `dk_salary` and nothing else.

1. Open <https://github.com/settings/personal-access-tokens/new>.
2. **Token name:** `nba_dfs_optimizer reads dk_salary`.
3. **Expiration:** pick the longest option offered (set a reminder to renew it).
4. **Resource owner:** `csorcic`.
5. **Repository access:** *Only select repositories* → pick `dk_salary`.
6. **Permissions → Repository permissions → Contents:** *Read-only*. Leave everything else alone.
7. Click **Generate token** and copy it (it starts with `github_pat_`). You only see it once.
8. Open <https://github.com/csorcic/nba_dfs_optimizer/settings/secrets/actions/new>.
9. **Name:** `DK_SALARY_TOKEN`. **Secret:** paste the token. Click **Add secret**.

## 2. ODDS_API_KEY: free Vegas lines

1. Go to <https://the-odds-api.com/> and choose the free **Starter** plan (500 requests/month, no card).
2. The key arrives by email.
3. Open <https://github.com/csorcic/nba_dfs_optimizer/settings/secrets/actions/new>.
4. **Name:** `ODDS_API_KEY`. **Secret:** paste the key. Click **Add secret**.

If you skip this, the app still works and takes lines from ESPN instead.

## 3. Let the pipeline save its data

1. Open <https://github.com/csorcic/nba_dfs_optimizer/settings/actions>.
2. Under **Workflow permissions**, choose **Read and write permissions** and click **Save**.

## 4. Turn on GitHub Pages (hosts the phone app for free)

1. Open <https://github.com/csorcic/nba_dfs_optimizer/settings/pages>.
2. **Source:** *Deploy from a branch*. **Branch:** `main`, folder `/docs`. Click **Save**.
3. After a minute or two, <https://csorcic.github.io/nba_dfs_optimizer/> shows a page saying "GitHub Pages is working."

## 5. Run the setup check

1. Open <https://github.com/csorcic/nba_dfs_optimizer/actions/workflows/setup_check.yml>.
2. Click **Run workflow** → **Run workflow**.
3. When it finishes, click the run. The summary shows a table:
   - **OK** on all three lines: done.
   - **FAIL** or **WARN**: the line says what's wrong. Tell Claude what it says.

## 6. Install the app on your Android phone

1. In Chrome on the phone, open <https://csorcic.github.io/nba_dfs_optimizer/>.
2. Tap **⋮** (top right) → **Add to Home screen** (or **Install app**) → **Install**.
3. Open it from the home screen. It works offline with the last slate it loaded.

## 7. Upload DK contest results (optional)

This adds the real winning score, the cash line, real ownership and your own finish to the
**Review** tab. Do it any time after a slate's games are over.

**Get the file from DraftKings** (phone or computer):
1. On draftkings.com, open **My Contests → Completed**, then open the contest.
2. Tap **Export Lineups to CSV** near the standings (DK sometimes renames this button; look for "export" or a download icon).
   DK gives you a `.zip` file, e.g. `contest-standings-197619862.zip`. You don't need to unzip it.

**Upload it to GitHub:**
1. Open <https://github.com/csorcic/nba_dfs_optimizer/tree/main/data/contests>.
2. Click **Add file → Upload files**.
3. Drag the `.zip` (or `.csv`) onto the page. You can add several at once.
4. At the bottom, leave **Commit directly to the main branch** selected and click **Commit changes**.

That's it. Within a few minutes the **Contest standings** action runs on its own. It works out
which slate the file belongs to, adds the results to that day's review, and moves the file into
`data/contests/processed/`. Open the **Review** tab on your phone to see it.

If a file can't be used (not a standings file, or no matching slate yet), it's moved to
`data/contests/unmatched/` with a note saying why. Nothing else is affected. If you uploaded it
before the slate's review existed, the next pipeline run picks it up automatically.

## If something looks wrong

- **"Today's slate hasn't been published yet"**: GitHub sometimes starts scheduled runs late. Open
  <https://github.com/csorcic/nba_dfs_optimizer/actions/workflows/pipeline.yml> → **Run workflow**.
  The app picks up the new slate a minute or two after the run turns green.
- **"No betting line yet"**: sportsbooks hadn't posted that game when the pipeline ran. The later runs fill it in.
- **A player shows NO DATA**: we couldn't find him on ESPN (usually a rookie). If he's a real rotation
  player, tell Claude his name so it can add a fix to `config/name_overrides.yaml`.
- **The app looks stale after an update**: close it fully and reopen; it updates itself.
