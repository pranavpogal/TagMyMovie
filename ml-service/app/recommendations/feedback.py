from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

from app.config import FeedbackPolicySettings
from app.recommendations.candidates import Candidate


@dataclass(frozen=True)
class FeedbackInputs:
    interactions: tuple[Mapping[str, Any], ...]
    catalogue_by_key: Mapping[str, Mapping[str, Any]]
    exclude_previously_favourited: bool = True
    exclude_previously_rated: bool = True


@dataclass(frozen=True)
class FeedbackApplication:
    candidates: tuple[Candidate, ...]
    excluded_reasons: Mapping[str, tuple[str, ...]]
    negative_penalties: Mapping[str, float]
    seen_penalties: Mapping[str, float]
    policy_version: str


class FeedbackPolicyService:
    def __init__(self, repository: Any, settings: FeedbackPolicySettings) -> None:
        settings.validate()
        self.repository = repository
        self.settings = settings

    def apply(
        self,
        user_id: str,
        candidates: Iterable[Candidate],
        *,
        seed_item_key: str | None = None,
        now: datetime | None = None,
    ) -> FeedbackApplication:
        return apply_feedback_policy(
            candidates,
            self.repository.feedback_inputs(user_id),
            settings=self.settings,
            seed_item_key=seed_item_key,
            now=now,
        )


def apply_feedback_policy(
    candidates: Iterable[Candidate],
    inputs: FeedbackInputs,
    *,
    settings: FeedbackPolicySettings | None = None,
    seed_item_key: str | None = None,
    now: datetime | None = None,
) -> FeedbackApplication:
    settings = settings or FeedbackPolicySettings()
    settings.validate()
    reference = now or datetime.now(timezone.utc)
    effective = _effective_states(inputs.interactions)
    exclusions: dict[str, set[str]] = {}
    negative: dict[str, float] = {}
    seen: dict[str, float] = {}
    disliked: set[str] = set()
    impressions: Counter[str] = Counter()
    click_cutoff = reference - timedelta(days=settings.recent_click_days)
    impression_cutoff = reference - timedelta(days=settings.impression_window_days)

    if seed_item_key:
        exclusions.setdefault(seed_item_key, set()).add("current_seed")
    for interaction in effective:
        key = _key(interaction)
        created_at = _date(interaction.get("createdAt"))
        event = interaction.get("eventType")
        value = interaction.get("value")
        if not key or created_at is None:
            continue
        if event == "not_interested":
            exclusions.setdefault(key, set()).add("not_interested")
            disliked.add(key)
        elif event == "rating_submit":
            if inputs.exclude_previously_rated:
                exclusions.setdefault(key, set()).add("previously_rated")
            try:
                if float(value) <= 4:
                    exclusions.setdefault(key, set()).add("low_rating")
                    disliked.add(key)
            except (TypeError, ValueError):
                pass
        elif event == "favourite_add" and inputs.exclude_previously_favourited:
            exclusions.setdefault(key, set()).add("existing_favourite")
        elif event == "favourite_remove":
            negative[key] = max(negative.get(key, 0), settings.removed_favourite_penalty)
            disliked.add(key)
        elif event == "recommendation_click" and click_cutoff <= created_at <= reference:
            seen[key] = max(seen.get(key, 0), settings.recent_click_penalty)
        elif event == "recommendation_impression" and impression_cutoff <= created_at <= reference:
            impressions[key] += 1

    for key, count in impressions.items():
        if count >= settings.repeated_impression_threshold:
            seen[key] = max(seen.get(key, 0), settings.repeated_impression_penalty)

    genre_counts: Counter[int] = Counter()
    people_counts: Counter[str] = Counter()
    for key in disliked:
        metadata = inputs.catalogue_by_key.get(key, {})
        genre_counts.update(set(metadata.get("genreIds") or []))
        people_counts.update(_people(metadata))
    retained = []
    for candidate in candidates:
        if candidate.item_key in exclusions:
            continue
        retained.append(candidate)
        genre_matches = sum(
            genre_counts[genre] >= settings.repeated_attribute_threshold
            for genre in set(candidate.metadata.get("genreIds") or [])
        )
        people_matches = sum(
            people_counts[person] >= settings.repeated_attribute_threshold
            for person in _people(candidate.metadata)
        )
        similarity = min(
            1.0,
            settings.maximum_genre_penalty * genre_matches
            + settings.maximum_people_penalty * people_matches,
        )
        if similarity:
            negative[candidate.item_key] = max(
                negative.get(candidate.item_key, 0), similarity
            )
    return FeedbackApplication(
        tuple(retained),
        {key: tuple(sorted(reasons)) for key, reasons in exclusions.items()},
        negative,
        seen,
        settings.version,
    )


def _effective_states(interactions: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    repeated = []
    latest: dict[tuple[str, str], Mapping[str, Any]] = {}
    for item in interactions:
        key = _key(item)
        event = item.get("eventType")
        family = "rating" if event == "rating_submit" else "favourite" if event in {"favourite_add", "favourite_remove"} else None
        if not key or family is None:
            repeated.append(item)
            continue
        current = latest.get((key, family))
        if current is None or (_date(item.get("createdAt")) or datetime.min.replace(tzinfo=timezone.utc)) >= (_date(current.get("createdAt")) or datetime.min.replace(tzinfo=timezone.utc)):
            latest[(key, family)] = item
    return [*repeated, *latest.values()]


def _key(item: Mapping[str, Any]) -> str | None:
    media_type = item.get("mediaType")
    media_id = str(item.get("mediaId") or "").strip()
    return f"{media_type}:{media_id}" if media_type in {"movie", "tv"} and media_id else None


def _date(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _people(metadata: Mapping[str, Any]) -> set[str]:
    return {
        str(value).casefold()
        for field in ("cast", "directors", "creators")
        for value in metadata.get(field) or []
        if str(value).strip()
    }
