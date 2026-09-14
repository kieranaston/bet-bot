"""Thin wrapper around The Odds API v4 (https://the-odds-api.com/liveapi/guides/v4/).

Covers five endpoints (cost formulas confirmed against crawled docs in
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
  - /sports/{sport}/events/{eventId}/odds -- same cost formula as /odds, but for
    "additional markets" (player props, alternate lines) which the bulk /odds endpoint
    rejects outright. Charged per event, not once per sport -- see get_event_odds.
  - /sports/{sport}/events/{eventId}/markets -- 1 credit/call flat. Ground truth: every
    market key a bookmaker has actually opened for one event, no market list to guess at
    upfront -- see get_event_markets. Used for discovery (scripts/list_event_markets.py),
    never in a real scan.
  - /sports/{sport}/scores  -- 1 credit/request normally, 2 credits if `daysFrom` is set
    (needed to see completed games) -- used for automatic bet settlement instead of a
    secondary results API.
"""
from __future__ import annotations

import datetime as dt
import logging
import time
from dataclasses import dataclass, field
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
    last_headers: dict[str, str | None] = field(default_factory=dict)

    def _get(self, path: str, params: dict[str, Any], log_label: str) -> Any:
        url = f"{self.base_url}{path}"
        attempt = 0
        while True:
            try:
                resp = requests.get(url, params=params, timeout=30)
            except requests.exceptions.RequestException as exc:
                # A transport-level failure (timeout, DNS, connection reset) raises here
                # before any response exists, so there's no status code to check -- wrap it
                # as OddsApiError so callers' existing `except OddsApiError: skip this sport`
                # handling covers this too, instead of crashing the whole run.
                raise OddsApiError(f"Network error calling {log_label}: {exc}") from exc
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
            # Stashed so get_quota() can report the latest usage snapshot without assuming
            # any particular prior call happened this run.
            self.last_headers = {"used": used, "remaining": remaining, "last": last}
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

    def get_quota(self) -> dict[str, str | None]:
        """On-demand usage snapshot: {"used", "remaining", "last"} (all usage-credit counts
        as strings, per the API). Piggybacks on the free /sports call so checking quota never
        itself costs quota -- see list_sports."""
        self.list_sports()
        return self.last_headers

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

    def get_event_odds(
        self,
        sport_key: str,
        event_id: str,
        markets: list[str],
        bookmakers: str | None = None,
        regions: str | None = None,
        include_links: bool = False,
    ) -> dict[str, Any]:
        """Fetch odds for a single event, for markets not available on the bulk /odds
        endpoint (player props, alternate lines, period markets -- "additional markets"
        per the docs). Cost = [unique markets returned] x [region-equivalents], charged
        per call -- unlike get_odds, there is no per-sport batching here, so callers own
        capping how many events they fetch per scan.

        Exactly one of `bookmakers` or `regions` must be given, same as get_odds.
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
        if include_links:
            params["includeLinks"] = "true"
        return self._get(
            f"/sports/{sport_key}/events/{event_id}/odds",
            params,
            f"{sport_key} (event {event_id} odds)",
        )

    def get_event_markets(
        self,
        sport_key: str,
        event_id: str,
        bookmakers: str | None = None,
        regions: str | None = None,
    ) -> dict[str, Any]:
        """Ground truth: every market key each bookmaker has actually opened for one
        event -- no market-key list to guess at upfront, unlike get_event_odds. "Only
        returns recently seen market keys... not a comprehensive list of all supported
        markets" (docs) -- a book can still open a market later as the event approaches.
        Flat 1 credit/call regardless of how many bookmakers/markets come back. Discovery
        use only (scripts/list_event_markets.py) -- never called from a real scan.

        Exactly one of `bookmakers` or `regions` must be given, same as get_odds.
        """
        if bool(bookmakers) == bool(regions):
            raise ValueError("Specify exactly one of bookmakers= or regions=")
        params: dict[str, Any] = {"apiKey": self.api_key, "dateFormat": "iso"}
        if bookmakers:
            params["bookmakers"] = bookmakers
        else:
            params["regions"] = regions
        return self._get(
            f"/sports/{sport_key}/events/{event_id}/markets",
            params,
            f"{sport_key} (event {event_id} markets, 1 credit)",
        )

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
