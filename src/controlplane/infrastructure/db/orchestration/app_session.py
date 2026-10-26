"""PW-G1: PostgreSQL store for AppSession rows (cp_app_sessions) on a caller-owned connection."""
from __future__ import annotations

import re
from typing import Any

from controlplane.domain.orchestration import OrchestrationContractError

INVALID_RECOVERY_EPOCH = 'INVALID_RECOVERY_EPOCH'
INVALID_SESSION_REF = 'INVALID_SESSION_REF'
_DECIMAL_EPOCH = re.compile(r'[0-9]+')


class PostgresAppSessions:
    def __init__(self, connection: Any, workspace_id: str) -> None:
        self._connection = connection
        self._workspace_id = workspace_id

    def begin(self, session_ref: str, recovery_epoch: str) -> None:
        if not isinstance(session_ref, str) or session_ref.strip() == '':
            raise OrchestrationContractError(INVALID_SESSION_REF)
        if not isinstance(recovery_epoch, str) or _DECIMAL_EPOCH.fullmatch(recovery_epoch) is None:
            raise OrchestrationContractError(INVALID_RECOVERY_EPOCH)
        self._connection.execute(
            "WITH abandoned AS ("
            "UPDATE controlplane.cp_app_sessions "
            "SET status = 'ABANDONED', ended_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
            "WHERE workspace_id = %s AND status = 'ACTIVE' RETURNING session_ref) "
            "INSERT INTO controlplane.cp_app_sessions "
            "(workspace_id, session_ref, status, recovery_epoch, started_at) "
            "VALUES (%s, %s, 'ACTIVE', %s, CURRENT_TIMESTAMP)",
            (self._workspace_id, self._workspace_id, session_ref, recovery_epoch),
        )

    def end(self, session_ref: str) -> None:
        self._connection.execute(
            "UPDATE controlplane.cp_app_sessions "
            "SET status = 'ENDED', ended_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
            "WHERE workspace_id = %s AND session_ref = %s AND status = 'ACTIVE'",
            (self._workspace_id, session_ref),
        )


__all__ = ['INVALID_RECOVERY_EPOCH', 'INVALID_SESSION_REF', 'PostgresAppSessions']
