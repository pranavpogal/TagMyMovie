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
    versions_directory = artifact_directory / "versions"
    versions_directory.mkdir(parents=True, exist_ok=True)
    candidate = Path(
        tempfile.mkdtemp(prefix=".candidate-", dir=versions_directory)
    )
    version_directory = versions_directory / version_name
    temporary_link = artifact_directory / f".current-{uuid.uuid4().hex}"
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
        temporary_link.symlink_to(Path("versions") / version_name)
        os.replace(temporary_link, artifact_directory / "current")
        return version_directory
    except Exception:
        shutil.rmtree(candidate, ignore_errors=True)
        raise
    finally:
        temporary_link.unlink(missing_ok=True)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")
