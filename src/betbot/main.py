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
from zoneinfo import ZoneInfo

from betbot import commands, settlement
from betbot.config import Secrets, settings
from betbot.devig import devig
from betbot.ev import ev_pct
from betbot.kelly import stake_amount
from betbot.odds_client import OddsApiClient, OddsApiError
from betbot.scheduler import current_scan_window_key, should_alert
from betbot.storage import Alert, Database
from betbot.telegram import TelegramClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("betbot.main")

PRICE_CHANGE_EPSILON = 0.02  # decimal odds points; smaller moves don't count as "changed"

MARKET_LABELS = {"h2h": "ML", "spreads": "Spread", "totals": "Total"}


def extract_outcomes(
    market: dict, book_bm: dict
) -> list[tuple[str, float | None, float, str | None]]:
    """Returns (name, point, price, deep_link) per outcome. deep_link prefers the most
    specific link The Odds API offers (outcome > market > bookmaker/event), falling back
    to None if `includeLinks=true` didn't return one for this book."""
    bm_link = book_bm.get("link")
    market_link = market.get("link") or bm_link
    return [
        (o["name"], o.get("point"), float(o["price"]), o.get("link") or market_link)
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
    sharp_bm = next((bm for bm in bookmakers if bm["key"] in settings.sharp_book_keys), None)
    if sharp_bm is None:
        return 0

    ontario_bms = [bm for bm in bookmakers if settings.is_ontario_book(bm["key"])]
    if not ontario_bms:
        return 0

    alerts_sent = 0
    for market_key in markets:
        sharp_market = find_market(sharp_bm, market_key)
        if not sharp_market:
            continue
        sharp_outcomes = extract_outcomes(sharp_market, sharp_bm)
        if len(sharp_outcomes) < 2:
            continue
        try:
            true_probs = devig(
                [price for _, _, price, _ in sharp_outcomes], method=settings.devig_method
            )
        except ValueError:
            continue
        sharp_lookup = {
            (name, point): p for (name, point, _, _), p in zip(sharp_outcomes, true_probs)
        }

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
            for name, point, price, link in extract_outcomes(book_market, book_bm):
                link = link or settings.homepage_url(book_bm["key"])
                key = (name, point)
                current = best_by_outcome.get(key)
                if current is None or price > current[1]:
                    best_by_outcome[key] = (book_bm["key"], price, link)

        for (name, point), (bookmaker_key, price, link) in best_by_outcome.items():
            true_prob = sharp_lookup.get((name, point))
            if true_prob is None:
                continue  # line doesn't match the sharp book's current line -- skip
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
                hours_to_commence=hours_to_commence,
                now=now,
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
    hours_to_commence: float,
    now: dt.datetime,
) -> int:
    with db.session() as s:
        existing = (
            s.query(Alert)
            .filter_by(
                event_id=event["id"],
                market=market_key,
                outcome_name=outcome_name,
                point=point,
                bookmaker_key=bookmaker_key,
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
                bookmaker_key=bookmaker_key,
                book_odds=price,
                deep_link=deep_link,
                sharp_book_key=settings.sharp_book_keys[0],
                true_prob=true_prob,
                ev_pct=ev,
                recommended_stake=stake,
                status="new",
            )
            s.add(alert)
            price_changed = True
        else:
            if existing.status in (
                "placed", "skipped", "settled_win", "settled_loss", "settled_push",
            ):
                return 0  # user already acted on this -- don't re-alert
            price_changed = abs(existing.book_odds - price) >= PRICE_CHANGE_EPSILON
            existing.book_odds = price
            existing.deep_link = deep_link
            existing.true_prob = true_prob
            existing.ev_pct = ev
            existing.recommended_stake = stake
            alert = existing

        if not should_alert(
            hours_to_commence=hours_to_commence,
            tiers=settings.scheduling_tiers,
            last_alerted_at=alert.last_alerted_at,
            now=now,
            price_changed=price_changed,
        ):
            return 0

        s.flush()  # ensure alert.id is populated for new rows
        _send_alert_message(telegram, alert)
        alert.status = "notified"
        alert.last_alerted_at = now
        return 1


def _local_time_str(commence_time: dt.datetime) -> str:
    local = commence_time.astimezone(ZoneInfo(settings.timezone))
    hour12 = local.hour % 12 or 12
    ampm = "am" if local.hour < 12 else "pm"
    return f"{local.strftime('%a')} {hour12}:{local.minute:02d}{ampm} ET"


def _send_alert_message(telegram: TelegramClient, alert: Alert) -> None:
    """Bare-minimum alert: what to bet, at what odds/book, for how much, and the two
    commands to act on it -- true_prob is dropped since it's a diagnostic backing number,
    not something needed to decide whether to place the bet."""
    label = MARKET_LABELS.get(alert.market, alert.market)
    book = settings.display_name(alert.bookmaker_key)

    lines = [
        f"*+{alert.ev_pct:.1f}% EV* · {label}: {alert.outcome_display()} @ {alert.book_odds_display()} ({book})",
        f"{alert.away_team} @ {alert.home_team} · {_local_time_str(alert.commence_time)} · "
        f"${alert.recommended_stake:,.2f}",
    ]
    if alert.deep_link:
        lines.append(f"[Bet now]({alert.deep_link})")
    lines.append(f"`/placed {alert.id}`  `/skip {alert.id}`")
    telegram.send_message("\n".join(lines))


def run() -> None:
    secrets = Secrets.from_env()
    db = Database(secrets.database_url)
    telegram = TelegramClient(secrets.telegram_bot_token, secrets.telegram_chat_id)

    # 1. Apply any Telegram commands the user sent since the last run. This runs on every
    # tick regardless of scan windows -- it's free (no Odds API calls), and keeps /placed,
    # /skip, /settle etc. responsive rather than waiting hours for the next real scan.
    offset_raw = db.get_kv("telegram_update_offset")
    offset = int(offset_raw) if offset_raw else None
    updates = telegram.get_updates(offset)
    replies = commands.process_updates(
        db, settings, updates, allowed_chat_id=secrets.telegram_chat_id.strip()
    )
    logger.info("Telegram: fetched %d update(s), sending %d reply(ies).", len(updates), len(replies))
    for reply in replies:
        telegram.send_message(reply)

    # 2. Only spend Odds API credits during the configured scan windows (see
    # config/settings.yaml `scheduling.scan_times_local`). When run() is called by a tight
    # poll loop (e.g. the VPS's continuous Telegram-polling loop) rather than one cron tick
    # per window, current_scan_window_key + the "last_scan_window" marker below ensure the
    # actual scan still only fires once per window, not once per poll.
    now = dt.datetime.now(dt.timezone.utc)
    force_run = os.environ.get("FORCE_RUN") == "true"
    window_key = current_scan_window_key(
        now, settings.scan_times_local, settings.timezone, settings.scan_window_minutes
    )
    if not force_run:
        if window_key is None:
            logger.info("Outside scheduled scan window -- skipping odds fetch.")
            return
        if db.get_kv("last_scan_window") == window_key:
            logger.info("Already scanned this window (%s) -- skipping odds fetch.", window_key)
            return

    odds_client = OddsApiClient(
        api_key=secrets.odds_api_key,
        base_url=settings.odds_api_base_url,
        odds_format=settings.odds_format,
    )

    # 3. Auto-settle any placed bets whose games have finished (cheap flat-rate /scores
    # call, only for sports with something actually pending).
    if settings.settlement_enabled:
        settled = settlement.auto_settle_pending(db, settings, telegram, odds_client)
        if settled:
            logger.info("Auto-settled %d bet(s).", settled)

    # 4. Scan configured sports/markets for +EV lines.
    bankroll = db.current_bankroll(settings.starting_bankroll)
    window_from = now
    window_to = now + dt.timedelta(hours=settings.max_hours_ahead)
    total_alerts = 0
    for sport in settings.sports:
        sport_key, markets = sport["key"], sport["markets"]

        # Free precheck (an empty /odds response also costs 0, per the docs, but this
        # skips an unnecessary round-trip/rate-limit hit for sports with nothing upcoming).
        try:
            upcoming = odds_client.get_events(sport_key, window_from, window_to)
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
        except OddsApiError:
            logger.exception("Failed to fetch odds for %s", sport_key)
            continue
        for event in events:
            total_alerts += process_event(
                db, telegram, event, sport_key, markets, bankroll, now
            )
    if not force_run:
        db.set_kv("last_scan_window", window_key)
    logger.info("Scan complete: %d new/updated alert(s) sent.", total_alerts)


if __name__ == "__main__":
    run()
