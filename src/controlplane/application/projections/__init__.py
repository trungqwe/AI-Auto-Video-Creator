"""Application seams for P3 projection orchestration."""


class EventConsumer:
    def __init__(self, processor: object) -> None:
        self._processor = processor

    def process(self, **kwargs: object) -> object:
        return self._processor.process(**kwargs)


class OperationStreamProjector:
    def __init__(self, repository: object) -> None:
        self._repository = repository

    def append(self, **kwargs: object) -> object:
        return self._repository.append(**kwargs)


__all__ = ["EventConsumer", "OperationStreamProjector"]
