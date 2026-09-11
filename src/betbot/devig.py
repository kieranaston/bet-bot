"""Remove the vig from a sharp book's two-way market to estimate true win probabilities.

v1 implements the "multiplicative" (basic proportional) devig method, which is standard
for two-way markets (moneyline, spreads, totals) and is what most public +EV tooling uses
as a baseline. It normalizes the implied probabilities so they sum to 1:

    true_prob_i = implied_prob_i / sum(implied_prob_j for all j in the market)

This is a reasonable approximation for two-outcome markets; it does not correct for
favorite-longshot bias the way Shin's method does. That's a documented future improvement,
not implemented here.
"""
from __future__ import annotations


def implied_prob(decimal_odds: float) -> float:
    if decimal_odds <= 1.0:
        raise ValueError(f"decimal_odds must be > 1.0, got {decimal_odds}")
    return 1.0 / decimal_odds


def devig_multiplicative(decimal_odds: list[float]) -> list[float]:
    """Given the sharp book's decimal odds for every outcome in a two-way market, return
    the vig-free true probability for each outcome, in the same order."""
    if len(decimal_odds) < 2:
        raise ValueError("Need at least two outcomes to devig a market")
    implied = [implied_prob(o) for o in decimal_odds]
    total = sum(implied)
    return [p / total for p in implied]


def devig(decimal_odds: list[float], method: str = "multiplicative") -> list[float]:
    if method != "multiplicative":
        raise NotImplementedError(f"Devig method '{method}' is not implemented in v1")
    return devig_multiplicative(decimal_odds)
