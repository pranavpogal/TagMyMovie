from __future__ import annotations

from pathlib import Path

import pytest

from app.config import (
    CandidateGenerationSettings,
    ConfigurationError,
    CollaborativeDatasetSettings,
    CollaborativeInferenceSettings,
    CollaborativeModelSettings,
    DiversitySettings,
    EmbeddingSettings,
    ExplanationSettings,
    FeatureTextSettings,
    FeedbackPolicySettings,
    HybridRankingSettings,
    MovieLensSettings,
    ProfileSettings,
    Settings,
    VectorSearchSettings,
)


def test_settings_reuse_existing_environment_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MONGODB_URL", "mongodb://localhost:27017/tagmymovie")
    monkeypatch.setenv("TMDB_BASE_URL", "https://api.themoviedb.org/3/")
    monkeypatch.setenv("TMDB_KEY", "test-key")
    monkeypatch.setenv("CATALOGUE_MOVIE_PAGES", "2")
    monkeypatch.setenv("CATALOGUE_TV_PAGES", "3")

    settings = Settings.from_env()

    assert settings.tmdb_api_key == "test-key"
    assert settings.movie_pages == 2
    assert settings.tv_pages == 3
    assert settings.sync_mode == "incremental"


def test_settings_require_credentials_and_valid_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MONGODB_URL", raising=False)
    monkeypatch.delenv("TMDB_KEY", raising=False)
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    monkeypatch.delenv("TMDB_ACCESS_TOKEN", raising=False)
    with pytest.raises(ConfigurationError):
        Settings.from_env()

    monkeypatch.setenv("MONGODB_URL", "mongodb://localhost:27017/tagmymovie")
    monkeypatch.setenv("TMDB_KEY", "test-key")
    monkeypatch.setenv("CATALOGUE_SYNC_MODE", "invalid")
    with pytest.raises(ConfigurationError):
        Settings.from_env()


def test_feature_text_limits_are_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEATURE_TEXT_CAST_LIMIT", "8")
    monkeypatch.setenv("FEATURE_TEXT_KEYWORD_LIMIT", "12")

    settings = FeatureTextSettings.from_env()

    assert settings.cast_limit == 8
    assert settings.keyword_limit == 12


def test_embedding_settings_have_local_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MONGODB_URL", "mongodb://localhost/tagmymovie")

    settings = EmbeddingSettings.from_env()

    assert settings.model_name == "sentence-transformers/all-MiniLM-L6-v2"
    assert settings.version == "content-embedding-v1"
    assert settings.batch_size == 64
    assert settings.vector_backend == "faiss"


def test_embedding_settings_support_mongodb_and_reject_unknown_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MONGODB_URL", "mongodb://localhost/tagmymovie")
    monkeypatch.setenv("VECTOR_BACKEND", "mongodb")
    assert EmbeddingSettings.from_env().vector_backend == "mongodb"

    monkeypatch.setenv("VECTOR_BACKEND", "unknown")

    with pytest.raises(ConfigurationError):
        EmbeddingSettings.from_env()


def test_vector_search_settings_validate_candidate_overfetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = VectorSearchSettings.from_env()
    assert settings.candidate_limit == 150
    assert settings.num_candidates == 300

    monkeypatch.setenv("CONTENT_CANDIDATE_LIMIT", "20")
    monkeypatch.setenv("VECTOR_NUM_CANDIDATES", "10")
    with pytest.raises(ConfigurationError, match="at least"):
        VectorSearchSettings.from_env()


def test_profile_settings_are_configurable_and_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RECENCY_DECAY_FACTOR", "0.95")
    monkeypatch.setenv("PROFILE_WEAK_POSITIVE_CAP", "1.5")
    settings = ProfileSettings.from_env()
    assert settings.decay_factor == 0.95
    assert settings.weak_positive_cap == 1.5

    monkeypatch.setenv("PROFILE_NEGATIVE_CENTROID_SCALE", "1.1")
    with pytest.raises(ConfigurationError, match="at most one"):
        ProfileSettings.from_env()


def test_collaborative_dataset_settings_validate_confidence_caps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MONGODB_URL", "mongodb://localhost/tagmymovie")
    settings = CollaborativeDatasetSettings.from_env()
    assert settings.minimum_user_items == 2
    assert settings.weak_confidence_cap == 2

    monkeypatch.setenv("CF_WEAK_CONFIDENCE_CAP", "11")
    monkeypatch.setenv("CF_MAX_CONFIDENCE", "10")
    with pytest.raises(ConfigurationError, match="must not exceed"):
        CollaborativeDatasetSettings.from_env()


def test_collaborative_model_settings_use_reproducible_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = CollaborativeModelSettings.from_env()
    assert settings.factors == 64
    assert settings.regularization == 0.05
    assert settings.iterations == 30
    assert settings.alpha == 20
    assert settings.random_seed == 42
    assert settings.evaluation_k == 10
    assert settings.minimum_recall_at_k == 0.01

    monkeypatch.setenv("CF_MIN_RECALL_AT_K", "1.1")
    with pytest.raises(ConfigurationError, match="at most one"):
        CollaborativeModelSettings.from_env()


def test_movielens_modes_are_explicit_and_require_a_local_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert MovieLensSettings.from_env().data_source == "tagmymovie"

    monkeypatch.setenv("CF_DATA_SOURCE", "combined")
    with pytest.raises(ConfigurationError, match="MOVIELENS_DATASET_PATH"):
        MovieLensSettings.from_env()

    monkeypatch.setenv("MOVIELENS_DATASET_PATH", "/tmp/ml-small")
    assert MovieLensSettings.from_env().dataset_path == Path("/tmp/ml-small")


def test_collaborative_inference_overlap_thresholds_are_configurable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = CollaborativeInferenceSettings.from_env()
    assert settings.minimum_overlap_items == 3
    assert settings.moderate_overlap_items == 6
    assert settings.full_confidence_items == 10

    monkeypatch.setenv("CF_MIN_OVERLAP_ITEMS", "5")
    monkeypatch.setenv("CF_FULL_WEIGHT_ITEMS", "4")
    with pytest.raises(ConfigurationError, match="at least"):
        CollaborativeInferenceSettings.from_env()

    monkeypatch.setenv("CF_FULL_WEIGHT_ITEMS", "10")
    monkeypatch.setenv("CF_MODERATE_OVERLAP_ITEMS", "4")
    with pytest.raises(ConfigurationError, match="ordered"):
        CollaborativeInferenceSettings.from_env()

    monkeypatch.setenv("CF_MIN_OVERLAP_ITEMS", "3")
    monkeypatch.setenv("CF_MODERATE_OVERLAP_ITEMS", "6")
    monkeypatch.setenv("CF_LOW_CONFIDENCE_CEILING", "0.8")
    monkeypatch.setenv("CF_MODERATE_CONFIDENCE_CEILING", "0.7")
    with pytest.raises(ConfigurationError, match="ceilings"):
        CollaborativeInferenceSettings.from_env()


def test_candidate_pool_defaults_and_vector_overfetch_are_configurable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = CandidateGenerationSettings.from_env()
    assert (
        settings.content_limit,
        settings.collaborative_limit,
        settings.popularity_limit,
        settings.preference_limit,
    ) == (150, 150, 40, 40)

    monkeypatch.setenv("SEED_SIMILARITY_CANDIDATE_LIMIT", "400")
    with pytest.raises(ConfigurationError, match="cover"):
        CandidateGenerationSettings.from_env()

    monkeypatch.setenv("SEED_SIMILARITY_CANDIDATE_LIMIT", "150")
    monkeypatch.setenv("POPULARITY_MINIMUM_VOTE_AVERAGE", "11")
    with pytest.raises(ConfigurationError, match="at most ten"):
        CandidateGenerationSettings.from_env()


def test_hybrid_ranking_configuration_is_versioned_and_validated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = HybridRankingSettings.from_env()
    assert settings.version == "hybrid-ranking-v1"
    assert settings.maximum_collaborative_weight == 0.4

    monkeypatch.setenv("RANKING_VERSION", "")
    with pytest.raises(ConfigurationError, match="RANKING_VERSION"):
        HybridRankingSettings.from_env()

    with pytest.raises(ConfigurationError, match="sum to one"):
        HybridRankingSettings(new_user_content_weight=0.9).validate()


def test_feedback_policy_configuration_is_versioned_and_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = FeedbackPolicySettings.from_env()
    assert settings.version == "feedback-policy-v1"
    assert settings.repeated_attribute_threshold == 2

    monkeypatch.setenv("FEEDBACK_MAX_GENRE_PENALTY", "1.1")
    with pytest.raises(ConfigurationError, match="feedback penalties"):
        FeedbackPolicySettings.from_env()


def test_diversity_configuration_preserves_a_unit_weight_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = DiversitySettings.from_env()
    assert settings.version == "diversity-mmr-v1"
    assert settings.output_limit == 20

    monkeypatch.setenv("DIVERSITY_WEIGHT", "0.4")
    with pytest.raises(ConfigurationError, match="sum to one"):
        DiversitySettings.from_env()


def test_explanation_configuration_limits_public_reason_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = ExplanationSettings.from_env()
    assert settings.version == "recommendation-explanations-v1"
    assert settings.maximum_reasons == 3

    monkeypatch.setenv("EXPLANATION_MAX_REASONS", "4")
    with pytest.raises(ConfigurationError, match="at most three"):
        ExplanationSettings.from_env()
