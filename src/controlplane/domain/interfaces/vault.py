"""Secret Vault interface definition (ADR-0008, ADR-0009).

Pure domain abstraction for secret reference retrieval.
Secrets are never passed in cleartext across boundaries; domain only works with SecretHandles.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class ISecretVault(ABC):
    """Interface for secret retrieval from encrypted persistent storage."""

    @abstractmethod
    def retrieve_secret(self, secret_handle: str) -> str:
        """Retrieve cleartext secret value for the given handle within secure execution context."""
        raise NotImplementedError("retrieve_secret must be implemented by concrete secure vault.")
