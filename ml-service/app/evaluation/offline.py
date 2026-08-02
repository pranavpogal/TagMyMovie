from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Callable, Iterable

from app.collaborative.interaction_weights import collaborative_confidence


MODEL_NAMES = (
    "popularity",
    "content_based",
    "collaborative_als",
    "hybrid_without_diversity",
    "hybrid_with_diversity",
)


@dataclass(frozen=True)
class TimeSplit:
    training: tuple[dict[str, Any], ...]
    test_by_user: dict[str, tuple[str, ...]]
    eligible_users: tuple[str, ...]
    cold_start_users: int
    cold_start_items: int


def time_based_split(
    interactions: Iterable[dict[str, Any]], *, minimum_interactions: int = 3,
    test_items_per_user: int = 1,
) -> TimeSplit:
    if minimum_interactions < 2 or test_items_per_user < 1 or test_items_per_user >= minimum_interactions:
        raise ValueError("time split settings are invalid")
    by_user: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    all_valid: list[dict[str, Any]] = []
    for value in interactions:
        user = str(value.get("user") or "").strip()
        media_type = value.get("mediaType")
        media_id = str(value.get("mediaId") or "").strip()
        created_at = value.get("createdAt")
        if (not user or media_type not in {"movie", "tv"} or not media_id
                or not isinstance(created_at, datetime)
                or collaborative_confidence(str(value.get("eventType") or ""), value.get("value")) <= 0):
            continue
        normalized = {**value, "user": user, "mediaId": media_id}
        all_valid.append(normalized)
        key = f"{media_type}:{media_id}"
        previous = by_user[user].get(key)
        if previous is None or created_at > previous["createdAt"]:
            by_user[user][key] = normalized

    eligible = tuple(sorted(user for user, values in by_user.items() if len(values) >= minimum_interactions))
    held_signatures: set[tuple[str, str, str]] = set()
    test_by_user: dict[str, tuple[str, ...]] = {}
    for user in eligible:
        ordered = sorted(by_user[user].items(), key=lambda pair: (pair[1]["createdAt"], pair[0]))
        held = ordered[-test_items_per_user:]
        test_by_user[user] = tuple(key for key, _ in held)
        held_signatures.update((user, value["mediaType"], value["mediaId"]) for _, value in held)
    training = tuple(value for value in all_valid if (
        str(value["user"]), value["mediaType"], value["mediaId"]
    ) not in held_signatures)
    training_users = {str(value["user"]) for value in training}
    training_items = {f"{value['mediaType']}:{value['mediaId']}" for value in training}
    return TimeSplit(
        training=training,
        test_by_user=test_by_user,
        eligible_users=eligible,
        cold_start_users=sum(user not in training_users for user in eligible),
        cold_start_items=len({item for values in test_by_user.values() for item in values} - training_items),
    )


def evaluate_rankings(
    split: TimeSplit,
    recommenders: dict[str, Callable[[str, int], list[str]]],
    catalogue: dict[str, dict[str, Any]], *, k: int = 10,
    minimum_evaluation_users: int = 5,
) -> dict[str, Any]:
    missing = set(MODEL_NAMES) - set(recommenders)
    if missing:
        raise ValueError(f"missing recommenders: {', '.join(sorted(missing))}")
    counts = {
        "eligibleUsers": len(split.eligible_users), "items": len(catalogue),
        "trainingInteractions": len(split.training),
        "testInteractions": sum(len(values) for values in split.test_by_user.values()),
        "coldStartUsers": split.cold_start_users, "coldStartItems": split.cold_start_items,
    }
    warning = None
    if len(split.eligible_users) < minimum_evaluation_users:
        warning = f"insufficient evaluation sample: {len(split.eligible_users)} users; require {minimum_evaluation_users}"
        return {"k": k, "counts": counts, "warning": warning, "models": {name: None for name in MODEL_NAMES}}
    popularity = Counter(f"{value['mediaType']}:{value['mediaId']}" for value in split.training)
    models = {}
    for name in MODEL_NAMES:
        rankings = {user: _unique(recommenders[name](user, k))[:k] for user in split.eligible_users}
        models[name] = _metrics(rankings, split.test_by_user, catalogue, popularity, k)
    return {"k": k, "counts": counts, "warning": warning, "models": models}


def _metrics(rankings, expected_by_user, catalogue, popularity, k):
    recall = hit_rate = ndcg = average_precision = reciprocal_rank = 0.0
    recommended_catalogue: set[str] = set()
    genre_diversities = []
    intra_list = []
    novelties = []
    total_popularity = max(1, sum(popularity.values()))
    for user, expected_values in expected_by_user.items():
        expected = set(expected_values)
        ranked = rankings[user]
        hits = [index for index, item in enumerate(ranked, 1) if item in expected]
        recall += len(hits) / len(expected)
        hit_rate += float(bool(hits))
        ndcg += sum(1 / math.log2(rank + 1) for rank in hits) / sum(
            1 / math.log2(rank + 1) for rank in range(1, min(len(expected), k) + 1)
        )
        precisions = [sum(1 for previous in hits if previous <= rank) / rank for rank in hits]
        average_precision += sum(precisions) / min(len(expected), k)
        reciprocal_rank += 1 / hits[0] if hits else 0
        recommended_catalogue.update(ranked)
        genre_sets = [set(catalogue.get(item, {}).get("genreIds") or []) for item in ranked]
        genre_union = set().union(*genre_sets) if genre_sets else set()
        genre_diversities.append(len(genre_union) / max(1, len(ranked)))
        distances = [1 - _jaccard(genre_sets[i], genre_sets[j]) for i in range(len(genre_sets)) for j in range(i + 1, len(genre_sets))]
        intra_list.append(sum(distances) / len(distances) if distances else 0.0)
        novelties.extend(-math.log2(max(1, popularity[item]) / total_popularity) for item in ranked)
    users = len(expected_by_user)
    return {
        f"recallAt{k}": recall / users, f"hitRateAt{k}": hit_rate / users,
        f"ndcgAt{k}": ndcg / users, f"mapAt{k}": average_precision / users,
        f"mrrAt{k}": reciprocal_rank / users,
        "catalogueCoverage": len(recommended_catalogue) / max(1, len(catalogue)),
        "genreDiversity": sum(genre_diversities) / users,
        "intraListDiversity": sum(intra_list) / users,
        "novelty": sum(novelties) / len(novelties) if novelties else 0.0,
    }


def content_scores(user: str, training_by_user: dict[str, set[str]], catalogue: dict[str, dict[str, Any]]) -> dict[str, float]:
    liked = training_by_user.get(user, set())
    liked_genres = Counter(genre for key in liked for genre in catalogue.get(key, {}).get("genreIds", []))
    liked_languages = Counter(catalogue.get(key, {}).get("originalLanguage") for key in liked)
    return {key: sum(liked_genres[genre] for genre in item.get("genreIds", []))
            + 0.5 * liked_languages[item.get("originalLanguage")] for key, item in catalogue.items() if key not in liked}


def rank_scores(scores: dict[str, float], k: int) -> list[str]:
    return [key for key, _ in sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))[:k]]


def reciprocal_rank_fusion(*rankings: list[str]) -> dict[str, float]:
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, item in enumerate(ranking, 1):
            scores[item] += 1 / (60 + rank)
    return dict(scores)


def diversify(ranking: list[str], catalogue: dict[str, dict[str, Any]], k: int, relevance_weight: float = 0.8) -> list[str]:
    candidates = list(ranking)
    selected: list[str] = []
    relevance = {item: 1 - index / max(1, len(candidates)) for index, item in enumerate(candidates)}
    while candidates and len(selected) < k:
        best = max(candidates, key=lambda item: (
            relevance_weight * relevance[item] - (1 - relevance_weight) * max(
                (_jaccard(set(catalogue.get(item, {}).get("genreIds", [])), set(catalogue.get(other, {}).get("genreIds", []))) for other in selected),
                default=0,
            ), -candidates.index(item),
        ))
        selected.append(best)
        candidates.remove(best)
    return selected


def _jaccard(left: set[Any], right: set[Any]) -> float:
    return len(left & right) / len(left | right) if left | right else 0.0


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))
