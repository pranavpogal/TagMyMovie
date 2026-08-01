from __future__ import annotations

from datetime import datetime, timezone

from app.catalogue.repository import MediaCatalogRepository


class FakeCollection:
    def __init__(self, existing=None) -> None:
        self.existing = existing or []
        self.operations = []

    def find(self, _query, _projection):
        return self.existing

    def bulk_write(self, operations, ordered):
        self.operations.extend(operations)
        assert ordered is False


def record(**overrides):
    value = {
        "tmdbId": "603",
        "mediaType": "movie",
        "title": "The Matrix",
        "originalTitle": "The Matrix",
        "overview": "Overview",
        "genres": [{"id": 878, "name": "Science Fiction"}],
        "genreIds": [878],
        "originalLanguage": "en",
        "spokenLanguages": ["en"],
        "releaseDate": datetime(1999, 3, 30, tzinfo=timezone.utc),
        "releaseYear": 1999,
        "cast": ["Keanu Reeves"],
        "directors": ["Lana Wachowski"],
        "creators": [],
        "keywords": ["simulation"],
        "popularity": 100.0,
        "voteAverage": 8.2,
        "voteCount": 25000,
        "posterPath": "/poster.jpg",
        "backdropPath": "/backdrop.jpg",
        "lastSyncedAt": datetime(2026, 8, 1, tzinfo=timezone.utc),
    }
    value.update(overrides)
    return value


def test_bulk_upsert_counts_created_updated_and_unchanged() -> None:
    unchanged = record(tmdbId="1")
    updated = record(tmdbId="2", title="Old title")
    collection = FakeCollection([unchanged, updated])
    repository = MediaCatalogRepository(collection)

    counts = repository.upsert_batch(
        [
            record(tmdbId="1"),
            record(tmdbId="2", title="New title"),
            record(tmdbId="3"),
        ]
    )

    assert (counts.created, counts.updated, counts.unchanged) == (1, 1, 1)
    assert len(collection.operations) == 3


def test_upsert_never_overwrites_existing_feature_or_embedding_fields() -> None:
    collection = FakeCollection([])
    MediaCatalogRepository(collection).upsert_batch([record()])

    update_document = collection.operations[0]._doc
    assert "embedding" not in update_document["$set"]
    assert "featureText" not in update_document["$set"]
    assert update_document["$setOnInsert"]["embedding"] == []
    assert update_document["$setOnInsert"]["featureText"] == ""
