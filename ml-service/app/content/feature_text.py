from __future__ import annotations

import hashlib
import math
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable


class FeatureTextError(ValueError):
    """Raised when a catalogue record cannot produce valid feature text."""


@dataclass(frozen=True)
class FeatureTextResult:
    text: str
    feature_hash: str


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(unicodedata.normalize("NFC", str(value)).split())


def _unique(values: Iterable[Any], limit: int | None = None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _clean(value)
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
            if limit is not None and len(result) >= limit:
                break
    return result


def _genres(record: dict[str, Any]) -> list[str]:
    names: list[Any] = []
    for genre in record.get("genres") or []:
        names.append(genre.get("name") if isinstance(genre, dict) else genre)
    return sorted(_unique(names), key=str.casefold)


def _sorted_unique(values: Iterable[Any], limit: int | None = None) -> list[str]:
    normalized = sorted(_unique(values), key=str.casefold)
    return normalized[:limit] if limit is not None else normalized


def _append(parts: list[str], label: str, value: Any) -> None:
    normalized = _clean(value)
    if normalized:
        suffix = "" if normalized.endswith((".", "!", "?")) else "."
        parts.append(f"{label}: {normalized}{suffix}")


def _append_list(parts: list[str], label: str, values: list[str]) -> None:
    if values:
        parts.append(f"{label}: {', '.join(values)}.")


def build_feature_text(
    record: dict[str, Any], *, cast_limit: int = 10, keyword_limit: int = 20
) -> str:
    if cast_limit < 1 or keyword_limit < 1:
        raise FeatureTextError("cast and keyword limits must be positive")

    media_type = record.get("mediaType")
    if media_type not in {"movie", "tv"}:
        raise FeatureTextError("mediaType must be movie or tv")

    title = _clean(record.get("title") or record.get("originalTitle"))
    if not title:
        raise FeatureTextError("title is required")

    parts: list[str] = []
    _append(parts, "Title", title)
    _append(parts, "Type", "Movie" if media_type == "movie" else "TV Show")
    _append_list(parts, "Genres", _genres(record))
    _append(parts, "Original language", record.get("originalLanguage"))

    release_year = record.get("releaseYear")
    if isinstance(release_year, int) and 1870 <= release_year <= 2200:
        _append(parts, "Release year", release_year)

    if media_type == "movie":
        _append_list(
            parts,
            "Directors",
            _sorted_unique(record.get("directors") or []),
        )
    else:
        _append_list(
            parts,
            "Creators",
            _sorted_unique(record.get("creators") or []),
        )

    _append_list(parts, "Cast", _unique(record.get("cast") or [], cast_limit))
    _append_list(
        parts,
        "Keywords",
        _sorted_unique(record.get("keywords") or [], keyword_limit),
    )
    _append(parts, "Plot", record.get("overview"))

    text = " ".join(parts)
    if not text:
        raise FeatureTextError("feature text is empty")
    return text


def hash_feature_text(feature_text: str) -> str:
    normalized = _clean(feature_text)
    if not normalized:
        raise FeatureTextError("feature text is required")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def create_feature_text(
    record: dict[str, Any], *, cast_limit: int = 10, keyword_limit: int = 20
) -> FeatureTextResult:
    text = build_feature_text(
        record, cast_limit=cast_limit, keyword_limit=keyword_limit
    )
    return FeatureTextResult(text=text, feature_hash=hash_feature_text(text))


def embedding_needs_refresh(
    record: dict[str, Any],
    *,
    feature_hash: str,
    embedding_model: str,
    embedding_version: str,
) -> bool:
    if record.get("featureHash") != feature_hash:
        return True
    if record.get("embeddingModel") != embedding_model:
        return True
    if record.get("embeddingVersion") != embedding_version:
        return True

    embedding = record.get("embedding") or []
    dimension = record.get("embeddingDimension") or 0
    if not embedding or dimension != len(embedding):
        return True
    return any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in embedding)
