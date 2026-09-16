"""Server-owned bootstrap capabilities and hashed HTTP sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from threading import Lock
from typing import Any, Callable, Protocol
import uuid


class SessionRepositoryPort(Protocol):
    def create(self, *, session_id: str, workspace_id: str, actor_id: str,
               token_hash: bytes, expires_at: datetime) -> None: ...
    def resolve(self, *, token_hash: bytes) -> dict[str, str] | None: ...


@dataclass(frozen=True)
class BootstrapBinding:
    workspace_id: str
    actor_id: str
    expires_at: datetime


class BootstrapCapabilityRegistry:
    """A local-launch channel issues server-bound, one-time short-lived capabilities."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._pending: dict[bytes, BootstrapBinding] = {}

    def issue(self, *, workspace_id: str, actor_id: str,
              ttl_seconds: int = 60) -> str:
        if not 1 <= ttl_seconds <= 60:
            raise ValueError("bootstrap TTL must be within 1..60 seconds")
        capability = secrets.token_urlsafe(32)
        digest = hashlib.sha256(capability.encode("ascii")).digest()
        binding = BootstrapBinding(
            workspace_id, actor_id,
            datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
        )
        with self._lock:
            self._pending[digest] = binding
        return capability

    def consume(self, capability: str) -> BootstrapBinding:
        digest = hashlib.sha256(capability.encode("utf-8")).digest()
        with self._lock:
            binding = self._pending.pop(digest, None)
        if binding is None or binding.expires_at <= datetime.now(timezone.utc):
            raise PermissionError("invalid or expired bootstrap capability")
        return binding


class SessionSecurityService:
    def __init__(self, repository_factory: Callable[[Any], SessionRepositoryPort]) -> None:
        self._repository_factory = repository_factory

    def create(self, *, connection: Any, binding: BootstrapBinding,
               lifetime: timedelta = timedelta(hours=8)) -> tuple[str, str]:
        token = secrets.token_urlsafe(32)
        session_id = str(uuid.uuid4())
        self._repository_factory(connection).create(
            session_id=session_id, workspace_id=binding.workspace_id,
            actor_id=binding.actor_id,
            token_hash=hashlib.sha256(token.encode("ascii")).digest(),
            expires_at=datetime.now(timezone.utc) + lifetime,
        )
        return session_id, token

    def resolve(self, *, connection: Any, token: str) -> dict[str, str]:
        if not token:
            raise PermissionError("session required")
        identity = self._repository_factory(connection).resolve(
            token_hash=hashlib.sha256(token.encode("utf-8")).digest(),
        )
        if identity is None:
            raise PermissionError("invalid or expired session")
        return identity
