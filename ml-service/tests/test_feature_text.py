from __future__ import annotations

import unicodedata

import pytest

from app.content.feature_text import (
    FeatureTextError,
    build_feature_text,
    create_feature_text,
    embedding_needs_refresh,
    hash_feature_text,
)


def movie(**overrides):
    record = {
        "tmdbId": "157336",
        "mediaType": "movie",
        "title": "Interstellar",
        "originalTitle": "Interstellar",
        "overview": "A team of explorers travels through a wormhole in space.",
        "genres": [
            {"id": 18, "name": "Drama"},
            {"id": 878, "name": "Science Fiction"},
            {"id": 12, "name": "Adventure"},
        ],
        "originalLanguage": "en",
        "releaseYear": 2014,
        "directors": ["Christopher Nolan"],
        "creators": [],
        "cast": [
            "Matthew McConaughey",
            "Anne Hathaway",
            "Jessica Chastain",
        ],
        "keywords": [
            "time dilation",
            "space travel",
            "father daughter relationship",
        ],
    }
    record.update(overrides)
    return record


def test_builds_movie_text_in_fixed_field_order() -> None:
    text = build_feature_text(movie())

    assert text == (
        "Title: Interstellar. Type: Movie. "
        "Genres: Adventure, Drama, Science Fiction. "
        "Original language: en. Release year: 2014. "
        "Directors: Christopher Nolan. "
        "Cast: Matthew McConaughey, Anne Hathaway, Jessica Chastain. "
        "Keywords: father daughter relationship, space travel, time dilation. "
        "Plot: A team of explorers travels through a wormhole in space."
    )


def test_builds_tv_text_with_creators_instead_of_directors() -> None:
    text = build_feature_text(
        movie(
            mediaType="tv",
            title="Dark",
            releaseYear=2017,
            directors=["Not emitted"],
            creators=["Baran bo Odar", "Jantje Friese"],
        )
    )

    assert "Type: TV Show." in text
    assert "Creators: Baran bo Odar, Jantje Friese." in text
    assert "Directors:" not in text


@pytest.mark.parametrize(
    ("missing_field", "absent_label"),
    [
        ("overview", "Plot:"),
        ("cast", "Cast:"),
        ("directors", "Directors:"),
    ],
)
def test_omits_empty_labels(missing_field: str, absent_label: str) -> None:
    text = build_feature_text(movie(**{missing_field: None}))

    assert absent_label not in text
    assert "None" not in text
    assert "undefined" not in text


def test_normalizes_unicode_titles_and_whitespace() -> None:
    decomposed = "Cafe\u0301   Society"
    text = build_feature_text(movie(title=decomposed, overview="  ಒಂದು   ಕಥೆ  "))

    assert "Title: Café Society." in text
    assert "Plot: ಒಂದು ಕಥೆ." in text
    assert unicodedata.is_normalized("NFC", text)


def test_limits_long_cast_and_keyword_lists() -> None:
    text = build_feature_text(
        movie(
            cast=[f"Actor {index}" for index in range(20)],
            keywords=[f"Keyword {index:02d}" for index in range(20)],
        ),
        cast_limit=3,
        keyword_limit=4,
    )

    assert "Cast: Actor 0, Actor 1, Actor 2." in text
    assert "Actor 3" not in text
    assert "Keywords: Keyword 00, Keyword 01, Keyword 02, Keyword 03." in text
    assert "Keyword 04" not in text


def test_output_and_hash_are_deterministic() -> None:
    first = create_feature_text(movie())
    second = create_feature_text(movie())

    assert first == second
    assert len(first.feature_hash) == 64
    assert first.feature_hash == hash_feature_text(first.text)


def test_rejects_missing_title_and_invalid_limits() -> None:
    with pytest.raises(FeatureTextError):
        build_feature_text(movie(title="", originalTitle=""))
    with pytest.raises(FeatureTextError):
        build_feature_text(movie(), cast_limit=0)


def test_embedding_refresh_uses_hash_model_version_and_vector_validity() -> None:
    result = create_feature_text(movie())
    current = {
        "featureHash": result.feature_hash,
        "embeddingModel": "model-a",
        "embeddingVersion": "v1",
        "embedding": [0.1, 0.2],
        "embeddingDimension": 2,
    }

    assert not embedding_needs_refresh(
        current,
        feature_hash=result.feature_hash,
        embedding_model="model-a",
        embedding_version="v1",
    )
    assert embedding_needs_refresh(
        current,
        feature_hash="changed-hash",
        embedding_model="model-a",
        embedding_version="v1",
    )
    assert embedding_needs_refresh(
        current,
        feature_hash=result.feature_hash,
        embedding_model="model-b",
        embedding_version="v1",
    )
    assert embedding_needs_refresh(
        {**current, "embeddingDimension": 3},
        feature_hash=result.feature_hash,
        embedding_model="model-a",
        embedding_version="v1",
    )
