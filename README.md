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

- **To-do list, goals, and habits:** tap **Edit** on the dashboard itself. Changes save on that device only, so they are private and need no GitHub.
  `config.json` holds the default lists, and the **Reset to default** button restores them.
- **Watchlist, news feeds, timezone, weather location:** edit `config.json` (the GitHub mobile app works).
- **Delivery time:** edit the `cron` line in `.github/workflows/daily.yml`. It is in UTC, so
  11:00 UTC is 7am US Eastern during daylight time and 6am in winter. GitHub may start a few minutes late.
- **Weather:** set `lat` and `lon` in `config.json`.
- **Preview the design with sample data:** `python generate.py --demo`

## New sections

- **Country of the day:** a different country each day (data from REST Countries, text from Claude), with flag, facts, history,
  famous people, and three maps: a globe, the country with its neighbors, and, when the country was once part of a larger state
  such as Yugoslavia, a map of that former state. Maps use today's borders because historical borders are not available.
  The maps load from a public CDN, so they need an internet connection.
- **Sales skill:** one technique a day with an example script and a small practice.
- **Evening review:** saved on your device as you type, with a Past reviews list and a Share or copy all button.

## Good to know

- Edits, checkmarks, and reviews live in your browser. The Home Screen version and Safari keep **separate** storage, so use one of them
  consistently. Use Share or copy all now and then to back your reviews up (for example into Notes).

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
