"""PostgreSQL adapter of E: OutputRepository for the kinds declared by the port and the voice/media unit of work."""

from __future__ import annotations

from voice.persistence.errors import (
    TransactionAlreadyActiveError,
    TransactionNotActiveError,
    UnsupportedKindError,
    WorkspaceNotBoundError,
)
from voice.persistence.outbox import PostgresVoiceOutboxWriter
from voice.persistence.output_repository import PostgresOutputRepository
from voice.persistence.unit_of_work import PostgresVoiceUnitOfWork

__all__ = [
    'PostgresOutputRepository',
    'PostgresVoiceOutboxWriter',
    'PostgresVoiceUnitOfWork',
    'TransactionAlreadyActiveError',
    'TransactionNotActiveError',
    'UnsupportedKindError',
    'WorkspaceNotBoundError',
]
