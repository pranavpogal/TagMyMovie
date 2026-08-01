from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.content.embedding_repository import EmbeddingRepository, EmbeddingUpdate


class FakeCollection:
    def __init__(self) -> None:
        self.operations = []

    def bulk_write(self, operations, ordered):
        assert ordered is False
        self.operations.extend(operations)
        return SimpleNamespace(modified_count=len(operations))


def test_persistence_stores_complete_embedding_contract_with_race_guard() -> None:
    collection = FakeCollection()
    observed_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
    update = EmbeddingUpdate(
        document_id="mongo-id",
        previous_feature_hash="old-hash",
        source_updated_at=observed_at,
        feature_text="Title: Example.",
        feature_hash="new-hash",
        embedding=[0.6, 0.8],
        model_name="model",
        version="v1",
    )

    result = EmbeddingRepository(collection).persist([update])

    assert result == (1, 0)
    operation = collection.operations[0]
    assert operation._filter == {
        "_id": "mongo-id",
        "featureHash": "old-hash",
        "updatedAt": observed_at,
    }
    stored = operation._doc["$set"]
    assert stored["featureText"] == "Title: Example."
    assert stored["featureHash"] == "new-hash"
    assert stored["embedding"] == [0.6, 0.8]
    assert stored["embeddingDimension"] == 2
    assert stored["embeddingModel"] == "model"
    assert stored["embeddingVersion"] == "v1"
