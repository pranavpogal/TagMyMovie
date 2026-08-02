from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from app.config import ExplanationSettings
from app.recommendations.candidates import (
    SOURCE_COLLABORATIVE,
    SOURCE_CONTENT,
    SOURCE_POPULARITY,
    SOURCE_PREFERENCES,
    SOURCE_SEED_SIMILARITY,
)
from app.recommendations.ranking import RankedCandidate, RankingContext


LANGUAGE_NAMES = {
    "en": "English", "hi": "Hindi", "kn": "Kannada", "ta": "Tamil",
    "te": "Telugu", "ml": "Malayalam", "mr": "Marathi", "bn": "Bengali",
}


@dataclass(frozen=True)
class ExplanationResult:
    ranked: tuple[RankedCandidate, ...]
    version: str


class ExplanationService:
    def __init__(self, settings: ExplanationSettings) -> None:
        settings.validate()
        self.settings = settings

    def explain(
        self,
        ranked: Iterable[RankedCandidate],
        *,
        context: RankingContext,
        seed_title: str | None = None,
    ) -> ExplanationResult:
        return explain_ranked_candidates(
            ranked, context=context, seed_title=seed_title, settings=self.settings
        )


def explain_ranked_candidates(
    ranked: Iterable[RankedCandidate],
    *,
    context: RankingContext | None = None,
    seed_title: str | None = None,
    settings: ExplanationSettings | None = None,
) -> ExplanationResult:
    settings = settings or ExplanationSettings()
    settings.validate()
    context = context or RankingContext()
    explained = []
    for item in ranked:
        reasons = _reasons(item, context, seed_title, settings)
        explained.append(replace(item, explanations=tuple(reasons[: settings.maximum_reasons])))
    return ExplanationResult(tuple(explained), settings.version)


def _reasons(item, context, seed_title, settings):
    candidate, features = item.candidate, item.debug.features
    threshold = settings.minimum_signal_score
    signals: list[tuple[float, int, str]] = []
    if SOURCE_SEED_SIMILARITY in candidate.source_models and features.seed_similarity_score >= threshold:
        text = f"Similar themes to {seed_title}" if seed_title else "Similar to this title"
        signals.append((features.seed_similarity_score, 0, text))
    if features.genre_preference_score > 0 and context.preferred_genre_ids:
        name = _matched_genre_name(candidate.metadata, context.preferred_genre_ids)
        text = f"Matches your {name} preference" if name else "Matches your genre preferences"
        signals.append((features.genre_preference_score, 1, text))
    if features.language_preference_score > 0:
        code = str(candidate.metadata.get("originalLanguage") or "").lower()
        signals.append((1.0, 2, f"Matches your preference for {LANGUAGE_NAMES.get(code, code.upper())}-language titles"))
    if SOURCE_COLLABORATIVE in candidate.source_models and features.collaborative_score >= threshold and features.collaborative_confidence > 0:
        signals.append((features.collaborative_score * features.collaborative_confidence, 3, "Popular among users with similar preferences"))
    if SOURCE_CONTENT in candidate.source_models and features.content_similarity >= threshold:
        signals.append((features.content_similarity, 4, "Recommended from your activity"))
    if features.quality_score >= 0.60 and features.genre_preference_score > 0:
        signals.append((features.quality_score, 5, "Highly rated in genres you often choose"))
    if SOURCE_POPULARITY in candidate.source_models and features.popularity_score >= threshold:
        signals.append((features.popularity_score, 6, "Popular and well-rated"))
    if SOURCE_PREFERENCES in candidate.source_models and not any(value[1] in {1, 2} for value in signals):
        signals.append((0.25, 7, "Matches your selected preferences"))
    if not signals:
        if SOURCE_COLLABORATIVE in candidate.source_models:
            signals.append((0, 8, "Suggested from collaborative recommendation patterns"))
        elif SOURCE_CONTENT in candidate.source_models:
            signals.append((0, 9, "Suggested from your activity profile"))
        else:
            signals.append((0, 10, "Selected from quality catalogue signals"))
    signals.sort(key=lambda value: (-value[0], value[1], value[2]))
    return [text for _, _, text in signals]


def _matched_genre_name(metadata, preferred_ids):
    for genre in metadata.get("genres") or []:
        if isinstance(genre, dict) and genre.get("id") in preferred_ids and genre.get("name"):
            return str(genre["name"])
    return None
