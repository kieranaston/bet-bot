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

When Pinnacle is fresh, its own points still win at exact matches; consensus-book points the
sharp book doesn't quote are merged in as interpolation anchors so an Ontario half-point
mismatch can still resolve (the design intent of #2 above -- without that merge, a
single-line fresh Pinnacle forced exact match again).
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
    outcomes: list[tuple[object, float | None, float]], devig_method: str
) -> dict[object, list[tuple[float | None, float]]]:
    """Devigs one book's own full outcome set for a *single* 2-way (or 3-way h2h) market
    and returns {outcome_key: [(point, true_prob)]}. Correct for featured h2h/spreads/totals
    where the market blob is one line. Do NOT use this for alternate_totals / team_totals /
    alternate_team_totals ladders -- those put many lines in one market and must go through
    book_points_by_line (joint N-way degig collapses every side toward 1/N)."""
    if len(outcomes) < 2:
        return {}
    try:
        probs = devig([price for _, _, price in outcomes], method=devig_method)
    except ValueError:
        return {}
    result: dict[object, list[tuple[float | None, float]]] = defaultdict(list)
    for (key, point, _), prob in zip(outcomes, probs):
        result[key].append((point, prob))
    return dict(result)


def book_points_by_line(
    outcomes: list[tuple[object, float | None, float]], devig_method: str
) -> dict[object, list[tuple[float | None, float]]]:
    """Devigs each 2-way line independently for multi-line markets (alternate_totals,
    team_totals, alternate_team_totals). Groups by (description, point) when the outcome
    key is `(description, name)`, else by point alone. Each group must have >=2 sides."""
    groups: dict[tuple[object, float | None], list[tuple[object, float]]] = defaultdict(list)
    for key, point, price in outcomes:
        if isinstance(key, tuple) and len(key) == 2:
            description, _name = key
            line_id: tuple[object, float | None] = (description, point)
        else:
            line_id = (None, point)
        groups[line_id].append((key, price))

    result: dict[object, list[tuple[float | None, float]]] = defaultdict(list)
    for (_description, point), pairs in groups.items():
        if len(pairs) < 2:
            continue
        try:
            probs = devig([price for _, price in pairs], method=devig_method)
        except ValueError:
            continue
        for (key, _), prob in zip(pairs, probs):
            result[key].append((point, prob))
    return dict(result)


def build_curve(
    per_book_points: list[dict[object, list[tuple[float | None, float]]]],
    aggregate: str = "mean",
) -> dict[object, list[tuple[float | None, float]]]:
    """Merges independently-devigged per-book observations (from book_points / book_points_by_line,
    one dict per contributing book) into one probability curve per outcome key, sorted by
    point. Where multiple books agree on the exact same point, combines them via `aggregate`
    ("mean" or "median") -- median is used for the Pinnacle-fallback basket, for robustness
    against one outlier book; "mean" (the default) preserves player-prop consensus's existing
    behavior. Ready to pass to true_prob_at()."""
    combine = statistics.median if aggregate == "median" else statistics.mean
    grouped: dict[object, dict[float | None, list[float]]] = defaultdict(lambda: defaultdict(list))
    for book in per_book_points:
        for key, observations in book.items():
            for point, prob in observations:
                grouped[key][point].append(prob)
    curve: dict[object, list[tuple[float | None, float]]] = {}
    for key, by_point in grouped.items():
        points = sorted(by_point, key=lambda p: (p is not None, p if p is not None else 0.0))
        curve[key] = [(p, combine(by_point[p])) for p in points]
    return curve


def merge_curve_anchors(
    primary: dict[object, list[tuple[float | None, float]]],
    secondary: dict[object, list[tuple[float | None, float]]],
) -> dict[object, list[tuple[float | None, float]]]:
    """Keep primary probs at its observed points; add secondary points the primary doesn't
    have so true_prob_at can interpolate (e.g. fresh Pinnacle at -3.0 plus a consensus book
    at -4.0 bracketing an Ontario -3.5). Never overwrites a primary observation."""
    out: dict[object, list[tuple[float | None, float]]] = {
        key: list(observations) for key, observations in primary.items()
    }
    for key, observations in secondary.items():
        have = {point for point, _ in out.get(key, [])}
        extras = [(point, prob) for point, prob in observations if point not in have]
        if not extras:
            continue
        merged = out.get(key, []) + extras
        merged.sort(key=lambda x: (x[0] is not None, x[0] if x[0] is not None else 0.0))
        out[key] = merged
    return out


def select_reference(
    sharp_bm: dict | None,
    sharp_outcomes: list[tuple[object, float | None, float]] | None,
    basket_candidates: list[tuple[str, list[tuple[object, float | None, float]]]],
    devig_method: str,
    min_consensus_books: int,
    now: dt.datetime,
    max_staleness_minutes: float,
    *,
    pair_by_line: bool = False,
) -> tuple[dict[object, list[tuple[float | None, float]]], str] | None:
    """Picks the best available true-probability reference for one (event, market): Pinnacle
    if its bookmaker entry is present, fresh (is_fresh), and actually has this market
    (sharp_outcomes not None/empty) -- otherwise a median basket of whichever consensus
    books (config/bookmakers.yaml `consensus:`) also have it, if at least
    `min_consensus_books` distinct ones do. When Pinnacle is usable, consensus points it
    doesn't quote are still merged in as interpolation anchors (label stays the sharp key).

    `pair_by_line=True` uses book_points_by_line (required for alternate_totals / team_totals
    / alternate_team_totals ladders). Featured markets keep the default joint book_points.

    Returns (curve, contributing_label) -- contributing_label is "pinnacle" or a sorted
    comma-joined list of basket book keys, ready to store as Alert.sharp_book_key.
    Returns None if neither reference is usable."""
    points_fn = book_points_by_line if pair_by_line else book_points

    basket_keys: list[str] = []
    basket_points_list: list[dict[object, list[tuple[float | None, float]]]] = []
    for book_key, outcomes in basket_candidates:
        points = points_fn(outcomes, devig_method)
        if points:
            basket_keys.append(book_key)
            basket_points_list.append(points)

    basket_curve = (
        build_curve(basket_points_list, aggregate="median")
        if len(basket_keys) >= min_consensus_books
        else None
    )

    if sharp_bm is not None and sharp_outcomes and is_fresh(sharp_bm, now, max_staleness_minutes):
        sharp_points = points_fn(sharp_outcomes, devig_method)
        if sharp_points:
            curve = build_curve([sharp_points], aggregate="mean")
            if basket_curve is not None:
                curve = merge_curve_anchors(curve, basket_curve)
            return curve, sharp_bm["key"]

    if basket_curve is None:
        return None
    return basket_curve, ",".join(sorted(basket_keys))


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
