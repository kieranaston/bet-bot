"""Bet grading (win/loss/push) and settlement application.

Shared by two paths: the manual `/settle` Telegram command (betbot.commands), and
automatic settlement via The Odds API's /scores endpoint (`auto_settle_pending` below),
which runs once per scan (see betbot.main) so it stays within the same 3x/day cadence
that keeps API usage low.
"""
from __future__ import annotations

import logging

from sqlalchemy import or_

from betbot.config import Settings
from betbot.odds_client import OddsApiClient, OddsApiError
from betbot.storage import Alert, Database, utcnow
from betbot.telegram import TelegramClient

logger = logging.getLogger(__name__)

# Markets `grade_alert` can actually resolve from the two final team scores /scores
# returns. alternate_spreads/alternate_totals grade identically to spreads/totals (just a
# different line); team_totals/alternate_team_totals need only one team's own score, which
# grade_alert pulls via `alert.participant` (these markets store the team name there, same
# slot player props use for the player name -- see extract_outcomes' `description`).
# Everything else (player_*, batter_*, pitcher_*, ...) is a player-level prop that /scores
# can never grade -- /settle <id> win|loss|push is the only path for those.
GRADABLE_MARKETS = {
    "h2h", "spreads", "totals",
    "alternate_spreads", "alternate_totals", "team_totals", "alternate_team_totals",
}


def _grade_over_under(name: str, total: float, point: float) -> str | None:
    name = name.lower()
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


def grade_alert(alert: Alert, home_score: float, away_score: float) -> str | None:
    """Returns "win" | "loss" | "push", or None if the alert's outcome/market can't be
    graded from these two scores (e.g. outcome_name doesn't match either team -- shouldn't
    happen, but we never want to guess a settlement)."""
    if alert.market == "h2h":
        # Three-way markets (soccer: home/draw/away) have no push on a tied team bet -- a
        # tie means the draw outcome won, so a home/away bet on the game just loses. Two-way
        # sports (NFL/NBA/NHL/MLB moneyline) have no draw outcome, so a tie (the rare NFL
        # regular-season tie) is correctly a push there.
        is_three_way = alert.sport_key.startswith("soccer_")
        if alert.outcome_name == "Draw":
            return "win" if home_score == away_score else "loss"
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
        return "loss" if is_three_way else "push"

    if alert.market in ("spreads", "alternate_spreads"):
        # alternate_spreads grades identically to spreads (same team/point math) -- it's
        # only the sourcing/pairing of the *line itself* (point negation, see
        # main.py::_devig_spread_alternates) that differs, not settlement.
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

    if alert.market in ("totals", "alternate_totals"):
        return _grade_over_under(alert.outcome_name, home_score + away_score, alert.point or 0.0)

    if alert.market in ("team_totals", "alternate_team_totals"):
        # These alert against ONE team's own total, not the combined game total --
        # `alert.participant` holds that team's name (Odds API's `description` field on
        # these outcomes, the same slot player props use for the player name).
        if alert.participant == alert.home_team:
            team_score = home_score
        elif alert.participant == alert.away_team:
            team_score = away_score
        else:
            return None
        return _grade_over_under(alert.outcome_name, team_score, alert.point or 0.0)

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
    """Checks every placed-but-unsettled bet whose game has started against The Odds API's
    /scores endpoint. Bets on a `GRADABLE_MARKETS` market get settled outright; anything
    else (player props -- /scores never returns player-level box scores) gets a one-time
    "needs manual /settle" nudge once its game is confirmed `completed`, tracked via
    `Alert.settlement_reminder_sent_at` so it isn't repeated every scan.

    Only calls /scores for sports that actually need it -- skips bets whose commence_time
    hasn't passed yet (a game that hasn't started can't be `completed`, so querying for it
    would just burn a flat 2-credit call for nothing every scan until it does), and once a
    prop bet's reminder has fired there's nothing further this function can do for it (it's
    stuck until the user runs /settle), so it drops out of the query too rather than paying
    for a /scores call on its behalf forever. Still only one /scores call per sport per
    call, regardless of how many pending bets that sport has."""
    with db.session() as s:
        pending = (
            s.query(Alert)
            .filter(
                Alert.status == "placed",
                Alert.commence_time <= utcnow(),
                or_(
                    Alert.market.in_(GRADABLE_MARKETS),
                    Alert.settlement_reminder_sent_at.is_(None),
                ),
            )
            .all()
        )
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

                if alert.market not in GRADABLE_MARKETS:
                    alert.settlement_reminder_sent_at = utcnow()
                    telegram.send_message(
                        f"Game over for #{alert.id}: {alert.outcome_display()} "
                        f"({alert.away_team} @ {alert.home_team}) needs manual settlement.\n"
                        f"`/settle {alert.id} win|loss|push`"
                    )
                    continue

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
