#!/usr/bin/env python3
"""Discovery helper for player props, mirroring scripts/list_bookmakers.py's role: prints
which bookmakers are actually returning data right now for each configured
`player_markets` key, for one live event. scripts/list_bookmakers.py can't be reused here
-- it calls the bulk /odds endpoint, which rejects "additional markets" (player props)
outright with INVALID_MARKET; these only work one event at a time via
OddsApiClient.get_event_odds.

Live-verify with this before trusting config/settings.yaml's `player_markets:` lists or
config/bookmakers.yaml's `consensus:` book keys -- both drift over time, same as the
sharp/Ontario keys scripts/list_bookmakers.py already guards.

Also prints the GROUND-TRUTH market list each Ontario book has actually opened for the
event (via OddsApiClient.get_event_markets, 1 credit) -- this is what actually answers "is
this sport just not supported, or did I just not check closely enough / too early" (see
chat 2026-09-13): an empty result for your guessed `player_markets` list is ambiguous, but
seeing the book has opened 15+ other markets (alternates, halves, team totals, ...) for
this exact event and zero of them are player props is a real answer, not an inference.

Usage:
    python scripts/list_event_markets.py americanfootball_nfl
    python scripts/list_event_markets.py basketball_nba
"""
from __future__ import annotations

import argparse
import datetime as dt

from betbot.config import Secrets, settings
from betbot.odds_client import OddsApiClient, OddsApiError


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sport_key", help="e.g. americanfootball_nfl")
    args = parser.parse_args()

    sport_cfg = next((s for s in settings.sports if s["key"] == args.sport_key), None)
    player_markets = (sport_cfg or {}).get("player_markets")
    if not player_markets:
        raise SystemExit(
            f"{args.sport_key!r} has no `player_markets:` configured in "
            "config/settings.yaml -- nothing to check."
        )

    secrets = Secrets.from_env()
    client = OddsApiClient(
        api_key=secrets.odds_api_key,
        base_url=settings.odds_api_base_url,
        odds_format=settings.odds_format,
    )

    now = dt.datetime.now(dt.timezone.utc)
    events = client.get_events(
        args.sport_key, now, now + dt.timedelta(hours=settings.props_max_hours_ahead)
    )
    if not events:
        raise SystemExit(
            f"No upcoming {args.sport_key} events in the next "
            f"{settings.props_max_hours_ahead:.0f}h -- nothing to check right now."
        )
    event = events[0]
    print(
        f"Checking {event['away_team']} @ {event['home_team']} "
        f"({event['commence_time']}), markets={player_markets}\n"
    )

    try:
        odds = client.get_event_odds(
            args.sport_key, event["id"], player_markets, regions="us"
        )
    except OddsApiError as exc:
        raise SystemExit(f"get_event_odds failed: {exc}")

    seen: dict[str, set[str]] = {m: set() for m in player_markets}
    for bm in odds.get("bookmakers", []):
        for market in bm.get("markets", []):
            if market["key"] in seen:
                seen[market["key"]].add(bm["key"])

    consensus_keys = set(settings.consensus_book_keys)
    for market_key in player_markets:
        books = seen[market_key]
        if not books:
            print(f"  {market_key}: ** no bookmaker returned this market for this event **")
            continue
        tags = [
            f"{b}{' <- consensus' if b in consensus_keys else ''}"
            for b in sorted(books)
        ]
        print(f"  {market_key}: {', '.join(tags)}")

    missing_consensus = consensus_keys - {
        b for books in seen.values() for b in books if b in consensus_keys
    }
    if missing_consensus:
        print(
            f"\n** consensus book(s) not seen for ANY of these markets on this event: "
            f"{sorted(missing_consensus)} -- may need a different key or don't cover "
            f"this sport **"
        )

    print("\nGround truth -- ALL markets each Ontario book has actually opened for this "
          "event (not just the player_markets list above):")
    ontario_keys = ",".join(settings.ontario_known_keys)
    try:
        market_data = client.get_event_markets(args.sport_key, event["id"], bookmakers=ontario_keys)
    except OddsApiError as exc:
        print(f"  get_event_markets failed: {exc}")
        return
    opened = {bm["key"]: sorted(m["key"] for m in bm.get("markets", [])) for bm in market_data.get("bookmakers", [])}
    if not opened:
        print("  ** no Ontario book has opened ANY market for this event yet -- this "
              "specific book/event pair has no coverage at all, not just no props **")
    def is_player_prop(key: str) -> bool:
        # Any additional-market key naming a player/batter/pitcher, not just our
        # currently-configured player_markets list -- catches a market we haven't
        # thought to add yet, not only the ones we already guessed at.
        return key.startswith(("player_", "batter_", "pitcher_"))

    for book in settings.ontario_known_keys:
        keys = opened.get(book)
        if keys is None:
            print(f"  {book}: not covering this event at all")
        else:
            player_keys = [k for k in keys if is_player_prop(k)]
            other_keys = [k for k in keys if not is_player_prop(k)]
            print(f"  {book}: {len(keys)} market(s) opened -- {len(player_keys)} are "
                  f"player props {player_keys or '(none)'}; others: {other_keys}")


if __name__ == "__main__":
    main()
