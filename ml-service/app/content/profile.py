from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence, TypeGuard

from app.collaborative.interaction_weights import WEIGHT_VERSION, weighted_signal
from app.config import ProfileSettings


@dataclass(frozen=True)
class MediaWeight:
    media_key: str
    positive_weight: float
    negative_weight: float


@dataclass(frozen=True)
class ContentProfile:
    status: str
    vector: tuple[float, ...]
    reason: str | None
    profile_version: str
    weight_version: str
    positive_weight: float
    negative_weight: float
    contributing_media: int

    @property
    def is_cold_start(self) -> bool:
        return self.status == "cold_start"


def aggregate_media_weights(
    interactions: Iterable[dict[str, Any]],
    *,
    settings: ProfileSettings,
    now: datetime,
    onboarding_seed_keys: Iterable[str] = (),
) -> dict[str, MediaWeight]:
    settings.validate()
    grouped: dict[str, dict[str, float]] = {}
    observed_onboarding: set[str] = set()
    for interaction in _effective_interactions(interactions):
        signal = weighted_signal(
            interaction, now=now, decay_factor=settings.decay_factor
        )
        if signal is None:
            continue
        weights = grouped.setdefault(
            signal.media_key, {"strong": 0.0, "weak": 0.0, "negative": 0.0}
        )
        if signal.event_type == "onboarding_favourite":
            observed_onboarding.add(signal.media_key)
        if signal.weight < 0:
            weights["negative"] += abs(signal.weight)
        elif signal.is_weak_positive:
            weights["weak"] += signal.weight
        else:
            weights["strong"] += signal.weight

    for media_key in set(onboarding_seed_keys) - observed_onboarding:
        if not _valid_media_key(media_key):
            continue
        weights = grouped.setdefault(
            media_key, {"strong": 0.0, "weak": 0.0, "negative": 0.0}
        )
        weights["strong"] += 4.0

    return {
        media_key: MediaWeight(
            media_key=media_key,
            positive_weight=values["strong"]
            + min(values["weak"], settings.weak_positive_cap),
            negative_weight=values["negative"],
        )
        for media_key, values in grouped.items()
    }


def build_content_profile(
    interactions: Iterable[dict[str, Any]],
    embeddings: Mapping[str, Sequence[float]],
    *,
    settings: ProfileSettings | None = None,
    now: datetime | None = None,
    onboarding_seed_keys: Iterable[str] = (),
) -> ContentProfile:
    settings = settings or ProfileSettings(
        version="user-profile-v1",
        decay_factor=0.98,
        weak_positive_cap=2.0,
        negative_centroid_scale=0.35,
    )
    settings.validate()
    weights = aggregate_media_weights(
        interactions,
        settings=settings,
        now=now or datetime.now(timezone.utc),
        onboarding_seed_keys=onboarding_seed_keys,
    )
    positive_vectors: list[tuple[Sequence[float], float]] = []
    negative_vectors: list[tuple[Sequence[float], float]] = []
    dimension: int | None = None
    contributing_keys: set[str] = set()
    for media_key, media_weight in weights.items():
        vector = embeddings.get(media_key)
        if not _valid_vector(vector, dimension):
            continue
        dimension = dimension or len(vector)
        if media_weight.positive_weight > 0:
            positive_vectors.append((vector, media_weight.positive_weight))
            contributing_keys.add(media_key)
        if media_weight.negative_weight > 0:
            negative_vectors.append((vector, media_weight.negative_weight))
            contributing_keys.add(media_key)

    if not positive_vectors or dimension is None:
        return _cold_start(
            settings,
            "no_positive_profile_evidence",
            negative_weight=sum(weight for _, weight in negative_vectors),
            contributing_media=len(contributing_keys),
        )

    positive_centroid, positive_total = _weighted_centroid(
        positive_vectors, dimension
    )
    negative_total = sum(weight for _, weight in negative_vectors)
    raw_profile = positive_centroid
    if negative_vectors:
        negative_centroid, _ = _weighted_centroid(negative_vectors, dimension)
        subtraction = settings.negative_centroid_scale * min(
            1.0, negative_total / positive_total
        )
        raw_profile = [
            positive - subtraction * negative
            for positive, negative in zip(positive_centroid, negative_centroid)
        ]

    normalized = _normalize(raw_profile)
    if normalized is None:
        return _cold_start(settings, "degenerate_profile_vector")
    return ContentProfile(
        status="ready",
        vector=tuple(normalized),
        reason=None,
        profile_version=settings.version,
        weight_version=WEIGHT_VERSION,
        positive_weight=positive_total,
        negative_weight=negative_total,
        contributing_media=len(contributing_keys),
    )


def _weighted_centroid(
    vectors: list[tuple[Sequence[float], float]], dimension: int
) -> tuple[list[float], float]:
    total = sum(weight for _, weight in vectors)
    centroid = [0.0] * dimension
    for vector, weight in vectors:
        for index, value in enumerate(vector):
            centroid[index] += float(value) * weight
    return [value / total for value in centroid], total


def _normalize(vector: Sequence[float]) -> list[float] | None:
    if any(not math.isfinite(value) for value in vector):
        return None
    norm = math.sqrt(sum(value * value for value in vector))
    if not math.isfinite(norm) or norm <= 1e-12:
        return None
    return [value / norm for value in vector]


def _valid_vector(
    vector: Sequence[float] | None, dimension: int | None
) -> TypeGuard[Sequence[float]]:
    if vector is None or len(vector) == 0:
        return False
    return (dimension is None or len(vector) == dimension) and all(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        for value in vector
    )


def _valid_media_key(media_key: str) -> bool:
    media_type, separator, media_id = media_key.partition(":")
    return separator == ":" and media_type in {"movie", "tv"} and bool(media_id)


def _effective_interactions(
    interactions: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    repeated: list[dict[str, Any]] = []
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for interaction in interactions:
        event_type = interaction.get("eventType")
        media_type = interaction.get("mediaType")
        media_id = str(interaction.get("mediaId") or "").strip()
        if event_type == "rating_submit":
            family = "rating"
        elif event_type in {"favourite_add", "favourite_remove"}:
            family = "favourite"
        elif event_type == "not_interested":
            family = "not_interested"
        else:
            repeated.append(interaction)
            continue
        key = (f"{media_type}:{media_id}", family)
        current = latest.get(key)
        created_at = interaction.get("createdAt")
        current_created_at = current.get("createdAt") if current else None
        if current is None or (
            isinstance(created_at, datetime)
            and (
                not isinstance(current_created_at, datetime)
                or created_at >= current_created_at
            )
        ):
            latest[key] = interaction
    return [*repeated, *latest.values()]


def _cold_start(
    settings: ProfileSettings,
    reason: str,
    *,
    negative_weight: float = 0.0,
    contributing_media: int = 0,
) -> ContentProfile:
    return ContentProfile(
        status="cold_start",
        vector=(),
        reason=reason,
        profile_version=settings.version,
        weight_version=WEIGHT_VERSION,
        positive_weight=0.0,
        negative_weight=negative_weight,
        contributing_media=contributing_media,
    )
