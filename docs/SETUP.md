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
