from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.collaborative.evaluation import (
    EvaluationMetrics,
    evaluate_model,
    leave_one_out_split,
    metrics_are_finite,
)
from app.collaborative.matrix_builder import CollaborativeDataset
from app.collaborative.model import create_als_model, validate_factor_shapes
from app.collaborative.model_artifacts import promote_model_artifacts
from app.config import CollaborativeModelSettings


class TrainingValidationError(RuntimeError):
    """Raised when a candidate cannot pass the minimum validation gate."""


@dataclass(frozen=True)
class TrainingResult:
    version_directory: Path
    metrics: EvaluationMetrics
    metadata: dict[str, Any]


def train_and_promote(
    dataset: CollaborativeDataset,
    settings: CollaborativeModelSettings,
    *,
    data_start: datetime | None,
    data_end: datetime | None,
    trained_at: datetime | None = None,
    model: Any | None = None,
) -> TrainingResult:
    settings.validate()
    if dataset.matrix.shape[0] == 0 or dataset.matrix.shape[1] == 0:
        raise TrainingValidationError("collaborative dataset is empty")
    training_matrix, held_out = leave_one_out_split(
        dataset.matrix, random_seed=settings.random_seed
    )
    if len(held_out) < settings.minimum_validation_users:
        raise TrainingValidationError("not enough users for holdout validation")
    candidate = model or create_als_model(settings)
    candidate.fit(training_matrix, show_progress=False)
    validate_factor_shapes(
        candidate, training_matrix.shape[0], training_matrix.shape[1]
    )
    metrics = evaluate_model(
        candidate, training_matrix, held_out, k=settings.evaluation_k
    )
    if not metrics_are_finite(metrics):
        raise TrainingValidationError("candidate produced non-finite metrics")
    if metrics.recall_at_k < settings.minimum_recall_at_k:
        raise TrainingValidationError("candidate recall is below the promotion threshold")

    timestamp = trained_at or datetime.now(timezone.utc)
    version_name = (
        f"{settings.model_version}-{timestamp.strftime('%Y%m%d-%H%M%S-%f')}-"
        f"{settings.random_seed}"
    )
    metrics_payload = {
        f"recallAt{metrics.k}": metrics.recall_at_k,
        f"ndcgAt{metrics.k}": metrics.ndcg_at_k,
        f"hitRateAt{metrics.k}": metrics.hit_rate_at_k,
        "k": metrics.k,
        "validationUsers": metrics.validation_users,
    }
    metadata = {
        "modelVersion": settings.model_version,
        "artifactVersion": version_name,
        "trainedAt": timestamp.isoformat(),
        "trainingUsers": training_matrix.shape[0],
        "trainingItems": training_matrix.shape[1],
        "trainingInteractions": training_matrix.nnz,
        "factors": settings.factors,
        "regularization": settings.regularization,
        "iterations": settings.iterations,
        "alpha": settings.alpha,
        "randomSeed": settings.random_seed,
        "matrixOrientation": "users_by_items",
        "matrixVersion": dataset.matrix_version,
        "confidenceVersion": dataset.confidence_version,
        "dataStart": data_start.isoformat() if data_start else None,
        "dataEnd": data_end.isoformat() if data_end else None,
        "metrics": metrics_payload,
    }
    version_directory = promote_model_artifacts(
        model=candidate,
        mappings=dataset.mappings,
        metadata=metadata,
        evaluation={
            **metrics_payload,
            "method": "deterministic_leave_one_out",
            "randomSeed": settings.random_seed,
            "passed": True,
        },
        artifact_directory=settings.artifact_directory,
        version_name=version_name,
    )
    return TrainingResult(version_directory, metrics, metadata)
