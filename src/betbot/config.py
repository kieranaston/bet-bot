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
            # Defaults to a local sqlite file so the bot works out of the box for local/VPS
            # runs. For GitHub Actions you MUST set this to a hosted DB (e.g. Supabase
            # Postgres) since the runner's disk doesn't persist between runs.
            database_url=os.environ.get(
                "DATABASE_URL", f"sqlite:///{REPO_ROOT / 'data' / 'betbot.db'}"
            ),
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
    def devig_method(self) -> str:
        return str(self._raw["ev"]["devig_method"])

    @property
    def sports(self) -> list[dict[str, Any]]:
        return self._raw["sports"]

    @property
    def discovery_regions(self) -> str:
        return str(self._raw["odds_api"]["discovery_regions"])

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
    def settlement_enabled(self) -> bool:
        return bool(self._raw["settlement"]["enabled"])

    @property
    def settlement_days_from(self) -> int:
        return int(self._raw["settlement"]["days_from"])

    @property
    def sharp_book_keys(self) -> list[str]:
        return list(self._bookmakers["sharp"]["known_keys"])

    @property
    def ontario_known_keys(self) -> list[str]:
        return list(self._bookmakers["ontario"]["known_keys"])

    @property
    def scan_bookmakers(self) -> str:
        """Comma-separated bookmaker keys for the `bookmakers=` param on real scans --
        Pinnacle + our confirmed Ontario books. 7 keys total, so this prices as 1
        region-equivalent (every group of <=10 named bookmakers = 1 region-equivalent)."""
        return ",".join(self.sharp_book_keys + self.ontario_known_keys)

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
        for group in ("sharp", "ontario"):
            name = self._bookmakers[group].get("display_names", {}).get(bookmaker_key)
            if name:
                return name
        return bookmaker_key


settings = Settings()
