import datetime as dt

import pytest
from sqlalchemy.exc import IntegrityError

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


def _prop_alert_kwargs(**overrides) -> dict:
    defaults = dict(
        event_id="e1", sport_key="basketball_nba", commence_time=dt.datetime.now(dt.timezone.utc),
        home_team="H", away_team="A", market="player_points", outcome_name="Over", point=24.5,
        bookmaker_key="bet99_ca_on", book_odds=2.0, sharp_book_key="fanduel,draftkings",
        true_prob=0.5, ev_pct=5.0, recommended_stake=10.0,
    )
    defaults.update(overrides)
    return defaults


def test_alert_participant_defaults_to_empty_string_for_team_markets():
    db = Database("sqlite:///:memory:")
    with db.session() as s:
        alert = Alert(
            event_id="e1", sport_key="s", commence_time=dt.datetime.now(dt.timezone.utc),
            home_team="H", away_team="A", market="h2h", outcome_name="H",
            bookmaker_key="b", book_odds=2.0, sharp_book_key="pinnacle",
            true_prob=0.5, ev_pct=5.0, recommended_stake=10.0,
        )
        s.add(alert)
        s.flush()
        alert_id = alert.id
    with db.session() as s:
        assert s.get(Alert, alert_id).participant == ""


def test_alert_outcome_display_prefixes_participant_for_props():
    alert = Alert(**_prop_alert_kwargs(participant="P. Mahomes"))
    assert alert.outcome_display() == "P. Mahomes Over 24.5"


def test_alert_uniqueness_allows_different_participants_same_line():
    """Two different players sharing an otherwise-identical (event, market, outcome,
    point, bookmaker) must both be storable -- this is exactly why `participant` is part
    of uq_alert_identity, not just outcome_name/point."""
    db = Database("sqlite:///:memory:")
    with db.session() as s:
        s.add(Alert(**_prop_alert_kwargs(participant="Player A")))
        s.add(Alert(**_prop_alert_kwargs(participant="Player B")))
    with db.session() as s:
        assert s.query(Alert).count() == 2


def test_alert_uniqueness_still_rejects_true_duplicate():
    db = Database("sqlite:///:memory:")
    with db.session() as s:
        s.add(Alert(**_prop_alert_kwargs(participant="Player A")))
    with pytest.raises(IntegrityError):
        with db.session() as s:
            s.add(Alert(**_prop_alert_kwargs(participant="Player A")))


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
