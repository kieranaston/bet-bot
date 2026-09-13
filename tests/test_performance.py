import datetime as dt
from types import SimpleNamespace

from betbot.performance import build_report_lines, summarize
from betbot.storage import Alert, Database


def _fake_settings(starting_bankroll: float = 1000.0) -> SimpleNamespace:
    return SimpleNamespace(starting_bankroll=starting_bankroll)


def _db() -> Database:
    return Database("sqlite:///:memory:")


def _insert_alert(db: Database, **kwargs) -> int:
    defaults = dict(
        event_id="e1",
        sport_key="icehockey_nhl",
        commence_time=dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=3),
        home_team="Toronto Maple Leafs",
        away_team="Montreal Canadiens",
        market="h2h",
        outcome_name="Toronto Maple Leafs",
        point=None,
        bookmaker_key="bet99_ca_on",
        book_odds=2.05,
        sharp_book_key="pinnacle",
        true_prob=0.52,
        ev_pct=4.3,
        recommended_stake=40.0,
        status="notified",
    )
    defaults.update(kwargs)
    with db.session() as s:
        alert = Alert(**defaults)
        s.add(alert)
        s.flush()
        return alert.id


def test_summarize_empty_alerts():
    perf = summarize([])
    assert perf.bets_settled == 0
    assert perf.wins == 0
    assert perf.losses == 0
    assert perf.pushes == 0
    assert perf.total_staked == 0.0
    assert perf.total_profit == 0.0
    assert perf.roi_pct == 0.0


def test_summarize_counts_settled_outcomes_and_ignores_open_bets():
    db = _db()
    _insert_alert(db, event_id="e1", status="settled_win", placed_stake=40.0, profit=42.0)
    _insert_alert(db, event_id="e2", status="settled_loss", placed_stake=50.0, profit=-50.0)
    _insert_alert(db, event_id="e3", status="settled_push", placed_stake=30.0, profit=0.0)
    _insert_alert(db, event_id="e4", status="placed", placed_stake=20.0)  # not settled

    with db.session() as s:
        alerts = s.query(Alert).all()
        perf = summarize(alerts)

    assert perf.bets_settled == 3
    assert perf.wins == 1
    assert perf.losses == 1
    assert perf.pushes == 1
    assert perf.total_staked == 120.0
    assert perf.total_profit == -8.0
    assert perf.roi_pct == round(-8.0 / 120.0 * 100.0, 2)


def test_build_report_lines_includes_bankroll_open_bets_and_performance():
    db = _db()
    settings = _fake_settings(starting_bankroll=500.0)
    _insert_alert(db, event_id="e1", status="placed", placed_stake=25.0)
    _insert_alert(db, event_id="e2", status="settled_win", placed_stake=40.0, profit=42.0)

    lines = build_report_lines(db, settings)

    assert "Bankroll: $500.00" in lines
    assert "Open bets: 1" in lines
    assert any(line.startswith("Settled: 1 (1W-0L-0P)") for line in lines)
    assert "Total staked: $40.00" in lines
    assert "Total profit: $42.00" in lines
    assert "ROI: +105.0%" in lines
