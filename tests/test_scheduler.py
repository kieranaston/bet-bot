import datetime as dt

from betbot.scheduler import (
    cooldown_minutes_for,
    current_scan_window_key,
    is_scan_time,
    should_alert,
)

SCAN_TIMES = ["11:00", "17:00", "23:00"]
TZ = "America/Toronto"

TIERS = [
    {"max_hours_to_commence": 1, "cooldown_minutes": 5},
    {"max_hours_to_commence": 6, "cooldown_minutes": 15},
    {"max_hours_to_commence": 24, "cooldown_minutes": 60},
    {"max_hours_to_commence": 999999, "cooldown_minutes": 120},
]


def test_cooldown_picks_correct_tier():
    assert cooldown_minutes_for(0.5, TIERS) == 5
    assert cooldown_minutes_for(3, TIERS) == 15
    assert cooldown_minutes_for(12, TIERS) == 60
    assert cooldown_minutes_for(1000, TIERS) == 120


def test_should_alert_first_time_always_true():
    now = dt.datetime.now(dt.timezone.utc)
    assert should_alert(12, TIERS, None, now, price_changed=False) is True


def test_should_alert_true_if_price_changed_even_within_cooldown():
    now = dt.datetime.now(dt.timezone.utc)
    last = now - dt.timedelta(minutes=1)
    assert should_alert(12, TIERS, last, now, price_changed=True) is True


def test_should_alert_false_within_cooldown_no_price_change():
    now = dt.datetime.now(dt.timezone.utc)
    last = now - dt.timedelta(minutes=1)
    assert should_alert(12, TIERS, last, now, price_changed=False) is False


def test_should_alert_true_after_cooldown_elapses():
    now = dt.datetime.now(dt.timezone.utc)
    last = now - dt.timedelta(minutes=61)
    assert should_alert(12, TIERS, last, now, price_changed=False) is True


def test_is_scan_time_handles_edt():
    # July 15 2026 is EDT (UTC-4). 11:00 ET = 15:00 UTC.
    now = dt.datetime(2026, 7, 15, 15, 3, tzinfo=dt.timezone.utc)
    assert is_scan_time(now, SCAN_TIMES, TZ, window_minutes=10) is True


def test_is_scan_time_handles_est():
    # January 15 2026 is EST (UTC-5). 11:00 ET = 16:00 UTC.
    now = dt.datetime(2026, 1, 15, 16, 3, tzinfo=dt.timezone.utc)
    assert is_scan_time(now, SCAN_TIMES, TZ, window_minutes=10) is True


def test_is_scan_time_false_outside_window():
    # EDT: 11:00 ET = 15:00 UTC. 15:15 UTC is past the 10-minute window.
    now = dt.datetime(2026, 7, 15, 15, 15, tzinfo=dt.timezone.utc)
    assert is_scan_time(now, SCAN_TIMES, TZ, window_minutes=10) is False


def test_is_scan_time_false_wrong_hour():
    now = dt.datetime(2026, 7, 15, 12, 0, tzinfo=dt.timezone.utc)
    assert is_scan_time(now, SCAN_TIMES, TZ, window_minutes=10) is False


def test_current_scan_window_key_stable_across_the_same_window():
    # Two polls three minutes apart, both inside the same 10-minute window, must produce
    # the identical key -- this is what lets a tight poll loop scan only once per window.
    first = dt.datetime(2026, 7, 15, 15, 1, tzinfo=dt.timezone.utc)
    second = dt.datetime(2026, 7, 15, 15, 4, tzinfo=dt.timezone.utc)
    key1 = current_scan_window_key(first, SCAN_TIMES, TZ, window_minutes=10)
    key2 = current_scan_window_key(second, SCAN_TIMES, TZ, window_minutes=10)
    assert key1 is not None
    assert key1 == key2


def test_current_scan_window_key_differs_across_windows():
    first_window = dt.datetime(2026, 7, 15, 15, 3, tzinfo=dt.timezone.utc)  # 11:00 ET window
    second_window = dt.datetime(2026, 7, 15, 21, 3, tzinfo=dt.timezone.utc)  # 17:00 ET window
    key1 = current_scan_window_key(first_window, SCAN_TIMES, TZ, window_minutes=10)
    key2 = current_scan_window_key(second_window, SCAN_TIMES, TZ, window_minutes=10)
    assert key1 is not None and key2 is not None
    assert key1 != key2


def test_current_scan_window_key_none_outside_window():
    now = dt.datetime(2026, 7, 15, 12, 0, tzinfo=dt.timezone.utc)
    assert current_scan_window_key(now, SCAN_TIMES, TZ, window_minutes=10) is None
