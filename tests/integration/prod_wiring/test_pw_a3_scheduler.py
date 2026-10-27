"""PW-A3: vòng lặp thu thập cục bộ, consumer khởi enrichment và RegisterMediaDiscovery trên PostgreSQL thật và máy chủ test của temporalio.

coveredIds: PW-A3-01, CT-SRC-004, FR-COL-001
"""
from __future__ import annotations

import asyncio
import hashlib
import pathlib
import uuid
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from dataclasses import replace
from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
import pytest
from temporalio.common import WorkflowIDReusePolicy
from temporalio.worker import UnsandboxedWorkflowRunner, Worker

from catalog.application.discovery import DiscoveryObservation
from catalog.application.media_discovery_handler import MediaDiscoveryDeps, register_media_discovery
from catalog.domain.identity import CanonicalFingerprint, MediaKind, ProvenanceEntry, ProvenanceRelation, RightsStatus
from catalog.persistence.assets import PostgresMediaAssetRepository
from controlplane.api.wiring.workflow import build_temporal_registration, build_workflow_services
from controlplane.application.orchestration.grant_runtime import GrantRevokingDispatcher, build_grant_issuer
from controlplane.application.orchestration.workflows.activities import (
    ENRICHMENT_STAGE_ACTIVITIES,
    INVALID_ACTIVITY_REQUEST,
    MISSING_EXECUTION_GRANT,
    ActivityRejected,
)
from controlplane.application.orchestration.workflows.settings import settings_from_parameters
from controlplane.domain.events import DomainEvent
from controlplane.domain.orchestration.activity_binding import validate_activity_result
from controlplane.infrastructure.db.orchestration.app_session import PostgresAppSessions
from controlplane.infrastructure.db.orchestration.collection_scheduler import CollectionScheduler, EnrichmentStarter
from controlplane.infrastructure.db.orchestration.outbox_relay import NoActiveAppSessionError
from controlplane.infrastructure.db.outbox.postgres import PostgresOutboxRepository
from controlplane.infrastructure.db.uow import TransactionManager
from source_ingestion.adapters.real_media_fetch import MediaFetchBatch, StagedImage
from source_ingestion.application.plan_cycle import PlanCollectionCycle, plan_collection_cycle_handler
from source_ingestion.application.seed_sources import seed_sources
from source_ingestion.application.source_commands import SourceCommandHandler
from source_ingestion.domain.source import SourcePolicy
from source_ingestion.persistence.unit_of_work import PostgresSourceIngestionUnitOfWork

ROOT = pathlib.Path(__file__).resolve().parents[3]
SCHEDULER_SOURCE = ROOT / 'src/controlplane/infrastructure/db/orchestration/collection_scheduler.py'
HANDLER_SOURCE = ROOT / 'src/catalog/application/media_discovery_handler.py'
SOURCES_PATH = ROOT / 'tools' / 'launcher' / 'prod' / 'sources.json'
TIERS = ('tier_1', 'tier_2', 'tier_3')
POLICY = SourcePolicy(policy_revision='pw-a3', source_kinds=frozenset({'rss_feed'}), tiers=frozenset(TIERS), admin_metadata_keys=frozenset())
ICT = ZoneInfo('Asia/Ho_Chi_Minh')
GRANT_NOW = datetime(2026, 10, 27, 1, 2, 3, tzinfo=timezone.utc)
PARAMETERS = {
    'workflow.start_to_close_seconds': {'control-workflows': 60, 'cloud-io': 900, 'cloud-ai': 240, 'desktop-cpu': 600, 'desktop-gpu': 900, 'desktop-render': 1200},
    'workflow.heartbeat_seconds': 30,
    'workflow.retry': {'initial_interval_seconds': 5, 'backoff_coefficient': 2.0, 'maximum_interval_seconds': 120, 'maximum_attempts': 3},
    'workflow.schedule': {'cloud_schedule_enabled': False},
    'ai.quota_wait_poll_seconds': 60,
    'meta.revision': 1,
}
SETTINGS = settings_from_parameters(PARAMETERS)


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def ict(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=ICT)


class Resolver:
    def __call__(self, host: str) -> list[str]:
        return ['8.8.8.8']


class RecordingClient:
    def __init__(self, client: Any, *, fail_on: tuple[int, ...] = ()) -> None:
        self._client = client
        self.fail_on = set(fail_on)
        self.calls: list[tuple[Any, Any]] = []

    async def start_workflow(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        if len(self.calls) in self.fail_on:
            raise RuntimeError('injected start failure')
        return await self._client.start_workflow(*args, **kwargs)


@pytest.fixture
def manager(pw_database: Any):
    pool = TransactionManager(pw_database.dsn, pool_max_size=6)
    try:
        yield pool
    finally:
        pool.close()


def seed(manager: Any, db: Any) -> None:
    handler = SourceCommandHandler(
        uow=PostgresSourceIngestionUnitOfWork(manager, workspace_id=db.workspace_id),
        policy_provider=lambda workspace_id: POLICY,
        resolver=Resolver(),
        recovery_epoch='pw-a3',
    )
    assert seed_sources(handler, SOURCES_PATH, workspace_id=db.workspace_id).registered == 7


def begin_session(db: Any) -> None:
    with db.connect() as connection:
        PostgresAppSessions(connection, db.workspace_id).begin('ses-1', '5')


def scalar(db: Any, sql: str, params: tuple = ()) -> Any:
    with db.connect() as connection:
        return connection.execute(sql, params).fetchone()[0]


def make_scheduler(db: Any, client: Any, clock: Any, tier_order: tuple[str, ...] = TIERS) -> CollectionScheduler:
    return CollectionScheduler(
        lambda: psycopg.connect(db.dsn), client, db.workspace_id, SETTINGS, clock,
        collection_interval_minutes=180, tier_order=tier_order,
    )


def make_starter(db: Any, client: Any) -> EnrichmentStarter:
    return EnrichmentStarter(lambda: psycopg.connect(db.dsn), client, db.workspace_id, SETTINGS, lambda: GRANT_NOW)


def enqueue_event(db: Any, event_name: str, aggregate_id: str, payload: dict) -> None:
    event = DomainEvent(
        contract_name='source_ingestion.collected_document', contract_version=1, message_id=str(uuid.uuid4()),
        workspace_id=db.workspace_id, correlation_id='pw-a3', causation_id=None, trace_context=None,
        occurred_at='2026-10-27T01:00:00Z', actor='pw-a3', recovery_epoch=None, payload=payload,
        event_id=str(uuid.uuid4()), event_name=event_name, aggregate_type='collected_document',
        aggregate_id=aggregate_id, aggregate_revision=1, producer='pw-a3', schema_version=1, sensitivity='internal',
    )
    with db.connect() as connection:
        PostgresOutboxRepository(connection).enqueue(event)


def doc_event(db: Any, document_id: str) -> None:
    enqueue_event(db, 'CollectedDocumentAvailable', document_id, {'collected_document_id': document_id})


def outbox_rows(db: Any) -> list[tuple]:
    with db.connect() as connection:
        return connection.execute(
            'SELECT aggregate_id, event_name, published FROM controlplane.cp_outbox_events '
            'WHERE workspace_id = %s ORDER BY recorded_at, event_id',
            (db.workspace_id,),
        ).fetchall()


def ok_result(claims: Any, refs: tuple = ()) -> dict[str, Any]:
    return {
        'stage_run_id': claims.stage_run_id, 'grant_id': claims.grant_id,
        'execution_generation': claims.execution_generation, 'recovery_epoch': claims.recovery_epoch,
        'disposition': 'succeeded', 'output_refs': list(refs), 'completed_at': '2026-10-27T01:02:03Z',
    }


def daily_handlers(manager: Any, db: Any, clock: Any, collected: list[str]) -> dict[str, Any]:
    service = PlanCollectionCycle(
        uow_factory=lambda: PostgresSourceIngestionUnitOfWork(manager, workspace_id=db.workspace_id),
        workspace_id=db.workspace_id, tier_order=TIERS, clock=clock,
    )

    def collect(request: Any, claims: Any) -> dict[str, Any]:
        collected.append(request['input_refs'][0]['ref_id'])
        return ok_result(claims, [{'ref_type': 'collection_run', 'ref_id': request['operation_key']}])

    return {'PlanCollectionCycle': plan_collection_cycle_handler(service, lambda: GRANT_NOW), 'CollectSource': collect}


@asynccontextmanager
async def running_workers(client: Any, db: Any, handlers: dict[str, Any]):
    services = build_workflow_services(parameters=PARAMETERS, handlers=handlers, clock=lambda: GRANT_NOW, timezone_approved=False)
    services = replace(services, dispatcher=GrantRevokingDispatcher(services.dispatcher, db.connect, db.workspace_id))
    registration = build_temporal_registration(
        services,
        grant_issuer=build_grant_issuer(db.connect, db.workspace_id, None, lambda: GRANT_NOW),
        capability_reader=lambda: {'desktop_production': {'status': 'available'}},
    )
    async with AsyncExitStack() as stack:
        for queue, functions in registration.activities_by_queue.items():
            extra = {'workflows': list(registration.workflows)} if queue == 'control-workflows' else {}
            await stack.enter_async_context(
                Worker(client, task_queue=queue, activities=list(functions), workflow_runner=UnsandboxedWorkflowRunner(), **extra)
            )
        yield


@pytest.mark.asyncio
async def test_pw_a3_01_four_checks_in_a_day_collect_each_source_once(manager, pw_database, pw_temporal):
    begin_session(pw_database)
    seed(manager, pw_database)
    clock = Clock(ict(27, 1))
    client = RecordingClient(pw_temporal)
    scheduler = make_scheduler(pw_database, client, clock)
    collected: list[str] = []
    async with running_workers(pw_temporal, pw_database, daily_handlers(manager, pw_database, clock, collected)):
        assert await scheduler.run_once() is True
        first = await asyncio.wait_for(pw_temporal.get_workflow_handle('collect:2026-10-27:000').result(), timeout=120)
        assert first['status'] == 'COMPLETED'
        for hour in (4, 7, 10):
            clock.now = ict(27, hour)
            assert await scheduler.run_once() is False
        assert len(collected) == 7 and len(set(collected)) == 7
        assert scalar(pw_database, 'SELECT count(*) FROM controlplane.cp_source_cycle_marks') == 7
        (args, kwargs), = client.calls
        assert args[0] == 'DailyCollectionWorkflow'
        assert args[1] == {'settings': SETTINGS.to_payload(), 'input_fingerprint': 'collect:2026-10-27:000', 'worker_lease_id': 'ses-1'}
        assert kwargs == {'id': 'collect:2026-10-27:000', 'task_queue': 'control-workflows', 'id_reuse_policy': WorkflowIDReusePolicy.REJECT_DUPLICATE}
        clock.now = ict(28, 0, 30)
        assert await scheduler.run_once() is True
        await asyncio.wait_for(pw_temporal.get_workflow_handle('collect:2026-10-28:000').result(), timeout=120)
        assert len(collected) == 14
        assert scalar(pw_database, 'SELECT count(*) FROM controlplane.cp_source_cycle_marks') == 14


@pytest.mark.asyncio
async def test_pw_a3_01_the_same_check_twice_is_one_workflow(manager, pw_database, pw_temporal):
    begin_session(pw_database)
    seed(manager, pw_database)
    client = RecordingClient(pw_temporal)
    scheduler = make_scheduler(pw_database, client, Clock(ict(27, 1)))
    assert await scheduler.run_once() is True
    first = await pw_temporal.get_workflow_handle('collect:2026-10-27:000').describe()
    assert await scheduler.run_once() is True
    second = await pw_temporal.get_workflow_handle('collect:2026-10-27:000').describe()
    assert first.run_id == second.run_id and len(client.calls) == 2


@pytest.mark.asyncio
async def test_pw_a3_01_no_due_source_starts_nothing_and_a_due_source_needs_a_session(manager, pw_database, pw_temporal):
    seed(manager, pw_database)
    client = RecordingClient(pw_temporal)
    assert await make_scheduler(pw_database, client, Clock(ict(27, 1)), tier_order=('tier_9',)).run_once() is False
    with pytest.raises(NoActiveAppSessionError):
        await make_scheduler(pw_database, client, Clock(ict(27, 1))).run_once()
    assert client.calls == []
    assert scalar(pw_database, 'SELECT count(*) FROM controlplane.cp_source_cycle_marks') == 0


async def wait_for_calls(client: RecordingClient, count: int, seconds: int = 15) -> None:
    for _ in range(seconds * 10):
        if len(client.calls) >= count:
            return
        await asyncio.sleep(0.1)
    raise AssertionError('scheduler did not reach the expected call count')


@pytest.mark.asyncio
async def test_pw_a3_01_run_forever_checks_at_once_and_stops_gracefully(manager, pw_database, pw_temporal):
    begin_session(pw_database)
    seed(manager, pw_database)
    client = RecordingClient(pw_temporal)
    stop_event = asyncio.Event()
    task = asyncio.create_task(make_scheduler(pw_database, client, Clock(ict(27, 1))).run_forever(stop_event))
    await wait_for_calls(client, 1)
    stop_event.set()
    await asyncio.wait_for(task, timeout=5)
    assert len(client.calls) == 1
    stopped = asyncio.Event()
    stopped.set()
    await asyncio.wait_for(make_scheduler(pw_database, client, Clock(ict(27, 1))).run_forever(stopped), timeout=5)
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_pw_a3_01_run_forever_survives_a_failed_cycle_and_still_stops(manager, pw_database, pw_temporal):
    begin_session(pw_database)
    seed(manager, pw_database)
    client = RecordingClient(pw_temporal, fail_on=(1,))
    stop_event = asyncio.Event()
    task = asyncio.create_task(make_scheduler(pw_database, client, Clock(ict(27, 1))).run_forever(stop_event))
    await wait_for_calls(client, 1)
    stop_event.set()
    await asyncio.wait_for(task, timeout=5)


def test_pw_a3_01_constructor_and_clock_are_validated():
    db = SimpleNamespace(dsn='unused', workspace_id=str(uuid.uuid4()))
    for bad in (0, -1, True, '180'):
        with pytest.raises(ValueError):
            CollectionScheduler(lambda: None, None, db.workspace_id, SETTINGS, Clock(ict(27, 1)), collection_interval_minutes=bad, tier_order=TIERS)
    for bad_tiers in ('tier_1', ()):
        with pytest.raises(ValueError):
            make_scheduler(db, None, Clock(ict(27, 1)), tier_order=bad_tiers)
    naive = make_scheduler(db, None, Clock(datetime(2026, 10, 27, 1, 0)))
    with pytest.raises(ValueError, match='timezone-aware'):
        asyncio.run(naive.run_once())


def test_pw_a3_01_check_slots_follow_the_ict_day():
    scheduler = make_scheduler(SimpleNamespace(dsn='unused', workspace_id=str(uuid.uuid4())), None, Clock(ict(27, 1)))
    assert scheduler.check_slot(ict(27, 2, 59)) == (date(2026, 10, 27), 0)
    assert scheduler.check_slot(ict(27, 3)) == (date(2026, 10, 27), 1)
    assert scheduler.check_slot(ict(27, 23, 59)) == (date(2026, 10, 27), 7)
    assert scheduler.check_slot(datetime(2026, 10, 27, 17, 30, tzinfo=timezone.utc)) == (date(2026, 10, 28), 0)
    assert scheduler.workflow_id(date(2026, 10, 28), 3) == 'collect:2026-10-28:003'


def test_pw_a3_01_scheduler_source_is_local_with_no_cloud_schedule():
    text = SCHEDULER_SOURCE.read_text(encoding='utf-8')
    for needle in ('REJECT_DUPLICATE', 'collection_interval_minutes', 'FOR UPDATE SKIP LOCKED', 'WorkflowAlreadyStartedError', 'to_thread', 'stop_event'):
        assert needle in text, needle
    lowered = text.lower()
    for banned in ('from src.', 'import src', 'schedulespec', 'create_schedule', 'psycopg', 'fake', 'mock', 'memory'):
        assert banned not in lowered, banned


def test_module_docstring_declares_covered_ids():
    assert 'coveredIds: PW-A3-01, CT-SRC-004, FR-COL-001' in (__doc__ or '')


@pytest.mark.asyncio
async def test_one_enrichment_per_document_and_a_rerun_starts_no_second(pw_database, pw_temporal):
    begin_session(pw_database)
    doc_event(pw_database, 'doc-1')
    doc_event(pw_database, 'doc-2')
    enqueue_event(pw_database, 'job.created', 'job-x', {'job_id': 'job-x'})
    client = RecordingClient(pw_temporal, fail_on=(2,))
    starter = make_starter(pw_database, client)
    with pytest.raises(RuntimeError, match='injected start failure'):
        await starter.run_once()
    assert [row[2] for row in outbox_rows(pw_database)] == [False, False, False]
    first = await pw_temporal.get_workflow_handle('enrich:doc-1').describe()
    client.fail_on = set()
    assert await starter.run_once() == 2
    assert (await pw_temporal.get_workflow_handle('enrich:doc-1').describe()).run_id == first.run_id
    assert (await pw_temporal.get_workflow_handle('enrich:doc-2').describe()).id == 'enrich:doc-2'
    assert {row[0]: row[2] for row in outbox_rows(pw_database)} == {'doc-1': True, 'doc-2': True, 'job-x': False}
    (args, kwargs) = client.calls[0]
    refs = [[{'ref_type': 'collected_document', 'ref_id': 'doc-1'}]]
    assert args[0] == 'ContentEnrichmentWorkflow'
    assert args[1] == {
        'settings': SETTINGS.to_payload(), 'input_fingerprint': 'enrich:doc-1', 'worker_lease_id': 'ses-1',
        'item_refs': {'ResolveCollectedDocument': refs, 'RegisterMediaDiscovery': refs},
    }
    assert kwargs == {'id': 'enrich:doc-1', 'task_queue': 'control-workflows', 'id_reuse_policy': WorkflowIDReusePolicy.REJECT_DUPLICATE}
    assert await starter.run_once() == 0


@pytest.mark.asyncio
async def test_the_enrichment_workflow_passes_the_document_ref_to_the_media_stage(pw_database, pw_temporal):
    begin_session(pw_database)
    doc_event(pw_database, 'doc-1')
    seen: dict[str, list] = {}

    def recorder(name: str):
        def handler(request: Any, claims: Any) -> dict[str, Any]:
            seen.setdefault(name, []).append(request['input_refs'])
            return ok_result(claims)

        return handler

    handlers = {name: recorder(name) for name in ('ResolveCollectedDocument', 'RegisterMediaDiscovery')}
    async with running_workers(pw_temporal, pw_database, handlers):
        assert await make_starter(pw_database, RecordingClient(pw_temporal)).run_once() == 1
        snapshot = await asyncio.wait_for(pw_temporal.get_workflow_handle('enrich:doc-1').result(), timeout=120)
    ref = [{'ref_type': 'collected_document', 'ref_id': 'doc-1'}]
    assert seen == {'ResolveCollectedDocument': [ref], 'RegisterMediaDiscovery': [ref]}
    assert snapshot['status'] == 'COMPLETED' and snapshot['unbound'] == ['dedup', 'enrich_ai', 'index']


@pytest.mark.asyncio
async def test_without_a_session_nothing_starts_and_a_malformed_event_is_skipped(pw_database, pw_temporal):
    doc_event(pw_database, 'doc-1')
    client = RecordingClient(pw_temporal)
    with pytest.raises(NoActiveAppSessionError):
        await make_starter(pw_database, client).run_once()
    assert client.calls == [] and [row[2] for row in outbox_rows(pw_database)] == [False]
    begin_session(pw_database)
    enqueue_event(pw_database, 'CollectedDocumentAvailable', 'bad', {'collected_document_id': ''})
    assert await make_starter(pw_database, client).run_once() == 1
    assert {row[0]: row[2] for row in outbox_rows(pw_database)} == {'doc-1': True, 'bad': False}


@pytest.mark.asyncio
async def test_the_enrichment_starter_run_forever_stops_at_once(pw_database, pw_temporal):
    begin_session(pw_database)
    doc_event(pw_database, 'doc-1')
    client = RecordingClient(pw_temporal)
    stop_event = asyncio.Event()
    task = asyncio.create_task(make_starter(pw_database, client).run_forever(stop_event, 3600))
    await wait_for_calls(client, 1)
    stop_event.set()
    await asyncio.wait_for(task, timeout=5)


URL = 'https://img.example.test/a.jpg'
OBSERVED_AT = '2026-10-27T01:02:03Z'
IMAGE_BYTES = b'pw-a3-image'
SHA = hashlib.sha256(IMAGE_BYTES).hexdigest()
CLAIMS = SimpleNamespace(stage_run_id='enrich:doc-1:media:r1', grant_id='grant-1', execution_generation=1, recovery_epoch='5')
PACKAGE = {'collected_document_id': 'doc-1', 'source_id': 'src-1', 'media_discoveries': [{'locator': URL, 'role': 'hero', 'media_kind': 'image'}]}


class StubFetcher:
    def __init__(self, *images: Any) -> None:
        self.images = images
        self.calls: list[tuple] = []

    def fetch_article_media(self, media_items: Any, *, source_ref: Any, article_ref: Any, event_ref: Any = None) -> MediaFetchBatch:
        self.calls.append((list(media_items), source_ref, article_ref))
        return MediaFetchBatch(tuple(self.images), ())


def staged(article_ref: str | None = 'doc-1', sha: str = SHA) -> StagedImage:
    entry = ProvenanceEntry('src-1', article_ref, None, URL, OBSERVED_AT, ProvenanceRelation.HERO_IMAGE)
    observation = DiscoveryObservation('disc-' + URL, MediaKind.IMAGE, entry, CanonicalFingerprint(sha) if sha else None, True)
    return StagedImage(observation, pathlib.Path('staged.jpg'), SHA, len(IMAGE_BYTES), 'image/jpeg', URL)


def request(ref_id: str = 'doc-1') -> dict[str, Any]:
    return {'input_refs': [{'ref_type': 'collected_document', 'ref_id': ref_id}], 'operation_key': 'op-1'}


def make_deps(manager: Any, db: Any, fetcher: Any, loader: Any = None) -> MediaDiscoveryDeps:
    @contextmanager
    def open_assets(workspace_id: str):
        with manager.borrow_connection() as connection:
            yield PostgresMediaAssetRepository(connection, workspace_id)

    return MediaDiscoveryDeps(db.workspace_id, loader or (lambda ref: PACKAGE), fetcher, open_assets)


def run_handler(manager: Any, db: Any, fetcher: Any, loader: Any = None) -> dict[str, Any]:
    return register_media_discovery(request(), CLAIMS, make_deps(manager, db, fetcher, loader), lambda: GRANT_NOW)


def test_the_downloaded_image_is_registered_with_provenance_and_no_usage_right(manager, pw_database):
    fetcher = StubFetcher(staged())
    result = run_handler(manager, pw_database, fetcher)
    assert validate_activity_result(result) == []
    assert fetcher.calls == [(PACKAGE['media_discoveries'], 'src-1', 'doc-1')]
    with manager.borrow_connection() as connection:
        asset = PostgresMediaAssetRepository(connection, pw_database.workspace_id).find_by_fingerprint(CanonicalFingerprint(SHA))
    assert asset.provenance == (ProvenanceEntry('src-1', 'doc-1', None, URL, OBSERVED_AT, ProvenanceRelation.HERO_IMAGE),)
    assert asset.fingerprint.value == SHA and asset.kind is MediaKind.IMAGE and asset.rights.status is RightsStatus.UNKNOWN
    assert result['output_refs'] == [{'ref_type': 'media_asset', 'ref_id': asset.media_asset_id}]
    assert result['metrics']['registered'] == 1
    assert scalar(pw_database, 'SELECT count(*) FROM controlplane.cp_media_usage') == 0


def test_replaying_the_same_request_registers_nothing_new(manager, pw_database):
    first = run_handler(manager, pw_database, StubFetcher(staged()))
    second = run_handler(manager, pw_database, StubFetcher(staged()))
    assert second['output_refs'] == first['output_refs']
    assert second['metrics']['duplicates'] == 1 and second['metrics']['registered'] == 0
    assert scalar(pw_database, 'SELECT count(*) FROM controlplane.cp_media_assets') == 1


def test_an_image_without_provenance_or_sha256_is_not_registered(manager, pw_database):
    result = run_handler(manager, pw_database, StubFetcher(staged(article_ref=None), staged(sha='')))
    assert result['disposition'] == 'succeeded' and result['output_refs'] == []
    assert result['metrics']['rejected'] == 2 and result['metrics']['registered'] == 0
    assert scalar(pw_database, 'SELECT count(*) FROM controlplane.cp_media_assets') == 0


def test_bad_requests_and_package_errors_are_distinct(manager, pw_database):
    fetcher = StubFetcher(staged())
    deps = make_deps(manager, pw_database, fetcher)
    with pytest.raises(ActivityRejected) as missing:
        register_media_discovery(request(), None, deps, lambda: GRANT_NOW)
    assert missing.value.code == MISSING_EXECUTION_GRANT
    for bad in ({'input_refs': []}, {'input_refs': [{'ref_type': 'other', 'ref_id': 'doc-1'}]}, {'input_refs': [{'ref_type': 'collected_document', 'ref_id': ' '}]}):
        with pytest.raises(ActivityRejected) as invalid:
            register_media_discovery(bad, CLAIMS, deps, lambda: GRANT_NOW)
        assert invalid.value.code == INVALID_ACTIVITY_REQUEST

    def not_found(ref: Any) -> Any:
        raise LookupError('missing')

    def unavailable(ref: Any) -> Any:
        raise OSError('down')

    gone = run_handler(manager, pw_database, fetcher, not_found)
    assert gone['disposition'] == 'failed' and gone['problem']['retryable'] is False and validate_activity_result(gone) == []
    down = run_handler(manager, pw_database, fetcher, unavailable)
    assert down['disposition'] == 'failed' and down['problem']['retryable'] is True
    assert fetcher.calls == []


def test_the_media_stage_is_bound_to_register_media_discovery():
    assert ENRICHMENT_STAGE_ACTIVITIES['media'] == ('RegisterMediaDiscovery',)


def test_the_handler_source_wraps_register_discovery_and_grants_no_right():
    text = HANDLER_SOURCE.read_text(encoding='utf-8')
    assert 'register_discovery' in text
    lowered = text.lower()
    for banned in ('from src.', 'import src', 'source_ingestion', 'fake', 'mock', 'memory', 'usage', 'rightsassessment', 'rightsstatus'):
        assert banned not in lowered, banned
