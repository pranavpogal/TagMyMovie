from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from app.collaborative.mappings import MatrixMappings


def promote_model_artifacts(
    *,
    model: Any,
    mappings: MatrixMappings,
    metadata: dict[str, Any],
    evaluation: dict[str, Any],
    artifact_directory: Path,
    version_name: str,
) -> Path:
    version_directory = write_model_version(
        model=model, mappings=mappings, metadata=metadata, evaluation=evaluation,
        artifact_directory=artifact_directory, version_name=version_name,
    )
    activate_model_version(artifact_directory, version_directory)
    return version_directory


def write_model_version(
    *, model: Any, mappings: MatrixMappings, metadata: dict[str, Any],
    evaluation: dict[str, Any], artifact_directory: Path, version_name: str,
) -> Path:
    versions_directory = artifact_directory / "versions"
    versions_directory.mkdir(parents=True, exist_ok=True)
    candidate = Path(
        tempfile.mkdtemp(prefix=".candidate-", dir=versions_directory)
    )
    version_directory = versions_directory / version_name
    try:
        model.save(candidate / "model.npz")
        _write_json(
            candidate / "user_mapping.json",
            {
                "ids": list(mappings.users),
                "idToIndex": mappings.user_to_index,
            },
        )
        _write_json(
            candidate / "item_mapping.json",
            {
                "keys": list(mappings.items),
                "keyToIndex": mappings.item_to_index,
            },
        )
        _write_json(candidate / "model_metadata.json", metadata)
        _write_json(candidate / "evaluation.json", evaluation)
        os.replace(candidate, version_directory)
        return version_directory
    except Exception:
        shutil.rmtree(candidate, ignore_errors=True)
        raise


def activate_model_version(artifact_directory: Path, version_directory: Path) -> None:
    artifact_directory.mkdir(parents=True, exist_ok=True)
    expected_parent = (artifact_directory / "versions").resolve()
    if version_directory.resolve().parent != expected_parent:
        raise ValueError("model version is outside the artifact versions directory")
    temporary_link = artifact_directory / f".current-{uuid.uuid4().hex}"
    try:
        temporary_link.symlink_to(Path("versions") / version_directory.name)
        os.replace(temporary_link, artifact_directory / "current")
    finally:
        temporary_link.unlink(missing_ok=True)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")
