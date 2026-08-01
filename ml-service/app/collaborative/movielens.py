from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class MovieLensDatasetError(ValueError):
    """Raised when a local MovieLens dataset is absent or malformed."""


@dataclass(frozen=True)
class MovieLensLoadResult:
    interactions: list[dict[str, Any]]
    user_ids: set[str]
    mapped_movies: int
    skipped_unmapped: int
    skipped_non_positive: int
    invalid_rows: int

    def as_dict(self) -> dict[str, int]:
        return {
            "interactions": len(self.interactions),
            "users": len(self.user_ids),
            "mappedMovies": self.mapped_movies,
            "skippedUnmapped": self.skipped_unmapped,
            "skippedNonPositive": self.skipped_non_positive,
            "invalidRows": self.invalid_rows,
        }


def load_movielens(
    dataset_path: Path, *, valid_movie_tmdb_ids: set[str]
) -> MovieLensLoadResult:
    links_path = dataset_path / "links.csv"
    ratings_path = dataset_path / "ratings.csv"
    if not dataset_path.is_dir() or not links_path.is_file() or not ratings_path.is_file():
        raise MovieLensDatasetError(
            "dataset path must contain MovieLens links.csv and ratings.csv"
        )

    links: dict[str, str] = {}
    invalid_rows = 0
    with links_path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        _require_columns(reader, {"movieId", "tmdbId"}, "links.csv")
        for row in reader:
            movie_id = str(row.get("movieId") or "").strip()
            tmdb_id = str(row.get("tmdbId") or "").strip()
            if movie_id.isdigit() and tmdb_id.isdigit():
                links[movie_id] = tmdb_id
            else:
                invalid_rows += 1

    interactions: list[dict[str, Any]] = []
    users: set[str] = set()
    mapped_tmdb_ids: set[str] = set()
    skipped_unmapped = 0
    skipped_non_positive = 0
    with ratings_path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        _require_columns(
            reader, {"userId", "movieId", "rating", "timestamp"}, "ratings.csv"
        )
        for row in reader:
            try:
                user_id = str(row.get("userId") or "").strip()
                movie_id = str(row.get("movieId") or "").strip()
                rating = float(row.get("rating") or "")
                timestamp = int(row.get("timestamp") or "")
                if (
                    not user_id.isdigit()
                    or not movie_id.isdigit()
                    or not 0.5 <= rating <= 5
                ):
                    raise ValueError
                created_at = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            except (ValueError, TypeError, OSError, OverflowError):
                invalid_rows += 1
                continue
            tmdb_id = links.get(movie_id)
            if tmdb_id is None or tmdb_id not in valid_movie_tmdb_ids:
                skipped_unmapped += 1
                continue
            ten_point_rating = rating * 2
            if ten_point_rating < 7:
                skipped_non_positive += 1
                continue
            namespaced_user = f"movielens:{user_id}"
            users.add(namespaced_user)
            mapped_tmdb_ids.add(tmdb_id)
            interactions.append(
                {
                    "user": namespaced_user,
                    "mediaId": tmdb_id,
                    "mediaType": "movie",
                    "eventType": "rating_submit",
                    "value": ten_point_rating,
                    "createdAt": created_at,
                    "sessionId": None,
                    "recommendationId": None,
                    "dataSource": "movielens",
                    "external": True,
                }
            )
    return MovieLensLoadResult(
        interactions,
        users,
        len(mapped_tmdb_ids),
        skipped_unmapped,
        skipped_non_positive,
        invalid_rows,
    )


def _require_columns(
    reader: csv.DictReader, required: set[str], file_name: str
) -> None:
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise MovieLensDatasetError(
            f"{file_name} is missing required columns: {', '.join(sorted(required))}"
        )
