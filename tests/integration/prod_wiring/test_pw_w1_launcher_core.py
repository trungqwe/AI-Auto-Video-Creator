"""PW-W1: launcher nối G, A, B, C, I trên PostgreSQL thật; Temporal, Drive và mạng là adapter giả.

coveredIds: PW-W1-01, CT-WF-004, CT-WF-007, ARCH-009
"""
from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import importlib.util
import json
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

import controlplane.api.wiring.production as production_wiring
import controlplane.api.wiring.production_profile as profile_wiring
import controlplane.api.wiring.workflow as workflow_wiring
from controlplane.api.wiring.collection import build_collection_services
from controlplane.api.wiring.storage import build_storage_services
from controlplane.application.orchestration.capability_view import AVAILABLE, CAPABILITY_KEY, DEGRADED, UNAVAILABLE
from controlplane.application.orchestration.workflows.activities import ActivityRejected
from controlplane.infrastructure.db.orchestration.app_session import PostgresAppSessions
from controlplane.infrastructure.db.uow import TransactionManager
from controlplane.infrastructure.production_ports.gpu_lease import LocalGpuLease

ROOT = Path(__file__).resolve().parents[3]
LAUNCHER_PATH = ROOT / 'tools' / 'launcher' / 'launcher.py'
PROFILE_PATH = ROOT / 'tools' / 'launcher' / 'prod' / 'profile.json'
NOW = datetime(2026, 10, 27, 1, 2, 3, tzinfo=timezone.utc)
FFMPEG_BYTES = b'pinned-ffmpeg-bytes'
LISTED = ('PlanCollectionCycle', 'CollectSource', 'ResolveCollectedDocument', 'RegisterMediaDiscovery', 'AllocateJob', 'FinalizeBatch', 'ReserveVariant', 'CommitVideoCompletion', 'MaterializeArtifactSet', 'PersistVideoOutput', 'RequestCleanupEvaluation', 'ReconcileStorage')


@pytest.fixture(scope='module')
def launcher():
    spec = importlib.util.spec_from_file_location('pw_w1_launcher', LAUNCHER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_runtime(tmp_path):
    ffmpeg = tmp_path / 'ffmpeg.exe'
    ffmpeg.write_bytes(FFMPEG_BYTES)
    lock = tmp_path / 'runtime.lock.json'
    lock.write_text(json.dumps({'pins': {'ffmpeg': {'status': 'PINNED', 'sha256': hashlib.sha256(FFMPEG_BYTES).hexdigest()}}}), encoding='utf-8')
    return profile_wiring.ProductionRuntime(
        ffmpeg_path=ffmpeg,
        ffprobe_path=tmp_path / 'ffprobe.exe',
        runtime_lock_path=lock,
        weights_dir=tmp_path / 'weights',
        weights_lock_path=tmp_path / 'model-weights.lock.json',
        whisper_model_dir=tmp_path / 'whisper',
        staging_root=tmp_path / 'staging',
        secret_store_root=tmp_path / 'vault',
        oauth_client_secrets_path=tmp_path / 'client.json',
        oauth_consent_timeout_seconds=300,
        route_cost_per_request=Decimal('0'),
        tokenization={'revision': 'pw-w1', 'unicode_form': 'NFC', 'casefold': True, 'edge_strip_categories': ('P',), 'gap_tolerance_ms': 500, 'min_confidence': 0.5},
        drive_placement={'original': 'folder-original', 'reusable': 'folder-reusable', 'output': 'folder-output'},
        drive_fallback_parent_id='folder-root',
        route_catalog=SimpleNamespace(candidates=lambda workspace_id, ai_role: ()),
        provider_credentials=SimpleNamespace(acquire=lambda method, account: None),
        vision_route=SimpleNamespace(invoke_vision=lambda *args, **kwargs: ''),
        artifact_source=SimpleNamespace(open=lambda artifact_version_id: None),
        drive_token_broker=SimpleNamespace(acquire=lambda method, account: None),
        gpu_lease=LocalGpuLease(2, 60.0),
    )


def scalar(database, sql):
    with database.connect() as connection:
        return connection.execute(sql, (database.workspace_id,)).fetchone()[0]


@pytest.fixture
def rig(pw_database, tmp_path):
    profile = profile_wiring.load_production_profile(PROFILE_PATH)
    runtime = make_runtime(tmp_path)
    config = profile_wiring.WiringConfig(mode='production', workspace_id=pw_database.workspace_id, profile=profile, runtime=runtime)
    manager = TransactionManager(pw_database.dsn, pool_max_size=4)
    try:
        app = SimpleNamespace(
            manager=manager,
            workspace_id=pw_database.workspace_id,
            services={'collection': build_collection_services(manager, config), 'storage': build_storage_services(manager, config)},
            api_app=SimpleNamespace(state=SimpleNamespace(production_runtime=runtime)),
        )
        yield SimpleNamespace(app=app, database=pw_database, manager=manager, profile=profile, runtime=runtime)
    finally:
        manager.close()


class FakeTemporalClient:
    async def start_workflow(self, *args, **kwargs):
        return SimpleNamespace(id=kwargs.get('id'))


def start_with_spies(launcher, rig, monkeypatch):
    import temporalio.client
    seen = {}

    class FakeClient:
        @staticmethod
        async def connect(target, namespace='default', **kw):
            seen['connect'] = (target, namespace)
            return FakeTemporalClient()

    class FakeGroup:
        def __init__(self, client, registration, *, graceful_shutdown_seconds):
            self.done = None

        async def run(self):
            self.done = asyncio.Event()
            await self.done.wait()

        async def stop(self):
            self.done.set()

    real_registration = workflow_wiring.build_temporal_registration

    def spy_registration(services, **kw):
        seen['services'] = services
        seen['kw'] = kw
        return real_registration(services, **kw)

    monkeypatch.setattr(temporalio.client, 'Client', FakeClient)
    monkeypatch.setattr(production_wiring, 'TemporalWorkerGroup', FakeGroup)
    monkeypatch.setattr(workflow_wiring, 'build_temporal_registration', spy_registration)
    monkeypatch.setattr(launcher, 'STOP_GRACE_SECONDS', 5)
    handle = launcher.start_worker(rig.app, None)
    time.sleep(0.3)
    return handle, seen


def test_start_worker_binds_every_listed_activity_and_wraps_the_dispatcher(launcher, rig, monkeypatch):
    handle, seen = start_with_spies(launcher, rig, monkeypatch)
    try:
        outer = seen['services'].dispatcher
        assert type(outer).__name__ == 'GrantRevokingDispatcher'
        recording = outer._inner
        assert type(recording).__name__ == 'ResultRecordingDispatcher'
        assert [type(item).__name__ for item in recording._listeners] == ['JobLifecycleListener']
        inner = recording._inner
        assert type(inner).__name__ == 'ActivityDispatcher'
        unbound = [name for name in LISTED if 'unbound_handler' in inner._handlers[name].__qualname__]
        assert unbound == []
        assert set(LISTED) <= set(seen['services'].bound_activities)
        assert seen['connect'] == ('127.0.0.1:7233', 'default')
    finally:
        handle.stop()


def request_for(claims, activity_name):
    return {
        'workflow_id': 'wf-1',
        'workflow_run_id': 'run-1',
        'stage_run_id': claims.stage_run_id,
        'activity_name': activity_name,
        'activity_version': '1',
        'input_refs': [],
        'operation_key': 'op-' + activity_name,
        'capability_requirements': {},
        'retry_policy_ref': 'retry-1',
        'execution_grant': dataclasses.asdict(claims),
    }


def test_capability_reader_follows_the_real_probes(launcher, rig, monkeypatch):
    handle, seen = start_with_spies(launcher, rig, monkeypatch)
    try:
        reader = seen['kw']['capability_reader']
        status = lambda: reader()[CAPABILITY_KEY]['status']
        assert status() == UNAVAILABLE
        with rig.database.connect() as connection:
            PostgresAppSessions(connection, rig.database.workspace_id).begin('ses-1', '5')
        assert status() == AVAILABLE
        leases = [rig.runtime.gpu_lease.acquire('probe-a'), rig.runtime.gpu_lease.acquire('probe-b')]
        assert status() == DEGRADED
        for lease in leases:
            rig.runtime.gpu_lease.release(lease)
        assert status() == AVAILABLE
        rig.runtime.ffmpeg_path.write_bytes(FFMPEG_BYTES + b'-tampered')
        assert status() == UNAVAILABLE
    finally:
        handle.stop()


def test_grant_is_revoked_after_a_real_handler_ran(launcher, rig, monkeypatch):
    handle, seen = start_with_spies(launcher, rig, monkeypatch)
    try:
        with rig.database.connect() as connection:
            PostgresAppSessions(connection, rig.database.workspace_id).begin('ses-1', '5')
        claims = seen['kw']['grant_issuer']('wf-1:reconcile:r1', 'ReconcileStorage', 'fp-1', 'ses-1')
        assert scalar(rig.database, 'SELECT count(*) FROM controlplane.cp_execution_grants WHERE workspace_id = %s AND revoked_at IS NULL') == 1
        result = None
        try:
            result = seen['services'].dispatcher.dispatch(request_for(claims, 'ReconcileStorage'))
        except ActivityRejected:
            pass
        if result is not None:
            assert result['disposition'] == 'succeeded'
        assert scalar(rig.database, 'SELECT count(*) FROM controlplane.cp_execution_grants WHERE workspace_id = %s AND revoked_at IS NULL') == 0
        assert scalar(rig.database, 'SELECT count(*) FROM controlplane.cp_execution_grants WHERE workspace_id = %s') == 1
    finally:
        handle.stop()


def test_worker_runs_relay_scheduler_and_enrichment_and_stop_ends_them(launcher, rig, monkeypatch):
    import controlplane.infrastructure.db.orchestration.collection_scheduler as scheduler_module
    import controlplane.infrastructure.db.orchestration.outbox_relay as relay_module
    log = []

    def spy(real, name):
        class Spy(real):
            async def run_forever(self, stop_event, *args):
                log.append((name, 'start'))
                try:
                    await super().run_forever(stop_event, *args)
                finally:
                    log.append((name, 'end'))

        return Spy

    monkeypatch.setattr(relay_module, 'OutboxRelay', spy(relay_module.OutboxRelay, 'relay'))
    monkeypatch.setattr(scheduler_module, 'CollectionScheduler', spy(scheduler_module.CollectionScheduler, 'scheduler'))
    monkeypatch.setattr(scheduler_module, 'EnrichmentStarter', spy(scheduler_module.EnrichmentStarter, 'enrichment'))
    handle, _seen = start_with_spies(launcher, rig, monkeypatch)
    assert sorted(name for name, state in log if state == 'start') == ['enrichment', 'relay', 'scheduler']
    started = time.monotonic()
    handle.stop()
    assert time.monotonic() - started < 5
    assert sorted(name for name, state in log if state == 'end') == ['enrichment', 'relay', 'scheduler']


def test_persist_video_output_uses_the_cloud_store(rig, tmp_path):
    import controlplane.api.wiring.storage as storage_wiring
    store = storage_wiring.InMemoryCloudObjectStore()
    services = storage_wiring.StorageServices('production', rig.manager, store, None)
    root = tmp_path / 'persist-staging'
    (root / 'render').mkdir(parents=True)
    (root / 'render' / 'out.mp4').write_bytes(b'\x00\x00\x00\x18ftypmp42' + bytes(range(200)))
    table = storage_wiring.storage_activity_services(services, transactions=rig.manager, workspace_id=rig.database.workspace_id, staging_root=root)
    assert set(table) == {'MaterializeArtifactSet', 'PersistVideoOutput', 'RequestCleanupEvaluation', 'ReconcileStorage'}
    request = {'video_job_id': 'job-1', 'operation_key': 'op-1', 'input_refs': [{'ref_type': 'render_output', 'ref_id': 'render/out.mp4'}]}
    result = table['PersistVideoOutput'](request, SimpleNamespace(grant_id='grant-1', recovery_epoch='5'))
    assert result['disposition'] == 'succeeded'
    assert len(store._objects) == 1


def spy_deps(launcher, tmp_path, events):
    def note(name):
        def record(*args):
            events.append((name, *args))
        return record

    def spawn(cmd, **kw):
        events.append(('spawn', cmd))
        return SimpleNamespace(pid=4242)

    def make_cert(cert, key):
        cert.write_bytes(b'CERT')
        key.write_bytes(b'KEY')

    return dataclasses.replace(
        launcher.default_deps({'AIAVC_DATA_DIR': str(tmp_path / 'data')}),
        run=lambda cmd, **kw: SimpleNamespace(returncode=0, stdout='', stderr=''),
        spawn=spawn, out=lambda message: None, ask=lambda prompt='': '', sleep=lambda seconds: None,
        wait_tcp=lambda host, port, timeout: True, pid_alive=lambda pid: False,
        migrate=note('migrate'), ensure_identity=note('identity'), begin_session=note('begin_session'),
        end_session=note('end_session'), max_session_epoch=lambda dsn, workspace_id: 0,
        make_cert=make_cert, open_browser=lambda url: True, now=lambda: NOW,
        ensure_namespace=lambda host, port: 'EXISTS', seed_defaults=note('seed_defaults'),
    )


def test_start_seeds_after_the_app_session_and_before_the_worker(launcher, tmp_path):
    events = []
    assert launcher.cmd_start(spy_deps(launcher, tmp_path, events), SimpleNamespace()) == 0
    names = [event[0] for event in events]
    assert names.index('begin_session') < names.index('seed_defaults') < names.index('spawn')
    begin = next(event for event in events if event[0] == 'begin_session')
    identity = next(event for event in events if event[0] == 'identity')
    seed = next(event for event in events if event[0] == 'seed_defaults')
    assert seed[1:] == (begin[1], begin[2], identity[3], begin[4])


def test_a_failed_session_blocks_the_seed(launcher, tmp_path):
    events = []

    def refuse(*args):
        raise RuntimeError('session refused')

    deps = dataclasses.replace(spy_deps(launcher, tmp_path, events), begin_session=refuse)
    with pytest.raises(RuntimeError):
        launcher.cmd_start(deps, SimpleNamespace())
    assert not any(event[0] in ('seed_defaults', 'spawn') for event in events)


def test_seed_defaults_registers_seven_sources_and_six_prompts_once(launcher, pw_database, monkeypatch):
    import controlplane.api.wiring.collection as collection_wiring
    monkeypatch.setattr(collection_wiring, 'system_dns_resolver', lambda host: ['93.184.216.34'])
    for _ in range(2):
        launcher.seed_defaults(pw_database.dsn, pw_database.workspace_id, pw_database.actor_id, '1')
    assert scalar(pw_database, 'SELECT count(*) FROM controlplane.cp_sources WHERE workspace_id = %s') == 7
    assert scalar(pw_database, "SELECT count(*) FROM controlplane.cp_config_revisions WHERE workspace_id = %s AND scope_kind = 'prompt'") == 6
