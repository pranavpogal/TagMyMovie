from __future__ import annotations

from datetime import datetime

from app.config import ProfileSettings
from app.content.profile import ContentProfile, build_content_profile
from app.content.profile_repository import ContentProfileRepository


class UserContentProfileBuilder:
    def __init__(
        self,
        repository: ContentProfileRepository,
        settings: ProfileSettings,
        *,
        embedding_model: str,
        embedding_version: str,
    ) -> None:
        self.repository = repository
        self.settings = settings
        self.embedding_model = embedding_model
        self.embedding_version = embedding_version

    def build(self, user_id: str, *, now: datetime | None = None) -> ContentProfile:
        inputs = self.repository.load(
            user_id,
            embedding_model=self.embedding_model,
            embedding_version=self.embedding_version,
        )
        return build_content_profile(
            inputs.interactions,
            inputs.embeddings,
            settings=self.settings,
            now=now,
            onboarding_seed_keys=inputs.onboarding_seed_keys,
        )
