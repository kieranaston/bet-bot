"""Bet grading (win/loss/push) and settlement application.

Shared by two paths: the manual `/settle` Telegram command (betbot.commands), and
automatic settlement via The Odds API's /scores endpoint (`auto_settle_pending` below),
which runs once per scan (see betbot.main) so it stays within the same 3x/day cadence
that keeps API usage low.
"""
from __future__ import annotations

import logging

from betbot.config import Settings
from betbot.odds_client import OddsApiClient, OddsApiError
from betbot.storage import Alert, Database
from betbot.telegram import TelegramClient

logger = logging.getLogger(__name__)


def grade_alert(alert: Alert, home_score: float, away_score: float) -> str | None:
    """Returns "win" | "loss" | "push", or None if the alert's outcome/market can't be
    graded from these two scores (e.g. outcome_name doesn't match either team -- shouldn't
    happen, but we never want to guess a settlement)."""
    if alert.market == "h2h":
        if alert.outcome_name == alert.home_team:
            team, opp = home_score, away_score
        elif alert.outcome_name == alert.away_team:
            team, opp = away_score, home_score
        else:
            return None
        if team > opp:
            return "win"
        if team < opp:
            return "loss"
        return "push"

    if alert.market == "spreads":
        if alert.outcome_name == alert.home_team:
            team, opp = home_score, away_score
        elif alert.outcome_name == alert.away_team:
            team, opp = away_score, home_score
        else:
            return None
        adjusted = team + (alert.point or 0.0)
        if adjusted > opp:
            return "win"
        if adjusted < opp:
            return "loss"
        return "push"

    if alert.market == "totals":
        total = home_score + away_score
        point = alert.point or 0.0
        name = alert.outcome_name.lower()
        if name == "over":
            if total > point:
                return "win"
            if total < point:
                return "loss"
            return "push"
        if name == "under":
            if total < point:
                return "win"
            if total > point:
                return "loss"
            return "push"
        return None

    return None


def apply_settlement(db: Database, settings: Settings, alert: Alert, outcome: str) -> float:
    """Grades `alert` as won/lost/pushed, updates its profit/status, and updates the
    tracked bankroll. `alert` must be attached to an active session (caller commits).
    Returns the new bankroll."""
    if outcome == "win":
        profit = alert.placed_stake * (alert.book_odds - 1.0)
    elif outcome == "loss":
        profit = -alert.placed_stake
    else:
        profit = 0.0

    alert.status = f"settled_{outcome}"
    alert.profit = round(profit, 2)

    current = db.current_bankroll(settings.starting_bankroll)
    new_bankroll = round(current + profit, 2)
    db.set_bankroll(new_bankroll, reason=f"settle alert #{alert.id} ({outcome})")
    return new_bankroll


def auto_settle_pending(
    db: Database, settings: Settings, telegram: TelegramClient, odds_client: OddsApiClient
) -> int:
    """Checks every placed-but-unsettled bet against The Odds API's /scores endpoint and
    settles anything whose game has finished. Only calls /scores for sports that actually
    have a pending bet (skips the call entirely otherwise), and only once per sport per
    call regardless of how many pending bets that sport has."""
    with db.session() as s:
        pending = s.query(Alert).filter(Alert.status == "placed").all()
        if not pending:
            return 0

        by_sport: dict[str, list[Alert]] = {}
        for alert in pending:
            by_sport.setdefault(alert.sport_key, []).append(alert)

        settled_count = 0
        for sport_key, alerts in by_sport.items():
            try:
                scores = odds_client.get_scores(sport_key, days_from=settings.settlement_days_from)
            except OddsApiError:
                logger.exception("Failed to fetch scores for %s", sport_key)
                continue
            scores_by_event = {ev["id"]: ev for ev in scores}

            for alert in alerts:
                event = scores_by_event.get(alert.event_id)
                if not event or not event.get("completed"):
                    continue  # not finished yet (or event fell outside days_from) -- retry next scan

                score_map: dict[str, float] = {}
                for entry in event.get("scores") or []:
                    try:
                        score_map[entry["name"]] = float(entry["score"])
                    except (TypeError, ValueError, KeyError):
                        continue
                home_score = score_map.get(alert.home_team)
                away_score = score_map.get(alert.away_team)
                if home_score is None or away_score is None:
                    logger.warning(
                        "Could not match team names to scores for alert #%s (%s @ %s)",
                        alert.id, alert.away_team, alert.home_team,
                    )
                    continue

                outcome = grade_alert(alert, home_score, away_score)
                if outcome is None:
                    logger.warning("Could not grade alert #%s (market=%s)", alert.id, alert.market)
                    continue

                new_bankroll = apply_settlement(db, settings, alert, outcome)
                telegram.send_message(
                    f"Auto-settled #{alert.id}: *{outcome.upper()}* ({alert.profit:+.2f})\n"
                    f"Bankroll: ${new_bankroll:,.2f}"
                )
                settled_count += 1

    return settled_count
