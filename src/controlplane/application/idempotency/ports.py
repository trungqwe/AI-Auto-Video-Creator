"""P2 idempotency port stub; no persistence behavior exists during RED."""


class IdempotencyCoordinator:
    def __init__(self, uow_factory: object, repository_factory: object) -> None:
        self._uow_factory = uow_factory
        self._repository_factory = repository_factory

    def submit(self, **_: object) -> object:
        raise NotImplementedError("P2 idempotency behavior is not implemented during RED.")
