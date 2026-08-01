from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from app.catalogue.normalizer import CatalogueNormalizationError, normalize_tmdb_media
from app.catalogue.repository import MediaCatalogRepository, UpsertCounts
from app.catalogue.tmdb_client import TMDB_SOURCES, TmdbClient, TmdbRequestError
from app.config import Settings


LOGGER = logging.getLogger(__name__)


@dataclass
class CatalogueSummary:
    discovered: int = 0
    fetched: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    failed: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


class CataloguePipeline:
    def __init__(
        self,
        settings: Settings,
        tmdb: TmdbClient,
        repository: MediaCatalogRepository,
    ) -> None:
        self.settings = settings
        self.tmdb = tmdb
        self.repository = repository

    def run(self) -> CatalogueSummary:
        summary = CatalogueSummary()
        seen: set[str] = set()
        pending: list[dict] = []
        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=self.settings.incremental_max_age_hours
        )

        for source in TMDB_SOURCES:
            page_count = (
                self.settings.movie_pages
                if source.media_type == "movie"
                else self.settings.tv_pages
            )
            for page in range(1, page_count + 1):
                try:
                    listed = self.tmdb.list_page(source, page)
                except TmdbRequestError as error:
                    summary.failed += 1
                    LOGGER.warning(
                        "catalogue list page failed",
                        extra={
                            "stage": "list",
                            "media_type": source.media_type,
                            "source": source.name,
                            "page": page,
                            "count_failed": summary.failed,
                        },
                    )
                    continue

                candidates: list[tuple[str, str]] = []
                for item in listed:
                    tmdb_id = str(item.get("id") or "").strip()
                    key = f"{source.media_type}:{tmdb_id}"
                    if tmdb_id.isdigit() and key not in seen:
                        seen.add(key)
                        candidates.append((source.media_type, tmdb_id))
                summary.discovered += len(candidates)

                existing = self.repository.get_existing(candidates)
                for media_type, tmdb_id in candidates:
                    key = f"{media_type}:{tmdb_id}"
                    current = existing.get(key)
                    if (
                        self.settings.sync_mode == "incremental"
                        and current
                        and self.repository.is_recent(current, cutoff)
                    ):
                        summary.unchanged += 1
                        continue

                    try:
                        detail = self.tmdb.media_detail(media_type, tmdb_id)
                        record = normalize_tmdb_media(
                            detail,
                            media_type,
                            cast_limit=self.settings.cast_limit,
                            keyword_limit=self.settings.keyword_limit,
                        )
                        pending.append(record)
                        summary.fetched += 1
                    except (TmdbRequestError, CatalogueNormalizationError, TypeError, ValueError):
                        summary.failed += 1
                        LOGGER.warning(
                            "catalogue title failed",
                            extra={
                                "stage": "detail",
                                "media_type": media_type,
                                "tmdb_id": tmdb_id,
                                "count_failed": summary.failed,
                            },
                        )

                    if len(pending) >= self.settings.batch_size:
                        self._flush(pending, summary)
                        pending.clear()

        if pending:
            self._flush(pending, summary)

        LOGGER.info(
            "catalogue sync complete",
            extra={
                "stage": "complete",
                **{
                    f"count_{field}": value
                    for field, value in summary.as_dict().items()
                },
            },
        )
        return summary

    def _flush(self, records: list[dict], summary: CatalogueSummary) -> None:
        counts: UpsertCounts = self.repository.upsert_batch(records)
        summary.created += counts.created
        summary.updated += counts.updated
        summary.unchanged += counts.unchanged
