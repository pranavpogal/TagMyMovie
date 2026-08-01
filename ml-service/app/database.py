from __future__ import annotations

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection


MEDIA_CATALOG_COLLECTION = "media_catalog"


def create_mongo_client(mongodb_url: str) -> MongoClient:
    return MongoClient(
        mongodb_url,
        appname="tagmymovie-ml-catalogue",
        serverSelectionTimeoutMS=10_000,
        connectTimeoutMS=10_000,
        socketTimeoutMS=20_000,
        retryWrites=True,
        tz_aware=True,
    )


def get_media_catalog_collection(
    client: MongoClient, database_name: str
) -> Collection:
    return client[database_name][MEDIA_CATALOG_COLLECTION]


def ensure_media_catalog_indexes(collection: Collection) -> None:
    collection.create_index(
        [("tmdbId", ASCENDING), ("mediaType", ASCENDING)],
        unique=True,
        name="tmdbId_1_mediaType_1",
    )
    collection.create_index([("mediaType", ASCENDING)], name="mediaType_1")
    collection.create_index([("genreIds", ASCENDING)], name="genreIds_1")
    collection.create_index(
        [("originalLanguage", ASCENDING)], name="originalLanguage_1"
    )
    collection.create_index([("releaseYear", ASCENDING)], name="releaseYear_1")
    collection.create_index([("voteCount", ASCENDING)], name="voteCount_1")
    collection.create_index([("lastSyncedAt", DESCENDING)], name="lastSyncedAt_-1")
