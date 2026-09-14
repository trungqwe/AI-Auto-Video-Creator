"""PostgreSQL persistence adapter for durable P2 idempotency."""


class PostgresIdempotencyRepository:
    """Repository constructed from the active SqlUnitOfWork connection."""

    def __init__(self, connection: object) -> None:
        self._connection = connection

    @staticmethod
    def _receipt(row: object, disposition: str | None = None) -> dict[str, object]:
        receipt_id, command_id, persisted_disposition, operation_id, resource_ref, accepted_at, current_revision = row
        return {
            "receipt_id": receipt_id,
            "command_id": command_id,
            "disposition": disposition or persisted_disposition,
            "operation_id": operation_id,
            "resource_ref": resource_ref,
            "accepted_at": accepted_at,
            "current_revision": current_revision,
        }

    def create_receipt(self, **_: object) -> object:
        import uuid
        receipt_id=uuid.uuid4(); workspace_id=_["workspace_id"]; command_id=_.get("command_id") or str(uuid.uuid4())
        row = self._connection.execute(
            "INSERT INTO controlplane.cp_command_receipts(receipt_id,workspace_id,command_id,disposition,accepted_at) "
            "VALUES(%s,%s,%s,'accepted',CURRENT_TIMESTAMP) "
            "RETURNING receipt_id,command_id,disposition,operation_id,resource_ref,accepted_at,current_revision",
            (receipt_id, workspace_id, command_id),
        ).fetchone()
        return self._receipt(row)

    def get_record(self, **_: object) -> object:
        return self._connection.execute("SELECT request_hash,receipt_id FROM controlplane.cp_idempotency_records WHERE workspace_id=%s AND command_name=%s AND idempotency_key=%s",(_["workspace_id"],_["command_name"],_["idempotency_key"])).fetchone()

    def lock_key(self, **_: object) -> None:
        self._connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f'{_["workspace_id"]}:{_["command_name"]}:{_["idempotency_key"]}',))

    def replay_receipt(self, receipt_id: object) -> object:
        row = self._connection.execute(
            "SELECT receipt_id,command_id,disposition,operation_id,resource_ref,accepted_at,current_revision "
            "FROM controlplane.cp_command_receipts WHERE receipt_id=%s",
            (receipt_id,),
        ).fetchone()
        return self._receipt(row, disposition="duplicate")

    def create_record(self, **_: object) -> object:
        self._connection.execute("INSERT INTO controlplane.cp_idempotency_records(workspace_id,command_name,idempotency_key,request_hash,receipt_id,created_at) VALUES(%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)",(_["workspace_id"],_["command_name"],_["idempotency_key"],_["request_hash"],_["receipt_id"]))
