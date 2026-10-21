"""PostgreSQL grant and recovery epoch stores for caller-owned transactions."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from controlplane.domain.orchestration import OrchestrationContractError
from controlplane.domain.orchestration.fencing import GrantClaims


def _iso(value: Any) -> str:
    if isinstance(value, str):
        return value
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def _parse(text: str) -> datetime:
    iso_text = text[:-1] + '+00:00' if text.endswith('Z') else text
    dt = datetime.fromisoformat(iso_text)
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError('datetime must be timezone-aware')
    return dt


def _claims(row: Any) -> GrantClaims:
    return GrantClaims(
        grant_id=str(row[0]),
        stage_run_id=str(row[1]),
        execution_generation=int(row[2]),
        recovery_epoch=str(row[3]),
        worker_lease_id=str(row[4]),
        issued_at=_iso(row[5]),
        expires_at=_iso(row[6]),
        allowed_operation=str(row[7]),
        input_fingerprint=str(row[8]),
    )


class PostgresGrantStore:
    def __init__(self, connection: Any, workspace_id: str) -> None:
        self._connection = connection
        self._workspace_id = workspace_id

    def latest_generation(self, stage_run_id: str) -> int:
        row = self._connection.execute(
            "SELECT COALESCE(MAX(execution_generation), 0) "
            "FROM controlplane.cp_execution_grants "
            "WHERE workspace_id = %s AND stage_run_id = %s",
            (self._workspace_id, stage_run_id),
        ).fetchone()
        return int(row[0]) if row is not None else 0

    def active_grant(self, stage_run_id: str, now: datetime) -> GrantClaims | None:
        row = self._connection.execute(
            "SELECT grant_id, stage_run_id, execution_generation, recovery_epoch, "
            "worker_lease_id, issued_at, expires_at, allowed_operation, input_fingerprint "
            "FROM controlplane.cp_execution_grants "
            "WHERE workspace_id = %s AND stage_run_id = %s AND revoked_at IS NULL",
            (self._workspace_id, stage_run_id),
        ).fetchone()
        return _claims(row) if row is not None else None

    def insert(self, claims: GrantClaims) -> None:
        issued = _parse(claims.issued_at)
        expires = _parse(claims.expires_at)
        if claims.execution_generation <= self.latest_generation(claims.stage_run_id):
            raise ValueError('execution_generation must exceed the latest generation')
        self._connection.execute(
            "INSERT INTO controlplane.cp_execution_grants "
            "(grant_id, workspace_id, stage_run_id, execution_generation, recovery_epoch, "
            "worker_lease_id, issued_at, expires_at, allowed_operation, input_fingerprint) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                claims.grant_id,
                self._workspace_id,
                claims.stage_run_id,
                claims.execution_generation,
                str(claims.recovery_epoch),
                claims.worker_lease_id,
                issued,
                expires,
                claims.allowed_operation,
                claims.input_fingerprint,
            ),
        )

    def revoke(self, grant_id: str) -> None:
        self._connection.execute(
            "UPDATE controlplane.cp_execution_grants "
            "SET revoked_at = CURRENT_TIMESTAMP "
            "WHERE workspace_id = %s AND grant_id = %s AND revoked_at IS NULL",
            (self._workspace_id, grant_id),
        )


class PostgresRecoveryEpoch:
    def __init__(self, connection: Any, workspace_id: str) -> None:
        self._connection = connection
        self._workspace_id = workspace_id

    def current(self) -> str:
        row = self._connection.execute(
            "SELECT recovery_epoch FROM controlplane.cp_app_sessions "
            "WHERE workspace_id = %s AND status = 'ACTIVE' "
            "ORDER BY started_at DESC, session_ref DESC LIMIT 1",
            (self._workspace_id,),
        ).fetchone()
        if row is None:
            raise OrchestrationContractError('NOT_FOUND')
        return str(row[0])


__all__ = ['PostgresGrantStore', 'PostgresRecoveryEpoch']