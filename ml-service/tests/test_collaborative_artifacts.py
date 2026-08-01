from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from scipy.sparse import load_npz

from app.collaborative.artifacts import persist_collaborative_dataset
from app.collaborative.matrix_builder import build_interaction_matrix
from app.config import CollaborativeDatasetSettings


def test_persists_matrix_stable_bidirectional_mappings_and_activation_manifest(
    tmp_path: Path,
) -> None:
    settings = CollaborativeDatasetSettings(
        "mongodb://example", "db", tmp_path, "matrix-v1", 1, 2, 10, 1
    )
    dataset = build_interaction_matrix(
        [
            {
                "user": "user",
                "mediaId": "1",
                "mediaType": "movie",
                "eventType": "favourite_add",
                "value": 1,
                "createdAt": datetime(2026, 8, 1, tzinfo=timezone.utc),
            }
        ],
        valid_user_ids={"user"},
        valid_item_keys={"movie:1"},
        settings=settings,
    )

    paths = persist_collaborative_dataset(dataset, tmp_path)
    manifest = json.loads(Path(paths["manifest"]).read_text(encoding="utf-8"))
    mappings = json.loads(Path(paths["mappings"]).read_text(encoding="utf-8"))
    matrix = load_npz(paths["matrix"])

    assert manifest["matrixVersion"] == "matrix-v1"
    assert manifest["confidenceVersion"] == "implicit-confidence-v1"
    assert manifest["shape"] == [1, 1]
    assert mappings == {
        "users": ["user"],
        "items": ["movie:1"],
        "userToIndex": {"user": 0},
        "itemToIndex": {"movie:1": 0},
    }
    assert matrix.toarray().tolist() == [[4.0]]
