from __future__ import annotations

import pytest

from app.config import ConfigurationError, FeatureTextSettings, Settings


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
