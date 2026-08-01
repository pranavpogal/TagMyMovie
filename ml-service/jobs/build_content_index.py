from __future__ import annotations

import json
import logging

from dotenv import load_dotenv

from app.config import ConfigurationError, EmbeddingSettings
from app.content.embedding_pipeline import ContentEmbeddingPipeline
from app.content.embedding_repository import EmbeddingRepository
from app.content.embeddings import SentenceTransformerEmbedder
from app.database import create_mongo_client, get_media_catalog_collection
from app.logging_config import configure_logging


LOGGER = logging.getLogger(__name__)


def main() -> int:
    load_dotenv()
    configure_logging()
    client = None
    try:
        settings = EmbeddingSettings.from_env()
        client = create_mongo_client(settings.mongodb_url)
        client.admin.command("ping")
        collection = get_media_catalog_collection(client, settings.mongodb_database)
        pipeline = ContentEmbeddingPipeline(
            settings,
            EmbeddingRepository(collection),
            SentenceTransformerEmbedder(settings.model_name),
        )
        print(json.dumps(pipeline.run().as_dict(), indent=2))
        return 0
    except ConfigurationError as error:
        LOGGER.error("embedding configuration invalid", extra={"stage": "configuration"})
        print(str(error))
        return 2
    except Exception as error:  # boundary: do not expose database URLs or model internals
        LOGGER.error("content embedding pipeline failed", extra={"stage": "pipeline"})
        print(f"{error.__class__.__name__}: content embedding pipeline failed")
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
