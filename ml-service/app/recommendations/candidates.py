from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Mapping

from app.config import CandidateGenerationSettings
from app.content.vector_store import VectorSearchResult, VectorStore


SOURCE_CONTENT = "content"
SOURCE_COLLABORATIVE = "collaborative"
SOURCE_POPULARITY = "popularity"
SOURCE_PREFERENCES = "preferences"
SOURCE_SEED_SIMILARITY = "seed_similarity"
SOURCE_ORDER = (
    SOURCE_CONTENT,
    SOURCE_COLLABORATIVE,
    SOURCE_POPULARITY,
    SOURCE_PREFERENCES,
    SOURCE_SEED_SIMILARITY,
)


@dataclass(frozen=True)
class Candidate:
    media_type: str
    media_id: str
    source_models: tuple[str, ...]
    raw_scores: Mapping[str, float] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def item_key(self) -> str:
        return f"{self.media_type}:{self.media_id}"


@dataclass(frozen=True)
class CandidateGenerationResult:
    content: tuple[Candidate, ...]
    collaborative: tuple[Candidate, ...]
    popularity: tuple[Candidate, ...]
    preferences: tuple[Candidate, ...]
    seed_similarity: tuple[Candidate, ...]
    merged: tuple[Candidate, ...]
    collaborative_confidence: float
    collaborative_fallback_reason: str | None


class CandidateGenerationService:
    def __init__(
        self,
        *,
        profile_builder: Any,
        vector_store: VectorStore,
        collaborative_service: Any,
        repository: Any,
        settings: CandidateGenerationSettings,
    ) -> None:
        settings.validate()
        self.profile_builder = profile_builder
        self.vector_store = vector_store
        self.collaborative_service = collaborative_service
        self.repository = repository
        self.settings = settings

    def generate(
        self,
        user_id: str,
        *,
        seed_item_key: str | None = None,
        now: datetime | None = None,
    ) -> CandidateGenerationResult:
        content = self._content_candidates(user_id, now=now)
        collaborative_result = self.collaborative_service.recommend(
            user_id, limit=self.settings.collaborative_limit, now=now
        )
        collaborative = tuple(
            _candidate(
                item.media_type,
                item.media_id,
                SOURCE_COLLABORATIVE,
                item.raw_score,
            )
            for item in collaborative_result.candidates
        )
        popularity = tuple(
            _catalogue_candidate(document, SOURCE_POPULARITY, "popularity")
            for document in self.repository.popularity_candidates(
                limit=self.settings.popularity_limit,
                minimum_vote_count=self.settings.popularity_minimum_vote_count,
                minimum_vote_average=self.settings.popularity_minimum_vote_average,
            )
        )
        preferences = tuple(
            _catalogue_candidate(document, SOURCE_PREFERENCES, "popularity")
            for document in self.repository.preference_candidates(
                user_id, limit=self.settings.preference_limit
            )
        )
        seed_similarity = self._seed_candidates(seed_item_key)
        pools = (content, collaborative, popularity, preferences, seed_similarity)
        return CandidateGenerationResult(
            content=content,
            collaborative=collaborative,
            popularity=popularity,
            preferences=preferences,
            seed_similarity=seed_similarity,
            merged=merge_candidate_pools(*pools),
            collaborative_confidence=collaborative_result.collaborative_confidence,
            collaborative_fallback_reason=collaborative_result.fallback_reason,
        )

    def _content_candidates(
        self, user_id: str, *, now: datetime | None
    ) -> tuple[Candidate, ...]:
        profile = self.profile_builder.build(user_id, now=now)
        if profile.is_cold_start:
            return ()
        results = self.vector_store.search(
            profile.vector,
            limit=self.settings.content_limit,
            num_candidates=self.settings.vector_num_candidates,
        )
        return tuple(_vector_candidate(item, SOURCE_CONTENT) for item in results)

    def _seed_candidates(self, seed_item_key: str | None) -> tuple[Candidate, ...]:
        if seed_item_key is None:
            return ()
        vector = self.repository.item_embedding(seed_item_key)
        if vector is None:
            return ()
        results = self.vector_store.search(
            vector,
            limit=self.settings.seed_similarity_limit,
            num_candidates=self.settings.vector_num_candidates,
        )
        return tuple(
            _vector_candidate(item, SOURCE_SEED_SIMILARITY)
            for item in results
            if item.key != seed_item_key
        )


def merge_candidate_pools(*pools: Iterable[Candidate]) -> tuple[Candidate, ...]:
    merged: dict[str, Candidate] = {}
    for pool in pools:
        for candidate in pool:
            current = merged.get(candidate.item_key)
            if current is None:
                merged[candidate.item_key] = candidate
                continue
            sources = tuple(
                source
                for source in SOURCE_ORDER
                if source in {*current.source_models, *candidate.source_models}
            )
            merged[candidate.item_key] = Candidate(
                media_type=current.media_type,
                media_id=current.media_id,
                source_models=sources,
                raw_scores={**current.raw_scores, **candidate.raw_scores},
                metadata={**current.metadata, **candidate.metadata},
            )
    return tuple(merged.values())


def _candidate(
    media_type: str,
    media_id: str,
    source: str,
    score: Any,
    metadata: Mapping[str, Any] | None = None,
) -> Candidate:
    try:
        numeric_score = float(score or 0)
    except (TypeError, ValueError):
        numeric_score = 0.0
    if not math.isfinite(numeric_score):
        numeric_score = 0.0
    return Candidate(
        media_type=media_type,
        media_id=str(media_id),
        source_models=(source,),
        raw_scores={source: numeric_score},
        metadata=metadata or {},
    )


def _vector_candidate(item: VectorSearchResult, source: str) -> Candidate:
    return _candidate(item.media_type, item.tmdb_id, source, item.score, item.metadata)


def _catalogue_candidate(
    document: Mapping[str, Any], source: str, score_field: str
) -> Candidate:
    metadata = {
        key: value
        for key, value in document.items()
        if key not in {"_id", "mediaType", "tmdbId"}
    }
    return _candidate(
        str(document["mediaType"]),
        str(document["tmdbId"]),
        source,
        document.get(score_field),
        metadata,
    )
