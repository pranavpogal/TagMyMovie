from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from scipy.sparse import csr_matrix

from app.collaborative.interaction_weights import (
    COLLABORATIVE_CONFIDENCE_VERSION,
    WEAK_POSITIVE_EVENTS,
    collaborative_confidence,
    recency_multiplier,
)
from app.collaborative.mappings import MatrixMappings
from app.config import CollaborativeDatasetSettings


@dataclass
class MatrixSummary:
    scanned: int = 0
    duplicates: int = 0
    invalid: int = 0
    unresolved: int = 0
    non_positive: int = 0
    weak_users: int = 0
    users: int = 0
    items: int = 0
    interactions: int = 0
    scanned_native: int = 0
    scanned_external: int = 0
    interactions_native: int = 0
    interactions_external: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class CollaborativeDataset:
    matrix: csr_matrix
    mappings: MatrixMappings
    summary: MatrixSummary
    matrix_version: str
    confidence_version: str = COLLABORATIVE_CONFIDENCE_VERSION


@dataclass
class _PairConfidence:
    weak_sum: float = 0.0
    strong_sum: float = 0.0


def build_interaction_matrix(
    interactions: Iterable[dict[str, Any]],
    *,
    valid_user_ids: set[str],
    valid_item_keys: set[str],
    settings: CollaborativeDatasetSettings,
    now: datetime | None = None,
) -> CollaborativeDataset:
    settings.validate()
    reference_time = now or datetime.now(timezone.utc)
    summary = MatrixSummary()
    unique: list[dict[str, Any]] = []
    signatures: set[tuple[Any, ...]] = set()
    for interaction in interactions:
        summary.scanned += 1
        if interaction.get("dataSource") == "movielens":
            summary.scanned_external += 1
        else:
            summary.scanned_native += 1
        signature = _signature(interaction)
        if signature is None:
            summary.invalid += 1
            continue
        if signature in signatures:
            summary.duplicates += 1
            continue
        signatures.add(signature)
        unique.append(interaction)

    effective = _latest_state_interactions(unique)
    external_timestamps = [
        interaction["createdAt"]
        for interaction in effective
        if interaction.get("dataSource") == "movielens"
    ]
    external_reference_time = (
        max(external_timestamps) if external_timestamps else reference_time
    )
    pair_confidence: dict[tuple[str, str], _PairConfidence] = {}
    for interaction in effective:
        user_id = str(interaction.get("user") or "").strip()
        media_type = interaction.get("mediaType")
        media_id = str(interaction.get("mediaId") or "").strip()
        item_key = f"{media_type}:{media_id}"
        if user_id not in valid_user_ids or item_key not in valid_item_keys:
            summary.unresolved += 1
            continue
        base = collaborative_confidence(
            str(interaction.get("eventType") or ""), interaction.get("value")
        )
        if base <= 0:
            summary.non_positive += 1
            continue
        created_at = interaction["createdAt"]
        effective_weight = base * recency_multiplier(
            created_at,
            now=(
                external_reference_time
                if interaction.get("dataSource") == "movielens"
                else reference_time
            ),
            decay_factor=settings.decay_factor,
        )
        pair = pair_confidence.setdefault((user_id, item_key), _PairConfidence())
        if interaction.get("eventType") in WEAK_POSITIVE_EVENTS:
            pair.weak_sum += effective_weight
        else:
            pair.strong_sum += effective_weight

    values: dict[tuple[str, str], float] = {}
    for pair_key, confidence in pair_confidence.items():
        weak_confidence = min(
            settings.weak_confidence_cap, math.log1p(confidence.weak_sum)
        )
        total = min(
            settings.max_confidence, confidence.strong_sum + weak_confidence
        )
        if total > 0 and math.isfinite(total):
            values[pair_key] = total

    item_counts: dict[str, int] = {}
    for user_id, _ in values:
        item_counts[user_id] = item_counts.get(user_id, 0) + 1
    retained_users = {
        user_id
        for user_id, count in item_counts.items()
        if count >= settings.minimum_user_items
    }
    summary.weak_users = len(item_counts) - len(retained_users)
    retained = {
        pair: confidence
        for pair, confidence in values.items()
        if pair[0] in retained_users
    }
    mappings = MatrixMappings.stable(
        (user_id for user_id, _ in retained),
        (item_key for _, item_key in retained),
    )
    user_to_index = mappings.user_to_index
    item_to_index = mappings.item_to_index
    ordered = sorted(retained.items())
    matrix = csr_matrix(
        (
            [confidence for _, confidence in ordered],
            (
                [user_to_index[user_id] for (user_id, _), _ in ordered],
                [item_to_index[item_key] for (_, item_key), _ in ordered],
            ),
        ),
        shape=(len(mappings.users), len(mappings.items)),
        dtype="float32",
    )
    summary.users = matrix.shape[0]
    summary.items = matrix.shape[1]
    summary.interactions = matrix.nnz
    summary.interactions_external = sum(
        1 for (user_id, _), _ in retained.items() if user_id.startswith("movielens:")
    )
    summary.interactions_native = summary.interactions - summary.interactions_external
    return CollaborativeDataset(
        matrix=matrix,
        mappings=mappings,
        summary=summary,
        matrix_version=settings.matrix_version,
    )


def _signature(interaction: dict[str, Any]) -> tuple[Any, ...] | None:
    created_at = interaction.get("createdAt")
    media_type = interaction.get("mediaType")
    media_id = str(interaction.get("mediaId") or "").strip()
    user_id = str(interaction.get("user") or "").strip()
    if (
        not user_id
        or media_type not in {"movie", "tv"}
        or not media_id
        or not isinstance(created_at, datetime)
    ):
        return None
    return (
        user_id,
        media_type,
        media_id,
        interaction.get("eventType"),
        interaction.get("value"),
        created_at.isoformat(),
        interaction.get("sessionId"),
        interaction.get("recommendationId"),
    )


def _latest_state_interactions(
    interactions: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    repeated: list[dict[str, Any]] = []
    latest: dict[tuple[str, str, str], dict[str, Any]] = {}
    for interaction in interactions:
        event_type = interaction.get("eventType")
        if event_type == "rating_submit":
            family = "rating"
        elif event_type in {"favourite_add", "favourite_remove"}:
            family = "favourite"
        elif event_type == "onboarding_favourite":
            family = "onboarding"
        elif event_type == "not_interested":
            family = "not_interested"
        else:
            repeated.append(interaction)
            continue
        key = (
            str(interaction.get("user")),
            f"{interaction.get('mediaType')}:{interaction.get('mediaId')}",
            family,
        )
        current = latest.get(key)
        if current is None or interaction["createdAt"] >= current["createdAt"]:
            latest[key] = interaction
    return [*repeated, *latest.values()]
