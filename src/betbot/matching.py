"""Turns whatever reference points we could actually observe -- one sharp book's own line,
or several high-volume books' independently-devigged lines -- into a fair probability at an
arbitrary target point. This is the shared primitive behind two related changes (see
CLAUDE.md's "Sharp reference selection" section):

1. Falling back from Pinnacle to a multi-book median basket when Pinnacle is absent or stale
   (Pinnacle odds are scraped from Pinnacle's own public website per The Odds API's docs, so
   gaps are an expected characteristic of the feed, not just a rare fluke -- live-verified
   2026-09-14 that Pinnacle returned zero data for every configured sport that day).
2. No longer requiring a book's line to match the reference at the *exact* same point --
   spreads/totals/alternates routinely disagree by half a point between books, which made the
   old exact-match requirement a much stricter filter for those markets than for moneyline
   (which has no point at all).
"""
from __future__ import annotations

import datetime as dt
import statistics
from collections import defaultdict

from betbot.devig import devig


def is_fresh(bookmaker: dict, now: dt.datetime, max_staleness_minutes: float) -> bool:
    """True if `bookmaker`'s own last_update is within max_staleness_minutes of now, OR if
    last_update is missing/unparseable. Real Odds API responses always carry it (verified
    live) -- a missing value only ever means synthetic test data, which should behave as
    "fresh" rather than silently routing every existing Pinnacle-path test into the fallback
    basket."""
    raw = bookmaker.get("last_update")
    if not raw:
        return True
    try:
        last_update = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return True
    age_minutes = (now - last_update).total_seconds() / 60.0
    return age_minutes <= max_staleness_minutes


def book_points(
    outcomes: list[tuple[str, float | None, float]], devig_method: str
) -> dict[str, list[tuple[float | None, float]]]:
    """Devigs one book's own full outcome set for a market independently (a book's vig only
    reflects its own pricing) and returns {outcome_name: [(point, true_prob)]} -- exactly one
    observation per name for a book that only quotes one line (typical h2h/spreads/totals),
    more for a book quoting several (e.g. Pinnacle's own alternate-line ladder). `outcomes` is
    (name, point, decimal_price), already extracted from one book's market. Returns {} if the
    market can't be devigged (fewer than two outcomes, or a bad price)."""
    if len(outcomes) < 2:
        return {}
    try:
        probs = devig([price for _, _, price in outcomes], method=devig_method)
    except ValueError:
        return {}
    result: dict[str, list[tuple[float | None, float]]] = defaultdict(list)
    for (name, point, _), prob in zip(outcomes, probs):
        result[name].append((point, prob))
    return dict(result)


def build_curve(
    per_book_points: list[dict[str, list[tuple[float | None, float]]]],
    aggregate: str = "mean",
) -> dict[str, list[tuple[float | None, float]]]:
    """Merges independently-devigged per-book observations (from book_points, one dict per
    contributing book) into one probability curve per outcome name, sorted by point. Where
    multiple books agree on the exact same point, combines them via `aggregate` ("mean" or
    "median") -- median is used for the Pinnacle-fallback basket, for robustness against one
    outlier book; "mean" (the default) preserves player-prop consensus's existing behavior.
    Ready to pass to true_prob_at()."""
    combine = statistics.median if aggregate == "median" else statistics.mean
    grouped: dict[str, dict[float | None, list[float]]] = defaultdict(lambda: defaultdict(list))
    for book in per_book_points:
        for name, observations in book.items():
            for point, prob in observations:
                grouped[name][point].append(prob)
    curve: dict[str, list[tuple[float | None, float]]] = {}
    for name, by_point in grouped.items():
        points = sorted(by_point, key=lambda p: (p is not None, p if p is not None else 0.0))
        curve[name] = [(p, combine(by_point[p])) for p in points]
    return curve


def select_reference(
    sharp_bm: dict | None,
    sharp_outcomes: list[tuple[object, float | None, float]] | None,
    basket_candidates: list[tuple[str, list[tuple[object, float | None, float]]]],
    devig_method: str,
    min_consensus_books: int,
    now: dt.datetime,
    max_staleness_minutes: float,
) -> tuple[dict[object, list[tuple[float | None, float]]], str] | None:
    """Picks the best available true-probability reference for one (event, market): Pinnacle
    if its bookmaker entry is present, fresh (is_fresh), and actually has this market
    (sharp_outcomes not None/empty) -- otherwise a median basket of whichever consensus
    books (config/bookmakers.yaml `consensus:`) also have it, if at least
    `min_consensus_books` distinct ones do. Returns (curve, contributing_label) --
    contributing_label is "pinnacle" or a sorted comma-joined list of basket book keys,
    ready to store as Alert.sharp_book_key exactly as before. Returns None if neither
    reference is usable -- caller should skip this market for this event, same as when
    Pinnacle alone was required.

    `sharp_outcomes`/each basket entry's outcomes are (outcome_key, point, decimal_price)
    already extracted from that book's market -- outcome_key is whatever the caller groups
    by (a bare outcome name for h2h/spreads/totals, or (description, name) for game-level
    alternate markets keyed by team/description -- see betbot.main)."""
    if sharp_bm is not None and sharp_outcomes and is_fresh(sharp_bm, now, max_staleness_minutes):
        points = book_points(sharp_outcomes, devig_method)
        if points:
            return build_curve([points], aggregate="mean"), sharp_bm["key"]

    contributing_keys = []
    per_book_points_list = []
    for book_key, outcomes in basket_candidates:
        points = book_points(outcomes, devig_method)
        if points:
            contributing_keys.append(book_key)
            per_book_points_list.append(points)

    if len(contributing_keys) < min_consensus_books:
        return None
    return build_curve(per_book_points_list, aggregate="median"), ",".join(sorted(contributing_keys))


def true_prob_at(
    curve: list[tuple[float | None, float]], target_point: float | None
) -> float | None:
    """Exact match if target_point is one of the curve's observed points (this covers h2h,
    where both sides are always point=None); otherwise linear interpolation if target_point
    is bracketed by two observed points; otherwise None. Never extrapolates -- a target point
    outside the observed range is treated as "no signal", the same conservative skip-on-
    mismatch behavior as before this existed, rather than guessing at a curve shape beyond
    what was actually observed."""
    for point, prob in curve:
        if point == target_point:
            return prob
    if target_point is None:
        return None  # h2h: no numeric bracketing applies, and the exact match above covers it

    below = [(p, pr) for p, pr in curve if p is not None and p < target_point]
    above = [(p, pr) for p, pr in curve if p is not None and p > target_point]
    if not below or not above:
        return None
    p0, v0 = max(below, key=lambda x: x[0])
    p1, v1 = min(above, key=lambda x: x[0])
    weight = (target_point - p0) / (p1 - p0)
    return v0 + weight * (v1 - v0)
