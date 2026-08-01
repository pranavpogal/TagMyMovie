from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Protocol, Sequence

from app.config import EmbeddingSettings
from app.content.embedding_repository import EmbeddingRepository, EmbeddingUpdate
from app.content.embeddings import EmbeddingError
from app.content.feature_text import (
    FeatureTextError,
    create_feature_text,
    embedding_needs_refresh,
)
from app.content.index_builder import build_faiss_index


LOGGER = logging.getLogger(__name__)


class BatchEmbedder(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


@dataclass
class EmbeddingSummary:
    scanned: int = 0
    unchanged: int = 0
    generated: int = 0
    persisted: int = 0
    failed: int = 0
    indexed: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class PendingEmbedding:
    record: dict[str, Any]
    text: str
    feature_hash: str


class ContentEmbeddingPipeline:
    def __init__(
        self,
        settings: EmbeddingSettings,
        repository: EmbeddingRepository,
        embedder: BatchEmbedder,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.embedder = embedder

    def run(self) -> EmbeddingSummary:
        summary = EmbeddingSummary()
        pending: list[PendingEmbedding] = []
        current_feature_hashes: dict[str, str] = {}
        for record in self.repository.iter_source_records():
            summary.scanned += 1
            try:
                feature = create_feature_text(
                    record,
                    cast_limit=self.settings.cast_limit,
                    keyword_limit=self.settings.keyword_limit,
                )
                current_feature_hashes[str(record["_id"])] = feature.feature_hash
                if not embedding_needs_refresh(
                    record,
                    feature_hash=feature.feature_hash,
                    embedding_model=self.settings.model_name,
                    embedding_version=self.settings.version,
                ):
                    summary.unchanged += 1
                    continue
                pending.append(PendingEmbedding(record, feature.text, feature.feature_hash))
            except (FeatureTextError, TypeError, ValueError):
                summary.failed += 1
                self._warn(record, "feature_text")

            if len(pending) >= self.settings.batch_size:
                self._process_batch(pending, summary)
                pending.clear()

        if pending:
            self._process_batch(pending, summary)

        records = [
            record
            for record in self.repository.index_records(
                self.settings.model_name, self.settings.version
            )
            if record.get("featureHash")
            == current_feature_hashes.get(str(record.get("_id")))
        ]
        summary.indexed = build_faiss_index(
            records,
            artifact_directory=self.settings.artifact_directory,
            index_name=self.settings.index_name,
            model_name=self.settings.model_name,
            version=self.settings.version,
        )
        LOGGER.info(
            "content embedding build complete",
            extra={f"count_{key}": value for key, value in summary.as_dict().items()},
        )
        return summary

    def _process_batch(
        self, pending: list[PendingEmbedding], summary: EmbeddingSummary
    ) -> None:
        successful: list[tuple[PendingEmbedding, list[float]]] = []
        try:
            vectors = self.embedder.embed([item.text for item in pending])
            if len(vectors) != len(pending):
                raise EmbeddingError("embedding batch result count mismatch")
            successful.extend(zip(pending, vectors))
        except EmbeddingError:
            # Isolate a bad record/model response so the remainder of the batch can finish.
            for item in pending:
                try:
                    vectors = self.embedder.embed([item.text])
                    if len(vectors) != 1:
                        raise EmbeddingError("single embedding result count mismatch")
                    successful.append((item, vectors[0]))
                except EmbeddingError:
                    summary.failed += 1
                    self._warn(item.record, "embedding")

        updates = [
            EmbeddingUpdate(
                document_id=item.record["_id"],
                previous_feature_hash=str(item.record.get("featureHash") or ""),
                source_updated_at=item.record.get("updatedAt"),
                feature_text=item.text,
                feature_hash=item.feature_hash,
                embedding=vector,
                model_name=self.settings.model_name,
                version=self.settings.version,
            )
            for item, vector in successful
        ]
        summary.generated += len(updates)
        persisted, failed = self.repository.persist(updates)
        summary.persisted += persisted
        summary.failed += failed

    @staticmethod
    def _warn(record: dict[str, Any], stage: str) -> None:
        LOGGER.warning(
            "content embedding record failed",
            extra={
                "stage": stage,
                "media_type": record.get("mediaType"),
                "tmdb_id": record.get("tmdbId"),
            },
        )
