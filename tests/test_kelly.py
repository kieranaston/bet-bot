import pytest

from betbot.kelly import full_kelly_fraction, stake_amount


def test_full_kelly_zero_when_no_edge():
    assert full_kelly_fraction(0.5, 2.0) == pytest.approx(0.0)


def test_full_kelly_positive_with_edge():
    # true_prob 0.55, decimal odds 2.0 -> full kelly = (0.55*1 - 0.45)/1 = 0.10
    assert full_kelly_fraction(0.55, 2.0) == pytest.approx(0.10)


def test_stake_amount_applies_quarter_kelly():
    stake = stake_amount(
        true_prob=0.55,
        decimal_odds=2.0,
        bankroll=1000.0,
        kelly_fraction=0.25,
        max_stake_pct=0.05,
        min_stake=1.0,
    )
    # full kelly 10% * 0.25 = 2.5% of 1000 = 25.0
    assert stake == pytest.approx(25.0)


def test_stake_amount_capped_by_max_pct():
    stake = stake_amount(
        true_prob=0.90,
        decimal_odds=3.0,  # huge edge -> full kelly way above cap
        bankroll=1000.0,
        kelly_fraction=0.25,
        max_stake_pct=0.05,
        min_stake=1.0,
    )
    assert stake == pytest.approx(50.0)  # 5% cap


def test_stake_amount_zero_below_min_stake():
    stake = stake_amount(
        true_prob=0.51,
        decimal_odds=2.0,
        bankroll=10.0,  # tiny bankroll -> computed stake rounds below min_stake
        kelly_fraction=0.25,
        max_stake_pct=0.05,
        min_stake=1.0,
    )
    assert stake == 0.0


def test_stake_amount_zero_when_no_edge():
    stake = stake_amount(
        true_prob=0.45,
        decimal_odds=2.0,
        bankroll=1000.0,
        kelly_fraction=0.25,
        max_stake_pct=0.05,
        min_stake=1.0,
    )
    assert stake == 0.0
