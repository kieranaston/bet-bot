# bet-bot

Finds positive-EV bets at Ontario-licensed sportsbooks by comparing their lines against
Pinnacle's devigged "true" odds, and sends you a Telegram alert when it finds one. You
reply to the bot (`/placed`, `/skip`, `/settle`) to log what you actually did, and it
tracks your bankroll and performance over time.

## How it works

1. A GitHub Actions workflow (`.github/workflows/scan.yml`) runs every 15 minutes.
2. It pulls upcoming NFL/NBA/NHL/MLB odds (moneyline, spread, totals) from
   [The Odds API](https://the-odds-api.com/), for Pinnacle (sharp reference, region `eu`)
   and Ontario-licensed books (region `ca`).
3. For each market, it devigs Pinnacle's two-way price into a true win probability
   (`src/betbot/devig.py`), then checks every Ontario book's price against that true
   probability (`src/betbot/ev.py`). Anything at or above the EV threshold in
   `config/settings.yaml` (default 2%) gets sized with quarter-Kelly
   (`src/betbot/kelly.py`) against your current bankroll and sent to you on Telegram.
4. It won't spam you: each (event, market, outcome, book) combination is only re-alerted
   after a cooldown that tightens as game time approaches, or immediately if the price
   moves (`src/betbot/scheduler.py`, tunable in `config/settings.yaml`).
5. You reply in Telegram:
   - `/placed <id> [stake]` — log that you bet it (defaults to the suggested stake)
   - `/skip <id>` — dismiss it
   - `/settle <id> win|loss|push [closing_odds]` — grade it; updates your bankroll and
     (if you pass the closing line) tracks closing-line value (CLV)
   - `/bankroll [amount]` — check or manually correct your bankroll
   - `/status` — list bets you've placed that aren't settled yet
6. A second workflow (`.github/workflows/daily_report.yml`) sends a daily digest:
   bankroll, open bets, win/loss record, ROI, average CLV.

## First-time setup

### 1. Get an Odds API key
Sign up at https://the-odds-api.com/ (the free tier is enough to start). Copy your API key.

### 2. Create a Telegram bot
1. Message [@BotFather](https://t.me/BotFather) on Telegram, send `/newbot`, follow the
   prompts. It gives you a **bot token**.
2. Send your new bot any message (e.g. "hi") so it has a chat to talk back to.
3. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser and find
   `"chat":{"id": ...}` in the JSON — that's your **chat ID**.

### 3. Set up a persistent database (required for GitHub Actions)
GitHub Actions runners are thrown away after every run, so bankroll/bet history can't
live in a local SQLite file there. The free path:
1. Create a free project at https://supabase.com/.
2. Project Settings → Database → Connection string → **URI** tab. Copy it
   (`postgresql://postgres:[password]@...`).
3. That's your `DATABASE_URL`.

(If you instead run this on a VPS or your own machine via cron — see "Alternative:
running without GitHub Actions" below — you can skip this and just let it use the default
local SQLite file at `data/betbot.db`.)

### 4. Add secrets to the GitHub repo
In the repo on GitHub: **Settings → Secrets and variables → Actions → New repository
secret**. Add all four:
- `ODDS_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `DATABASE_URL`

Once these are set, `.github/workflows/scan.yml` will start running automatically every
15 minutes (also triggerable manually from the Actions tab via "Run workflow").

### 5. Verify your Ontario bookmaker keys
`config/bookmakers.yaml` ships with best-known bookmaker keys, but The Odds API adds/renames
books over time. After step 1-2 above, run locally (see below) to check:

```bash
python scripts/list_bookmakers.py americanfootball_nfl
```

This prints every bookmaker key currently returned and flags which ones your config
auto-matches as Ontario books. Update `config/bookmakers.yaml` if anything's missing or
wrong — `ontario.auto_match_suffixes` (`_ca_on`, `_on`) catches most new additions
automatically, but it's worth a sanity check.

### 6. Set your real starting bankroll
Edit `bankroll.starting_amount` in `config/settings.yaml` before the first run (it only
takes effect once, when the database is first created — after that, use the `/bankroll`
Telegram command to adjust it).

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in your keys; DATABASE_URL can be left blank for local SQLite
pytest -q              # run the unit tests (devig, EV, Kelly, scheduler logic)
python -m betbot.main  # run one scan
python scripts/report.py  # send a daily-digest-style message on demand
```

## Alternative: running without GitHub Actions

If you'd rather run this on an always-on box (VPS, home server, Raspberry Pi) instead of
GitHub Actions — e.g. for tighter in-play scan intervals — nothing in the code changes:
1. Leave `DATABASE_URL` unset to use the local SQLite file, or point it at Postgres if you
   want to keep the same DB either way.
2. Point cron (or `launchd`/systemd) at `python -m betbot.main` on whatever interval you
   want, and at `python scripts/report.py` once a day.
3. Delete/disable `.github/workflows/scan.yml` and `daily_report.yml` if you don't want
   both running redundantly.

## Project layout

```
config/settings.yaml     bankroll, Kelly fraction, EV threshold, sports/markets, cooldowns
config/bookmakers.yaml    sharp book + Ontario book keys
src/betbot/
  odds_client.py          The Odds API wrapper
  devig.py                vig removal -> true probabilities
  ev.py                   true prob vs. book price -> EV%
  kelly.py                quarter-Kelly stake sizing
  scheduler.py            adaptive re-alert cooldown
  storage.py              SQLAlchemy models (alerts, bankroll history, kv state)
  telegram.py             Telegram Bot API client (send + short-poll getUpdates)
  commands.py             parses /placed, /skip, /settle, /bankroll, /status
  performance.py          ROI / win-rate / CLV rollups
  main.py                 orchestrates a single scan run
scripts/
  list_bookmakers.py      discovery helper for real bookmaker keys
  init_db.py               creates tables / seeds bankroll
  report.py                daily digest sender
.github/workflows/
  scan.yml                 runs the scan every 15 min
  daily_report.yml         sends the daily digest
  tests.yml                runs pytest on push/PR
```

## Known limitations (v1)

- Devig uses the basic multiplicative method, not Shin's method — fine for liquid
  two-way markets (moneyline/spread/totals), which is all this targets.
- Bet settlement (`/settle`) is manual — there's no automatic score-checking yet.
- No player props (main markets only), per initial scope.
- Line matching between Pinnacle and the Ontario book requires an exact point match for
  spreads/totals; if a book's line differs from Pinnacle's, that outcome is skipped rather
  than approximated.

## Responsible use

This tool surfaces pricing discrepancies between books for your own personal betting
decisions — it doesn't place bets automatically. Sportsbooks can and do limit or close
accounts they suspect of advantage betting; that's a business decision on their end, not
something this tool tries to evade. Bet within your means and your jurisdiction's rules.
