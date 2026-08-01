from __future__ import annotations

from pathlib import Path

import pytest

from app.content.faiss_vector_store import FaissVectorStore
from app.content.vector_store import VectorFilters, VectorItem, VectorStoreError


def item(
    tmdb_id: str,
    media_type: str,
    vector: list[float],
    *,
    language: str,
    genres: tuple[int, ...],
    year: int,
    votes: int,
) -> VectorItem:
    return VectorItem(
        tmdb_id,
        media_type,
        vector,
        language,
        genres,
        year,
        votes,
    )


def test_faiss_upsert_search_filters_replace_and_delete(tmp_path: Path) -> None:
    store = FaissVectorStore(tmp_path, "media")
    store.upsert(
        [
            item("1", "movie", [1, 0], language="en", genres=(18,), year=2020, votes=500),
            item("2", "tv", [0.8, 0.2], language="ko", genres=(18,), year=2022, votes=900),
            item("3", "movie", [0, 1], language="en", genres=(35,), year=1995, votes=20),
        ]
    )

    results = store.search(
        [1, 0],
        VectorFilters(
            media_types=("movie",),
            languages=("en",),
            genre_ids=(18,),
            release_year_min=2000,
            minimum_vote_count=100,
        ),
        limit=2,
        num_candidates=3,
    )
    assert [result.key for result in results] == ["movie:1"]
    assert results[0].score == pytest.approx(1.0)

    store.upsert(
        [item("1", "movie", [0, 1], language="en", genres=(18,), year=2020, votes=500)]
    )
    assert store.health_check().item_count == 3
    assert store.delete(["movie:1", "missing:9"]) == 1
    assert [result.key for result in store.search([1, 0], limit=2, num_candidates=2)] == ["tv:2", "movie:3"]


def test_faiss_health_reports_missing_or_inconsistent_artifacts(tmp_path: Path) -> None:
    store = FaissVectorStore(tmp_path, "media")
    assert not store.health_check().healthy
    (tmp_path / "media.json").write_text("{}", encoding="utf-8")
    assert not store.health_check().healthy


def test_faiss_validates_search_bounds_and_dimensions(tmp_path: Path) -> None:
    store = FaissVectorStore(tmp_path, "media")
    store.upsert([item("1", "movie", [1, 0], language="en", genres=(), year=2020, votes=1)])

    with pytest.raises(VectorStoreError, match="num_candidates"):
        store.search([1, 0], limit=3, num_candidates=2)
    with pytest.raises(VectorStoreError, match="dimension"):
        store.search([1, 0, 0], limit=1, num_candidates=1)
