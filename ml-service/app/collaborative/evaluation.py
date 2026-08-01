from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from scipy.sparse import csr_matrix


@dataclass(frozen=True)
class EvaluationMetrics:
    recall_at_k: float
    ndcg_at_k: float
    hit_rate_at_k: float
    validation_users: int
    k: int

    def as_dict(self) -> dict[str, float | int]:
        return asdict(self)


def leave_one_out_split(
    user_items: csr_matrix, *, random_seed: int
) -> tuple[csr_matrix, dict[int, int]]:
    random = np.random.default_rng(random_seed)
    training = user_items.tolil(copy=True)
    held_out: dict[int, int] = {}
    for user_index in range(user_items.shape[0]):
        start, end = user_items.indptr[user_index : user_index + 2]
        item_indexes = user_items.indices[start:end]
        if len(item_indexes) < 2:
            continue
        held_out_item = int(item_indexes[random.integers(0, len(item_indexes))])
        training[user_index, held_out_item] = 0
        held_out[user_index] = held_out_item
    result = training.tocsr()
    result.eliminate_zeros()
    return result, held_out


def evaluate_model(
    model: Any,
    training_user_items: csr_matrix,
    held_out: dict[int, int],
    *,
    k: int,
) -> EvaluationMetrics:
    hits = 0
    ndcg = 0.0
    for user_index, expected_item in sorted(held_out.items()):
        item_ids, _ = model.recommend(
            user_index,
            training_user_items[user_index],
            N=min(k, training_user_items.shape[1]),
            filter_already_liked_items=True,
        )
        recommended = [int(item_id) for item_id in item_ids]
        if expected_item in recommended:
            hits += 1
            rank = recommended.index(expected_item) + 1
            ndcg += 1.0 / math.log2(rank + 1)
    users = len(held_out)
    recall = hits / users if users else 0.0
    return EvaluationMetrics(
        recall_at_k=recall,
        ndcg_at_k=ndcg / users if users else 0.0,
        hit_rate_at_k=recall,
        validation_users=users,
        k=k,
    )


def metrics_are_finite(metrics: EvaluationMetrics) -> bool:
    return all(
        math.isfinite(value)
        for value in (
            metrics.recall_at_k,
            metrics.ndcg_at_k,
            metrics.hit_rate_at_k,
        )
    )
