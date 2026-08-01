from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


WEIGHT_VERSION = "interaction-weights-v1"

POSITIVE_EVENT_WEIGHTS: dict[str, float] = {
    "detail_view": 0.20,
    "search_click": 0.50,
    "recommendation_click": 0.75,
    "trailer_play": 1.00,
    "review_create": 0.50,
    "favourite_add": 4.00,
    "onboarding_favourite": 4.00,
}

NEGATIVE_EVENT_WEIGHTS: dict[str, float] = {
    "favourite_remove": -1.50,
    "not_interested": -4.00,
}

WEAK_POSITIVE_EVENTS = frozenset(
    {"detail_view", "search_click", "recommendation_click", "trailer_play"}
)


@dataclass(frozen=True)
class WeightedSignal:
    media_key: str
    weight: float
    event_type: str
    is_weak_positive: bool


def rating_weight(value: Any) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return 0.0
    rating = float(value)
    if rating < 1 or rating > 10:
        return 0.0
    if rating <= 3:
        return -3.0
    if rating <= 5:
        return -1.0
    if rating >= 9:
        return 3.0
    if rating >= 7:
        return 2.0
    return 0.0


def base_interaction_weight(event_type: str, value: Any = None) -> float:
    if event_type == "rating_submit":
        return rating_weight(value)
    return POSITIVE_EVENT_WEIGHTS.get(
        event_type, NEGATIVE_EVENT_WEIGHTS.get(event_type, 0.0)
    )


def recency_multiplier(
    created_at: datetime,
    *,
    now: datetime,
    decay_factor: float,
) -> float:
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    days_since_event = max(0.0, (now - created_at).total_seconds() / 86_400)
    return decay_factor**days_since_event


def weighted_signal(
    interaction: dict[str, Any],
    *,
    now: datetime,
    decay_factor: float,
) -> WeightedSignal | None:
    media_type = interaction.get("mediaType")
    media_id = str(interaction.get("mediaId") or "").strip()
    event_type = str(interaction.get("eventType") or "")
    created_at = interaction.get("createdAt")
    if (
        media_type not in {"movie", "tv"}
        or not media_id
        or not isinstance(created_at, datetime)
    ):
        return None
    base_weight = base_interaction_weight(event_type, interaction.get("value"))
    if base_weight == 0:
        return None
    return WeightedSignal(
        media_key=f"{media_type}:{media_id}",
        weight=base_weight
        * recency_multiplier(
            created_at, now=now, decay_factor=decay_factor
        ),
        event_type=event_type,
        is_weak_positive=event_type in WEAK_POSITIVE_EVENTS,
    )
