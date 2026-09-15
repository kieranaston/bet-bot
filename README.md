# bet-bot

Finds positive-EV bets at Ontario-licensed sportsbooks by comparing their lines against
Pinnacle's devigged "true" odds (or, for player props, a multi-book consensus), and sends a
Telegram alert when it finds one. Reply `/placed`, `/skip`, or `/settle` to log what you did;
it tracks bankroll and performance over time. Doesn't place bets automatically.

Runs continuously on a small always-on VPS (Docker + SQLite). GitHub Actions can run the same
code as a manual-dispatch-only emergency backup (see below), but isn't a real substitute — see
"Backup: running via GitHub Actions".

## How it works

1. A Docker container polls Telegram commands every ~20s (free) and, on a schedule
   (`config/settings.yaml` `scheduling.scan_times_local` / `props.scan_times_local`, DST-aware
   Eastern time), spends Odds API credits to scan for value:
   - **Main markets** (h2h/spreads/totals) across configured sports, matched against Pinnacle
     (or a median fallback of FanDuel/DraftKings/BetMGM if Pinnacle's absent/stale).
   - **Additional markets** (player props, game-level alternate lines) fetched per-event,
     proximity-gated to just before kickoff since books only post these close to game time.
2. Each candidate is devigged to a true win probability (`betbot/devig.py`), checked against
   the EV floor and a minimum true-probability floor (filters extreme longshots), then sized
   with quarter-Kelly (`betbot/kelly.py`) against your bankroll and sent to Telegram.
3. Re-alerts are cooldown-gated (tighter near game time) unless price moves meaningfully, and
   never repeat once you've acted on a given alert.
4. Placed bets are auto-settled from `/scores` when the game finishes (moneyline/spread/total/
   team-total markets); player props have no player-level box score in that feed, so those
   need a manual `/settle`.
5. A daily digest (bankroll, open bets, record, ROI) sends automatically at
   `reporting.time_local`, or on demand via `scripts/report.py`.

See `CLAUDE.md` for the full architecture, cost model, and the reasoning behind specific
config choices (schedule cadence, market allowlists, devig method, etc).

### Telegram commands

- `/placed <id> [stake]` — log that you bet it
- `/skip <id>` — dismiss it
- `/settle <id> win|loss|push` — grade it manually
- `/bankroll [amount]` — check or correct your bankroll
- `/status` — bets placed but not yet settled
- `/stats` — bankroll + settled performance
- `/scan` — run a scan on demand (rate-limited)
- `/quota` — check Odds API usage
- `/help` — list all commands

## First-time setup

1. **Odds API key** — sign up at https://the-odds-api.com/ (free tier is enough to start).
2. **Telegram bot** — message [@BotFather](https://t.me/BotFather), `/newbot`, get a bot
   token. Message your new bot once, then visit
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` to find your chat ID in the JSON.
3. **Verify bookmaker keys** — `config/bookmakers.yaml` is a closed allowlist (Ontario books +
   Pinnacle + consensus fallback books). Confirm live keys before changing it:
   ```bash
   python scripts/list_bookmakers.py americanfootball_nfl              # main markets
   python scripts/list_bookmakers.py soccer_epl --market spreads       # coverage check
   python scripts/list_event_markets.py baseball_mlb                   # props/alt markets
   ```
4. **Starting bankroll** — set `bankroll.starting_amount` in `config/settings.yaml` before
   first run (only used once, at DB creation; use `/bankroll` to adjust after that).
5. **Deploy** — see below.

### Deploying to a VPS

Any small always-on VPS works (e.g. a free-tier GCP `e2-micro`).

```bash
sudo apt update && sudo apt upgrade -y && sudo apt install -y docker.io git
sudo usermod -aG docker $USER   # log out/in after this

git clone <this-repo-url> bet-bot && cd bet-bot
cat > .env << 'EOF'
ODDS_API_KEY=your_key_here
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
EOF
# Leave DATABASE_URL unset -- defaults to local SQLite at data/betbot.db.

mkdir -p data && chmod 777 data
docker build -t bet-bot .
docker run -d --name bet-bot --restart unless-stopped --env-file .env -v $(pwd)/data:/app/data bet-bot
docker logs -f bet-bot   # should show a Telegram poll line every ~20s
```

### Updating the running VPS

Pushing to GitHub does **not** redeploy automatically:

```bash
ssh <user>@<VM_IP> && cd ~/bet-bot
git pull
docker build -t bet-bot .
docker stop bet-bot && docker rm bet-bot
docker run -d --name bet-bot --restart unless-stopped --env-file .env -v $(pwd)/data:/app/data bet-bot
```

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # fill in keys; DATABASE_URL can be left blank for local SQLite
pytest -q                   # run tests
python -m betbot.main       # run one iteration (poll + scan if in a window)
python scripts/report.py    # send a daily-digest message on demand
```

## Backup: running via GitHub Actions

Not currently set up or planned — the VPS is the only real deployment, using local SQLite.
`.github/workflows/betbot-scan.yml` and `daily_report.yml` exist as manual-dispatch-only
fallbacks (GitHub's native `schedule:` trigger proved unreliable for this at short cadences).
Reviving this path would need a fresh persistent database (Actions runners have no durable
disk) — see `CLAUDE.md` for the full history if you want to go there.

## Project layout

```
config/settings.yaml      bankroll, Kelly, EV thresholds, sports/markets, schedule, report time
config/bookmakers.yaml    sharp/consensus/Ontario bookmaker keys
src/betbot/
  odds_client.py          The Odds API wrapper
  devig.py                vig removal -> true probabilities
  ev.py                   true prob vs. book price -> EV%
  kelly.py                quarter-Kelly stake sizing
  matching.py             sharp/consensus reference selection + point interpolation
  scheduler.py            scan-window gating + adaptive re-alert cooldown
  settlement.py           win/loss/push grading + auto-settle via /scores
  storage.py              SQLAlchemy models
  telegram.py             Telegram Bot API client
  commands.py             /placed, /skip, /settle, /bankroll, /status, /stats, /scan, /quota
  performance.py          ROI / win-rate rollups
  main.py                 entry point: poll, gate, scan, settle, report
scripts/
  list_bookmakers.py      discovery helper (main markets)
  list_event_markets.py   discovery helper (props/game-alt markets, ground truth)
  init_db.py              creates tables / seeds bankroll
  report.py               manual on-demand daily-digest sender
  migrate_*.py            one-time DB migrations
.github/workflows/        disabled-by-default backups + pytest CI
Dockerfile                how the VPS runs the bot
```

## Known limitations

See `CLAUDE.md`'s "Known v1 limitations" section for the full, current list (player prop
sport coverage, devig method scope, settlement gaps, etc) — kept in one place to avoid drift
between two copies.

## Responsible use

This tool surfaces pricing discrepancies between books for your own betting decisions — it
doesn't place bets automatically. Sportsbooks can limit or close accounts they suspect of
advantage betting; that's their business decision, not something this tool tries to evade.
Bet within your means and your jurisdiction's rules.
