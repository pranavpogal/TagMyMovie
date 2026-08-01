from __future__ import annotations

import json
import logging
from datetime import datetime

from dotenv import load_dotenv

from app.collaborative.dataset_repository import CollaborativeDatasetRepository
from app.collaborative.matrix_builder import build_interaction_matrix
from app.collaborative.training import TrainingValidationError, train_and_promote
from app.config import (
    CollaborativeDatasetSettings,
    CollaborativeModelSettings,
    ConfigurationError,
)
from app.database import create_mongo_client
from app.logging_config import configure_logging


LOGGER = logging.getLogger(__name__)


def main() -> int:
    load_dotenv()
    configure_logging()
    client = None
    try:
        dataset_settings = CollaborativeDatasetSettings.from_env()
        model_settings = CollaborativeModelSettings.from_env()
        client = create_mongo_client(dataset_settings.mongodb_url)
        client.admin.command("ping")
        repository = CollaborativeDatasetRepository(
            client[dataset_settings.mongodb_database]
        )
        interactions = list(repository.iter_interactions())
        timestamps = [
            interaction["createdAt"]
            for interaction in interactions
            if isinstance(interaction.get("createdAt"), datetime)
        ]
        dataset = build_interaction_matrix(
            interactions,
            valid_user_ids=repository.valid_user_ids(),
            valid_item_keys=repository.valid_item_keys(),
            settings=dataset_settings,
        )
        result = train_and_promote(
            dataset,
            model_settings,
            data_start=min(timestamps) if timestamps else None,
            data_end=max(timestamps) if timestamps else None,
        )
        print(
            json.dumps(
                {
                    "promoted": True,
                    "versionDirectory": str(result.version_directory),
                    "metrics": result.metrics.as_dict(),
                    "dataset": dataset.summary.as_dict(),
                },
                indent=2,
            )
        )
        return 0
    except ConfigurationError as error:
        LOGGER.error("ALS configuration invalid", extra={"stage": "configuration"})
        print(str(error))
        return 2
    except TrainingValidationError as error:
        LOGGER.warning("ALS candidate not promoted", extra={"stage": "validation"})
        print(f"candidate not promoted: {error}")
        return 3
    except Exception as error:  # boundary: do not expose user data or credentials
        LOGGER.error("ALS training failed", extra={"stage": "training"})
        print(f"{error.__class__.__name__}: ALS training failed")
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
