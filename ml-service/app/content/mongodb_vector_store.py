from __future__ import annotations

from typing import Any, Sequence

from pymongo import UpdateOne
from pymongo.collection import Collection

from app.content.vector_store import (
    VectorFilters,
    VectorItem,
    VectorSearchResult,
    VectorStore,
    VectorStoreError,
    VectorStoreHealth,
    normalized_vector,
)


class MongoDBVectorStore(VectorStore):
    def __init__(
        self,
        collection: Collection,
        index_name: str,
        embedding_dimension: int | None = None,
    ) -> None:
        self.collection = collection
        self.index_name = index_name
        self.embedding_dimension = embedding_dimension

    def upsert(self, items: Sequence[VectorItem]) -> int:
        if not items:
            return 0
        operations: list[UpdateOne] = []
        for item in items:
            if item.media_type not in {"movie", "tv"} or not str(item.tmdb_id).strip():
                raise VectorStoreError("item requires compound movie/TV identity")
            if not item.embedding_model or not item.embedding_version:
                raise VectorStoreError(
                    "MongoDB vector items require embedding model and version"
                )
            vector = normalized_vector(item.vector, self.embedding_dimension)
            self.embedding_dimension = self.embedding_dimension or len(vector)
            operations.append(
                UpdateOne(
                    {"tmdbId": str(item.tmdb_id), "mediaType": item.media_type},
                    {
                        "$set": {
                            "embedding": vector,
                            "embeddingDimension": len(vector),
                            "embeddingModel": item.embedding_model,
                            "embeddingVersion": item.embedding_version,
                        },
                        "$currentDate": {"updatedAt": True},
                    },
                    upsert=False,
                )
            )
        result = self.collection.bulk_write(operations, ordered=False)
        return int(result.modified_count)

    def delete(self, item_keys: Sequence[str]) -> int:
        identities = []
        for key in set(item_keys):
            try:
                media_type, tmdb_id = key.split(":", 1)
            except ValueError as error:
                raise VectorStoreError("item key must be mediaType:tmdbId") from error
            if media_type not in {"movie", "tv"} or not tmdb_id:
                raise VectorStoreError("item key must be mediaType:tmdbId")
            identities.append({"mediaType": media_type, "tmdbId": tmdb_id})
        if not identities:
            return 0
        result = self.collection.update_many(
            {"$or": identities},
            {
                "$set": {
                    "embedding": [],
                    "embeddingDimension": 0,
                    "embeddingModel": None,
                    "embeddingVersion": None,
                },
                "$currentDate": {"updatedAt": True},
            },
        )
        return int(result.modified_count)

    def search(
        self,
        query_vector: Sequence[float],
        filters: VectorFilters | None = None,
        limit: int = 150,
        num_candidates: int = 300,
    ) -> list[VectorSearchResult]:
        if limit < 1 or num_candidates < limit:
            raise VectorStoreError("num_candidates must be at least the positive limit")
        filters = filters or VectorFilters()
        filters.validate()
        vector = normalized_vector(query_vector, self.embedding_dimension)
        self.embedding_dimension = self.embedding_dimension or len(vector)
        vector_stage: dict[str, Any] = {
            "index": self.index_name,
            "path": "embedding",
            "queryVector": vector,
            "numCandidates": num_candidates,
            "limit": limit,
        }
        mongo_filter = self._mongo_filter(filters)
        if mongo_filter:
            vector_stage["filter"] = mongo_filter
        pipeline = [
            {"$vectorSearch": vector_stage},
            {
                "$project": {
                    "_id": 0,
                    "tmdbId": 1,
                    "mediaType": 1,
                    "originalLanguage": 1,
                    "genreIds": 1,
                    "releaseYear": 1,
                    "voteCount": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]
        return [
            VectorSearchResult(
                tmdb_id=str(document["tmdbId"]),
                media_type=str(document["mediaType"]),
                score=float(document["score"]),
                metadata={key: value for key, value in document.items() if key != "score"},
            )
            for document in self.collection.aggregate(pipeline)
        ]

    def health_check(self) -> VectorStoreHealth:
        try:
            self.collection.database.client.admin.command("ping")
            count = self.collection.count_documents({"embedding.0": {"$exists": True}})
            return VectorStoreHealth(
                True, "mongodb", count, self.embedding_dimension or 0
            )
        except Exception as error:  # boundary: return no connection details
            return VectorStoreHealth(False, "mongodb", 0, 0, error.__class__.__name__)

    @staticmethod
    def _mongo_filter(filters: VectorFilters) -> dict[str, Any]:
        clauses: list[dict[str, Any]] = []
        if filters.media_types:
            clauses.append({"mediaType": {"$in": list(filters.media_types)}})
        if filters.languages:
            clauses.append({"originalLanguage": {"$in": list(filters.languages)}})
        if filters.genre_ids:
            clauses.append({"genreIds": {"$in": list(filters.genre_ids)}})
        release_year: dict[str, int] = {}
        if filters.release_year_min is not None:
            release_year["$gte"] = filters.release_year_min
        if filters.release_year_max is not None:
            release_year["$lte"] = filters.release_year_max
        if release_year:
            clauses.append({"releaseYear": release_year})
        if filters.minimum_vote_count is not None:
            clauses.append({"voteCount": {"$gte": filters.minimum_vote_count}})
        if not clauses:
            return {}
        return clauses[0] if len(clauses) == 1 else {"$and": clauses}
