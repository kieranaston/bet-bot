"""Compare a sharp book's devigged true probability against an Ontario book's price to
find positive-EV bets."""
from __future__ import annotations

from dataclasses import dataclass

from betbot.devig import devig


@dataclass
class EvResult:
    true_prob: float
    ev_pct: float  # e.g. 3.5 means +3.5% EV per dollar staked


def ev_pct(true_prob: float, decimal_odds: float) -> float:
    """EV per $1 staked, as a percentage. E.g. true_prob=0.55, decimal_odds=2.0
    -> EV = 0.55*2.0 - 1 = 0.10 -> 10.0%"""
    return (true_prob * decimal_odds - 1.0) * 100.0


def evaluate_two_way_market(
    sharp_decimal_odds: list[float],
    book_decimal_odds: list[float],
    devig_method: str = "multiplicative",
) -> list[EvResult]:
    """sharp_decimal_odds and book_decimal_odds must be same length/order (outcome-aligned).
    Returns one EvResult per outcome."""
    if len(sharp_decimal_odds) != len(book_decimal_odds):
        raise ValueError("sharp and book outcome lists must be the same length")
    true_probs = devig(sharp_decimal_odds, method=devig_method)
    return [
        EvResult(true_prob=p, ev_pct=ev_pct(p, book_odds))
        for p, book_odds in zip(true_probs, book_decimal_odds)
    ]
