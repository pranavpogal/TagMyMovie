from __future__ import annotations

import re
from typing import Any

from bson import ObjectId
from pymongo.database import Database

from app.recommendations.ranking import RankingContext


PROJECTION = {
    "_id": 0,
    "tmdbId": 1,
    "mediaType": 1,
    "title": 1,
    "posterPath": 1,
    "genreIds": 1,
    "originalLanguage": 1,
    "releaseYear": 1,
    "popularity": 1,
    "voteAverage": 1,
    "voteCount": 1,
}


class CandidateRepository:
    def __init__(self, database: Database) -> None:
        self.catalogue = database["media_catalog"]
        self.preferences = database["userpreferences"]

    def popularity_candidates(
        self,
        *,
        limit: int,
        minimum_vote_count: int,
        minimum_vote_average: float,
    ) -> list[dict[str, Any]]:
        cursor = self.catalogue.find(
            {
                "mediaType": {"$in": ["movie", "tv"]},
                "voteCount": {"$gte": minimum_vote_count},
                "voteAverage": {"$gte": minimum_vote_average},
            },
            PROJECTION,
        ).sort([("popularity", -1), ("voteAverage", -1), ("voteCount", -1)])
        return list(cursor.limit(limit))

    def preference_candidates(
        self, user_id: str | ObjectId, *, limit: int
    ) -> list[dict[str, Any]]:
        user = _object_id(user_id)
        preference = self.preferences.find_one(
            {"user": user},
            {
                "_id": 0,
                "preferredGenreIds": 1,
                "preferredLanguages": 1,
                "preferredReleasePeriods": 1,
            },
        ) or {}
        clauses: list[dict[str, Any]] = [{"mediaType": {"$in": ["movie", "tv"]}}]
        genres = preference.get("preferredGenreIds") or []
        languages = preference.get("preferredLanguages") or []
        years = _release_year_ranges(preference.get("preferredReleasePeriods") or [])
        if genres:
            clauses.append({"genreIds": {"$in": genres}})
        if languages:
            clauses.append({"originalLanguage": {"$in": languages}})
        if years:
            clauses.append({"$or": [{"releaseYear": value} for value in years]})
        if len(clauses) == 1:
            return []
        cursor = self.catalogue.find({"$and": clauses}, PROJECTION).sort(
            [("popularity", -1), ("voteAverage", -1), ("voteCount", -1)]
        )
        return list(cursor.limit(limit))

    def item_embedding(self, item_key: str) -> list[float] | None:
        try:
            media_type, media_id = item_key.split(":", 1)
        except ValueError:
            return None
        if media_type not in {"movie", "tv"} or not media_id:
            return None
        document = self.catalogue.find_one(
            {
                "mediaType": media_type,
                "tmdbId": media_id,
                "embedding.0": {"$exists": True},
            },
            {"_id": 0, "embedding": 1},
        )
        return document.get("embedding") if document else None

    def ranking_context(self, user_id: str | ObjectId) -> RankingContext:
        preference = self.preferences.find_one(
            {"user": _object_id(user_id)},
            {
                "_id": 0,
                "preferredGenreIds": 1,
                "preferredLanguages": 1,
                "preferredReleasePeriods": 1,
            },
        ) or {}
        return RankingContext(
            preferred_genre_ids=frozenset(preference.get("preferredGenreIds") or []),
            preferred_languages=frozenset(
                str(value).lower()
                for value in preference.get("preferredLanguages") or []
            ),
            preferred_release_periods=tuple(
                _release_period_bounds(
                    preference.get("preferredReleasePeriods") or []
                )
            ),
        )


def _object_id(user_id: str | ObjectId) -> ObjectId:
    if isinstance(user_id, ObjectId):
        return user_id
    if not ObjectId.is_valid(user_id):
        raise ValueError("user_id must be a valid ObjectId")
    return ObjectId(user_id)


def _release_year_ranges(periods: list[str]) -> list[dict[str, int]]:
    return [
        {
            **({"$gte": minimum} if minimum is not None else {}),
            **({"$lte": maximum} if maximum is not None else {}),
        }
        for minimum, maximum in _release_period_bounds(periods)
    ]


def _release_period_bounds(
    periods: list[str],
) -> list[tuple[int | None, int | None]]:
    ranges: list[tuple[int | None, int | None]] = []
    for period in periods:
        normalized = str(period).strip().lower()
        decade = re.fullmatch(r"(\d{4})s", normalized)
        span = re.fullmatch(r"(\d{4})[-_](\d{4})", normalized)
        if decade:
            start = int(decade.group(1))
            ranges.append((start, start + 9))
        elif span:
            ranges.append((int(span.group(1)), int(span.group(2))))
        elif normalized in {"classic", "pre_1980", "before_1980"}:
            ranges.append((None, 1979))
        elif normalized in {"recent", "2020_present", "2020-present"}:
            ranges.append((2020, None))
    return ranges
