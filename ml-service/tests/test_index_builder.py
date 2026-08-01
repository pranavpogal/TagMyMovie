from __future__ import annotations

import json
from pathlib import Path

import faiss
import pytest

from app.content.embeddings import EmbeddingError
from app.content.index_builder import build_faiss_index


def test_builds_faiss_index_and_aligned_identity_manifest(tmp_path: Path) -> None:
    records = [
        {
            "tmdbId": "10",
            "mediaType": "movie",
            "embedding": [1.0, 0.0],
            "embeddingDimension": 2,
        },
        {
            "tmdbId": "20",
            "mediaType": "tv",
            "embedding": [0.0, 2.0],
            "embeddingDimension": 2,
        },
    ]

    count = build_faiss_index(
        records,
        artifact_directory=tmp_path,
        index_name="media",
        model_name="model",
        version="v1",
    )

    index = faiss.read_index(str(tmp_path / "media.faiss"))
    manifest = json.loads((tmp_path / "media.json").read_text(encoding="utf-8"))
    assert count == 2
    assert index.ntotal == 2
    assert index.d == 2
    assert manifest["items"] == [
        {"mediaType": "movie", "tmdbId": "10"},
        {"mediaType": "tv", "tmdbId": "20"},
    ]
    assert manifest["dimension"] == 2


def test_index_rejects_mixed_dimensions(tmp_path: Path) -> None:
    records = [
        {"tmdbId": "1", "mediaType": "movie", "embedding": [1.0], "embeddingDimension": 1},
        {"tmdbId": "2", "mediaType": "tv", "embedding": [1.0, 0.0], "embeddingDimension": 2},
    ]

    with pytest.raises(EmbeddingError, match="mixed dimensions"):
        build_faiss_index(
            records,
            artifact_directory=tmp_path,
            index_name="media",
            model_name="model",
            version="v1",
        )
