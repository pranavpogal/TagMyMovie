from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

from app.content.embeddings import EmbeddingError


def build_faiss_index(
    records: list[dict[str, Any]],
    *,
    artifact_directory: Path,
    index_name: str,
    model_name: str,
    version: str,
) -> int:
    try:
        import faiss
        import numpy as np
    except ImportError as error:  # pragma: no cover - depends on local installation
        raise EmbeddingError("faiss-cpu and numpy must be installed") from error

    identities: list[dict[str, str]] = []
    vectors: list[list[float]] = []
    dimension: int | None = None
    for record in records:
        vector = record.get("embedding") or []
        if not vector or any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in vector):
            raise EmbeddingError("cannot index an invalid embedding")
        if record.get("embeddingDimension") != len(vector):
            raise EmbeddingError("stored embedding dimension does not match vector")
        dimension = dimension or len(vector)
        if len(vector) != dimension:
            raise EmbeddingError("content index contains mixed dimensions")
        identities.append(
            {"mediaType": str(record["mediaType"]), "tmdbId": str(record["tmdbId"])}
        )
        vectors.append([float(value) for value in vector])

    artifact_directory.mkdir(parents=True, exist_ok=True)
    index_path = artifact_directory / f"{index_name}.faiss"
    metadata_path = artifact_directory / f"{index_name}.json"
    resolved_dimension = dimension or 0
    index = faiss.IndexFlatIP(resolved_dimension)
    if vectors:
        matrix = np.asarray(vectors, dtype="float32")
        faiss.normalize_L2(matrix)
        index.add(matrix)

    with tempfile.NamedTemporaryFile(dir=artifact_directory, delete=False) as temporary:
        temporary_index = Path(temporary.name)
    temporary_metadata = temporary_index.with_suffix(".json")
    try:
        faiss.write_index(index, str(temporary_index))
        temporary_metadata.write_text(
            json.dumps(
                {
                    "backend": "faiss",
                    "indexName": index_name,
                    "model": model_name,
                    "version": version,
                    "dimension": resolved_dimension,
                    "count": len(identities),
                    "items": identities,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        os.replace(temporary_index, index_path)
        os.replace(temporary_metadata, metadata_path)
    finally:
        temporary_index.unlink(missing_ok=True)
        temporary_metadata.unlink(missing_ok=True)
    return len(identities)
