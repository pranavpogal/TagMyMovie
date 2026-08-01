from __future__ import annotations

from dataclasses import dataclass

from app.config import CandidateGenerationSettings
from app.content.vector_store import VectorSearchResult
from app.recommendations.candidates import CandidateGenerationService


@dataclass
class Profile:
    is_cold_start: bool
    vector: tuple[float, ...] = (1.0, 0.0)


class ProfileBuilder:
    def __init__(self, cold=False) -> None:
        self.cold = cold

    def build(self, user_id, now=None):
        return Profile(self.cold)


class VectorStore:
    def __init__(self) -> None:
        self.calls = []

    def search(self, vector, filters=None, limit=150, num_candidates=300):
        self.calls.append((tuple(vector), limit, num_candidates))
        if tuple(vector) == (0.0, 1.0):
            return [
                VectorSearchResult("seed", "movie", 1.0),
                VectorSearchResult("shared", "movie", 0.8),
                VectorSearchResult("similar", "tv", 0.7),
            ]
        return [
            VectorSearchResult("shared", "movie", 0.9),
            VectorSearchResult("content", "tv", 0.7),
        ]


class CollaborativeResult:
    candidates = ()
    collaborative_confidence = 0.4
    fallback_reason = None


class CollaborativeService:
    def recommend(self, user_id, limit, now=None):
        from app.collaborative.inference import CollaborativeCandidate

        result = CollaborativeResult()
        result.candidates = (
            CollaborativeCandidate("movie", "shared", 4.2),
            CollaborativeCandidate("tv", "collaborative", -1.2),
        )
        return result


class Repository:
    def popularity_candidates(self, **kwargs):
        return [
            {"mediaType": "movie", "tmdbId": "popular", "popularity": 100},
            {"mediaType": "movie", "tmdbId": "shared", "popularity": 90},
        ]

    def preference_candidates(self, user_id, limit):
        return [
            {"mediaType": "tv", "tmdbId": "preferred", "popularity": 70}
        ]

    def item_embedding(self, item_key):
        return [0.0, 1.0] if item_key == "movie:seed" else None


def test_generates_independent_pools_and_merges_compound_keys_with_provenance() -> None:
    vector_store = VectorStore()
    service = CandidateGenerationService(
        profile_builder=ProfileBuilder(),
        vector_store=vector_store,
        collaborative_service=CollaborativeService(),
        repository=Repository(),
        settings=CandidateGenerationSettings(),
    )

    result = service.generate("user", seed_item_key="movie:seed")

    assert len(result.content) == 2
    assert len(result.collaborative) == 2
    assert len(result.popularity) == 2
    assert len(result.preferences) == 1
    assert [item.item_key for item in result.seed_similarity] == [
        "movie:shared", "tv:similar"
    ]
    assert len(result.merged) == 6
    shared = next(item for item in result.merged if item.item_key == "movie:shared")
    assert shared.source_models == (
        "content", "collaborative", "popularity", "seed_similarity"
    )
    assert shared.raw_scores == {
        "content": 0.9,
        "collaborative": 4.2,
        "popularity": 90.0,
        "seed_similarity": 0.8,
    }
    assert set(shared.normalized_scores) == set(shared.source_models)
    assert result.normalization_version == "tied-rank-percentile-v1"
    assert result.collaborative_confidence == 0.4
    assert vector_store.calls == [((1.0, 0.0), 150, 300), ((0.0, 1.0), 150, 300)]


def test_cold_profile_and_missing_seed_produce_empty_model_pools() -> None:
    vector_store = VectorStore()
    service = CandidateGenerationService(
        profile_builder=ProfileBuilder(cold=True),
        vector_store=vector_store,
        collaborative_service=CollaborativeService(),
        repository=Repository(),
        settings=CandidateGenerationSettings(),
    )

    result = service.generate("user", seed_item_key="bad")

    assert result.content == ()
    assert result.seed_similarity == ()
    assert vector_store.calls == []
    assert result.popularity
