import datetime as dt
from unittest.mock import MagicMock

from betbot.main import process_event
from betbot.storage import Alert, Database


def _event(bookmakers: list[dict], hours_to_commence: float = 3.0) -> dict:
    commence = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=hours_to_commence)
    return {
        "id": "evt1",
        "commence_time": commence.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "home_team": "Home Team",
        "away_team": "Away Team",
        "bookmakers": bookmakers,
    }


def _bookmaker(key: str, outcomes: list[dict]) -> dict:
    return {"key": key, "markets": [{"key": "h2h", "outcomes": outcomes}]}


def test_process_event_alerts_only_the_best_priced_book_for_the_same_outcome():
    """Two Ontario books both offer +EV on the same outcome -- this must produce exactly
    one alert, at the better price, not one alert per qualifying book (that reads as
    duplicate notifications for what's really a single betting decision)."""
    db = Database("sqlite:///:memory:")
    telegram = MagicMock()

    sharp = _bookmaker(
        "pinnacle", [{"name": "Home Team", "price": 1.91}, {"name": "Away Team", "price": 1.91}]
    )
    worse_book = _bookmaker(
        "betano_ca_on",
        [{"name": "Home Team", "price": 2.05}, {"name": "Away Team", "price": 1.80}],
    )
    better_book = _bookmaker(
        "bet99_ca_on",
        [{"name": "Home Team", "price": 2.20}, {"name": "Away Team", "price": 1.75}],
    )
    event = _event([sharp, worse_book, better_book])

    sent = process_event(
        db, telegram, event, "americanfootball_nfl", ["h2h"],
        bankroll=1000.0, now=dt.datetime.now(dt.timezone.utc),
    )

    assert sent == 1
    with db.session() as s:
        alerts = s.query(Alert).all()
        assert len(alerts) == 1
        assert alerts[0].bookmaker_key == "bet99_ca_on"
        assert alerts[0].book_odds == 2.20


def test_process_event_alerts_both_sides_of_a_market_independently():
    """Different outcomes (e.g. the home vs. away side of a spread) are legitimately
    different bets and must both still alert -- the best-book fix only dedupes the SAME
    outcome+point across books, not different outcomes from each other."""
    db = Database("sqlite:///:memory:")
    telegram = MagicMock()

    sharp = _bookmaker(
        "pinnacle",
        [
            {"name": "Home Team", "point": -3.0, "price": 1.91},
            {"name": "Away Team", "point": 3.0, "price": 1.91},
        ],
    )
    book = _bookmaker(
        "bet99_ca_on",
        [
            {"name": "Home Team", "point": -3.0, "price": 2.05},
            {"name": "Away Team", "point": 3.0, "price": 2.10},
        ],
    )
    event = _event([sharp, book])
    for bm in (sharp, book):
        bm["markets"][0]["key"] = "spreads"

    sent = process_event(
        db, telegram, event, "americanfootball_nfl", ["spreads"],
        bankroll=1000.0, now=dt.datetime.now(dt.timezone.utc),
    )

    assert sent == 2
    with db.session() as s:
        names = sorted(a.outcome_name for a in s.query(Alert).all())
        assert names == ["Away Team", "Home Team"]
