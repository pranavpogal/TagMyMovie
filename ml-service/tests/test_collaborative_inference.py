from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from app.collaborative.inference import infer_collaborative_candidates
from app.collaborative.model_loader import LoadedCollaborativeModel
from app.config import CollaborativeInferenceSettings


NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


class FakeModel:
    def __init__(self, *, factor=None) -> None:
        self.factor = np.asarray(factor if factor is not None else [1.0, 0.5])
        self.recalculate_calls = 0
        self.recommend_calls = []

    def recalculate_user(self, user_id, user_items):
        self.recalculate_calls += 1
        assert user_items.shape == (1, 5)
        return self.factor

    def recommend(
        self,
        user_id,
        user_items,
        N,
        filter_already_liked_items,
        recalculate_user,
    ):
        self.recommend_calls.append((user_id, recalculate_user, user_items.copy()))
        return np.asarray([3, 4]), np.asarray([0.9, 0.4])


def settings(tmp_path: Path) -> CollaborativeInferenceSettings:
    return CollaborativeInferenceSettings(tmp_path, 3, 10, 0.98, 2, 10)


def loaded(model, *, users=()) -> LoadedCollaborativeModel:
    return LoadedCollaborativeModel(
        model=model,
        user_ids=tuple(users),
        item_keys=("movie:1", "movie:2", "tv:1", "movie:3", "tv:2"),
        metadata={"modelVersion": "als-v1"},
        directory=Path("/model"),
    )


def interactions(count: int):
    keys = [("movie", "1"), ("movie", "2"), ("tv", "1")]
    return [
        {
            "mediaType": media_type,
            "mediaId": media_id,
            "eventType": "favourite_add",
            "value": 1,
            "createdAt": NOW,
        }
        for media_type, media_id in keys[:count]
    ]


def test_new_user_uses_temporary_factor_without_mutating_model_or_artifacts(tmp_path: Path) -> None:
    model = FakeModel()
    result = infer_collaborative_candidates(
        "new-user",
        interactions(3),
        settings=settings(tmp_path),
        now=NOW,
        loaded=loaded(model),
    )

    assert result.used_collaborative
    assert result.temporary_factor is True
    assert result.user_in_model is False
    assert result.overlap_items == 3
    assert result.collaborative_confidence == 0.3
    assert [(candidate.item_key, candidate.raw_score) for candidate in result.candidates] == [
        ("movie:3", 0.9),
        ("tv:2", 0.4),
    ]
    assert model.recalculate_calls == 1
    assert model.recommend_calls[0][1] is True
    assert list(tmp_path.iterdir()) == []


def test_known_user_uses_stored_factor_but_returns_confidence_separately(tmp_path: Path) -> None:
    model = FakeModel()
    result = infer_collaborative_candidates(
        "known-user",
        interactions(3),
        settings=settings(tmp_path),
        now=NOW,
        loaded=loaded(model, users=("known-user",)),
    )

    assert result.used_collaborative
    assert result.user_in_model is True
    assert result.temporary_factor is False
    assert result.collaborative_confidence == 0.3
    assert model.recalculate_calls == 0
    assert model.recommend_calls[0][1] is False


def test_no_or_insufficient_overlap_returns_explicit_content_fallback(tmp_path: Path) -> None:
    model = FakeModel()
    no_overlap = infer_collaborative_candidates(
        "user",
        [
            {
                "mediaType": "movie",
                "mediaId": "missing",
                "eventType": "favourite_add",
                "createdAt": NOW,
            }
        ],
        settings=settings(tmp_path),
        now=NOW,
        loaded=loaded(model),
    )
    insufficient = infer_collaborative_candidates(
        "user",
        interactions(2),
        settings=settings(tmp_path),
        now=NOW,
        loaded=loaded(model),
    )

    assert no_overlap.strategy == "content_fallback"
    assert no_overlap.fallback_reason == "no_overlapping_positive_items"
    assert no_overlap.collaborative_confidence == 0
    assert insufficient.fallback_reason == "insufficient_overlapping_items"
    assert insufficient.overlap_items == 2
    assert model.recalculate_calls == 0


def test_invalid_temporary_factor_and_missing_model_fall_back(tmp_path: Path) -> None:
    invalid_factor = infer_collaborative_candidates(
        "user",
        interactions(3),
        settings=settings(tmp_path),
        now=NOW,
        loaded=loaded(FakeModel(factor=[float("nan"), 0])),
    )
    missing_model = infer_collaborative_candidates(
        "user", interactions(3), settings=settings(tmp_path), now=NOW
    )

    assert invalid_factor.fallback_reason == "temporary_factor_invalid"
    assert missing_model.fallback_reason == "model_unavailable"
    assert missing_model.model_version is None
