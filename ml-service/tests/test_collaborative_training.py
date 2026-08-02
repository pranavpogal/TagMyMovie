from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest
from scipy.sparse import csr_matrix

from app.collaborative.mappings import MatrixMappings
from app.collaborative.matrix_builder import CollaborativeDataset, MatrixSummary
from app.collaborative.training import TrainingValidationError, train_and_promote
from app.collaborative.model_artifacts import activate_model_version, write_model_version
from app.config import CollaborativeModelSettings


class FakeModel:
    def fit(self, user_items, show_progress):
        assert show_progress is False
        self.user_factors = np.ones((user_items.shape[0], 2), dtype="float32")
        self.item_factors = np.ones((user_items.shape[1], 2), dtype="float32")

    def recommend(self, userid, user_items, N, filter_already_liked_items):
        return np.arange(N), np.linspace(1, 0, N)

    def save(self, path):
        Path(path).write_bytes(b"safe-model-artifact")


class NoHitModel(FakeModel):
    def recommend(self, userid, user_items, N, filter_already_liked_items):
        return np.asarray([], dtype=int), np.asarray([], dtype=float)


def settings(tmp_path: Path, minimum_validation_users=1):
    return CollaborativeModelSettings(
        tmp_path, "als-v1", 2, 0.05, 2, 20, 42, 3, minimum_validation_users
    )


def dataset(matrix) -> CollaborativeDataset:
    return CollaborativeDataset(
        csr_matrix(matrix, dtype="float32"),
        MatrixMappings(("user-a", "user-b"), ("movie:1", "movie:2", "tv:1")),
        MatrixSummary(users=2, items=3, interactions=4),
        "matrix-v1",
    )


def test_training_writes_version_and_atomically_promotes_current(tmp_path: Path) -> None:
    trained_at = datetime(2026, 8, 1, 12, 30, tzinfo=timezone.utc)
    result = train_and_promote(
        dataset([[1, 1, 0], [0, 1, 1]]),
        settings(tmp_path),
        data_start=datetime(2026, 7, 1, tzinfo=timezone.utc),
        data_end=datetime(2026, 8, 1, tzinfo=timezone.utc),
        trained_at=trained_at,
        model=FakeModel(),
    )

    current = tmp_path / "current"
    assert current.is_symlink()
    assert current.resolve() == result.version_directory.resolve()
    assert (current / "model.npz").read_bytes() == b"safe-model-artifact"
    metadata = json.loads((current / "model_metadata.json").read_text())
    evaluation = json.loads((current / "evaluation.json").read_text())
    assert metadata["matrixOrientation"] == "users_by_items"
    assert metadata["trainingUsers"] == 2
    assert metadata["trainingItems"] == 3
    assert metadata["dataStart"] == "2026-07-01T00:00:00+00:00"
    assert metadata["metrics"]["recallAt3"] == result.metrics.recall_at_k
    assert evaluation["passed"] is True
    assert (current / "user_mapping.json").exists()
    assert (current / "item_mapping.json").exists()


def test_candidate_version_does_not_replace_current_until_activation(tmp_path: Path) -> None:
    previous = tmp_path / "versions" / "previous"
    previous.mkdir(parents=True)
    (previous / "model.npz").write_bytes(b"previous")
    (tmp_path / "current").symlink_to(Path("versions") / "previous")
    candidate = write_model_version(
        model=FakeModel(), mappings=dataset([[1, 1, 0], [0, 1, 1]]).mappings,
        metadata={"modelVersion": "test"}, evaluation={"passed": True},
        artifact_directory=tmp_path, version_name="candidate",
    )
    assert (tmp_path / "current").resolve() == previous.resolve()
    activate_model_version(tmp_path, candidate)
    assert (tmp_path / "current").resolve() == candidate.resolve()


def test_failed_validation_does_not_create_or_replace_current(tmp_path: Path) -> None:
    previous = tmp_path / "versions" / "previous"
    previous.mkdir(parents=True)
    (previous / "model.npz").write_bytes(b"previous")
    (tmp_path / "current").symlink_to(Path("versions") / "previous")
    one_item_dataset = CollaborativeDataset(
        csr_matrix([[1]], dtype="float32"),
        MatrixMappings(("user",), ("movie:1",)),
        MatrixSummary(users=1, items=1, interactions=1),
        "matrix-v1",
    )

    with pytest.raises(TrainingValidationError, match="not enough users"):
        train_and_promote(
            one_item_dataset,
            settings(tmp_path),
            data_start=None,
            data_end=None,
            model=FakeModel(),
        )

    assert (tmp_path / "current" / "model.npz").read_bytes() == b"previous"


def test_zero_recall_candidate_is_not_promoted(tmp_path: Path) -> None:
    with pytest.raises(TrainingValidationError, match="recall"):
        train_and_promote(
            dataset([[1, 1, 0], [0, 1, 1]]),
            settings(tmp_path),
            data_start=None,
            data_end=None,
            model=NoHitModel(),
        )

    assert not (tmp_path / "current").exists()


def test_combined_training_records_separate_native_validation(tmp_path: Path) -> None:
    combined = CollaborativeDataset(
        csr_matrix([[1, 1, 0], [0, 1, 1]], dtype="float32"),
        MatrixMappings(("native-user", "movielens:1"), ("movie:1", "movie:2", "movie:3")),
        MatrixSummary(
            users=2,
            items=3,
            interactions=4,
            interactions_native=2,
            interactions_external=2,
        ),
        "matrix-v1",
    )
    result = train_and_promote(
        combined,
        settings(tmp_path),
        data_start=None,
        data_end=None,
        model=FakeModel(),
        data_source="combined",
        source_counts={"tagmymovieRecords": 2, "movielensRecords": 2},
    )

    assert result.native_metrics is not None
    assert result.native_metrics.validation_users == 1
    assert result.metadata["dataSource"] == "combined"
    assert result.metadata["sourceCounts"]["movielensRecords"] == 2
    evaluation = json.loads(
        (tmp_path / "current" / "evaluation.json").read_text(encoding="utf-8")
    )
    assert evaluation["nativeEvaluationAvailable"] is True
    assert evaluation["nativeMetrics"]["validationUsers"] == 1
