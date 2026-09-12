import datetime as dt
from types import SimpleNamespace
from unittest.mock import MagicMock

from betbot.settlement import auto_settle_pending, grade_alert
from betbot.storage import Alert, Database


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


def _soccer_alert(**kwargs) -> Alert:
    defaults = dict(sport_key="soccer_epl", home_team="Arsenal", away_team="Chelsea")
    defaults.update(kwargs)
    return _alert(**defaults)


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


def test_grade_soccer_h2h_tie_is_loss_not_push():
    # 3-way market: a tied score means the Draw outcome won, so a home-team bet loses --
    # it must NOT be treated as a push like the 2-way (NFL tie) case is.
    alert = _soccer_alert(outcome_name="Arsenal")
    assert grade_alert(alert, home_score=1, away_score=1) == "loss"


def test_grade_soccer_h2h_draw_bet_wins_on_tie():
    alert = _soccer_alert(outcome_name="Draw")
    assert grade_alert(alert, home_score=1, away_score=1) == "win"


def test_grade_soccer_h2h_draw_bet_loses_on_decisive_result():
    alert = _soccer_alert(outcome_name="Draw")
    assert grade_alert(alert, home_score=2, away_score=1) == "loss"


def test_grade_two_way_h2h_tie_is_still_a_push():
    # 2-way sports (e.g. an NFL regular-season tie) have no draw outcome to lose to, so a
    # tied score on a team bet remains a push, as before.
    alert = _alert(sport_key="americanfootball_nfl", outcome_name="Toronto Maple Leafs")
    assert grade_alert(alert, home_score=3, away_score=3) == "push"


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


def _fake_settings(days_from=2, starting_bankroll=1000.0) -> SimpleNamespace:
    return SimpleNamespace(settlement_days_from=days_from, starting_bankroll=starting_bankroll)


def test_auto_settle_skips_games_that_havent_started_yet():
    """A placed bet on a future game can't possibly be `completed` yet -- querying
    /scores for it would just burn a flat-rate credit for nothing every scan until the
    game starts, so it should be excluded before /scores is even called."""
    db = Database("sqlite:///:memory:")
    with db.session() as s:
        s.add(
            _alert(
                status="placed",
                commence_time=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1),
            )
        )

    odds_client = MagicMock()
    telegram = MagicMock()
    settled = auto_settle_pending(db, _fake_settings(), telegram, odds_client)

    assert settled == 0
    odds_client.get_scores.assert_not_called()


def test_auto_settle_queries_scores_for_started_games():
    db = Database("sqlite:///:memory:")
    with db.session() as s:
        s.add(
            _alert(
                status="placed",
                commence_time=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=3),
            )
        )

    odds_client = MagicMock()
    odds_client.get_scores.return_value = []  # game not yet in the scores response
    telegram = MagicMock()
    settled = auto_settle_pending(db, _fake_settings(), telegram, odds_client)

    assert settled == 0
    odds_client.get_scores.assert_called_once_with("icehockey_nhl", days_from=2)
