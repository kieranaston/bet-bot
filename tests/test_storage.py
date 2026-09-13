import datetime as dt

import pytest

from betbot.storage import Alert, Database, american_odds


def test_american_odds_favorite():
    # -110 is decimal 1 + 100/110
    assert american_odds(1 + 100 / 110) == "-110"


def test_american_odds_big_favorite():
    assert american_odds(1.5) == "-200"


def test_american_odds_underdog():
    assert american_odds(3.0) == "+200"


def test_american_odds_even_money_boundary():
    assert american_odds(2.0) == "+100"


def test_alert_book_odds_display_uses_american_odds():
    alert = Alert(
        event_id="e1",
        sport_key="s",
        commence_time=None,
        home_team="H",
        away_team="A",
        market="h2h",
        outcome_name="H",
        bookmaker_key="b",
        book_odds=2.5,
        sharp_book_key="pinnacle",
        true_prob=0.4,
        ev_pct=0.0,
        recommended_stake=0.0,
    )
    assert alert.book_odds_display() == "+150"


def test_datetime_columns_stay_timezone_aware_through_sqlite():
    """Regression test: plain DateTime(timezone=True) silently comes back naive from
    SQLite, which crashes should_alert()'s (now - last_alerted_at) the moment a bet gets
    re-evaluated on a later scan. AwareDateTime must prevent that on every datetime column."""
    db = Database("sqlite:///:memory:")
    commence = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=3)
    alerted = dt.datetime.now(dt.timezone.utc)

    with db.session() as s:
        alert = Alert(
            event_id="e1", sport_key="icehockey_nhl", commence_time=commence,
            home_team="H", away_team="A", market="h2h", outcome_name="H",
            bookmaker_key="bet99_ca_on", book_odds=2.0, sharp_book_key="pinnacle",
            true_prob=0.5, ev_pct=3.0, recommended_stake=10.0, last_alerted_at=alerted,
        )
        s.add(alert)
        s.flush()
        alert_id = alert.id

    with db.session() as s:
        reloaded = s.get(Alert, alert_id)
        assert reloaded.commence_time.tzinfo is not None
        assert reloaded.last_alerted_at.tzinfo is not None
        # Must not raise "can't subtract offset-naive and offset-aware datetimes".
        elapsed = (dt.datetime.now(dt.timezone.utc) - reloaded.last_alerted_at).total_seconds()
        assert elapsed >= 0
