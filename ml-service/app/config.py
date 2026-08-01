from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigurationError(ValueError):
    """Raised when required pipeline configuration is missing or invalid."""


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
