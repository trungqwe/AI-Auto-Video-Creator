"""OPSTREAM-WIRE: outbox events reach controlplane.cp_operation_stream in production through the accepted P3 consumer.

The relay runs PostgresEventProcessor and PostgresOperationStreamRepository unchanged against an in-memory stand-in of the
five P3 tables that answers exactly the SQL the relay and the P3 adapters send (any other statement fails the test), so
no PostgreSQL, Temporal or network is needed. The launcher test starts the real start_worker with stand-ins for Temporal
and the other background loops.

coveredIds: CT-API-008
"""
from __future__ import annotations

import asyncio
import copy
from datetime import datetime, timedelta, timezone
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
import uuid

import pytest

ROOT = Path(__file__).resolve().parents[3]
LAUNCHER_PATH = ROOT / 'tools' / 'launcher' / 'launcher.py'
WS = '00000000-0000-0000-0000-00000000a001'
OTHER_WS = '00000000-0000-0000-0000-00000000b002'
T0 = datetime(2026, 11, 2, 8, 0, 0, tzinfo=timezone.utc)


def relay_module():
    return importlib.import_module('controlplane.infrastructure.db.projections.operation_stream_relay')


class InjectedFailure(RuntimeError):
    pass


class FakeP3Database:
    """cp_outbox_events, cp_event_checkpoints, cp_event_quarantine and cp_operation_stream with commit and rollback."""

    def __init__(self) -> None:
        self.committed = {'outbox': [], 'checkpoints': {}, 'quarantine': {}, 'stream': []}
        self.sequence = 0
        self.fail_stream_for: set[str] = set()
        self.statements: list[str] = []

    def add(self, *, workspace_id=WS, event_name='video_job.state_changed', aggregate_type='video_job', aggregate_id=None,
            revision=1, payload=None, schema_version=1, recorded_at=T0, event_id=None) -> str:
        event_id = event_id or str(uuid.uuid4())
        self.committed['outbox'].append({
            'event_id': event_id, 'workspace_id': workspace_id, 'contract_name': 'controlplane.video_job', 'contract_version': 1,
            'message_id': 'message-' + event_id[:8], 'correlation_id': 'corr-' + event_id[:8], 'causation_id': None,
            'trace_context': None, 'occurred_at': recorded_at, 'actor': 'system', 'recovery_epoch': None,
            'payload': {'status': 'RUNNING'} if payload is None else payload, 'event_name': event_name,
            'aggregate_type': aggregate_type, 'aggregate_id': aggregate_id or str(uuid.uuid4()),
            'aggregate_revision': revision, 'producer': 'controlplane.test', 'schema_version': schema_version,
            'sensitivity': 'internal', 'recorded_at': recorded_at, 'published': False, 'published_at': None,
        })
        return event_id

    def connect(self, *, autocommit=False) -> 'FakeConnection':
        return FakeConnection(self, autocommit)

    @property
    def stream(self):
        return self.committed['stream']

    @property
    def checkpoints(self):
        return self.committed['checkpoints']

    @property
    def quarantine(self):
        return self.committed['quarantine']


class FakeResult:
    def __init__(self, rows) -> None:
        self._rows = list(rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class FakeConnection:
    def __init__(self, db: FakeP3Database, autocommit: bool) -> None:
        self.db = db
        self.autocommit = autocommit
        self.closed = False
        self.work = None
        self.commits = 0
        self.rollbacks = 0

    def _state(self):
        if self.work is None:
            self.work = copy.deepcopy(self.db.committed)
        return self.work

    def commit(self) -> None:
        if self.work is not None:
            self.db.committed = self.work
        self.work = None
        self.commits += 1

    def rollback(self) -> None:
        self.work = None
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True

    def execute(self, sql, params=()):
        assert not self.closed
        self.db.statements.append(sql)
        s = self._state()
        text = ' '.join(sql.split())
        if text.startswith('SELECT e.event_id::text'):
            workspace_id, consumer, consumer_q, limit = params
            assert consumer == consumer_q
            rows = [r for r in s['outbox'] if r['workspace_id'] == workspace_id
                    and (consumer, r['event_id']) not in s['checkpoints'] and (consumer, r['event_id']) not in s['quarantine']]
            rows.sort(key=lambda r: (r['recorded_at'], r['aggregate_revision'], r['event_id']))
            columns = relay_module().COLUMNS
            return FakeResult([tuple(copy.deepcopy(r[c]) for c in columns) for r in rows[:limit]])
        if text.startswith('SELECT MAX(e.aggregate_revision)'):
            consumer, status, workspace_id, aggregate_type, aggregate_id = params
            revisions = [r['aggregate_revision'] for r in s['outbox'] if r['workspace_id'] == workspace_id
                         and r['aggregate_type'] == aggregate_type and r['aggregate_id'] == aggregate_id
                         and s['checkpoints'].get((consumer, r['event_id']), {}).get('status') == status]
            return FakeResult([(max(revisions) if revisions else None,)])
        if text.startswith('SELECT status FROM controlplane.cp_event_checkpoints'):
            found = s['checkpoints'].get(tuple(params))
            return FakeResult([(found['status'],)] if found else [])
        if text.startswith('SELECT pg_advisory_xact_lock(hashtext(%s))'):
            return FakeResult([(None,)])
        if 'INSERT INTO controlplane.cp_operation_stream' in text:
            fence, workspace_id, operation_id, rtype, rid, rev, kind, occurred_at, summary, correlation = params
            assert fence == workspace_id and 'pg_advisory_xact_lock' in text
            self.db.sequence += 1
            if rid in self.db.fail_stream_for:
                raise InjectedFailure('stream insert failed for ' + rid)
            s['stream'].append({'stream_event_id': self.db.sequence, 'workspace_id': workspace_id, 'operation_id': operation_id,
                                'resource_type': rtype, 'resource_id': rid, 'resource_revision': rev, 'event_kind': kind,
                                'occurred_at': occurred_at, 'summary': summary, 'correlation_id': correlation})
            return FakeResult([(self.db.sequence,)])
        if text.startswith('INSERT INTO controlplane.cp_event_checkpoints'):
            consumer, event_id, workspace_id, atype, aid, rev, current, status = params
            s['checkpoints'].setdefault((consumer, event_id), {'status': status, 'workspace_id': workspace_id, 'revision': rev})
            return FakeResult([])
        if text.startswith('INSERT INTO controlplane.cp_event_quarantine'):
            consumer, event_id, workspace_id, reason, envelope = params
            json.loads(envelope)
            s['quarantine'].setdefault((consumer, event_id), {'reason': reason, 'envelope': envelope, 'workspace_id': workspace_id})
            return FakeResult([])
        raise AssertionError('unexpected SQL: ' + text[:160])


def make_relay(db, **kw):
    return relay_module().OperationStreamRelay(lambda: db.connect(), WS, **kw)


def test_outbox_events_become_operation_stream_rows_of_their_workspace():
    db = FakeP3Database()
    a = db.add(event_name='production_batch.start_accepted', aggregate_type='production_batch', aggregate_id='batch-1')
    b = db.add(event_name='video_job.state_changed', aggregate_id='job-1', recorded_at=T0 + timedelta(seconds=1))
    c = db.add(event_name='render.output_inspected', aggregate_type='Render', aggregate_id='render-1', revision=3,
               recorded_at=T0 + timedelta(seconds=2))
    db.add(workspace_id=OTHER_WS, aggregate_id='job-other')
    assert make_relay(db).run_once() == 3
    rows = db.stream
    assert [r['event_kind'] for r in rows] == ['production_batch.start_accepted', 'video_job.state_changed', 'render.output_inspected']
    assert [r['stream_event_id'] for r in rows] == [1, 2, 3]
    assert {r['workspace_id'] for r in rows} == {WS}
    assert [(r['resource_type'], r['resource_id'], r['resource_revision']) for r in rows] == [
        ('production_batch', 'batch-1', 1), ('video_job', 'job-1', 1), ('Render', 'render-1', 3)]
    assert all(r['summary'] == 'projection' and r['correlation_id'].startswith('corr-') for r in rows)
    consumer = relay_module().CONSUMER_ID
    assert {k: v['status'] for k, v in db.checkpoints.items()} == {(consumer, a): 'APPLIED', (consumer, b): 'APPLIED', (consumer, c): 'APPLIED'}
    assert all(not r['published'] and r['published_at'] is None for r in db.committed['outbox'])
    assert not any(' '.join(q.split()).startswith('UPDATE') for q in db.statements)


def test_running_again_appends_nothing_twice():
    db = FakeP3Database()
    for i in range(3):
        db.add(aggregate_id=f'job-{i}', recorded_at=T0 + timedelta(seconds=i))
    relay = make_relay(db)
    assert relay.run_once() == 3
    assert relay.run_once() == 0
    assert make_relay(db).run_once() == 0
    assert len(db.stream) == 3
    db.add(aggregate_id='job-9', recorded_at=T0 + timedelta(seconds=9))
    assert relay.run_once() == 1
    assert [r['resource_id'] for r in db.stream] == ['job-0', 'job-1', 'job-2', 'job-9']


def test_revisions_of_one_aggregate_follow_the_p3_order_rules():
    db = FakeP3Database()
    second = db.add(aggregate_id='job-1', revision=2, event_id='ffffffff-0000-0000-0000-000000000002')
    first = db.add(aggregate_id='job-1', revision=1, event_id='00000000-0000-0000-0000-000000000001')
    stale = db.add(aggregate_id='job-1', revision=1, recorded_at=T0 + timedelta(seconds=5))
    gap = db.add(aggregate_id='job-1', revision=5, recorded_at=T0 + timedelta(seconds=6))
    assert make_relay(db).run_once() == 2
    assert [(r['resource_id'], r['resource_revision']) for r in db.stream] == [('job-1', 1), ('job-1', 2)]
    consumer = relay_module().CONSUMER_ID
    status = {k[1]: v['status'] for k, v in db.checkpoints.items()}
    assert status == {first: 'APPLIED', second: 'APPLIED', stale: 'OUT_OF_ORDER', gap: 'GAP_BLOCKED'}
    assert all(k[0] == consumer for k in db.checkpoints)


def test_unsafe_payload_is_quarantined_by_reference_and_never_streamed():
    db = FakeP3Database()
    bad = db.add(aggregate_id='job-bad', payload={'note': 'token=abc123'})
    good = db.add(aggregate_id='job-good', recorded_at=T0 + timedelta(seconds=1))
    relay = make_relay(db)
    assert relay.run_once() == 1
    assert [r['resource_id'] for r in db.stream] == ['job-good']
    module = relay_module()
    entry = db.quarantine[(module.CONSUMER_ID, bad)]
    assert entry['reason'] == module.UNSAFE_PAYLOAD and entry['workspace_id'] == WS
    envelope = json.loads(entry['envelope'])
    assert envelope['event_id'] == bad and envelope['source'] == 'controlplane.cp_outbox_events'
    assert 'payload' not in envelope and 'abc123' not in entry['envelope']
    assert (module.CONSUMER_ID, good) in db.checkpoints
    assert relay.run_once() == 0 and len(db.stream) == 1


def test_unsupported_schema_goes_to_the_p3_quarantine_once():
    db = FakeP3Database()
    old = db.add(aggregate_id='job-v2', schema_version=2)
    relay = make_relay(db)
    assert relay.run_once() == 0
    module = relay_module()
    entry = db.quarantine[(module.CONSUMER_ID, old)]
    assert entry['reason'] == 'QUARANTINED_UNSUPPORTED_SCHEMA'
    assert json.loads(entry['envelope'])['occurred_at'] == T0.isoformat()
    assert db.stream == [] and relay.run_once() == 0


def test_a_failed_event_rolls_back_alone_and_is_projected_on_the_next_cycle():
    db = FakeP3Database()
    db.add(aggregate_id='job-1')
    db.add(aggregate_id='job-2', recorded_at=T0 + timedelta(seconds=1))
    db.add(aggregate_id='job-3', recorded_at=T0 + timedelta(seconds=2))
    db.fail_stream_for = {'job-2'}
    relay = make_relay(db)
    with pytest.raises(InjectedFailure):
        relay.run_once()
    assert [r['resource_id'] for r in db.stream] == ['job-1']
    assert len(db.checkpoints) == 1
    db.fail_stream_for = set()
    assert relay.run_once() == 2
    assert [r['resource_id'] for r in db.stream] == ['job-1', 'job-2', 'job-3']
    assert [r['stream_event_id'] for r in db.stream] == [1, 3, 4]


def test_connections_with_autocommit_are_refused_and_always_closed():
    db = FakeP3Database()
    db.add(aggregate_id='job-1')
    opened = []

    def factory():
        connection = db.connect(autocommit=True)
        opened.append(connection)
        return connection

    with pytest.raises(ValueError):
        relay_module().OperationStreamRelay(factory, WS).run_once()
    assert opened[0].closed and db.stream == []


def test_run_forever_waits_one_interval_and_survives_a_failed_cycle():
    module = relay_module()
    db = FakeP3Database()
    db.add(aggregate_id='job-1')
    calls = []

    def factory():
        calls.append(time.monotonic())
        if len(calls) == 1:
            raise OSError('database not reachable yet')
        return db.connect()

    async def scenario():
        stop = asyncio.Event()
        task = asyncio.ensure_future(module.OperationStreamRelay(factory, WS).run_forever(stop, 0.05))
        await asyncio.sleep(0.01)
        assert calls == []
        for _ in range(200):
            if db.stream:
                break
            await asyncio.sleep(0.01)
        stop.set()
        await asyncio.wait_for(task, timeout=2)

    asyncio.run(scenario())
    assert len(calls) >= 2 and [r['resource_id'] for r in db.stream] == ['job-1']
    with pytest.raises(ValueError):
        asyncio.run(module.OperationStreamRelay(factory, WS).run_forever(asyncio.Event(), 0))


@pytest.fixture(scope='module')
def launcher():
    spec = importlib.util.spec_from_file_location('opstream_wire_launcher', LAUNCHER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_start_worker_runs_the_stream_relay_beside_the_outbox_relay(launcher, monkeypatch):
    launcher.ensure_src_on_path()
    module = relay_module()
    import temporalio.client
    import controlplane.api.wiring.workflow as workflow_wiring
    import controlplane.api.wiring.production as production_wiring
    import controlplane.api.wiring.production_profile as profile_wiring
    import controlplane.application.orchestration.capability_view as capability_view
    import controlplane.application.orchestration.grant_runtime as grant_runtime
    import controlplane.infrastructure.db.orchestration.collection_scheduler as scheduler_module
    import controlplane.infrastructure.db.orchestration.outbox_relay as outbox_module

    seen = {}
    running = threading.Event()

    class FakeClient:
        @staticmethod
        async def connect(target, namespace='default', **kw):
            return SimpleNamespace()

    class FakeGroup:
        def __init__(self, client, registration, *, graceful_shutdown_seconds):
            self.done = None

        async def run(self):
            self.done = asyncio.Event()
            await self.done.wait()

        async def stop(self):
            self.done.set()

    class Loop:
        def __init__(self, *args, **kw):
            seen.setdefault('built', {})[type(self).__name__] = args

        async def run_forever(self, stop_event, *args):
            seen.setdefault('run', {})[type(self).__name__] = (stop_event, args)
            if type(self).__name__ == 'StreamRelay':
                running.set()
            await stop_event.wait()
            seen.setdefault('stopped', []).append(type(self).__name__)

    class OutboxLoop(Loop):
        pass

    class SchedulerLoop(Loop):
        pass

    class StarterLoop(Loop):
        pass

    class StreamRelay(Loop):
        pass

    monkeypatch.setattr(temporalio.client, 'Client', FakeClient)
    monkeypatch.setattr(workflow_wiring, 'assemble_activity_handlers', lambda **kw: {})
    monkeypatch.setattr(launcher, 'assemble_dfe_handlers', lambda *a, **kw: {})
    monkeypatch.setattr(workflow_wiring, 'build_workflow_services', lambda **kw: SimpleNamespace(settings=SimpleNamespace()))
    monkeypatch.setattr(workflow_wiring, 'wrap_dispatcher', lambda services, **kw: services)
    monkeypatch.setattr(workflow_wiring, 'build_capability_probes', lambda **kw: {})
    monkeypatch.setattr(workflow_wiring, 'build_temporal_registration', lambda services, **kw: SimpleNamespace())
    monkeypatch.setattr(grant_runtime, 'build_grant_issuer', lambda *a, **k: (lambda *x: None))
    monkeypatch.setattr(capability_view, 'CapabilityReader', lambda probes: (lambda: {}))
    monkeypatch.setattr(outbox_module, 'OutboxRelay', OutboxLoop)
    monkeypatch.setattr(scheduler_module, 'CollectionScheduler', SchedulerLoop)
    monkeypatch.setattr(scheduler_module, 'EnrichmentStarter', StarterLoop)
    monkeypatch.setattr(module, 'OperationStreamRelay', StreamRelay)
    monkeypatch.setattr(production_wiring, 'TemporalWorkerGroup', FakeGroup)
    parameters = {'collection.tiers': {'tier_1': 'x'}, 'collection.collection_interval_minutes': 180}
    monkeypatch.setattr(profile_wiring, 'load_production_profile', lambda path: SimpleNamespace(parameters=parameters))
    monkeypatch.setattr(launcher, 'STOP_GRACE_SECONDS', 5)
    runtime = SimpleNamespace(ffmpeg_path=Path('ffmpeg.exe'), runtime_lock_path=Path('runtime.lock.json'), gpu_lease=SimpleNamespace())
    app = SimpleNamespace(
        manager=SimpleNamespace(dsn='postgresql://unused'),
        workspace_id=WS,
        services={'collection': SimpleNamespace(), 'storage': SimpleNamespace()},
        api_app=SimpleNamespace(state=SimpleNamespace(production_runtime=runtime)),
    )
    handle = launcher.start_worker(app, None)
    try:
        assert running.wait(timeout=5), 'start_worker did not run OperationStreamRelay.run_forever'
    finally:
        handle.stop()
    built = seen['built']
    assert built['StreamRelay'][0] is built['OutboxLoop'][0] and built['StreamRelay'][1:] == (WS,)
    stream_stop, stream_args = seen['run']['StreamRelay']
    assert stream_stop is seen['run']['OutboxLoop'][0]
    assert stream_args == (launcher.OPERATION_STREAM_INTERVAL_SECONDS,) and launcher.OPERATION_STREAM_INTERVAL_SECONDS > 0
    assert 'StreamRelay' in seen['stopped']
