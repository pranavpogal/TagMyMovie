from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId

from app.content.profile_repository import ContentProfileRepository


class FakeCursor(list):
    def sort(self, *args):
        return self


class FakeCollection:
    def __init__(self, *, found=None, one=None) -> None:
        self.found = found or []
        self.one = one
        self.queries = []

    def find(self, query, projection):
        self.queries.append((query, projection))
        return FakeCursor(self.found)

    def find_one(self, query, projection):
        self.queries.append((query, projection))
        return self.one


class FakeDatabase:
    def __init__(self, collections) -> None:
        self.collections = collections

    def __getitem__(self, name):
        return self.collections[name]


def test_repository_loads_user_signals_seeds_and_current_model_vectors() -> None:
    user_id = ObjectId()
    interactions = FakeCollection(
        found=[
            {
                "mediaId": "1",
                "mediaType": "movie",
                "eventType": "detail_view",
                "createdAt": datetime(2026, 8, 1, tzinfo=timezone.utc),
            }
        ]
    )
    preferences = FakeCollection(
        one={"favouriteSeedMedia": [{"mediaId": "2", "mediaType": "tv"}]}
    )
    catalogue = FakeCollection(
        found=[
            {"tmdbId": "1", "mediaType": "movie", "embedding": [1.0, 0.0]},
            {"tmdbId": "2", "mediaType": "tv", "embedding": [0.0, 1.0]},
        ]
    )
    repository = ContentProfileRepository(
        FakeDatabase(
            {
                "interactions": interactions,
                "userpreferences": preferences,
                "media_catalog": catalogue,
            }
        )
    )

    inputs = repository.load(
        str(user_id), embedding_model="model", embedding_version="v1"
    )

    assert inputs.onboarding_seed_keys == ("tv:2",)
    assert inputs.embeddings == {"movie:1": [1.0, 0.0], "tv:2": [0.0, 1.0]}
    assert interactions.queries[0][0]["user"] == user_id
    catalogue_query = catalogue.queries[0][0]
    assert catalogue_query["embeddingModel"] == "model"
    assert catalogue_query["embeddingVersion"] == "v1"
    assert catalogue_query["$or"] == [
        {"mediaType": "movie", "tmdbId": "1"},
        {"mediaType": "tv", "tmdbId": "2"},
    ]
