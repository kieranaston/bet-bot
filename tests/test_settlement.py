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


def test_grade_alternate_spreads_same_math_as_spreads():
    alert = _alert(market="alternate_spreads", outcome_name="Toronto Maple Leafs", point=-3.5)
    assert grade_alert(alert, home_score=100, away_score=96) == "win"


def test_grade_alternate_totals_same_math_as_totals():
    alert = _alert(market="alternate_totals", outcome_name="Under", point=210.5)
    assert grade_alert(alert, home_score=100, away_score=100) == "win"


def test_grade_team_totals_uses_home_participant_score_not_combined_total():
    alert = _alert(
        market="team_totals", participant="Toronto Maple Leafs",
        outcome_name="Over", point=3.5,
    )
    # Combined total (5) would fail an Over 3.5 on the away team's total alone, but the
    # home team's own score (4) clears it -- this must grade off `participant`, not the sum.
    assert grade_alert(alert, home_score=4, away_score=1) == "win"


def test_grade_team_totals_uses_away_participant_score():
    alert = _alert(
        market="alternate_team_totals", participant="Montreal Canadiens",
        outcome_name="Under", point=2.5,
    )
    assert grade_alert(alert, home_score=4, away_score=3) == "loss"


def test_grade_team_totals_unmatched_participant_returns_none():
    alert = _alert(market="team_totals", participant="Some Other Team", outcome_name="Over", point=3.5)
    assert grade_alert(alert, home_score=4, away_score=1) is None


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


def test_auto_settle_grades_alternate_spreads():
    db = Database("sqlite:///:memory:")
    with db.session() as s:
        s.add(
            _alert(
                market="alternate_spreads", outcome_name="Toronto Maple Leafs", point=-3.5,
                status="placed", placed_stake=10.0, book_odds=2.0,
                commence_time=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=3),
            )
        )

    odds_client = MagicMock()
    odds_client.get_scores.return_value = [
        {
            "id": "e1", "completed": True,
            "scores": [
                {"name": "Toronto Maple Leafs", "score": "5"},
                {"name": "Montreal Canadiens", "score": "1"},
            ],
        }
    ]
    telegram = MagicMock()
    settled = auto_settle_pending(db, _fake_settings(), telegram, odds_client)

    assert settled == 1
    telegram.send_message.assert_called_once()
    assert "WIN" in telegram.send_message.call_args[0][0]


def test_auto_settle_grades_team_totals_off_participant():
    db = Database("sqlite:///:memory:")
    with db.session() as s:
        s.add(
            _alert(
                market="team_totals", participant="Montreal Canadiens",
                outcome_name="Over", point=2.5,
                status="placed", placed_stake=10.0, book_odds=2.0,
                commence_time=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=3),
            )
        )

    odds_client = MagicMock()
    odds_client.get_scores.return_value = [
        {
            "id": "e1", "completed": True,
            "scores": [
                {"name": "Toronto Maple Leafs", "score": "5"},
                {"name": "Montreal Canadiens", "score": "1"},
            ],
        }
    ]
    telegram = MagicMock()
    settled = auto_settle_pending(db, _fake_settings(), telegram, odds_client)

    assert settled == 1
    assert "LOSS" in telegram.send_message.call_args[0][0]


def test_auto_settle_sends_manual_reminder_once_prop_game_completes():
    """/scores never returns player-level box scores, so a placed prop bet can never be
    graded -- but once its game is confirmed `completed`, the bot should still nudge the
    user toward /settle instead of leaving it to sit silently forever."""
    db = Database("sqlite:///:memory:")
    with db.session() as s:
        s.add(
            _alert(
                market="player_points", outcome_name="Over", point=24.5,
                status="placed", participant="Some Player",
                commence_time=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=3),
            )
        )

    odds_client = MagicMock()
    odds_client.get_scores.return_value = [{"id": "e1", "completed": True, "scores": []}]
    telegram = MagicMock()
    settled = auto_settle_pending(db, _fake_settings(), telegram, odds_client)

    assert settled == 0  # can't be graded -- only reminded
    telegram.send_message.assert_called_once()
    assert "/settle" in telegram.send_message.call_args[0][0]

    with db.session() as s:
        alert = s.query(Alert).one()
        assert alert.settlement_reminder_sent_at is not None
        assert alert.status == "placed"  # reminder doesn't change lifecycle status


def test_auto_settle_prop_reminder_not_sent_before_game_completes():
    db = Database("sqlite:///:memory:")
    with db.session() as s:
        s.add(
            _alert(
                market="player_points", outcome_name="Over", point=24.5,
                status="placed", participant="Some Player",
                commence_time=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1),
            )
        )

    odds_client = MagicMock()
    odds_client.get_scores.return_value = []  # game not yet finished/found
    telegram = MagicMock()
    settled = auto_settle_pending(db, _fake_settings(), telegram, odds_client)

    assert settled == 0
    telegram.send_message.assert_not_called()


def test_auto_settle_does_not_repeat_prop_reminder_or_requery_scores():
    """Once a prop bet's reminder has fired, there's nothing more auto-settle can do for it
    (it's stuck until the user runs /settle) -- it should drop out of the query entirely so
    it doesn't keep paying for a /scores call on its behalf every scan forever."""
    db = Database("sqlite:///:memory:")
    with db.session() as s:
        s.add(
            _alert(
                market="player_points", outcome_name="Over", point=24.5,
                status="placed", participant="Some Player",
                commence_time=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=3),
                settlement_reminder_sent_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1),
            )
        )

    odds_client = MagicMock()
    telegram = MagicMock()
    settled = auto_settle_pending(db, _fake_settings(), telegram, odds_client)

    assert settled == 0
    odds_client.get_scores.assert_not_called()
    telegram.send_message.assert_not_called()
