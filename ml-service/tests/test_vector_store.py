from pathlib import Path

import pytest

from app.content.faiss_vector_store import FaissVectorStore
from app.content.mongodb_vector_store import MongoDBVectorStore
from app.content.vector_store import VectorFilters, VectorStoreError, create_vector_store


def test_factory_hides_backend_construction(tmp_path: Path) -> None:
    collection = object()
    assert isinstance(create_vector_store("faiss", artifact_directory=tmp_path), FaissVectorStore)
    assert isinstance(create_vector_store("mongodb", collection=collection), MongoDBVectorStore)
    with pytest.raises(VectorStoreError):
        create_vector_store("unknown")


def test_filter_validation_rejects_invalid_values() -> None:
    with pytest.raises(VectorStoreError):
        VectorFilters(media_types=("person",)).validate()
    with pytest.raises(VectorStoreError):
        VectorFilters(release_year_min=2025, release_year_max=2000).validate()
