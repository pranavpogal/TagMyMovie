from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from dotenv import load_dotenv

from app.collaborative.artifacts import persist_collaborative_dataset
from app.collaborative.data_sources import load_collaborative_sources
from app.collaborative.dataset_repository import CollaborativeDatasetRepository
from app.collaborative.matrix_builder import build_interaction_matrix
from app.config import (
    CollaborativeDatasetSettings,
    ConfigurationError,
    MovieLensSettings,
)
from app.database import create_mongo_client
from app.logging_config import configure_logging


LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an opt-in MovieLens collaborative bootstrap dataset."
    )
    parser.add_argument(
        "--dataset-path",
        required=True,
        type=Path,
        help="Local extracted MovieLens directory containing ratings.csv and links.csv",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    configure_logging()
    args = parse_args()
    client = None
    try:
        dataset_settings = CollaborativeDatasetSettings.from_env()
        source_settings = MovieLensSettings("movielens", args.dataset_path.expanduser())
        source_settings.validate()
        client = create_mongo_client(dataset_settings.mongodb_url)
        client.admin.command("ping")
        repository = CollaborativeDatasetRepository(
            client[dataset_settings.mongodb_database]
        )
        sources = load_collaborative_sources(repository, source_settings)
        dataset = build_interaction_matrix(
            sources.interactions,
            valid_user_ids=sources.valid_user_ids,
            valid_item_keys=sources.valid_item_keys,
            settings=dataset_settings,
        )
        artifacts = persist_collaborative_dataset(
            dataset, dataset_settings.artifact_directory
        )
        print(
            json.dumps(
                {
                    "dataSource": "movielens",
                    "externalBootstrap": True,
                    "movielens": sources.movielens.as_dict() if sources.movielens else {},
                    "matrix": dataset.summary.as_dict(),
                    "artifacts": artifacts,
                },
                indent=2,
            )
        )
        return 0
    except ConfigurationError as error:
        LOGGER.error("MovieLens configuration invalid", extra={"stage": "configuration"})
        print(str(error))
        return 2
    except Exception as error:  # boundary: do not expose user data or credentials
        LOGGER.error("MovieLens bootstrap failed", extra={"stage": "bootstrap"})
        print(f"{error.__class__.__name__}: MovieLens bootstrap failed")
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
