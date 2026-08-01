from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, Iterable, Mapping


NORMALIZATION_VERSION = "tied-rank-percentile-v1"
EQUAL_POOL_SCORE = 0.5


def normalize_candidate_scores(candidates: Iterable[Any]) -> tuple[Any, ...]:
    """Attach independently normalized [0, 1] scores without changing raw scores."""
    ordered = tuple(candidates)
    sources = sorted(
        {
            source
            for candidate in ordered
            for source, score in candidate.raw_scores.items()
            if _finite_number(score)
        }
    )
    by_item: dict[str, dict[str, float]] = {
        candidate.item_key: {} for candidate in ordered
    }
    for source in sources:
        values = [
            (candidate.item_key, float(candidate.raw_scores[source]))
            for candidate in ordered
            if source in candidate.raw_scores
            and _finite_number(candidate.raw_scores[source])
        ]
        for item_key, percentile in tied_rank_percentiles(values).items():
            by_item[item_key][source] = percentile
    return tuple(
        replace(candidate, normalized_scores=by_item[candidate.item_key])
        for candidate in ordered
    )


def tied_rank_percentiles(
    values: Iterable[tuple[str, float]],
) -> Mapping[str, float]:
    """Map higher-is-better values to percentiles, assigning ties their mean rank."""
    valid = [
        (str(item_key), float(score))
        for item_key, score in values
        if _finite_number(score)
    ]
    if not valid:
        return {}
    if len(valid) == 1:
        return {valid[0][0]: 1.0}
    if len({score for _, score in valid}) == 1:
        return {item_key: EQUAL_POOL_SCORE for item_key, _ in valid}

    ordered = sorted(valid, key=lambda value: (-value[1], value[0]))
    denominator = len(ordered) - 1
    normalized: dict[str, float] = {}
    position = 0
    while position < len(ordered):
        end = position + 1
        while end < len(ordered) and ordered[end][1] == ordered[position][1]:
            end += 1
        average_rank = (position + end - 1) / 2
        percentile = 1.0 - average_rank / denominator
        for item_key, _ in ordered[position:end]:
            normalized[item_key] = percentile
        position = end
    return normalized


def _finite_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False
