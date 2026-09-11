#!/usr/bin/env python3
"""Discovery helper: print every bookmaker key The Odds API currently returns for a sport,
so you can correct/extend config/bookmakers.yaml with real, live keys.

Usage:
    python scripts/list_bookmakers.py americanfootball_nfl
"""
from __future__ import annotations

import sys

from betbot.config import Secrets, settings
from betbot.odds_client import OddsApiClient


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <sport_key>  (e.g. americanfootball_nfl)")
        sys.exit(1)
    sport_key = sys.argv[1]

    secrets = Secrets.from_env()
    client = OddsApiClient(
        api_key=secrets.odds_api_key,
        base_url=settings.odds_api_base_url,
        regions=settings.odds_api_regions,
        odds_format=settings.odds_format,
    )
    keys = sorted(client.list_bookmaker_keys(sport_key, markets=["h2h"]))
    print(f"Bookmaker keys currently returned for {sport_key} (regions={settings.odds_api_regions}):\n")
    for key in keys:
        tag = " <- Ontario (auto-matched)" if settings.is_ontario_book(key) else ""
        print(f"  {key}{tag}")


if __name__ == "__main__":
    main()
