import datetime as dt
from types import SimpleNamespace

from betbot import commands
from betbot.storage import Alert, Database


def _fake_settings(starting_bankroll: float = 1000.0) -> SimpleNamespace:
    return SimpleNamespace(
        starting_bankroll=starting_bankroll,
        display_name=lambda key: {"bet99_ca_on": "Bet99"}.get(key, key),
    )


def _db() -> Database:
    return Database("sqlite:///:memory:")


def _insert_alert(db: Database, **kwargs) -> int:
    defaults = dict(
        event_id="e1",
        sport_key="icehockey_nhl",
        commence_time=dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=3),
        home_team="Toronto Maple Leafs",
        away_team="Montreal Canadiens",
        market="spreads",
        outcome_name="Toronto Maple Leafs",
        point=-1.5,
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


def test_help_and_start_return_help_text():
    db = _db()
    settings = _fake_settings()
    assert commands._dispatch(db, settings, "/help") == commands.HELP_TEXT
    assert commands._dispatch(db, settings, "/start") == commands.HELP_TEXT


def test_unrecognized_command_is_ignored_silently():
    db = _db()
    settings = _fake_settings()
    assert commands._dispatch(db, settings, "hello there") == ""


def test_empty_text_is_ignored():
    db = _db()
    settings = _fake_settings()
    assert commands._dispatch(db, settings, "   ") == ""


def test_bankroll_no_args_shows_current():
    db = _db()
    settings = _fake_settings(starting_bankroll=500.0)
    assert commands._dispatch(db, settings, "/bankroll") == "Current bankroll: $500.00"


def test_bankroll_with_arg_sets_it():
    db = _db()
    settings = _fake_settings()
    reply = commands._dispatch(db, settings, "/bankroll 1500")
    assert reply == "Bankroll set to $1,500.00"
    assert db.current_bankroll(0.0) == 1500.0


def test_placed_no_args_shows_usage():
    db = _db()
    settings = _fake_settings()
    assert commands._dispatch(db, settings, "/placed") == "Usage: /placed <alert_id> [stake]"


def test_placed_unknown_alert():
    db = _db()
    settings = _fake_settings()
    assert commands._dispatch(db, settings, "/placed 999") == "No alert #999 found."


def test_placed_defaults_to_recommended_stake_and_shows_point():
    db = _db()
    settings = _fake_settings()
    alert_id = _insert_alert(db, market="spreads", outcome_name="Toronto Maple Leafs", point=-1.5)

    reply = commands._dispatch(db, settings, f"/placed {alert_id}")

    assert reply == (
        f"Logged bet #{alert_id}: Toronto Maple Leafs -1.5 @ +105 (Bet99) for $40.00"
    )
    with db.session() as s:
        alert = s.get(Alert, alert_id)
        assert alert.status == "placed"
        assert alert.placed_stake == 40.0


def test_placed_with_explicit_stake():
    db = _db()
    settings = _fake_settings()
    alert_id = _insert_alert(db)

    reply = commands._dispatch(db, settings, f"/placed {alert_id} 75")

    assert "for $75.00" in reply
    with db.session() as s:
        assert s.get(Alert, alert_id).placed_stake == 75.0


def test_placed_non_integer_id_reports_error_without_crashing():
    db = _db()
    settings = _fake_settings()
    reply = commands._dispatch(db, settings, "/placed abc")
    assert reply.startswith("Error handling `/placed abc`:")


def test_skip_no_args_shows_usage():
    db = _db()
    settings = _fake_settings()
    assert commands._dispatch(db, settings, "/skip") == "Usage: /skip <alert_id>"


def test_skip_unknown_alert():
    db = _db()
    settings = _fake_settings()
    assert commands._dispatch(db, settings, "/skip 999") == "No alert #999 found."


def test_skip_marks_alert_skipped():
    db = _db()
    settings = _fake_settings()
    alert_id = _insert_alert(db)

    reply = commands._dispatch(db, settings, f"/skip {alert_id}")

    assert reply == f"Skipped alert #{alert_id}."
    with db.session() as s:
        assert s.get(Alert, alert_id).status == "skipped"


def test_settle_bad_usage():
    db = _db()
    settings = _fake_settings()
    expected = "Usage: /settle <alert_id> win|loss|push [closing_odds]"
    assert commands._dispatch(db, settings, "/settle 1") == expected
    assert commands._dispatch(db, settings, "/settle 1 maybe") == expected


def test_settle_unknown_alert():
    db = _db()
    settings = _fake_settings()
    assert commands._dispatch(db, settings, "/settle 999 win") == "No alert #999 found."


def test_settle_never_placed():
    db = _db()
    settings = _fake_settings()
    alert_id = _insert_alert(db, status="notified", placed_stake=None)

    reply = commands._dispatch(db, settings, f"/settle {alert_id} win")

    assert reply == f"Alert #{alert_id} was never marked /placed -- nothing to settle."


def test_settle_already_settled():
    db = _db()
    settings = _fake_settings()
    alert_id = _insert_alert(db, status="settled_win", placed_stake=40.0)

    reply = commands._dispatch(db, settings, f"/settle {alert_id} win")

    assert reply == f"Alert #{alert_id} is already settled (settled_win)."


def test_settle_win_updates_bankroll_and_records_closing_odds():
    db = _db()
    settings = _fake_settings(starting_bankroll=1000.0)
    alert_id = _insert_alert(
        db, status="placed", placed_stake=40.0, book_odds=2.05, market="h2h", point=None
    )

    reply = commands._dispatch(db, settings, f"/settle {alert_id} win 2.00")

    assert reply == f"Settled #{alert_id} as WIN: +42.00. Bankroll now $1,042.00"
    with db.session() as s:
        alert = s.get(Alert, alert_id)
        assert alert.status == "settled_win"
        assert alert.closing_odds == 2.00
        assert alert.profit == 42.00


def test_settle_loss_without_closing_odds():
    db = _db()
    settings = _fake_settings(starting_bankroll=1000.0)
    alert_id = _insert_alert(db, status="placed", placed_stake=40.0, market="h2h", point=None)

    reply = commands._dispatch(db, settings, f"/settle {alert_id} loss")

    assert reply == f"Settled #{alert_id} as LOSS: -40.00. Bankroll now $960.00"
    with db.session() as s:
        assert s.get(Alert, alert_id).closing_odds is None


def test_status_no_open_bets():
    db = _db()
    settings = _fake_settings()
    assert commands._dispatch(db, settings, "/status") == "No open bets."


def test_status_lists_open_bets_with_point():
    db = _db()
    settings = _fake_settings()
    alert_id = _insert_alert(
        db,
        status="placed",
        placed_stake=40.0,
        market="spreads",
        outcome_name="Toronto Maple Leafs",
        point=-1.5,
    )

    reply = commands._dispatch(db, settings, "/status")

    assert reply == (
        "*Open bets:*\n"
        f"#{alert_id} Montreal Canadiens @ Toronto Maple Leafs — Toronto Maple Leafs -1.5 "
        "@ +105 (Bet99) $40.00"
    )


def test_status_excludes_non_placed_alerts():
    db = _db()
    settings = _fake_settings()
    _insert_alert(db, event_id="e1", status="notified")
    _insert_alert(db, event_id="e2", status="skipped")

    assert commands._dispatch(db, settings, "/status") == "No open bets."


def test_process_updates_advances_offset_and_filters_empty_replies():
    db = _db()
    settings = _fake_settings()
    updates = [
        {"update_id": 5, "message": {"text": "not a command"}},
        {"update_id": 6, "message": {"text": "/help"}},
    ]

    replies = commands.process_updates(db, settings, updates)

    assert replies == [commands.HELP_TEXT]
    assert db.get_kv("telegram_update_offset") == "7"


def test_process_updates_skips_messages_without_text():
    db = _db()
    settings = _fake_settings()
    updates = [{"update_id": 1, "message": {"sticker": {}}}]

    replies = commands.process_updates(db, settings, updates)

    assert replies == []
    assert db.get_kv("telegram_update_offset") == "2"


def test_process_updates_falls_back_to_channel_post():
    db = _db()
    settings = _fake_settings()
    updates = [{"update_id": 1, "channel_post": {"text": "/help"}}]

    replies = commands.process_updates(db, settings, updates)

    assert replies == [commands.HELP_TEXT]
