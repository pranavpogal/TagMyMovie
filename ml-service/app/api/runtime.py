from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.collaborative.dataset_repository import CollaborativeDatasetRepository
from app.collaborative.inference import CollaborativeInferenceService
from app.collaborative.model_loader import CollaborativeArtifactError, load_current_model
from app.config import (
    CandidateGenerationSettings, CollaborativeInferenceSettings, DiversitySettings,
    EmbeddingSettings, ExplanationSettings, FeedbackPolicySettings,
    HybridRankingSettings, ProfileSettings, StrategySettings, VectorSearchSettings,
)
from app.content.embeddings import SentenceTransformerEmbedder
from app.content.profile_builder import UserContentProfileBuilder
from app.content.profile_repository import ContentProfileRepository
from app.content.vector_store import VectorFilters, create_vector_store
from app.database import create_mongo_client
from app.recommendations.candidates import CandidateGenerationService
from app.recommendations.diversity import DiversityRerankingService
from app.recommendations.explanations import ExplanationService
from app.recommendations.feedback import FeedbackPolicyService
from app.recommendations.ranking import HybridRankingService
from app.recommendations.repository import CandidateRepository


class RecommendationRuntime:
    def __init__(self) -> None:
        embedding = EmbeddingSettings.from_env()
        vector = VectorSearchSettings.from_env()
        database_settings = CollaborativeInferenceSettings.from_env()
        self.client = create_mongo_client(embedding.mongodb_url)
        self.database = self.client[embedding.mongodb_database]
        self.vector_store = create_vector_store(
            vector.backend, collection=self.database["media_catalog"],
            index_name=vector.index_name, artifact_directory=vector.artifact_directory,
        )
        self.embedder = SentenceTransformerEmbedder(embedding.model_name)
        repository = CandidateRepository(self.database)
        profile_builder = UserContentProfileBuilder(
            ContentProfileRepository(self.database), ProfileSettings.from_env(),
            embedding_model=embedding.model_name, embedding_version=embedding.version,
        )
        collaborative = CollaborativeInferenceService(
            CollaborativeDatasetRepository(self.database), database_settings
        )
        candidate_service = CandidateGenerationService(
            profile_builder=profile_builder, vector_store=self.vector_store,
            collaborative_service=collaborative, repository=repository,
            settings=CandidateGenerationSettings.from_env(),
        )
        self.service = HybridRankingService(
            candidate_service=candidate_service, context_repository=repository,
            settings=HybridRankingSettings.from_env(),
            feedback_service=FeedbackPolicyService(repository, FeedbackPolicySettings.from_env()),
            diversity_service=DiversityRerankingService(repository, DiversitySettings.from_env()),
            explanation_service=ExplanationService(ExplanationSettings.from_env()),
            strategy_settings=StrategySettings.from_env(),
        )
        self.repository = repository
        self.embedding_settings = embedding
        self.collaborative_settings = database_settings

    def close(self) -> None:
        self.client.close()

    def ready(self) -> dict[str, bool]:
        checks = {"mongodb": False, "contentIndex": False}
        try:
            self.client.admin.command("ping")
            checks["mongodb"] = True
        except Exception:
            pass
        checks["contentIndex"] = self.vector_store.health_check().healthy
        return checks

    def model_status(self) -> dict[str, Any]:
        health = self.vector_store.health_check()
        collaborative: dict[str, Any] = {"available": False, "version": None}
        try:
            loaded = load_current_model(self.collaborative_settings.artifact_directory)
            collaborative = {"available": True, "version": loaded.metadata.get("modelVersion")}
        except CollaborativeArtifactError:
            pass
        return {
            "embedding": {"available": health.healthy, "version": self.embedding_settings.version,
                          "model": self.embedding_settings.model_name, "itemCount": health.item_count},
            "collaborative": collaborative,
        }

    def recommend(self, user_id: str, params: dict[str, Any]) -> dict[str, Any]:
        seed_key = _seed_key(params.get("seed_media_type"), params.get("seed_media_id"))
        result = self.service.recommend(user_id, seed_item_key=seed_key)
        items = list(result.ranked)
        if params.get("media_type"):
            items = [item for item in items if item.candidate.media_type == params["media_type"]]
        if params.get("language"):
            items = [item for item in items if item.candidate.metadata.get("originalLanguage") == params["language"]]
        genres = set(params.get("genres") or [])
        if genres:
            items = [item for item in items if genres.intersection(item.candidate.metadata.get("genreIds") or [])]
        items = items[: params["limit"]]
        return self._response(result.strategy, result.collaborative_confidence, items, params.get("debug", False), result)

    def similar(self, media_type: str, media_id: str, limit: int) -> dict[str, Any]:
        key = f"{media_type}:{media_id}"
        vector = self.repository.item_embedding(key)
        if vector is None:
            return self._simple_response("tmdb_fallback", [], 0)
        values = self.vector_store.search(vector, limit=limit + 1, num_candidates=max(300, limit + 1))
        results = [value for value in values if value.key != key][:limit]
        return self._simple_response("seeded_hybrid", results, 0)

    def semantic_search(self, query: str, filters: VectorFilters, limit: int) -> dict[str, Any]:
        vector = self.embedder.embed([query])[0]
        values = self.vector_store.search(vector, filters=filters, limit=limit, num_candidates=max(300, limit))
        return self._simple_response("content_based", values, 0)

    def _response(self, strategy, confidence, items, debug, result):
        status = self.model_status()
        versions = {
            "embedding": self.embedding_settings.version,
            "collaborative": status["collaborative"]["version"],
            "profile": ProfileSettings.from_env().version,
            "ranking": result.ranking_version,
            "diversity": result.diversity_version,
        }
        return {
            "recommendationId": str(uuid.uuid4()), "strategy": strategy,
            "generatedAt": datetime.now(timezone.utc), "modelVersions": versions,
            "collaborativeConfidence": confidence,
            "results": [_ranked_item(item, debug) for item in items],
            "debug": {"strategyVersion": result.strategy_version} if debug else None,
        }

    def _simple_response(self, strategy, values, confidence):
        return {
            "recommendationId": str(uuid.uuid4()), "strategy": strategy,
            "generatedAt": datetime.now(timezone.utc),
            "modelVersions": {"embedding": self.embedding_settings.version,
                              "collaborative": None, "profile": None, "ranking": None, "diversity": None},
            "collaborativeConfidence": confidence,
            "results": [{"mediaId": value.tmdb_id, "mediaType": value.media_type,
                         "score": value.score, "sourceModels": ["content"], "reasons": []}
                        for value in values],
        }


def _ranked_item(item, debug):
    metadata = item.candidate.metadata
    value = {"mediaId": item.candidate.media_id, "mediaType": item.candidate.media_type,
             "title": metadata.get("title", ""), "posterPath": metadata.get("posterPath", ""),
             "releaseYear": metadata.get("releaseYear"), "voteAverage": metadata.get("voteAverage", 0),
             "score": item.score, "sourceModels": list(item.candidate.source_models),
             "reasons": list(item.explanations)}
    if debug:
        value["debug"] = item.to_debug_dict()["debug"]
    return value


def _seed_key(media_type, media_id):
    if bool(media_type) != bool(media_id):
        raise ValueError("seed_media_type and seed_media_id must be provided together")
    return f"{media_type}:{media_id}" if media_type and media_id else None
