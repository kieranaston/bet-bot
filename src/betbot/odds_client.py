"""Thin wrapper around The Odds API v4 (https://the-odds-api.com/liveapi/guides/v4/).

Covers three endpoints (cost formulas confirmed against crawled docs in
api-docs/docs_markdown/, not just an AI summary of the docs page):
  - /sports/{sport}/events  -- free (no quota cost). An empty /odds response also costs 0,
    so this precheck saves round-trips/rate-limit headroom rather than credits per se, but
    it's still used to skip sports with nothing upcoming before even trying /odds.
  - /sports/{sport}/odds    -- cost = [markets] x [region-equivalents]. Real scans use
    `bookmakers=` (our fixed 7-book allowlist, built from config/bookmakers.yaml) rather
    than `regions=`: the docs confirm "every group of 10 bookmakers is the equivalent of
    1 region", so our 7 books cost 1 region-equivalent instead of the 2 regions
    `regions=eu,ca` would need for the same data. `regions=` is kept for
    scripts/list_bookmakers.py's broad discovery use.
  - /sports/{sport}/scores  -- 1 credit/request normally, 2 credits if `daysFrom` is set
    (needed to see completed games) -- used for automatic bet settlement instead of a
    secondary results API.
"""
from __future__ import annotations

import datetime as dt
import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Docs (api-docs/docs_markdown/liveapi_guides_v4_api-error-codes.html.md, EXCEEDED_FREQ_LIMIT):
# on a 429, "consider retrying the request after a couple of seconds."
RATE_LIMIT_RETRIES = 2
RATE_LIMIT_BACKOFF_SECONDS = 2.0


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
        attempt = 0
        while True:
            resp = requests.get(url, params=params, timeout=30)
            remaining = resp.headers.get("x-requests-remaining")
            used = resp.headers.get("x-requests-used")
            last = resp.headers.get("x-requests-last")
            if remaining is not None:
                logger.info(
                    "Odds API usage for %s: used=%s remaining=%s cost_of_this_call=%s",
                    log_label, used, remaining, last,
                )
            if resp.status_code == 429 and attempt < RATE_LIMIT_RETRIES:
                attempt += 1
                wait = RATE_LIMIT_BACKOFF_SECONDS * attempt
                logger.warning(
                    "Odds API rate-limited for %s (attempt %d/%d) -- retrying in %.0fs",
                    log_label, attempt, RATE_LIMIT_RETRIES, wait,
                )
                time.sleep(wait)
                continue
            if resp.status_code != 200:
                raise OddsApiError(
                    f"The Odds API returned {resp.status_code} for {log_label}: {resp.text[:500]}"
                )
            return resp.json()

    def list_sports(self, all_sports: bool = False) -> list[dict[str, Any]]:
        """Free -- no quota cost. Returns every currently valid sport key (in-season only,
        unless all_sports=True), each with a "key", "title", and "active" flag. Use this to
        confirm a sport key is real and in-season before adding it to config/settings.yaml
        -- e.g. tennis has historically used per-tournament keys rather than one persistent
        key, so check here rather than guessing."""
        params: dict[str, Any] = {"apiKey": self.api_key}
        if all_sports:
            params["all"] = "true"
        return self._get("/sports", params, "sports list (free)")

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
