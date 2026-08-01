from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class MatrixMappings:
    users: tuple[str, ...]
    items: tuple[str, ...]

    @classmethod
    def stable(
        cls, user_ids: Iterable[str], item_keys: Iterable[str]
    ) -> "MatrixMappings":
        return cls(
            users=tuple(sorted(set(user_ids))),
            items=tuple(sorted(set(item_keys))),
        )

    @property
    def user_to_index(self) -> dict[str, int]:
        return {user_id: index for index, user_id in enumerate(self.users)}

    @property
    def item_to_index(self) -> dict[str, int]:
        return {item_key: index for index, item_key in enumerate(self.items)}

    def as_dict(self) -> dict[str, object]:
        return {
            "users": list(self.users),
            "items": list(self.items),
            "userToIndex": self.user_to_index,
            "itemToIndex": self.item_to_index,
        }
