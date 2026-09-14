import pytest

from betbot.devig import devig, devig_additive, devig_consensus, devig_multiplicative, implied_prob


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


def test_devig_additive_matches_hand_computed_values():
    # r1 = 1/1.40 = 0.714286, r2 = 1/3.20 = 0.3125, sum = 1.026786, excess/2 = 0.013393
    true_probs = devig_additive([1.40, 3.20])
    assert true_probs[0] == pytest.approx(0.714286 - 0.013393, abs=1e-5)
    assert true_probs[1] == pytest.approx(0.3125 - 0.013393, abs=1e-5)
    assert sum(true_probs) == pytest.approx(1.0)


def test_devig_additive_shifts_toward_favorite_vs_multiplicative():
    # This is the actual favorite-longshot-bias correction: additive should assign a
    # HIGHER true probability to the favorite (and lower to the longshot) than
    # multiplicative does, for any market with real vig and unequal sides.
    odds = [1.40, 3.20]
    additive_probs = devig_additive(odds)
    multiplicative_probs = devig_multiplicative(odds)
    assert additive_probs[0] > multiplicative_probs[0]  # favorite
    assert additive_probs[1] < multiplicative_probs[1]  # longshot


def test_devig_additive_equals_multiplicative_when_no_vig():
    # Zero overround (sum of implied probs == 1) -- both methods are no-ops here.
    odds = [1.50, 3.00]  # 1/1.50 + 1/3.00 == 1.0 exactly
    assert devig_additive(odds) == pytest.approx(devig_multiplicative(odds))


def test_devig_additive_equals_multiplicative_when_symmetric():
    odds = [1.91, 1.91]
    assert devig_additive(odds) == pytest.approx(devig_multiplicative(odds))


def test_devig_additive_never_negative_even_for_extreme_longshot():
    # Provably safe for exactly two outcomes: p_i < 0 would require r_i < r_j - 1, which
    # is impossible since every implied probability is in (0, 1).
    true_probs = devig_additive([1.01, 25.0])
    assert all(p >= 0 for p in true_probs)


def test_devig_additive_rejects_non_two_outcome():
    with pytest.raises(ValueError):
        devig_additive([1.91, 1.91, 1.91])


def test_devig_defaults_to_additive():
    odds = [1.40, 3.20]
    assert devig(odds) == pytest.approx(devig_additive(odds))


def test_devig_additive_falls_back_to_multiplicative_for_three_outcomes():
    # Shin's-method equivalence/safety only holds for exactly two outcomes (soccer's
    # 3-way h2h is the real case) -- devig() must not call devig_additive there.
    odds = [2.5, 3.4, 3.0]
    assert devig(odds, method="additive") == pytest.approx(devig_multiplicative(odds))


def test_devig_rejects_unknown_method():
    with pytest.raises(NotImplementedError):
        devig([1.91, 1.91], method="shin")


def test_devig_consensus_averages_true_probs_across_books():
    # Each book is devigged on its own (its vig only reflects its own book) before
    # averaging -- not e.g. averaging raw prices first.
    per_book = {"fanduel": [1.91, 1.91], "draftkings": [1.83, 2.05]}
    result = devig_consensus(per_book, min_books=2)
    expected_a = devig(per_book["fanduel"])
    expected_b = devig(per_book["draftkings"])
    assert result[0] == pytest.approx((expected_a[0] + expected_b[0]) / 2)
    assert result[1] == pytest.approx((expected_a[1] + expected_b[1]) / 2)
    assert sum(result) == pytest.approx(1.0)


def test_devig_consensus_requires_min_books():
    # A single book's price is not a consensus -- caller should skip, not trust it.
    assert devig_consensus({"fanduel": [1.91, 1.91]}, min_books=2) is None


def test_devig_consensus_meets_min_books_exactly():
    per_book = {"fanduel": [1.91, 1.91], "draftkings": [1.91, 1.91], "betmgm": [1.91, 1.91]}
    result = devig_consensus(per_book, min_books=2)
    assert result is not None
    assert len(result) == 2
