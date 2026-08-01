from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.content.mongodb_vector_store import MongoDBVectorStore
from app.content.vector_store import VectorFilters, VectorItem, VectorStoreError


class FakeAdmin:
    def command(self, name):
        assert name == "ping"


class FakeCollection:
    def __init__(self) -> None:
        self.database = SimpleNamespace(client=SimpleNamespace(admin=FakeAdmin()))
        self.operations = []
        self.pipeline = None
        self.delete_query = None

    def bulk_write(self, operations, ordered):
        assert ordered is False
        self.operations = operations
        return SimpleNamespace(modified_count=len(operations))

    def aggregate(self, pipeline):
        self.pipeline = pipeline
        return [{"tmdbId": "1", "mediaType": "movie", "score": 0.9, "genreIds": [18]}]

    def update_many(self, query, update):
        self.delete_query = query
        return SimpleNamespace(modified_count=1)

    def count_documents(self, query):
        assert query == {"embedding.0": {"$exists": True}}
        return 7


def test_mongodb_search_translates_neutral_filters() -> None:
    collection = FakeCollection()
    store = MongoDBVectorStore(collection, "vector-index", 2)

    results = store.search(
        [3, 4],
        VectorFilters(
            media_types=("movie",),
            languages=("en",),
            genre_ids=(18, 878),
            release_year_min=2000,
            release_year_max=2025,
            minimum_vote_count=50,
        ),
        limit=10,
        num_candidates=25,
    )

    stage = collection.pipeline[0]["$vectorSearch"]
    assert stage["index"] == "vector-index"
    assert stage["numCandidates"] == 25
    assert stage["limit"] == 10
    assert stage["queryVector"] == pytest.approx([0.6, 0.8])
    assert stage["filter"] == {
        "$and": [
            {"mediaType": {"$in": ["movie"]}},
            {"originalLanguage": {"$in": ["en"]}},
            {"genreIds": {"$in": [18, 878]}},
            {"releaseYear": {"$gte": 2000, "$lte": 2025}},
            {"voteCount": {"$gte": 50}},
        ]
    }
    assert results[0].key == "movie:1"


def test_mongodb_upsert_delete_health_and_dimension_validation() -> None:
    collection = FakeCollection()
    store = MongoDBVectorStore(collection, "vector-index", 2)
    vector_item = VectorItem(
        "1", "movie", [3, 4], "en", (18,), 2020, 100, "model", "v1"
    )

    assert store.upsert([vector_item]) == 1
    assert collection.operations[0]._filter == {"tmdbId": "1", "mediaType": "movie"}
    assert collection.operations[0]._doc["$set"]["embedding"] == pytest.approx([0.6, 0.8])
    assert store.delete(["movie:1"]) == 1
    assert collection.delete_query == {"$or": [{"mediaType": "movie", "tmdbId": "1"}]}
    assert store.health_check().item_count == 7

    with pytest.raises(VectorStoreError, match="dimension"):
        store.upsert(
            [
                VectorItem(
                    "2",
                    "tv",
                    [1, 2, 3],
                    embedding_model="model",
                    embedding_version="v1",
                )
            ]
        )
