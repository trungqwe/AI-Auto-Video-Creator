"""PW-G3: grant issuance on PostgreSQL, grant revocation after each result and the ExecutionGrant currency check.

Synchronous: callers run these in worker threads. Every database action is its own committed transaction.
"""
from __future__ import annotations

import contextlib
import datetime
from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any

from controlplane.application.orchestration.grant_issuance import GrantIssuer
from controlplane.application.orchestration.workflows.activities import BINDINGS_BY_NAME
from controlplane.domain.orchestration import ExecutionGrant, OrchestrationContractError
from controlplane.domain.orchestration.fencing import GrantClaims
from controlplane.domain.orchestration.workflow_catalog import TaskQueue
from controlplane.infrastructure.db.orchestration.grants import PostgresGrantStore, PostgresRecoveryEpoch
from controlplane.infrastructure.db.orchestration.stage_runs import PostgresStageRuns

# ASSUMPTION D8, OI-PW-05: default grant lifetime in seconds per task queue; profile values override per queue.
DEFAULT_TTL_BY_QUEUE: Mapping[str, int] = MappingProxyType({
    TaskQueue.CONTROL_WORKFLOWS.value: 300,
    TaskQueue.CLOUD_IO.value: 900,
    TaskQueue.CLOUD_AI.value: 900,
    TaskQueue.DESKTOP_CPU.value: 900,
    TaskQueue.DESKTOP_GPU.value: 1800,
    TaskQueue.DESKTOP_RENDER.value: 3600,
})
FALLBACK_QUEUE = TaskQueue.CONTROL_WORKFLOWS.value


def _ttl_table(overrides: Mapping[str, int] | None) -> dict[str, int]:
    table = dict(DEFAULT_TTL_BY_QUEUE)
    for queue, ttl in (overrides or {}).items():
        if queue not in table:
            raise ValueError(f'unknown task queue in ttl_by_queue: {queue}')
        if isinstance(ttl, bool) or not isinstance(ttl, int) or ttl <= 0:
            raise ValueError(f'ttl_by_queue[{queue}] must be a positive int')
        table[queue] = ttl
    return table


def build_grant_issuer(
    connection_factory: Callable[[], Any],
    workspace_id: str,
    ttl_by_queue: Mapping[str, int] | None,
    clock: Callable[[], datetime.datetime],
) -> Callable[[str, str, str, str], GrantClaims]:
    ttls = _ttl_table(ttl_by_queue)

    def issue(stage_run_id: str, allowed_operation: str, input_fingerprint: str, worker_lease_id: str) -> GrantClaims:
        binding = BINDINGS_BY_NAME.get(allowed_operation)
        ttl_seconds = ttls[binding.queue.value if binding is not None else FALLBACK_QUEUE]
        with connection_factory() as connection:
            with connection.transaction():
                epochs = PostgresRecoveryEpoch(connection, workspace_id)
                PostgresStageRuns(connection, workspace_id).ensure(stage_run_id, epochs.current())
                issuer = GrantIssuer(PostgresGrantStore(connection, workspace_id), epochs)
                return issuer.issue(stage_run_id, allowed_operation, input_fingerprint, worker_lease_id, ttl_seconds, clock())

    return issue


def _request_grant_id(request: Any) -> str | None:
    if not isinstance(request, Mapping):
        return None
    grant = request.get('execution_grant')
    if not isinstance(grant, Mapping):
        return None
    grant_id = grant.get('grant_id')
    if not isinstance(grant_id, str) or not grant_id:
        return None
    if grant.get('stage_run_id') != request.get('stage_run_id'):
        return None
    return grant_id


class GrantRevokingDispatcher:
    """Wraps the PW-G2 dispatcher: after every result, including a raising handler, the request's grant is revoked in its own transaction (CT-WF-004)."""

    def __init__(self, inner: Any, connection_factory: Callable[[], Any], workspace_id: str) -> None:
        self._inner = inner
        self._connection_factory = connection_factory
        self._workspace_id = workspace_id

    def dispatch(self, request: Mapping[str, Any]) -> dict[str, Any]:
        try:
            result = self._inner.dispatch(request)
        except BaseException:
            with contextlib.suppress(Exception):
                self._revoke(request)
            raise
        self._revoke(request)
        return result

    def _revoke(self, request: Any) -> None:
        grant_id = _request_grant_id(request)
        if grant_id is None:
            return
        with self._connection_factory() as connection:
            with connection.transaction():
                PostgresGrantStore(connection, self._workspace_id).revoke(grant_id)


def _parse_utc(text: object) -> datetime.datetime | None:
    if not isinstance(text, str):
        return None
    try:
        parsed = datetime.datetime.fromisoformat(text[:-1] + '+00:00' if text.endswith('Z') else text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None


class ExecutionGrantCurrency:
    """is_grant_current for an ExecutionGrant: operation_id equals the stored grant_id, with the same generation and the current recovery epoch, not revoked and not expired."""

    def __init__(self, connection_factory: Callable[[], Any], workspace_id: str, clock: Callable[[], datetime.datetime]) -> None:
        self._connection_factory = connection_factory
        self._workspace_id = workspace_id
        self._clock = clock

    def is_grant_current(self, grant: ExecutionGrant) -> bool:
        if not isinstance(grant, ExecutionGrant) or grant.workspace_id != self._workspace_id:
            return False
        if isinstance(grant.execution_generation, bool) or isinstance(grant.recovery_epoch, bool):
            return False
        epoch = str(grant.recovery_epoch)
        now = self._clock()
        with self._connection_factory() as connection:
            with connection.transaction():
                try:
                    current_epoch = PostgresRecoveryEpoch(connection, self._workspace_id).current()
                except OrchestrationContractError:
                    return False
                active = PostgresGrantStore(connection, self._workspace_id).active_grant(grant.stage_run_id, now)
        if active is None:
            return False
        expires_at = _parse_utc(active.expires_at)
        return (
            expires_at is not None
            and active.grant_id == grant.operation_id
            and active.execution_generation == grant.execution_generation
            and active.recovery_epoch == epoch == current_epoch
            and now < expires_at
        )


__all__ = ['DEFAULT_TTL_BY_QUEUE', 'ExecutionGrantCurrency', 'GrantRevokingDispatcher', 'build_grant_issuer']
