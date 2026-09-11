"""Thin wrapper around The Odds API v4 (https://the-odds-api.com/liveapi/guides/v4/).

Covers three endpoints:
  - /sports/{sport}/events  -- free (no quota cost), used to check whether a sport has
    anything upcoming before spending credits on /odds.
  - /sports/{sport}/odds    -- the paid endpoint. Cost = markets x region-equivalents.
    Using `bookmakers=` (our fixed 7-book allowlist) instead of `regions=` costs 1
    region-equivalent (every group of <=10 named bookmakers = 1 region) instead of 2
    (eu for Pinnacle + ca for Ontario books) -- half the cost for the same data.
  - /sports/{sport}/scores  -- flat 2 credits/request (with daysFrom set), used for
    automatic bet settlement instead of a secondary results API.
"""
from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Any

import requests

logger = logging.getLogger(__name__)


class OddsApiError(RuntimeError):
    pass


def _iso(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class OddsApiClient:
    api_key: str
    base_url: str
    odds_format: str = "decimal"

    def _get(self, path: str, params: dict[str, Any], log_label: str) -> Any:
        url = f"{self.base_url}{path}"
        resp = requests.get(url, params=params, timeout=30)
        remaining = resp.headers.get("x-requests-remaining")
        used = resp.headers.get("x-requests-used")
        if remaining is not None:
            logger.info("Odds API usage for %s: used=%s remaining=%s", log_label, used, remaining)
        if resp.status_code != 200:
            raise OddsApiError(
                f"The Odds API returned {resp.status_code} for {log_label}: {resp.text[:500]}"
            )
        return resp.json()

    def get_events(
        self,
        sport_key: str,
        commence_time_from: dt.datetime | None = None,
        commence_time_to: dt.datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Free -- no quota cost. Just event ids/teams/commence times, no odds."""
        params: dict[str, Any] = {"apiKey": self.api_key, "dateFormat": "iso"}
        if commence_time_from is not None:
            params["commenceTimeFrom"] = _iso(commence_time_from)
        if commence_time_to is not None:
            params["commenceTimeTo"] = _iso(commence_time_to)
        return self._get(f"/sports/{sport_key}/events", params, f"{sport_key} (events, free)")

    def get_odds(
        self,
        sport_key: str,
        markets: list[str],
        bookmakers: str | None = None,
        regions: str | None = None,
        commence_time_from: dt.datetime | None = None,
        commence_time_to: dt.datetime | None = None,
        include_links: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch odds for upcoming events in a sport for the given markets.

        Exactly one of `bookmakers` (comma-separated bookmaker keys -- what betbot.main
        uses for real scans, since our allowlist is fixed and small) or `regions`
        (comma-separated region codes -- what scripts/list_bookmakers.py uses for broad
        discovery) must be given; they're mutually exclusive on The Odds API side.

        Returns the raw list of event dicts as documented at:
        https://the-odds-api.com/liveapi/guides/v4/#get-odds
        """
        if bool(bookmakers) == bool(regions):
            raise ValueError("Specify exactly one of bookmakers= or regions=")
        params: dict[str, Any] = {
            "apiKey": self.api_key,
            "markets": ",".join(markets),
            "oddsFormat": self.odds_format,
            "dateFormat": "iso",
        }
        if bookmakers:
            params["bookmakers"] = bookmakers
        else:
            params["regions"] = regions
        if commence_time_from is not None:
            params["commenceTimeFrom"] = _iso(commence_time_from)
        if commence_time_to is not None:
            params["commenceTimeTo"] = _iso(commence_time_to)
        if include_links:
            params["includeLinks"] = "true"
        return self._get(f"/sports/{sport_key}/odds", params, sport_key)

    def get_scores(self, sport_key: str, days_from: int | None = None) -> list[dict[str, Any]]:
        """1 credit/request normally, 2 if `days_from` is set (needed to see completed
        games -- without it you only get live/upcoming, never `completed: true`)."""
        params: dict[str, Any] = {"apiKey": self.api_key, "dateFormat": "iso"}
        if days_from is not None:
            params["daysFrom"] = days_from
        return self._get(f"/sports/{sport_key}/scores", params, f"{sport_key} (scores)")

    def list_bookmaker_keys(self, sport_key: str, markets: list[str], regions: str) -> set[str]:
        """Helper for scripts/list_bookmakers.py -- returns every distinct bookmaker key seen
        across all events currently returned for a sport, using broad region discovery."""
        events = self.get_odds(sport_key, markets, regions=regions)
        keys: set[str] = set()
        for event in events:
            for bm in event.get("bookmakers", []):
                keys.add(bm["key"])
        return keys
