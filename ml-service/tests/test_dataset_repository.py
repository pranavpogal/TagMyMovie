from __future__ import annotations

from bson import ObjectId

from app.collaborative.dataset_repository import CollaborativeDatasetRepository


class FakeCursor(list):
    def sort(self, *args):
        return self


class FakeCollection:
    def __init__(self, documents) -> None:
        self.documents = documents
        self.find_calls = []

    def find(self, query, projection):
        self.find_calls.append((query, projection))
        return FakeCursor(self.documents)


class FakeDatabase:
    def __init__(self, collections) -> None:
        self.collections = collections

    def __getitem__(self, name):
        return self.collections[name]


def test_repository_resolves_users_catalogue_and_reads_source_without_mutation() -> None:
    user_id = ObjectId()
    users = FakeCollection([{"_id": user_id}])
    catalogue = FakeCollection(
        [
            {"mediaType": "movie", "tmdbId": "1"},
            {"mediaType": "tv", "tmdbId": "1"},
        ]
    )
    interactions = FakeCollection([{"user": user_id, "mediaId": "1"}])
    repository = CollaborativeDatasetRepository(
        FakeDatabase(
            {
                "users": users,
                "media_catalog": catalogue,
                "interactions": interactions,
            }
        )
    )

    assert repository.valid_user_ids() == {str(user_id)}
    assert repository.valid_item_keys() == {"movie:1", "tv:1"}
    assert list(repository.iter_interactions()) == [
        {"user": user_id, "mediaId": "1"}
    ]
    assert not hasattr(interactions, "delete_many")

    assert list(repository.user_interactions(str(user_id))) == [
        {"user": user_id, "mediaId": "1"}
    ]
    assert interactions.find_calls[-1][0] == {"user": user_id}
