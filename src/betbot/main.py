"""Entry point: process any pending Telegram commands, auto-settle finished bets, then
scan configured sports/markets for +EV lines at Ontario books (vs. Pinnacle as the sharp
reference) and alert on them.

Run via: python -m betbot.main
Intended to be invoked on a schedule by .github/workflows/betbot-scan.yml (or a local cron / VPS
scheduler -- see README for both options).
"""
from __future__ import annotations

import datetime as dt
import logging
import os
from collections import defaultdict
from typing import Callable

from betbot import commands, settlement
from betbot.config import Secrets, Settings, settings
from betbot.devig import devig, devig_consensus
from betbot.ev import ev_pct
from betbot.kelly import stake_amount
from betbot.matching import (
    build_curve,
    is_fresh,
    select_reference,
    true_prob_at,
)
from betbot.odds_client import OddsApiClient, OddsApiError, OddsApiQuotaExceededError
from betbot.performance import build_report_lines
from betbot.scheduler import current_scan_window_key
from betbot.storage import Alert, Database, local_time_str
from betbot.telegram import TelegramClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("betbot.main")

MARKET_LABELS = {
    "h2h": "ML", "spreads": "Spread", "totals": "Total",
    # Player props (config `sports:` entries' `player_markets:`) -- see process_prop_event.
    "player_pass_yds": "Pass Yds", "player_pass_tds": "Pass TDs",
    "player_rush_yds": "Rush Yds", "player_receptions": "Receptions",
    "player_reception_yds": "Reception Yds", "player_anytime_td": "Anytime TD",
    "player_points": "Points", "player_rebounds": "Rebounds",
    "player_assists": "Assists", "player_threes": "Threes",
    "player_points_rebounds_assists": "Pts+Reb+Ast", "player_double_double": "Double-Double",
    "batter_hits": "Hits", "batter_rbis": "RBIs", "batter_total_bases": "Total Bases",
    "batter_doubles": "Doubles", "batter_singles": "Singles", "batter_runs_scored": "Runs",
    "batter_hits_runs_rbis": "Hits+Runs+RBIs", "batter_stolen_bases": "Stolen Bases",
    "pitcher_strikeouts": "Strikeouts", "pitcher_outs": "Outs Recorded",
    "pitcher_earned_runs": "Earned Runs", "pitcher_hits_allowed": "Hits Allowed",
    # Game-level alternate markets (config `sports:` entries' `game_alt_markets:`) --
    # devigged against Pinnacle, not the player-props consensus. See process_prop_event.
    "alternate_spreads": "Alt Spread", "alternate_totals": "Alt Total",
    "team_totals": "Team Total", "alternate_team_totals": "Alt Team Total",
}


def extract_outcomes(
    market: dict, book_bm: dict
) -> list[tuple[str, float | None, float, str | None, str | None]]:
    """Returns (name, point, price, description, deep_link) per outcome. `description`
    carries the player name for prop markets ("additional markets" per the docs); it's
    absent (None) on the featured markets (h2h/spreads/totals) used until now. deep_link
    prefers the most specific link The Odds API offers (outcome > market > bookmaker/event),
    falling back to None if `includeLinks=true` didn't return one for this book."""
    bm_link = book_bm.get("link")
    market_link = market.get("link") or bm_link
    return [
        (
            o["name"], o.get("point"), float(o["price"]), o.get("description"),
            o.get("link") or market_link,
        )
        for o in market.get("outcomes", [])
    ]


def find_market(bookmaker: dict, market_key: str) -> dict | None:
    for m in bookmaker.get("markets", []):
        if m["key"] == market_key:
            return m
    return None


def process_event(
    db: Database,
    telegram: TelegramClient,
    event: dict,
    sport_key: str,
    markets: list[str],
    bankroll: float,
    now: dt.datetime,
) -> int:
    """Returns number of alerts sent for this event."""
    commence_time = dt.datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))
    hours_to_commence = (commence_time - now).total_seconds() / 3600.0
    if hours_to_commence < 0 or hours_to_commence > settings.max_hours_ahead:
        return 0

    bookmakers = event.get("bookmakers", [])
    ontario_bms = [bm for bm in bookmakers if settings.is_ontario_book(bm["key"])]
    if not ontario_bms:
        return 0

    alerts_sent = 0
    for market_key in markets:
        # Reference true-probability curve: Pinnacle if present/fresh/has this market,
        # else a median basket of the consensus books (see betbot.matching.select_reference)
        # -- added 2026-09-14 after live-verifying Pinnacle can go fully dark (scraped from
        # Pinnacle's own public website per The Odds API's docs, so gaps are expected).
        sharp_bm = next((bm for bm in bookmakers if bm["key"] in settings.sharp_book_keys), None)
        sharp_market = find_market(sharp_bm, market_key) if sharp_bm else None
        sharp_outcomes = (
            [(name, point, price) for name, point, price, _, _ in extract_outcomes(sharp_market, sharp_bm)]
            if sharp_market else None
        )
        basket_candidates = []
        for bm in bookmakers:
            if bm["key"] not in settings.consensus_book_keys:
                continue
            bm_market = find_market(bm, market_key)
            if not bm_market:
                continue
            basket_candidates.append(
                (bm["key"], [(name, point, price) for name, point, price, _, _ in extract_outcomes(bm_market, bm)])
            )
        selection = select_reference(
            sharp_bm, sharp_outcomes, basket_candidates, settings.devig_method,
            settings.min_consensus_books, now, settings.sharp_max_staleness_minutes,
        )
        if selection is None:
            continue
        curve, sharp_book_key = selection

        # Pick only the single best-priced Ontario book per (outcome, point) instead of
        # alerting on every book that clears the EV threshold -- otherwise the same bet
        # showing value at multiple books each sends its own alert with a slightly
        # different EV%, which reads as duplicate notifications for one decision. The best
        # price is also strictly the right recommendation anyway, so this loses nothing.
        best_by_outcome: dict[tuple[str, float | None], tuple[str, float, str | None]] = {}
        for book_bm in ontario_bms:
            book_market = find_market(book_bm, market_key)
            if not book_market:
                continue
            for name, point, price, _, link in extract_outcomes(book_market, book_bm):
                link = link or settings.homepage_url(book_bm["key"])
                key = (name, point)
                current = best_by_outcome.get(key)
                if current is None or price > current[1]:
                    best_by_outcome[key] = (book_bm["key"], price, link)

        for (name, point), (bookmaker_key, price, link) in best_by_outcome.items():
            true_prob = true_prob_at(curve.get(name, []), point)
            if true_prob is None:
                continue  # not bracketed by any point the reference actually observed -- skip
            if true_prob < settings.min_true_prob:
                continue  # too much of a longshot -- high variance, devig error grows at the tails

            ev = ev_pct(true_prob, price)
            if ev < settings.min_ev_pct:
                continue

            stake = stake_amount(
                true_prob=true_prob,
                decimal_odds=price,
                bankroll=bankroll,
                kelly_fraction=settings.kelly_fraction,
                max_stake_pct=settings.max_stake_pct,
                min_stake=settings.min_stake,
            )
            if stake <= 0:
                continue

            alerts_sent += _upsert_and_maybe_notify(
                db=db,
                telegram=telegram,
                event=event,
                sport_key=sport_key,
                market_key=market_key,
                outcome_name=name,
                point=point,
                bookmaker_key=bookmaker_key,
                price=price,
                deep_link=link,
                true_prob=true_prob,
                ev=ev,
                stake=stake,
                commence_time=commence_time,
                now=now,
                sharp_book_key=sharp_book_key,
            )
    return alerts_sent


def _upsert_and_maybe_notify(
    db: Database,
    telegram: TelegramClient,
    event: dict,
    sport_key: str,
    market_key: str,
    outcome_name: str,
    point: float | None,
    bookmaker_key: str,
    price: float,
    deep_link: str | None,
    true_prob: float,
    ev: float,
    stake: float,
    commence_time: dt.datetime,
    now: dt.datetime,
    sharp_book_key: str,
    participant: str = "",
) -> int:
    """Persist a still-+EV candidate and maybe Telegram-notify.

    The first time an identity clears the EV floor it is stored as pending_confirm and
    not sent. confirm_pending re-fetches it after ev.confirm_delay_minutes and only then
    pings, if it's still +EV — a price that existed for one scrape and vanished doesn't
    reach you. confirm_delay_minutes of 0 sends on this first sighting.

    A line already notified (and not /placed, /skip'd, or settled) re-pings on every
    later scan that still finds it +EV. Lines that fall below the EV floor never reach
    this function, so they go quiet without being marked skipped."""
    delay = settings.confirm_delay_minutes
    with db.session() as s:
        existing = (
            s.query(Alert)
            .filter_by(
                event_id=event["id"],
                market=market_key,
                outcome_name=outcome_name,
                point=point,
                bookmaker_key=bookmaker_key,
                participant=participant,
            )
            .one_or_none()
        )

        if existing is None:
            alert = Alert(
                event_id=event["id"],
                sport_key=sport_key,
                commence_time=commence_time,
                home_team=event["home_team"],
                away_team=event["away_team"],
                market=market_key,
                outcome_name=outcome_name,
                point=point,
                participant=participant,
                bookmaker_key=bookmaker_key,
                book_odds=price,
                deep_link=deep_link,
                sharp_book_key=sharp_book_key,
                true_prob=true_prob,
                ev_pct=ev,
                recommended_stake=stake,
                status="pending_confirm" if delay > 0 else "new",
                first_seen_at=now,
            )
            s.add(alert)
            s.flush()  # ensure alert.id is populated for the hold log
            if delay > 0:
                logger.info(
                    "Holding alert %s for a %.0f min recheck: %s %s @ %s",
                    alert.id, delay, market_key, outcome_name, bookmaker_key,
                )
                return 0
        else:
            if existing.status in (
                "placed", "skipped", "settled_win", "settled_loss", "settled_push",
            ):
                return 0  # user already acted on this -- don't re-alert
            if existing.status == "pending_confirm" and delay > 0:
                seen = existing.first_seen_at or now
                age_minutes = (now - seen).total_seconds() / 60.0
                # A different Ontario number has to survive its own wait. Once the
                # wait is already over, this snapshot is the recheck — alert it as-is.
                if abs(existing.book_odds - price) > 1e-6 and age_minutes < delay:
                    existing.first_seen_at = now
                    age_minutes = 0.0
                if age_minutes < delay:
                    existing.book_odds = price
                    existing.deep_link = deep_link
                    existing.true_prob = true_prob
                    existing.ev_pct = ev
                    existing.recommended_stake = stake
                    existing.sharp_book_key = sharp_book_key
                    return 0
            existing.book_odds = price
            existing.deep_link = deep_link
            existing.true_prob = true_prob
            existing.ev_pct = ev
            existing.recommended_stake = stake
            existing.sharp_book_key = sharp_book_key
            alert = existing

        s.flush()  # ensure alert.id is populated for new rows
        _send_alert_message(telegram, alert)
        alert.status = "notified"
        alert.last_alerted_at = now
        return 1


def _send_alert_message(telegram: TelegramClient, alert: Alert) -> None:
    """What to bet, at what odds/book/league, for how much, what we think it's really
    worth and how we priced that, and the two commands to act on it."""
    label = MARKET_LABELS.get(alert.market, alert.market)
    book = settings.display_name(alert.bookmaker_key)

    lines = [
        f"*+{alert.ev_pct:.1f}% EV* · {alert.league_display()} {label}: "
        f"{alert.outcome_display()} @ {alert.book_odds_display()} ({book})",
        f"{alert.away_team} @ {alert.home_team} · {local_time_str(alert.commence_time, settings.timezone)} · "
        f"${alert.recommended_stake:,.2f}",
        f"True odds: {alert.true_odds_display()} (via {settings.method_display(alert.sharp_book_key)})",
    ]
    if alert.deep_link:
        lines.append(f"[Bet now]({alert.deep_link})")
    lines.append(f"`/placed {alert.id}`  `/skip {alert.id}`")
    telegram.send_message("\n".join(lines))


def run_scan(db: Database, settings: Settings, telegram: TelegramClient,
             odds_client: OddsApiClient, bankroll: float, now: dt.datetime) -> int:
    """Fetch odds for every configured sport and alert on +EV lines. Returns the number of
    alerts sent. Shared by the scheduled scan window (step 5 below) and the on-demand
    `/scan` Telegram command -- callers own their own quota/dedup gating around this."""
    window_from = now
    window_to = now + dt.timedelta(hours=settings.max_hours_ahead)
    total_alerts = 0
    for sport in settings.sports:
        sport_key, markets = sport["key"], sport["markets"]

        # Free precheck (an empty /odds response also costs 0, per the docs, but this
        # skips an unnecessary round-trip/rate-limit hit for sports with nothing upcoming).
        try:
            upcoming = odds_client.get_events(sport_key, window_from, window_to)
        except OddsApiQuotaExceededError:
            raise  # let the quota gate in run() handle this, not the per-sport skip below
        except OddsApiError:
            logger.exception("Failed to fetch events for %s", sport_key)
            continue
        if not upcoming:
            logger.info("No upcoming %s events in window -- skipping odds fetch.", sport_key)
            continue

        try:
            events = odds_client.get_odds(
                sport_key,
                markets,
                bookmakers=settings.scan_bookmakers,
                commence_time_from=window_from,
                commence_time_to=window_to,
                include_links=True,
            )
        except OddsApiQuotaExceededError:
            raise  # let the quota gate in run() handle this, not the per-sport skip below
        except OddsApiError:
            logger.exception("Failed to fetch odds for %s", sport_key)
            continue
        for event in events:
            total_alerts += process_event(
                db, telegram, event, sport_key, markets, bankroll, now
            )
    return total_alerts


def _consensus_true_probs(
    consensus_bms: list[dict], market_key: str, min_books: int, devig_method: str
) -> dict[tuple[str | None, str, float | None], tuple[float, str]]:
    """Groups a book's outcomes by (participant, point) -- the full set of outcomes for
    one line (Over/Under, or Yes/No) -- then devigs each contributing book's own price set
    independently (a book's vig only reflects its own book) before averaging (mean) across
    books via devig_consensus. Player-props-only (`consensus_bms` = several non-Ontario US
    books) -- game-level alternate markets use betbot.matching.select_reference/true_prob_at.
    Kept separate deliberately: Pinnacle never prices player props at all, so there's no
    fresh-vs-stale distinction or fallback tier to apply here, and mean (not median) remains
    the intended aggregate for this reference. `alternate_spreads` never fit this grouping
    (see _devig_spread_alternates) since its two sides pair by point negation, not equality.

    Returns {(participant, outcome_name, point): (true_prob, "book1,book2")} -- keyed by
    outcome_name too so callers can look up whichever side an Ontario book is offering.
    Only books quoting every side of a given line contribute to that line's average (a
    book missing one side can't be devigged), independent of book-agreement per market
    overall -- one book can be a full contributor for one player's line and absent from
    another's in the same response.
    """
    grouped: dict[tuple[str | None, float | None], dict[str, dict[str, float]]] = {}
    for bm in consensus_bms:
        market = find_market(bm, market_key)
        if not market:
            continue
        for name, point, price, description, _ in extract_outcomes(market, bm):
            grouped.setdefault((description, point), {}).setdefault(bm["key"], {})[name] = price

    lookup: dict[tuple[str | None, str, float | None], tuple[float, str]] = {}
    for (description, point), by_book in grouped.items():
        names_order = sorted({name for prices in by_book.values() for name in prices})
        per_book_odds = {
            book: [prices[name] for name in names_order]
            for book, prices in by_book.items()
            if set(names_order) <= set(prices)
        }
        try:
            true_probs = devig_consensus(per_book_odds, min_books=min_books, method=devig_method)
        except ValueError:
            continue
        if true_probs is None:
            continue
        contributing = ",".join(sorted(per_book_odds))
        for name, prob in zip(names_order, true_probs):
            lookup[(description, name, point)] = (prob, contributing)
    return lookup


def _consensus_prop_lookup(
    consensus_bms: list[dict], market_key: str, min_books: int, devig_method: str
) -> Callable[[str | None, str, float | None], tuple[float, str] | None]:
    """Player-prop true-prob lookup with point interpolation. Builds a per-(player, side)
    curve from the exact-point consensus probs, then true_prob_at -- so Ontario 24.5 can
    still resolve when consensus books only quote 24.0 and 25.0. Never extrapolates."""
    exact = _consensus_true_probs(consensus_bms, market_key, min_books, devig_method)
    curves: dict[tuple[str | None, str], list[tuple[float | None, float]]] = {}
    labels: dict[tuple[str | None, str], set[str]] = defaultdict(set)
    for (description, name, point), (prob, contributing) in exact.items():
        key = (description, name)
        curves.setdefault(key, []).append((point, prob))
        labels[key].update(contributing.split(","))
    for key in curves:
        curves[key].sort(key=lambda x: (x[0] is not None, x[0] if x[0] is not None else 0.0))

    def lookup(
        description: str | None, name: str, point: float | None
    ) -> tuple[float, str] | None:
        key = (description, name)
        curve = curves.get(key)
        if not curve:
            return None
        true_prob = true_prob_at(curve, point)
        if true_prob is None:
            return None
        return true_prob, ",".join(sorted(labels[key]))

    return lookup


def _devig_spread_alternates(
    sharp_bm: dict, market_key: str, devig_method: str
) -> dict[tuple[str, float], float]:
    """`alternate_spreads` pairs by POINT NEGATION between the two team names, not matching
    point -- e.g. Cowboys at -3.5 pairs with Giants at +3.5 (verified on live NFL data:
    every one of Dallas's alternate points had an exact negated counterpart in New York's).
    This doesn't fit _consensus_true_probs's (description, point) grouping -- there's no
    `description` field on these outcomes, and the two paired outcomes have DIFFERENT point
    values, not equal ones -- so it needs its own grouping: bucket by abs(point), expect
    exactly 2 outcomes per bucket (one per team), devig the pair, and key the result by each
    outcome's own REAL signed point, not the magnitude -- collapsing -3.5/+3.5 to the same
    key would silently corrupt the lookup.

    `sharp_bm` is a single sharp book (Pinnacle) -- like other game-level alternate
    markets, this devigs against Pinnacle alone, not a multi-book consensus.
    Returns {(team_name, signed_point): true_prob}.
    """
    market = find_market(sharp_bm, market_key)
    if not market:
        return {}

    by_magnitude: dict[float, dict[str, tuple[float, float]]] = {}
    for name, point, price, _, _ in extract_outcomes(market, sharp_bm):
        if point is None:
            continue
        by_magnitude.setdefault(abs(point), {})[name] = (price, point)

    lookup: dict[tuple[str, float], float] = {}
    for teams in by_magnitude.values():
        if len(teams) != 2:
            continue  # not a clean 2-team pair at this magnitude -- skip rather than guess
        names = sorted(teams)
        prices = [teams[n][0] for n in names]
        try:
            true_probs = devig(prices, method=devig_method)
        except ValueError:
            continue
        for name, prob in zip(names, true_probs):
            lookup[(name, teams[name][1])] = prob
    return lookup


def _spread_alt_points_from_bm(
    bm: dict, market_key: str, devig_method: str
) -> dict[tuple[str | None, str], list[tuple[float | None, float]]]:
    """Convert _devig_spread_alternates flat lookup into a (None, team)-keyed curve dict
    suitable for build_curve / _curve_lookup."""
    raw = _devig_spread_alternates(bm, market_key, devig_method)
    curve: dict[tuple[str | None, str], list[tuple[float | None, float]]] = defaultdict(list)
    for (name, point), prob in raw.items():
        curve[(None, name)].append((point, prob))
    for key in curve:
        curve[key].sort(key=lambda x: (x[0] is not None, x[0] if x[0] is not None else 0.0))
    return dict(curve)


def _alert_on_matched_lines(
    db: Database,
    telegram: TelegramClient,
    event: dict,
    sport_key: str,
    market_key: str,
    ontario_bms: list[dict],
    true_prob_lookup: Callable[[str | None, str, float | None], tuple[float, str] | None],
    min_ev_pct: float,
    bankroll: float,
    commence_time: dt.datetime,
    now: dt.datetime,
) -> int:
    """Shared best-price-selection + alerting for one already-devigged additional market --
    used for both player props (interpolating consensus lookup, props.min_ev_pct floor) and
    game-level alternates (Pinnacle-or-basket curve lookup with interpolation, ev.min_ev_pct
    floor). `true_prob_lookup(description, name, point) -> (true_prob, contributing_label) |
    None` abstracts over that difference."""
    # Same "one alert per decision" best-price selection as process_event, keyed by
    # (participant, outcome, point) instead of just (outcome, point).
    best_by_outcome: dict[
        tuple[str | None, str, float | None], tuple[str, float, str | None]
    ] = {}
    for book_bm in ontario_bms:
        book_market = find_market(book_bm, market_key)
        if not book_market:
            continue
        for name, point, price, description, link in extract_outcomes(book_market, book_bm):
            link = link or settings.homepage_url(book_bm["key"])
            key = (description, name, point)
            current = best_by_outcome.get(key)
            if current is None or price > current[1]:
                best_by_outcome[key] = (book_bm["key"], price, link)

    alerts_sent = 0
    for (description, name, point), (bookmaker_key, price, link) in best_by_outcome.items():
        hit = true_prob_lookup(description, name, point)
        if hit is None:
            continue  # not bracketed by any point the reference actually observed -- skip
        true_prob, contributing_books = hit
        if true_prob < settings.min_true_prob:
            continue  # too much of a longshot -- high variance, devig error grows at the tails

        ev = ev_pct(true_prob, price)
        if ev < min_ev_pct:
            continue

        stake = stake_amount(
            true_prob=true_prob,
            decimal_odds=price,
            bankroll=bankroll,
            kelly_fraction=settings.kelly_fraction,
            max_stake_pct=settings.max_stake_pct,
            min_stake=settings.min_stake,
        )
        if stake <= 0:
            continue

        alerts_sent += _upsert_and_maybe_notify(
            db=db,
            telegram=telegram,
            event=event,
            sport_key=sport_key,
            market_key=market_key,
            outcome_name=name,
            point=point,
            bookmaker_key=bookmaker_key,
            price=price,
            deep_link=link,
            true_prob=true_prob,
            ev=ev,
            stake=stake,
            commence_time=commence_time,
            now=now,
            sharp_book_key=contributing_books,
            participant=description or "",
        )
    return alerts_sent


def process_prop_event(
    db: Database,
    telegram: TelegramClient,
    event: dict,
    sport_key: str,
    player_markets: list[str],
    bankroll: float,
    now: dt.datetime,
    game_alt_markets: list[str] | None = None,
) -> int:
    """Additional-markets counterpart to process_event, covering two different categories
    that share the same per-event fetch but devig differently:

    - `player_markets`: Pinnacle doesn't reliably price player props, so there's no single
      sharp book -- the "true" line is a multi-book average of non-Ontario US books'
      no-vig probabilities (config/bookmakers.yaml `consensus:`, via _consensus_prop_lookup),
      with point interpolation across consensus lines, gated behind the higher
      `props.min_ev_pct` floor since that reference is noisier than a genuinely sharp book.
    - `game_alt_markets`: game-level alternate lines (alternate_spreads, alternate_totals,
      team_totals, alternate_team_totals) that Pinnacle DOES price -- these use the same
      Pinnacle-or-median-basket-fallback selection and point interpolation as main markets
      (betbot.matching.select_reference/true_prob_at, with per-line devig for totals-style
      ladders; alternate_spreads uses point-negation pairing and now also accepts a
      consensus basket when Pinnacle is missing/stale), and the main-markets `ev.min_ev_pct`
      floor, not the props one.

    `event` is a single-event response from OddsApiClient.get_event_odds (already scoped to
    the combined market list), not the bulk /odds shape process_event consumes.
    """
    game_alt_markets = game_alt_markets or []
    commence_time = dt.datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))
    hours_to_commence = (commence_time - now).total_seconds() / 3600.0
    if hours_to_commence < 0 or hours_to_commence > settings.props_max_hours_ahead:
        return 0

    bookmakers = event.get("bookmakers", [])
    ontario_bms = [bm for bm in bookmakers if settings.is_ontario_book(bm["key"])]
    if not ontario_bms:
        return 0

    alerts_sent = 0

    consensus_bms = [bm for bm in bookmakers if bm["key"] in settings.consensus_book_keys]
    if player_markets and len(consensus_bms) >= settings.min_consensus_books:
        for market_key in player_markets:
            sharp_lookup = _consensus_prop_lookup(
                consensus_bms, market_key, settings.min_consensus_books, settings.devig_method
            )
            alerts_sent += _alert_on_matched_lines(
                db, telegram, event, sport_key, market_key, ontario_bms, sharp_lookup,
                settings.props_min_ev_pct, bankroll, commence_time, now,
            )

    pinnacle_bm = next((bm for bm in bookmakers if bm["key"] in settings.sharp_book_keys), None)
    if game_alt_markets:
        for market_key in game_alt_markets:
            if market_key == "alternate_spreads":
                # Point-negation pairing (Cowboys -3.5 / Giants +3.5), not equal-point --
                # doesn't fit select_reference's per-book-outcome shape. Prefer fresh
                # Pinnacle; fall back to a median basket of consensus books that carry a
                # compatible 2-team-per-magnitude ladder; merge basket anchors onto Pinnacle
                # for half-point interpolation.
                lookup = _select_spread_alt_lookup(
                    pinnacle_bm, consensus_bms, market_key, now,
                )
                if lookup is None:
                    continue
            else:
                sharp_market = find_market(pinnacle_bm, market_key) if pinnacle_bm else None
                sharp_outcomes = (
                    [
                        ((description, name), point, price)
                        for name, point, price, description, _ in extract_outcomes(sharp_market, pinnacle_bm)
                    ]
                    if sharp_market else None
                )
                basket_candidates = []
                for bm in consensus_bms:
                    bm_market = find_market(bm, market_key)
                    if not bm_market:
                        continue
                    basket_candidates.append((
                        bm["key"],
                        [
                            ((description, name), point, price)
                            for name, point, price, description, _ in extract_outcomes(bm_market, bm)
                        ],
                    ))
                selection = select_reference(
                    pinnacle_bm, sharp_outcomes, basket_candidates, settings.devig_method,
                    settings.min_consensus_books, now, settings.sharp_max_staleness_minutes,
                    pair_by_line=True,
                )
                if selection is None:
                    continue
                curve, label = selection
                lookup = _curve_lookup(curve, label)

            alerts_sent += _alert_on_matched_lines(
                db, telegram, event, sport_key, market_key, ontario_bms, lookup,
                settings.min_ev_pct, bankroll, commence_time, now,
            )

    return alerts_sent


def _select_spread_alt_lookup(
    pinnacle_bm: dict | None,
    consensus_bms: list[dict],
    market_key: str,
    now: dt.datetime,
) -> Callable[[str | None, str, float | None], tuple[float, str] | None] | None:
    """Build an interpolating lookup for alternate_spreads from Pinnacle and/or consensus."""
    basket_keys: list[str] = []
    basket_points: list[dict] = []
    for bm in consensus_bms:
        points = _spread_alt_points_from_bm(bm, market_key, settings.devig_method)
        if points:
            basket_keys.append(bm["key"])
            basket_points.append(points)
    basket_curve = (
        build_curve(basket_points, aggregate="median")
        if len(basket_keys) >= settings.min_consensus_books
        else None
    )

    pinnacle_ok = (
        pinnacle_bm is not None
        and is_fresh(pinnacle_bm, now, settings.sharp_max_staleness_minutes)
    )
    if pinnacle_ok:
        sharp_curve = _spread_alt_points_from_bm(pinnacle_bm, market_key, settings.devig_method)
        if sharp_curve:
            # Interpolate only within Pinnacle's own ladder -- do not splice soft-book
            # points in as anchors (that inverted favorite alt-spread true probs).
            return _curve_lookup(sharp_curve, "pinnacle")

    if basket_curve is None:
        return None
    return _curve_lookup(basket_curve, ",".join(sorted(basket_keys)))


def _curve_lookup(
    curve: dict[tuple[str | None, str], list[tuple[float | None, float]]], label: str
) -> Callable[[str | None, str, float | None], tuple[float, str] | None]:
    """Adapts a (description, name)-keyed probability curve into the
    `true_prob_lookup(description, name, point)` shape _alert_on_matched_lines expects,
    interpolating via betbot.matching.true_prob_at instead of requiring an exact point."""
    def lookup(description: str | None, name: str, point: float | None) -> tuple[float, str] | None:
        prob = true_prob_at(curve.get((description, name), []), point)
        return None if prob is None else (prob, label)
    return lookup


def _events_within_pregame_window(
    events: list[dict], now: dt.datetime, window_hours: float
) -> list[dict]:
    """Only games actually close to starting -- see config/settings.yaml `props:
    pregame_window_hours` for why: these Ontario/consensus books open player props and
    game-level alternates close to kickoff, not gradually the way main markets build up
    over days (live-verified 2026-09-13: games 23-25h out had zero props from any book,
    consensus included, while a game <0.2h out had full coverage). A twice-a-day fixed
    schedule reliably misses that narrow per-game window; this proximity filter is what
    replaced it."""
    result = []
    for event in events:
        commence_time = dt.datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))
        hours_to_commence = (commence_time - now).total_seconds() / 3600.0
        if 0 <= hours_to_commence <= window_hours:
            result.append(event)
    return result


def run_props_scan(db: Database, settings: Settings, telegram: TelegramClient,
                    odds_client: OddsApiClient, bankroll: float, now: dt.datetime) -> int:
    """Additional-markets counterpart to run_scan (player props + game-level alternates --
    see process_prop_event). Fetched one event at a time via the per-event odds endpoint
    (get_event_odds) since these aren't available on the bulk /odds endpoint -- a
    different, more expensive cost shape (see config/settings.yaml `props:` for the cost
    budgeting this is sized against). Only sports with `player_markets` and/or
    `game_alt_markets` configured (config/settings.yaml `sports:`) are scanned; candidate
    events are filtered to `props.pregame_window_hours` of commence_time
    (_events_within_pregame_window) -- the real cost/relevance control now -- then capped
    at `props.max_events_per_scan_per_sport` as a hard safety ceiling, nearest first."""
    window_from = now
    window_to = now + dt.timedelta(hours=settings.props_max_hours_ahead)
    total_alerts = 0
    for sport in settings.sports:
        player_markets = sport.get("player_markets") or []
        game_alt_markets = sport.get("game_alt_markets") or []
        if not player_markets and not game_alt_markets:
            continue
        sport_key = sport["key"]
        # No overlap expected between the two lists, but de-dup defensively so a market
        # accidentally listed in both isn't requested (and charged) twice in one call.
        combined_markets = list(dict.fromkeys(player_markets + game_alt_markets))

        try:
            upcoming = odds_client.get_events(sport_key, window_from, window_to)
        except OddsApiQuotaExceededError:
            raise  # let the quota gate in run() handle this, not the per-sport skip below
        except OddsApiError:
            logger.exception("Failed to fetch events for %s (props)", sport_key)
            continue
        if not upcoming:
            logger.info("No upcoming %s events in props window -- skipping.", sport_key)
            continue

        candidates = _events_within_pregame_window(upcoming, now, settings.props_pregame_window_hours)
        candidates.sort(key=lambda e: e["commence_time"])
        for event_stub in candidates[: settings.props_max_events_per_scan_per_sport]:
            try:
                event = odds_client.get_event_odds(
                    sport_key,
                    event_stub["id"],
                    combined_markets,
                    bookmakers=settings.props_bookmakers,
                    include_links=True,
                )
            except OddsApiQuotaExceededError:
                raise  # let the quota gate in run() handle this, not the per-event skip below
            except OddsApiError:
                logger.exception(
                    "Failed to fetch prop odds for %s event %s", sport_key, event_stub["id"]
                )
                continue
            total_alerts += process_prop_event(
                db, telegram, event, sport_key, player_markets, bankroll, now,
                game_alt_markets=game_alt_markets,
            )
    return total_alerts


# kv_state keys used by the quota-exhaustion gate below. The Odds API's quota resets
# monthly but no response exposes the reset date (see the "Quota baseline" note in
# CLAUDE.md), so there's no way to compute a resume time up front -- instead we just stop
# spending credits and periodically retry a free call until it reports headroom again.
QUOTA_EXHAUSTED_KV_KEY = "quota_exhausted"
QUOTA_EXHAUSTED_AT_KV_KEY = "quota_exhausted_at"


def _mark_quota_exhausted(db: Database, telegram: TelegramClient) -> None:
    """Called wherever a paid Odds API call raises OddsApiQuotaExceededError (see run(),
    and commands._cmd_scan for the manual /scan path). Persists the paused state so every
    future tick's quota gate (see run()) skips paid calls until _quota_available() confirms
    credits are back, and sends a one-time Telegram alert on the transition into paused."""
    already_exhausted = db.get_kv(QUOTA_EXHAUSTED_KV_KEY) == "true"
    db.set_kv(QUOTA_EXHAUSTED_KV_KEY, "true")
    if already_exhausted:
        return
    db.set_kv(QUOTA_EXHAUSTED_AT_KV_KEY, dt.datetime.now(dt.timezone.utc).isoformat())
    telegram.send_message(
        "\U0001F6AB *Odds API quota exhausted* for this billing period -- pausing all "
        "scans (main markets, props, and auto-settlement) until it resets.\n"
        "I'll keep checking for free in the background and resume automatically; "
        "`/quota` still works any time to check manually."
    )


def _quota_available(db: Database, odds_client: OddsApiClient, telegram: TelegramClient) -> bool:
    """Free recheck of whether credits are available again -- piggybacks on
    OddsApiClient.get_quota()'s /sports call, which the docs confirm costs 0 regardless of
    quota state, so polling this while paused never itself spends anything. Only meant to
    be called when QUOTA_EXHAUSTED_KV_KEY is already set."""
    try:
        quota = odds_client.get_quota()
    except OddsApiError:
        logger.exception("Quota recheck failed -- staying paused.")
        return False
    remaining = quota.get("remaining")
    try:
        available = int(remaining) > 0
    except (TypeError, ValueError):
        available = False
    if not available:
        return False
    db.set_kv(QUOTA_EXHAUSTED_KV_KEY, "false")
    telegram.send_message(
        f"✅ *Odds API quota available again* (remaining: {remaining}) -- resuming scans."
    )
    return True


# Featured markets live on the bulk /odds endpoint. Everything else (player props,
# alternate lines) is an additional market and has to be re-fetched per event.
_MAIN_MARKETS = frozenset({"h2h", "spreads", "totals"})
_GAME_ALT_MARKETS = frozenset({
    "alternate_spreads", "alternate_totals", "team_totals", "alternate_team_totals",
})
_CONFIRM_BACKOFF_KEY = "confirm_retry_after"
_CONFIRM_BACKOFF_MINUTES = 2


def scan_followup_message(
    sent: int, held: int, delay_minutes: float, *, manual: bool = False
) -> str | None:
    """What to tell the user after a scan, besides the alerts themselves.

    A scheduled scan that already sent alerts stays quiet (the alerts are the message)
    unless it also held new lines for a recheck. A manual /scan always gets a reply.
    """
    prefix = "Manual scan complete" if manual else "Scan complete"
    if held and delay_minutes > 0:
        noun = "line" if held == 1 else "lines"
        hold = (
            f"{held} {noun} look +EV. "
            f"Rechecking in {delay_minutes:g} min before alerting, "
            f"so a price that vanishes immediately won't ping you."
        )
        if sent:
            return f"{prefix}: {sent} alert(s) sent above. {hold}"
        return f"{prefix}: {hold}"
    if sent:
        return f"{prefix}: {sent} alert(s) sent above." if manual else None
    return f"{prefix}: no new +EV opportunities right now."


def count_pending_since(db: Database, since: dt.datetime) -> int:
    """How many lines this scan held for a recheck (first seen at or after `since`).

    Compared in Python, not SQL: SQLite drops timezone info, and a SQL >= against an
    aware datetime doesn't round-trip (see storage.AwareDateTime)."""
    with db.session() as s:
        rows = s.query(Alert).filter(Alert.status == "pending_confirm").all()
        return sum(
            1 for row in rows
            if row.first_seen_at is not None and row.first_seen_at >= since
        )


def _expire_old_pending(db: Database, now: dt.datetime) -> None:
    max_age = dt.timedelta(minutes=settings.confirm_max_age_minutes)
    with db.session() as s:
        rows = s.query(Alert).filter(Alert.status == "pending_confirm").all()
        for row in rows:
            seen = row.first_seen_at
            if seen is None or now - seen > max_age:
                logger.info(
                    "Expiring unconfirmed alert %s — held longer than %.0f min.",
                    row.id, settings.confirm_max_age_minutes,
                )
                s.delete(row)


def _drop_unconfirmed(db: Database, alert_ids: list[int]) -> None:
    """Remove holds whose recheck no longer finds them +EV. Deleting (rather than marking
    them skipped) lets a later scan start a fresh hold if the price comes back."""
    if not alert_ids:
        return
    with db.session() as s:
        rows = (
            s.query(Alert)
            .filter(Alert.id.in_(alert_ids), Alert.status == "pending_confirm")
            .all()
        )
        for row in rows:
            logger.info(
                "Dropping unconfirmed alert %s %s %s — not +EV on recheck.",
                row.id, row.market, row.outcome_name,
            )
            s.delete(row)


def _due_pending(db: Database, now: dt.datetime) -> list[tuple[int, str, str, str]]:
    """(id, sport_key, event_id, market) for holds old enough to recheck."""
    delay = dt.timedelta(minutes=settings.confirm_delay_minutes)
    with db.session() as s:
        rows = s.query(Alert).filter(Alert.status == "pending_confirm").all()
        due = []
        for row in rows:
            if row.first_seen_at is None:
                continue
            if now - row.first_seen_at >= delay:
                due.append((row.id, row.sport_key, row.event_id, row.market))
        return due


def confirm_pending(
    db: Database,
    telegram: TelegramClient,
    odds_client: OddsApiClient,
    now: dt.datetime,
) -> int:
    """Re-fetch held lines whose wait has elapsed and alert only the ones still +EV.

    Runs on every poll tick, not only inside a scan window, so the wait is a few minutes
    rather than until the next scheduled scan. Costs credits only for sports/events that
    actually have a hold due. An API error backs off briefly and leaves the holds in
    place to retry; it does not alert off the original snapshot.
    """
    if settings.confirm_delay_minutes <= 0:
        return 0
    _expire_old_pending(db, now)
    due = _due_pending(db, now)
    if not due:
        return 0
    retry_raw = db.get_kv(_CONFIRM_BACKOFF_KEY)
    if retry_raw:
        retry_at = dt.datetime.fromisoformat(retry_raw)
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=dt.timezone.utc)
        if now < retry_at:
            logger.info("Confirmation recheck on backoff until %s.", retry_at.isoformat())
            return 0

    bankroll = db.current_bankroll(settings.starting_bankroll)
    main_by_sport: dict[str, list[tuple[str, list[tuple[int, str, str, str]]]]] = defaultdict(list)
    extra_by_event: dict[tuple[str, str], list[tuple[int, str, str, str]]] = defaultdict(list)
    for item in due:
        _id, sport_key, event_id, market = item
        if market in _MAIN_MARKETS:
            groups = main_by_sport.setdefault(sport_key, [])
            bucket = next((g for g in groups if g[0] == event_id), None)
            if bucket is None:
                groups.append((event_id, [item]))
            else:
                bucket[1].append(item)
        else:
            extra_by_event[(sport_key, event_id)].append(item)

    sent = 0
    failed = False
    window_to = now + dt.timedelta(hours=settings.max_hours_ahead)
    for sport_key, event_groups in main_by_sport.items():
        markets = sorted({item[3] for _, items in event_groups for item in items})
        try:
            events = odds_client.get_odds(
                sport_key,
                markets,
                bookmakers=settings.scan_bookmakers,
                commence_time_from=now,
                commence_time_to=window_to,
                include_links=True,
            )
        except OddsApiQuotaExceededError:
            raise
        except OddsApiError:
            logger.exception("Confirm re-fetch failed for %s", sport_key)
            failed = True
            continue
        by_id = {event["id"]: event for event in events}
        for event_id, items in event_groups:
            event = by_id.get(event_id)
            if event is not None:
                sent += process_event(
                    db, telegram, event, sport_key, markets, bankroll, now
                )
            _drop_unconfirmed(db, [item[0] for item in items])

    for (sport_key, event_id), items in extra_by_event.items():
        markets = sorted({item[3] for item in items})
        player_markets = [m for m in markets if m not in _GAME_ALT_MARKETS]
        game_alt_markets = [m for m in markets if m in _GAME_ALT_MARKETS]
        try:
            event = odds_client.get_event_odds(
                sport_key,
                event_id,
                markets,
                bookmakers=settings.props_bookmakers,
                include_links=True,
            )
        except OddsApiQuotaExceededError:
            raise
        except OddsApiError:
            logger.exception(
                "Confirm re-fetch failed for %s event %s", sport_key, event_id
            )
            failed = True
            continue
        sent += process_prop_event(
            db, telegram, event, sport_key, player_markets, bankroll, now,
            game_alt_markets=game_alt_markets,
        )
        _drop_unconfirmed(db, [item[0] for item in items])

    if failed:
        retry_at = now + dt.timedelta(minutes=_CONFIRM_BACKOFF_MINUTES)
        db.set_kv(_CONFIRM_BACKOFF_KEY, retry_at.isoformat())
        logger.info("Confirmation recheck backing off until %s.", retry_at.isoformat())
    return sent


def run() -> None:
    secrets = Secrets.from_env()
    db = Database(secrets.database_url)
    telegram = TelegramClient(secrets.telegram_bot_token, secrets.telegram_chat_id)
    odds_client = OddsApiClient(
        api_key=secrets.odds_api_key,
        base_url=settings.odds_api_base_url,
        odds_format=settings.odds_format,
    )

    # 1. Apply any Telegram commands the user sent since the last run. This runs on every
    # tick regardless of scan windows -- it's free (no Odds API calls), and keeps /placed,
    # /skip, /settle etc. responsive rather than waiting hours for the next real scan.
    # (/scan and /quota do spend Odds API credits, but only when the user actually sends them.)
    offset_raw = db.get_kv("telegram_update_offset")
    offset = int(offset_raw) if offset_raw else None
    updates = telegram.get_updates(offset)
    replies = commands.process_updates(
        db, settings, updates, telegram, odds_client,
        allowed_chat_id=secrets.telegram_chat_id.strip(),
    )
    logger.info("Telegram: fetched %d update(s), sending %d reply(ies).", len(updates), len(replies))
    for reply in replies:
        telegram.send_message(reply)

    now = dt.datetime.now(dt.timezone.utc)
    force_run = os.environ.get("FORCE_RUN") == "true"

    # 2. Send the daily performance digest once a day (config/settings.yaml
    # `reporting.time_local`), independent of the scan windows below -- same per-window
    # dedup pattern (a separate "last_daily_report_window" marker) so the continuous poll
    # loop doesn't resend it on every ~20s tick. scripts/report.py is the manual equivalent.
    report_window_key = current_scan_window_key(
        now, [settings.daily_report_time_local], settings.timezone, settings.scan_window_minutes
    )
    if force_run or (
        report_window_key is not None
        and db.get_kv("last_daily_report_window") != report_window_key
    ):
        lines = ["*Daily Bet Bot Report*"] + build_report_lines(db, settings)
        telegram.send_message("\n".join(lines))
        if not force_run:
            db.set_kv("last_daily_report_window", report_window_key)

    # 3. Only spend Odds API credits during the configured scan windows (see
    # config/settings.yaml `scheduling.scan_times_local`). When run() is called by a tight
    # poll loop (e.g. the VPS's continuous Telegram-polling loop) rather than one cron tick
    # per window, current_scan_window_key + the "last_scan_window" marker below ensure the
    # actual scan still only fires once per window, not once per poll. Player props run on
    # their own, coarser, independent gate (config/settings.yaml `props:`) since they're a
    # different and more expensive cost shape (see run_props_scan) -- a tick can run main
    # markets, props, both, or neither, depending on which window(s) it falls in.
    window_key = current_scan_window_key(
        now, settings.scan_times_local, settings.timezone, settings.scan_window_minutes
    )
    should_scan_main = force_run or (
        window_key is not None and db.get_kv("last_scan_window") != window_key
    )
    props_window_key = current_scan_window_key(
        now, settings.props_scan_times_local, settings.timezone, settings.props_scan_window_minutes
    )
    should_scan_props = force_run or (
        props_window_key is not None
        and db.get_kv("last_props_scan_window") != props_window_key
    )
    # 3.5 Quota gate: a prior tick may have already hit OUT_OF_USAGE_CREDITS (see the
    # try/except below) and paused scanning. Before spending anything this tick, do one
    # free recheck; if credits are still exhausted, skip all paid calls below entirely
    # rather than re-discovering the same OUT_OF_USAGE_CREDITS error on every sport.
    # This includes the +EV recheck, which is a paid fetch when a hold is due.
    if db.get_kv(QUOTA_EXHAUSTED_KV_KEY) == "true" and not _quota_available(db, odds_client, telegram):
        logger.info("Odds API quota still exhausted -- skipping scan(s) this tick.")
        return

    scan_sent = 0

    try:
        # Held lines recheck on every tick, including between scan windows, so the wait is
        # a few minutes rather than until the next scheduled scan. No-op (no API call) when
        # nothing is due.
        confirmed = confirm_pending(db, telegram, odds_client, now)
        if confirmed:
            logger.info("Confirmed %d held alert(s).", confirmed)

        if not should_scan_main and not should_scan_props:
            logger.info("Outside scheduled scan windows -- skipping odds fetch.")
            return

        bankroll = db.current_bankroll(settings.starting_bankroll)
        if should_scan_main:
            # 4. Auto-settle any placed bets whose games have finished (cheap flat-rate
            # /scores call, only for sports with something actually pending).
            if settings.settlement_enabled:
                settled = settlement.auto_settle_pending(db, settings, telegram, odds_client)
                if settled:
                    logger.info("Auto-settled %d bet(s).", settled)

            # 5. Scan configured sports/markets for +EV lines.
            scan_sent += run_scan(db, settings, telegram, odds_client, bankroll, now)
            if not force_run:
                db.set_kv("last_scan_window", window_key)

        if should_scan_props:
            # 6. Scan configured sports' player_markets for +EV props (consensus devig).
            scan_sent += run_props_scan(db, settings, telegram, odds_client, bankroll, now)
            if not force_run:
                db.set_kv("last_props_scan_window", props_window_key)
    except OddsApiQuotaExceededError:
        # Whatever step raised this didn't finish (and didn't mark its window consumed),
        # so the next tick after quota recovers will retry it cleanly -- any alerts sent by
        # an earlier step this same tick (e.g. main markets, before props hit the wall) are
        # already persisted and unaffected.
        _mark_quota_exhausted(db, telegram)
        logger.warning("Odds API quota exhausted mid-scan -- pausing further scans until it resets.")
        return

    held = count_pending_since(db, now) if settings.confirm_delay_minutes > 0 else 0
    logger.info("Scan complete: %d alert(s) sent, %d held for recheck.", scan_sent, held)
    followup = scan_followup_message(scan_sent, held, settings.confirm_delay_minutes)
    if followup:
        telegram.send_message(followup)


if __name__ == "__main__":
    run()
