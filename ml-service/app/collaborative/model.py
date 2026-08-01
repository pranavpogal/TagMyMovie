from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from app.config import CollaborativeModelSettings


class CollaborativeModelError(RuntimeError):
    """Raised when the implicit ALS dependency or trained factors are invalid."""


def create_als_model(settings: CollaborativeModelSettings) -> Any:
    try:
        from implicit.als import AlternatingLeastSquares
    except ImportError as error:  # pragma: no cover - installation boundary
        raise CollaborativeModelError(
            "implicit is not installed; install ml-service requirements"
        ) from error
    return AlternatingLeastSquares(
        factors=settings.factors,
        regularization=settings.regularization,
        alpha=settings.alpha,
        iterations=settings.iterations,
        random_state=settings.random_seed,
        dtype=np.float32,
    )


def load_als_model(path: Path) -> Any:
    try:
        from implicit.cpu.als import AlternatingLeastSquares
    except ImportError as error:  # pragma: no cover - installation boundary
        raise CollaborativeModelError(
            "implicit is not installed; install ml-service requirements"
        ) from error
    return AlternatingLeastSquares.load(path)


def validate_factor_shapes(model: Any, user_count: int, item_count: int) -> None:
    user_factors = getattr(model, "user_factors", None)
    item_factors = getattr(model, "item_factors", None)
    if user_factors is None or item_factors is None:
        raise CollaborativeModelError("ALS did not create factor matrices")
    if user_factors.shape[0] != user_count or item_factors.shape[0] != item_count:
        raise CollaborativeModelError(
            "ALS factor orientation does not match users-by-items input"
        )
    if not np.isfinite(user_factors).all() or not np.isfinite(item_factors).all():
        raise CollaborativeModelError("ALS produced non-finite factors")
