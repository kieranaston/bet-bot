"""Scan-time gating for when to spend Odds API credits.

The VPS poll loop (and optional GitHub Actions backup) ticks far more often than we want
to hit The Odds API. `current_scan_window_key` / `is_scan_time` decide that using real
Eastern clock time (DST-aware, via zoneinfo) so the schedule stays correct across the
November/March clock changes without anyone having to edit a cron expression.

Re-alerting a still-+EV line is no longer cooldown-gated: once a scan finds a candidate
that clears the EV floor, main._upsert_and_maybe_notify always notifies unless the user
already /placed, /skip'd, or settled that alert identity.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo


def current_scan_window_key(
    now_utc: dt.datetime, scan_times_local: list[str], timezone: str, window_minutes: int
) -> str | None:
    """Returns a stable identifier for the scan window `now_utc` currently falls in (the
    matched slot's local ISO timestamp), or None if it's not within any window. Callers that
    poll far more often than once per window (e.g. a continuously-running loop rather than
    one cron tick per window) can use this to only actually scan once per window instead of
    every poll."""
    local = now_utc.astimezone(ZoneInfo(timezone))
    for time_str in scan_times_local:
        hour, minute = (int(part) for part in time_str.split(":"))
        target = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        elapsed_minutes = (local - target).total_seconds() / 60.0
        if 0 <= elapsed_minutes < window_minutes:
            return target.isoformat()
    return None


def is_scan_time(
    now_utc: dt.datetime, scan_times_local: list[str], timezone: str, window_minutes: int
) -> bool:
    return current_scan_window_key(now_utc, scan_times_local, timezone, window_minutes) is not None
