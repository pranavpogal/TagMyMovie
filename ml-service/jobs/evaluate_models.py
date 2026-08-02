from __future__ import annotations

import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from app.collaborative.data_sources import load_collaborative_sources
from app.collaborative.dataset_repository import CollaborativeDatasetRepository
from app.collaborative.matrix_builder import build_interaction_matrix
from app.collaborative.model import create_als_model, validate_factor_shapes
from app.collaborative.model_artifacts import activate_model_version, write_model_version
from app.collaborative.model_loader import load_model_version
from app.config import CollaborativeDatasetSettings, CollaborativeModelSettings, MovieLensSettings
from app.database import create_mongo_client
from app.evaluation.offline import (
    content_scores, diversify, evaluate_rankings, rank_scores,
    reciprocal_rank_fusion, time_based_split,
)


def _integer(name: str, default: int) -> int:
    value = int(os.getenv(name, default))
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


def _catalogue(database) -> dict[str, dict]:
    projection = {"_id": 0, "tmdbId": 1, "mediaType": 1, "genreIds": 1,
                  "originalLanguage": 1, "popularity": 1}
    return {f"{item['mediaType']}:{item['tmdbId']}": item for item in
            database["media_catalog"].find({"mediaType": {"$in": ["movie", "tv"]}}, projection)}


def _suite(model, dataset, split, catalogue, k):
    training_by_user: dict[str, set[str]] = defaultdict(set)
    popularity = Counter()
    for value in split.training:
        key = f"{value['mediaType']}:{value['mediaId']}"
        training_by_user[str(value["user"])].add(key)
        popularity[key] += 1
    popular = [key for key, _ in sorted(popularity.items(), key=lambda pair: (-pair[1], pair[0]))]
    users = dataset.mappings.user_to_index
    items = dataset.mappings.items
    cache: dict[tuple[str, str], list[str]] = {}

    def popularity_rank(user, limit):
        seen = training_by_user.get(user, set())
        return [key for key in popular if key not in seen][:limit]

    def content_rank(user, limit):
        return rank_scores(content_scores(user, training_by_user, catalogue), limit)

    def collaborative_rank(user, limit):
        if user not in users:
            return []
        ids, _ = model.recommend(users[user], dataset.matrix[users[user]],
                                 N=min(limit, len(items)), filter_already_liked_items=True)
        return [items[int(index)] for index in ids]

    def cached(kind, user, factory):
        key = (kind, user)
        if key not in cache:
            cache[key] = factory(user, max(k * 10, 100))
        return cache[key]

    def hybrid(user, limit):
        scores = reciprocal_rank_fusion(
            cached("pop", user, popularity_rank), cached("content", user, content_rank),
            cached("als", user, collaborative_rank),
        )
        return rank_scores(scores, limit)

    return {
        "popularity": popularity_rank,
        "content_based": content_rank,
        "collaborative_als": collaborative_rank,
        "hybrid_without_diversity": hybrid,
        "hybrid_with_diversity": lambda user, limit: diversify(hybrid(user, max(limit * 5, 50)), catalogue, limit),
    }


def run_evaluation(database, dataset_settings, model_settings, source_settings, *, now=None):
    repository = CollaborativeDatasetRepository(database)
    sources = load_collaborative_sources(repository, source_settings)
    valid_interactions = [value for value in sources.interactions
                          if str(value.get("user")) in sources.valid_user_ids
                          and f"{value.get('mediaType')}:{value.get('mediaId')}" in sources.valid_item_keys]
    minimum_interactions = _integer("EVALUATION_MIN_INTERACTIONS_PER_USER", 3)
    minimum_users = _integer("EVALUATION_MIN_USERS", 5)
    test_items = _integer("EVALUATION_TEST_ITEMS_PER_USER", 1)
    split = time_based_split(valid_interactions, minimum_interactions=minimum_interactions,
                             test_items_per_user=test_items)
    dataset = build_interaction_matrix(split.training, valid_user_ids=sources.valid_user_ids,
                                       valid_item_keys=sources.valid_item_keys, settings=dataset_settings,
                                       now=now or datetime.now(timezone.utc))
    if not dataset.matrix.shape[0] or not dataset.matrix.shape[1]:
        raise ValueError("time-based training dataset is empty")
    candidate = create_als_model(model_settings)
    candidate.fit(dataset.matrix, show_progress=False)
    validate_factor_shapes(candidate, *dataset.matrix.shape)
    catalogue = _catalogue(database)
    report = evaluate_rankings(
        split, _suite(candidate, dataset, split, catalogue, model_settings.evaluation_k),
        catalogue, k=model_settings.evaluation_k, minimum_evaluation_users=minimum_users,
    )
    generated = now or datetime.now(timezone.utc)
    report.update({"generatedAt": generated.isoformat(), "split": "time_based_latest_positive",
                   "minimumInteractionsPerUser": minimum_interactions,
                   "testItemsPerUser": test_items})
    return report, candidate, dataset, generated


def _promotion_checks(report, loaded, dataset, catastrophic_ratio):
    checks = {
        "artifactLoads": loaded is not None,
        "finiteFactors": bool(math.isfinite(float(loaded.model.user_factors.sum())) and math.isfinite(float(loaded.model.item_factors.sum()))),
        "mappingsPresent": bool(loaded.user_ids and loaded.item_keys),
        "recommendationGeneration": False,
        "sampleSizeReported": report["counts"]["eligibleUsers"] > 0,
        "coverageNonZero": False,
        "notCatastrophicallyBelowPopularity": False,
    }
    if loaded.user_ids:
        ids, _ = loaded.model.recommend(0, dataset.matrix[0], N=min(10, len(loaded.item_keys)), filter_already_liked_items=True)
        checks["recommendationGeneration"] = len(ids) > 0
    popularity = report["models"]["popularity"]
    hybrid = report["models"]["hybrid_with_diversity"]
    if hybrid is not None and popularity is not None:
        k = report["k"]
        checks["coverageNonZero"] = hybrid["catalogueCoverage"] > 0
        checks["notCatastrophicallyBelowPopularity"] = hybrid[f"ndcgAt{k}"] >= popularity[f"ndcgAt{k}"] * catastrophic_ratio
    return checks


def main() -> int:
    load_dotenv()
    client = None
    try:
        dataset_settings = CollaborativeDatasetSettings.from_env()
        model_settings = CollaborativeModelSettings.from_env()
        source_settings = MovieLensSettings.from_env()
        client = create_mongo_client(dataset_settings.mongodb_url)
        client.admin.command("ping")
        report, candidate, dataset, generated = run_evaluation(
            client[dataset_settings.mongodb_database], dataset_settings, model_settings, source_settings)
        artifact_root = model_settings.artifact_directory
        evaluations = artifact_root / "evaluations"
        evaluations.mkdir(parents=True, exist_ok=True)
        version = f"{model_settings.model_version}-{generated.strftime('%Y%m%d-%H%M%S-%f')}-evaluated"
        metadata = {"modelVersion": model_settings.model_version, "artifactVersion": version,
                    "trainedAt": generated.isoformat(), "trainingUsers": dataset.matrix.shape[0],
                    "trainingItems": dataset.matrix.shape[1], "trainingInteractions": dataset.matrix.nnz,
                    "matrixOrientation": "users_by_items", "evaluationSplit": "time_based"}
        version_directory = write_model_version(model=candidate, mappings=dataset.mappings,
                                                metadata=metadata, evaluation=report,
                                                artifact_directory=artifact_root, version_name=version)
        loaded = load_model_version(version_directory)
        ratio = float(os.getenv("EVALUATION_CATASTROPHIC_NDCG_RATIO", "0.5"))
        if not 0 <= ratio <= 1:
            raise ValueError("EVALUATION_CATASTROPHIC_NDCG_RATIO must be between zero and one")
        checks = _promotion_checks(report, loaded, dataset, ratio)
        report["promotion"] = {"candidate": version, "checks": checks, "promoted": all(checks.values())}
        report_path = evaluations / f"evaluation-{generated.strftime('%Y%m%d-%H%M%S-%f')}.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        (version_directory / "evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        if all(checks.values()):
            activate_model_version(artifact_root, version_directory)
        print(json.dumps({"report": str(report_path), **report["promotion"]}, indent=2))
        return 0 if all(checks.values()) else 3
    except Exception as error:
        print(f"{error.__class__.__name__}: offline evaluation failed")
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
