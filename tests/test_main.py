import datetime as dt
from unittest.mock import MagicMock

import pytest

from betbot.main import (
    _devig_spread_alternates,
    _events_within_pregame_window,
    process_event,
    process_prop_event,
)
from betbot.storage import Alert, Database


def _stale_iso(now: dt.datetime, hours: float) -> str:
    return (now - dt.timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def _prop_bookmaker(key: str, market_key: str, outcomes: list[dict]) -> dict:
    return {"key": key, "markets": [{"key": market_key, "outcomes": outcomes}]}


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


def test_process_event_filters_out_extreme_longshots():
    """A huge-EV bet on a low true-probability longshot must be suppressed (high variance,
    devig error grows at the tails); a normal-probability +EV bet in the same event still
    alerts."""
    db = Database("sqlite:///:memory:")
    telegram = MagicMock()

    # Sharp implied probs already sum to 1.0: Home 0.8333 (favorite), Away 0.1667 (longshot,
    # below the 0.25 min_true_prob floor).
    sharp = _bookmaker(
        "pinnacle", [{"name": "Home Team", "price": 1.20}, {"name": "Away Team", "price": 6.00}]
    )
    book = _bookmaker(
        "bet99_ca_on",
        [
            {"name": "Home Team", "price": 1.30},  # true 0.8333 -> +EV, not a longshot
            {"name": "Away Team", "price": 8.00},  # true 0.1667 -> huge +EV, but a longshot
        ],
    )
    event = _event([sharp, book])

    sent = process_event(
        db, telegram, event, "americanfootball_nfl", ["h2h"],
        bankroll=1000.0, now=dt.datetime.now(dt.timezone.utc),
    )

    assert sent == 1
    with db.session() as s:
        alerts = s.query(Alert).all()
        assert len(alerts) == 1
        assert alerts[0].outcome_name == "Home Team"


def test_process_prop_event_keeps_different_players_separate():
    """Two different players sharing the identical Over/line/book must both alert, not
    collide into one -- regression for the participant-aware dedup key
    (storage.Alert.uq_alert_identity)."""
    db = Database("sqlite:///:memory:")
    telegram = MagicMock()
    market_key = "player_points"

    def outcomes_for(player: str, point: float) -> list[dict]:
        return [
            {"name": "Over", "point": point, "price": 1.91, "description": player},
            {"name": "Under", "point": point, "price": 1.91, "description": player},
        ]

    fanduel = _prop_bookmaker(
        "fanduel", market_key, outcomes_for("Player A", 24.5) + outcomes_for("Player B", 18.5)
    )
    draftkings = _prop_bookmaker(
        "draftkings", market_key, outcomes_for("Player A", 24.5) + outcomes_for("Player B", 18.5)
    )
    ontario = _prop_bookmaker(
        "bet99_ca_on",
        market_key,
        [
            {"name": "Over", "point": 24.5, "price": 2.30, "description": "Player A"},
            {"name": "Over", "point": 18.5, "price": 2.30, "description": "Player B"},
        ],
    )
    event = _event([fanduel, draftkings, ontario])

    sent = process_prop_event(
        db, telegram, event, "basketball_nba", [market_key],
        bankroll=1000.0, now=dt.datetime.now(dt.timezone.utc),
    )

    assert sent == 2
    with db.session() as s:
        alerts = {a.participant: a for a in s.query(Alert).all()}
        assert set(alerts) == {"Player A", "Player B"}
        assert all(a.market == market_key for a in alerts.values())
        assert all(a.sharp_book_key == "draftkings,fanduel" for a in alerts.values())


def test_process_prop_event_requires_min_consensus_books():
    """Only one consensus book quoting a line -- even at a huge apparent price -- must not
    alert, since a single book's price isn't a consensus
    (config/bookmakers.yaml consensus.min_books_required)."""
    db = Database("sqlite:///:memory:")
    telegram = MagicMock()
    market_key = "player_points"

    fanduel = _prop_bookmaker(
        "fanduel",
        market_key,
        [
            {"name": "Over", "point": 24.5, "price": 1.91, "description": "Player A"},
            {"name": "Under", "point": 24.5, "price": 1.91, "description": "Player A"},
        ],
    )
    ontario = _prop_bookmaker(
        "bet99_ca_on", market_key,
        [{"name": "Over", "point": 24.5, "price": 3.00, "description": "Player A"}],
    )
    event = _event([fanduel, ontario])

    sent = process_prop_event(
        db, telegram, event, "basketball_nba", [market_key],
        bankroll=1000.0, now=dt.datetime.now(dt.timezone.utc),
    )

    assert sent == 0


def _iso(offset_hours: float) -> str:
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=offset_hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def test_events_within_pregame_window_filters_far_out_and_started_events():
    """Only games within `pregame_window_hours` of commence_time (and not yet started)
    should be scanned -- this is what replaced the old fixed twice-daily schedule, since
    these books open props/alternates close to kickoff, not gradually."""
    now = dt.datetime.now(dt.timezone.utc)
    events = [
        {"id": "already_started", "commence_time": _iso(-1.0)},
        {"id": "well_within_window", "commence_time": _iso(0.5)},
        {"id": "exactly_at_boundary", "commence_time": _iso(3.0)},
        {"id": "just_outside_window", "commence_time": _iso(3.1)},
    ]

    result = _events_within_pregame_window(events, now, window_hours=3.0)

    assert {e["id"] for e in result} == {"well_within_window", "exactly_at_boundary"}


def test_devig_spread_alternates_pairs_by_point_negation():
    """alternate_spreads pairs the two teams by NEGATED point (Cowboys -3.5 with Giants
    +3.5), not matching point -- and must key the result by each side's own real signed
    point, not the shared magnitude, or Cowboys(-3.5)/Cowboys(-7.0) would collide."""
    pinnacle = _prop_bookmaker(
        "pinnacle",
        "alternate_spreads",
        [
            {"name": "Cowboys", "point": -3.5, "price": 2.00},
            {"name": "Giants", "point": 3.5, "price": 1.87},
            {"name": "Cowboys", "point": -7.0, "price": 3.20},
            {"name": "Giants", "point": 7.0, "price": 1.40},
        ],
    )

    lookup = _devig_spread_alternates(pinnacle, "alternate_spreads", "additive")

    assert set(lookup) == {("Cowboys", -3.5), ("Giants", 3.5), ("Cowboys", -7.0), ("Giants", 7.0)}
    assert lookup[("Cowboys", -3.5)] + lookup[("Giants", 3.5)] == pytest.approx(1.0)
    assert lookup[("Cowboys", -7.0)] + lookup[("Giants", 7.0)] == pytest.approx(1.0)
    assert lookup[("Cowboys", -3.5)] != lookup[("Cowboys", -7.0)]


def test_devig_spread_alternates_skips_incomplete_magnitude():
    """A magnitude with only one side quoted (the other team hasn't posted that line yet)
    must be skipped, not guessed at or crashed on."""
    pinnacle = _prop_bookmaker(
        "pinnacle",
        "alternate_spreads",
        [{"name": "Cowboys", "point": -3.5, "price": 2.00}],
    )

    lookup = _devig_spread_alternates(pinnacle, "alternate_spreads", "additive")

    assert lookup == {}


def test_process_event_falls_back_to_median_basket_when_pinnacle_stale():
    """A technically-present but stale Pinnacle line (last_update beyond
    sharp_max_staleness_minutes) must be treated the same as an absent one -- fall back to
    the median of whichever consensus books are present."""
    db = Database("sqlite:///:memory:")
    telegram = MagicMock()
    now = dt.datetime.now(dt.timezone.utc)

    stale_pinnacle = _bookmaker(
        "pinnacle", [{"name": "Home Team", "price": 1.91}, {"name": "Away Team", "price": 1.91}]
    )
    stale_pinnacle["last_update"] = _stale_iso(now, 3)
    fanduel = _bookmaker(
        "fanduel", [{"name": "Home Team", "price": 1.87}, {"name": "Away Team", "price": 2.05}]
    )
    draftkings = _bookmaker(
        "draftkings", [{"name": "Home Team", "price": 1.95}, {"name": "Away Team", "price": 1.87}]
    )
    book = _bookmaker(
        "bet99_ca_on", [{"name": "Home Team", "price": 2.30}, {"name": "Away Team", "price": 1.60}]
    )
    event = _event([stale_pinnacle, fanduel, draftkings, book])

    sent = process_event(
        db, telegram, event, "americanfootball_nfl", ["h2h"],
        bankroll=1000.0, now=now,
    )

    assert sent == 1
    with db.session() as s:
        alert = s.query(Alert).filter(Alert.outcome_name == "Home Team").one()
        assert alert.sharp_book_key == "draftkings,fanduel"


def test_process_event_falls_back_to_basket_when_pinnacle_absent():
    db = Database("sqlite:///:memory:")
    telegram = MagicMock()
    now = dt.datetime.now(dt.timezone.utc)

    fanduel = _bookmaker(
        "fanduel", [{"name": "Home Team", "price": 1.87}, {"name": "Away Team", "price": 2.05}]
    )
    draftkings = _bookmaker(
        "draftkings", [{"name": "Home Team", "price": 1.95}, {"name": "Away Team", "price": 1.87}]
    )
    book = _bookmaker(
        "bet99_ca_on", [{"name": "Home Team", "price": 2.30}, {"name": "Away Team", "price": 1.60}]
    )
    event = _event([fanduel, draftkings, book])

    sent = process_event(
        db, telegram, event, "americanfootball_nfl", ["h2h"],
        bankroll=1000.0, now=now,
    )

    assert sent == 1
    with db.session() as s:
        alert = s.query(Alert).filter(Alert.outcome_name == "Home Team").one()
        assert alert.sharp_book_key == "draftkings,fanduel"


def test_process_event_skips_when_pinnacle_absent_and_basket_below_min_books():
    """Only one consensus book -- even at a huge apparent price -- must not alert, since a
    single book's price isn't a consensus (mirrors the player-props min-books rule)."""
    db = Database("sqlite:///:memory:")
    telegram = MagicMock()
    now = dt.datetime.now(dt.timezone.utc)

    fanduel = _bookmaker(
        "fanduel", [{"name": "Home Team", "price": 1.50}, {"name": "Away Team", "price": 3.00}]
    )
    book = _bookmaker(
        "bet99_ca_on", [{"name": "Home Team", "price": 3.00}, {"name": "Away Team", "price": 1.50}]
    )
    event = _event([fanduel, book])

    sent = process_event(
        db, telegram, event, "americanfootball_nfl", ["h2h"],
        bankroll=1000.0, now=now,
    )

    assert sent == 0


def test_process_event_interpolates_across_basket_points_for_spreads():
    """No single reference book posts the Ontario book's exact -3.5 -- fanduel has -4.0,
    draftkings has -3.0. Bracketed linear interpolation between them should still produce a
    usable true probability instead of skipping the line entirely."""
    db = Database("sqlite:///:memory:")
    telegram = MagicMock()
    now = dt.datetime.now(dt.timezone.utc)

    fanduel = _bookmaker(
        "fanduel",
        [
            {"name": "Home Team", "point": -4.0, "price": 1.91},
            {"name": "Away Team", "point": 4.0, "price": 1.91},
        ],
    )
    fanduel["markets"][0]["key"] = "spreads"
    draftkings = _bookmaker(
        "draftkings",
        [
            {"name": "Home Team", "point": -3.0, "price": 1.91},
            {"name": "Away Team", "point": 3.0, "price": 1.91},
        ],
    )
    draftkings["markets"][0]["key"] = "spreads"
    book = _bookmaker(
        "bet99_ca_on",
        [
            {"name": "Home Team", "point": -3.5, "price": 2.20},
            {"name": "Away Team", "point": 3.5, "price": 1.70},
        ],
    )
    book["markets"][0]["key"] = "spreads"
    event = _event([fanduel, draftkings, book])

    sent = process_event(
        db, telegram, event, "americanfootball_nfl", ["spreads"],
        bankroll=1000.0, now=now,
    )

    assert sent == 1
    with db.session() as s:
        alert = s.query(Alert).one()
        assert alert.outcome_name == "Home Team"
        assert alert.point == -3.5
        assert alert.true_prob == pytest.approx(0.5)
        assert alert.sharp_book_key == "draftkings,fanduel"


def test_process_event_skips_point_outside_basket_range():
    """A huge apparent price at a point nowhere near what any reference book actually
    quoted must not alert -- interpolation never extrapolates beyond the observed range."""
    db = Database("sqlite:///:memory:")
    telegram = MagicMock()
    now = dt.datetime.now(dt.timezone.utc)

    fanduel = _bookmaker(
        "fanduel",
        [
            {"name": "Home Team", "point": -4.0, "price": 1.91},
            {"name": "Away Team", "point": 4.0, "price": 1.91},
        ],
    )
    fanduel["markets"][0]["key"] = "spreads"
    draftkings = _bookmaker(
        "draftkings",
        [
            {"name": "Home Team", "point": -3.0, "price": 1.91},
            {"name": "Away Team", "point": 3.0, "price": 1.91},
        ],
    )
    draftkings["markets"][0]["key"] = "spreads"
    book = _bookmaker(
        "bet99_ca_on",
        [
            {"name": "Home Team", "point": -1.0, "price": 5.00},
            {"name": "Away Team", "point": 1.0, "price": 1.10},
        ],
    )
    book["markets"][0]["key"] = "spreads"
    event = _event([fanduel, draftkings, book])

    sent = process_event(
        db, telegram, event, "americanfootball_nfl", ["spreads"],
        bankroll=1000.0, now=now,
    )

    assert sent == 0


def test_process_prop_event_alternate_spreads_interpolates_across_pinnacle_ladder():
    """alternate_spreads stays Pinnacle-only, but should now interpolate across Pinnacle's
    own point-negated ladder instead of requiring an exact point match."""
    db = Database("sqlite:///:memory:")
    telegram = MagicMock()
    now = dt.datetime.now(dt.timezone.utc)

    pinnacle = _prop_bookmaker(
        "pinnacle",
        "alternate_spreads",
        [
            {"name": "Cowboys", "point": -3.5, "price": 1.91},
            {"name": "Giants", "point": 3.5, "price": 1.91},
            {"name": "Cowboys", "point": -7.0, "price": 3.20},
            {"name": "Giants", "point": 7.0, "price": 1.40},
        ],
    )
    ontario = _prop_bookmaker(
        "bet99_ca_on", "alternate_spreads",
        [{"name": "Cowboys", "point": -5.0, "price": 2.60}],
    )
    event = _event([pinnacle, ontario])

    sent = process_prop_event(
        db, telegram, event, "americanfootball_nfl", [],
        bankroll=1000.0, now=now, game_alt_markets=["alternate_spreads"],
    )

    assert sent == 1
    with db.session() as s:
        alert = s.query(Alert).one()
        assert alert.point == -5.0
        assert alert.sharp_book_key == "pinnacle"


def test_process_prop_event_alternate_spreads_skips_when_pinnacle_stale():
    db = Database("sqlite:///:memory:")
    telegram = MagicMock()
    now = dt.datetime.now(dt.timezone.utc)

    pinnacle = _prop_bookmaker(
        "pinnacle", "alternate_spreads",
        [
            {"name": "Cowboys", "point": -3.5, "price": 1.91},
            {"name": "Giants", "point": 3.5, "price": 1.91},
        ],
    )
    pinnacle["last_update"] = _stale_iso(now, 3)
    ontario = _prop_bookmaker(
        "bet99_ca_on", "alternate_spreads",
        [{"name": "Cowboys", "point": -3.5, "price": 2.60}],
    )
    event = _event([pinnacle, ontario])

    sent = process_prop_event(
        db, telegram, event, "americanfootball_nfl", [],
        bankroll=1000.0, now=now, game_alt_markets=["alternate_spreads"],
    )

    assert sent == 0


def test_process_prop_event_game_alt_falls_back_to_basket_when_pinnacle_missing():
    """team_totals/alternate_totals/alternate_team_totals (unlike alternate_spreads) go
    through the same Pinnacle-or-median-basket selection as main markets."""
    db = Database("sqlite:///:memory:")
    telegram = MagicMock()
    now = dt.datetime.now(dt.timezone.utc)
    market_key = "team_totals"

    fanduel = _prop_bookmaker(
        "fanduel", market_key,
        [
            {"name": "Over", "point": 24.5, "price": 1.91, "description": "Home Team"},
            {"name": "Under", "point": 24.5, "price": 1.91, "description": "Home Team"},
        ],
    )
    draftkings = _prop_bookmaker(
        "draftkings", market_key,
        [
            {"name": "Over", "point": 24.5, "price": 1.80, "description": "Home Team"},
            {"name": "Under", "point": 24.5, "price": 2.20, "description": "Home Team"},
        ],
    )
    ontario = _prop_bookmaker(
        "bet99_ca_on", market_key,
        [{"name": "Over", "point": 24.5, "price": 2.10, "description": "Home Team"}],
    )
    event = _event([fanduel, draftkings, ontario])

    sent = process_prop_event(
        db, telegram, event, "americanfootball_nfl", [],
        bankroll=1000.0, now=now, game_alt_markets=[market_key],
    )

    assert sent == 1
    with db.session() as s:
        alert = s.query(Alert).one()
        assert alert.participant == "Home Team"
        assert alert.sharp_book_key == "draftkings,fanduel"


def test_process_prop_event_game_alt_market_uses_main_ev_floor_not_props_floor():
    """game_alt_markets devig against Pinnacle (a genuinely sharp book), so they should
    clear at ev.min_ev_pct (2%), NOT the stricter props.min_ev_pct (5%) used for the
    noisier multi-book player-prop consensus."""
    db = Database("sqlite:///:memory:")
    telegram = MagicMock()

    pinnacle = _prop_bookmaker(
        "pinnacle",
        "team_totals",
        [
            {"name": "Over", "point": 24.5, "price": 1.87, "description": "Home Team"},
            {"name": "Under", "point": 24.5, "price": 2.05, "description": "Home Team"},
        ],
    )
    ontario = _prop_bookmaker(
        "bet99_ca_on", "team_totals",
        [{"name": "Over", "point": 24.5, "price": 1.98, "description": "Home Team"}],
    )
    event = _event([pinnacle, ontario])

    sent = process_prop_event(
        db, telegram, event, "americanfootball_nfl", [],
        bankroll=1000.0, now=dt.datetime.now(dt.timezone.utc),
        game_alt_markets=["team_totals"],
    )

    assert sent == 1
    with db.session() as s:
        alert = s.query(Alert).one()
        assert alert.participant == "Home Team"
        assert alert.sharp_book_key == "pinnacle"
        # EV here sits between the two floors (~3.6%) -- this only alerts if the game-alt
        # path used ev.min_ev_pct (2.0), not props.min_ev_pct (5.0).
        assert 2.0 <= alert.ev_pct < 5.0
