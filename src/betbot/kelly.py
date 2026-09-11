"""Quarter-Kelly stake sizing."""
from __future__ import annotations


def full_kelly_fraction(true_prob: float, decimal_odds: float) -> float:
    """Fraction of bankroll the full Kelly criterion would stake. Can be negative
    (meaning: no edge, don't bet) -- callers should clamp to >= 0."""
    b = decimal_odds - 1.0
    if b <= 0:
        return 0.0
    q = 1.0 - true_prob
    return (true_prob * b - q) / b


def stake_amount(
    true_prob: float,
    decimal_odds: float,
    bankroll: float,
    kelly_fraction: float,
    max_stake_pct: float,
    min_stake: float,
) -> float:
    """Recommended stake in bankroll currency, using `kelly_fraction` of full Kelly
    (e.g. 0.25 for quarter Kelly), capped at `max_stake_pct` of bankroll as a hard safety
    limit. Returns 0.0 if there's no edge or the sizing falls below `min_stake`."""
    fk = full_kelly_fraction(true_prob, decimal_odds)
    if fk <= 0:
        return 0.0
    fraction = min(fk * kelly_fraction, max_stake_pct)
    stake = round(bankroll * fraction, 2)
    return stake if stake >= min_stake else 0.0
