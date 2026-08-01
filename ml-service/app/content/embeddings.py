from __future__ import annotations

import math
from functools import lru_cache
from typing import Protocol, Sequence


class EmbeddingError(RuntimeError):
    """Raised when embedding output is missing, malformed, or inconsistent."""


class Encoder(Protocol):
    def encode(self, sentences: Sequence[str], **kwargs: object) -> object: ...


@lru_cache(maxsize=None)
def load_sentence_transformer(model_name: str) -> Encoder:
    """Load each configured transformer once in the current Python process."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as error:  # pragma: no cover - depends on local installation
        raise EmbeddingError(
            "sentence-transformers is not installed; install ml-service requirements"
        ) from error
    return SentenceTransformer(model_name)


def _validated_vector(raw_vector: object, expected_dimension: int | None) -> list[float]:
    try:
        vector = [float(value) for value in raw_vector]  # type: ignore[union-attr]
    except (TypeError, ValueError) as error:
        raise EmbeddingError("model returned a non-numeric embedding") from error
    if not vector or any(not math.isfinite(value) for value in vector):
        raise EmbeddingError("model returned an empty or non-finite embedding")
    if expected_dimension is not None and len(vector) != expected_dimension:
        raise EmbeddingError("model returned inconsistent embedding dimensions")
    norm = math.sqrt(sum(value * value for value in vector))
    if not math.isfinite(norm) or norm <= 0:
        raise EmbeddingError("model returned a zero-norm embedding")
    normalized = [value / norm for value in vector]
    return normalized


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str, encoder: Encoder | None = None) -> None:
        self.model_name = model_name
        self.encoder = encoder or load_sentence_transformer(model_name)
        self.dimension: int | None = None

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            raw_vectors = self.encoder.encode(
                list(texts),
                batch_size=len(texts),
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except Exception as error:
            raise EmbeddingError("sentence-transformer encoding failed") from error
        try:
            vectors = list(raw_vectors)  # type: ignore[arg-type]
        except TypeError as error:
            raise EmbeddingError("model returned an invalid embedding batch") from error
        if len(vectors) != len(texts):
            raise EmbeddingError("model returned the wrong number of embeddings")
        validated: list[list[float]] = []
        for raw_vector in vectors:
            vector = _validated_vector(raw_vector, self.dimension)
            self.dimension = self.dimension or len(vector)
            validated.append(vector)
        return validated
