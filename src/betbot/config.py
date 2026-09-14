"""Load settings.yaml / bookmakers.yaml and environment secrets in one place."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"

load_dotenv(REPO_ROOT / ".env")


def _load_yaml(name: str) -> dict[str, Any]:
    with open(CONFIG_DIR / name, "r") as f:
        return yaml.safe_load(f)


@dataclass(frozen=True)
class Secrets:
    odds_api_key: str
    telegram_bot_token: str
    telegram_chat_id: str
    database_url: str

    @classmethod
    def from_env(cls) -> "Secrets":
        missing = [
            name
            for name in ("ODDS_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
            if not os.environ.get(name)
        ]
        if missing:
            raise RuntimeError(
                f"Missing required environment variable(s): {', '.join(missing)}. "
                "Copy .env.example to .env and fill them in (or set them as GitHub "
                "Actions secrets)."
            )
        return cls(
            odds_api_key=os.environ["ODDS_API_KEY"],
            telegram_bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
            telegram_chat_id=os.environ["TELEGRAM_CHAT_ID"],
            # Defaults to a local sqlite file -- the VPS is the only real deployment as of
            # 2026-09-13 (Supabase/Postgres was dropped, see README's GitHub Actions backup
            # section), so this default is what's actually used in production, not just local
            # dev. A DATABASE_URL would still need to point at a hosted, persistent DB (e.g.
            # Postgres) if the GitHub Actions backup path is ever revived, since that runner's
            # disk doesn't persist between runs -- but nothing is configured for that today.
            database_url=os.environ.get("DATABASE_URL")
            or f"sqlite:///{REPO_ROOT / 'data' / 'betbot.db'}",
        )


class Settings:
    def __init__(self) -> None:
        self._raw = _load_yaml("settings.yaml")
        self._bookmakers = _load_yaml("bookmakers.yaml")

    @property
    def starting_bankroll(self) -> float:
        return float(self._raw["bankroll"]["starting_amount"])

    @property
    def kelly_fraction(self) -> float:
        return float(self._raw["bankroll"]["kelly_fraction"])

    @property
    def max_stake_pct(self) -> float:
        return float(self._raw["bankroll"]["max_stake_pct_of_bankroll"])

    @property
    def min_stake(self) -> float:
        return float(self._raw["bankroll"]["min_stake"])

    @property
    def min_ev_pct(self) -> float:
        return float(self._raw["ev"]["min_ev_pct"])

    @property
    def min_true_prob(self) -> float:
        return float(self._raw["ev"]["min_true_prob"])

    @property
    def devig_method(self) -> str:
        return str(self._raw["ev"]["devig_method"])

    @property
    def sharp_max_staleness_minutes(self) -> float:
        """How old Pinnacle's own last_update can be before betbot.matching.is_fresh treats
        it as unusable and falls back to the consensus basket -- see the comment above this
        key in config/settings.yaml for why (Pinnacle odds are scraped from Pinnacle's public
        website, so gaps/staleness are an expected characteristic of the feed)."""
        return float(self._raw["ev"]["sharp_max_staleness_minutes"])

    @property
    def sports(self) -> list[dict[str, Any]]:
        return self._raw["sports"]

    @property
    def odds_api_regions(self) -> str:
        return str(self._raw["odds_api"]["regions"])

    @property
    def odds_format(self) -> str:
        return str(self._raw["odds_api"]["odds_format"])

    @property
    def odds_api_base_url(self) -> str:
        return str(self._raw["odds_api"]["base_url"])

    @property
    def timezone(self) -> str:
        return str(self._raw["scheduling"]["timezone"])

    @property
    def scan_times_local(self) -> list[str]:
        return list(self._raw["scheduling"]["scan_times_local"])

    @property
    def scan_window_minutes(self) -> int:
        return int(self._raw["scheduling"]["scan_window_minutes"])

    @property
    def scheduling_tiers(self) -> list[dict[str, Any]]:
        return sorted(
            self._raw["scheduling"]["tiers"], key=lambda t: t["max_hours_to_commence"]
        )

    @property
    def max_hours_ahead(self) -> float:
        return float(self._raw["scheduling"]["max_hours_ahead"])

    @property
    def props_scan_times_local(self) -> list[str]:
        return list(self._raw["props"]["scan_times_local"])

    @property
    def props_scan_window_minutes(self) -> int:
        return int(self._raw["props"]["scan_window_minutes"])

    @property
    def props_min_ev_pct(self) -> float:
        return float(self._raw["props"]["min_ev_pct"])

    @property
    def props_max_hours_ahead(self) -> float:
        return float(self._raw["props"]["max_hours_ahead"])

    @property
    def props_pregame_window_hours(self) -> float:
        """The real cost/relevance filter for additional-markets scans: only fetch
        per-event odds for events within this many hours of commence_time -- see the
        comment above config/settings.yaml's `props:` section for why (these books open
        props/alternates close to kickoff, not gradually)."""
        return float(self._raw["props"]["pregame_window_hours"])

    @property
    def props_max_events_per_scan_per_sport(self) -> int:
        return int(self._raw["props"]["max_events_per_scan_per_sport"])

    @property
    def daily_report_time_local(self) -> str:
        return str(self._raw["reporting"]["time_local"])

    @property
    def settlement_enabled(self) -> bool:
        return bool(self._raw["settlement"]["enabled"])

    @property
    def settlement_days_from(self) -> int:
        return int(self._raw["settlement"]["days_from"])

    @property
    def sharp_book_keys(self) -> list[str]:
        return list(self._bookmakers["sharp"]["known_keys"])

    @property
    def consensus_book_keys(self) -> list[str]:
        return list(self._bookmakers["consensus"]["known_keys"])

    @property
    def min_consensus_books(self) -> int:
        return int(self._bookmakers["consensus"]["min_books_required"])

    @property
    def ontario_known_keys(self) -> list[str]:
        return list(self._bookmakers["ontario"]["known_keys"])

    @property
    def scan_bookmakers(self) -> str:
        """Comma-separated bookmaker keys for the `bookmakers=` param on real scans --
        Pinnacle + the 3 consensus books (fanduel/draftkings/betmgm -- fallback reference
        when Pinnacle is absent or stale, see betbot.matching) + our confirmed Ontario
        books. 10 keys total (<=10), confirmed by The Odds API docs to price as 1
        region-equivalent instead of 2 (eu + ca). Deliberately NOT extended with a 4th
        fallback book (e.g. Caesars) -- that would push this to 11 keys, tipping into 2
        region-equivalents and doubling the cost of every single main-market scan
        permanently, not just during a Pinnacle gap."""
        return ",".join(self.sharp_book_keys + self.consensus_book_keys + self.ontario_known_keys)

    @property
    def props_bookmakers(self) -> str:
        """Comma-separated bookmaker keys for per-event odds calls: Pinnacle (sharp
        reference for `game_alt_markets:`) + consensus books (config/bookmakers.yaml
        `consensus:`, reference for `player_markets:`) + our confirmed Ontario books. 10
        keys total (<=10), same 1-region-equivalent pricing as scan_bookmakers."""
        return ",".join(self.sharp_book_keys + self.consensus_book_keys + self.ontario_known_keys)

    @property
    def ontario_auto_match_suffixes(self) -> list[str]:
        return list(self._bookmakers["ontario"]["auto_match_suffixes"])

    def is_ontario_book(self, bookmaker_key: str) -> bool:
        if bookmaker_key in self.ontario_known_keys:
            return True
        return any(
            bookmaker_key.endswith(suffix) for suffix in self.ontario_auto_match_suffixes
        )

    def display_name(self, bookmaker_key: str) -> str:
        """Human-readable book name for Telegram alerts, falling back to the raw API key
        if it's somehow not in our (deliberately closed) allowlist yet."""
        for group in ("sharp", "consensus", "ontario"):
            name = self._bookmakers[group].get("display_names", {}).get(bookmaker_key)
            if name:
                return name
        return bookmaker_key

    def method_display(self, sharp_book_key: str) -> str:
        """Human-readable rendering of Alert.sharp_book_key: either the single sharp book
        ("Pinnacle") or, for player props/game-alt markets devigged via consensus (see
        main.py::_consensus_true_probs), the comma-joined contributing books it stores
        there (e.g. "betmgm,draftkings,fanduel") rendered as "BetMGM + DraftKings +
        FanDuel" -- lets a user see at a glance whether a line's "true" price came from
        Pinnacle or an average of soft books, which matters since the latter is a noisier
        reference (see props.min_ev_pct's higher floor in config/settings.yaml)."""
        return " + ".join(self.display_name(key) for key in sharp_book_key.split(","))

    def homepage_url(self, bookmaker_key: str) -> str | None:
        """Last-resort deep-link fallback (per Odds API docs) when includeLinks didn't
        return an outcome/market/bookmaker link for this book."""
        return self._bookmakers["ontario"].get("homepage_urls", {}).get(bookmaker_key)


settings = Settings()
