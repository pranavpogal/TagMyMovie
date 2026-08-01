from __future__ import annotations

from typing import Any, Iterable

from bson import ObjectId
from pymongo.database import Database


class CollaborativeDatasetRepository:
    def __init__(self, database: Database) -> None:
        self.users = database["users"]
        self.catalogue = database["media_catalog"]
        self.interactions = database["interactions"]

    def valid_user_ids(self) -> set[str]:
        return {str(document["_id"]) for document in self.users.find({}, {"_id": 1})}

    def valid_item_keys(self) -> set[str]:
        return {
            f"{document['mediaType']}:{document['tmdbId']}"
            for document in self.catalogue.find(
                {"mediaType": {"$in": ["movie", "tv"]}},
                {"_id": 0, "mediaType": 1, "tmdbId": 1},
            )
        }

    def valid_movie_tmdb_ids(self) -> set[str]:
        return {
            str(document["tmdbId"])
            for document in self.catalogue.find(
                {"mediaType": "movie"}, {"_id": 0, "tmdbId": 1}
            )
        }

    def iter_interactions(self) -> Iterable[dict[str, Any]]:
        projection = {
            "user": 1,
            "mediaId": 1,
            "mediaType": 1,
            "eventType": 1,
            "value": 1,
            "createdAt": 1,
            "sessionId": 1,
            "recommendationId": 1,
        }
        return self.interactions.find({}, projection).sort("createdAt", 1)

    def user_interactions(self, user_id: str | ObjectId) -> Iterable[dict[str, Any]]:
        normalized_user_id = (
            user_id
            if isinstance(user_id, ObjectId)
            else ObjectId(user_id)
            if ObjectId.is_valid(user_id)
            else None
        )
        if normalized_user_id is None:
            raise ValueError("user_id must be a valid ObjectId")
        projection = {
            "_id": 0,
            "user": 1,
            "mediaId": 1,
            "mediaType": 1,
            "eventType": 1,
            "value": 1,
            "createdAt": 1,
            "sessionId": 1,
            "recommendationId": 1,
        }
        return self.interactions.find(
            {"user": normalized_user_id}, projection
        ).sort("createdAt", 1)
