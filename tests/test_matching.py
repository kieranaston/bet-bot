import datetime as dt

import pytest

from betbot.devig import devig
from betbot.matching import book_points, build_curve, is_fresh, select_reference, true_prob_at


def _bm(key: str, last_update: str | None = None) -> dict:
    bm = {"key": key}
    if last_update is not None:
        bm["last_update"] = last_update
    return bm


def test_is_fresh_missing_last_update_treated_as_fresh():
    # Real Odds API responses always carry last_update -- a missing value only ever means
    # synthetic test data, which should behave as fresh rather than silently forcing every
    # existing Pinnacle-path test into the fallback basket.
    now = dt.datetime.now(dt.timezone.utc)
    assert is_fresh(_bm("pinnacle"), now, max_staleness_minutes=20) is True


def test_is_fresh_within_threshold():
    now = dt.datetime.now(dt.timezone.utc)
    recent = (now - dt.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert is_fresh(_bm("pinnacle", recent), now, max_staleness_minutes=20) is True


def test_is_fresh_beyond_threshold():
    now = dt.datetime.now(dt.timezone.utc)
    stale = (now - dt.timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert is_fresh(_bm("pinnacle", stale), now, max_staleness_minutes=20) is False


def test_book_points_devigs_one_books_own_market():
    outcomes = [("Home", -3.5, 1.91), ("Away", 3.5, 1.91)]
    points = book_points(outcomes, "additive")
    assert set(points) == {"Home", "Away"}
    assert points["Home"] == [(-3.5, pytest.approx(0.5))]
    assert points["Away"] == [(3.5, pytest.approx(0.5))]


def test_book_points_empty_for_single_outcome():
    assert book_points([("Home", None, 1.91)], "additive") == {}


def test_build_curve_merges_and_sorts_multiple_books():
    book_a = book_points([("Home", -3.5, 1.91), ("Away", 3.5, 1.91)], "additive")
    book_b = book_points([("Home", -3.0, 1.87), ("Away", 3.0, 2.05)], "additive")
    curve = build_curve([book_a, book_b], aggregate="mean")
    assert [p for p, _ in curve["Home"]] == [-3.5, -3.0]


def test_build_curve_median_at_agreeing_point():
    books = [
        book_points([("Home", -3.0, 1.91), ("Away", 3.0, 1.91)], "additive"),
        book_points([("Home", -3.0, 1.80), ("Away", 3.0, 2.20)], "additive"),
        book_points([("Home", -3.0, 4.00), ("Away", 3.0, 1.35)], "additive"),  # outlier
    ]
    median_curve = build_curve(books, aggregate="median")
    mean_curve = build_curve(books, aggregate="mean")
    # The outlier book should pull the mean further from the two agreeing books than the
    # median is.
    agreeing_avg = (devig([1.91, 1.91])[0] + devig([1.80, 2.20])[0]) / 2
    assert abs(median_curve["Home"][0][1] - agreeing_avg) <= abs(mean_curve["Home"][0][1] - agreeing_avg)


def test_true_prob_at_exact_match():
    curve = [(-3.5, 0.55), (-3.0, 0.52)]
    assert true_prob_at(curve, -3.5) == pytest.approx(0.55)


def test_true_prob_at_h2h_none_point():
    curve = [(None, 0.55)]
    assert true_prob_at(curve, None) == pytest.approx(0.55)


def test_true_prob_at_interpolates_between_bracketing_points():
    curve = [(-4.0, 0.60), (-3.0, 0.52)]
    result = true_prob_at(curve, -3.5)
    assert result == pytest.approx((0.60 + 0.52) / 2)


def test_true_prob_at_returns_none_outside_observed_range():
    curve = [(-4.0, 0.60), (-3.0, 0.52)]
    assert true_prob_at(curve, -1.0) is None
    assert true_prob_at(curve, -10.0) is None


def test_true_prob_at_empty_curve_returns_none():
    assert true_prob_at([], -3.5) is None


def test_select_reference_prefers_fresh_pinnacle():
    now = dt.datetime.now(dt.timezone.utc)
    sharp_bm = _bm("pinnacle")
    sharp_outcomes = [("Home", None, 1.91), ("Away", None, 1.91)]
    selection = select_reference(
        sharp_bm, sharp_outcomes, basket_candidates=[], devig_method="additive",
        min_consensus_books=2, now=now, max_staleness_minutes=20,
    )
    assert selection is not None
    curve, label = selection
    assert label == "pinnacle"
    assert true_prob_at(curve["Home"], None) == pytest.approx(0.5)


def test_select_reference_falls_back_when_pinnacle_stale():
    now = dt.datetime.now(dt.timezone.utc)
    stale = (now - dt.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    sharp_bm = _bm("pinnacle", stale)
    sharp_outcomes = [("Home", None, 1.91), ("Away", None, 1.91)]
    basket = [
        ("fanduel", [("Home", None, 1.87), ("Away", None, 2.05)]),
        ("draftkings", [("Home", None, 1.95), ("Away", None, 1.87)]),
    ]
    selection = select_reference(
        sharp_bm, sharp_outcomes, basket, devig_method="additive",
        min_consensus_books=2, now=now, max_staleness_minutes=20,
    )
    assert selection is not None
    curve, label = selection
    assert label == "draftkings,fanduel"


def test_select_reference_falls_back_when_pinnacle_missing():
    now = dt.datetime.now(dt.timezone.utc)
    basket = [
        ("fanduel", [("Home", None, 1.87), ("Away", None, 2.05)]),
        ("draftkings", [("Home", None, 1.95), ("Away", None, 1.87)]),
    ]
    selection = select_reference(
        None, None, basket, devig_method="additive",
        min_consensus_books=2, now=now, max_staleness_minutes=20,
    )
    assert selection is not None
    _, label = selection
    assert label == "draftkings,fanduel"


def test_select_reference_none_when_basket_below_min_books():
    now = dt.datetime.now(dt.timezone.utc)
    basket = [("fanduel", [("Home", None, 1.87), ("Away", None, 2.05)])]
    selection = select_reference(
        None, None, basket, devig_method="additive",
        min_consensus_books=2, now=now, max_staleness_minutes=20,
    )
    assert selection is None


def test_select_reference_none_when_pinnacle_missing_and_no_basket():
    now = dt.datetime.now(dt.timezone.utc)
    selection = select_reference(
        None, None, [], devig_method="additive",
        min_consensus_books=2, now=now, max_staleness_minutes=20,
    )
    assert selection is None


def test_book_points_by_line_devigs_each_total_line_independently():
    from betbot.matching import book_points, book_points_by_line

    ladder = []
    for pt in (41.5, 42.5, 43.5):
        ladder.append((("game", "Over"), pt, 1.91))
        ladder.append((("game", "Under"), pt, 1.91))

    # Joint (wrong for ladders): collapses toward 1/N
    joint = book_points(ladder, "additive")
    assert joint[("game", "Over")][0][1] == pytest.approx(1 / 6)

    # Per-line: each Over ≈ 0.5
    by_line = book_points_by_line(ladder, "additive")
    for pt, prob in by_line[("game", "Over")]:
        assert prob == pytest.approx(0.5)


def test_merge_curve_anchors_keeps_primary_and_adds_missing_points():
    from betbot.matching import merge_curve_anchors, true_prob_at

    primary = {"Home": [(-3.0, 0.55)]}
    secondary = {"Home": [(-4.0, 0.60), (-3.0, 0.50)]}  # -3.0 must not overwrite primary
    merged = merge_curve_anchors(primary, secondary)
    assert merged["Home"] == [(-4.0, 0.60), (-3.0, 0.55)]
    assert true_prob_at(merged["Home"], -3.5) == pytest.approx(0.575)


def test_select_reference_merges_basket_anchors_when_pinnacle_fresh():
    now = dt.datetime.now(dt.timezone.utc)
    sharp_bm = _bm("pinnacle")
    sharp_outcomes = [("Home", -3.0, 1.91), ("Away", 3.0, 1.91)]
    basket = [
        ("fanduel", [("Home", -4.0, 1.91), ("Away", 4.0, 1.91)]),
        ("draftkings", [("Home", -4.0, 1.91), ("Away", 4.0, 1.91)]),
    ]
    selection = select_reference(
        sharp_bm, sharp_outcomes, basket, devig_method="additive",
        min_consensus_books=2, now=now, max_staleness_minutes=20,
    )
    assert selection is not None
    curve, label = selection
    assert label == "pinnacle"
    # Ontario -3.5 is bracketed by Pinnacle -3.0 and basket -4.0
    assert true_prob_at(curve["Home"], -3.5) == pytest.approx(0.5)
