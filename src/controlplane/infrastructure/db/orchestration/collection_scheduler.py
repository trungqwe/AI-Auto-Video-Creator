"""PW-A3: vòng lặp thu thập cục bộ (U1, không dùng Temporal Schedule) và consumer của CollectedDocumentAvailable.

collection_interval_minutes (180) chỉ là nhịp kiểm. Mỗi lượt kiểm đếm nguồn đến hạn (cp_sources ACTIVE, đúng Tier và chủ đề, chưa có mark của business_date theo Asia/Ho_Chi_Minh trong cp_source_cycle_marks); còn nguồn đến hạn thì khởi DailyCollectionWorkflow với id xác định theo ngày và lượt kiểm, REJECT_DUPLICATE và WorkflowAlreadyStartedError đều là thành công. PlanCollectionCycle ghi mark nên nhịp kiểm lặp lại không làm một nguồn bị quét quá một lượt định kỳ mỗi ngày.

Hàm tạo connection_factory phải trả về một đối tượng kết nối chưa bật autocommit.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from datetime import date, datetime
import logging
from typing import Any
from zoneinfo import ZoneInfo

from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from controlplane.application.orchestration.workflows.activities import SUBSCRIPTIONS, document_input_refs
from controlplane.application.orchestration.workflows.settings import WorkflowSettings
from controlplane.domain.orchestration.workflow_catalog import TaskQueue
from controlplane.infrastructure.db.orchestration.outbox_relay import SESSION_SQL, NoActiveAppSessionError

DAILY_WORKFLOW_NAME = 'DailyCollectionWorkflow'
ENRICHMENT_WORKFLOW_NAME = 'ContentEnrichmentWorkflow'
EVENT_NAME = 'CollectedDocumentAvailable'
MEDIA_ACTIVITY = 'RegisterMediaDiscovery'
DEFAULT_TIMEZONE = 'Asia/Ho_Chi_Minh'
DEFAULT_TOPIC = 'news'
ENRICH_BATCH_LIMIT = 20
_LOG = logging.getLogger(__name__)
DUE_SQL = (
    "SELECT count(*) FROM controlplane.cp_sources s WHERE s.workspace_id = %s AND s.status = 'ACTIVE' "
    "AND s.payload->>'tier' = ANY(%s) AND s.payload->'topics' @> to_jsonb(%s::text) "
    'AND NOT EXISTS (SELECT 1 FROM controlplane.cp_source_cycle_marks m '
    'WHERE m.workspace_id = s.workspace_id AND m.source_id = s.source_id AND m.cycle_day = %s)'
)
SELECT_SQL = (
    'SELECT event_id, payload FROM controlplane.cp_outbox_events '
    'WHERE workspace_id = %s AND published = false AND event_name = %s '
    'ORDER BY recorded_at, event_id LIMIT %s FOR UPDATE SKIP LOCKED'
)
ACK_SQL = (
    'UPDATE controlplane.cp_outbox_events SET published = true, published_at = %s '
    'WHERE event_id = %s AND published = false'
)


def _end(connection: Any, commit: bool) -> None:
    if commit:
        getattr(connection, 'commit')()
    else:
        getattr(connection, 'rollback')()


def _active_session(connection: Any, workspace_id: str) -> str:
    row = connection.execute(SESSION_SQL, (workspace_id,)).fetchone()
    if row is None:
        raise NoActiveAppSessionError('no ACTIVE AppSession for the workspace')
    return row[0]


class CollectionScheduler:
    def __init__(
        self,
        connection_factory: Callable[[], Any],
        temporal_client: Any,
        workspace_id: str,
        settings: WorkflowSettings,
        clock: Callable[[], datetime],
        *,
        collection_interval_minutes: int,
        tier_order: Sequence[str],
        topic: str = DEFAULT_TOPIC,
        timezone_name: str = DEFAULT_TIMEZONE,
    ) -> None:
        if type(collection_interval_minutes) is not int or collection_interval_minutes <= 0:
            raise ValueError('collection_interval_minutes must be a positive int')
        tiers = () if isinstance(tier_order, str) else tuple(tier_order)
        if not tiers or any(not isinstance(tier, str) or not tier for tier in tiers):
            raise ValueError('tier_order must be a non-empty sequence of Tiers')
        self._connection_factory = connection_factory
        self._client = temporal_client
        self._workspace_id = workspace_id
        self._settings_payload = settings.to_payload()
        self._clock = clock
        self._interval_minutes = collection_interval_minutes
        self._tier_order = tiers
        self._topic = topic
        self._zone = ZoneInfo(timezone_name)

    def check_slot(self, at: datetime) -> tuple[date, int]:
        if not isinstance(at, datetime) or at.tzinfo is None:
            raise ValueError('clock must return a timezone-aware datetime')
        local = at.astimezone(self._zone)
        return local.date(), (local.hour * 60 + local.minute) // self._interval_minutes

    def workflow_id(self, business_date: date, slot: int) -> str:
        return f'collect:{business_date.isoformat()}:{slot:03d}'

    def _lease_if_due(self, connection: Any, business_date: date) -> str | None:
        params = (self._workspace_id, list(self._tier_order), self._topic, business_date)
        due = connection.execute(DUE_SQL, params).fetchone()[0]
        return _active_session(connection, self._workspace_id) if due else None

    async def run_once(self) -> bool:
        """Một lượt kiểm: True khi workflow của lượt này đã được khởi hoặc đã tồn tại; False khi hết nguồn đến hạn."""
        business_date, slot = self.check_slot(self._clock())
        connection = await asyncio.to_thread(self._connection_factory)
        try:
            if connection.autocommit:
                raise ValueError('connection_factory must return a connection with autocommit off')
            lease = await asyncio.to_thread(self._lease_if_due, connection, business_date)
            await asyncio.to_thread(_end, connection, True)
        except BaseException:
            await asyncio.to_thread(_end, connection, False)
            raise
        finally:
            await asyncio.to_thread(connection.close)
        if lease is None:
            return False
        workflow_id = self.workflow_id(business_date, slot)
        request = {
            'settings': dict(self._settings_payload), 'input_fingerprint': workflow_id, 'worker_lease_id': lease,
            'input_refs': [{'ref_type': 'business_date', 'ref_id': business_date.isoformat()}],
        }
        try:
            await self._client.start_workflow(
                DAILY_WORKFLOW_NAME,
                request,
                id=workflow_id,
                task_queue=TaskQueue.CONTROL_WORKFLOWS.value,
                id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            )
        except WorkflowAlreadyStartedError:
            pass
        return True

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        interval_seconds = self._interval_minutes * 60
        while not stop_event.is_set():
            try:
                await self.run_once()
            except Exception:
                _LOG.exception('collection scheduler cycle failed')
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            except asyncio.TimeoutError:
                pass


class EnrichmentStarter:
    """Consumer của CollectedDocumentAvailable (SUBSCRIPTIONS): mỗi tài liệu mới khởi một ContentEnrichmentWorkflow id enrich:<document_id>."""

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
        lease = await asyncio.to_thread(_active_session, connection, self._workspace_id)
        acked = 0
        for event_id, payload in rows:
            document_id = self._document_id(event_id, payload)
            if document_id is None:
                continue
            try:
                await self._client.start_workflow(
                    ENRICHMENT_WORKFLOW_NAME,
                    self._request(document_id, lease),
                    id=f'enrich:{document_id}',
                    task_queue=TaskQueue.CONTROL_WORKFLOWS.value,
                    id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
                )
            except WorkflowAlreadyStartedError:
                pass
            await asyncio.to_thread(self._ack, connection, event_id)
            acked += 1
        return acked

    def _claim(self, connection: Any) -> list[tuple[Any, ...]]:
        return connection.execute(SELECT_SQL, (self._workspace_id, EVENT_NAME, ENRICH_BATCH_LIMIT)).fetchall()

    def _document_id(self, event_id: Any, payload: Any) -> str | None:
        value = payload.get('collected_document_id') if isinstance(payload, dict) else None
        if not isinstance(value, str) or not value.strip():
            _LOG.warning('outbox event %s has an invalid document payload; skipped', event_id)
            return None
        return value

    def _request(self, document_id: str, lease: str) -> dict[str, Any]:
        refs = [list(group) for group in document_input_refs([document_id])]
        return {
            'settings': dict(self._settings_payload),
            'input_fingerprint': f'enrich:{document_id}',
            'worker_lease_id': lease,
            'item_refs': {SUBSCRIPTIONS[EVENT_NAME]: refs, MEDIA_ACTIVITY: refs},
        }

    def _ack(self, connection: Any, event_id: Any) -> None:
        connection.execute(ACK_SQL, (self._clock(), event_id))

    async def run_forever(self, stop_event: asyncio.Event, interval_seconds: float) -> None:
        if interval_seconds <= 0:
            raise ValueError('interval_seconds must be positive')
        while not stop_event.is_set():
            try:
                await self.run_once()
            except Exception:
                _LOG.exception('enrichment starter cycle failed')
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            except asyncio.TimeoutError:
                pass


__all__ = ['CollectionScheduler', 'EnrichmentStarter']
