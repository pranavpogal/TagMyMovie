from __future__ import annotations

from pathlib import Path

from scipy.sparse import csr_matrix

from app.collaborative.mappings import MatrixMappings
from app.collaborative.model import create_als_model
from app.collaborative.model_artifacts import promote_model_artifacts
from app.collaborative.model_loader import load_current_model
from app.config import CollaborativeModelSettings


def test_loads_complete_active_model_with_aligned_mappings(tmp_path: Path) -> None:
    settings = CollaborativeModelSettings(
        tmp_path, "als-test", 2, 0.05, 2, 2, 42, 2, 1, 0
    )
    model = create_als_model(settings)
    model.fit(
        csr_matrix([[1, 1, 0], [0, 1, 1]], dtype="float32"),
        show_progress=False,
    )
    promote_model_artifacts(
        model=model,
        mappings=MatrixMappings(
            ("user-a", "user-b"), ("movie:1", "movie:2", "tv:1")
        ),
        metadata={"modelVersion": "als-test"},
        evaluation={"passed": True},
        artifact_directory=tmp_path,
        version_name="als-test-version",
    )

    loaded = load_current_model(tmp_path)

    assert loaded.user_to_index == {"user-a": 0, "user-b": 1}
    assert loaded.item_to_index == {"movie:1": 0, "movie:2": 1, "tv:1": 2}
    assert loaded.metadata["modelVersion"] == "als-test"
    assert loaded.model.user_factors.shape[0] == 2
    assert loaded.model.item_factors.shape[0] == 3
