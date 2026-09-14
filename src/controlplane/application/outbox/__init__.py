"""Structural P3 outbox seams; no P3 behavior is authorized yet."""


class OutboxWriter:
    def enqueue(self, **_: object) -> object:
        raise NotImplementedError("P3 outbox writer is not implemented during Behavioral RED")


class OutboxPublisher:
    def dispatch(self, **_: object) -> object:
        raise NotImplementedError("P3 outbox publisher is not implemented during Behavioral RED")


__all__ = ["OutboxPublisher", "OutboxWriter"]
