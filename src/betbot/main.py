"""Entry point: process any pending Telegram commands, then scan configured sports/markets
for +EV lines at Ontario books (vs. Pinnacle as the sharp reference) and alert on them.

Run via: python -m betbot.main
Intended to be invoked on a schedule by .github/workflows/scan.yml (or a local cron / VPS
scheduler -- see README for both options).
"""
from __future__ import annotations

import datetime as dt
import logging

from betbot import commands
from betbot.config import Secrets, settings
from betbot.ev import ev_pct
from betbot.devig import devig
from betbot.kelly import stake_amount
from betbot.odds_client import OddsApiClient, OddsApiError
from betbot.scheduler import should_alert
from betbot.storage import Alert, Database
from betbot.telegram import TelegramClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("betbot.main")

PRICE_CHANGE_EPSILON = 0.02  # decimal odds points; smaller moves don't count as "changed"

MARKET_LABELS = {"h2h": "Moneyline", "spreads": "Spread", "totals": "Total"}


def extract_outcomes(market: dict) -> list[tuple[str, float | None, float]]:
    return [(o["name"], o.get("point"), float(o["price"])) for o in market.get("outcomes", [])]


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
        sharp_outcomes = extract_outcomes(sharp_market)
        if len(sharp_outcomes) < 2:
            continue
        try:
            true_probs = devig(
                [price for _, _, price in sharp_outcomes], method=settings.devig_method
            )
        except ValueError:
            continue
        sharp_lookup = {
            (name, point): p for (name, point, _), p in zip(sharp_outcomes, true_probs)
        }

        for book_bm in ontario_bms:
            book_market = find_market(book_bm, market_key)
            if not book_market:
                continue
            for name, point, price in extract_outcomes(book_market):
                true_prob = sharp_lookup.get((name, point))
                if true_prob is None:
                    continue  # line doesn't match the sharp book's current line -- skip

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
                    bookmaker_key=book_bm["key"],
                    price=price,
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


def _send_alert_message(telegram: TelegramClient, alert: Alert) -> None:
    point_str = f" {alert.point:+g}" if alert.point is not None else ""
    label = MARKET_LABELS.get(alert.market, alert.market)
    text = (
        f"*+EV Bet Found* (#{alert.id})\n"
        f"{alert.away_team} @ {alert.home_team}\n"
        f"{label}: *{alert.outcome_name}{point_str}*\n"
        f"Book: {alert.bookmaker_key} @ {alert.book_odds:.2f}\n"
        f"Sharp true prob: {alert.true_prob * 100:.1f}% (via {alert.sharp_book_key})\n"
        f"*EV: +{alert.ev_pct:.1f}%*\n"
        f"Suggested stake (1/4 Kelly): *${alert.recommended_stake:,.2f}*\n"
        f"Game starts: {alert.commence_time.strftime('%a %b %d, %I:%M %p UTC')}\n\n"
        f"Reply `/placed {alert.id}` to log this bet, `/skip {alert.id}` to dismiss."
    )
    telegram.send_message(text)


def run() -> None:
    secrets = Secrets.from_env()
    db = Database(secrets.database_url)
    telegram = TelegramClient(secrets.telegram_bot_token, secrets.telegram_chat_id)
    odds_client = OddsApiClient(
        api_key=secrets.odds_api_key,
        base_url=settings.odds_api_base_url,
        regions=settings.odds_api_regions,
        odds_format=settings.odds_format,
    )

    # 1. Apply any Telegram commands the user sent since the last run.
    offset_raw = db.get_kv("telegram_update_offset")
    offset = int(offset_raw) if offset_raw else None
    updates = telegram.get_updates(offset)
    for reply in commands.process_updates(db, settings, updates):
        telegram.send_message(reply)

    # 2. Scan configured sports/markets for +EV lines.
    now = dt.datetime.now(dt.timezone.utc)
    bankroll = db.current_bankroll(settings.starting_bankroll)
    total_alerts = 0
    for sport in settings.sports:
        sport_key, markets = sport["key"], sport["markets"]
        try:
            events = odds_client.get_odds(sport_key, markets)
        except OddsApiError:
            logger.exception("Failed to fetch odds for %s", sport_key)
            continue
        for event in events:
            total_alerts += process_event(
                db, telegram, event, sport_key, markets, bankroll, now
            )
    logger.info("Scan complete: %d new/updated alert(s) sent.", total_alerts)


if __name__ == "__main__":
    run()
