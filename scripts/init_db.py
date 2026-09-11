#!/usr/bin/env python3
"""One-off helper to create tables and seed the starting bankroll. Not required -- the bot
creates tables automatically on first run -- but handy for inspecting a fresh DB locally."""
from __future__ import annotations

from betbot.config import Secrets, settings
from betbot.storage import Database


def main() -> None:
    secrets = Secrets.from_env()
    db = Database(secrets.database_url)
    bankroll = db.current_bankroll(settings.starting_bankroll)
    print(f"DB ready at {secrets.database_url}. Current bankroll: ${bankroll:,.2f}")


if __name__ == "__main__":
    main()
