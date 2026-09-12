import pytest

from betbot.ev import ev_pct


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
