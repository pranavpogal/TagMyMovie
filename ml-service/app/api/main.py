from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from app.api.runtime import RecommendationRuntime
from app.api.schemas import HealthResponse, ModelStatusResponse, ReadyResponse, RecommendationResponse
from app.config import ApiSettings
from app.content.vector_store import VectorFilters
from app.logging_config import configure_logging


LOGGER = logging.getLogger("tagmymovie.api")


def create_app(runtime: Any | None = None, settings: ApiSettings | None = None) -> FastAPI:
    settings = settings or ApiSettings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runtime = runtime or RecommendationRuntime()
        yield
        close = getattr(app.state.runtime, "close", None)
        if close:
            close()

    app = FastAPI(title="TagMyMovie ML Service", version="1.0.0", lifespan=lifespan)

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        LOGGER.info("request completed", extra={"stage": "api", "method": request.method,
                    "path": request.url.path, "status": response.status_code,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2)})
        return response

    def get_runtime(request: Request):
        return request.app.state.runtime

    def debug_allowed(debug: bool = False, x_internal_key: str | None = Header(None)) -> bool:
        if debug and (not settings.internal_debug_key or x_internal_key != settings.internal_debug_key):
            raise HTTPException(status_code=403, detail="debug access is forbidden")
        return debug

    @app.get("/health", response_model=HealthResponse)
    def health(): return {"status": "ok"}

    @app.get("/ready", response_model=ReadyResponse)
    def ready(service=Depends(get_runtime)):
        checks = service.ready()
        return {"ready": all(checks.values()), "checks": checks}

    @app.get("/models/status", response_model=ModelStatusResponse)
    def models(service=Depends(get_runtime)): return {"models": service.model_status()}

    @app.get("/recommendations/{user_id}", response_model=RecommendationResponse)
    def recommendations(
        user_id: str, media_type: str | None = Query(None, pattern="^(movie|tv)$"),
        limit: int = Query(20, ge=1, le=100), context: str | None = None,
        seed_media_id: str | None = None,
        seed_media_type: str | None = Query(None, pattern="^(movie|tv)$"),
        language: str | None = Query(None, min_length=2, max_length=3),
        genres: list[int] = Query(default=[]), exclude_seen: bool = True,
        debug: bool = Depends(debug_allowed), service=Depends(get_runtime),
    ):
        try:
            return service.recommend(user_id, locals())
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

    @app.get("/similar/{media_type}/{media_id}", response_model=RecommendationResponse)
    def similar(media_type: str, media_id: str, limit: int = Query(20, ge=1, le=100), service=Depends(get_runtime)):
        if media_type not in {"movie", "tv"}:
            raise HTTPException(status_code=422, detail="media_type must be movie or tv")
        return service.similar(media_type, media_id, limit)

    @app.get("/semantic-search", response_model=RecommendationResponse)
    def semantic_search(
        q: str = Query(min_length=2, max_length=500), limit: int = Query(20, ge=1, le=100),
        media_type: str | None = Query(None, pattern="^(movie|tv)$"), language: str | None = None,
        genres: list[int] = Query(default=[]), service=Depends(get_runtime),
    ):
        filters = VectorFilters(media_types=(media_type,) if media_type else (),
                                languages=(language,) if language else (), genre_ids=tuple(genres))
        return service.semantic_search(q, filters, limit)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, error: Exception):
        LOGGER.error("request failed", extra={"stage": "api", "path": request.url.path,
                                              "error_type": error.__class__.__name__})
        return JSONResponse(status_code=500, content={"detail": "internal service error"})
    return app


load_dotenv()
configure_logging()
app = create_app()
