from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Sequence

from app.content.vector_store import (
    VectorFilters,
    VectorItem,
    VectorSearchResult,
    VectorStore,
    VectorStoreError,
    VectorStoreHealth,
    normalized_vector,
)


class FaissVectorStore(VectorStore):
    def __init__(self, artifact_directory: Path, index_name: str) -> None:
        self.artifact_directory = artifact_directory
        self.index_name = index_name
        self.index_path = artifact_directory / f"{index_name}.faiss"
        self.metadata_path = artifact_directory / f"{index_name}.json"
        self._lock = threading.RLock()

    @staticmethod
    def _dependencies():
        try:
            import faiss
            import numpy as np
        except ImportError as error:  # pragma: no cover - installation boundary
            raise VectorStoreError("faiss-cpu and numpy must be installed") from error
        return faiss, np

    def _load(self):
        faiss, _ = self._dependencies()
        if not self.index_path.exists() or not self.metadata_path.exists():
            raise VectorStoreError("FAISS index or identity manifest is missing")
        try:
            index = faiss.read_index(str(self.index_path))
            manifest = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as error:
            raise VectorStoreError("FAISS artifacts could not be loaded") from error
        items = manifest.get("items")
        if not isinstance(items, list) or index.ntotal != len(items):
            raise VectorStoreError("FAISS index and identity manifest are inconsistent")
        if manifest.get("dimension") != index.d:
            raise VectorStoreError("FAISS dimension metadata is inconsistent")
        return index, manifest

    def upsert(self, items: Sequence[VectorItem]) -> int:
        if not items:
            return 0
        with self._lock:
            existing: dict[str, VectorItem] = {}
            if self.index_path.exists() or self.metadata_path.exists():
                index, manifest = self._load()
                for row, metadata in enumerate(manifest["items"]):
                    vector = index.reconstruct(row).tolist()
                    item = self._item_from_metadata(metadata, vector)
                    existing[item.key] = item
            for item in items:
                self._validate_item(item)
                existing[item.key] = item
            self._write(list(existing.values()))
        return len(items)

    def delete(self, item_keys: Sequence[str]) -> int:
        keys = set(item_keys)
        if not keys:
            return 0
        with self._lock:
            index, manifest = self._load()
            retained: list[VectorItem] = []
            deleted = 0
            for row, metadata in enumerate(manifest["items"]):
                item = self._item_from_metadata(metadata, index.reconstruct(row).tolist())
                if item.key in keys:
                    deleted += 1
                else:
                    retained.append(item)
            if deleted:
                self._write(retained)
            return deleted

    def search(
        self,
        query_vector: Sequence[float],
        filters: VectorFilters | None = None,
        limit: int = 150,
        num_candidates: int = 300,
    ) -> list[VectorSearchResult]:
        self._validate_search(limit, num_candidates)
        filters = filters or VectorFilters()
        filters.validate()
        with self._lock:
            index, manifest = self._load()
            if index.ntotal == 0:
                return []
            _, np = self._dependencies()
            query = np.asarray([normalized_vector(query_vector, index.d)], dtype="float32")
            candidate_count = min(index.ntotal, max(limit, num_candidates))
            scores, rows = index.search(query, candidate_count)
            results: list[VectorSearchResult] = []
            for score, row in zip(scores[0], rows[0]):
                if row < 0:
                    continue
                metadata = manifest["items"][int(row)]
                if not self._matches(metadata, filters):
                    continue
                results.append(
                    VectorSearchResult(
                        tmdb_id=str(metadata["tmdbId"]),
                        media_type=str(metadata["mediaType"]),
                        score=float(score),
                        metadata=dict(metadata),
                    )
                )
                if len(results) >= limit:
                    break
            return results

    def health_check(self) -> VectorStoreHealth:
        try:
            with self._lock:
                index, _ = self._load()
            return VectorStoreHealth(True, "faiss", index.ntotal, index.d)
        except VectorStoreError as error:
            return VectorStoreHealth(False, "faiss", 0, 0, str(error))

    def _write(self, items: Sequence[VectorItem]) -> None:
        faiss, np = self._dependencies()
        ordered = sorted(items, key=lambda item: item.key)
        dimension = len(ordered[0].vector) if ordered else 0
        vectors = [normalized_vector(item.vector, dimension) for item in ordered]
        index = faiss.IndexFlatIP(dimension)
        if vectors:
            index.add(np.asarray(vectors, dtype="float32"))
        manifest = {
            "backend": "faiss",
            "indexName": self.index_name,
            "dimension": dimension,
            "count": len(ordered),
            "items": [self._metadata(item) for item in ordered],
        }
        self.artifact_directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=self.artifact_directory, delete=False) as temporary:
            temporary_index = Path(temporary.name)
        temporary_metadata = temporary_index.with_suffix(".json")
        try:
            faiss.write_index(index, str(temporary_index))
            temporary_metadata.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            os.replace(temporary_index, self.index_path)
            os.replace(temporary_metadata, self.metadata_path)
        finally:
            temporary_index.unlink(missing_ok=True)
            temporary_metadata.unlink(missing_ok=True)

    @staticmethod
    def _validate_item(item: VectorItem) -> None:
        if item.media_type not in {"movie", "tv"} or not str(item.tmdb_id).strip():
            raise VectorStoreError("item requires compound movie/TV identity")
        normalized_vector(item.vector)

    @staticmethod
    def _validate_search(limit: int, num_candidates: int) -> None:
        if limit < 1 or num_candidates < limit:
            raise VectorStoreError("num_candidates must be at least the positive limit")

    @staticmethod
    def _metadata(item: VectorItem) -> dict[str, Any]:
        return {
            "mediaType": item.media_type,
            "tmdbId": str(item.tmdb_id),
            "originalLanguage": item.language,
            "genreIds": list(item.genre_ids),
            "releaseYear": item.release_year,
            "voteCount": item.vote_count,
            "embeddingModel": item.embedding_model,
            "embeddingVersion": item.embedding_version,
        }

    @staticmethod
    def _item_from_metadata(metadata: dict[str, Any], vector: Sequence[float]) -> VectorItem:
        return VectorItem(
            tmdb_id=str(metadata["tmdbId"]),
            media_type=str(metadata["mediaType"]),
            vector=vector,
            language=str(metadata.get("originalLanguage") or ""),
            genre_ids=tuple(metadata.get("genreIds") or []),
            release_year=metadata.get("releaseYear"),
            vote_count=int(metadata.get("voteCount") or 0),
            embedding_model=str(metadata.get("embeddingModel") or ""),
            embedding_version=str(metadata.get("embeddingVersion") or ""),
        )

    @staticmethod
    def _matches(metadata: dict[str, Any], filters: VectorFilters) -> bool:
        if filters.media_types and metadata.get("mediaType") not in filters.media_types:
            return False
        if filters.languages and metadata.get("originalLanguage") not in filters.languages:
            return False
        if filters.genre_ids and not set(filters.genre_ids).intersection(metadata.get("genreIds") or []):
            return False
        year = metadata.get("releaseYear")
        if filters.release_year_min is not None and (year is None or year < filters.release_year_min):
            return False
        if filters.release_year_max is not None and (year is None or year > filters.release_year_max):
            return False
        return filters.minimum_vote_count is None or int(metadata.get("voteCount") or 0) >= filters.minimum_vote_count
