from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.collaborative.model import load_als_model, validate_factor_shapes


class CollaborativeArtifactError(RuntimeError):
    """Raised when the active ALS artifact set is absent or inconsistent."""


@dataclass(frozen=True)
class LoadedCollaborativeModel:
    model: Any
    user_ids: tuple[str, ...]
    item_keys: tuple[str, ...]
    metadata: dict[str, Any]
    directory: Path

    @property
    def user_to_index(self) -> dict[str, int]:
        return {user_id: index for index, user_id in enumerate(self.user_ids)}

    @property
    def item_to_index(self) -> dict[str, int]:
        return {item_key: index for index, item_key in enumerate(self.item_keys)}


def load_current_model(artifact_directory: Path) -> LoadedCollaborativeModel:
    current = artifact_directory / "current"
    try:
        resolved = current.resolve(strict=True)
    except OSError as error:
        raise CollaborativeArtifactError("active collaborative artifacts are missing") from error
    return _load_version(resolved)


@lru_cache(maxsize=4)
def _load_version(current: Path) -> LoadedCollaborativeModel:
    required = {
        "model": current / "model.npz",
        "users": current / "user_mapping.json",
        "items": current / "item_mapping.json",
        "metadata": current / "model_metadata.json",
    }
    if any(not path.is_file() for path in required.values()):
        raise CollaborativeArtifactError("active collaborative artifacts are missing")
    try:
        users_payload = _read_json(required["users"])
        items_payload = _read_json(required["items"])
        metadata = _read_json(required["metadata"])
        users = tuple(str(value) for value in users_payload["ids"])
        items = tuple(str(value) for value in items_payload["keys"])
        _validate_mapping(users, users_payload.get("idToIndex"), "user")
        _validate_mapping(items, items_payload.get("keyToIndex"), "item")
        model = load_als_model(required["model"])
        validate_factor_shapes(model, len(users), len(items))
    except CollaborativeArtifactError:
        raise
    except Exception as error:
        raise CollaborativeArtifactError(
            "active collaborative artifacts are invalid"
        ) from error
    return LoadedCollaborativeModel(model, users, items, metadata, current)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("artifact JSON must contain an object")
    return value


def _validate_mapping(
    values: tuple[str, ...], stored: Any, label: str
) -> None:
    expected = {value: index for index, value in enumerate(values)}
    if len(set(values)) != len(values) or stored != expected:
        raise CollaborativeArtifactError(f"{label} mapping is inconsistent")
