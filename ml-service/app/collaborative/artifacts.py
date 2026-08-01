from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from scipy.sparse import save_npz

from app.collaborative.matrix_builder import CollaborativeDataset


def persist_collaborative_dataset(
    dataset: CollaborativeDataset, artifact_directory: Path
) -> dict[str, str]:
    artifact_directory.mkdir(parents=True, exist_ok=True)
    generation = uuid.uuid4().hex
    matrix_name = f"interaction-matrix-{generation}.npz"
    mappings_name = f"mappings-{generation}.json"
    matrix_path = artifact_directory / matrix_name
    mappings_path = artifact_directory / mappings_name
    manifest_path = artifact_directory / "dataset-manifest.json"
    temporary_matrix = artifact_directory / f".{matrix_name}.tmp.npz"
    temporary_mappings = artifact_directory / f".{mappings_name}.tmp"
    temporary_manifest = artifact_directory / ".dataset-manifest.tmp"
    try:
        save_npz(temporary_matrix, dataset.matrix, compressed=True)
        temporary_mappings.write_text(
            json.dumps(dataset.mappings.as_dict(), indent=2), encoding="utf-8"
        )
        manifest = {
            "generation": generation,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "matrixVersion": dataset.matrix_version,
            "confidenceVersion": dataset.confidence_version,
            "matrix": matrix_name,
            "mappings": mappings_name,
            "shape": list(dataset.matrix.shape),
            "nonzero": dataset.matrix.nnz,
            "summary": dataset.summary.as_dict(),
        }
        temporary_manifest.write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        os.replace(temporary_matrix, matrix_path)
        os.replace(temporary_mappings, mappings_path)
        os.replace(temporary_manifest, manifest_path)
        return {
            "manifest": str(manifest_path),
            "matrix": str(matrix_path),
            "mappings": str(mappings_path),
        }
    finally:
        temporary_matrix.unlink(missing_ok=True)
        temporary_mappings.unlink(missing_ok=True)
        temporary_manifest.unlink(missing_ok=True)
