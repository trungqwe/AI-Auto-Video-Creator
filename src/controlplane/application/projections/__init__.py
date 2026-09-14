"""Structural P3 projection seams; no P3 behavior is authorized yet."""


class EventConsumer:
    def process(self, **_: object) -> object:
        raise NotImplementedError("P3 event consumer is not implemented during Behavioral RED")


class OperationStreamProjector:
    def append(self, **_: object) -> object:
        raise NotImplementedError("P3 operation stream projector is not implemented during Behavioral RED")


__all__ = ["EventConsumer", "OperationStreamProjector"]
