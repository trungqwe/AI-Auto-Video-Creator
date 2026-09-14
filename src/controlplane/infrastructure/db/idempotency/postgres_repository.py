"""Structural P2 repository port; persistence behavior is intentionally absent during RED."""


class PostgresIdempotencyRepository:
    """Repository constructed from the active SqlUnitOfWork connection."""

    def __init__(self, connection: object) -> None:
        self._connection = connection

    def create_receipt(self, **_: object) -> object:
        raise NotImplementedError("P2 idempotency persistence is not implemented during RED.")

    def get_record(self, **_: object) -> object:
        raise NotImplementedError("P2 idempotency persistence is not implemented during RED.")

    def create_record(self, **_: object) -> object:
        raise NotImplementedError("P2 idempotency persistence is not implemented during RED.")
