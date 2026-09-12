import pytest

from betbot.storage import Alert, american_odds


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
