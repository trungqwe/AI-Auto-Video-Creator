"""P2 structural stubs; behavior is intentionally absent before RED review."""


class MessageEnvelope:
    @classmethod
    def create(cls, **_: object) -> "MessageEnvelope":
        raise NotImplementedError("P2 MessageEnvelope behavior is not implemented during RED.")


class ProblemDetail:
    @classmethod
    def create(cls, **_: object) -> "ProblemDetail":
        raise NotImplementedError("P2 ProblemDetail behavior is not implemented during RED.")
