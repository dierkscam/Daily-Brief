# Daily brief

Every morning a GitHub Action pulls your watchlist prices and news, asks Claude to write the day's
lessons, rebuilds the dashboard, and sends a notification to your phone.

## One-time setup (about 20 minutes)

1. **Create the repo.** On github.com, New repository, name it `daily-brief`, set it to **Public**
   (free GitHub Pages requires this), and upload every file from this folder. The `.github` folder
   must keep its path: `.github/workflows/daily.yml`.
2. **Get a Finnhub key** (free) at finnhub.io. This gives prices, company news, and earnings dates.
3. **Get a Claude API key** at console.anthropic.com. This is separate from the Claude app
   subscription. Daily use costs pennies.
4. **Pick a private notification topic.** Make up a long random name, for example
   `camden-brief-7f3k29xq81`. Anyone who knows the name can read the notifications, so keep it secret.
5. **Add secrets.** In the repo: Settings, Secrets and variables, Actions, New repository secret.
   Add `ANTHROPIC_API_KEY`, `FINNHUB_API_KEY`, and `NTFY_TOPIC` (your topic name from step 4).
6. **Turn on Pages.** Settings, Pages, Deploy from a branch, branch `main`, folder `/docs`, Save.
   Your dashboard will live at `https://YOUR-USERNAME.github.io/daily-brief/`.
7. **Run it once.** Actions tab, Daily brief, Run workflow. After about two minutes, open your page.
8. **Phone.** Install the free **ntfy** app, tap +, and subscribe to your topic name. Then open your
   dashboard in Safari, tap Share, Add to Home Screen. Tapping the notification opens the dashboard.

## Changing things

- **Watchlist, goals, tasks, habits, news feeds, timezone, weather location:** edit `config.json`.
  You can do this from the GitHub mobile app.
- **Delivery time:** edit the `cron` line in `.github/workflows/daily.yml`. It is in UTC, so
  11:00 UTC is 7am US Eastern during daylight time and 6am in winter. GitHub may start a few minutes late.
- **Weather:** set `lat` and `lon` in `config.json`.
- **Preview the design with sample data:** `python generate.py --demo`

## Good to know

- GitHub Pages sites are public. Anyone with the link can see your watchlist, goals, and tasks.
  Checkmarks and evening notes stay in your own browser and are never uploaded.
- Index prices are shown through ETFs (SPY, DIA, QQQ) because the free data tier has no index feeds.
- If a data source or the Claude call fails, that section is skipped for the day instead of breaking the page.
- Lessons are tracked in `data/state.json` so topics do not repeat.
- Prices are as of the last update, not live.

## Optional: iPhone Shortcut instead of ntfy

Shortcuts, Automation, Time of Day, Run Immediately: Get Contents of URL (`.../summary.json`), Get Dictionary
Value (`body`), Show Notification. Tapping a Shortcuts notification opens the Shortcuts app, not your page,
which is why ntfy is the default.
