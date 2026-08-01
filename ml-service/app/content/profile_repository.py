from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bson import ObjectId
from pymongo.database import Database


PROFILE_EVENT_TYPES = (
    "detail_view",
    "search_click",
    "recommendation_click",
    "trailer_play",
    "review_create",
    "rating_submit",
    "favourite_add",
    "favourite_remove",
    "not_interested",
    "onboarding_favourite",
)


@dataclass(frozen=True)
class ProfileInputs:
    interactions: list[dict[str, Any]]
    embeddings: dict[str, list[float]]
    onboarding_seed_keys: tuple[str, ...]


class ContentProfileRepository:
    def __init__(self, database: Database) -> None:
        self.interactions = database["interactions"]
        self.preferences = database["userpreferences"]
        self.catalogue = database["media_catalog"]

    def load(
        self, user_id: str | ObjectId, *, embedding_model: str, embedding_version: str
    ) -> ProfileInputs:
        normalized_user_id = self._object_id(user_id)
        interactions = list(
            self.interactions.find(
                {
                    "user": normalized_user_id,
                    "eventType": {"$in": list(PROFILE_EVENT_TYPES)},
                },
                {
                    "_id": 0,
                    "mediaId": 1,
                    "mediaType": 1,
                    "eventType": 1,
                    "value": 1,
                    "createdAt": 1,
                },
            ).sort("createdAt", 1)
        )
        preference = self.preferences.find_one(
            {"user": normalized_user_id}, {"_id": 0, "favouriteSeedMedia": 1}
        ) or {}
        seed_keys = tuple(
            f"{item.get('mediaType')}:{str(item.get('mediaId') or '').strip()}"
            for item in preference.get("favouriteSeedMedia") or []
            if item.get("mediaType") in {"movie", "tv"}
            and str(item.get("mediaId") or "").strip()
        )
        keys = {
            (str(item.get("mediaType")), str(item.get("mediaId") or "").strip())
            for item in interactions
            if item.get("mediaType") in {"movie", "tv"}
            and str(item.get("mediaId") or "").strip()
        }
        keys.update(
            (media_type, media_id)
            for media_type, media_id in (
                key.split(":", 1) for key in seed_keys
            )
        )
        identities = [
            {"mediaType": media_type, "tmdbId": media_id}
            for media_type, media_id in sorted(keys)
        ]
        embeddings: dict[str, list[float]] = {}
        if identities:
            documents = self.catalogue.find(
                {
                    "$or": identities,
                    "embeddingModel": embedding_model,
                    "embeddingVersion": embedding_version,
                    "embedding.0": {"$exists": True},
                },
                {"_id": 0, "tmdbId": 1, "mediaType": 1, "embedding": 1},
            )
            embeddings = {
                f"{document['mediaType']}:{document['tmdbId']}": document["embedding"]
                for document in documents
            }
        return ProfileInputs(interactions, embeddings, seed_keys)

    @staticmethod
    def _object_id(user_id: str | ObjectId) -> ObjectId:
        if isinstance(user_id, ObjectId):
            return user_id
        if not ObjectId.is_valid(user_id):
            raise ValueError("user_id must be a valid ObjectId")
        return ObjectId(user_id)
