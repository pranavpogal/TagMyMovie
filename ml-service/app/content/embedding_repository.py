from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from pymongo import UpdateOne
from pymongo.collection import Collection
from pymongo.errors import BulkWriteError


EMBEDDING_SOURCE_FIELDS = {
    "tmdbId": 1,
    "mediaType": 1,
    "title": 1,
    "originalTitle": 1,
    "overview": 1,
    "genres": 1,
    "originalLanguage": 1,
    "releaseYear": 1,
    "cast": 1,
    "directors": 1,
    "creators": 1,
    "keywords": 1,
    "featureText": 1,
    "featureHash": 1,
    "embedding": 1,
    "embeddingDimension": 1,
    "embeddingModel": 1,
    "embeddingVersion": 1,
    "updatedAt": 1,
}


@dataclass(frozen=True)
class EmbeddingUpdate:
    document_id: Any
    previous_feature_hash: str
    source_updated_at: Any
    feature_text: str
    feature_hash: str
    embedding: list[float]
    model_name: str
    version: str


class EmbeddingRepository:
    def __init__(self, collection: Collection) -> None:
        self.collection = collection

    def iter_source_records(self) -> Iterable[dict[str, Any]]:
        return self.collection.find({}, EMBEDDING_SOURCE_FIELDS).sort("_id", 1)

    def persist(self, updates: list[EmbeddingUpdate]) -> tuple[int, int]:
        if not updates:
            return 0, 0
        operations = [
            UpdateOne(
                {
                    "_id": update.document_id,
                    "featureHash": update.previous_feature_hash,
                    **(
                        {"updatedAt": update.source_updated_at}
                        if update.source_updated_at is not None
                        else {"updatedAt": {"$exists": False}}
                    ),
                },
                {
                    "$set": {
                        "featureText": update.feature_text,
                        "featureHash": update.feature_hash,
                        "embedding": update.embedding,
                        "embeddingDimension": len(update.embedding),
                        "embeddingModel": update.model_name,
                        "embeddingVersion": update.version,
                    },
                    "$currentDate": {"updatedAt": True},
                },
            )
            for update in updates
        ]
        try:
            result = self.collection.bulk_write(operations, ordered=False)
            persisted = result.modified_count
            return persisted, len(updates) - persisted
        except BulkWriteError as error:
            details = error.details or {}
            failed_indexes = {item.get("index") for item in details.get("writeErrors", [])}
            failed = len(failed_indexes)
            persisted = int(details.get("nModified", 0))
            return persisted, max(failed, len(updates) - persisted)

    def index_records(self, model_name: str, version: str) -> list[dict[str, Any]]:
        projection = {
            "tmdbId": 1,
            "mediaType": 1,
            "featureHash": 1,
            "embedding": 1,
            "embeddingDimension": 1,
            "originalLanguage": 1,
            "genreIds": 1,
            "releaseYear": 1,
            "voteCount": 1,
        }
        return list(
            self.collection.find(
                {
                    "embeddingModel": model_name,
                    "embeddingVersion": version,
                    "embedding.0": {"$exists": True},
                },
                projection,
            ).sort([("mediaType", 1), ("tmdbId", 1)])
        )
