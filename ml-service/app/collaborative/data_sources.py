from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.collaborative.dataset_repository import CollaborativeDatasetRepository
from app.collaborative.movielens import MovieLensLoadResult, load_movielens
from app.config import MovieLensSettings


@dataclass(frozen=True)
class CollaborativeSourceBundle:
    interactions: list[dict[str, Any]]
    valid_user_ids: set[str]
    valid_item_keys: set[str]
    data_source: str
    native_records: int
    external_records: int
    movielens: MovieLensLoadResult | None


def load_collaborative_sources(
    repository: CollaborativeDatasetRepository,
    settings: MovieLensSettings,
) -> CollaborativeSourceBundle:
    settings.validate()
    valid_item_keys = repository.valid_item_keys()
    interactions: list[dict[str, Any]] = []
    valid_users: set[str] = set()
    native_records = 0
    external_records = 0
    movie_lens: MovieLensLoadResult | None = None

    if settings.data_source in {"tagmymovie", "combined"}:
        native = [
            {**interaction, "dataSource": "tagmymovie", "external": False}
            for interaction in repository.iter_interactions()
        ]
        interactions.extend(native)
        valid_users.update(repository.valid_user_ids())
        native_records = len(native)

    if settings.data_source in {"movielens", "combined"}:
        assert settings.dataset_path is not None
        movie_lens = load_movielens(
            settings.dataset_path,
            valid_movie_tmdb_ids=repository.valid_movie_tmdb_ids(),
        )
        interactions.extend(movie_lens.interactions)
        valid_users.update(movie_lens.user_ids)
        external_records = len(movie_lens.interactions)

    return CollaborativeSourceBundle(
        interactions=interactions,
        valid_user_ids=valid_users,
        valid_item_keys=valid_item_keys,
        data_source=settings.data_source,
        native_records=native_records,
        external_records=external_records,
        movielens=movie_lens,
    )
