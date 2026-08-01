from __future__ import annotations

from pathlib import Path

from scipy.sparse import csr_matrix
import numpy as np

from app.collaborative.model import (
    create_als_model,
    load_als_model,
    validate_factor_shapes,
)
from app.config import CollaborativeModelSettings


def model_settings(tmp_path: Path) -> CollaborativeModelSettings:
    return CollaborativeModelSettings(tmp_path, "als-test", 3, 0.05, 2, 2, 42, 2, 1)


def test_installed_implicit_model_uses_users_by_items_orientation(tmp_path: Path) -> None:
    user_items = csr_matrix(
        [[1, 1, 0, 0], [0, 1, 1, 0], [1, 0, 0, 1]], dtype="float32"
    )
    model = create_als_model(model_settings(tmp_path))

    model.fit(user_items, show_progress=False)
    validate_factor_shapes(model, user_count=3, item_count=4)

    assert model.user_factors.shape[0] == user_items.shape[0]
    assert model.item_factors.shape[0] == user_items.shape[1]

    model_path = tmp_path / "model.npz"
    model.save(model_path)
    restored = load_als_model(model_path)
    assert restored.user_factors.shape == model.user_factors.shape
    assert restored.item_factors.shape == model.item_factors.shape

    temporary_row = csr_matrix([[1, 1, 0, 0]], dtype="float32")
    temporary_factor = model.recalculate_user(0, temporary_row)
    item_ids, scores = model.recommend(
        0,
        temporary_row,
        N=2,
        filter_already_liked_items=True,
        recalculate_user=True,
    )
    assert temporary_factor.shape == (model.user_factors.shape[1],)
    assert np.isfinite(temporary_factor).all()
    assert len(item_ids) == len(scores) == 2
