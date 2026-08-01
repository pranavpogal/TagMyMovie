from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class CatalogueNormalizationError(ValueError):
    pass


def _clean_string(value: Any) -> str:
    return " ".join(str(value or "").split())


def _unique_strings(values: list[Any], limit: int | None = None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _clean_string(value)
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
            if limit and len(result) >= limit:
                break
    return result


def _release_date(value: Any) -> tuple[datetime | None, int | None]:
    normalized = _clean_string(value)
    if not normalized:
        return None, None
    try:
        parsed = datetime.strptime(normalized, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
        return parsed, parsed.year
    except ValueError:
        return None, None


def normalize_tmdb_media(
    detail: dict[str, Any],
    media_type: str,
    *,
    cast_limit: int,
    keyword_limit: int,
    synced_at: datetime | None = None,
) -> dict[str, Any]:
    if media_type not in {"movie", "tv"}:
        raise CatalogueNormalizationError("media_type must be movie or tv")

    tmdb_id = _clean_string(detail.get("id"))
    title = _clean_string(detail.get("title") or detail.get("name"))
    original_title = _clean_string(
        detail.get("original_title") or detail.get("original_name") or title
    )
    if not tmdb_id or not tmdb_id.isdigit() or not title:
        raise CatalogueNormalizationError("TMDB detail lacks a valid ID or title")

    genres: list[dict[str, Any]] = []
    seen_genres: set[int] = set()
    for genre in detail.get("genres") or []:
        try:
            genre_id = int(genre.get("id"))
        except (AttributeError, TypeError, ValueError):
            continue
        genre_name = _clean_string(genre.get("name"))
        if genre_id > 0 and genre_name and genre_id not in seen_genres:
            seen_genres.add(genre_id)
            genres.append({"id": genre_id, "name": genre_name})

    credits = detail.get("credits") or {}
    cast = _unique_strings(
        [member.get("name") for member in credits.get("cast") or [] if member],
        cast_limit,
    )
    directors = _unique_strings(
        [
            member.get("name")
            for member in credits.get("crew") or []
            if member and member.get("job") == "Director"
        ]
    )
    creators = _unique_strings(
        [creator.get("name") for creator in detail.get("created_by") or [] if creator]
    )

    keyword_payload = detail.get("keywords") or {}
    raw_keywords = keyword_payload.get("keywords") or keyword_payload.get("results") or []
    keywords = _unique_strings(
        [keyword.get("name") for keyword in raw_keywords if keyword], keyword_limit
    )

    release_date, release_year = _release_date(
        detail.get("release_date")
        if media_type == "movie"
        else detail.get("first_air_date")
    )

    spoken_languages = _unique_strings(
        [
            language.get("iso_639_1")
            for language in detail.get("spoken_languages") or []
            if language
        ]
    )

    return {
        "tmdbId": tmdb_id,
        "mediaType": media_type,
        "title": title,
        "originalTitle": original_title,
        "overview": _clean_string(detail.get("overview")),
        "genres": genres,
        "genreIds": [genre["id"] for genre in genres],
        "originalLanguage": _clean_string(detail.get("original_language")).lower(),
        "spokenLanguages": [language.lower() for language in spoken_languages],
        "releaseDate": release_date,
        "releaseYear": release_year,
        "cast": cast,
        "directors": directors,
        "creators": creators,
        "keywords": keywords,
        "popularity": max(float(detail.get("popularity") or 0), 0),
        "voteAverage": min(max(float(detail.get("vote_average") or 0), 0), 10),
        "voteCount": max(int(detail.get("vote_count") or 0), 0),
        "posterPath": _clean_string(detail.get("poster_path")),
        "backdropPath": _clean_string(detail.get("backdrop_path")),
        "lastSyncedAt": synced_at or datetime.now(timezone.utc),
    }
