"""Credential Broker and Secret Lifetime Management (INV-015 / CT-SEC-002).

Enforces strictly scoped secret access, automated expiration, and zero memory retention.
"""
from __future__ import annotations

from typing import Dict, Optional, Generator
from contextlib import contextmanager
from src.controlplane.security.dpapi import dpapi_decrypt


class SecretError(Exception):
    """Base exception for secret management."""
    pass


class SecretNotFoundError(SecretError):
    """Raised when requested secret alias is not registered."""
    pass


class SecretLifetimeExpiredError(SecretError):
    """Raised when secret handle is accessed outside its valid lifecycle."""
    pass


class UnauthorizedSecretAccessError(SecretError):
    """Raised when access to secret is unauthorized."""
    pass


class ScopedSecretHandle:
    """Temporary handle to a secret that strictly expires upon scope exit."""

    def __init__(self, alias: str, raw_secret: str) -> None:
        self.alias = alias
        self._raw_secret = raw_secret
        self._expired = False

    def is_expired(self) -> bool:
        """Returns True if the handle's lifecycle has ended."""
        return self._expired

    def get_secret_value(self) -> str:
        """Retrieves raw secret value; fails if handle is expired.

        Raises:
            SecretLifetimeExpiredError: If handle has expired.
        """
        if self._expired:
            raise SecretLifetimeExpiredError(f"Secret handle for '{self.alias}' has expired")
        return self._raw_secret

    def _expire(self) -> None:
        """Internal teardown to invalidate handle and purge raw secret from memory."""
        self._expired = True
        self._raw_secret = ""


class CredentialBroker:
    """Broker controlling secret access, decryption from vault, and lifecycle scoping."""

    def __init__(self, vault: Optional[Dict[str, bytes]] = None) -> None:
        self.vault: Dict[str, bytes] = vault or {}

    @contextmanager
    def acquire_secret(self, alias: str) -> Generator[ScopedSecretHandle, None, None]:
        """Acquires a scoped secret handle with automatic lifetime management.

        Args:
            alias: The registered key alias to look up in vault.

        Yields:
            ScopedSecretHandle: Scoped handle to decrypt credential.

        Raises:
            UnauthorizedSecretAccessError: If alias is missing from vault.
        """
        if alias not in self.vault:
            raise UnauthorizedSecretAccessError(
                f"Access denied: alias '{alias}' is not authorized or not present in vault"
            )

        encrypted_secret = self.vault[alias]
        decrypted_bytes = dpapi_decrypt(encrypted_secret)
        handle = ScopedSecretHandle(alias=alias, raw_secret=decrypted_bytes.decode("utf-8"))

        try:
            yield handle
        finally:
            handle._expire()
