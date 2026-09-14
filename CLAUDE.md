# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A +EV sports betting bot: finds mispriced lines at Ontario-licensed sportsbooks by comparing
them against Pinnacle's devigged "true" odds (or, for player props, a multi-book consensus —
see Architecture below), and alerts via Telegram. Runs on a schedule (VPS is the primary and, as
of 2026-09-13, only real deployment — see Persistence below), not as a long-lived service. It
does not place bets automatically.

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
python scripts/list_event_markets.py basketball_nba     # discover live player-prop coverage
python scripts/init_db.py   # create tables / seed bankroll
python scripts/migrate_add_participant.py  # one-time: adds Alert.participant to an existing DB
```

There is no lint/format command configured (no ruff/black/flake8 in dependencies).

**Local dev checkouts may already have a working `.env`** (real `ODDS_API_KEY`,
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) — check it (e.g. `grep -c '^ODDS_API_KEY=.\+' .env`,
never print the actual value) before assuming discovery/migration scripts can't be run live.
Getting this wrong once already cost a round of back-and-forth in this project's history.

## Architecture

`src/betbot/main.py::run()` is the single entry point, invoked on every scheduler tick
(`.github/workflows/betbot-scan.yml`, every 3 hours as a disabled-by-default backup; the VPS's
~20s poll loop is the primary deployment — see README). It does one thing unconditionally cheaply,
then up to two things gated by independent scan windows:

1. **Always**: poll Telegram `getUpdates` and dispatch `/placed`, `/skip`, `/settle`, `/bankroll`,
 `/status` via `commands.py` — free, so this stays responsive even between real scans.
2. **Gated by `scheduler.current_scan_window_key()` against `scheduling.scan_times_local`**
 (hourly, 10am-11pm ET in `config/settings.yaml`, DST-aware via `zoneinfo`, not a fixed UTC
 cron): auto-settle any `/placed` bets whose games finished (`settlement.py`, via `/scores`),
 then scan each configured sport (`config/settings.yaml` `sports:`) for +EV lines on main
 markets (h2h/spreads/totals) via `run_scan()`/`process_event()`.
3. **Gated by a separate, denser window against `props.scan_times_local`** (every 15 min,
 10am-11pm ET): scan sports with `player_markets` and/or `game_alt_markets` configured for
 +EV additional markets via `run_props_scan()`/`process_prop_event()`. Independent of #2 —
 a tick can run main markets, props, both, or neither. This exists because these markets
 aren't on the bulk `/odds` endpoint at all (see cost model below), a fundamentally
 different and pricier fetch shape. Redesigned 2026-09-13 from a twice-daily fixed
 schedule to proximity-based scanning after live-verifying these books open
 props/alternates close to kickoff (not gradually like main markets) — see
 `main.py::_events_within_pregame_window` and `config/settings.yaml`'s `props:
 pregame_window_hours`.

The main-market pipeline per sport, per event, per market (`main.py::process_event`):
`odds_client.py` (fetch) → `devig.py::devig()` (Pinnacle price → true probability) →
`ev.py` (true prob vs. Ontario book price → EV%) → `kelly.py` (quarter-Kelly stake sizing,
capped by `bankroll.max_stake_pct_of_bankroll`) → `storage.py` (upsert `Alert`, keyed on
event+market+outcome+point+bookmaker+participant) → `scheduler.should_alert()` (adaptive
cooldown gate) → `telegram.py` (send).

`main.py::process_prop_event` covers TWO different categories of additional markets that
share the same per-event fetch but devig differently:
- **`player_markets`** (currently MLB, NBA — **not** NFL, see below): Pinnacle doesn't
  reliably price player props, so `devig.py::devig_consensus()` averages no-vig true
  probabilities across several non-Ontario US books instead (`config/bookmakers.yaml`
  `consensus:` — FanDuel/DraftKings/BetMGM by default, requiring `min_books_required` of
  them to agree on a given player+line before it's trusted). Outcomes are grouped by
  `(participant, outcome_name, point)` instead of just `(outcome_name, point)`, since the
  same Over/Under name and line recur across different players within one market. Alerts
  use the higher `props.min_ev_pct` floor (5% vs. main markets' 2%), since a multi-soft-book
  average is a noisier reference than a genuinely sharp book.
- **`game_alt_markets`** (currently NFL, MLB — `alternate_spreads`, `alternate_totals`,
  `team_totals`, `alternate_team_totals`): game-level alternate lines that Pinnacle DOES
  price, added 2026-09-13. These devig against Pinnacle alone (`main.py::_consensus_true_probs`
  called with a single-book list and `min_books=1`) and use the main-markets `ev.min_ev_pct`
  floor (2%), not the props one — Pinnacle is just as sharp here as for h2h/spreads/totals.
  `alternate_spreads` needs its own grouping function, `_devig_spread_alternates`: unlike
  every other market in this bot, its two sides pair by **point negation** (Cowboys -3.5
  pairs with Giants +3.5), not matching point — verified live, not assumed. Don't try to
  route it through `_consensus_true_probs`'s `(description, point)` grouping.

Key invariants to preserve when touching this path:
- **Devig method**: `ev.devig_method` is `additive` (changed from `multiplicative`
  2026-09-13), which for exactly two outcomes is mathematically equivalent to Shin's
  method and corrects for favorite-longshot bias that multiplicative ignores — verified
  against the Shin-method literature, not assumed. Provably safe (can't go negative) only
  for exactly two outcomes; `devig.py::devig()` automatically falls back to multiplicative
  for 3+ outcomes (soccer's 3-way h2h) since that safety/equivalence proof doesn't extend
  there. Don't call `devig_additive()` directly for a 3-outcome market — it raises.
- **Cost model (main markets)**: real scans fetch odds with `bookmakers=` (built from
  `config/bookmakers.yaml` sharp + Ontario keys, ≤10 keys total) rather than `regions=`, because
  The Odds API prices every group of 10 bookmakers as 1 region-equivalent — half the cost of
  `regions=eu,ca` for the same data. `config/settings.yaml`'s `odds_api.regions` is kept only for
  `scripts/list_bookmakers.py`'s discovery use, not real scans. Don't reintroduce `regions=` on
  the real scan path without redoing this cost math.
- **Cost model (props/game-alt)**: these ("additional markets" per the docs) are rejected
  outright by the bulk `/odds` endpoint — they require `odds_client.py::get_event_odds()`,
  charged **per event**, not once per sport, and an empty response (no book has data at
  all) costs 0 regardless of markets/events requested. `run_props_scan()` bounds real spend
  with `props.pregame_window_hours` (the primary filter — only fetch events actually close
  to commence_time, since that's when these books post data) and
  `props.max_events_per_scan_per_sport` (hard safety ceiling). `player_markets:` and
  `game_alt_markets:` for one event are combined into a single `get_event_odds` call, not
  two. Don't add a sport/market to either list without re-checking the combined budget math
  in the comments above `config/settings.yaml`'s `props:` section.
- **Ontario allowlist is closed**: `config.py::Settings.is_ontario_book()` only matches
  `config/bookmakers.yaml`'s `known_keys` (plus `auto_match_suffixes`) — a book not listed is
  never checked even if the API returns it under the `ca` region. Adding a book means confirming
  its live key first via `scripts/list_bookmakers.py` (main markets) or
  `scripts/list_event_markets.py` (props), since keys occasionally change.
- **Verifying prop coverage needs ground truth, not a guessed market list**: an empty result
  from `get_event_odds` for a market you specified is ambiguous (wrong key? not posted yet?
  genuinely unsupported?). `odds_client.py::get_event_markets()` (wraps
  `/events/{id}/markets`, 1 credit/call) returns every market key a book has *actually*
  opened for an event — `scripts/list_event_markets.py` prints this by default. This is how
  NFL/NCAAF/soccer's "zero player props" conclusion below was actually proven, not inferred.
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
  `(event_id, market, outcome_name, point, bookmaker_key, participant)` — `participant` (the
  player name; `""` for team markets, never `NULL` — see the comment on the column, Postgres
  treats `NULL != NULL` in a unique constraint) is what stops two different players' identical
  Over/line/book from colliding into one alert. Once a user acts (`placed`/`skipped`/settled),
  that alert is never re-sent (`main.py::_upsert_and_maybe_notify`). Otherwise re-alerting is
  gated by `scheduler.should_alert()`'s cooldown tiers (tighter near game time), bypassed
  immediately if price moves more than `PRICE_CHANGE_EPSILON`. A DB created before the
  2026-09-13 props rollout needs `scripts/migrate_add_participant.py` run once (`Base.metadata.
  create_all` never alters an existing table).
- **Auto-settlement grades every market `/scores`' two final team scores can resolve**:
  `settlement.py::GRADABLE_MARKETS` is `h2h, spreads, totals` plus the four
  `game_alt_markets` keys (`alternate_spreads`, `alternate_totals`, `team_totals`,
  `alternate_team_totals`) — added 2026-09-13 alongside the manual-settlement reminder
  below. `alternate_spreads`/`alternate_totals` grade with the exact same math as
  `spreads`/`totals` (only the line-sourcing differs, not settlement); `team_totals`/
  `alternate_team_totals` grade off `Alert.participant` (the team name, stored the same
  slot player props use for the player name) rather than the combined game score. Player
  props (`player_*`, `batter_*`, `pitcher_*`, ...) are the only markets left ungradable —
  `/scores` never returns player-level box scores, so `/settle <id> win|loss|push` is the
  only path for those.
- **Manual-settlement reminder**: once `auto_settle_pending` sees a *non-gradable* market's
  game reach `completed` in `/scores`, it sends a one-time Telegram nudge toward
  `/settle <id> win|loss|push` and stamps `Alert.settlement_reminder_sent_at` so it isn't
  repeated every scan. That column also narrows the query itself: a placed bet on a
  gradable market is always re-checked until settled, but a non-gradable bet whose reminder
  has already fired drops out entirely (nothing more this function can do for it until the
  user acts), so it stops paying for a `/scores` call on its behalf. A DB from before this
  rollout needs `scripts/migrate_add_settlement_reminder.py` run once (same
  `create_all`-never-alters caveat as `migrate_add_participant.py`).
- **Persistence**: `storage.py` uses SQLAlchemy, and as of 2026-09-13 the only real deployment is
  local SQLite on the VPS (`DATABASE_URL` unset, default path). **Supabase/Postgres is no longer
  used** — dropped deliberately, don't reintroduce it or "fix" the DB back to Postgres. This
  means the `.github/workflows/betbot-scan.yml` GitHub Actions backup path (which historically
  needed Postgres specifically because Actions runners don't persist disk between runs) has no
  persistent DB to point at right now — treat it as not currently viable as a real backup until/
  unless a new persistent DB story is chosen for it; the VPS is the only place this bot actually
  runs. Two independent SQLite files exist: your local dev checkout's `data/betbot.db` (test data
  only) and the VPS's own `data/betbot.db` (the real one) — a migration script run locally does
  NOT touch the VPS's copy.

`config.py` centralizes all config/secret loading: `Settings` wraps `config/settings.yaml` +
`config/bookmakers.yaml`, `Secrets.from_env()` wraps required env vars (`.env` locally, GitHub
Actions secrets in CI/prod). Nothing else in the codebase reads YAML or `os.environ` directly.

## Known v1 limitations (don't "fix" without asking)

- Devig is `additive` (Shin-equivalent for exactly two outcomes) as of 2026-09-13, falling
  back to basic `multiplicative` only for 3+ outcome markets (soccer's 3-way h2h) — see the
  devig-method invariant above. No genuine N>2 Shin's method is implemented.
- Player props are limited to MLB and NBA (`config/settings.yaml` `sports:` `player_markets:`)
  and a modest starting market list per sport — each addition costs real per-event API budget
  (see the cost model above), so extending this is a config change plus a budget re-check, not
  a code change. **NFL was tried and dropped 2026-09-13**: live-verified via
  `scripts/list_event_markets.py` and a broader survey across NFL/NCAAF/CFL/5 soccer leagues
  that none of the 6 Ontario books post ANY player prop for those sports right now (confirmed
  even 1.6h before an NFL kickoff — not a "too early" timing artifact) — MLB was the only sport
  found with real Ontario-side coverage (`betmgm_ca_on`, `sportsinteraction_ca_on`). Don't
  re-add NFL/soccer to `player_markets:` without re-running that check; the per-event odds call
  still costs real credits whenever the consensus side has data even if the Ontario side is
  empty, so this isn't a free thing to leave on speculatively.
- The props "true" line (multi-book consensus of FanDuel/DraftKings/BetMGM) is a materially
  noisier reference than Pinnacle — expect a higher false-positive rate on props than main
  markets even behind the higher `props.min_ev_pct` floor.
- `game_alt_markets:` (added 2026-09-13) is limited to NFL and MLB, the only sports
  live-verified to have both Pinnacle AND Ontario coverage of `alternate_spreads`/
  `alternate_totals`/`team_totals`/`alternate_team_totals` — NCAAF has Pinnacle coverage but
  zero Ontario books carry it (excluded, same reasoning as NFL player props); CFL/soccer/MMA
  have neither. NFL's list excludes `alternate_team_totals` specifically because Pinnacle
  itself didn't have it on the checked game, not an Ontario-side gap.
- Additional-markets scanning (`props:`) is proximity-based (`pregame_window_hours`, default
  3h before commence_time), not a fixed daily schedule — these books post props/alternates
  close to kickoff, not gradually. A sport/event outside that window is skipped for free
  regardless of how the fixed `scan_times_local` slots line up.
- Auto-settlement only runs alongside a main-market scan, so a finished game can sit unsettled
  for up to an hour; `/settle` exists as the manual escape hatch (and is the *only* path for
  player props, which `/scores` can never auto-grade — see above).
- `homepage_urls` in `config/bookmakers.yaml` (final deep-link fallback) are best-effort guesses,
  not verified against each book's actual current domain.
