from __future__ import annotations

import pytest

from app.config import (
    ConfigurationError,
    CollaborativeDatasetSettings,
    CollaborativeModelSettings,
    EmbeddingSettings,
    FeatureTextSettings,
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
