# bet-bot

Finds positive-EV bets at Ontario-licensed sportsbooks by comparing their lines against
Pinnacle's devigged "true" odds, and sends you a Telegram alert when it finds one. You
reply to the bot (`/placed`, `/skip`, `/settle`) to log what you actually did, and it
tracks your bankroll and performance over time.

Runs continuously on a small always-on VPS (Docker + SQLite, $0/month on a free-tier VM) so
Telegram commands get near-instant replies. GitHub Actions can run the same code as a
disabled-by-default backup — see "Backup: running via GitHub Actions" below — but the VPS
is the primary deployment.

## How it works

1. A small Docker container runs `python -m betbot.main` in a loop (~every 20 seconds) on
   the VPS. Each iteration polls Telegram for new commands (`/placed`, `/skip`, `/settle`,
   `/scan`, etc.) — that's free, so this stays responsive between real scans — then checks
   whether it's time to actually spend Odds API credits.
2. Real scans only happen hourly, 10am-11pm Eastern (14x/day), configurable via
   `config/settings.yaml` `scheduling.scan_times_local` — checked in real, DST-aware
   Eastern clock time via `betbot.scheduler.is_scan_time`, not a fixed UTC cron, so it stays
   correct across daylight saving changes. Since the poll loop ticks far more often than
   that, `betbot.scheduler.current_scan_window_key` + a `last_scan_window` marker in the
   database make sure each hourly window is only actually scanned once, not once per ~20s
   poll. Deliberately restricted to waking/actionable hours rather than round-the-clock —
   an alert at 3am ET is useless if you're asleep and can't act on it before the price
   moves, even though Pinnacle's soccer lines are most active overnight (European business
   hours). Overnight soccer mispricings are a known, accepted gap in this schedule.
3. Per sport, it first hits the free `/events` endpoint to check whether anything's even
   upcoming, skipping the odds call entirely if not (an empty `/odds` response also costs
   0 credits per the docs, so this mainly saves a round-trip rather than credits). Otherwise
   it pulls odds for the sports/markets configured in `config/settings.yaml` `sports:` — NFL,
   NBA, NHL, MLB, NCAAF get h2h/spreads/totals; CFL, MMA, and five soccer leagues (EPL,
   La Liga, Bundesliga, Serie A, MLS) are restricted to h2h only — from
   [The Odds API](https://the-odds-api.com/) via `bookmakers=` — Pinnacle + your 6 Ontario
   books, 7 keys total. The Odds API's docs confirm "every group of 10 bookmakers is the
   equivalent of 1 region," so our 7 books cost 1 region-equivalent instead of the 2 regions
   `regions=eu,ca` would need for the same data. That's roughly 9,200 credits/month at 14
   scans/day (~46% of a 20,000/month plan) — sized to stay on markets/leagues where
   Pinnacle is still a sharp, liquid reference, deliberately not extended to player props or
   thin/niche leagues where "true odds" would be less trustworthy. The h2h-only restriction
   on CFL/MMA/soccer follows the docs' own caveat that "spreads and totals markets are mainly
   available for US sports and bookmakers" — since the plain `/odds` endpoint charges for
   every *requested* market regardless of whether any bookmaker actually returns data for it,
   requesting a market Pinnacle doesn't reliably price there is wasted spend, not just a
   missed signal. Every sport/market above was live-verified (2026-09-12) to actually have
   Pinnacle present; `basketball_ncaab` and `soccer_uefa_champs_league` were pulled from the
   list after that check found zero upcoming events for either in the 7-day scan window (see
   comments in `config/settings.yaml` for when/how to re-add and re-verify each). Use
   `scripts/list_bookmakers.py <sport> --market spreads` to re-check Pinnacle coverage
   yourself at any point. Soccer's h2h is a 3-way market (home/draw/away);
   `betbot.ev`/`betbot.main`'s matching already generalizes to N-way markets, and
   `betbot.settlement.grade_alert` handles a tied score as a loss (not a push) for a
   home/away bet in 3-way sports. Run
   `python -c "from betbot.config import Secrets, settings; from betbot.odds_client import OddsApiClient; c = OddsApiClient(Secrets.from_env().odds_api_key, settings.odds_api_base_url); print(c.list_sports())"`
   (free, no quota cost) to confirm a sport's current key before adding another one —
   tennis was left out here because the API has historically used per-tournament keys
   rather than one persistent `tennis_atp`/`tennis_wta` key.
4. For each market, it devigs Pinnacle's two-way price into a true win probability
   (`src/betbot/devig.py`), then checks every Ontario book's price against that true
   probability (`src/betbot/ev.py`). If more than one Ontario book clears the bar for the
   same outcome, only the single best-priced one is used -- otherwise the same bet showing
   value at multiple books would each send their own alert, which reads as duplicate
   notifications for one decision. To actually alert, a bet needs both EV at or above the
   threshold in `config/settings.yaml` (default 2%) *and* a true (fair) win probability at
   or above `ev.min_true_prob` (default 25%, i.e. no longer than roughly +300 American) --
   high-EV longshots are both higher-variance and less trustworthy, since devig error grows
   proportionally larger at the tails. Whatever survives both filters gets sized with
   quarter-Kelly (`src/betbot/kelly.py`) against your current bankroll and sent to you on
   Telegram (odds shown in American format), including a direct bet-slip link when the book
   provides one (`includeLinks=true`).
5. It won't spam you: each (event, market, outcome, line) combination is only re-alerted
   after a cooldown that tightens as game time approaches, or immediately if the price
   moves (`src/betbot/scheduler.py`, tunable in `config/settings.yaml`).
6. Whenever a real scan happens, it also first auto-settles any bet you've logged as
   `/placed` whose game has finished, using The Odds API's `/scores` endpoint (flat 2
   credits/request, only called for sports with something actually pending) —
   `src/betbot/settlement.py` grades moneyline/spread/total outcomes from the final score
   and updates your bankroll automatically. You can still `/settle` manually any time if you
   don't want to wait for the next scan window.
7. Once a day, at `config/settings.yaml` `reporting.time_local`, it automatically sends a
   digest to Telegram: bankroll, open bets, settled win/loss record, and ROI (same
   once-per-window dedup pattern as the scan gating, via a `last_daily_report_window`
   marker). `scripts/report.py` sends the same digest on demand if you want it sooner.
8. You reply in Telegram:
   - `/placed <id> [stake]` — log that you bet it (defaults to the suggested stake)
   - `/skip <id>` — dismiss it
   - `/settle <id> win|loss|push` — grade it manually; updates your bankroll
   - `/bankroll [amount]` — check or manually correct your bankroll
   - `/status` — list bets you've placed that aren't settled yet
   - `/stats` — bankroll + settled performance (wins/losses/ROI), on demand
   - `/scan` — run a scan on demand instead of waiting for the next window (uses Odds API
     credits, same as an automatic scan; rate-limited to once every
     `commands.SCAN_COOLDOWN_MINUTES` (5 min) so a repeated tap can't blow through quota)
   - `/quota` — check Odds API usage (used/remaining/% of the current period used)
   - `/help` — list all of the above

## First-time setup

### 1. Get an Odds API key
Sign up at https://the-odds-api.com/ (the free tier is enough to start). Copy your API key.

### 2. Create a Telegram bot
1. Message [@BotFather](https://t.me/BotFather) on Telegram, send `/newbot`, follow the
   prompts. It gives you a **bot token**.
2. Send your new bot any message (e.g. "hi") so it has a chat to talk back to.
3. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser and find
   `"chat":{"id": ...}` in the JSON — that's your **chat ID**.

### 3. Verify your Ontario bookmaker keys
`config/bookmakers.yaml` is a deliberately closed allowlist — currently `bet99_ca_on`,
`betano_ca_on`, `betmgm_ca_on`, `betrivers_ca_on`, `proline_ca_on`, `sportsinteraction_ca_on`.
No suffix auto-matching: a book not in that list is never checked, even if The Odds API
returns it under the `ca` region. If you want to add or remove a book, run locally (see
"Local development" below) to confirm the exact live key first:

```bash
python scripts/list_bookmakers.py americanfootball_nfl
```

The same script also doubles as a Pinnacle-coverage check before trusting a market in
`config/settings.yaml` — pass `--market spreads` or `--market totals` (defaults to `h2h`) to
confirm `pinnacle` actually appears for that sport/market combo. This matters because the
docs warn spreads/totals coverage is "mainly available for US sports and bookmakers" — several
non-US leagues in `sports:` are deliberately restricted to `h2h` only until verified this way:

```bash
python scripts/list_bookmakers.py soccer_epl --market spreads
```

This prints every bookmaker key The Odds API currently returns for that sport/region —
use it to confirm a key before adding it to `config/bookmakers.yaml`, since keys
occasionally change.

### 4. Set your real starting bankroll
Edit `bankroll.starting_amount` in `config/settings.yaml` before the first run (it only
takes effect once, when the database is first created — after that, use the `/bankroll`
Telegram command to adjust it).

### 5. Deploy to a VPS

Any small VPS works. A free-tier VM (e.g. Google Cloud's `e2-micro`, always-free in
`us-west1`/`us-central1`/`us-east1`) is enough for this — the bot is lightweight and only
does real work ~14x/day.

1. Create an Ubuntu 24.04 VM and SSH into it.
2. Install Docker and git:
   ```bash
   sudo apt update && sudo apt upgrade -y
   sudo apt install -y docker.io git
   sudo usermod -aG docker $USER
   ```
   Log out and back in (or open a fresh SSH session) for the group change to apply.
3. Clone the repo and create `.env`:
   ```bash
   git clone <this-repo-url> bet-bot
   cd bet-bot
   cat > .env << 'EOF'
   ODDS_API_KEY=your_key_here
   TELEGRAM_BOT_TOKEN=your_token_here
   TELEGRAM_CHAT_ID=your_chat_id_here
   EOF
   ```
   Leave `DATABASE_URL` out entirely — it defaults to a local SQLite file at
   `data/betbot.db`, which persists fine on a VPS's real disk (unlike a GitHub Actions
   runner). No Postgres/Supabase needed for this path.
4. Build and run it as a long-lived container:
   ```bash
   mkdir -p data && chmod 777 data
   docker build -t bet-bot .
   docker run -d --name bet-bot --restart unless-stopped --env-file .env -v $(pwd)/data:/app/data bet-bot
   ```
   `chmod 777 data` avoids a permissions mismatch between the container's non-root user and
   the host directory when bind-mounting. `--restart unless-stopped` means the container
   survives VM reboots and restarts automatically if it ever crashes.
5. Confirm it's running:
   ```bash
   docker logs -f bet-bot
   ```
   You should see a Telegram poll log line roughly every 20 seconds. Try `/status` or
   `/stats` in Telegram — it should reply within ~20 seconds.

   Note: the VPS creates its own fresh `data/betbot.db` on first run — if you'd previously
   tested locally or on a different machine, that data doesn't carry over automatically.

## Updating the running VPS deployment

Pushing to GitHub does **not** update the VPS by itself — you need to redeploy manually:

```bash
ssh <your-username>@<VM_EXTERNAL_IP>
cd ~/bet-bot
git pull
docker build -t bet-bot .
docker stop bet-bot
docker rm bet-bot
docker run -d --name bet-bot --restart unless-stopped --env-file .env -v $(pwd)/data:/app/data bet-bot
```

Then confirm it picked up the change:

```bash
docker logs -f bet-bot
```

You should see a Telegram poll log line within ~20 seconds (`Ctrl+C` to stop watching the
logs — this does not stop the container).

## Local development

For running tests and one-off manual checks — not how the bot is actually deployed:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in your keys; DATABASE_URL can be left blank for local SQLite
pytest -q              # run the unit tests (devig, EV, Kelly, scheduler logic)
python -m betbot.main  # run one iteration (Telegram poll + scan if in a window)
python scripts/report.py  # send a daily-digest-style message on demand
```

## Backup: running via GitHub Actions

`.github/workflows/betbot-scan.yml` and `daily_report.yml` can run the exact same code on
GitHub's own schedulers instead of (or alongside) the VPS. **Both are currently disabled**
(`gh workflow list --all` to check) — this repo found GitHub's native `schedule:` trigger
unreliable at anything faster than a few-times-a-day cadence (it silently dropped ~98% of
ticks at `*/10`, then 100% of ticks at twice-hourly — see git history on
`betbot-scan.yml`), which is why the VPS is the primary path. `betbot-scan.yml` now only
has a manual `workflow_dispatch` trigger (with a `force` checkbox to bypass scan-window
gating), meant as an emergency fallback if the VPS goes down, not a schedule.

To use this path instead of (or in addition to) the VPS:

1. GitHub Actions runners are thrown away after every run, so bankroll/bet history can't
   live in a local SQLite file there — you need a persistent hosted database:
   1. Create a free project at https://supabase.com/.
   2. Project Settings → Database → Connection string → **Session pooler** tab (not "URI" /
      direct connection — Supabase's direct connection is IPv6-only on new projects, and
      GitHub Actions runners have no IPv6 route, so it fails with "Network is unreachable").
      Copy it (`postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres`).
   3. That's your `DATABASE_URL`.
2. In the repo on GitHub: **Settings → Secrets and variables → Actions → New repository
   secret**. Add all four: `ODDS_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
   `DATABASE_URL`.
3. Re-enable the workflow(s):
   ```bash
   gh workflow enable betbot-scan.yml
   gh workflow enable daily_report.yml
   ```
4. If running this instead of the VPS, add back a `schedule:` block to
   `betbot-scan.yml` at a cadence you've actually verified fires reliably (test with
   `gh run list --workflow=betbot-scan.yml` before trusting it) — don't assume the old
   twice-hourly cadence works, since that's exactly what didn't.

**Note on the two databases:** if you run the VPS (local SQLite) and GitHub Actions
(Supabase Postgres) at different times, they track separate bankroll/bet histories — the
data doesn't automatically sync between them.

## Project layout

```
config/settings.yaml     bankroll, Kelly fraction, EV threshold, longshot floor, sports/markets, cooldowns, report time
config/bookmakers.yaml    sharp book + Ontario book keys
src/betbot/
  odds_client.py          The Odds API wrapper (/events, /odds, /scores, /sports quota check)
  devig.py                vig removal -> true probabilities
  ev.py                   true prob vs. book price -> EV%
  kelly.py                quarter-Kelly stake sizing
  scheduler.py            scan-window gating (DST-safe, dedup-safe) + adaptive re-alert cooldown
  settlement.py           win/loss/push grading + auto-settle via /scores
  storage.py              SQLAlchemy models (alerts, bankroll history, kv state)
  telegram.py             Telegram Bot API client (send + short-poll getUpdates)
  commands.py             parses /placed, /skip, /settle, /bankroll, /status, /stats, /scan, /quota
  performance.py          ROI / win-rate rollups, shared report-line builder
  main.py                 continuous-loop entry point: poll, gate, scan, settle, report
scripts/
  list_bookmakers.py      discovery helper for real bookmaker keys
  init_db.py               creates tables / seeds bankroll
  report.py                manual on-demand daily-digest sender
.github/workflows/
  betbot-scan.yml          disabled by default; manual-dispatch-only backup (see "Backup" above)
  daily_report.yml         disabled by default; manual-dispatch-only backup
  tests.yml                runs pytest on push/PR
Dockerfile                 how the VPS runs the bot (continuous poll loop)
```

## Known limitations (v1)

- Devig uses the basic multiplicative method, not Shin's method — fine for liquid
  two-way markets (moneyline/spread/totals), which is all this targets.
- No player props (main markets only), per initial scope — also a poor cost/quality
  trade-off: props require a per-event API call instead of one bulk call per sport, and
  Pinnacle is less liquid/reliable there as a "true odds" reference.
- No closing-line-value (CLV) tracking — considered and deliberately dropped, since it
  would require either extra API calls to snapshot the closing line or manual entry, and
  wasn't worth the added complexity for this use case.
- Line matching between Pinnacle and the Ontario book requires an exact point match for
  spreads/totals; if a book's line differs from Pinnacle's, that outcome is skipped rather
  than approximated.
- Auto-settlement only checks games within `settlement.days_from` (2 days) of finishing,
  and only runs alongside a real scan (hourly, 10am-11pm ET) — a bet finishing overnight
  can sit unsettled until the next scan window catches it. `/settle` still works manually if
  you don't want to wait.
- Bookmaker homepage URLs in `config/bookmakers.yaml` (`homepage_urls`, used as the final
  deep-link fallback) are best-effort guesses, not verified against each book's actual
  current domain.

## Responsible use

This tool surfaces pricing discrepancies between books for your own personal betting
decisions — it doesn't place bets automatically. Sportsbooks can and do limit or close
accounts they suspect of advantage betting; that's a business decision on their end, not
something this tool tries to evade. Bet within your means and your jurisdiction's rules.
