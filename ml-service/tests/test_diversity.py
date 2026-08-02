from __future__ import annotations

from app.config import DiversitySettings, HybridRankingSettings
from app.recommendations.candidates import Candidate
from app.recommendations.diversity import candidate_similarity, diversify_ranked_candidates
from app.recommendations.ranking import RankingContext, rank_candidates


def ranked(item_id, score, **metadata):
    candidate = Candidate("movie", item_id, ("content",), {}, metadata, {"content": score})
    return rank_candidates(
        [candidate], collaborative_confidence=0,
        context=RankingContext(), settings=HybridRankingSettings()
    )[0].__class__(
        candidate, score, "hybrid-ranking-v1",
        rank_candidates([candidate], collaborative_confidence=0)[0].debug,
    )


def test_mmr_promotes_a_relevant_different_item_without_randomization() -> None:
    values = [
        ranked("1", 1.00, title="Saga One", genreIds=[18], directors=["A"], originalLanguage="en"),
        ranked("2", 0.98, title="Saga Two", genreIds=[18], directors=["A"], originalLanguage="en"),
        ranked("3", 0.90, title="Comedy Night", genreIds=[35], directors=["B"], originalLanguage="fr"),
    ]
    result = diversify_ranked_candidates(
        values, settings=DiversitySettings(relevance_weight=0.7, diversity_weight=0.3)
    )
    again = diversify_ranked_candidates(
        values, settings=DiversitySettings(relevance_weight=0.7, diversity_weight=0.3)
    )

    assert [item.candidate.media_id for item in result.ranked] == ["1", "3", "2"]
    assert result.ranked == again.ranked
    assert result.ranked[0].score == 1.0


def test_franchise_cap_prefers_available_alternatives_but_never_empties_output() -> None:
    values = [
        ranked(str(index), 1 - index / 100, franchise="same") for index in range(4)
    ] + [ranked("other", 0.5, franchise="other")]
    result = diversify_ranked_candidates(values, settings=DiversitySettings())
    order = [item.candidate.media_id for item in result.ranked]
    assert order.index("other") < order.index("2")
    assert len(order) == 5


def test_similarity_uses_vector_and_metadata_without_crossing_media_identity() -> None:
    first = ranked("1", 1, genreIds=[18], embedding=[1, 0], popularity=100)
    same = ranked("2", 1, genreIds=[18], embedding=[1, 0], popularity=100)
    different = ranked("3", 1, genreIds=[35], embedding=[0, 1], popularity=1)
    assert candidate_similarity(first, same) > candidate_similarity(first, different)
    assert first.candidate.item_key == "movie:1"


def test_empty_and_tied_inputs_are_deterministic() -> None:
    assert diversify_ranked_candidates([]).ranked == ()
    values = [ranked("b", 0.5), ranked("a", 0.5)]
    result = diversify_ranked_candidates(values)
    assert [item.candidate.media_id for item in result.ranked] == ["a", "b"]
