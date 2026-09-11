#!/usr/bin/env python3
"""Send a daily Telegram digest: current bankroll, open bets, and settled performance.
Intended to be run once a day by .github/workflows/daily_report.yml."""
from __future__ import annotations

from betbot.config import Secrets, settings
from betbot.performance import summarize
from betbot.storage import Alert, Database
from betbot.telegram import TelegramClient


def main() -> None:
    secrets = Secrets.from_env()
    db = Database(secrets.database_url)
    telegram = TelegramClient(secrets.telegram_bot_token, secrets.telegram_chat_id)

    bankroll = db.current_bankroll(settings.starting_bankroll)
    with db.session() as s:
        all_alerts = s.query(Alert).all()
        open_bets = [a for a in all_alerts if a.status == "placed"]

    perf = summarize(all_alerts)

    lines = [
        "*Daily Bet Bot Report*",
        f"Bankroll: ${bankroll:,.2f}",
        f"Open bets: {len(open_bets)}",
        "",
        f"Settled: {perf.bets_settled} ({perf.wins}W-{perf.losses}L-{perf.pushes}P)",
        f"Total staked: ${perf.total_staked:,.2f}",
        f"Total profit: ${perf.total_profit:,.2f}",
        f"ROI: {perf.roi_pct:+.1f}%",
    ]
    if perf.avg_clv_pct is not None:
        lines.append(f"Avg CLV: {perf.avg_clv_pct:+.2f}%")

    telegram.send_message("\n".join(lines))


if __name__ == "__main__":
    main()
