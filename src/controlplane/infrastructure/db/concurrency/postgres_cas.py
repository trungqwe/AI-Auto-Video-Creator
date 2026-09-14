"""Structural P2 PostgreSQL CAS adapter; no behavior exists during RED."""


class PostgresRevisionedMutationAdapter:
    def __init__(self, connection: object) -> None:
        self._connection = connection

    def mutate(self, **_: object) -> object:
        resource_id=_["resource_id"]; expected=_["expected_revision"]; payload=_["payload"]
        row=self._connection.execute("UPDATE controlplane.cp_revision_probe SET revision=revision+1,payload=%s WHERE resource_id=%s AND revision=%s RETURNING revision",(payload,resource_id,expected)).fetchone()
        if row is None:
            from controlplane.application.concurrency import RevisionConflictError
            current=self._connection.execute("SELECT revision FROM controlplane.cp_revision_probe WHERE resource_id=%s",(resource_id,)).fetchone()[0]
            raise RevisionConflictError(current)
        return {"revision":row[0]}
