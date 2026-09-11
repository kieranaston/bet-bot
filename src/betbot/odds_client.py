"""Thin wrapper around The Odds API v4 (https://the-odds-api.com/liveapi/guides/v4/)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import requests

logger = logging.getLogger(__name__)


class OddsApiError(RuntimeError):
    pass


@dataclass
class OddsApiClient:
    api_key: str
    base_url: str
    regions: str
    odds_format: str = "decimal"

    def get_odds(self, sport_key: str, markets: list[str]) -> list[dict[str, Any]]:
        """Fetch odds for every upcoming event in a sport for the given markets.

        Returns the raw list of event dicts as documented at:
        https://the-odds-api.com/liveapi/guides/v4/#get-odds
        """
        url = f"{self.base_url}/sports/{sport_key}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": self.regions,
            "markets": ",".join(markets),
            "oddsFormat": self.odds_format,
            "dateFormat": "iso",
        }
        resp = requests.get(url, params=params, timeout=30)
        remaining = resp.headers.get("x-requests-remaining")
        used = resp.headers.get("x-requests-used")
        if remaining is not None:
            logger.info(
                "Odds API usage for %s: used=%s remaining=%s", sport_key, used, remaining
            )
        if resp.status_code != 200:
            raise OddsApiError(
                f"The Odds API returned {resp.status_code} for {sport_key}: {resp.text[:500]}"
            )
        return resp.json()

    def list_bookmaker_keys(self, sport_key: str, markets: list[str]) -> set[str]:
        """Helper for scripts/list_bookmakers.py -- returns every distinct bookmaker key seen
        across all events currently returned for a sport."""
        events = self.get_odds(sport_key, markets)
        keys: set[str] = set()
        for event in events:
            for bm in event.get("bookmakers", []):
                keys.add(bm["key"])
        return keys
