"""Scan-time gating and adaptive re-alert cooldown.

The GitHub Actions cron in .github/workflows/betbot-scan.yml ticks a couple of times an hour so
Telegram commands stay responsive, but we only want to actually spend Odds API credits a
few times a day. `is_scan_time` decides that using real Eastern clock time (DST-aware, via
zoneinfo) so the schedule stays correct across the November/March clock changes without
anyone having to edit a cron expression.

`should_alert` is a separate concern: once we *do* scan, this controls how often we'll
re-notify about the same still-open opportunity between scans -- tighter cooldowns for
games about to start, looser for games far out.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo


def is_scan_time(
    now_utc: dt.datetime, scan_times_local: list[str], timezone: str, window_minutes: int
) -> bool:
    local = now_utc.astimezone(ZoneInfo(timezone))
    for time_str in scan_times_local:
        hour, minute = (int(part) for part in time_str.split(":"))
        target = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        elapsed_minutes = (local - target).total_seconds() / 60.0
        if 0 <= elapsed_minutes < window_minutes:
            return True
    return False


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
