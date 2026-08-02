from __future__ import annotations

from app.config import ExplanationSettings
from app.recommendations.candidates import Candidate
from app.recommendations.explanations import explain_ranked_candidates
from app.recommendations.ranking import RankingContext, rank_candidates


def ranked(source_scores, metadata=None, confidence=0.7):
    candidate = Candidate(
        "movie", "1", tuple(source_scores), {}, metadata or {}, source_scores
    )
    return rank_candidates(
        [candidate], collaborative_confidence=confidence,
        context=RankingContext(
            preferred_genre_ids=frozenset({878}),
            preferred_languages=frozenset({"kn"}),
        ),
    )[0]


def test_explanations_use_strongest_real_seed_preference_and_activity_signals() -> None:
    item = ranked(
        {"seed_similarity": 0.9, "content": 0.8, "preferences": 1.0},
        {"genres": [{"id": 878, "name": "Science Fiction"}], "genreIds": [878],
         "originalLanguage": "kn"},
    )
    context = RankingContext(
        preferred_genre_ids=frozenset({878}), preferred_languages=frozenset({"kn"})
    )
    result = explain_ranked_candidates([item], context=context, seed_title="Interstellar")
    reasons = result.ranked[0].explanations

    assert len(reasons) == 3
    assert "Similar themes to Interstellar" in reasons
    assert "Matches your Science Fiction preference" in reasons
    assert "Matches your preference for Kannada-language titles" in reasons


def test_collaborative_reason_is_privacy_safe_and_requires_actual_evidence() -> None:
    collaborative = explain_ranked_candidates(
        [ranked({"collaborative": 0.8})], context=RankingContext()
    ).ranked[0]
    content = explain_ranked_candidates(
        [ranked({"content": 0.8}, confidence=0)], context=RankingContext()
    ).ranked[0]

    assert "Popular among users with similar preferences" in collaborative.explanations
    assert all("user " not in reason.lower() for reason in collaborative.explanations)
    assert all("review" not in reason.lower() and "factor" not in reason.lower() for reason in collaborative.explanations)
    assert all("similar preferences" not in reason for reason in content.explanations)


def test_unsupported_preferences_are_never_claimed() -> None:
    item = ranked(
        {"popularity": 0.9},
        {"genreIds": [35], "originalLanguage": "en", "voteAverage": 8, "voteCount": 500},
        confidence=0,
    )
    result = explain_ranked_candidates(
        [item],
        context=RankingContext(
            preferred_genre_ids=frozenset({878}), preferred_languages=frozenset({"kn"})
        ),
    ).ranked[0]
    assert result.explanations == ("Popular and well-rated",)


def test_reason_count_is_one_to_three_and_public_output_contains_no_debug() -> None:
    item = ranked({"content": 1, "collaborative": 1, "popularity": 1})
    explained = explain_ranked_candidates([item], context=RankingContext()).ranked[0]
    assert 1 <= len(explained.explanations) <= 3
    public = explained.to_public_dict()
    assert public["explanations"] == list(explained.explanations)
    assert "debug" not in public


def test_empty_input_and_version_are_deterministic() -> None:
    result = explain_ranked_candidates([], settings=ExplanationSettings())
    assert result.ranked == ()
    assert result.version == "recommendation-explanations-v1"
