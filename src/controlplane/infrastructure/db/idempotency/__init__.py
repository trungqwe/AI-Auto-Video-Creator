"""P2 idempotency database adapter structural exports."""

from .postgres_repository import PostgresIdempotencyRepository

__all__ = ["PostgresIdempotencyRepository"]
