"""Importable P5B application seams with no persistence implementation."""
from __future__ import annotations

from typing import Any


class ArtifactVersionStore:
    def register(self, **kwargs: Any) -> object:
        raise NotImplementedError("P5B artifact-version store is not implemented")

    def get_scoped(self, **kwargs: Any) -> object | None:
        raise NotImplementedError("P5B scoped artifact-version repository is not implemented")


class ArtifactLocationStore:
    def declare(self, **kwargs: Any) -> object:
        raise NotImplementedError("P5B artifact-location store is not implemented")

    def get_scoped(self, **kwargs: Any) -> object | None:
        raise NotImplementedError("P5B scoped artifact-location repository is not implemented")

    def transition(self, **kwargs: Any) -> object:
        raise NotImplementedError("P5B artifact-location transition persistence is not implemented")

    def validate_transition(self, **kwargs: Any) -> object:
        raise NotImplementedError("P5B P4-backed artifact-location validator is not implemented")


class CleanupAuthorizationStore:
    def authorize(self, **kwargs: Any) -> object:
        raise NotImplementedError("P5B cleanup-authorization policy/store is not implemented")

    def is_expired(self, **kwargs: Any) -> bool:
        raise NotImplementedError("P5B cleanup-authorization expiry evaluation is not implemented")


__all__ = ["ArtifactLocationStore", "ArtifactVersionStore", "CleanupAuthorizationStore"]
