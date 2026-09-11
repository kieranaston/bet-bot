# bet-bot

Finds positive-EV bets at Ontario-licensed sportsbooks by comparing their lines against
Pinnacle's devigged "true" odds, and sends you a Telegram alert when it finds one. You
reply to the bot (`/placed`, `/skip`, `/settle`) to log what you actually did, and it
tracks your bankroll and performance over time.

## How it works

1. A GitHub Actions workflow (`.github/workflows/scan.yml`) ticks every 10 minutes, but
   only actually calls the Odds API 3x/day, at 11am/5pm/11pm Eastern (configurable via
   `config/settings.yaml` `scheduling.scan_times_local` — checked in real, DST-aware
   Eastern clock time via `betbot.scheduler.is_scan_time`, not a fixed UTC cron, so it
   stays correct across daylight saving changes). Telegram command handling (`/placed`,
   `/skip`, `/settle`, etc.) still runs every 10-minute tick since it's free.
2. Per sport, it first hits the free `/events` endpoint (no quota cost) to check whether
   anything's even upcoming — if not, it skips the paid odds call entirely. Otherwise it
   pulls NFL/NBA/NHL/MLB odds (moneyline, spread, totals) from
   [The Odds API](https://the-odds-api.com/) via `bookmakers=` (Pinnacle + your 6 Ontario
   books, see `config/bookmakers.yaml`) rather than `regions=` — The Odds API prices every
   group of ≤10 named bookmakers as 1 region-equivalent, so our 7 books cost half of what
   `regions=eu,ca` would for the same data.
3. For each market, it devigs Pinnacle's two-way price into a true win probability
   (`src/betbot/devig.py`), then checks every Ontario book's price against that true
   probability (`src/betbot/ev.py`). Anything at or above the EV threshold in
   `config/settings.yaml` (default 2%) gets sized with quarter-Kelly
   (`src/betbot/kelly.py`) against your current bankroll and sent to you on Telegram,
   including a direct bet-slip link when the book provides one (`includeLinks=true`).
4. It won't spam you: each (event, market, outcome, book) combination is only re-alerted
   after a cooldown that tightens as game time approaches, or immediately if the price
   moves (`src/betbot/scheduler.py`, tunable in `config/settings.yaml`).
5. Before scanning for new opportunities, it also auto-settles any bet you've logged as
   `/placed` whose game has finished, using The Odds API's `/scores` endpoint (flat 2
   credits/request, only called for sports with something actually pending) —
   `src/betbot/settlement.py` grades moneyline/spread/total outcomes from the final score
   and updates your bankroll automatically. You can still `/settle` manually if you want to
   record the closing line for CLV, or if you'd rather not wait for the next scan window.
6. You reply in Telegram:
   - `/placed <id> [stake]` — log that you bet it (defaults to the suggested stake)
   - `/skip <id>` — dismiss it
   - `/settle <id> win|loss|push [closing_odds]` — grade it manually; updates your bankroll
     and (if you pass the closing line) tracks closing-line value (CLV)
   - `/bankroll [amount]` — check or manually correct your bankroll
   - `/status` — list bets you've placed that aren't settled yet
7. A second workflow (`.github/workflows/daily_report.yml`) sends a daily digest:
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
2. Project Settings → Database → Connection string → **Session pooler** tab (not "URI" /
   direct connection — Supabase's direct connection is IPv6-only on new projects, and
   GitHub Actions runners have no IPv6 route, so it fails with "Network is unreachable").
   Copy it (`postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres`).
3. That's your `DATABASE_URL`.

(If you instead run this on a VPS or your own machine via cron — see "Alternative:
running without GitHub Actions" below — you can skip this and just let it use the default
local SQLite file at `data/betbot.db`.)

**Already ran a scan before this update?** The `alerts` table needs one new column. In
Supabase's SQL Editor, run:
```sql
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS deep_link VARCHAR;
```
(A fresh install doesn't need this — `Database.__init__` creates the table with the new
column already included.)

### 4. Add secrets to the GitHub repo
In the repo on GitHub: **Settings → Secrets and variables → Actions → New repository
secret**. Add all four:
- `ODDS_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `DATABASE_URL`

Once these are set, `.github/workflows/scan.yml` will start ticking automatically every
10 minutes, actually scanning 3x/day (see "How it works" above; also triggerable manually
from the Actions tab via "Run workflow"). **Both scheduled workflows are currently
disabled** (`gh workflow list --all` to check) — re-enable with
`gh workflow enable scan.yml` and `gh workflow enable daily_report.yml` when ready.

### 5. Verify your Ontario bookmaker keys
`config/bookmakers.yaml` is a deliberately closed allowlist — currently `bet99_ca_on`,
`betano_ca_on`, `betmgm_ca_on`, `betrivers_ca_on`, `proline_ca_on`, `sportsinteraction_ca_on`.
No suffix auto-matching: a book not in that list is never checked, even if The Odds API
returns it under the `ca` region. If you want to add or remove a book, run locally (see
below) to confirm the exact live key first:

```bash
python scripts/list_bookmakers.py americanfootball_nfl
```

This prints every bookmaker key The Odds API currently returns for that sport/region —
use it to confirm a key before adding it to `config/bookmakers.yaml`, since keys
occasionally change.

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
  odds_client.py          The Odds API wrapper (/events, /odds, /scores)
  devig.py                vig removal -> true probabilities
  ev.py                   true prob vs. book price -> EV%
  kelly.py                quarter-Kelly stake sizing
  scheduler.py            scan-window gating (DST-safe) + adaptive re-alert cooldown
  settlement.py           win/loss/push grading + auto-settle via /scores
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
  scan.yml                 ticks every 10 min, actually scans 3x/day (see scan_times_local)
  daily_report.yml         sends the daily digest
  tests.yml                runs pytest on push/PR
```

## Known limitations (v1)

- Devig uses the basic multiplicative method, not Shin's method — fine for liquid
  two-way markets (moneyline/spread/totals), which is all this targets.
- No player props (main markets only), per initial scope.
- Line matching between Pinnacle and the Ontario book requires an exact point match for
  spreads/totals; if a book's line differs from Pinnacle's, that outcome is skipped rather
  than approximated.
- Auto-settlement only checks games within `settlement.days_from` (2 days) of finishing,
  and only runs during the 3x/day scan window — a bet can sit unsettled for a few hours
  after its game ends before the next scan catches it. `/settle` still works manually if
  you don't want to wait.
- The exact JSON field(s) `includeLinks=true` returns aren't fully documented by The Odds
  API; `extract_outcomes` in `main.py` tries `outcome.link` → `market.link` →
  `bookmaker.link` and falls back to no link if none are present. Worth double-checking
  against real response data the first time this runs live.

## Responsible use

This tool surfaces pricing discrepancies between books for your own personal betting
decisions — it doesn't place bets automatically. Sportsbooks can and do limit or close
accounts they suspect of advantage betting; that's a business decision on their end, not
something this tool tries to evade. Bet within your means and your jurisdiction's rules.
