"""Structural P2 PostgreSQL CAS adapter; no behavior exists during RED."""


class PostgresRevisionedMutationAdapter:
    def __init__(self, uow_factory: object) -> None:
        self._uow_factory = uow_factory

    def mutate(self, **_: object) -> object:
        raise NotImplementedError("P2 PostgreSQL CAS behavior is not implemented during RED.")
