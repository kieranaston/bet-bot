"""Parse and apply Telegram commands the user sends in reply to alerts.

Supported commands:
  /placed <alert_id> [stake]   Mark a bet as placed (defaults to the recommended stake).
  /skip <alert_id>             Mark an alert as skipped (won't be re-alerted).
  /settle <alert_id> win|loss|push [closing_odds]
                                Grade a placed bet, update bankroll, optionally record the
                                closing line for CLV tracking.
  /bankroll [amount]           Show current bankroll, or set it manually.
  /status                      List bets that are placed but not yet settled.
  /help                        List commands.
"""
from __future__ import annotations

import logging

from betbot import settlement
from betbot.config import Settings
from betbot.storage import Alert, Database

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "*Commands*\n"
    "/placed <id> [stake] — mark a bet placed (defaults to recommended stake)\n"
    "/skip <id> — dismiss an alert\n"
    "/settle <id> win|loss|push [closing_odds] — grade a bet & update bankroll\n"
    "/bankroll [amount] — show or set current bankroll\n"
    "/status — list open (placed, unsettled) bets\n"
    "/help — this message"
)


def process_updates(
    db: Database, settings: Settings, updates: list[dict]
) -> list[str]:
    """Applies each update's command and returns the reply text(s) to send back, in order.
    Also advances the stored Telegram update offset so we never reprocess a command."""
    replies: list[str] = []
    last_update_id = None
    for update in updates:
        last_update_id = update["update_id"]
        message = update.get("message") or update.get("channel_post")
        if not message or "text" not in message:
            continue
        replies.append(_dispatch(db, settings, message["text"].strip()))

    if last_update_id is not None:
        db.set_kv("telegram_update_offset", str(last_update_id + 1))
    return [r for r in replies if r]


def _dispatch(db: Database, settings: Settings, text: str) -> str:
    parts = text.split()
    if not parts:
        return ""
    cmd = parts[0].lower()
    args = parts[1:]

    try:
        if cmd == "/help" or cmd == "/start":
            return HELP_TEXT
        if cmd == "/bankroll":
            return _cmd_bankroll(db, settings, args)
        if cmd == "/placed":
            return _cmd_placed(db, settings, args)
        if cmd == "/skip":
            return _cmd_skip(db, args)
        if cmd == "/settle":
            return _cmd_settle(db, settings, args)
        if cmd == "/status":
            return _cmd_status(db, settings)
    except Exception as exc:  # noqa: BLE001 -- surface the error to the user, don't crash the run
        logger.exception("Error handling command %r", text)
        return f"Error handling `{text}`: {exc}"

    return ""  # unrecognized text -- ignore silently rather than spamming replies


def _cmd_bankroll(db: Database, settings: Settings, args: list[str]) -> str:
    if args:
        amount = float(args[0])
        db.set_bankroll(amount, reason="manual /bankroll update")
        return f"Bankroll set to ${amount:,.2f}"
    current = db.current_bankroll(settings.starting_bankroll)
    return f"Current bankroll: ${current:,.2f}"


def _get_alert(db, session, alert_id: int) -> Alert | None:
    return session.get(Alert, alert_id)


def _cmd_placed(db: Database, settings: Settings, args: list[str]) -> str:
    if not args:
        return "Usage: /placed <alert_id> [stake]"
    alert_id = int(args[0])
    with db.session() as s:
        alert = _get_alert(db, s, alert_id)
        if not alert:
            return f"No alert #{alert_id} found."
        stake = float(args[1]) if len(args) > 1 else alert.recommended_stake
        alert.status = "placed"
        alert.placed_stake = stake
        return (
            f"Logged bet #{alert_id}: {alert.outcome_name} @ {alert.book_odds} "
            f"({settings.display_name(alert.bookmaker_key)}) for ${stake:,.2f}"
        )


def _cmd_skip(db: Database, args: list[str]) -> str:
    if not args:
        return "Usage: /skip <alert_id>"
    alert_id = int(args[0])
    with db.session() as s:
        alert = _get_alert(db, s, alert_id)
        if not alert:
            return f"No alert #{alert_id} found."
        alert.status = "skipped"
        return f"Skipped alert #{alert_id}."


def _cmd_settle(db: Database, settings: Settings, args: list[str]) -> str:
    if len(args) < 2 or args[1].lower() not in ("win", "loss", "push"):
        return "Usage: /settle <alert_id> win|loss|push [closing_odds]"
    alert_id = int(args[0])
    outcome = args[1].lower()
    closing_odds = float(args[2]) if len(args) > 2 else None

    with db.session() as s:
        alert = _get_alert(db, s, alert_id)
        if not alert:
            return f"No alert #{alert_id} found."
        if not alert.placed_stake:
            return f"Alert #{alert_id} was never marked /placed -- nothing to settle."
        if alert.status.startswith("settled_"):
            return f"Alert #{alert_id} is already settled ({alert.status})."

        if closing_odds is not None:
            alert.closing_odds = closing_odds

        new_bankroll = settlement.apply_settlement(db, settings, alert, outcome)
        return (
            f"Settled #{alert_id} as {outcome.upper()}: {alert.profit:+.2f}. "
            f"Bankroll now ${new_bankroll:,.2f}"
        )


def _cmd_status(db: Database, settings: Settings) -> str:
    with db.session() as s:
        open_bets = (
            s.query(Alert).filter(Alert.status == "placed").order_by(Alert.commence_time)
        ).all()
        if not open_bets:
            return "No open bets."
        lines = ["*Open bets:*"]
        for a in open_bets:
            lines.append(
                f"#{a.id} {a.away_team} @ {a.home_team} — {a.outcome_name} "
                f"@ {a.book_odds} ({settings.display_name(a.bookmaker_key)}) "
                f"${a.placed_stake:,.2f}"
            )
        return "\n".join(lines)
