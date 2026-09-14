"""Application seams for P3 outbox orchestration."""


class OutboxWriter:
    def __init__(self, repository: object) -> None:
        self._repository = repository

    def enqueue(self, *, event: object) -> object:
        return self._repository.enqueue(event)


class OutboxPublisher:
    def __init__(self, repository: object) -> None:
        self._repository = repository

    def dispatch(self, **kwargs: object) -> object:
        return self._repository.dispatch(**kwargs)


__all__ = ["OutboxPublisher", "OutboxWriter"]
