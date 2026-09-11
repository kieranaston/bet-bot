import datetime as dt

from betbot.scheduler import cooldown_minutes_for, should_alert

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
