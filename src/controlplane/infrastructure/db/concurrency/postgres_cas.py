"""Structural P2 PostgreSQL CAS adapter; no behavior exists during RED."""


class PostgresRevisionedMutationAdapter:
    def __init__(self, connection: object) -> None:
        self._connection = connection

    def mutate(self, **_: object) -> object:
        raise NotImplementedError("P2 PostgreSQL CAS behavior is not implemented during RED.")
