from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping, Sequence

from app.config import DiversitySettings
from app.recommendations.ranking import RankedCandidate


@dataclass(frozen=True)
class DiversityDiagnostic:
    selection_score: float
    maximum_similarity: float
    selected_rank: int


@dataclass(frozen=True)
class DiversityResult:
    ranked: tuple[RankedCandidate, ...]
    diagnostics: Mapping[str, DiversityDiagnostic]
    version: str


class DiversityRerankingService:
    def __init__(self, repository: Any, settings: DiversitySettings) -> None:
        settings.validate()
        self.repository = repository
        self.settings = settings

    def rerank(self, ranked: Iterable[RankedCandidate]) -> DiversityResult:
        values = tuple(ranked)
        metadata = self.repository.diversity_metadata(
            [item.candidate.item_key for item in values]
        )
        enriched = tuple(
            replace(
                item,
                candidate=replace(
                    item.candidate,
                    metadata={
                        **item.candidate.metadata,
                        **metadata.get(item.candidate.item_key, {}),
                    },
                ),
            )
            for item in values
        )
        return diversify_ranked_candidates(enriched, settings=self.settings)


def diversify_ranked_candidates(
    ranked: Iterable[RankedCandidate],
    *,
    settings: DiversitySettings | None = None,
) -> DiversityResult:
    settings = settings or DiversitySettings()
    settings.validate()
    remaining = list(ranked)
    selected: list[RankedCandidate] = []
    diagnostics: dict[str, DiversityDiagnostic] = {}
    franchise_counts: dict[str, int] = {}
    while remaining and len(selected) < settings.output_limit:
        eligible = [
            item for item in remaining
            if not _franchise_limit_reached(item, franchise_counts, settings)
        ] or remaining
        scored = []
        for item in eligible:
            maximum_similarity = max(
                (candidate_similarity(item, chosen) for chosen in selected),
                default=0.0,
            )
            selection_score = (
                settings.relevance_weight * item.score
                - settings.diversity_weight * maximum_similarity
            )
            scored.append((selection_score, item.score, item.candidate.item_key, maximum_similarity, item))
        selection_score, _, _, maximum_similarity, chosen = min(
            scored, key=lambda value: (-value[0], -value[1], value[2])
        )
        selected.append(chosen)
        remaining.remove(chosen)
        franchise = _franchise(chosen)
        if franchise:
            franchise_counts[franchise] = franchise_counts.get(franchise, 0) + 1
        diagnostics[chosen.candidate.item_key] = DiversityDiagnostic(
            selection_score, maximum_similarity, len(selected)
        )
    return DiversityResult(tuple(selected), diagnostics, settings.version)


def candidate_similarity(left: RankedCandidate, right: RankedCandidate) -> float:
    a, b = left.candidate.metadata, right.candidate.metadata
    components: list[tuple[float, float]] = []
    _add(components, 0.20, _jaccard(a.get("genreIds"), b.get("genreIds")))
    franchise_a, franchise_b = _franchise(left), _franchise(right)
    if franchise_a and franchise_b:
        _add(components, 0.20, float(franchise_a == franchise_b))
    _add(components, 0.10, _jaccard(a.get("directors"), b.get("directors")))
    _add(components, 0.10, _jaccard((a.get("cast") or [])[:5], (b.get("cast") or [])[:5]))
    _add(components, 0.08, _same_release_period(a.get("releaseYear"), b.get("releaseYear")))
    if a.get("originalLanguage") and b.get("originalLanguage"):
        _add(components, 0.07, float(a["originalLanguage"] == b["originalLanguage"]))
    _add(components, 0.05, _same_popularity_band(a.get("popularity"), b.get("popularity")))
    cosine = _cosine(a.get("embedding"), b.get("embedding"))
    if cosine is not None:
        _add(components, 0.20, max(0.0, cosine))
    total = sum(weight for weight, _ in components)
    return sum(weight * value for weight, value in components) / total if total else 0.0


def _franchise_limit_reached(item, counts, settings) -> bool:
    franchise = _franchise(item)
    return bool(franchise and counts.get(franchise, 0) >= settings.maximum_same_franchise)


def _franchise(item: RankedCandidate) -> str:
    metadata = item.candidate.metadata
    explicit = metadata.get("collectionId") or metadata.get("franchise")
    if explicit:
        return str(explicit).casefold()
    title = str(metadata.get("title") or "").casefold()
    tokens = [token for token in re.findall(r"[a-z]+", title) if token not in {"the", "a", "an", "part", "chapter"}]
    return " ".join(tokens[:2]) if len(tokens) >= 2 else ""


def _jaccard(left, right) -> float | None:
    a, b = {str(v).casefold() for v in left or []}, {str(v).casefold() for v in right or []}
    return len(a & b) / len(a | b) if a and b else None


def _same_release_period(left, right) -> float | None:
    return float(int(left) // 10 == int(right) // 10) if isinstance(left, int) and isinstance(right, int) else None


def _same_popularity_band(left, right) -> float | None:
    try:
        return float(int(math.log10(max(0.0, float(left)) + 1)) == int(math.log10(max(0.0, float(right)) + 1)))
    except (TypeError, ValueError):
        return None


def _cosine(left: Any, right: Any) -> float | None:
    if not isinstance(left, Sequence) or not isinstance(right, Sequence) or len(left) != len(right) or not left:
        return None
    try:
        a, b = [float(v) for v in left], [float(v) for v in right]
        denominator = math.sqrt(sum(v * v for v in a) * sum(v * v for v in b))
        value = sum(x * y for x, y in zip(a, b)) / denominator
        return value if denominator > 0 and math.isfinite(value) else None
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _add(values, weight, value) -> None:
    if value is not None:
        values.append((weight, min(1.0, max(0.0, value))))
