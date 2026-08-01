from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from pymongo import UpdateOne
from pymongo.collection import Collection


CATALOGUE_METADATA_FIELDS = (
    "title",
    "originalTitle",
    "overview",
    "genres",
    "genreIds",
    "originalLanguage",
    "spokenLanguages",
    "releaseDate",
    "releaseYear",
    "cast",
    "directors",
    "creators",
    "keywords",
    "popularity",
    "voteAverage",
    "voteCount",
    "posterPath",
    "backdropPath",
)


@dataclass
class UpsertCounts:
    created: int = 0
    updated: int = 0
    unchanged: int = 0

    def add(self, other: "UpsertCounts") -> None:
        self.created += other.created
        self.updated += other.updated
        self.unchanged += other.unchanged


class MediaCatalogRepository:
    def __init__(self, collection: Collection) -> None:
        self.collection = collection

    @staticmethod
    def key(record: dict[str, Any]) -> str:
        return f"{record['mediaType']}:{record['tmdbId']}"

    def get_existing(self, keys: Iterable[tuple[str, str]]) -> dict[str, dict[str, Any]]:
        identities = [
            {"mediaType": media_type, "tmdbId": str(tmdb_id)}
            for media_type, tmdb_id in keys
        ]
        if not identities:
            return {}
        projection = {field: 1 for field in CATALOGUE_METADATA_FIELDS}
        projection.update(
            {
                "tmdbId": 1,
                "mediaType": 1,
                "lastSyncedAt": 1,
                "featureText": 1,
                "featureHash": 1,
                "embedding": 1,
                "embeddingDimension": 1,
                "embeddingModel": 1,
                "embeddingVersion": 1,
            }
        )
        documents = self.collection.find({"$or": identities}, projection)
        return {self.key(document): document for document in documents}

    @staticmethod
    def is_recent(document: dict[str, Any], cutoff: datetime) -> bool:
        synced_at = document.get("lastSyncedAt")
        if not isinstance(synced_at, datetime):
            return False
        if synced_at.tzinfo is None:
            synced_at = synced_at.replace(tzinfo=timezone.utc)
        return synced_at >= cutoff

    @staticmethod
    def metadata_changed(
        existing: dict[str, Any], incoming: dict[str, Any]
    ) -> bool:
        return any(existing.get(field) != incoming.get(field) for field in CATALOGUE_METADATA_FIELDS)

    def upsert_batch(self, records: list[dict[str, Any]]) -> UpsertCounts:
        if not records:
            return UpsertCounts()

        existing = self.get_existing(
            (record["mediaType"], record["tmdbId"]) for record in records
        )
        counts = UpsertCounts()
        operations: list[UpdateOne] = []

        for record in records:
            key = self.key(record)
            current = existing.get(key)
            if current is None:
                counts.created += 1
            elif self.metadata_changed(current, record):
                counts.updated += 1
            else:
                counts.unchanged += 1

            metadata_update = {
                field: record[field]
                for field in ("tmdbId", "mediaType", *CATALOGUE_METADATA_FIELDS)
            }
            metadata_update["lastSyncedAt"] = record["lastSyncedAt"]
            operations.append(
                UpdateOne(
                    {"tmdbId": record["tmdbId"], "mediaType": record["mediaType"]},
                    {
                        "$set": metadata_update,
                        "$setOnInsert": {
                            "featureText": "",
                            "featureHash": "",
                            "embedding": [],
                            "embeddingDimension": 0,
                            "embeddingModel": None,
                            "embeddingVersion": None,
                            "createdAt": record["lastSyncedAt"],
                        },
                        "$currentDate": {"updatedAt": True},
                    },
                    upsert=True,
                )
            )

        self.collection.bulk_write(operations, ordered=False)
        return counts
