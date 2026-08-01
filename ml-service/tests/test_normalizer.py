from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.catalogue.normalizer import CatalogueNormalizationError, normalize_tmdb_media


def test_normalizes_movie_metadata_deterministically() -> None:
    synced_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
    detail = {
        "id": 603,
        "title": " The   Matrix ",
        "original_title": "The Matrix",
        "overview": " A hacker learns the truth. ",
        "genres": [
            {"id": 28, "name": "Action"},
            {"id": 28, "name": "Action duplicate"},
            {"id": 878, "name": "Science Fiction"},
        ],
        "original_language": "EN",
        "spoken_languages": [{"iso_639_1": "en"}],
        "release_date": "1999-03-30",
        "credits": {
            "cast": [{"name": "Keanu Reeves"}, {"name": "Keanu Reeves"}],
            "crew": [{"name": "Lana Wachowski", "job": "Director"}],
        },
        "keywords": {"keywords": [{"name": "simulation"}]},
        "popularity": 100.5,
        "vote_average": 8.2,
        "vote_count": 25000,
        "poster_path": "/poster.jpg",
        "backdrop_path": "/backdrop.jpg",
    }

    result = normalize_tmdb_media(
        detail,
        "movie",
        cast_limit=10,
        keyword_limit=10,
        synced_at=synced_at,
    )

    assert result["tmdbId"] == "603"
    assert result["title"] == "The Matrix"
    assert result["genreIds"] == [28, 878]
    assert result["cast"] == ["Keanu Reeves"]
    assert result["directors"] == ["Lana Wachowski"]
    assert result["creators"] == []
    assert result["releaseYear"] == 1999
    assert result["lastSyncedAt"] == synced_at


def test_normalizes_tv_creators_results_keywords_and_missing_date() -> None:
    detail = {
        "id": 1396,
        "name": "Breaking Bad",
        "original_name": "Breaking Bad",
        "first_air_date": "",
        "created_by": [{"name": "Vince Gilligan"}],
        "credits": {"cast": [{"name": "Bryan Cranston"}], "crew": []},
        "keywords": {"results": [{"name": "antihero"}]},
    }

    result = normalize_tmdb_media(
        detail, "tv", cast_limit=10, keyword_limit=10
    )

    assert result["mediaType"] == "tv"
    assert result["creators"] == ["Vince Gilligan"]
    assert result["keywords"] == ["antihero"]
    assert result["releaseDate"] is None
    assert result["releaseYear"] is None


def test_rejects_invalid_identity() -> None:
    with pytest.raises(CatalogueNormalizationError):
        normalize_tmdb_media(
            {"id": "not-an-id", "title": "Invalid"},
            "movie",
            cast_limit=10,
            keyword_limit=10,
        )
