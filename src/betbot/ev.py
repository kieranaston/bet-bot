"""Compare a sharp book's devigged true probability against an Ontario book's price to
find positive-EV bets."""
from __future__ import annotations


def ev_pct(true_prob: float, decimal_odds: float) -> float:
    """EV per $1 staked, as a percentage. E.g. true_prob=0.55, decimal_odds=2.0
    -> EV = 0.55*2.0 - 1 = 0.10 -> 10.0%"""
    return (true_prob * decimal_odds - 1.0) * 100.0
