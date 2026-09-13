"""P2 revision port stub; no PostgreSQL CAS exists during RED."""


class RevisionedMutationPort:
    def mutate(self, **_: object) -> object:
        raise NotImplementedError("P2 revision CAS behavior is not implemented during RED.")
