from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence


class VectorStoreError(RuntimeError):
    """Raised when a vector store cannot safely complete an operation."""


@dataclass(frozen=True)
class VectorFilters:
    media_types: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    genre_ids: tuple[int, ...] = ()
    release_year_min: int | None = None
    release_year_max: int | None = None
    minimum_vote_count: int | None = None

    def validate(self) -> None:
        if any(value not in {"movie", "tv"} for value in self.media_types):
            raise VectorStoreError("media_types must contain movie or tv")
        if any(
            not isinstance(value, str) or not value.strip()
            for value in self.languages
        ):
            raise VectorStoreError("languages must not contain blank values")
        if any(not isinstance(value, int) or value <= 0 for value in self.genre_ids):
            raise VectorStoreError("genre_ids must contain positive integers")
        if (
            self.release_year_min is not None
            and self.release_year_max is not None
            and self.release_year_min > self.release_year_max
        ):
            raise VectorStoreError("release year range is invalid")
        if self.minimum_vote_count is not None and self.minimum_vote_count < 0:
            raise VectorStoreError("minimum_vote_count must be non-negative")


@dataclass(frozen=True)
class VectorItem:
    tmdb_id: str
    media_type: str
    vector: Sequence[float]
    language: str = ""
    genre_ids: tuple[int, ...] = ()
    release_year: int | None = None
    vote_count: int = 0
    embedding_model: str = ""
    embedding_version: str = ""

    @property
    def key(self) -> str:
        return f"{self.media_type}:{self.tmdb_id}"


@dataclass(frozen=True)
class VectorSearchResult:
    tmdb_id: str
    media_type: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.media_type}:{self.tmdb_id}"


@dataclass(frozen=True)
class VectorStoreHealth:
    healthy: bool
    backend: str
    item_count: int
    dimension: int
    message: str = ""


def normalized_vector(vector: Sequence[float], dimension: int | None = None) -> list[float]:
    try:
        values = [float(value) for value in vector]
    except (TypeError, ValueError) as error:
        raise VectorStoreError("vector must contain numeric values") from error
    if not values or any(not math.isfinite(value) for value in values):
        raise VectorStoreError("vector must be non-empty and finite")
    if dimension is not None and len(values) != dimension:
        raise VectorStoreError("vector dimension does not match the store")
    norm = math.sqrt(sum(value * value for value in values))
    if not math.isfinite(norm) or norm <= 0:
        raise VectorStoreError("vector must have a positive norm")
    return [value / norm for value in values]


class VectorStore(ABC):
    @abstractmethod
    def upsert(self, items: Sequence[VectorItem]) -> int: ...

    @abstractmethod
    def search(
        self,
        query_vector: Sequence[float],
        filters: VectorFilters | None = None,
        limit: int = 150,
        num_candidates: int = 300,
    ) -> list[VectorSearchResult]: ...

    @abstractmethod
    def delete(self, item_keys: Sequence[str]) -> int: ...

    @abstractmethod
    def health_check(self) -> VectorStoreHealth: ...


def create_vector_store(
    backend: str,
    *,
    collection: Any = None,
    index_name: str = "media_embedding_index",
    artifact_directory: Path = Path("artifacts/content"),
    embedding_dimension: int | None = None,
) -> VectorStore:
    if backend == "faiss":
        from app.content.faiss_vector_store import FaissVectorStore

        return FaissVectorStore(artifact_directory, index_name)
    if backend == "mongodb":
        if collection is None:
            raise VectorStoreError("MongoDB collection is required")
        from app.content.mongodb_vector_store import MongoDBVectorStore

        return MongoDBVectorStore(collection, index_name, embedding_dimension)
    raise VectorStoreError("VECTOR_BACKEND must be faiss or mongodb")
