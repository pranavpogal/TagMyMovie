from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable


TRACKED_EVENTS = {
    "recommendation_click": "clicks",
    "favourite_add": "favourites",
    "rating_submit": "ratings",
    "not_interested": "notInterested",
}


def generate_online_metrics(
    impressions: Iterable[dict[str, Any]], interactions: Iterable[dict[str, Any]],
    *, catalogue_item_count: int, attribution_window: timedelta = timedelta(hours=24),
    period_start: datetime | None = None, period_end: datetime | None = None,
) -> dict[str, Any]:
    if catalogue_item_count < 0 or attribution_window.total_seconds() <= 0:
        raise ValueError("report settings are invalid")
    end = period_end or datetime.now(timezone.utc)
    start = period_start or end - timedelta(days=30)
    if start >= end:
        raise ValueError("report period is invalid")

    batches: dict[str, dict[str, Any]] = {}
    exposures: dict[tuple[str, str, str], dict[str, Any]] = {}
    recent_by_item: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    strategies = Counter()
    for impression in impressions:
        recommendation_id = str(impression.get("recommendationId") or "").strip()
        user = str(impression.get("user") or "").strip()
        created_at = impression.get("createdAt")
        strategy = str(impression.get("strategy") or "unknown")
        if not recommendation_id or not user or not isinstance(created_at, datetime) or not start <= created_at <= end:
            continue
        batches[recommendation_id] = impression
        strategies[strategy] += 1
        for item in impression.get("items") or []:
            media_type = item.get("mediaType")
            media_id = str(item.get("mediaId") or "").strip()
            rank = item.get("rank")
            if media_type not in {"movie", "tv"} or not media_id or not isinstance(rank, int) or rank < 1:
                continue
            exposure = {"recommendationId": recommendation_id, "user": user,
                        "mediaType": media_type, "mediaId": media_id, "rank": rank,
                        "strategy": strategy, "createdAt": created_at}
            exposures[(recommendation_id, media_type, media_id)] = exposure
            recent_by_item[(user, media_type, media_id)].append(exposure)
    for values in recent_by_item.values():
        values.sort(key=lambda value: value["createdAt"], reverse=True)

    attributed: dict[str, set[tuple[str, str, str]]] = {
        metric: set() for metric in TRACKED_EVENTS.values()
    }
    clicked_ranks: list[int] = []
    attribution_counts = Counter()
    for interaction in sorted(interactions, key=lambda value: value.get("createdAt") or start):
        event = interaction.get("eventType")
        metric = TRACKED_EVENTS.get(event)
        created_at = interaction.get("createdAt")
        user = str(interaction.get("user") or "").strip()
        media_type = interaction.get("mediaType")
        media_id = str(interaction.get("mediaId") or "").strip()
        if not metric or not isinstance(created_at, datetime) or not start <= created_at <= end + attribution_window:
            continue
        exposure = _direct_exposure(interaction, exposures, user, media_type, media_id, created_at, attribution_window)
        method = "direct"
        if exposure is None and event in {"favourite_add", "rating_submit", "not_interested"}:
            exposure = _recent_exposure(recent_by_item.get((user, media_type, media_id), []), created_at, attribution_window)
            method = "recent_item"
        if exposure is None:
            continue
        key = (exposure["recommendationId"], media_type, media_id)
        if key in attributed[metric]:
            continue
        attributed[metric].add(key)
        attribution_counts[method] += 1
        if event == "recommendation_click":
            rank = interaction.get("recommendationRank") or exposure["rank"]
            if isinstance(rank, (int, float)) and rank >= 1:
                clicked_ranks.append(int(rank))

    exposure_count = len(exposures)
    batch_count = len(batches)
    unique_items = {(value["mediaType"], value["mediaId"]) for value in exposures.values()}
    strategy_usage = {
        strategy: {"count": count, "share": count / batch_count if batch_count else 0.0}
        for strategy, count in sorted(strategies.items())
    }
    rate = lambda count: count / exposure_count if exposure_count else None
    warning = "no recommendation impressions in the reporting period" if not exposure_count else None
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat(),
                   "attributionWindowHours": attribution_window.total_seconds() / 3600},
        "counts": {"recommendationBatches": batch_count, "itemExposures": exposure_count,
                   "uniqueRecommendedItems": len(unique_items),
                   "attributedClicks": len(attributed["clicks"]),
                   "attributedFavouriteAdds": len(attributed["favourites"]),
                   "attributedRatings": len(attributed["ratings"]),
                   "attributedNotInterested": len(attributed["notInterested"]),
                   "directAttributions": attribution_counts["direct"],
                   "recentItemAttributions": attribution_counts["recent_item"]},
        "metrics": {
            "recommendationClickThroughRate": rate(len(attributed["clicks"])),
            "favouriteAddRateAfterRecommendation": rate(len(attributed["favourites"])),
            "ratingSubmissionRateAfterRecommendation": rate(len(attributed["ratings"])),
            "notInterestedRate": rate(len(attributed["notInterested"])),
            "recommendedCatalogueCoverage": len(unique_items) / catalogue_item_count if catalogue_item_count else None,
            "averageRecommendationRankClicked": sum(clicked_ranks) / len(clicked_ranks) if clicked_ranks else None,
            "strategyUsageDistribution": strategy_usage,
        },
        "warning": warning,
        "interpretation": "Observational application metrics only; they do not establish causal impact without a controlled experiment.",
    }


def _direct_exposure(interaction, exposures, user, media_type, media_id, created_at, window):
    recommendation_id = str(interaction.get("recommendationId") or "").strip()
    exposure = exposures.get((recommendation_id, media_type, media_id))
    if exposure and exposure["user"] == user and exposure["createdAt"] <= created_at <= exposure["createdAt"] + window:
        return exposure
    return None


def _recent_exposure(values, created_at, window):
    return next((value for value in values if value["createdAt"] <= created_at <= value["createdAt"] + window), None)
