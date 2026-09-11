"""Roll up settled bets into performance stats: units won/lost, ROI, win rate, CLV."""
from __future__ import annotations

from dataclasses import dataclass

from betbot.storage import Alert


@dataclass
class PerformanceSummary:
    bets_settled: int
    wins: int
    losses: int
    pushes: int
    total_staked: float
    total_profit: float
    roi_pct: float
    avg_clv_pct: float | None


def summarize(alerts: list[Alert]) -> PerformanceSummary:
    settled = [a for a in alerts if a.status.startswith("settled_")]
    wins = sum(1 for a in settled if a.status == "settled_win")
    losses = sum(1 for a in settled if a.status == "settled_loss")
    pushes = sum(1 for a in settled if a.status == "settled_push")
    total_staked = sum(a.placed_stake or 0.0 for a in settled)
    total_profit = sum(a.profit or 0.0 for a in settled)
    roi_pct = (total_profit / total_staked * 100.0) if total_staked else 0.0

    clv_values = []
    for a in settled:
        if a.closing_odds and a.placed_stake:
            # CLV: how much better (or worse) your price was vs the closing line, in
            # percentage points of implied probability. Positive = you beat the closing line.
            clv_values.append((1 / a.closing_odds - 1 / a.book_odds) * 100.0)
    avg_clv_pct = sum(clv_values) / len(clv_values) if clv_values else None

    return PerformanceSummary(
        bets_settled=len(settled),
        wins=wins,
        losses=losses,
        pushes=pushes,
        total_staked=round(total_staked, 2),
        total_profit=round(total_profit, 2),
        roi_pct=round(roi_pct, 2),
        avg_clv_pct=round(avg_clv_pct, 2) if avg_clv_pct is not None else None,
    )
