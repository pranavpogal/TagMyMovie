from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.collaborative.matrix_builder import build_interaction_matrix
from app.config import CollaborativeDatasetSettings


NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def settings(tmp_path: Path, *, minimum_user_items: int = 2):
    return CollaborativeDatasetSettings(
        mongodb_url="mongodb://example",
        mongodb_database="tagmymovie",
        artifact_directory=tmp_path,
        matrix_version="matrix-v1",
        decay_factor=0.98,
        weak_confidence_cap=2,
        max_confidence=10,
        minimum_user_items=minimum_user_items,
    )


def event(
    user: str,
    media_id: str,
    event_type: str,
    *,
    media_type: str = "movie",
    value=1,
    days_ago=0,
    session="session",
):
    return {
        "user": user,
        "mediaId": media_id,
        "mediaType": media_type,
        "eventType": event_type,
        "value": value,
        "createdAt": NOW - timedelta(days=days_ago),
        "sessionId": session,
        "recommendationId": None,
    }


def test_builds_stable_compound_sparse_matrix_with_saturated_weak_events(tmp_path: Path) -> None:
    interactions = [
        event("user-b", "1", "detail_view", session="a"),
        event("user-b", "1", "detail_view", session="b"),
        event("user-b", "1", "detail_view", session="b"),  # exact duplicate
        event("user-b", "1", "favourite_add", media_type="tv"),
        event("user-a", "2", "favourite_add"),
        event("user-a", "3", "rating_submit", value=9),
    ]
    dataset = build_interaction_matrix(
        interactions,
        valid_user_ids={"user-a", "user-b"},
        valid_item_keys={"movie:1", "tv:1", "movie:2", "movie:3"},
        settings=settings(tmp_path),
        now=NOW,
    )

    assert dataset.mappings.users == ("user-a", "user-b")
    assert dataset.mappings.items == ("movie:1", "movie:2", "movie:3", "tv:1")
    assert dataset.matrix.shape == (2, 4)
    assert dataset.matrix.nnz == 4
    dense = dataset.matrix.toarray()
    assert dense[dataset.mappings.user_to_index["user-b"]][dataset.mappings.item_to_index["movie:1"]] == pytest.approx(math.log1p(0.2))
    assert dense[dataset.mappings.user_to_index["user-b"]][dataset.mappings.item_to_index["tv:1"]] == 4
    assert dataset.summary.duplicates == 1


def test_latest_negative_state_is_not_positive_and_weak_users_are_removed(tmp_path: Path) -> None:
    interactions = [
        event("user-a", "1", "rating_submit", value=10, days_ago=2),
        event("user-a", "1", "rating_submit", value=2, days_ago=1),
        event("user-a", "2", "favourite_add", days_ago=2),
        event("user-a", "2", "favourite_remove", days_ago=1),
        event("user-a", "3", "not_interested"),
        event("user-b", "4", "trailer_play"),
    ]
    dataset = build_interaction_matrix(
        interactions,
        valid_user_ids={"user-a", "user-b"},
        valid_item_keys={f"movie:{value}" for value in range(1, 5)},
        settings=settings(tmp_path, minimum_user_items=2),
        now=NOW,
    )

    assert dataset.matrix.shape == (0, 0)
    assert dataset.summary.non_positive == 3
    assert dataset.summary.weak_users == 1


def test_filters_invalid_deleted_unresolved_and_impression_records(tmp_path: Path) -> None:
    interactions = [
        event("deleted", "1", "favourite_add"),
        event("user", "missing", "favourite_add"),
        event("user", "1", "recommendation_impression"),
        {**event("user", "1", "detail_view"), "createdAt": "invalid"},
        {**event("user", "1", "detail_view"), "user": None},
    ]
    dataset = build_interaction_matrix(
        interactions,
        valid_user_ids={"user"},
        valid_item_keys={"movie:1"},
        settings=settings(tmp_path, minimum_user_items=1),
        now=NOW,
    )

    assert dataset.matrix.nnz == 0
    assert dataset.summary.invalid == 2
    assert dataset.summary.unresolved == 2
    assert dataset.summary.non_positive == 1


def test_confidence_uses_decay_cap_and_float32(tmp_path: Path) -> None:
    interactions = [
        event("user", "1", "trailer_play", days_ago=10, session=str(index))
        for index in range(100)
    ]
    dataset = build_interaction_matrix(
        interactions,
        valid_user_ids={"user"},
        valid_item_keys={"movie:1"},
        settings=settings(tmp_path, minimum_user_items=1),
        now=NOW,
    )

    assert dataset.matrix.data[0] == pytest.approx(2)
    assert dataset.matrix.dtype.name == "float32"


def test_summary_records_native_and_external_matrix_counts(tmp_path: Path) -> None:
    interactions = [
        {**event("native", "1", "favourite_add"), "dataSource": "tagmymovie"},
        {**event("movielens:1", "2", "rating_submit", value=10), "dataSource": "movielens"},
    ]
    dataset = build_interaction_matrix(
        interactions,
        valid_user_ids={"native", "movielens:1"},
        valid_item_keys={"movie:1", "movie:2"},
        settings=settings(tmp_path, minimum_user_items=1),
        now=NOW,
    )

    assert dataset.summary.scanned_native == 1
    assert dataset.summary.scanned_external == 1
    assert dataset.summary.interactions_native == 1
    assert dataset.summary.interactions_external == 1


def test_external_decay_is_relative_to_movielens_dataset_end(tmp_path: Path) -> None:
    old = datetime(2000, 1, 1, tzinfo=timezone.utc)
    interactions = [
        {
            **event("movielens:1", "1", "rating_submit", value=9),
            "createdAt": old,
            "dataSource": "movielens",
        },
        {
            **event("movielens:1", "2", "rating_submit", value=9),
            "createdAt": old + timedelta(days=1),
            "dataSource": "movielens",
        },
    ]
    dataset = build_interaction_matrix(
        interactions,
        valid_user_ids={"movielens:1"},
        valid_item_keys={"movie:1", "movie:2"},
        settings=settings(tmp_path),
        now=NOW,
    )

    values = dataset.matrix.toarray()[0]
    assert sorted(values) == pytest.approx(sorted([3 * 0.98, 3]))
