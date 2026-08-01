from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

import numpy as np
from scipy.sparse import csr_matrix

from app.collaborative.matrix_builder import build_interaction_matrix
from app.collaborative.model_loader import (
    CollaborativeArtifactError,
    LoadedCollaborativeModel,
    load_current_model,
)
from app.config import (
    CollaborativeDatasetSettings,
    CollaborativeInferenceSettings,
)


@dataclass(frozen=True)
class CollaborativeCandidate:
    media_type: str
    media_id: str
    raw_score: float

    @property
    def item_key(self) -> str:
        return f"{self.media_type}:{self.media_id}"


@dataclass(frozen=True)
class CollaborativeInferenceResult:
    strategy: str
    candidates: tuple[CollaborativeCandidate, ...]
    collaborative_confidence: float
    overlap_items: int
    user_in_model: bool
    temporary_factor: bool
    fallback_reason: str | None
    model_version: str | None

    @property
    def used_collaborative(self) -> bool:
        return self.strategy == "collaborative"


def infer_collaborative_candidates(
    user_id: str,
    interactions: Iterable[dict[str, Any]],
    *,
    settings: CollaborativeInferenceSettings,
    limit: int = 20,
    now: datetime | None = None,
    loaded: LoadedCollaborativeModel | None = None,
) -> CollaborativeInferenceResult:
    settings.validate()
    if limit < 1:
        raise ValueError("limit must be positive")
    try:
        active = loaded or load_current_model(settings.artifact_directory)
    except CollaborativeArtifactError:
        return _fallback("model_unavailable")

    interaction_list = [{**interaction, "user": user_id} for interaction in interactions]
    dataset_settings = CollaborativeDatasetSettings(
        mongodb_url="in-memory",
        mongodb_database="in-memory",
        artifact_directory=settings.artifact_directory,
        matrix_version="inference",
        decay_factor=settings.decay_factor,
        weak_confidence_cap=settings.weak_confidence_cap,
        max_confidence=settings.max_confidence,
        minimum_user_items=1,
    )
    user_dataset = build_interaction_matrix(
        interaction_list,
        valid_user_ids={user_id},
        valid_item_keys=set(active.item_keys),
        settings=dataset_settings,
        now=now,
    )
    if not user_dataset.mappings.users:
        return _fallback(
            "no_overlapping_positive_items",
            user_in_model=user_id in active.user_to_index,
            model_version=active.metadata.get("modelVersion"),
        )
    local_user_index = user_dataset.mappings.user_to_index[user_id]
    local_row = user_dataset.matrix[local_user_index]
    model_item_to_index = active.item_to_index
    columns = [
        model_item_to_index[user_dataset.mappings.items[index]]
        for index in local_row.indices
    ]
    model_row = csr_matrix(
        (local_row.data, ([0] * len(columns), columns)),
        shape=(1, len(active.item_keys)),
        dtype="float32",
    )
    overlap = model_row.nnz
    user_in_model = user_id in active.user_to_index
    if overlap < settings.minimum_overlap_items:
        return _fallback(
            "insufficient_overlapping_items",
            overlap_items=overlap,
            user_in_model=user_in_model,
            model_version=active.metadata.get("modelVersion"),
        )

    temporary_factor = not user_in_model
    model_user_index = active.user_to_index.get(user_id, 0)
    if temporary_factor:
        try:
            factor = np.asarray(
                active.model.recalculate_user(model_user_index, model_row)
            )
        except Exception:
            return _fallback(
                "temporary_factor_unavailable",
                overlap_items=overlap,
                model_version=active.metadata.get("modelVersion"),
            )
        if (
            factor.ndim != 1
            or factor.size == 0
            or not np.isfinite(factor).all()
            or float(np.linalg.norm(factor)) <= 1e-12
        ):
            return _fallback(
                "temporary_factor_invalid",
                overlap_items=overlap,
                model_version=active.metadata.get("modelVersion"),
            )

    try:
        item_ids, scores = active.model.recommend(
            model_user_index,
            model_row,
            N=min(limit, len(active.item_keys)),
            filter_already_liked_items=True,
            recalculate_user=temporary_factor,
        )
    except Exception:
        return _fallback(
            "collaborative_recommendation_failed",
            overlap_items=overlap,
            user_in_model=user_in_model,
            model_version=active.metadata.get("modelVersion"),
        )
    candidates: list[CollaborativeCandidate] = []
    for item_index, score in zip(item_ids, scores):
        numeric_score = float(score)
        index = int(item_index)
        if (
            index < 0
            or index >= len(active.item_keys)
            or not math.isfinite(numeric_score)
        ):
            continue
        media_type, media_id = active.item_keys[index].split(":", 1)
        candidates.append(
            CollaborativeCandidate(media_type, media_id, numeric_score)
        )
    if not candidates:
        return _fallback(
            "no_collaborative_candidates",
            overlap_items=overlap,
            user_in_model=user_in_model,
            model_version=active.metadata.get("modelVersion"),
        )
    confidence = min(1.0, overlap / settings.full_confidence_items)
    return CollaborativeInferenceResult(
        strategy="collaborative",
        candidates=tuple(candidates),
        collaborative_confidence=confidence,
        overlap_items=overlap,
        user_in_model=user_in_model,
        temporary_factor=temporary_factor,
        fallback_reason=None,
        model_version=active.metadata.get("modelVersion"),
    )


def _fallback(
    reason: str,
    *,
    overlap_items: int = 0,
    user_in_model: bool = False,
    model_version: str | None = None,
) -> CollaborativeInferenceResult:
    return CollaborativeInferenceResult(
        strategy="content_fallback",
        candidates=(),
        collaborative_confidence=0.0,
        overlap_items=overlap_items,
        user_in_model=user_in_model,
        temporary_factor=False,
        fallback_reason=reason,
        model_version=model_version,
    )


class CollaborativeInferenceService:
    def __init__(self, repository: Any, settings: CollaborativeInferenceSettings) -> None:
        self.repository = repository
        self.settings = settings

    def recommend(
        self, user_id: str, *, limit: int = 20, now: datetime | None = None
    ) -> CollaborativeInferenceResult:
        return infer_collaborative_candidates(
            user_id,
            self.repository.user_interactions(user_id),
            settings=self.settings,
            limit=limit,
            now=now,
        )
