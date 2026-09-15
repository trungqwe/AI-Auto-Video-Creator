"""Structural P5A ports; all behavioral entrypoints remain RED-gated."""
from __future__ import annotations

from typing import Any


class ConfigRevisionService:
    def create_revision(self, **kwargs: Any) -> object:
        raise NotImplementedError("P5A ConfigRevision behavior is not implemented")

    def transition(self, **kwargs: Any) -> object:
        raise NotImplementedError("P5A ConfigRevision behavior is not implemented")


class ConfigRevisionRepository:
    def get_scoped(self, **kwargs: Any) -> object:
        raise NotImplementedError("P5A scoped configuration repository is not implemented")

    def publish(self, **kwargs: Any) -> object:
        raise NotImplementedError("P5A publish CAS is not implemented")


class SecretHandleStore:
    def register(self, **kwargs: Any) -> object:
        raise NotImplementedError("P5A secret-handle boundary is not implemented")


class ConfigEventFactory:
    def publish_event(self, **kwargs: Any) -> object:
        raise NotImplementedError("P5A config event/audit construction is not implemented")

    def invalidation_event(self, **kwargs: Any) -> object:
        raise NotImplementedError("P5A config event/audit construction is not implemented")


__all__ = [
    "ConfigEventFactory",
    "ConfigRevisionRepository",
    "ConfigRevisionService",
    "SecretHandleStore",
]
