from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RecommendationItem(BaseModel):
    mediaId: str
    mediaType: str
    title: str = ""
    posterPath: str = ""
    releaseYear: int | None = None
    voteAverage: float = 0
    score: float
    sourceModels: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    debug: dict[str, Any] | None = None


class RecommendationResponse(BaseModel):
    recommendationId: str
    strategy: str
    generatedAt: datetime
    modelVersions: dict[str, str | None]
    collaborativeConfidence: float
    results: list[RecommendationItem]
    debug: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    ready: bool
    checks: dict[str, bool]


class ModelStatusResponse(BaseModel):
    models: dict[str, Any]
