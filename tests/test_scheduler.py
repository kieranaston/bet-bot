import datetime as dt

from betbot.scheduler import current_scan_window_key, is_scan_time

SCAN_TIMES = ["11:00", "17:00", "23:00"]
TZ = "America/Toronto"


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
