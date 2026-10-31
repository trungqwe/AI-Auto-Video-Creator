"""PW-G6: outbox relay khởi ProductionBatchWorkflow trong tiến trình worker.

Hàm tạo connection_factory phải trả về một đối tượng kết nối chưa bật autocommit.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
import logging
from typing import Any

from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from controlplane.application.orchestration.workflows.settings import WorkflowSettings
from controlplane.domain.orchestration.workflow_catalog import TaskQueue

EVENT_NAME = 'production_batch.start_accepted'
WORKFLOW_NAME = 'ProductionBatchWorkflow'
BATCH_LIMIT = 20
_LOG = logging.getLogger(__name__)
SELECT_SQL = (
    'SELECT event_id, payload FROM controlplane.cp_outbox_events '
    'WHERE workspace_id = %s AND published = false AND event_name = %s '
    'ORDER BY recorded_at, event_id LIMIT %s FOR UPDATE SKIP LOCKED'
)
SESSION_SQL = (
    "SELECT session_ref FROM controlplane.cp_app_sessions "
    "WHERE workspace_id = %s AND status = 'ACTIVE' ORDER BY started_at DESC LIMIT 1"
)
ACK_SQL = (
    'UPDATE controlplane.cp_outbox_events SET published = true, published_at = %s '
    'WHERE event_id = %s AND published = false'
)


class NoActiveAppSessionError(RuntimeError):
    """Không tìm thấy AppSession ở trạng thái ACTIVE cho workspace."""


def _end(connection: Any, commit: bool) -> None:
    if commit:
        connection.commit()
    else:
        connection.rollback()


class OutboxRelay:
    def __init__(
        self,
        connection_factory: Callable[[], Any],
        temporal_client: Any,
        workspace_id: str,
        settings: WorkflowSettings,
        clock: Callable[[], datetime],
    ) -> None:
        self._connection_factory = connection_factory
        self._client = temporal_client
        self._workspace_id = workspace_id
        self._settings_payload = settings.to_payload()
        self._clock = clock

    async def run_once(self) -> int:
        """Thực hiện một chu kỳ chuyển tiếp và trả về số sự kiện đã ack."""
        connection = await asyncio.to_thread(self._connection_factory)
        try:
            if connection.autocommit:
                raise ValueError('connection_factory must return a connection with autocommit off')
            acked = await self._publish(connection)
            await asyncio.to_thread(_end, connection, True)
            return acked
        except BaseException:
            await asyncio.to_thread(_end, connection, False)
            raise
        finally:
            await asyncio.to_thread(connection.close)

    async def _publish(self, connection: Any) -> int:
        rows = await asyncio.to_thread(self._claim, connection)
        if not rows:
            return 0
        lease = await asyncio.to_thread(self._active_session, connection)
        acked = 0
        for event_id, payload in rows:
            request = self._request(event_id, payload, lease)
            if request is None:
                continue
            try:
                await self._client.start_workflow(
                    WORKFLOW_NAME,
                    request,
                    id=request['batch_id'],
                    task_queue=TaskQueue.CONTROL_WORKFLOWS.value,
                    id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
                )
            except WorkflowAlreadyStartedError:
                pass
            await asyncio.to_thread(self._ack, connection, event_id)
            acked += 1
        return acked

    def _claim(self, connection: Any) -> list[tuple[Any, ...]]:
        return connection.execute(SELECT_SQL, (self._workspace_id, EVENT_NAME, BATCH_LIMIT)).fetchall()

    def _active_session(self, connection: Any) -> str:
        row = connection.execute(SESSION_SQL, (self._workspace_id,)).fetchone()
        if row is None:
            raise NoActiveAppSessionError('no ACTIVE AppSession for the workspace')
        return row[0]

    def _request(self, event_id: Any, payload: Any, lease: str) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            _LOG.warning('outbox event %s has an invalid start payload; skipped', event_id)
            return None
        batch_id = payload.get('batch_id')
        target = payload.get('target_count')
        if not isinstance(batch_id, str) or not batch_id or isinstance(target, bool) or not isinstance(target, int) or target <= 0:
            _LOG.warning('outbox event %s has an invalid start payload; skipped', event_id)
            return None
        concurrency = payload.get('max_concurrent_videos', 1)
        if isinstance(concurrency, bool) or not isinstance(concurrency, int) or concurrency < 1:
            _LOG.warning('outbox event %s has an invalid start payload; skipped', event_id)
            return None
        request = {
            'batch_id': batch_id,
            'target_videos': target,
            'jobs': [],
            'settings': dict(self._settings_payload),
            'worker_lease_id': lease,
        }
        if concurrency > 1:
            request['max_concurrent_videos'] = concurrency
        return request

    def _ack(self, connection: Any, event_id: Any) -> None:
        connection.execute(ACK_SQL, (self._clock(), event_id))

    async def run_forever(self, stop_event: asyncio.Event, interval_seconds: float) -> None:
        if interval_seconds <= 0:
            raise ValueError('interval_seconds must be positive')
        while not stop_event.is_set():
            try:
                await self.run_once()
            except Exception:
                _LOG.exception('outbox relay cycle failed')
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            except asyncio.TimeoutError:
                pass


__all__ = ['EVENT_NAME', 'NoActiveAppSessionError', 'OutboxRelay']
