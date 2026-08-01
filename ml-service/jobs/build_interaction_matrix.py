from __future__ import annotations

import json
import logging

from dotenv import load_dotenv

from app.collaborative.artifacts import persist_collaborative_dataset
from app.collaborative.dataset_repository import CollaborativeDatasetRepository
from app.collaborative.matrix_builder import build_interaction_matrix
from app.config import CollaborativeDatasetSettings, ConfigurationError
from app.database import create_mongo_client
from app.logging_config import configure_logging


LOGGER = logging.getLogger(__name__)


def main() -> int:
    load_dotenv()
    configure_logging()
    client = None
    try:
        settings = CollaborativeDatasetSettings.from_env()
        client = create_mongo_client(settings.mongodb_url)
        client.admin.command("ping")
        repository = CollaborativeDatasetRepository(
            client[settings.mongodb_database]
        )
        dataset = build_interaction_matrix(
            repository.iter_interactions(),
            valid_user_ids=repository.valid_user_ids(),
            valid_item_keys=repository.valid_item_keys(),
            settings=settings,
        )
        artifacts = persist_collaborative_dataset(
            dataset, settings.artifact_directory
        )
        output = {**dataset.summary.as_dict(), "artifacts": artifacts}
        print(json.dumps(output, indent=2))
        return 0
    except ConfigurationError as error:
        LOGGER.error("matrix configuration invalid", extra={"stage": "configuration"})
        print(str(error))
        return 2
    except Exception as error:  # boundary: do not expose data or credentials
        LOGGER.error("interaction matrix build failed", extra={"stage": "pipeline"})
        print(f"{error.__class__.__name__}: interaction matrix build failed")
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
