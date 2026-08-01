from __future__ import annotations

import math

import pytest

from app.content.embeddings import (
    EmbeddingError,
    SentenceTransformerEmbedder,
    load_sentence_transformer,
)


class FakeEncoder:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def encode(self, sentences: list[str], **kwargs: object) -> object:
        self.calls.append((sentences, kwargs))
        return self.result


def test_embeddings_are_batched_normalized_and_dimensionally_valid() -> None:
    encoder = FakeEncoder([[3, 4], [0, 2]])
    embedder = SentenceTransformerEmbedder("model", encoder)

    vectors = embedder.embed(["first", "second"])

    assert vectors[0] == pytest.approx([0.6, 0.8])
    assert vectors[1] == pytest.approx([0.0, 1.0])
    assert encoder.calls[0][0] == ["first", "second"]
    assert encoder.calls[0][1]["normalize_embeddings"] is True
    assert all(math.isclose(sum(value * value for value in vector), 1) for vector in vectors)


@pytest.mark.parametrize(
    "result",
    [[], [[1, float("nan")]], [[0, 0]], [[1, 2], [1, 2, 3]]],
)
def test_invalid_embedding_output_is_rejected(result: object) -> None:
    embedder = SentenceTransformerEmbedder("model", FakeEncoder(result))

    with pytest.raises(EmbeddingError):
        embedder.embed(["one"] if len(result) < 2 else ["one", "two"])  # type: ignore[arg-type]


def test_model_loader_is_cached_per_process(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    created: list[str] = []

    class FakeSentenceTransformer:
        def __init__(self, model_name: str) -> None:
            created.append(model_name)

    module = types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer)
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    load_sentence_transformer.cache_clear()

    first = load_sentence_transformer("same-model")
    second = load_sentence_transformer("same-model")

    assert first is second
    assert created == ["same-model"]
    load_sentence_transformer.cache_clear()
