"""PW-G6: outbox relay khởi ProductionBatchWorkflow trên PostgreSQL 18.6 thật và máy chủ test của temporalio.

coveredIds: PW-G6-01, ARCH-009, CT-WF-001
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import uuid

import psycopg
import pytest
from temporalio.common import WorkflowIDReusePolicy

from controlplane.application.orchestration.workflows.batch import BatchParams
from controlplane.application.orchestration.workflows.settings import WorkflowSettings, settings_from_parameters
from controlplane.domain.events import DomainEvent
from controlplane.infrastructure.db.control_api_commands import compose_command_service
from controlplane.infrastructure.db.orchestration.app_session import PostgresAppSessions
from controlplane.infrastructure.db.orchestration.outbox_relay import NoActiveAppSessionError, OutboxRelay
from controlplane.infrastructure.db.outbox.postgres import PostgresOutboxRepository
from controlplane.infrastructure.db.uow import TransactionManager

ROOT = Path(__file__).resolve().parents[3]
RELAY_SOURCE = ROOT / 'src/controlplane/infrastructure/db/orchestration/outbox_relay.py'
EVENT_NAME = 'production_batch.start_accepted'
NOW = datetime(2026, 10, 26, 3, 4, 5, tzinfo=timezone.utc)
PARAMETERS = {
    'workflow.start_to_close_seconds': {'control-workflows': 60, 'cloud-io': 900, 'cloud-ai': 240, 'desktop-cpu': 600, 'desktop-gpu': 900, 'desktop-render': 1200},
    'workflow.heartbeat_seconds': 30,
    'workflow.retry': {'initial_interval_seconds': 5, 'backoff_coefficient': 2.0, 'maximum_interval_seconds': 120, 'maximum_attempts': 3},
    'workflow.schedule': {'cloud_schedule_enabled': False},
    'ai.quota_wait_poll_seconds': 60,
    'meta.revision': 1,
}
SETTINGS = settings_from_parameters(PARAMETERS)


class RecordingClient:
    def __init__(self, client, *, delay=0.0, fail_on=()):
        self._client = client
        self.delay = delay
        self.fail_on = set(fail_on)
        self.calls = []

    async def start_workflow(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if len(self.calls) in self.fail_on:
            raise RuntimeError('injected start failure')
        if self.delay:
            await asyncio.sleep(self.delay)
        return await self._client.start_workflow(*args, **kwargs)


def new_batch(pw_database, target=2):
    manager = TransactionManager(pw_database.dsn)
    try:
        service = compose_command_service(manager.unit_of_work)
        receipt = service.start_batch(
            workspace_id=pw_database.workspace_id,
            actor_id=pw_database.actor_id,
            correlation_id='pw-g6',
            idempotency_key=str(uuid.uuid4()),
            payload={'target_completed_videos': target},
        )
        return receipt['resource_ref']['batch_id']
    finally:
        manager.close()


def begin_session(pw_database, session_ref='ses-1'):
    with pw_database.connect() as connection:
        PostgresAppSessions(connection, pw_database.workspace_id).begin(session_ref, '5')


def enqueue_event(pw_database, event_name, aggregate_id, payload):
    event = DomainEvent(
        contract_name='controlplane.production_batch',
        contract_version=1,
        message_id=str(uuid.uuid4()),
        workspace_id=pw_database.workspace_id,
        correlation_id='pw-g6',
        causation_id=None,
        trace_context=None,
        occurred_at='2026-10-26T01:00:00Z',
        actor='pw-g6',
        recovery_epoch=None,
        payload=payload,
        event_id=str(uuid.uuid4()),
        event_name=event_name,
        aggregate_type='production_batch',
        aggregate_id=aggregate_id,
        aggregate_revision=1,
        producer='pw-g6',
        schema_version=1,
        sensitivity='internal',
    )
    with pw_database.connect() as connection:
        PostgresOutboxRepository(connection).enqueue(event)


def outbox_rows(pw_database):
    with pw_database.connect() as connection:
        return connection.execute(
            'SELECT aggregate_id, event_name, published, published_at '
            'FROM controlplane.cp_outbox_events WHERE workspace_id = %s '
            'ORDER BY recorded_at, event_id',
            (pw_database.workspace_id,),
        ).fetchall()


def make_relay(pw_database, client):
    return OutboxRelay(
        lambda: psycopg.connect(pw_database.dsn),
        client,
        pw_database.workspace_id,
        SETTINGS,
        lambda: NOW,
    )


async def wait_published(pw_database, batch_id, seconds=15):
    for _ in range(int(seconds / 0.1)):
        if any(row[0] == batch_id and row[2] for row in outbox_rows(pw_database)):
            return
        await asyncio.sleep(0.1)
    raise AssertionError('batch event was not published: ' + batch_id)


@pytest.mark.asyncio
async def test_run_once_starts_one_workflow_per_batch_and_acks_after_start(pw_database, pw_temporal):
    begin_session(pw_database)
    batch_id = new_batch(pw_database, target=3)
    client = RecordingClient(pw_temporal)
    relay = make_relay(pw_database, client)
    assert await relay.run_once() == 1
    (args, kwargs), = client.calls
    assert args[0] == 'ProductionBatchWorkflow'
    assert args[1] == {
        'batch_id': batch_id,
        'target_videos': 3,
        'jobs': [],
        'settings': SETTINGS.to_payload(),
        'worker_lease_id': 'ses-1',
    }
    assert kwargs == {
        'id': batch_id,
        'task_queue': 'control-workflows',
        'id_reuse_policy': WorkflowIDReusePolicy.REJECT_DUPLICATE,
    }
    assert WorkflowSettings.from_payload(args[1]['settings']) == SETTINGS
    assert BatchParams.from_payload(args[1]).worker_lease_id == 'ses-1'
    description = await pw_temporal.get_workflow_handle(batch_id).describe()
    assert description.id == batch_id and description.task_queue == 'control-workflows'
    assert outbox_rows(pw_database) == [(batch_id, EVENT_NAME, True, NOW)]
    assert await relay.run_once() == 0 and len(client.calls) == 1


@pytest.mark.asyncio
async def test_two_parallel_relays_start_the_batch_once(pw_database, pw_temporal):
    begin_session(pw_database)
    batch_id = new_batch(pw_database)
    client = RecordingClient(pw_temporal, delay=1.0)
    results = await asyncio.gather(
        make_relay(pw_database, client).run_once(),
        make_relay(pw_database, client).run_once(),
    )
    assert sorted(results) == [0, 1]
    assert [kwargs['id'] for _, kwargs in client.calls] == [batch_id]
    assert outbox_rows(pw_database) == [(batch_id, EVENT_NAME, True, NOW)]


@pytest.mark.asyncio
async def test_start_failure_rolls_back_every_ack_and_the_next_run_recovers(pw_database, pw_temporal):
    begin_session(pw_database)
    first = new_batch(pw_database)
    second = new_batch(pw_database)
    client = RecordingClient(pw_temporal, fail_on={2})
    relay = make_relay(pw_database, client)
    with pytest.raises(RuntimeError, match='injected start failure'):
        await relay.run_once()
    assert outbox_rows(pw_database) == [
        (first, EVENT_NAME, False, None),
        (second, EVENT_NAME, False, None),
    ]
    client.fail_on = set()
    assert await relay.run_once() == 2
    assert [kwargs['id'] for _, kwargs in client.calls] == [first, second, first, second]
    assert outbox_rows(pw_database) == [
        (first, EVENT_NAME, True, NOW),
        (second, EVENT_NAME, True, NOW),
    ]
    for batch_id in (first, second):
        assert (await pw_temporal.get_workflow_handle(batch_id).describe()).id == batch_id


@pytest.mark.asyncio
async def test_already_started_workflow_is_acknowledged(pw_database, pw_temporal):
    begin_session(pw_database)
    batch_id = new_batch(pw_database)
    await pw_temporal.start_workflow('ProductionBatchWorkflow', {'batch_id': batch_id}, id=batch_id, task_queue='control-workflows')
    client = RecordingClient(pw_temporal)
    assert await make_relay(pw_database, client).run_once() == 1
    assert len(client.calls) == 1
    assert outbox_rows(pw_database) == [(batch_id, EVENT_NAME, True, NOW)]


@pytest.mark.asyncio
async def test_events_with_other_names_are_skipped_and_need_no_session(pw_database, pw_temporal):
    enqueue_event(pw_database, 'job.created', 'job-x', {'job_id': 'job-x'})
    client = RecordingClient(pw_temporal)
    relay = make_relay(pw_database, client)
    assert await relay.run_once() == 0 and client.calls == []
    batch_id = new_batch(pw_database)
    begin_session(pw_database)
    assert await relay.run_once() == 1
    assert outbox_rows(pw_database) == [
        ('job-x', 'job.created', False, None),
        (batch_id, EVENT_NAME, True, NOW),
    ]


@pytest.mark.asyncio
async def test_without_an_active_app_session_nothing_starts_and_nothing_is_acked(pw_database, pw_temporal):
    batch_id = new_batch(pw_database)
    client = RecordingClient(pw_temporal)
    with pytest.raises(NoActiveAppSessionError):
        await make_relay(pw_database, client).run_once()
    assert client.calls == []
    assert outbox_rows(pw_database) == [(batch_id, EVENT_NAME, False, None)]


@pytest.mark.asyncio
async def test_a_malformed_event_is_skipped_without_blocking_the_next_one(pw_database, pw_temporal):
    begin_session(pw_database)
    enqueue_event(pw_database, EVENT_NAME, 'bad', {'batch_id': '', 'target_count': 0})
    batch_id = new_batch(pw_database)
    client = RecordingClient(pw_temporal)
    assert await make_relay(pw_database, client).run_once() == 1
    assert [kwargs['id'] for _, kwargs in client.calls] == [batch_id]
    assert outbox_rows(pw_database) == [
        ('bad', EVENT_NAME, False, None),
        (batch_id, EVENT_NAME, True, NOW),
    ]


@pytest.mark.asyncio
async def test_a_connection_with_autocommit_is_rejected(pw_database):
    client = RecordingClient(None)
    relay = OutboxRelay(pw_database.connect, client, pw_database.workspace_id, SETTINGS, lambda: NOW)
    with pytest.raises(ValueError, match='autocommit'):
        await relay.run_once()
    assert client.calls == []


@pytest.mark.asyncio
async def test_run_forever_publishes_then_stops_at_once_even_with_a_long_interval(pw_database, pw_temporal):
    begin_session(pw_database)
    batch_id = new_batch(pw_database)
    client = RecordingClient(pw_temporal)
    stop_event = asyncio.Event()
    task = asyncio.create_task(make_relay(pw_database, client).run_forever(stop_event, 3600))
    await wait_published(pw_database, batch_id)
    stop_event.set()
    await asyncio.wait_for(task, timeout=5)
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_run_forever_with_stop_already_set_does_nothing(pw_database, pw_temporal):
    begin_session(pw_database)
    new_batch(pw_database)
    client = RecordingClient(pw_temporal)
    stop_event = asyncio.Event()
    stop_event.set()
    await asyncio.wait_for(make_relay(pw_database, client).run_forever(stop_event, 0.05), timeout=5)
    assert client.calls == []


@pytest.mark.asyncio
async def test_run_forever_survives_a_failed_cycle(pw_database, pw_temporal):
    begin_session(pw_database)
    batch_id = new_batch(pw_database)
    client = RecordingClient(pw_temporal, fail_on={1})
    stop_event = asyncio.Event()
    task = asyncio.create_task(make_relay(pw_database, client).run_forever(stop_event, 0.05))
    await wait_published(pw_database, batch_id)
    stop_event.set()
    await asyncio.wait_for(task, timeout=5)
    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_run_forever_rejects_a_non_positive_interval(pw_database):
    relay = make_relay(pw_database, RecordingClient(None))
    with pytest.raises(ValueError):
        await relay.run_forever(asyncio.Event(), 0)


def test_relay_source_uses_skip_locked_reject_duplicate_and_no_stub():
    text = RELAY_SOURCE.read_text(encoding='utf-8')
    for needle in ('FOR UPDATE SKIP LOCKED', 'REJECT_DUPLICATE', 'to_thread', 'production_batch.start_accepted', '.commit(', '.rollback('):
        assert needle in text, needle
    for banned in ('from src.', 'import src', 'PostgresOutboxPublisher', 'TransactionManager', 'ConnectionPool', 'psycopg', 'connect('):
        assert banned not in text, banned


def test_module_docstring_declares_covered_ids():
    assert 'coveredIds: PW-G6-01, ARCH-009, CT-WF-001' in (__doc__ or '')
