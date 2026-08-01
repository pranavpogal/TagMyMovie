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
        if self.vector_backend not in {"faiss", "mongodb"}:
            raise ConfigurationError("VECTOR_BACKEND must be faiss or mongodb")
        if not self.index_name or any(character in self.index_name for character in "/\\"):
            raise ConfigurationError("VECTOR_INDEX_NAME must be a safe file name")


@dataclass(frozen=True)
class VectorSearchSettings:
    backend: str
    index_name: str
    artifact_directory: Path
    candidate_limit: int
    num_candidates: int

    @classmethod
    def from_env(cls) -> "VectorSearchSettings":
        settings = cls(
            backend=os.getenv("VECTOR_BACKEND", "faiss").strip().lower(),
            index_name=os.getenv("VECTOR_INDEX_NAME", "media_embedding_index").strip(),
            artifact_directory=Path(
                os.getenv("CONTENT_ARTIFACT_DIRECTORY", "artifacts/content")
            ).expanduser(),
            candidate_limit=_integer("CONTENT_CANDIDATE_LIMIT", 150, 1),
            num_candidates=_integer("VECTOR_NUM_CANDIDATES", 300, 1),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.backend not in {"faiss", "mongodb"}:
            raise ConfigurationError("VECTOR_BACKEND must be faiss or mongodb")
        if not self.index_name or any(character in self.index_name for character in "/\\"):
            raise ConfigurationError("VECTOR_INDEX_NAME must be a safe file name")
        if self.num_candidates < self.candidate_limit:
            raise ConfigurationError(
                "VECTOR_NUM_CANDIDATES must be at least CONTENT_CANDIDATE_LIMIT"
            )


@dataclass(frozen=True)
class CandidateGenerationSettings:
    content_limit: int = 150
    collaborative_limit: int = 150
    popularity_limit: int = 40
    preference_limit: int = 40
    seed_similarity_limit: int = 150
    vector_num_candidates: int = 300
    popularity_minimum_vote_count: int = 100
    popularity_minimum_vote_average: float = 6.0

    @classmethod
    def from_env(cls) -> "CandidateGenerationSettings":
        settings = cls(
            content_limit=_integer("CONTENT_CANDIDATE_LIMIT", 150, 1),
            collaborative_limit=_integer("COLLABORATIVE_CANDIDATE_LIMIT", 150, 1),
            popularity_limit=_integer("POPULARITY_CANDIDATE_LIMIT", 40, 1),
            preference_limit=_integer("PREFERENCE_CANDIDATE_LIMIT", 40, 1),
            seed_similarity_limit=_integer("SEED_SIMILARITY_CANDIDATE_LIMIT", 150, 1),
            vector_num_candidates=_integer("VECTOR_NUM_CANDIDATES", 300, 1),
            popularity_minimum_vote_count=_integer(
                "POPULARITY_MINIMUM_VOTE_COUNT", 100, 0
            ),
            popularity_minimum_vote_average=_float(
                "POPULARITY_MINIMUM_VOTE_AVERAGE", 6.0, 0
            ),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        largest_vector_pool = max(self.content_limit, self.seed_similarity_limit)
        if self.vector_num_candidates < largest_vector_pool:
            raise ConfigurationError(
                "VECTOR_NUM_CANDIDATES must cover content and seed candidate limits"
            )
        if self.popularity_minimum_vote_average > 10:
            raise ConfigurationError(
                "POPULARITY_MINIMUM_VOTE_AVERAGE must be at most ten"
            )


@dataclass(frozen=True)
class ProfileSettings:
    version: str
    decay_factor: float
    weak_positive_cap: float
    negative_centroid_scale: float

    @classmethod
    def from_env(cls) -> "ProfileSettings":
        settings = cls(
            version=os.getenv("PROFILE_VERSION", "user-profile-v1").strip(),
            decay_factor=_float("RECENCY_DECAY_FACTOR", 0.98, 0.000001),
            weak_positive_cap=_float("PROFILE_WEAK_POSITIVE_CAP", 2.0, 0.000001),
            negative_centroid_scale=_float(
                "PROFILE_NEGATIVE_CENTROID_SCALE", 0.35, 0
            ),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not self.version:
            raise ConfigurationError("PROFILE_VERSION is required")
        if self.decay_factor > 1:
            raise ConfigurationError("RECENCY_DECAY_FACTOR must be at most one")
        if self.negative_centroid_scale > 1:
            raise ConfigurationError(
                "PROFILE_NEGATIVE_CENTROID_SCALE must be at most one"
            )


@dataclass(frozen=True)
class CollaborativeDatasetSettings:
    mongodb_url: str
    mongodb_database: str
    artifact_directory: Path
    matrix_version: str
    decay_factor: float
    weak_confidence_cap: float
    max_confidence: float
    minimum_user_items: int

    @classmethod
    def from_env(cls) -> "CollaborativeDatasetSettings":
        settings = cls(
            mongodb_url=os.getenv("MONGODB_URL", "").strip(),
            mongodb_database=os.getenv("MONGODB_DATABASE", "tagmymovie").strip(),
            artifact_directory=Path(
                os.getenv("CF_ARTIFACT_DIRECTORY", "artifacts/collaborative")
            ).expanduser(),
            matrix_version=os.getenv(
                "CF_MATRIX_VERSION", "interaction-matrix-v1"
            ).strip(),
            decay_factor=_float("CF_RECENCY_DECAY_FACTOR", 0.98, 0.000001),
            weak_confidence_cap=_float("CF_WEAK_CONFIDENCE_CAP", 2.0, 0.000001),
            max_confidence=_float("CF_MAX_CONFIDENCE", 10.0, 0.000001),
            minimum_user_items=_integer("CF_MIN_USER_ITEMS", 2, 1),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not self.mongodb_url:
            raise ConfigurationError("MONGODB_URL is required")
        if not self.mongodb_database:
            raise ConfigurationError("MONGODB_DATABASE is required")
        if not self.matrix_version:
            raise ConfigurationError("CF_MATRIX_VERSION is required")
        if self.decay_factor > 1:
            raise ConfigurationError("CF_RECENCY_DECAY_FACTOR must be at most one")
        if self.weak_confidence_cap > self.max_confidence:
            raise ConfigurationError(
                "CF_WEAK_CONFIDENCE_CAP must not exceed CF_MAX_CONFIDENCE"
            )


@dataclass(frozen=True)
class MovieLensSettings:
    data_source: str
    dataset_path: Path | None

    @classmethod
    def from_env(cls) -> "MovieLensSettings":
        raw_path = os.getenv("MOVIELENS_DATASET_PATH", "").strip()
        settings = cls(
            data_source=os.getenv("CF_DATA_SOURCE", "tagmymovie").strip().lower(),
            dataset_path=Path(raw_path).expanduser() if raw_path else None,
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.data_source not in {"tagmymovie", "movielens", "combined"}:
            raise ConfigurationError(
                "CF_DATA_SOURCE must be tagmymovie, movielens, or combined"
            )
        if self.data_source != "tagmymovie" and self.dataset_path is None:
            raise ConfigurationError(
                "MOVIELENS_DATASET_PATH is required for this CF_DATA_SOURCE"
            )


@dataclass(frozen=True)
class CollaborativeModelSettings:
    artifact_directory: Path
    model_version: str
    factors: int
    regularization: float
    iterations: int
    alpha: float
    random_seed: int
    evaluation_k: int
    minimum_validation_users: int
    minimum_recall_at_k: float = 0.01

    @classmethod
    def from_env(cls) -> "CollaborativeModelSettings":
        settings = cls(
            artifact_directory=Path(
                os.getenv("CF_ARTIFACT_DIRECTORY", "artifacts/collaborative")
            ).expanduser(),
            model_version=os.getenv("CF_MODEL_VERSION", "als-v1").strip(),
            factors=_integer("CF_FACTORS", 64, 1),
            regularization=_float("CF_REGULARIZATION", 0.05, 0.000001),
            iterations=_integer("CF_ITERATIONS", 30, 1),
            alpha=_float("CF_ALPHA", 20, 0.000001),
            random_seed=_integer("CF_RANDOM_SEED", 42, 0),
            evaluation_k=_integer("CF_EVALUATION_K", 10, 1),
            minimum_validation_users=_integer("CF_MIN_VALIDATION_USERS", 1, 1),
            minimum_recall_at_k=_float("CF_MIN_RECALL_AT_K", 0.01, 0),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not self.model_version or any(
            character in self.model_version for character in "/\\"
        ):
            raise ConfigurationError("CF_MODEL_VERSION must be a safe name")
        if self.minimum_recall_at_k > 1:
            raise ConfigurationError("CF_MIN_RECALL_AT_K must be at most one")


@dataclass(frozen=True)
class CollaborativeInferenceSettings:
    artifact_directory: Path
    minimum_overlap_items: int
    full_confidence_items: int
    decay_factor: float
    weak_confidence_cap: float
    max_confidence: float
    moderate_overlap_items: int = 6
    low_confidence_ceiling: float = 0.35
    moderate_confidence_ceiling: float = 0.70
    temporary_factor_multiplier: float = 0.85
    model_recency_decay_factor: float = 0.99

    @classmethod
    def from_env(cls) -> "CollaborativeInferenceSettings":
        settings = cls(
            artifact_directory=Path(
                os.getenv("CF_ARTIFACT_DIRECTORY", "artifacts/collaborative")
            ).expanduser(),
            minimum_overlap_items=_integer("CF_MIN_OVERLAP_ITEMS", 3, 1),
            full_confidence_items=_integer("CF_FULL_WEIGHT_ITEMS", 10, 1),
            decay_factor=_float("CF_RECENCY_DECAY_FACTOR", 0.98, 0.000001),
            weak_confidence_cap=_float("CF_WEAK_CONFIDENCE_CAP", 2.0, 0.000001),
            max_confidence=_float("CF_MAX_CONFIDENCE", 10.0, 0.000001),
            moderate_overlap_items=_integer("CF_MODERATE_OVERLAP_ITEMS", 6, 1),
            low_confidence_ceiling=_float("CF_LOW_CONFIDENCE_CEILING", 0.35, 0),
            moderate_confidence_ceiling=_float(
                "CF_MODERATE_CONFIDENCE_CEILING", 0.70, 0
            ),
            temporary_factor_multiplier=_float(
                "CF_TEMPORARY_FACTOR_MULTIPLIER", 0.85, 0
            ),
            model_recency_decay_factor=_float(
                "CF_MODEL_RECENCY_DECAY_FACTOR", 0.99, 0.000001
            ),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.full_confidence_items < self.minimum_overlap_items:
            raise ConfigurationError(
                "CF_FULL_WEIGHT_ITEMS must be at least CF_MIN_OVERLAP_ITEMS"
            )
        if not (
            self.minimum_overlap_items
            <= self.moderate_overlap_items
            <= self.full_confidence_items
        ):
            raise ConfigurationError(
                "CF overlap thresholds must be ordered minimum, moderate, full"
            )
        if self.decay_factor > 1:
            raise ConfigurationError("CF_RECENCY_DECAY_FACTOR must be at most one")
        if self.weak_confidence_cap > self.max_confidence:
            raise ConfigurationError(
                "CF_WEAK_CONFIDENCE_CAP must not exceed CF_MAX_CONFIDENCE"
            )
        if not (
            0 <= self.low_confidence_ceiling <= self.moderate_confidence_ceiling <= 1
        ):
            raise ConfigurationError("CF confidence ceilings must be ordered within zero and one")
        if not 0 <= self.temporary_factor_multiplier <= 1:
            raise ConfigurationError(
                "CF_TEMPORARY_FACTOR_MULTIPLIER must be between zero and one"
            )
        if self.model_recency_decay_factor > 1:
            raise ConfigurationError(
                "CF_MODEL_RECENCY_DECAY_FACTOR must be at most one"
            )


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
