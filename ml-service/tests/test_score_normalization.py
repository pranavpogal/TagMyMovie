from __future__ import annotations

from app.recommendations.candidates import Candidate
from app.recommendations.normalization import (
    normalize_candidate_scores,
    tied_rank_percentiles,
)


def candidate(item_id: str, **scores: float) -> Candidate:
    return Candidate("movie", item_id, tuple(scores), scores)


def test_tied_rank_percentiles_are_bounded_and_higher_is_better() -> None:
    assert tied_rank_percentiles([("a", 20), ("b", 10), ("c", -100)]) == {
        "a": 1.0,
        "b": 0.5,
        "c": 0.0,
    }


def test_ties_receive_average_rank_and_equal_pool_is_neutral() -> None:
    assert tied_rank_percentiles([("a", 10), ("b", 10), ("c", 0)]) == {
        "a": 0.75,
        "b": 0.75,
        "c": 0.0,
    }
    assert tied_rank_percentiles([("a", 4), ("b", 4)]) == {
        "a": 0.5,
        "b": 0.5,
    }


def test_one_candidate_and_empty_output_have_explicit_results() -> None:
    assert tied_rank_percentiles([("only", -1e300)]) == {"only": 1.0}
    assert tied_rank_percentiles([]) == {}
    assert normalize_candidate_scores([]) == ()


def test_sources_are_normalized_independently_and_missing_scores_stay_missing() -> None:
    normalized = normalize_candidate_scores(
        [
            candidate("a", content=0.2, collaborative=-1e300),
            candidate("b", content=0.9),
            candidate("c", content=0.5, collaborative=1e300),
        ]
    )
    by_key = {item.item_key: item for item in normalized}

    assert by_key["movie:b"].normalized_scores == {"content": 1.0}
    assert by_key["movie:c"].normalized_scores == {
        "collaborative": 1.0,
        "content": 0.5,
    }
    assert by_key["movie:a"].normalized_scores == {
        "collaborative": 0.0,
        "content": 0.0,
    }
    assert "collaborative" not in by_key["movie:b"].normalized_scores


def test_non_finite_or_non_numeric_values_are_ignored_without_changing_raw_data() -> None:
    invalid = Candidate(
        "movie",
        "bad",
        ("collaborative",),
        {"collaborative": float("inf"), "content": "bad"},
    )
    normalized = normalize_candidate_scores([invalid])[0]

    assert normalized.normalized_scores == {}
    assert normalized.raw_scores["collaborative"] == float("inf")


def test_normalization_is_deterministic_when_input_order_changes() -> None:
    first = [candidate("b", content=2), candidate("a", content=2), candidate("c", content=1)]
    second = list(reversed(first))

    first_scores = {
        item.item_key: item.normalized_scores for item in normalize_candidate_scores(first)
    }
    second_scores = {
        item.item_key: item.normalized_scores for item in normalize_candidate_scores(second)
    }
    assert first_scores == second_scores
