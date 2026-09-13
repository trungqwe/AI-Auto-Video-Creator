"""P2 idempotency port stub; no persistence behavior exists during RED."""


class IdempotencyCoordinator:
    def submit(self, **_: object) -> object:
        raise NotImplementedError("P2 idempotency behavior is not implemented during RED.")
