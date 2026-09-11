from betbot.settlement import grade_alert
from betbot.storage import Alert


def _alert(**kwargs) -> Alert:
    defaults = dict(
        event_id="e1",
        sport_key="icehockey_nhl",
        home_team="Toronto Maple Leafs",
        away_team="Montreal Canadiens",
        market="h2h",
        outcome_name="Toronto Maple Leafs",
        point=None,
        bookmaker_key="bet99_ca_on",
        book_odds=2.0,
        sharp_book_key="pinnacle",
        true_prob=0.5,
        ev_pct=5.0,
        recommended_stake=10.0,
    )
    defaults.update(kwargs)
    return Alert(**defaults)


def test_grade_h2h_win():
    alert = _alert(outcome_name="Toronto Maple Leafs")
    assert grade_alert(alert, home_score=4, away_score=2) == "win"


def test_grade_h2h_loss():
    alert = _alert(outcome_name="Toronto Maple Leafs")
    assert grade_alert(alert, home_score=2, away_score=4) == "loss"


def test_grade_h2h_push_on_tie():
    alert = _alert(outcome_name="Toronto Maple Leafs")
    assert grade_alert(alert, home_score=3, away_score=3) == "push"


def test_grade_h2h_unmatched_outcome_returns_none():
    alert = _alert(outcome_name="Some Other Team")
    assert grade_alert(alert, home_score=4, away_score=2) is None


def test_grade_spread_home_covers():
    # Home team -3.5, wins by 4 -> covers.
    alert = _alert(market="spreads", outcome_name="Toronto Maple Leafs", point=-3.5)
    assert grade_alert(alert, home_score=100, away_score=96) == "win"


def test_grade_spread_home_fails_to_cover():
    # Home team -3.5, wins by only 2 -> doesn't cover.
    alert = _alert(market="spreads", outcome_name="Toronto Maple Leafs", point=-3.5)
    assert grade_alert(alert, home_score=100, away_score=98) == "loss"


def test_grade_spread_push_on_whole_number_line():
    # Away team +3, loses by exactly 3 -> push.
    alert = _alert(market="spreads", outcome_name="Montreal Canadiens", point=3.0)
    assert grade_alert(alert, home_score=103, away_score=100) == "push"


def test_grade_totals_over_win():
    alert = _alert(market="totals", outcome_name="Over", point=210.5)
    assert grade_alert(alert, home_score=110, away_score=105) == "win"


def test_grade_totals_under_win():
    alert = _alert(market="totals", outcome_name="Under", point=210.5)
    assert grade_alert(alert, home_score=100, away_score=100) == "win"


def test_grade_totals_push_on_whole_number_line():
    alert = _alert(market="totals", outcome_name="Over", point=210.0)
    assert grade_alert(alert, home_score=110, away_score=100) == "push"
