import pytest

from betbot.ev import ev_pct, evaluate_two_way_market


def test_ev_pct_no_edge_matches_fair_odds():
    # true_prob 0.5 at fair decimal odds 2.0 -> exactly breakeven.
    assert ev_pct(0.5, 2.0) == pytest.approx(0.0)


def test_ev_pct_positive_edge():
    # true_prob 0.55 but book pays as if 0.50 (2.0 odds) -> positive EV.
    result = ev_pct(0.55, 2.0)
    assert result == pytest.approx(10.0)


def test_ev_pct_negative_edge():
    result = ev_pct(0.45, 2.0)
    assert result == pytest.approx(-10.0)


def test_evaluate_two_way_market_flags_soft_side():
    # Sharp book (devigged) has true probs [0.5, 0.5] (symmetric -110/-110 market).
    # Ontario book matches on side 0 (still -EV there, since 1.91 has vig) but offers much
    # better odds on side 1 -> +EV there.
    sharp_odds = [1.91, 1.91]
    book_odds = [1.91, 2.10]
    results = evaluate_two_way_market(sharp_odds, book_odds)
    assert results[1].ev_pct > 0
    assert results[0].ev_pct < 0
