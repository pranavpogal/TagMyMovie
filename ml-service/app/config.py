from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class ConfigurationError(ValueError):
    """Raised when required pipeline configuration is missing or invalid."""


@dataclass(frozen=True)
class FeatureTextSettings:
    cast_limit: int
    keyword_limit: int

    @classmethod
    def from_env(cls) -> "FeatureTextSettings":
        return cls(
            cast_limit=_integer("FEATURE_TEXT_CAST_LIMIT", 10, 1),
            keyword_limit=_integer("FEATURE_TEXT_KEYWORD_LIMIT", 20, 1),
        )


@dataclass(frozen=True)
class EmbeddingSettings:
    mongodb_url: str
    mongodb_database: str
    model_name: str
    version: str
    batch_size: int
    cast_limit: int
    keyword_limit: int
    vector_backend: str
    index_name: str
    artifact_directory: Path

    @classmethod
    def from_env(cls) -> "EmbeddingSettings":
        settings = cls(
            mongodb_url=os.getenv("MONGODB_URL", "").strip(),
            mongodb_database=os.getenv("MONGODB_DATABASE", "tagmymovie").strip(),
            model_name=os.getenv(
                "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
            ).strip(),
            version=os.getenv("EMBEDDING_VERSION", "content-embedding-v1").strip(),
            batch_size=_integer("EMBEDDING_BATCH_SIZE", 64, 1),
            cast_limit=_integer("FEATURE_TEXT_CAST_LIMIT", 10, 1),
            keyword_limit=_integer("FEATURE_TEXT_KEYWORD_LIMIT", 20, 1),
            vector_backend=os.getenv("VECTOR_BACKEND", "faiss").strip().lower(),
            index_name=os.getenv("VECTOR_INDEX_NAME", "media_embedding_index").strip(),
            artifact_directory=Path(
                os.getenv("CONTENT_ARTIFACT_DIRECTORY", "artifacts/content")
            ).expanduser(),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not self.mongodb_url:
            raise ConfigurationError("MONGODB_URL is required")
        if not self.mongodb_database:
            raise ConfigurationError("MONGODB_DATABASE is required")
        if not self.model_name:
            raise ConfigurationError("EMBEDDING_MODEL is required")
        if not self.version:
            raise ConfigurationError("EMBEDDING_VERSION is required")
        if self.vector_backend != "faiss":
            raise ConfigurationError("VECTOR_BACKEND must be faiss")
        if not self.index_name or any(character in self.index_name for character in "/\\"):
            raise ConfigurationError("VECTOR_INDEX_NAME must be a safe file name")


def _integer(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name)
    try:
        value = default if raw in (None, "") else int(raw)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be an integer") from error
    if value < minimum:
        raise ConfigurationError(f"{name} must be at least {minimum}")
    return value


def _float(name: str, default: float, minimum: float = 0) -> float:
    raw = os.getenv(name)
    try:
        value = default if raw in (None, "") else float(raw)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be a number") from error
    if value < minimum:
        raise ConfigurationError(f"{name} must be at least {minimum}")
    return value


@dataclass(frozen=True)
class Settings:
    mongodb_url: str
    mongodb_database: str
    tmdb_base_url: str
    tmdb_api_key: str | None
    tmdb_access_token: str | None
    movie_pages: int
    tv_pages: int
    sync_mode: str
    incremental_max_age_hours: int
    request_timeout_seconds: float
    max_retries: int
    retry_backoff_seconds: float
    requests_per_second: float
    batch_size: int
    cast_limit: int
    keyword_limit: int

    @classmethod
    def from_env(cls) -> "Settings":
        settings = cls(
            mongodb_url=os.getenv("MONGODB_URL", "").strip(),
            mongodb_database=os.getenv("MONGODB_DATABASE", "tagmymovie").strip(),
            tmdb_base_url=os.getenv(
                "TMDB_BASE_URL", "https://api.themoviedb.org/3/"
            ).strip(),
            tmdb_api_key=(os.getenv("TMDB_KEY") or os.getenv("TMDB_API_KEY") or "").strip()
            or None,
            tmdb_access_token=os.getenv("TMDB_ACCESS_TOKEN", "").strip() or None,
            movie_pages=_integer("CATALOGUE_MOVIE_PAGES", 10, 1),
            tv_pages=_integer("CATALOGUE_TV_PAGES", 10, 1),
            sync_mode=os.getenv("CATALOGUE_SYNC_MODE", "incremental").strip().lower(),
            incremental_max_age_hours=_integer(
                "CATALOGUE_INCREMENTAL_MAX_AGE_HOURS", 24, 0
            ),
            request_timeout_seconds=_float("TMDB_REQUEST_TIMEOUT_SECONDS", 10, 0.1),
            max_retries=_integer("TMDB_MAX_RETRIES", 4, 0),
            retry_backoff_seconds=_float("TMDB_RETRY_BACKOFF_SECONDS", 0.5, 0),
            requests_per_second=_float("TMDB_REQUESTS_PER_SECOND", 4, 0.1),
            batch_size=_integer("CATALOGUE_BATCH_SIZE", 100, 1),
            cast_limit=_integer("CATALOGUE_CAST_LIMIT", 20, 1),
            keyword_limit=_integer("CATALOGUE_KEYWORD_LIMIT", 30, 1),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not self.mongodb_url:
            raise ConfigurationError("MONGODB_URL is required")
        if not self.mongodb_database:
            raise ConfigurationError("MONGODB_DATABASE is required")
        if not self.tmdb_base_url.startswith(("http://", "https://")):
            raise ConfigurationError("TMDB_BASE_URL must be an HTTP(S) URL")
        if not self.tmdb_api_key and not self.tmdb_access_token:
            raise ConfigurationError("TMDB_KEY, TMDB_API_KEY, or TMDB_ACCESS_TOKEN is required")
        if self.sync_mode not in {"full", "incremental"}:
            raise ConfigurationError("CATALOGUE_SYNC_MODE must be full or incremental")
