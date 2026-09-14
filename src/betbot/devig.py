"""Remove the vig from a sharp book's two-way market to estimate true win probabilities.

Default method is "additive", which for exactly two outcomes is mathematically equivalent
to Shin's method (the standard correction for favorite-longshot bias -- bookmakers embed
proportionally more vig into longshot prices than favorite prices, and simple proportional
devig ("multiplicative") doesn't correct for that skew):

    true_prob_i = implied_prob_i - (sum(implied_prob_j for all j) - 1) / n

Provably safe (never produces a negative probability) only for exactly two outcomes: for
n=2, true_prob_i < 0 would require implied_prob_i < implied_prob_j - 1, impossible since
every implied probability is in (0, 1). Not proven Shin-equivalent or safe for 3+ outcomes
(e.g. soccer's 3-way h2h) -- devig() below falls back to "multiplicative" there rather than
risk it. "multiplicative" remains available/used for that fallback and is still the
textbook baseline most public +EV tooling uses:

    true_prob_i = implied_prob_i / sum(implied_prob_j for all j in the market)
"""
from __future__ import annotations


def implied_prob(decimal_odds: float) -> float:
    if decimal_odds <= 1.0:
        raise ValueError(f"decimal_odds must be > 1.0, got {decimal_odds}")
    return 1.0 / decimal_odds


def devig_multiplicative(decimal_odds: list[float]) -> list[float]:
    """Given the sharp book's decimal odds for every outcome in a market, return the
    vig-free true probability for each outcome, in the same order."""
    if len(decimal_odds) < 2:
        raise ValueError("Need at least two outcomes to devig a market")
    implied = [implied_prob(o) for o in decimal_odds]
    total = sum(implied)
    return [p / total for p in implied]


def devig_additive(decimal_odds: list[float]) -> list[float]:
    """Shin's-method-equivalent devig for exactly two outcomes (see module docstring for
    why this is only valid there). Raises ValueError for anything else -- callers must not
    use this for 3+ outcome markets; devig() below handles the fallback."""
    if len(decimal_odds) != 2:
        raise ValueError(
            f"devig_additive is only valid for exactly two outcomes, got {len(decimal_odds)}"
        )
    implied = [implied_prob(o) for o in decimal_odds]
    total = sum(implied)
    n = len(decimal_odds)
    return [p - (total - 1) / n for p in implied]


def devig(decimal_odds: list[float], method: str = "additive") -> list[float]:
    if method == "multiplicative":
        return devig_multiplicative(decimal_odds)
    if method == "additive":
        if len(decimal_odds) == 2:
            return devig_additive(decimal_odds)
        # Shin's method only reduces to a simple, provably-safe closed form for exactly
        # two outcomes -- not implemented for 3+ (soccer's 3-way h2h), so fall back to
        # multiplicative rather than risk a negative probability there.
        return devig_multiplicative(decimal_odds)
    raise NotImplementedError(f"Devig method '{method}' is not implemented")


def devig_consensus(
    per_book_odds: dict[str, list[float]],
    min_books: int,
    method: str = "additive",
) -> list[float] | None:
    """For markets with no single sharp reference (player props -- Pinnacle doesn't
    reliably price these), average no-vig true probabilities across several high-volume
    books instead of trusting any one of them. `per_book_odds` maps bookmaker key ->
    decimal odds for the same outcomes, in the same order, e.g.
    {"fanduel": [over_price, under_price], "draftkings": [over_price, under_price]}.

    Each book is devigged independently (its own vig only reflects its own book), then the
    resulting true probabilities are averaged per-outcome across books. Returns None if
    fewer than `min_books` books are present -- a single book's price is not a consensus,
    and the caller should skip rather than alert on a one-book "average". Also degenerates
    correctly to plain single-book devig when exactly one book is passed with
    `min_books=1` -- used for game-level alternate markets devigged against Pinnacle alone.
    """
    if len(per_book_odds) < min_books:
        return None
    per_book_probs = [devig(odds, method=method) for odds in per_book_odds.values()]
    num_outcomes = len(per_book_probs[0])
    return [
        sum(probs[i] for probs in per_book_probs) / len(per_book_probs)
        for i in range(num_outcomes)
    ]
