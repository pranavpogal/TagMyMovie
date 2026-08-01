from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from app.config import ProfileSettings
from app.content.profile import aggregate_media_weights, build_content_profile


NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)
SETTINGS = ProfileSettings("profile-v1", 0.98, 2.0, 0.35)


def interaction(media_id: str, event_type: str, *, value=1, days_ago=0):
    return {
        "mediaId": media_id,
        "mediaType": "movie",
        "eventType": event_type,
        "value": value,
        "createdAt": NOW - timedelta(days=days_ago),
    }


def test_repeated_weak_activity_is_aggregated_and_capped_below_favourite() -> None:
    interactions = [interaction("1", "detail_view") for _ in range(20)]
    interactions.extend([interaction("2", "favourite_add")])

    weights = aggregate_media_weights(interactions, settings=SETTINGS, now=NOW)

    assert weights["movie:1"].positive_weight == 2
    assert weights["movie:2"].positive_weight == 4


def test_onboarding_seed_is_added_once_and_uses_compound_identity() -> None:
    weights = aggregate_media_weights(
        [interaction("1", "onboarding_favourite")],
        settings=SETTINGS,
        now=NOW,
        onboarding_seed_keys=("movie:1", "tv:1", "invalid"),
    )

    assert weights["movie:1"].positive_weight == 4
    assert weights["tv:1"].positive_weight == 4
    assert "invalid" not in weights


def test_latest_rating_and_favourite_state_replace_older_state() -> None:
    weights = aggregate_media_weights(
        [
            interaction("1", "rating_submit", value=10, days_ago=2),
            interaction("1", "rating_submit", value=2, days_ago=1),
            interaction("2", "favourite_add", days_ago=2),
            interaction("2", "favourite_remove", days_ago=1),
        ],
        settings=SETTINGS,
        now=NOW,
    )

    assert weights["movie:1"].positive_weight == 0
    assert weights["movie:1"].negative_weight == pytest.approx(3 * 0.98)
    assert weights["movie:2"].positive_weight == 0
    assert weights["movie:2"].negative_weight == pytest.approx(1.5 * 0.98)


def test_profile_subtracts_bounded_negative_centroid_and_normalizes() -> None:
    profile = build_content_profile(
        [interaction("1", "favourite_add"), interaction("2", "not_interested")],
        {"movie:1": [1, 0], "movie:2": [0, 1]},
        settings=SETTINGS,
        now=NOW,
    )

    norm = math.sqrt(1 + 0.35**2)
    assert profile.status == "ready"
    assert profile.vector == pytest.approx((1 / norm, -0.35 / norm))
    assert profile.positive_weight == 4
    assert profile.negative_weight == 4
    assert profile.contributing_media == 2


def test_decay_changes_centroid_in_favour_of_recent_activity() -> None:
    profile = build_content_profile(
        [
            interaction("old", "favourite_add", days_ago=100),
            interaction("new", "favourite_add"),
        ],
        {"movie:old": [1, 0], "movie:new": [0, 1]},
        settings=SETTINGS,
        now=NOW,
    )

    assert profile.vector[1] > profile.vector[0]
    assert math.sqrt(sum(value * value for value in profile.vector)) == pytest.approx(1)


def test_negative_only_missing_and_degenerate_profiles_return_cold_start() -> None:
    negative_only = build_content_profile(
        [interaction("1", "not_interested")],
        {"movie:1": [1, 0]},
        settings=SETTINGS,
        now=NOW,
    )
    missing = build_content_profile(
        [interaction("1", "favourite_add")], {}, settings=SETTINGS, now=NOW
    )
    degenerate = build_content_profile(
        [interaction("1", "favourite_add")],
        {"movie:1": [0, 0]},
        settings=SETTINGS,
        now=NOW,
    )

    assert negative_only.is_cold_start
    assert negative_only.reason == "no_positive_profile_evidence"
    assert missing.is_cold_start
    assert degenerate.is_cold_start
    assert all(profile.vector == () for profile in (negative_only, missing, degenerate))
