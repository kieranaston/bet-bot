import datetime as dt
from types import SimpleNamespace

from betbot import commands
from betbot.storage import Alert, Database, local_time_str


def _fake_settings(starting_bankroll: float = 1000.0, sports: list | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        starting_bankroll=starting_bankroll,
        display_name=lambda key: {"bet99_ca_on": "Bet99", "pinnacle": "Pinnacle"}.get(key, key),
        method_display=lambda key: " + ".join(
            {"bet99_ca_on": "Bet99", "pinnacle": "Pinnacle"}.get(k, k) for k in key.split(",")
        ),
        sports=sports if sports is not None else [],
        max_hours_ahead=48,
        scan_bookmakers="bet99_ca_on,pinnacle",
        timezone="America/Toronto",
    )


def _db() -> Database:
    return Database("sqlite:///:memory:")


def _fake_telegram() -> SimpleNamespace:
    return SimpleNamespace(send_message=lambda *args, **kwargs: True)


def _fake_odds_client(quota: dict | None = None) -> SimpleNamespace:
    quota = quota if quota is not None else {"used": "10", "remaining": "9990", "last": "1"}
    return SimpleNamespace(get_quota=lambda: quota)


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
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    assert commands._dispatch(db, settings, telegram, odds_client, "/help") == commands.HELP_TEXT
    assert commands._dispatch(db, settings, telegram, odds_client, "/start") == commands.HELP_TEXT


def test_command_with_bot_mention_suffix_is_recognized():
    db = _db()
    settings = _fake_settings()
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    assert commands._dispatch(db, settings, telegram, odds_client, "/help@MyBetBot") == commands.HELP_TEXT
    assert commands._dispatch(db, settings, telegram, odds_client, "/bankroll@MyBetBot") == "Current bankroll: $1,000.00"


def test_unrecognized_command_is_ignored_silently():
    db = _db()
    settings = _fake_settings()
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    assert commands._dispatch(db, settings, telegram, odds_client, "hello there") == ""


def test_empty_text_is_ignored():
    db = _db()
    settings = _fake_settings()
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    assert commands._dispatch(db, settings, telegram, odds_client, "   ") == ""


def test_bankroll_no_args_shows_current():
    db = _db()
    settings = _fake_settings(starting_bankroll=500.0)
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    assert commands._dispatch(db, settings, telegram, odds_client, "/bankroll") == "Current bankroll: $500.00"


def test_bankroll_with_arg_sets_it():
    db = _db()
    settings = _fake_settings()
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    reply = commands._dispatch(db, settings, telegram, odds_client, "/bankroll 1500")
    assert reply == "Bankroll set to $1,500.00"
    assert db.current_bankroll(0.0) == 1500.0


def test_placed_no_args_shows_usage():
    db = _db()
    settings = _fake_settings()
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    assert commands._dispatch(db, settings, telegram, odds_client, "/placed") == "Usage: /placed <alert_id> [stake]"


def test_placed_unknown_alert():
    db = _db()
    settings = _fake_settings()
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    assert commands._dispatch(db, settings, telegram, odds_client, "/placed 999") == "No alert #999 found."


def test_placed_defaults_to_recommended_stake_and_shows_point():
    db = _db()
    settings = _fake_settings()
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    alert_id = _insert_alert(db, market="spreads", outcome_name="Toronto Maple Leafs", point=-1.5)

    reply = commands._dispatch(db, settings, telegram, odds_client, f"/placed {alert_id}")

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
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    alert_id = _insert_alert(db)

    reply = commands._dispatch(db, settings, telegram, odds_client, f"/placed {alert_id} 75")

    assert "for $75.00" in reply
    with db.session() as s:
        assert s.get(Alert, alert_id).placed_stake == 75.0


def test_placed_non_integer_id_reports_error_without_crashing():
    db = _db()
    settings = _fake_settings()
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    reply = commands._dispatch(db, settings, telegram, odds_client, "/placed abc")
    assert reply.startswith("Error handling `/placed abc`:")


def test_skip_no_args_shows_usage():
    db = _db()
    settings = _fake_settings()
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    assert commands._dispatch(db, settings, telegram, odds_client, "/skip") == "Usage: /skip <alert_id>"


def test_skip_unknown_alert():
    db = _db()
    settings = _fake_settings()
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    assert commands._dispatch(db, settings, telegram, odds_client, "/skip 999") == "No alert #999 found."


def test_skip_marks_alert_skipped():
    db = _db()
    settings = _fake_settings()
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    alert_id = _insert_alert(db)

    reply = commands._dispatch(db, settings, telegram, odds_client, f"/skip {alert_id}")

    assert reply == f"Skipped alert #{alert_id}."
    with db.session() as s:
        assert s.get(Alert, alert_id).status == "skipped"


def test_settle_bad_usage():
    db = _db()
    settings = _fake_settings()
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    expected = "Usage: /settle <alert_id> win|loss|push"
    assert commands._dispatch(db, settings, telegram, odds_client, "/settle 1") == expected
    assert commands._dispatch(db, settings, telegram, odds_client, "/settle 1 maybe") == expected


def test_settle_unknown_alert():
    db = _db()
    settings = _fake_settings()
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    assert commands._dispatch(db, settings, telegram, odds_client, "/settle 999 win") == "No alert #999 found."


def test_settle_never_placed():
    db = _db()
    settings = _fake_settings()
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    alert_id = _insert_alert(db, status="notified", placed_stake=None)

    reply = commands._dispatch(db, settings, telegram, odds_client, f"/settle {alert_id} win")

    assert reply == f"Alert #{alert_id} was never marked /placed -- nothing to settle."


def test_settle_already_settled():
    db = _db()
    settings = _fake_settings()
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    alert_id = _insert_alert(db, status="settled_win", placed_stake=40.0)

    reply = commands._dispatch(db, settings, telegram, odds_client, f"/settle {alert_id} win")

    assert reply == f"Alert #{alert_id} is already settled (settled_win)."


def test_settle_win_updates_bankroll():
    db = _db()
    settings = _fake_settings(starting_bankroll=1000.0)
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    alert_id = _insert_alert(
        db, status="placed", placed_stake=40.0, book_odds=2.05, market="h2h", point=None
    )

    reply = commands._dispatch(db, settings, telegram, odds_client, f"/settle {alert_id} win")

    assert reply == f"Settled #{alert_id} as WIN: +42.00. Bankroll now $1,042.00"
    with db.session() as s:
        alert = s.get(Alert, alert_id)
        assert alert.status == "settled_win"
        assert alert.profit == 42.00


def test_settle_loss_updates_bankroll():
    db = _db()
    settings = _fake_settings(starting_bankroll=1000.0)
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    alert_id = _insert_alert(db, status="placed", placed_stake=40.0, market="h2h", point=None)

    reply = commands._dispatch(db, settings, telegram, odds_client, f"/settle {alert_id} loss")

    assert reply == f"Settled #{alert_id} as LOSS: -40.00. Bankroll now $960.00"
    with db.session() as s:
        assert s.get(Alert, alert_id).status == "settled_loss"


def test_settle_win_works_for_player_props():
    """/settle takes the outcome directly from the user and never calls
    settlement.grade_alert() -- unlike auto-settlement, it doesn't need a market-specific
    grading rule, so it already works for player props with no code change. This locks
    that in as a regression test."""
    db = _db()
    settings = _fake_settings(starting_bankroll=1000.0)
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    alert_id = _insert_alert(
        db, status="placed", placed_stake=25.0, book_odds=1.91, market="batter_hits",
        outcome_name="Over", point=1.5, participant="Fernando Tatis Jr.",
    )

    reply = commands._dispatch(db, settings, telegram, odds_client, f"/settle {alert_id} win")

    assert reply == f"Settled #{alert_id} as WIN: +22.75. Bankroll now $1,022.75"
    with db.session() as s:
        alert = s.get(Alert, alert_id)
        assert alert.status == "settled_win"
        assert alert.participant == "Fernando Tatis Jr."


def test_status_no_open_bets():
    db = _db()
    settings = _fake_settings()
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    assert commands._dispatch(db, settings, telegram, odds_client, "/status") == "No open bets."


def test_status_lists_open_bets_with_point():
    db = _db()
    settings = _fake_settings()
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    commence_time = dt.datetime(2026, 12, 1, 19, 0, tzinfo=dt.timezone.utc)
    alert_id = _insert_alert(
        db,
        status="placed",
        placed_stake=40.0,
        market="spreads",
        outcome_name="Toronto Maple Leafs",
        point=-1.5,
        commence_time=commence_time,
        true_prob=0.52,
    )

    reply = commands._dispatch(db, settings, telegram, odds_client, "/status")

    when = local_time_str(commence_time, "America/Toronto")
    assert reply == (
        "*Open bets:*\n\n"
        f"#{alert_id} NHL Montreal Canadiens @ Toronto Maple Leafs ({when}) — "
        "Toronto Maple Leafs -1.5 @ +105 (Bet99) $40.00\n"
        "True odds: -108 (via Pinnacle)"
    )


def test_status_excludes_non_placed_alerts():
    db = _db()
    settings = _fake_settings()
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    _insert_alert(db, event_id="e1", status="notified")
    _insert_alert(db, event_id="e2", status="skipped")

    assert commands._dispatch(db, settings, telegram, odds_client, "/status") == "No open bets."


def test_stats_reports_bankroll_and_settled_performance():
    db = _db()
    settings = _fake_settings(starting_bankroll=500.0)
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    _insert_alert(db, event_id="e1", status="placed", placed_stake=25.0)
    _insert_alert(db, event_id="e2", status="settled_win", placed_stake=40.0, profit=42.0)

    reply = commands._dispatch(db, settings, telegram, odds_client, "/stats")

    assert reply.startswith("*Stats*\n")
    assert "Bankroll: $500.00" in reply
    assert "Open bets: 1" in reply
    assert "Settled: 1 (1W-0L-0P)" in reply
    assert "Total profit: $42.00" in reply


def test_scan_with_no_configured_sports_reports_no_opportunities():
    db = _db()
    settings = _fake_settings(sports=[])
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()

    reply = commands._dispatch(db, settings, telegram, odds_client, "/scan")

    assert reply.startswith("Manual scan complete: no new +EV opportunities")
    assert db.get_kv("last_manual_scan_at") is not None


def test_scan_second_call_within_cooldown_is_blocked():
    db = _db()
    settings = _fake_settings(sports=[])
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()

    first = commands._dispatch(db, settings, telegram, odds_client, "/scan")
    second = commands._dispatch(db, settings, telegram, odds_client, "/scan")

    assert first.startswith("Manual scan complete")
    assert second.startswith("Manual scan on cooldown")
    assert "more minute" in second


def test_scan_allowed_again_after_cooldown_elapses():
    db = _db()
    settings = _fake_settings(sports=[])
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()

    stale = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=commands.SCAN_COOLDOWN_MINUTES + 1)
    db.set_kv("last_manual_scan_at", stale.isoformat())

    reply = commands._dispatch(db, settings, telegram, odds_client, "/scan")

    assert reply.startswith("Manual scan complete")


def test_quota_reports_usage_and_percentage():
    db = _db()
    settings = _fake_settings()
    telegram = _fake_telegram()
    odds_client = _fake_odds_client({"used": "10", "remaining": "90", "last": "1"})

    reply = commands._dispatch(db, settings, telegram, odds_client, "/quota")

    assert reply.startswith("*Odds API quota*\n")
    assert "Used: 10" in reply
    assert "Remaining: 90" in reply
    assert "Used 10.0% of this period's quota" in reply


def test_quota_handles_missing_headers_without_crashing():
    db = _db()
    settings = _fake_settings()
    telegram = _fake_telegram()
    odds_client = _fake_odds_client({"used": None, "remaining": None, "last": None})

    reply = commands._dispatch(db, settings, telegram, odds_client, "/quota")

    assert "Used: ?" in reply
    assert "Remaining: ?" in reply
    assert "% of this period's quota" not in reply


def test_process_updates_advances_offset_and_filters_empty_replies():
    db = _db()
    settings = _fake_settings()
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    updates = [
        {"update_id": 5, "message": {"text": "not a command"}},
        {"update_id": 6, "message": {"text": "/help"}},
    ]

    replies = commands.process_updates(db, settings, updates, telegram, odds_client)

    assert replies == [commands.HELP_TEXT]
    assert db.get_kv("telegram_update_offset") == "7"


def test_process_updates_skips_messages_without_text():
    db = _db()
    settings = _fake_settings()
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    updates = [{"update_id": 1, "message": {"sticker": {}}}]

    replies = commands.process_updates(db, settings, updates, telegram, odds_client)

    assert replies == []
    assert db.get_kv("telegram_update_offset") == "2"


def test_process_updates_falls_back_to_channel_post():
    db = _db()
    settings = _fake_settings()
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    updates = [{"update_id": 1, "channel_post": {"text": "/help"}}]

    replies = commands.process_updates(db, settings, updates, telegram, odds_client)

    assert replies == [commands.HELP_TEXT]


def test_process_updates_handles_edited_message():
    db = _db()
    settings = _fake_settings()
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    updates = [{"update_id": 1, "edited_message": {"text": "/help"}}]

    replies = commands.process_updates(db, settings, updates, telegram, odds_client)

    assert replies == [commands.HELP_TEXT]


def test_process_updates_ignores_other_chats_but_still_advances_offset():
    db = _db()
    settings = _fake_settings()
    telegram = _fake_telegram()
    odds_client = _fake_odds_client()
    updates = [
        {"update_id": 4, "message": {"text": "/help", "chat": {"id": 999}}},
        {"update_id": 5, "message": {"text": "/help", "chat": {"id": 123}}},
    ]

    replies = commands.process_updates(db, settings, updates, telegram, odds_client, allowed_chat_id="123")

    assert replies == [commands.HELP_TEXT]
    assert db.get_kv("telegram_update_offset") == "6"
