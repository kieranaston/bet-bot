# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A +EV sports betting bot: finds mispriced lines at Ontario-licensed sportsbooks by comparing
them against Pinnacle's devigged "true" odds, and alerts via Telegram. Runs on a schedule (GitHub
Actions or cron/VPS), not as a long-lived service. It does not place bets automatically.

## Commands

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # fill in keys; DATABASE_URL can be left blank for local SQLite

pytest -q                   # run all tests
pytest tests/test_devig.py  # run a single test file
pytest -q -k ev_pct         # run tests matching a name

python -m betbot.main       # run one scan (respects scan-time gating, see below)
python scripts/report.py    # send a daily-digest-style message on demand
python scripts/list_bookmakers.py americanfootball_nfl  # discover live bookmaker keys for a sport
python scripts/init_db.py   # create tables / seed bankroll
```

There is no lint/format command configured (no ruff/black/flake8 in dependencies).

## Architecture

`src/betbot/main.py::run()` is the single entry point, invoked on every scheduler tick
(`.github/workflows/betbot-scan.yml`, twice hourly at :08/:38 UTC -- GitHub throttles `*/10` so
badly that commands were sitting unanswered for hours). It does two things unconditionally cheaply,
then one thing only inside scan windows:

1. **Always**: poll Telegram `getUpdates` and dispatch `/placed`, `/skip`, `/settle`, `/bankroll`,
 `/status` via `commands.py` — free, so this stays responsive even between real scans.
2. **Gated by `scheduler.is_scan_time()`**: only proceed past this point during the 8x/day windows
 (evenly every 3 hours, deliberately not bursted by game day or US evening hours — see the
 comment above `scan_times_local` in `config/settings.yaml`) in `config/settings.yaml`
 (`scheduling.scan_times_local`), checked in real DST-aware Eastern time via `zoneinfo` — not a
 fixed UTC cron. This is the load-bearing cost control: it's what keeps Odds API usage at
 ~8 calls/day/sport instead of one per tick.
3. Inside a scan window: auto-settle any `/placed` bets whose games finished (`settlement.py`, via
   `/scores`), then scan each configured sport (`config/settings.yaml` `sports:`) for +EV lines.

The scan pipeline per sport, per event, per market (`main.py::process_event`):
`odds_client.py` (fetch) → `devig.py` (Pinnacle two-way price → true probability) → `ev.py`
(true prob vs. Ontario book price → EV%) → `kelly.py` (quarter-Kelly stake sizing, capped by
`bankroll.max_stake_pct_of_bankroll`) → `storage.py` (upsert `Alert`, keyed on
event+market+outcome+bookmaker) → `scheduler.should_alert()` (adaptive cooldown gate) →
`telegram.py` (send).

Key invariants to preserve when touching this path:
- **Cost model**: real scans fetch odds with `bookmakers=` (built from `config/bookmakers.yaml`
  sharp + Ontario keys, ≤10 keys total) rather than `regions=`, because The Odds API prices every
  group of 10 bookmakers as 1 region-equivalent — half the cost of `regions=eu,ca` for the same
  data. `config/settings.yaml`'s `odds_api.regions` is kept only for
  `scripts/list_bookmakers.py`'s discovery use, not real scans. Don't reintroduce `regions=` on
  the real scan path without redoing this cost math.
- **Ontario allowlist is closed**: `config.py::Settings.is_ontario_book()` only matches
  `config/bookmakers.yaml`'s `known_keys` (plus `auto_match_suffixes`) — a book not listed is
  never checked even if the API returns it under the `ca` region. Adding a book means confirming
  its live key first via `scripts/list_bookmakers.py`, since keys occasionally change.
- **3-way markets (soccer h2h) grade differently from 2-way**: `devig.py`/`ev.py`/`main.py`'s
  matching already generalize to N outcomes, but `settlement.py::grade_alert()` must treat a
  tied score as a **loss** (not a push) for a home/away bet when `sport_key` starts with
  `soccer_` — the Draw outcome won, so the push branch is reserved for genuine 2-way ties
  (e.g. an NFL regular-season tie). Don't add a new 3-way sport without checking this branch
  still classifies its draw/tie outcome correctly.
- **Line matching is exact**: a book's outcome only compares against Pinnacle if `(name, point)`
  matches exactly (`main.py::process_event`, `sharp_lookup`); no point-approximation for
  spreads/totals.
- **Re-alert suppression**: `Alert` rows are deduplicated on
  `(event_id, market, outcome_name, point, bookmaker_key)`. Once a user acts (`placed`/`skipped`/
  settled), that alert is never re-sent (`main.py::_upsert_and_maybe_notify`). Otherwise
  re-alerting is gated by `scheduler.should_alert()`'s cooldown tiers (tighter near game time),
  bypassed immediately if price moves more than `PRICE_CHANGE_EPSILON`.
- **Persistence**: `storage.py` uses SQLAlchemy against either local SQLite (default, for
  local/VPS runs) or Postgres via `DATABASE_URL` (required for GitHub Actions, since runners don't
  persist disk between runs — see README for Supabase session-pooler setup, direct/URI connection
  is IPv6-only and unreachable from Actions runners).

`config.py` centralizes all config/secret loading: `Settings` wraps `config/settings.yaml` +
`config/bookmakers.yaml`, `Secrets.from_env()` wraps required env vars (`.env` locally, GitHub
Actions secrets in CI/prod). Nothing else in the codebase reads YAML or `os.environ` directly.

## Known v1 limitations (don't "fix" without asking)

- Devig is basic multiplicative, not Shin's method — intentional, fine for liquid two-way markets.
- Main markets only (h2h/spreads/totals), no player props — per initial scope.
- Auto-settlement only runs inside the 8x/day scan window, so a finished game can sit unsettled
  for a few hours; `/settle` exists as the manual escape hatch.
- `homepage_urls` in `config/bookmakers.yaml` (final deep-link fallback) are best-effort guesses,
  not verified against each book's actual current domain.
