from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from app.config import HybridRankingSettings
from app.recommendations.candidates import (
    Candidate,
    SOURCE_COLLABORATIVE,
    SOURCE_CONTENT,
    SOURCE_POPULARITY,
    SOURCE_SEED_SIMILARITY,
)


@dataclass(frozen=True)
class RankingContext:
    preferred_genre_ids: frozenset[int] = frozenset()
    preferred_languages: frozenset[str] = frozenset()
    preferred_release_periods: tuple[tuple[int | None, int | None], ...] = ()
    negative_penalties: Mapping[str, float] | None = None
    seen_penalties: Mapping[str, float] | None = None


@dataclass(frozen=True)
class RankingWeights:
    content: float
    collaborative: float
    preferences: float
    quality_popularity: float


@dataclass(frozen=True)
class RankingFeatures:
    content_similarity: float
    collaborative_score: float
    collaborative_confidence: float
    genre_preference_score: float
    language_preference_score: float
    release_period_preference_score: float
    quality_score: float
    popularity_score: float
    recency_or_freshness_score: float
    seed_similarity_score: float
    negative_penalty: float
    seen_penalty: float


@dataclass(frozen=True)
class RankingDebug:
    features: RankingFeatures
    weights: RankingWeights
    content_component: float
    preference_component: float
    quality_popularity_component: float
    positive_score: float


@dataclass(frozen=True)
class RankedCandidate:
    candidate: Candidate
    score: float
    ranking_version: str
    debug: RankingDebug
    explanations: tuple[str, ...] = ()

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "mediaType": self.candidate.media_type,
            "mediaId": self.candidate.media_id,
            "score": self.score,
            "sourceModels": list(self.candidate.source_models),
            "rankingVersion": self.ranking_version,
            "explanations": list(self.explanations),
        }

    def to_debug_dict(self) -> dict[str, Any]:
        return {**self.to_public_dict(), "debug": asdict(self.debug)}


@dataclass(frozen=True)
class HybridRankingResult:
    ranked: tuple[RankedCandidate, ...]
    collaborative_confidence: float
    ranking_version: str
    feedback_policy_version: str | None = None
    excluded_reasons: Mapping[str, tuple[str, ...]] | None = None
    diversity_version: str | None = None
    diversity_diagnostics: Mapping[str, Any] | None = None
    explanation_version: str | None = None
    strategy: str = "tmdb_fallback"
    strategy_version: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "strategyVersion": self.strategy_version,
            "rankingVersion": self.ranking_version,
            "items": [item.to_public_dict() for item in self.ranked],
        }


class HybridRankingService:
    def __init__(
        self,
        *,
        candidate_service: Any,
        context_repository: Any,
        settings: HybridRankingSettings,
        feedback_service: Any | None = None,
        diversity_service: Any | None = None,
        explanation_service: Any | None = None,
        strategy_settings: Any | None = None,
    ) -> None:
        settings.validate()
        self.candidate_service = candidate_service
        self.context_repository = context_repository
        self.settings = settings
        self.feedback_service = feedback_service
        self.diversity_service = diversity_service
        self.explanation_service = explanation_service
        self.strategy_settings = strategy_settings

    def recommend(
        self,
        user_id: str,
        *,
        seed_item_key: str | None = None,
        now: datetime | None = None,
    ) -> HybridRankingResult:
        generated = self.candidate_service.generate(
            user_id, seed_item_key=seed_item_key, now=now
        )
        context = self.context_repository.ranking_context(user_id)
        candidates = generated.merged
        feedback_version = None
        excluded_reasons = None
        if self.feedback_service is not None:
            feedback = self.feedback_service.apply(
                user_id, candidates, seed_item_key=seed_item_key, now=now
            )
            candidates = feedback.candidates
            feedback_version = feedback.policy_version
            excluded_reasons = feedback.excluded_reasons
            context = replace(
                context,
                negative_penalties=feedback.negative_penalties,
                seen_penalties=feedback.seen_penalties,
            )
        ranked = rank_candidates(
            candidates,
            collaborative_confidence=generated.collaborative_confidence,
            context=context,
            settings=self.settings,
            now=now,
        )
        diversity_version = None
        diversity_diagnostics = None
        if self.diversity_service is not None:
            diversity = self.diversity_service.rerank(ranked)
            ranked = diversity.ranked
            diversity_version = diversity.version
            diversity_diagnostics = diversity.diagnostics
        explanation_version = None
        if self.explanation_service is not None:
            seed_title = self.context_repository.seed_title(seed_item_key) if seed_item_key else None
            explained = self.explanation_service.explain(
                ranked, context=context, seed_title=seed_title
            )
            ranked = explained.ranked
            explanation_version = explained.version
        from app.recommendations.strategies import select_recommendation_strategy

        selection = select_recommendation_strategy(
            ranked,
            collaborative_confidence=generated.collaborative_confidence,
            seed_item_key=seed_item_key,
            settings=self.strategy_settings,
        )
        return HybridRankingResult(
            ranked=ranked,
            collaborative_confidence=generated.collaborative_confidence,
            ranking_version=self.settings.version,
            feedback_policy_version=feedback_version,
            excluded_reasons=excluded_reasons,
            diversity_version=diversity_version,
            diversity_diagnostics=diversity_diagnostics,
            explanation_version=explanation_version,
            strategy=selection.strategy,
            strategy_version=selection.version,
        )


def rank_candidates(
    candidates: Iterable[Candidate],
    *,
    collaborative_confidence: float,
    context: RankingContext | None = None,
    settings: HybridRankingSettings | None = None,
    now: datetime | None = None,
) -> tuple[RankedCandidate, ...]:
    settings = settings or HybridRankingSettings()
    settings.validate()
    context = context or RankingContext()
    reference = now or datetime.now(timezone.utc)
    confidence = _unit(collaborative_confidence)
    weights = dynamic_weights(confidence, settings)
    ranked = [
        _rank(candidate, confidence, weights, context, settings, reference)
        for candidate in candidates
    ]
    return tuple(sorted(ranked, key=lambda item: (-item.score, item.candidate.item_key)))


def dynamic_weights(
    collaborative_confidence: float, settings: HybridRankingSettings
) -> RankingWeights:
    confidence = _unit(collaborative_confidence)
    return RankingWeights(
        content=_interpolate(
            settings.new_user_content_weight,
            settings.established_content_weight,
            confidence,
        ),
        collaborative=settings.maximum_collaborative_weight * confidence,
        preferences=_interpolate(
            settings.new_user_preference_weight,
            settings.established_preference_weight,
            confidence,
        ),
        quality_popularity=_interpolate(
            settings.new_user_quality_weight,
            settings.established_quality_weight,
            confidence,
        ),
    )


def _rank(
    candidate: Candidate,
    confidence: float,
    weights: RankingWeights,
    context: RankingContext,
    settings: HybridRankingSettings,
    now: datetime,
) -> RankedCandidate:
    features = _features(candidate, confidence, context, settings, now)
    seed_available = SOURCE_SEED_SIMILARITY in candidate.normalized_scores
    content_available = SOURCE_CONTENT in candidate.normalized_scores
    seed_share = (
        settings.seed_share_of_content
        if seed_available and content_available
        else 1.0
        if seed_available
        else 0.0
    )
    content_component = (
        (1 - seed_share) * features.content_similarity
        + seed_share * features.seed_similarity_score
    )
    preference_values = [
        value
        for enabled, value in (
            (bool(context.preferred_genre_ids), features.genre_preference_score),
            (bool(context.preferred_languages), features.language_preference_score),
            (bool(context.preferred_release_periods), features.release_period_preference_score),
        )
        if enabled
    ]
    preference_component = (
        sum(preference_values) / len(preference_values) if preference_values else 0.0
    )
    quality_component = (
        settings.quality_vote_share * features.quality_score
        + settings.quality_popularity_share * features.popularity_score
        + settings.quality_freshness_share * features.recency_or_freshness_score
    )
    positive = (
        weights.content * content_component
        + weights.collaborative * features.collaborative_score
        + weights.preferences * preference_component
        + weights.quality_popularity * quality_component
    )
    score = _unit(positive - features.negative_penalty - features.seen_penalty)
    return RankedCandidate(
        candidate,
        score,
        settings.version,
        RankingDebug(
            features,
            weights,
            content_component,
            preference_component,
            quality_component,
            positive,
        ),
    )


def _features(
    candidate: Candidate,
    confidence: float,
    context: RankingContext,
    settings: HybridRankingSettings,
    now: datetime,
) -> RankingFeatures:
    metadata = candidate.metadata
    genre_ids = {int(value) for value in metadata.get("genreIds") or [] if _integer(value)}
    language = str(metadata.get("originalLanguage") or "").lower()
    release_year = _year(metadata.get("releaseYear"))
    vote_average = _unit(_number(metadata.get("voteAverage")) / 10)
    vote_count = max(0.0, _number(metadata.get("voteCount")))
    vote_confidence = min(1.0, vote_count / settings.quality_vote_confidence_count)
    negative = _penalty(context.negative_penalties, candidate.item_key)
    seen = _penalty(context.seen_penalties, candidate.item_key)
    return RankingFeatures(
        content_similarity=_normalized(candidate, SOURCE_CONTENT),
        collaborative_score=_normalized(candidate, SOURCE_COLLABORATIVE),
        collaborative_confidence=confidence,
        genre_preference_score=_overlap_score(genre_ids, context.preferred_genre_ids),
        language_preference_score=(
            1.0 if context.preferred_languages and language in context.preferred_languages else 0.0
        ),
        release_period_preference_score=_release_score(
            release_year, context.preferred_release_periods
        ),
        quality_score=vote_average * vote_confidence,
        popularity_score=_normalized(candidate, SOURCE_POPULARITY),
        recency_or_freshness_score=_freshness(
            release_year, now, settings.freshness_half_life_years
        ),
        seed_similarity_score=_normalized(candidate, SOURCE_SEED_SIMILARITY),
        negative_penalty=settings.maximum_negative_penalty * negative,
        seen_penalty=settings.maximum_seen_penalty * seen,
    )


def _normalized(candidate: Candidate, source: str) -> float:
    return _unit(candidate.normalized_scores.get(source, 0.0))


def _overlap_score(values: set[int], preferences: frozenset[int]) -> float:
    if not preferences:
        return 0.0
    return len(values.intersection(preferences)) / len(preferences)


def _release_score(
    year: int | None, periods: tuple[tuple[int | None, int | None], ...]
) -> float:
    if year is None or not periods:
        return 0.0
    return float(any(
        (minimum is None or year >= minimum) and (maximum is None or year <= maximum)
        for minimum, maximum in periods
    ))


def _freshness(year: int | None, now: datetime, half_life: float) -> float:
    if year is None:
        return 0.0
    return 0.5 ** (max(0, now.year - year) / half_life)


def _penalty(values: Mapping[str, float] | None, item_key: str) -> float:
    return _unit((values or {}).get(item_key, 0.0))


def _unit(value: Any) -> float:
    numeric = _number(value)
    return min(1.0, max(0.0, numeric))


def _number(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return numeric if math.isfinite(numeric) else 0.0


def _integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _year(value: Any) -> int | None:
    return value if isinstance(value, int) and 1800 <= value <= 3000 else None


def _interpolate(start: float, end: float, confidence: float) -> float:
    return start + (end - start) * confidence
