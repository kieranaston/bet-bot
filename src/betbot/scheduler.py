"""Adaptive re-alert cooldown: decide whether a given alert is stale enough to re-send.

The GitHub Actions cron (see .github/workflows/scan.yml) controls how often the bot *checks*
the odds. This module controls how often it will re-*notify* you about the same opportunity
between checks -- tighter cooldowns for games about to start (where lines move fast and
staying current matters more), looser cooldowns for games far out.
"""
from __future__ import annotations

import datetime as dt


def cooldown_minutes_for(hours_to_commence: float, tiers: list[dict]) -> float:
    for tier in tiers:  # tiers is pre-sorted ascending by max_hours_to_commence
        if hours_to_commence <= tier["max_hours_to_commence"]:
            return float(tier["cooldown_minutes"])
    return float(tiers[-1]["cooldown_minutes"])


def should_alert(
    hours_to_commence: float,
    tiers: list[dict],
    last_alerted_at: dt.datetime | None,
    now: dt.datetime,
    price_changed: bool,
) -> bool:
    if last_alerted_at is None:
        return True
    if price_changed:
        return True
    cooldown = cooldown_minutes_for(hours_to_commence, tiers)
    elapsed_minutes = (now - last_alerted_at).total_seconds() / 60.0
    return elapsed_minutes >= cooldown
