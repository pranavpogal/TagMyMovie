from __future__ import annotations

import pytest

from app.recommendations.candidates import Candidate
from app.recommendations.ranking import HybridRankingResult, rank_candidates
from app.recommendations.strategies import (
    COLD_START_POPULAR,
    COLLABORATIVE_BASED,
    CONTENT_BASED,
    CONTENT_COLLABORATIVE_HYBRID,
    ONBOARDING_PREFERENCES,
    PERSONALIZED_HYBRID,
    SEEDED_HYBRID,
    TMDB_FALLBACK,
    select_recommendation_strategy,
)


def ranked(*sources):
    candidate = Candidate(
        "movie", "1", tuple(sources), {}, {}, {source: 1 for source in sources}
    )
    return rank_candidates([candidate], collaborative_confidence=1)


@pytest.mark.parametrize(
    ("sources", "confidence", "seed", "expected"),
    [
        (("seed_similarity", "content"), 0, "movie:seed", SEEDED_HYBRID),
        (("content", "collaborative"), 0.5, None, CONTENT_COLLABORATIVE_HYBRID),
        (("content", "collaborative"), 0, None, CONTENT_BASED),
        (("collaborative",), 0.5, None, COLLABORATIVE_BASED),
        (("content",), 0, None, CONTENT_BASED),
        (("content", "popularity"), 0, None, PERSONALIZED_HYBRID),
        (("preferences", "popularity"), 0, None, ONBOARDING_PREFERENCES),
        (("popularity",), 0, None, COLD_START_POPULAR),
        ((), 0, None, TMDB_FALLBACK),
    ],
)
def test_strategy_matches_final_evidence(sources, confidence, seed, expected) -> None:
    values = ranked(*sources) if sources else ()
    selection = select_recommendation_strategy(
        values, collaborative_confidence=confidence, seed_item_key=seed
    )
    assert selection.strategy == expected
    assert selection.collaborative_active is (
        confidence > 0 and "collaborative" in sources
    )


def test_seed_label_requires_seed_source_in_the_returned_items() -> None:
    selection = select_recommendation_strategy(
        ranked("content"), collaborative_confidence=0, seed_item_key="movie:seed"
    )
    assert selection.strategy == CONTENT_BASED


def test_public_response_always_identifies_strategy_without_internal_diagnostics() -> None:
    result = HybridRankingResult(
        ranked=ranked("popularity"),
        collaborative_confidence=0,
        ranking_version="hybrid-ranking-v1",
        strategy=COLD_START_POPULAR,
        strategy_version="recommendation-strategy-v1",
    )
    public = result.to_public_dict()
    assert public["strategy"] == COLD_START_POPULAR
    assert public["strategyVersion"] == "recommendation-strategy-v1"
    assert "diversity_diagnostics" not in public
    assert "excluded_reasons" not in public
