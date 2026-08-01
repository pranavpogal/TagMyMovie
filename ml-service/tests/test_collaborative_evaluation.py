from __future__ import annotations

import numpy as np
import pytest
from scipy.sparse import csr_matrix

from app.collaborative.evaluation import evaluate_model, leave_one_out_split


class RankedModel:
    def __init__(self, recommendations):
        self.recommendations = recommendations

    def recommend(self, userid, user_items, N, filter_already_liked_items):
        values = self.recommendations[userid][:N]
        return np.asarray(values), np.ones(len(values))


def test_leave_one_out_split_is_deterministic_and_preserves_shape() -> None:
    matrix = csr_matrix([[1, 2, 0], [0, 3, 4], [5, 0, 0]], dtype="float32")

    first, first_holdout = leave_one_out_split(matrix, random_seed=42)
    second, second_holdout = leave_one_out_split(matrix, random_seed=42)

    assert first_holdout == second_holdout
    assert first.shape == matrix.shape
    assert first.nnz == matrix.nnz - 2
    assert set(first_holdout) == {0, 1}


def test_evaluation_uses_real_rank_positions() -> None:
    training = csr_matrix([[1, 0, 0], [0, 1, 0]], dtype="float32")
    model = RankedModel({0: [2, 1], 1: [0, 2]})

    metrics = evaluate_model(model, training, {0: 2, 1: 2}, k=2)

    assert metrics.recall_at_k == 1
    assert metrics.hit_rate_at_k == 1
    assert metrics.ndcg_at_k == pytest.approx((1 + 1 / np.log2(3)) / 2)
    assert metrics.validation_users == 2
