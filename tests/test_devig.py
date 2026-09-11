import pytest

from betbot.devig import devig, implied_prob


def test_implied_prob_evens():
    assert implied_prob(2.0) == pytest.approx(0.5)


def test_implied_prob_rejects_invalid_odds():
    with pytest.raises(ValueError):
        implied_prob(1.0)


def test_devig_removes_vig_symmetric_market():
    # Both sides at 1.91 (-110 American) -> vig-laden implied probs sum to > 1.
    true_probs = devig([1.91, 1.91])
    assert sum(true_probs) == pytest.approx(1.0)
    assert true_probs[0] == pytest.approx(true_probs[1])


def test_devig_preserves_relative_favorite():
    true_probs = devig([1.50, 3.00])  # heavy favorite vs underdog
    assert sum(true_probs) == pytest.approx(1.0)
    assert true_probs[0] > true_probs[1]


def test_devig_requires_at_least_two_outcomes():
    with pytest.raises(ValueError):
        devig([1.91])
