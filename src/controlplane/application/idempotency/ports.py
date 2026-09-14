"""P2 idempotency port stub; no persistence behavior exists during RED."""


class IdempotencyCoordinator:
    def __init__(self, uow_factory: object, repository_factory: object) -> None:
        self._uow_factory = uow_factory
        self._repository_factory = repository_factory

    def submit(self, **_: object) -> object:
        from .canonicalization import request_hash

        logical = {
            "workspace_id": _["workspace_id"],
            "command_name": _["command_name"],
            "payload": _["payload"],
        }
        for field in ("expected_revision", "policy_revision_id"):
            if field in _:
                logical[field] = _[field]
        digest=request_hash(logical)
        with self._uow_factory() as uow:
            repo=self._repository_factory(uow.connection)
            uow.connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",(f'{_["workspace_id"]}:{_["command_name"]}:{_["idempotency_key"]}',))
            record=repo.get_record(**_)
            if record:
                if record[0]!=digest: raise ValueError("IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD")
                row=uow.connection.execute("SELECT receipt_id,command_id FROM controlplane.cp_command_receipts WHERE receipt_id=%s",(record[1],)).fetchone()
                return {"receipt_id":row[0],"command_id":row[1],"disposition":"duplicate"}
            receipt=repo.create_receipt(workspace_id=_["workspace_id"])
            repo.create_record(workspace_id=_["workspace_id"],command_name=_["command_name"],idempotency_key=_["idempotency_key"],request_hash=digest,receipt_id=receipt["receipt_id"])
            return receipt
