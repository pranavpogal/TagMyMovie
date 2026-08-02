from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.config import HybridRankingSettings
from app.recommendations.candidates import Candidate
from app.recommendations.ranking import (
    HybridRankingService,
    RankingContext,
    dynamic_weights,
    rank_candidates,
)


NOW = datetime(2026, 8, 2, tzinfo=timezone.utc)


def candidate(
    item_id: str,
    *,
    normalized=None,
    metadata=None,
) -> Candidate:
    normalized = normalized or {}
    return Candidate(
        "movie",
        item_id,
        tuple(normalized),
        raw_scores={},
        metadata=metadata or {},
        normalized_scores=normalized,
    )


def test_dynamic_weights_cover_new_limited_and_established_history() -> None:
    settings = HybridRankingSettings()
    new = dynamic_weights(0, settings)
    limited = dynamic_weights(0.5, settings)
    established = dynamic_weights(1, settings)

    assert new.__dict__ == pytest.approx({
        "content": 0.45, "collaborative": 0, "preferences": 0.30,
        "quality_popularity": 0.25,
    })
    assert limited.__dict__ == pytest.approx({
        "content": 0.375, "collaborative": 0.20, "preferences": 0.225,
        "quality_popularity": 0.20,
    })
    assert established.__dict__ == pytest.approx({
        "content": 0.30, "collaborative": 0.40, "preferences": 0.15,
        "quality_popularity": 0.15,
    })
    assert sum(established.__dict__.values()) == pytest.approx(1)


def test_all_required_features_are_normalized_and_debuggable() -> None:
    item = candidate(
        "1",
        normalized={
            "content": 0.8,
            "collaborative": 0.6,
            "popularity": 0.7,
            "seed_similarity": 0.9,
        },
        metadata={
            "genreIds": [18, 35],
            "originalLanguage": "en",
            "releaseYear": 2024,
            "voteAverage": 8,
            "voteCount": 500,
        },
    )
    context = RankingContext(
        preferred_genre_ids=frozenset({18, 28}),
        preferred_languages=frozenset({"en"}),
        preferred_release_periods=((2020, None),),
    )

    ranked = rank_candidates(
        [item], collaborative_confidence=0.5, context=context, now=NOW
    )[0]
    features = ranked.debug.features

    assert features.content_similarity == 0.8
    assert features.collaborative_score == 0.6
    assert features.collaborative_confidence == 0.5
    assert features.genre_preference_score == 0.5
    assert features.language_preference_score == 1
    assert features.release_period_preference_score == 1
    assert features.quality_score == 0.8
    assert features.popularity_score == 0.7
    assert 0 < features.recency_or_freshness_score <= 1
    assert features.seed_similarity_score == 0.9
    assert features.negative_penalty == 0
    assert features.seen_penalty == 0
    assert 0 <= ranked.score <= 1
    assert ranked.ranking_version == "hybrid-ranking-v1"


def test_collaborative_score_has_no_effect_when_confidence_is_zero() -> None:
    weak = candidate("weak", normalized={"collaborative": 0})
    strong = candidate("strong", normalized={"collaborative": 1})

    ranked = rank_candidates([strong, weak], collaborative_confidence=0, now=NOW)

    assert ranked[0].score == ranked[1].score == 0
    assert [item.candidate.item_key for item in ranked] == ["movie:strong", "movie:weak"]


def test_seed_only_candidate_uses_the_content_weight() -> None:
    ranked = rank_candidates(
        [candidate("seed", normalized={"seed_similarity": 1})],
        collaborative_confidence=0,
        now=NOW,
    )[0]

    assert ranked.debug.content_component == 1
    assert ranked.score == pytest.approx(0.45)


def test_penalties_are_bounded_and_ties_use_compound_key_order() -> None:
    context = RankingContext(
        negative_penalties={"movie:b": 99},
        seen_penalties={"movie:b": 99},
    )
    ranked = rank_candidates(
        [
            candidate("b", normalized={"content": 1}),
            candidate("a", normalized={"content": 0}),
            candidate("c", normalized={"content": 0}),
        ],
        collaborative_confidence=0,
        context=context,
        now=NOW,
    )

    penalized = next(item for item in ranked if item.candidate.item_key == "movie:b")
    assert penalized.debug.features.negative_penalty == 0.25
    assert penalized.debug.features.seen_penalty == 0.15
    tied = [item.candidate.item_key for item in ranked if item.score == 0]
    assert tied == ["movie:a", "movie:c"]


def test_public_output_hides_internal_debug_features() -> None:
    ranked = rank_candidates(
        [candidate("1", normalized={"content": 1})],
        collaborative_confidence=0,
        now=NOW,
    )[0]

    assert "debug" not in ranked.to_public_dict()
    assert "debug" in ranked.to_debug_dict()
    assert ranked.to_public_dict()["rankingVersion"] == "hybrid-ranking-v1"


def test_empty_candidates_return_empty_ranking() -> None:
    assert rank_candidates([], collaborative_confidence=1, now=NOW) == ()


def test_hybrid_service_connects_candidate_generation_and_preference_context() -> None:
    class Generated:
        merged = (candidate("1", normalized={"content": 1}),)
        collaborative_confidence = 0.25

    class CandidateService:
        def generate(self, user_id, seed_item_key=None, now=None):
            assert (user_id, seed_item_key, now) == ("user", "movie:seed", NOW)
            return Generated()

    class ContextRepository:
        def ranking_context(self, user_id):
            assert user_id == "user"
            return RankingContext()

    service = HybridRankingService(
        candidate_service=CandidateService(),
        context_repository=ContextRepository(),
        settings=HybridRankingSettings(),
    )

    result = service.recommend("user", seed_item_key="movie:seed", now=NOW)

    assert len(result.ranked) == 1
    assert result.collaborative_confidence == 0.25
    assert result.ranking_version == "hybrid-ranking-v1"
