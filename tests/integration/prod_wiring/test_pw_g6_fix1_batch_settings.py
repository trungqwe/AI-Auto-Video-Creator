"""PW-G6-FIX1: mỗi lô chọn số luồng video 1-10 qua POST /v1/batches, payload outbox, relay và GET /v1/batch-settings.

coveredIds: PW-G6-FIX1-01
"""
from __future__ import annotations

import dataclasses
import importlib
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg
import pytest
from fastapi.testclient import TestClient

from controlplane.api.main import create_app
from controlplane.application.orchestration.workflows.batch import BatchParams
from controlplane.application.orchestration.workflows.settings import settings_from_parameters
from controlplane.application.session_security import BootstrapCapabilityRegistry
from controlplane.domain.events import DomainEvent
from controlplane.infrastructure.db.orchestration.app_session import PostgresAppSessions
from controlplane.infrastructure.db.orchestration.outbox_relay import OutboxRelay
from controlplane.infrastructure.db.outbox.postgres import PostgresOutboxRepository
from controlplane.infrastructure.db.uow import TransactionManager


def bc():
    return importlib.import_module('controlplane.application.control_api.batch_concurrency')


ORIGIN = 'https://localhost:8443'
EVENT_NAME = 'production_batch.start_accepted'
NOW = datetime(2026, 10, 31, 3, 4, 5, tzinfo=timezone.utc)
PARAMETERS = {
    'workflow.start_to_close_seconds': {'control-workflows': 60, 'cloud-io': 900, 'cloud-ai': 240, 'desktop-cpu': 600, 'desktop-gpu': 900, 'desktop-render': 1200},
    'workflow.heartbeat_seconds': 30,
    'workflow.retry': {'initial_interval_seconds': 5, 'backoff_coefficient': 2.0, 'maximum_interval_seconds': 120, 'maximum_attempts': 3},
    'workflow.schedule': {'cloud_schedule_enabled': False},
    'ai.quota_wait_poll_seconds': 60,
    'meta.revision': 1,
}
SETTINGS = settings_from_parameters(PARAMETERS)


def begin_session(pw_database, session_ref='ses-1'):
    with pw_database.connect() as connection:
        PostgresAppSessions(connection, pw_database.workspace_id).begin(session_ref, '5')


def enqueue_event(pw_database, event_name, aggregate_id, payload):
    event = DomainEvent(
        contract_name='controlplane.production_batch',
        contract_version=1,
        message_id=str(uuid.uuid4()),
        workspace_id=pw_database.workspace_id,
        correlation_id='pw-g6-fix1',
        causation_id=None,
        trace_context=None,
        occurred_at='2026-10-31T01:00:00Z',
        actor='pw-g6-fix1',
        recovery_epoch=None,
        payload=payload,
        event_id=str(uuid.uuid4()),
        event_name=event_name,
        aggregate_type='production_batch',
        aggregate_id=aggregate_id,
        aggregate_revision=1,
        producer='pw-g6-fix1',
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


@contextmanager
def api_client(pw_database, limits=None):
    manager = TransactionManager(pw_database.dsn)
    registry = BootstrapCapabilityRegistry()
    app = create_app(manager=manager, allowed_origins={ORIGIN}, bootstrap_registry=registry)
    if limits is not None:
        app.state.batch_concurrency = limits
    capability = registry.issue(workspace_id=pw_database.workspace_id, actor_id=pw_database.actor_id)
    try:
        with TestClient(app, base_url=ORIGIN, raise_server_exceptions=False) as client:
            response = client.post(
                '/v1/session/bootstrap',
                headers={
                    'Origin': ORIGIN,
                    'X-Launch-Capability': capability,
                    'Cookie': 'csrf_token=bootstrap',
                    'X-CSRF-Token': 'bootstrap',
                },
            )
            assert response.status_code == 200, response.text
            yield client
    finally:
        manager.close()


def post_batch(client, body):
    headers = {
        'Origin': ORIGIN,
        'X-CSRF-Token': client.cookies['csrf_token'],
        'Idempotency-Key': str(uuid.uuid4()),
    }
    return client.post('/v1/batches', json=body, headers=headers)


def counts(pw_database):
    tables = ('cp_production_batches', 'cp_command_receipts', 'cp_idempotency_records', 'cp_outbox_events')
    with pw_database.connect() as connection:
        return tuple(
            connection.execute(
                f'SELECT count(*) FROM controlplane.{table} WHERE workspace_id = %s',
                (pw_database.workspace_id,),
            ).fetchone()[0]
            for table in tables
        )


def event_payloads(pw_database):
    with pw_database.connect() as connection:
        rows = connection.execute(
            'SELECT payload FROM controlplane.cp_outbox_events '
            'WHERE workspace_id = %s AND event_name = %s ORDER BY recorded_at, event_id',
            (pw_database.workspace_id, EVENT_NAME),
        ).fetchall()
    return [row[0] for row in rows]


def test_resolve_missing_key_returns_default():
    limits = bc().BatchConcurrency(6, 10)
    assert bc().resolve({}, limits) == 6
    assert bc().resolve({'target_completed_videos': 2}, limits) == 6


def test_resolve_accepts_bounds():
    limits = bc().BatchConcurrency(6, 10)
    assert bc().resolve({'max_concurrent_videos': 1}, limits) == 1
    assert bc().resolve({'max_concurrent_videos': 10}, limits) == 10


@pytest.mark.parametrize('value', [0, 11, -1, True, False, '4', 1.5, None])
def test_resolve_rejects_invalid(value):
    limits = bc().BatchConcurrency(6, 10)
    with pytest.raises(bc().BatchFieldError) as exc:
        bc().resolve({'max_concurrent_videos': value}, limits)
    assert exc.value.field_errors == {'max_concurrent_videos': 'Số nguyên từ 1 tới 10.'}
    assert isinstance(exc.value, ValueError)


@pytest.mark.parametrize('default, maximum', [(7, 6), (0, 5), (6, 0), (-1, 5), (True, 5), (5, True), ('6', 10), (6.0, 10)])
def test_batch_concurrency_rejects_bad_limits(default, maximum):
    with pytest.raises(ValueError):
        bc().BatchConcurrency(default, maximum)


def test_sequential_is_one_one():
    assert bc().SEQUENTIAL == bc().BatchConcurrency(1, 1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        bc().SEQUENTIAL.default = 2


def test_batch_settings_endpoint_returns_limits(pw_database):
    with api_client(pw_database, bc().BatchConcurrency(6, 10)) as client:
        response = client.get('/v1/batch-settings')
        assert response.status_code == 200
        assert response.json() == {'max_concurrent_videos': {'default': 6, 'min': 1, 'max': 10}}


def test_batch_settings_without_state_is_sequential(pw_database):
    with api_client(pw_database) as client:
        response = client.get('/v1/batch-settings')
        assert response.status_code == 200
        assert response.json() == {'max_concurrent_videos': {'default': 1, 'min': 1, 'max': 1}}


def test_post_without_field_uses_default(pw_database):
    with api_client(pw_database, bc().BatchConcurrency(6, 10)) as client:
        response = post_batch(client, {'target_completed_videos': 2})
        assert response.status_code == 202, response.text
    payloads = event_payloads(pw_database)
    assert len(payloads) == 1
    assert payloads[0]['max_concurrent_videos'] == 6
    assert payloads[0]['target_count'] == 2


def test_post_with_three_carries_three(pw_database):
    with api_client(pw_database, bc().BatchConcurrency(6, 10)) as client:
        response = post_batch(client, {'target_completed_videos': 2, 'max_concurrent_videos': 3})
        assert response.status_code == 202, response.text
    payloads = event_payloads(pw_database)
    assert len(payloads) == 1
    assert payloads[0]['max_concurrent_videos'] == 3


def test_post_with_one_omits_key(pw_database):
    with api_client(pw_database, bc().BatchConcurrency(6, 10)) as client:
        response = post_batch(client, {'target_completed_videos': 2, 'max_concurrent_videos': 1})
        assert response.status_code == 202, response.text
    payloads = event_payloads(pw_database)
    assert len(payloads) == 1
    assert 'max_concurrent_videos' not in payloads[0]


@pytest.mark.parametrize('value', [0, 11, True, '4', 1.5])
def test_post_invalid_concurrency_is_422_and_creates_nothing(pw_database, value):
    with api_client(pw_database, bc().BatchConcurrency(6, 10)) as client:
        response = post_batch(client, {'target_completed_videos': 2, 'max_concurrent_videos': value})
        assert response.status_code == 422, response.text
        assert response.json()['code'] == 'VALIDATION_FAILED'
        assert 'max_concurrent_videos' in response.json()['field_errors']
    assert counts(pw_database) == (0, 0, 0, 0)


def test_target_zero_stays_validation_error(pw_database):
    with api_client(pw_database, bc().BatchConcurrency(6, 10)) as client:
        for body in (
            {'target_completed_videos': 0},
            {'target_completed_videos': 0, 'max_concurrent_videos': 99},
        ):
            response = post_batch(client, body)
            assert response.status_code == 422, response.text
            assert response.json()['code'] == 'VALIDATION_ERROR'
    assert counts(pw_database) == (0, 0, 0, 0)


def test_unknown_fields_are_not_rejected(pw_database):
    with api_client(pw_database, bc().BatchConcurrency(6, 10)) as client:
        response = post_batch(client, {'target_completed_videos': 2, 'workspace_id': str(uuid.uuid4()), 'foo': 'bar'})
        assert response.status_code == 202, response.text


def test_app_without_state_posts_sequentially(pw_database):
    with api_client(pw_database) as client:
        response = post_batch(client, {'target_completed_videos': 2})
        assert response.status_code == 202, response.text
        payloads = event_payloads(pw_database)
        assert len(payloads) == 1
        assert 'max_concurrent_videos' not in payloads[0]
        response = post_batch(client, {'target_completed_videos': 2, 'max_concurrent_videos': 2})
        assert response.status_code == 422, response.text
        assert response.json()['code'] == 'VALIDATION_FAILED'


class FakeClient:
    def __init__(self):
        self.calls = []

    async def start_workflow(self, *args, **kwargs):
        self.calls.append((args, kwargs))


@pytest.mark.asyncio
async def test_relay_forwards_concurrency_above_one(pw_database):
    begin_session(pw_database)
    bid = str(uuid.uuid4())
    enqueue_event(pw_database, EVENT_NAME, bid, {'batch_id': bid, 'target_count': 5, 'max_concurrent_videos': 4})
    client = FakeClient()
    relay = make_relay(pw_database, client)
    assert await relay.run_once() == 1
    request = client.calls[0][0][1]
    assert request['max_concurrent_videos'] == 4
    assert BatchParams.from_payload(request).max_concurrent_videos == 4
    assert outbox_rows(pw_database) == [(bid, EVENT_NAME, True, NOW)]


@pytest.mark.asyncio
@pytest.mark.parametrize('payload_extra', [{}, {'max_concurrent_videos': 1}])
async def test_relay_keeps_five_keys_when_missing_or_one(pw_database, payload_extra):
    begin_session(pw_database)
    bid = str(uuid.uuid4())
    enqueue_event(pw_database, EVENT_NAME, bid, {'batch_id': bid, 'target_count': 5, **payload_extra})
    client = FakeClient()
    assert await make_relay(pw_database, client).run_once() == 1
    request = client.calls[0][0][1]
    assert set(request) == {'batch_id', 'target_videos', 'jobs', 'settings', 'worker_lease_id'}


@pytest.mark.asyncio
@pytest.mark.parametrize('bad', [0, -1, True, 'x', 1.5])
async def test_relay_skips_invalid_concurrency_without_blocking(pw_database, bad):
    begin_session(pw_database)
    bad_id = str(uuid.uuid4())
    good_id = str(uuid.uuid4())
    enqueue_event(pw_database, EVENT_NAME, bad_id, {'batch_id': bad_id, 'target_count': 3, 'max_concurrent_videos': bad})
    enqueue_event(pw_database, EVENT_NAME, good_id, {'batch_id': good_id, 'target_count': 3, 'max_concurrent_videos': 2})
    client = FakeClient()
    assert await make_relay(pw_database, client).run_once() == 1
    assert len(client.calls) == 1
    assert client.calls[0][1]['id'] == good_id
    assert outbox_rows(pw_database) == [
        (bad_id, EVENT_NAME, False, None),
        (good_id, EVENT_NAME, True, NOW),
    ]


def test_module_docstring_declares_covered_ids():
    assert 'coveredIds: PW-G6-FIX1-01' in (__doc__ or '')
