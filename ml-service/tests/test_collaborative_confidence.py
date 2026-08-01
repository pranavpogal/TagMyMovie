from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.collaborative.confidence import (
    PositiveActivity,
    calculate_collaborative_confidence,
    summarize_positive_activity,
)
from app.config import CollaborativeInferenceSettings


NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def settings() -> CollaborativeInferenceSettings:
    return CollaborativeInferenceSettings(Path("/model"), 3, 10, 0.98, 2, 10)


def activity(count: int, recency: float = 1.0) -> PositiveActivity:
    keys = frozenset(f"movie:{index}" for index in range(count))
    return PositiveActivity(count, keys, keys, recency)


@pytest.mark.parametrize(
    ("count", "tier", "expected"),
    [(2, "inactive", 0.0), (3, "low", 0.35), (6, "moderate", 0.70), (10, "normal", 1.0)],
)
def test_overlap_tiers_control_activation_and_ceiling(count, tier, expected) -> None:
    result = calculate_collaborative_confidence(
        activity(count),
        settings=settings(),
        user_in_model=True,
        factor=[1.0],
        model_trained_at=NOW,
        catalogue_item_count=count,
        model_item_count=count,
        now=NOW,
    )

    assert result.evidence.tier == tier
    assert result.score <= expected
    if count == 10:
        assert result.score == 1.0


def test_temporary_factor_age_and_catalogue_coverage_reduce_confidence() -> None:
    baseline = calculate_collaborative_confidence(
        activity(10), settings=settings(), user_in_model=True, factor=[1],
        model_trained_at=NOW, catalogue_item_count=10, model_item_count=10, now=NOW,
    )
    reduced = calculate_collaborative_confidence(
        activity(10, 0.5), settings=settings(), user_in_model=False, factor=[1],
        model_trained_at=NOW - timedelta(days=100), catalogue_item_count=20,
        model_item_count=10, now=NOW,
    )

    assert reduced.score < baseline.score
    assert reduced.evidence.model_age_days == 100
    assert reduced.evidence.catalogue_coverage == 0.5


def test_invalid_factor_never_activates_collaborative_scoring() -> None:
    result = calculate_collaborative_confidence(
        activity(10), settings=settings(), user_in_model=True, factor=[float("nan")],
        model_trained_at="invalid", catalogue_item_count=10, model_item_count=10, now=NOW,
    )

    assert result.score == 0
    assert result.evidence.factor_valid is False
    assert result.evidence.model_age_days is None
    assert result.evidence.model_recency == 0


def test_positive_activity_deduplicates_and_applies_latest_state() -> None:
    favourite = {
        "mediaType": "movie", "mediaId": "1", "eventType": "favourite_add",
        "value": 1, "createdAt": NOW,
    }
    interactions = [
        favourite,
        dict(favourite),
        {**favourite, "mediaId": "2", "eventType": "rating_submit", "value": 9},
        {**favourite, "mediaId": "2", "eventType": "rating_submit", "value": 4,
         "createdAt": NOW + timedelta(seconds=1)},
        {**favourite, "mediaId": "3", "eventType": "detail_view"},
        {**favourite, "mediaId": "4", "createdAt": "invalid"},
    ]

    result = summarize_positive_activity(
        interactions, model_item_keys={"movie:1", "movie:3"}, now=NOW,
        decay_factor=0.98,
    )

    assert result.meaningful_interactions == 2
    assert result.unique_item_keys == {"movie:1", "movie:3"}
    assert result.overlapping_item_keys == {"movie:1", "movie:3"}
    assert result.recency_score == 1.0
