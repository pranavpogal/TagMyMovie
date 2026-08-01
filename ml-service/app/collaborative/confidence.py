from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

from app.collaborative.interaction_weights import (
    collaborative_confidence,
    recency_multiplier,
)
from app.config import CollaborativeInferenceSettings


CONFIDENCE_VERSION = "collaborative-confidence-v1"


@dataclass(frozen=True)
class CollaborativeConfidenceEvidence:
    meaningful_interactions: int
    unique_interacted_items: int
    overlapping_items: int
    interaction_recency: float
    model_age_days: float | None
    model_recency: float
    catalogue_coverage: float
    factor_valid: bool
    user_in_model: bool
    tier: str
    version: str = CONFIDENCE_VERSION


@dataclass(frozen=True)
class CollaborativeConfidence:
    score: float
    evidence: CollaborativeConfidenceEvidence


@dataclass(frozen=True)
class PositiveActivity:
    meaningful_interactions: int
    unique_item_keys: frozenset[str]
    overlapping_item_keys: frozenset[str]
    recency_score: float


def summarize_positive_activity(
    interactions: Iterable[dict[str, Any]],
    *,
    model_item_keys: set[str],
    now: datetime,
    decay_factor: float,
) -> PositiveActivity:
    unique_records: list[dict[str, Any]] = []
    signatures: set[tuple[Any, ...]] = set()
    for interaction in interactions:
        signature = _signature(interaction)
        if signature is None or signature in signatures:
            continue
        signatures.add(signature)
        unique_records.append(interaction)
    effective = _latest_state(unique_records)
    positive: list[dict[str, Any]] = []
    item_keys: set[str] = set()
    recency_values: list[float] = []
    for interaction in effective:
        if collaborative_confidence(
            str(interaction.get("eventType") or ""), interaction.get("value")
        ) <= 0:
            continue
        item_key = f"{interaction['mediaType']}:{str(interaction['mediaId']).strip()}"
        positive.append(interaction)
        item_keys.add(item_key)
        recency_values.append(
            recency_multiplier(
                interaction["createdAt"], now=now, decay_factor=decay_factor
            )
        )
    return PositiveActivity(
        meaningful_interactions=len(positive),
        unique_item_keys=frozenset(item_keys),
        overlapping_item_keys=frozenset(item_keys.intersection(model_item_keys)),
        recency_score=(sum(recency_values) / len(recency_values) if recency_values else 0.0),
    )


def calculate_collaborative_confidence(
    activity: PositiveActivity,
    *,
    settings: CollaborativeInferenceSettings,
    user_in_model: bool,
    factor: Sequence[float] | Any,
    model_trained_at: Any,
    catalogue_item_count: int,
    model_item_count: int,
    now: datetime,
) -> CollaborativeConfidence:
    factor_valid = valid_factor(factor)
    overlap = len(activity.overlapping_item_keys)
    tier, tier_ceiling = _tier(overlap, settings)
    model_age_days, model_recency = _model_recency(
        model_trained_at, now, settings.model_recency_decay_factor
    )
    coverage = (
        min(1.0, model_item_count / catalogue_item_count)
        if catalogue_item_count > 0
        else 0.0
    )
    evidence = CollaborativeConfidenceEvidence(
        meaningful_interactions=activity.meaningful_interactions,
        unique_interacted_items=len(activity.unique_item_keys),
        overlapping_items=overlap,
        interaction_recency=activity.recency_score,
        model_age_days=model_age_days,
        model_recency=model_recency,
        catalogue_coverage=coverage,
        factor_valid=factor_valid,
        user_in_model=user_in_model,
        tier=tier,
    )
    if tier == "inactive" or not factor_valid:
        return CollaborativeConfidence(0.0, evidence)

    activity_depth = min(
        1.0, activity.meaningful_interactions / settings.full_confidence_items
    )
    unique_depth = min(
        1.0, len(activity.unique_item_keys) / settings.full_confidence_items
    )
    evidence_quality = (
        0.25 * activity_depth
        + 0.20 * unique_depth
        + 0.20 * activity.recency_score
        + 0.15 * model_recency
        + 0.20 * coverage
    )
    membership_multiplier = (
        1.0 if user_in_model else settings.temporary_factor_multiplier
    )
    score = min(1.0, max(0.0, tier_ceiling * evidence_quality * membership_multiplier))
    return CollaborativeConfidence(score, evidence)


def valid_factor(factor: Sequence[float] | Any) -> bool:
    try:
        values = [float(value) for value in factor]
    except (TypeError, ValueError):
        return False
    return bool(
        values
        and all(math.isfinite(value) for value in values)
        and math.sqrt(sum(value * value for value in values)) > 1e-12
    )


def _tier(
    overlap: int, settings: CollaborativeInferenceSettings
) -> tuple[str, float]:
    if overlap < settings.minimum_overlap_items:
        return "inactive", 0.0
    if overlap < settings.moderate_overlap_items:
        return "low", settings.low_confidence_ceiling
    if overlap < settings.full_confidence_items:
        return "moderate", settings.moderate_confidence_ceiling
    return "normal", 1.0


def _model_recency(
    trained_at: Any, now: datetime, decay_factor: float
) -> tuple[float | None, float]:
    try:
        parsed = (
            trained_at
            if isinstance(trained_at, datetime)
            else datetime.fromisoformat(str(trained_at).replace("Z", "+00:00"))
        )
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None, 0.0
    reference = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (reference - parsed).total_seconds() / 86_400)
    return age_days, decay_factor**age_days


def _signature(interaction: dict[str, Any]) -> tuple[Any, ...] | None:
    created_at = interaction.get("createdAt")
    media_type = interaction.get("mediaType")
    media_id = str(interaction.get("mediaId") or "").strip()
    if media_type not in {"movie", "tv"} or not media_id or not isinstance(created_at, datetime):
        return None
    return (
        media_type,
        media_id,
        interaction.get("eventType"),
        interaction.get("value"),
        created_at.isoformat(),
        interaction.get("sessionId"),
        interaction.get("recommendationId"),
    )


def _latest_state(interactions: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    repeated: list[dict[str, Any]] = []
    latest: dict[tuple[str, str], dict[str, Any]] = {}
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
        key = (f"{interaction['mediaType']}:{interaction['mediaId']}", family)
        current = latest.get(key)
        if current is None or interaction["createdAt"] >= current["createdAt"]:
            latest[key] = interaction
    return [*repeated, *latest.values()]
