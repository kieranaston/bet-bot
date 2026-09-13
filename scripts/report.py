#!/usr/bin/env python3
"""Manually send the daily Telegram digest on demand (bankroll, open bets, settled
performance) -- the same digest betbot.main.run() now sends automatically once a day from
its continuous VPS loop. This script is a manual escape hatch (e.g. via SSH), not scheduled
by anything itself; set FORCE_RUN=true to bypass the `reporting.time_local` window check."""
from __future__ import annotations

import datetime as dt
import os

from betbot.config import Secrets, settings
from betbot.performance import build_report_lines
from betbot.scheduler import is_scan_time
from betbot.storage import Database
from betbot.telegram import TelegramClient


def main() -> None:
    now = dt.datetime.now(dt.timezone.utc)
    force_run = os.environ.get("FORCE_RUN") == "true"
    if not force_run and not is_scan_time(
        now, [settings.daily_report_time_local], settings.timezone, settings.scan_window_minutes
    ):
        return

    secrets = Secrets.from_env()
    db = Database(secrets.database_url)
    telegram = TelegramClient(secrets.telegram_bot_token, secrets.telegram_chat_id)

    lines = ["*Daily Bet Bot Report*"] + build_report_lines(db, settings)
    telegram.send_message("\n".join(lines))


if __name__ == "__main__":
    main()
