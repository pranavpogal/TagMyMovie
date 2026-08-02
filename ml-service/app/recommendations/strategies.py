from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.config import StrategySettings
from app.recommendations.candidates import (
    SOURCE_COLLABORATIVE,
    SOURCE_CONTENT,
    SOURCE_POPULARITY,
    SOURCE_PREFERENCES,
    SOURCE_SEED_SIMILARITY,
)
from app.recommendations.ranking import RankedCandidate


PERSONALIZED_HYBRID = "personalized_hybrid"
CONTENT_COLLABORATIVE_HYBRID = "content_collaborative_hybrid"
CONTENT_BASED = "content_based"
COLLABORATIVE_BASED = "collaborative_based"
ONBOARDING_PREFERENCES = "onboarding_preferences"
COLD_START_POPULAR = "cold_start_popular"
SEEDED_HYBRID = "seeded_hybrid"
TMDB_FALLBACK = "tmdb_fallback"


@dataclass(frozen=True)
class StrategySelection:
    strategy: str
    version: str
    active_sources: tuple[str, ...]
    collaborative_active: bool


def select_recommendation_strategy(
    ranked: Iterable[RankedCandidate],
    *,
    collaborative_confidence: float,
    seed_item_key: str | None = None,
    settings: StrategySettings | None = None,
) -> StrategySelection:
    settings = settings or StrategySettings()
    settings.validate()
    values = tuple(ranked)
    sources = {
        source for item in values for source in item.candidate.source_models
    }
    collaborative_active = (
        collaborative_confidence > 0 and SOURCE_COLLABORATIVE in sources
    )
    content_active = SOURCE_CONTENT in sources
    seed_active = bool(seed_item_key and SOURCE_SEED_SIMILARITY in sources)
    preference_active = SOURCE_PREFERENCES in sources
    popularity_active = SOURCE_POPULARITY in sources

    if seed_active:
        strategy = SEEDED_HYBRID
    elif content_active and collaborative_active:
        strategy = CONTENT_COLLABORATIVE_HYBRID
    elif collaborative_active and not (content_active or preference_active or popularity_active):
        strategy = COLLABORATIVE_BASED
    elif content_active and not (preference_active or popularity_active):
        strategy = CONTENT_BASED
    elif content_active or collaborative_active:
        strategy = PERSONALIZED_HYBRID
    elif preference_active:
        strategy = ONBOARDING_PREFERENCES
    elif popularity_active:
        strategy = COLD_START_POPULAR
    else:
        strategy = TMDB_FALLBACK
    ordered_sources = tuple(
        source for source in (
            SOURCE_CONTENT, SOURCE_COLLABORATIVE, SOURCE_PREFERENCES,
            SOURCE_POPULARITY, SOURCE_SEED_SIMILARITY,
        ) if source in sources
    )
    return StrategySelection(
        strategy, settings.version, ordered_sources, collaborative_active
    )
