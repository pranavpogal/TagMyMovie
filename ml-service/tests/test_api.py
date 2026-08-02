from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.config import ApiSettings


def payload(strategy="cold_start_popular"):
    return {
        "recommendationId": "00000000-0000-0000-0000-000000000001",
        "strategy": strategy,
        "generatedAt": datetime(2026, 8, 2, tzinfo=timezone.utc),
        "modelVersions": {
            "embedding": "content-v1", "collaborative": None, "profile": "profile-v1",
            "ranking": "ranking-v1", "diversity": "diversity-v1",
        },
        "collaborativeConfidence": 0,
        "results": [{
            "mediaId": "1", "mediaType": "movie", "title": "Movie",
            "score": 0.8, "sourceModels": ["popularity"], "reasons": ["Popular and well-rated"],
        }],
    }


class Runtime:
    def __init__(self):
        self.calls = []
        self.closed = False

    def ready(self): return {"mongodb": True, "contentIndex": True}
    def model_status(self):
        return {"embedding": {"available": True, "version": "content-v1"},
                "collaborative": {"available": False, "version": None}}
    def recommend(self, user_id, params):
        self.calls.append(("recommend", user_id, params))
        value = payload()
        if params["debug"]:
            value["debug"] = {"latencyMs": 1}
            value["results"][0]["debug"] = {"features": {}}
        return value
    def similar(self, media_type, media_id, limit):
        self.calls.append(("similar", media_type, media_id, limit))
        return payload("seeded_hybrid")
    def semantic_search(self, query, filters, limit):
        self.calls.append(("search", query, filters, limit))
        return payload("content_based")
    def close(self): self.closed = True


def client(runtime=None):
    runtime = runtime or Runtime()
    app = create_app(runtime, ApiSettings("127.0.0.1", 8000, "internal-secret"))
    return TestClient(app, raise_server_exceptions=False), runtime


def test_health_readiness_and_model_status() -> None:
    api, runtime = client()
    with api:
        assert api.get("/health").json() == {"status": "ok"}
        assert api.get("/ready").json()["ready"] is True
        models = api.get("/models/status").json()["models"]
        assert models["collaborative"]["available"] is False
    assert runtime.closed is True


def test_recommendation_parameters_are_validated_and_forwarded() -> None:
    api, runtime = client()
    with api:
        response = api.get(
            "/recommendations/507f1f77bcf86cd799439011",
            params=[("media_type", "movie"), ("limit", "10"), ("context", "home"),
                    ("seed_media_id", "2"), ("seed_media_type", "movie"),
                    ("language", "en"), ("genres", "18"), ("exclude_seen", "true")],
        )
    assert response.status_code == 200
    assert response.json()["strategy"] == "cold_start_popular"
    params = runtime.calls[0][2]
    assert params["limit"] == 10 and params["genres"] == [18]
    assert params["seed_media_type"] == "movie"
    assert api.get("/recommendations/user", params={"limit": 0}).status_code == 422


def test_debug_requires_internal_key_and_is_never_open_by_default() -> None:
    api, _ = client()
    with api:
        assert api.get("/recommendations/user", params={"debug": "true"}).status_code == 403
        allowed = api.get(
            "/recommendations/user", params={"debug": "true"},
            headers={"X-Internal-Key": "internal-secret"},
        )
    assert allowed.status_code == 200
    assert allowed.json()["debug"] == {"latencyMs": 1}


def test_similar_and_semantic_search_are_structured_and_filtered() -> None:
    api, runtime = client()
    with api:
        similar = api.get("/similar/movie/42", params={"limit": 5})
        search = api.get(
            "/semantic-search", params=[("q", "space adventure"), ("media_type", "tv"),
                                        ("language", "en"), ("genres", "18")],
        )
    assert similar.json()["strategy"] == "seeded_hybrid"
    assert search.json()["strategy"] == "content_based"
    filters = runtime.calls[1][2]
    assert filters.media_types == ("tv",) and filters.genre_ids == (18,)


def test_invalid_seed_pair_and_errors_do_not_expose_stack_traces() -> None:
    class Broken(Runtime):
        def recommend(self, user_id, params):
            if params.get("seed_media_id") and not params.get("seed_media_type"):
                raise ValueError("seed_media_type and seed_media_id must be provided together")
            raise RuntimeError("database password secret")

    api, _ = client(Broken())
    with api:
        invalid = api.get("/recommendations/user", params={"seed_media_id": "1"})
        failed = api.get("/recommendations/user")
    assert invalid.status_code == 422
    assert failed.status_code == 500
    assert failed.json() == {"detail": "internal service error"}
