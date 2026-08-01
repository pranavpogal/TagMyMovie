from __future__ import annotations

from pathlib import Path

import pytest

from app.collaborative.movielens import MovieLensDatasetError, load_movielens


def write_dataset(path: Path) -> None:
    path.mkdir()
    (path / "links.csv").write_text(
        "movieId,imdbId,tmdbId\n1,0111161,603\n2,0068646,238\n3,0000000,\n",
        encoding="utf-8",
    )
    (path / "ratings.csv").write_text(
        "userId,movieId,rating,timestamp\n"
        "1,1,4.0,1609459200\n"
        "1,1,2.0,1609545600\n"
        "2,2,5.0,1609459200\n"
        "3,999,4.5,1609459200\n"
        "bad,1,nope,invalid\n",
        encoding="utf-8",
    )


def test_movielens_maps_links_namespaces_users_and_keeps_movies_only(tmp_path: Path) -> None:
    dataset_path = tmp_path / "ml-small"
    write_dataset(dataset_path)

    result = load_movielens(dataset_path, valid_movie_tmdb_ids={"603"})

    assert len(result.interactions) == 1
    interaction = result.interactions[0]
    assert interaction["user"] == "movielens:1"
    assert interaction["mediaId"] == "603"
    assert interaction["mediaType"] == "movie"
    assert interaction["value"] == 8
    assert interaction["dataSource"] == "movielens"
    assert interaction["external"] is True
    assert result.user_ids == {"movielens:1"}
    assert result.skipped_non_positive == 1
    assert result.skipped_unmapped == 2
    assert result.invalid_rows == 2  # blank TMDB link and malformed rating


def test_movielens_requires_local_standard_csv_files(tmp_path: Path) -> None:
    with pytest.raises(MovieLensDatasetError, match="links.csv"):
        load_movielens(tmp_path, valid_movie_tmdb_ids=set())

    (tmp_path / "links.csv").write_text("wrong\n", encoding="utf-8")
    (tmp_path / "ratings.csv").write_text("wrong\n", encoding="utf-8")
    with pytest.raises(MovieLensDatasetError, match="required columns"):
        load_movielens(tmp_path, valid_movie_tmdb_ids=set())
