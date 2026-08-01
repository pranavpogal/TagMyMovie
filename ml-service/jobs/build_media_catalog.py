from __future__ import annotations

import json
import logging
from dotenv import load_dotenv

from app.catalogue.pipeline import CataloguePipeline
from app.catalogue.repository import MediaCatalogRepository
from app.catalogue.tmdb_client import TmdbClient
from app.config import ConfigurationError, Settings
from app.database import (
    create_mongo_client,
    ensure_media_catalog_indexes,
    get_media_catalog_collection,
)
from app.logging_config import configure_logging


LOGGER = logging.getLogger(__name__)


def main() -> int:
    load_dotenv()
    configure_logging()
    client = None
    try:
        settings = Settings.from_env()
        client = create_mongo_client(settings.mongodb_url)
        client.admin.command("ping")
        collection = get_media_catalog_collection(client, settings.mongodb_database)
        ensure_media_catalog_indexes(collection)

        tmdb = TmdbClient(
            base_url=settings.tmdb_base_url,
            api_key=settings.tmdb_api_key,
            access_token=settings.tmdb_access_token,
            timeout_seconds=settings.request_timeout_seconds,
            max_retries=settings.max_retries,
            retry_backoff_seconds=settings.retry_backoff_seconds,
            requests_per_second=settings.requests_per_second,
        )
        summary = CataloguePipeline(
            settings, tmdb, MediaCatalogRepository(collection)
        ).run()
        print(json.dumps(summary.as_dict(), indent=2))
        return 0
    except ConfigurationError as error:
        LOGGER.error("catalogue configuration invalid", extra={"stage": "configuration"})
        print(str(error))
        return 2
    except Exception as error:  # boundary: log no credentials or request payloads
        LOGGER.error(
            "catalogue pipeline failed",
            extra={"stage": "pipeline", "count_failed": 1},
        )
        print(f"{error.__class__.__name__}: catalogue pipeline failed")
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
