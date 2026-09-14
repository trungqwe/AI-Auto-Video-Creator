"""Structural P2 repository port; persistence behavior is intentionally absent during RED."""


class PostgresIdempotencyRepository:
    """Repository constructed from the active SqlUnitOfWork connection."""

    def __init__(self, connection: object) -> None:
        self._connection = connection

    def create_receipt(self, **_: object) -> object:
        import uuid
        receipt_id=uuid.uuid4(); workspace_id=_["workspace_id"]; command_id=str(uuid.uuid4())
        self._connection.execute("INSERT INTO controlplane.cp_command_receipts(receipt_id,workspace_id,command_id,disposition,accepted_at) VALUES(%s,%s,%s,'accepted',CURRENT_TIMESTAMP)",(receipt_id,workspace_id,command_id))
        return {"receipt_id":receipt_id,"command_id":command_id,"disposition":"accepted"}

    def get_record(self, **_: object) -> object:
        return self._connection.execute("SELECT request_hash,receipt_id FROM controlplane.cp_idempotency_records WHERE workspace_id=%s AND command_name=%s AND idempotency_key=%s",(_["workspace_id"],_["command_name"],_["idempotency_key"])).fetchone()

    def create_record(self, **_: object) -> object:
        self._connection.execute("INSERT INTO controlplane.cp_idempotency_records(workspace_id,command_name,idempotency_key,request_hash,receipt_id,created_at) VALUES(%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)",(_["workspace_id"],_["command_name"],_["idempotency_key"],_["request_hash"],_["receipt_id"]))
