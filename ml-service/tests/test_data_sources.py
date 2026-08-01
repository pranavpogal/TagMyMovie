from __future__ import annotations

from pathlib import Path

from app.collaborative.data_sources import load_collaborative_sources
from app.config import MovieLensSettings
from tests.test_movielens import write_dataset


class FakeRepository:
    def iter_interactions(self):
        return iter([{"user": "native", "mediaId": "603", "mediaType": "movie"}])

    def valid_user_ids(self):
        return {"native"}

    def valid_item_keys(self):
        return {"movie:603", "tv:603"}

    def valid_movie_tmdb_ids(self):
        return {"603"}


def test_combined_sources_keep_native_and_external_namespaces_separate(tmp_path: Path) -> None:
    dataset_path = tmp_path / "ml-small"
    write_dataset(dataset_path)

    bundle = load_collaborative_sources(
        FakeRepository(), MovieLensSettings("combined", dataset_path)
    )

    assert bundle.data_source == "combined"
    assert bundle.valid_user_ids == {"native", "movielens:1"}
    assert bundle.native_records == 1
    assert bundle.external_records == 1
    assert bundle.interactions[0]["dataSource"] == "tagmymovie"
    assert bundle.interactions[0]["external"] is False
    assert bundle.interactions[1]["mediaType"] == "movie"


def test_native_mode_does_not_read_movielens() -> None:
    bundle = load_collaborative_sources(
        FakeRepository(), MovieLensSettings("tagmymovie", None)
    )
    assert bundle.movielens is None
    assert bundle.external_records == 0
    assert bundle.valid_user_ids == {"native"}
