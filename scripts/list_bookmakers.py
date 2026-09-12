#!/usr/bin/env python3
"""Discovery helper: print every bookmaker key The Odds API currently returns for a sport
and market, so you can correct/extend config/bookmakers.yaml with real, live keys, or check
whether Pinnacle actually prices a given market for a sport before trusting it in
config/settings.yaml (e.g. the docs warn spreads/totals coverage is patchy outside US
sports -- see the comments above the `sports:` list in config/settings.yaml).

Usage:
    python scripts/list_bookmakers.py americanfootball_nfl
    python scripts/list_bookmakers.py soccer_epl --market spreads
"""
from __future__ import annotations

import argparse

from betbot.config import Secrets, settings
from betbot.odds_client import OddsApiClient


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sport_key", help="e.g. americanfootball_nfl")
    parser.add_argument(
        "--market", default="h2h", help="h2h (default), spreads, or totals"
    )
    args = parser.parse_args()

    secrets = Secrets.from_env()
    client = OddsApiClient(
        api_key=secrets.odds_api_key,
        base_url=settings.odds_api_base_url,
        odds_format=settings.odds_format,
    )
    keys = sorted(
        client.list_bookmaker_keys(
            args.sport_key, markets=[args.market], regions=settings.odds_api_regions
        )
    )
    print(
        f"Bookmaker keys currently returning {args.market!r} for {args.sport_key} "
        f"(regions={settings.odds_api_regions}):\n"
    )
    if "pinnacle" not in keys:
        print("  ** pinnacle is NOT present for this sport/market -- do not rely on it **\n")
    for key in keys:
        tag = " <- in our allowlist" if key in (settings.sharp_book_keys + settings.ontario_known_keys) else ""
        print(f"  {key}{tag}")


if __name__ == "__main__":
    main()
