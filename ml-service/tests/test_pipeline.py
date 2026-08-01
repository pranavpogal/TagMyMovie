from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from app.catalogue.pipeline import CataloguePipeline
from app.catalogue.repository import UpsertCounts
from app.config import Settings


def settings(**overrides) -> Settings:
    value = Settings(
        mongodb_url="mongodb://localhost/tagmymovie",
        mongodb_database="tagmymovie",
        tmdb_base_url="https://api.themoviedb.org/3/",
        tmdb_api_key="key",
        tmdb_access_token=None,
        movie_pages=1,
        tv_pages=1,
        sync_mode="full",
        incremental_max_age_hours=24,
        request_timeout_seconds=10,
        max_retries=1,
        retry_backoff_seconds=0,
        requests_per_second=100,
        batch_size=10,
        cast_limit=10,
        keyword_limit=10,
    )
    return replace(value, **overrides)


class FakeTmdb:
    def __init__(self) -> None:
        self.details = []

    def list_page(self, source, page):
        identifier = 603 if source.media_type == "movie" else 1396
        return [{"id": identifier}, {"id": identifier}]

    def media_detail(self, media_type, tmdb_id):
        self.details.append((media_type, tmdb_id))
        if media_type == "movie":
            return {"id": int(tmdb_id), "title": "The Matrix"}
        return {"id": int(tmdb_id), "name": "Breaking Bad"}


class FakeRepository:
    def __init__(self, existing=None) -> None:
        self.existing = existing or {}
        self.batches = []

    @staticmethod
    def is_recent(document, cutoff):
        return document["lastSyncedAt"] >= cutoff

    def get_existing(self, keys):
        return {
            f"{media_type}:{tmdb_id}": self.existing[f"{media_type}:{tmdb_id}"]
            for media_type, tmdb_id in keys
            if f"{media_type}:{tmdb_id}" in self.existing
        }

    def upsert_batch(self, records):
        self.batches.append(records)
        return UpsertCounts(created=len(records))


def test_full_pipeline_fetches_each_compound_title_once_across_sources() -> None:
    tmdb = FakeTmdb()
    repository = FakeRepository()

    summary = CataloguePipeline(settings(), tmdb, repository).run()

    assert sorted(tmdb.details) == [("movie", "603"), ("tv", "1396")]
    assert summary.discovered == 2
    assert summary.fetched == 2
    assert summary.created == 2
    assert summary.failed == 0


def test_incremental_pipeline_skips_recent_documents() -> None:
    tmdb = FakeTmdb()
    recent = datetime.now(timezone.utc)
    repository = FakeRepository(
        {
            "movie:603": {"lastSyncedAt": recent},
            "tv:1396": {"lastSyncedAt": recent},
        }
    )

    summary = CataloguePipeline(
        settings(sync_mode="incremental"), tmdb, repository
    ).run()

    assert tmdb.details == []
    assert summary.unchanged == 2
    assert repository.batches == []
