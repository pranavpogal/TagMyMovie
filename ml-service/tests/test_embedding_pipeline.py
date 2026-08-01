from __future__ import annotations

from pathlib import Path

from app.config import EmbeddingSettings
from app.content.embedding_pipeline import ContentEmbeddingPipeline
from app.content.embedding_repository import EmbeddingUpdate
from app.content.embeddings import EmbeddingError


def record(tmdb_id: str, *, current: bool = False) -> dict:
    result = {
        "_id": tmdb_id,
        "tmdbId": tmdb_id,
        "mediaType": "movie",
        "title": f"Title {tmdb_id}",
        "overview": "A plot",
        "genres": [{"id": 1, "name": "Drama"}],
        "cast": [],
        "directors": [],
        "creators": [],
        "keywords": [],
        "featureHash": "",
        "embedding": [],
        "embeddingDimension": 0,
        "embeddingModel": None,
        "embeddingVersion": None,
    }
    if current:
        from app.content.feature_text import create_feature_text

        feature = create_feature_text(result)
        result.update(
            featureText=feature.text,
            featureHash=feature.feature_hash,
            embedding=[1.0, 0.0],
            embeddingDimension=2,
            embeddingModel="test-model",
            embeddingVersion="v1",
        )
    return result


class FakeRepository:
    def __init__(self, records: list[dict]) -> None:
        self.records = records
        self.updates: list[EmbeddingUpdate] = []

    def iter_source_records(self):
        return iter(self.records)

    def persist(self, updates: list[EmbeddingUpdate]) -> tuple[int, int]:
        self.updates.extend(updates)
        return len(updates), 0

    def index_records(self, model_name: str, version: str) -> list[dict]:
        return [
            {
                "_id": update.document_id,
                "tmdbId": update.document_id,
                "mediaType": "movie",
                "featureHash": update.feature_hash,
                "embedding": update.embedding,
                "embeddingDimension": len(update.embedding),
            }
            for update in self.updates
        ]


class PartiallyFailingEmbedder:
    def embed(self, texts):
        if len(texts) > 1:
            raise EmbeddingError("batch failed")
        if "Title bad" in texts[0]:
            raise EmbeddingError("record failed")
        return [[1.0, 0.0]]


def settings(tmp_path: Path) -> EmbeddingSettings:
    return EmbeddingSettings(
        mongodb_url="mongodb://example",
        mongodb_database="tagmymovie",
        model_name="test-model",
        version="v1",
        batch_size=3,
        cast_limit=10,
        keyword_limit=20,
        vector_backend="faiss",
        index_name="test-index",
        artifact_directory=tmp_path,
    )


def test_pipeline_skips_current_vectors_and_isolates_batch_failures(
    monkeypatch, tmp_path: Path
) -> None:
    repository = FakeRepository([record("good"), record("bad"), record("old", current=True)])
    indexed: list[dict] = []

    def fake_index(records, **kwargs):
        indexed.extend(records)
        return len(records)

    monkeypatch.setattr(
        "app.content.embedding_pipeline.build_faiss_index", fake_index
    )

    summary = ContentEmbeddingPipeline(
        settings(tmp_path), repository, PartiallyFailingEmbedder()
    ).run()

    assert summary.as_dict() == {
        "scanned": 3,
        "unchanged": 1,
        "generated": 1,
        "persisted": 1,
        "failed": 1,
        "indexed": 1,
    }
    assert repository.updates[0].document_id == "good"
    assert repository.updates[0].model_name == "test-model"
    assert repository.updates[0].version == "v1"
    assert indexed[0]["tmdbId"] == "good"
