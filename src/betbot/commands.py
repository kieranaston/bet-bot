"""Parse and apply Telegram commands the user sends in reply to alerts.

Supported commands:
  /placed <alert_id> [stake odds]  Mark a bet as placed. With no extras, uses recommended
                                stake and the alert's stored odds. To override, pass BOTH
                                stake and odds (American +290/-110 or decimal 3.90).
  /skip <alert_id>             Mark an alert as skipped (won't be re-alerted).
  /settle <alert_id> win|loss|push Grade a placed bet and update bankroll.
  /bankroll [amount]           Show current bankroll, or set it manually.
  /status                      List bets that are placed but not yet settled.
  /stats                       Show bankroll + settled performance (wins/losses/ROI).
  /scan                        Run a scan right now (outside the usual windows) and alert on
                                +EV lines. Cooldown-limited (see SCAN_COOLDOWN_MINUTES) since
                                it bypasses the normal scan-window quota gating.
  /quota                       Show current Odds API usage (used/remaining/% of period used).
  /help                        List commands.
"""
from __future__ import annotations

import datetime as dt
import logging

from betbot import settlement
from betbot.config import Settings
from betbot.odds_client import OddsApiClient
from betbot.performance import build_report_lines
from betbot.storage import Alert, Database, local_time_str, parse_to_decimal_odds
from betbot.telegram import TelegramClient

logger = logging.getLogger(__name__)

SCAN_COOLDOWN_MINUTES = 5  # protects Odds API quota from an accidental repeated /scan

_PLACED_USAGE = "Usage: /placed <alert_id> [stake odds]"

HELP_TEXT = (
    "*Commands*\n"
    "`/placed <id>` — mark placed at recommended stake & alert odds\n"
    "`/placed <id> <stake> <odds>` — same, with your stake & American/decimal odds\n"
    "`/skip <id>` — dismiss an alert\n"
    "`/settle <id> win|loss|push` — grade a bet & update bankroll\n"
    "`/bankroll amount` — show or set current bankroll\n"
    "`/status` — list open (placed, unsettled) bets\n"
    "`/stats` — bankroll + settled performance (wins/losses/ROI)\n"
    f"`/scan` — run a scan right now and alert on +EV lines (uses Odds API credits, "
    f"max once every {SCAN_COOLDOWN_MINUTES} min)\n"
    "`/quota` — show current Odds API usage quota\n"
    "`/help` — this message"
)


def process_updates(
    db: Database,
    settings: Settings,
    updates: list[dict],
    telegram: TelegramClient,
    odds_client: OddsApiClient,
    allowed_chat_id: str | None = None,
) -> list[str]:
    """Applies each update's command and returns the reply text(s) to send back, in order.
    Also advances the stored Telegram update offset so we never reprocess a command."""
    replies: list[str] = []
    last_update_id = None
    for update in updates:
        last_update_id = update["update_id"]
        message = (
            update.get("message")
            or update.get("edited_message")
            or update.get("channel_post")
        )
        if not message or "text" not in message:
            continue
        if allowed_chat_id is not None:
            chat_id = str((message.get("chat") or {}).get("id", ""))
            if chat_id != str(allowed_chat_id):
                logger.info(
                    "Ignoring Telegram update %s from chat %s (expected %s)",
                    last_update_id, chat_id, allowed_chat_id,
                )
                continue
        replies.append(
            _dispatch(db, settings, telegram, odds_client, message["text"].strip())
        )

    if last_update_id is not None:
        db.set_kv("telegram_update_offset", str(last_update_id + 1))
    return [r for r in replies if r]


def _dispatch(
    db: Database,
    settings: Settings,
    telegram: TelegramClient,
    odds_client: OddsApiClient,
    text: str,
) -> str:
    parts = text.split()
    if not parts:
        return ""
    # Telegram clients (menu taps, groups) send `/help@BotName` -- match the verb only.
    cmd = parts[0].lower().split("@", 1)[0]
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
        if cmd == "/stats":
            return _cmd_stats(db, settings)
        if cmd == "/scan":
            return _cmd_scan(db, settings, telegram, odds_client)
        if cmd == "/quota":
            return _cmd_quota(odds_client)
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


def _get_alert(session, alert_id: int) -> Alert | None:
    return session.get(Alert, alert_id)


def _parse_placed_extras(tokens: list[str]) -> tuple[float | None, float | None]:
    """Parse optional stake+odds after the alert id. Returns (stake, decimal_odds).

    Either both omitted (use alert defaults) or both provided -- a single extra arg is
    rejected because decimal odds (3.90) are ambiguous with stake dollars.
    """
    if not tokens:
        return None, None
    if len(tokens) == 1:
        raise ValueError("provide both stake and odds, or neither")
    if len(tokens) > 2:
        raise ValueError("too many arguments")
    return float(tokens[0]), parse_to_decimal_odds(tokens[1])


def _cmd_placed(db: Database, settings: Settings, args: list[str]) -> str:
    if not args:
        return _PLACED_USAGE
    alert_id = int(args[0])
    try:
        stake_arg, odds_arg = _parse_placed_extras(args[1:])
    except ValueError as exc:
        return f"Could not parse stake/odds: {exc}. {_PLACED_USAGE}"
    with db.session() as s:
        alert = _get_alert(s, alert_id)
        if not alert:
            return f"No alert #{alert_id} found."
        stake = stake_arg if stake_arg is not None else alert.recommended_stake
        if odds_arg is not None:
            alert.book_odds = odds_arg
        alert.status = "placed"
        alert.placed_stake = stake
        return (
            f"Logged bet #{alert_id}: {alert.outcome_display()} @ {alert.book_odds_display()} "
            f"({settings.display_name(alert.bookmaker_key)}) for ${stake:,.2f}"
        )


def _cmd_skip(db: Database, args: list[str]) -> str:
    if not args:
        return "Usage: /skip <alert_id>"
    alert_id = int(args[0])
    with db.session() as s:
        alert = _get_alert(s, alert_id)
        if not alert:
            return f"No alert #{alert_id} found."
        alert.status = "skipped"
        return f"Skipped alert #{alert_id}."


def _cmd_settle(db: Database, settings: Settings, args: list[str]) -> str:
    if len(args) < 2 or args[1].lower() not in ("win", "loss", "push"):
        return "Usage: /settle <alert_id> win|loss|push"
    alert_id = int(args[0])
    outcome = args[1].lower()

    with db.session() as s:
        alert = _get_alert(s, alert_id)
        if not alert:
            return f"No alert #{alert_id} found."
        if not alert.placed_stake:
            return f"Alert #{alert_id} was never marked /placed -- nothing to settle."
        if alert.status.startswith("settled_"):
            return f"Alert #{alert_id} is already settled ({alert.status})."

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
        entries = []
        for a in open_bets:
            entries.append(
                f"#{a.id} {a.league_display()} {a.away_team} @ {a.home_team} "
                f"({local_time_str(a.commence_time, settings.timezone)}) — {a.outcome_display()} "
                f"@ {a.book_odds_display()} ({settings.display_name(a.bookmaker_key)}) "
                f"${a.placed_stake:,.2f}\n"
                f"True odds: {a.true_odds_display()} (via {settings.method_display(a.sharp_book_key)})"
            )
        return "*Open bets:*\n\n" + "\n\n".join(entries)


def _cmd_stats(db: Database, settings: Settings) -> str:
    lines = ["*Stats*"] + build_report_lines(db, settings)
    return "\n".join(lines)


def _cmd_scan(
    db: Database, settings: Settings, telegram: TelegramClient, odds_client: OddsApiClient
) -> str:
    # Local import: betbot.main imports this module to dispatch commands, so importing it
    # back at module level here would be circular. By the time this runs, main has already
    # finished importing, so it's safe.
    from betbot import main as betbot_main

    now = dt.datetime.now(dt.timezone.utc)
    last_raw = db.get_kv("last_manual_scan_at")
    if last_raw:
        elapsed_minutes = (now - dt.datetime.fromisoformat(last_raw)).total_seconds() / 60.0
        if elapsed_minutes < SCAN_COOLDOWN_MINUTES:
            wait = SCAN_COOLDOWN_MINUTES - elapsed_minutes
            return (
                f"Manual scan on cooldown -- wait {wait:.1f} more minute(s). "
                f"(Limit: one manual scan per {SCAN_COOLDOWN_MINUTES} min, to protect "
                "Odds API quota from an accidental repeat.)"
            )
    db.set_kv("last_manual_scan_at", now.isoformat())

    bankroll = db.current_bankroll(settings.starting_bankroll)
    alerts_sent = betbot_main.run_scan(db, settings, telegram, odds_client, bankroll, now)
    if alerts_sent:
        return f"Manual scan complete: {alerts_sent} alert(s) sent above."
    return "Manual scan complete: no new +EV opportunities right now."


def _cmd_quota(odds_client: OddsApiClient) -> str:
    # Deliberately doesn't show "last call cost": get_quota() always calls the free
    # /sports endpoint to check itself, and a fresh OddsApiClient is created every ~20s
    # loop tick, so that field could only ever reflect the cost of this check call (always
    # 0) -- never a real scan's cost, which happened in a different tick's client instance.
    quota = odds_client.get_quota()
    used, remaining = quota.get("used"), quota.get("remaining")
    lines = [
        "*Odds API quota*",
        f"Used: {used or '?'}",
        f"Remaining: {remaining or '?'}",
    ]
    try:
        total = int(used) + int(remaining)
        if total > 0:
            lines.append(f"Used {int(used) / total * 100.0:.1f}% of this period's quota")
    except (TypeError, ValueError):
        pass  # headers missing/non-numeric -- skip the percentage line rather than crash
    return "\n".join(lines)
