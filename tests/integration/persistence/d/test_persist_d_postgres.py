'''PERSIST-D: adapter PostgreSQL của creative trên PostgreSQL 18.6, cơ sở dữ liệu tạm riêng mỗi test.'''
from __future__ import annotations

import dataclasses
import os
import re
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.interfaces.outbox import IOutboxWriter
from controlplane.domain.interfaces.uow import IUnitOfWork
from controlplane.infrastructure.db.migration_runner import MigrationRunner
from controlplane.infrastructure.db.uow import TransactionManager
from creative.domain.analysis import AnalysisTrace, ContentAnalysis
from creative.domain.angles import StoryAngle, StoryAngleSet
from creative.domain.invocation import AIInvocationRecord, InvocationUsage
from creative.domain.output_metadata import OutputMetadata
from creative.domain.production_plan import ProductionPlan
from creative.domain.ref_resolver import ResourceRef
from creative.domain.script import ScriptSegment, ScriptVersion
from creative.domain.snapshot import build_production_snapshot
from creative.domain.variant import VariantValidationResult
from creative.persistence import PostgresCreativeUnitOfWork, TransactionAlreadyActiveError, TransactionNotActiveError
from creative.ports import repositories

REPO_ROOT = Path(__file__).resolve().parents[4]
MIGRATIONS_DIR = REPO_ROOT / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'migrations'
ADAPTER_DIR = REPO_ROOT / 'src' / 'creative' / 'persistence'
DATABASE_NAME = re.compile(r'^persist_d_[0-9a-f]+$')
WORKSPACE = '00000000-0000-0000-0000-00000000d001'
OTHER_WORKSPACE = '00000000-0000-0000-0000-00000000d002'
RECORD = ('workspace_id', 'record_key', 'revision', 'payload')
TABLES = {
    'cp_production_snapshots': ('snapshot_id', 'workspace_id', 'source_set_fingerprint', 'configuration_bundle_fingerprint', 'payload'),
    'cp_content_analyses': RECORD,
    'cp_story_angle_sets': RECORD + ('set_id',),
    'cp_story_angles': ('workspace_id', 'angle_id', 'set_id', 'payload'),
    'cp_script_versions': RECORD + ('script_version_id',),
    'cp_production_plans': RECORD + ('production_plan_id',),
    'cp_variant_validations': RECORD,
    'cp_output_metadata': RECORD,
    'cp_ai_invocation_records': RECORD,
    'cp_creative_receipts': ('workspace_id', 'idempotency_key', 'request_hash', 'aggregate_ref', 'aggregate_revision'),
}

@dataclasses.dataclass
class Database:
    name: str
    dsn: str


@pytest.fixture
def database():
    admin_dsn = os.environ.get('M2_TEST_PG_DSN')
    if not admin_dsn:
        pytest.fail('BLOCKED_EXTERNAL: M2_TEST_PG_DSN is required; no fallback is permitted.')
    name = f'persist_d_{uuid.uuid4().hex}'
    assert DATABASE_NAME.fullmatch(name)
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        if not admin.execute('SELECT rolcreatedb FROM pg_roles WHERE rolname = current_user').fetchone()[0]:
            pytest.fail('BLOCKED_EXTERNAL: M2_TEST_PG_DSN principal lacks CREATEDB.')
        assert 'PostgreSQL 18.6' in admin.execute('SELECT version()').fetchone()[0]
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    dsn = make_conninfo(admin_dsn, dbname=name)
    try:
        MigrationRunner(dsn, MIGRATIONS_DIR, is_test_env=True, expected_database_name=name).migrate_up()
        with psycopg.connect(dsn, autocommit=True) as connection:
            versions = connection.execute('SELECT version FROM controlplane.cp_schema_migrations ORDER BY version').fetchall()
            assert [row[0] for row in versions] == list(range(1, 20))
            for workspace in (WORKSPACE, OTHER_WORKSPACE):
                connection.execute('INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES (%s, %s, %s)', (workspace, 'w', 'ACTIVE'))
        yield Database(name, dsn)
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()', (name,))
            admin.execute(sql.SQL('DROP DATABASE IF EXISTS {}').format(sql.Identifier(name)))
            assert admin.execute('SELECT count(*) FROM pg_database WHERE datname = %s', (name,)).fetchone()[0] == 0


@pytest.fixture
def manager(database):
    created = TransactionManager(database.dsn, pool_max_size=4)
    yield created
    created.close()


class CountingManager:
    def __init__(self, inner):
        self.inner = inner
        self.borrowed = 0

    def borrow_connection(self):
        self.borrowed += 1
        return self.inner.borrow_connection()


def rows(database, query, params=()):
    with psycopg.connect(database.dsn, autocommit=True) as connection:
        return connection.execute(query, params).fetchall()


def count(database, table):
    return rows(database, f'SELECT count(*) FROM controlplane.{table}')[0][0]


def uow_for(manager, workspace=WORKSPACE):
    return PostgresCreativeUnitOfWork(manager, workspace_id=workspace)

def _ref(ref_id: str = 'a1') -> ResourceRef:
    return ResourceRef(workspace_id='ws-1', ref_type='article', ref_id=ref_id, revision_id='r1')


def _snapshot(snapshot_id: str = 'snap-1', ref_id: str = 'a1') -> object:
    return build_production_snapshot(
        snapshot_id=snapshot_id,
        production_mode='single_article',
        source_refs=[{'ref_type': 'article', 'ref_id': ref_id, 'revision_id': 'r1'}],
        index_revision_refs=[],
        configuration_revision_refs=[{'ref_type': 'config', 'ref_id': 'c1', 'revision_id': 'r1'}],
        content_ref_types=['article'],
        eligibility_reason='eligible',
        snapshot_timestamp='2026-10-19T00:00:00Z',
    )


def _analysis(analysis_id: str = 'analysis-1', revision: int = 1) -> ContentAnalysis:
    return ContentAnalysis(
        analysis_id=analysis_id,
        revision=revision,
        snapshot_id='snap-1',
        source_set_fingerprint='a' * 64,
        configuration_bundle_fingerprint='b' * 64,
        source_refs=(),
        topic='topic',
        entities=(),
        timeline=(),
        locations=(),
        facts=(),
        uncertainties=(),
        contradictions=(),
        event_relation='standalone',
        update_context='',
        risk_flags=(),
        narrative_opportunities=(),
        media_needs=(),
        trace=AnalysisTrace('p', 'm', _ref('prompt-1'), 'policy-1'),
    )


def _angle_set(set_id: str = 'set-1') -> StoryAngleSet:
    return StoryAngleSet(
        set_id=set_id,
        analysis_id='analysis-1',
        analysis_revision=1,
        requested_count=1,
        generation='initial',
        variation_policy_revision='vp-1',
        angles=(
            StoryAngle(
                angle_id='angle-1',
                title='T',
                summary='S',
                narrative_question='Q?',
                focus_entities=('city',),
                timeframe='2026',
                evidence_refs=(_ref(),),
                planned_inference_elements=(),
                planned_creative_elements=(),
                suitability='high',
                risk_flags=(),
            ),
        ),
        excluded=(),
    )


def _script(script_version_id: str = 'script-1', text: str = 'hello world') -> ScriptVersion:
    return ScriptVersion(
        script_version_id=script_version_id,
        language='en',
        hook_intent='hook',
        thumbnail_transition='cut',
        segments=(
            ScriptSegment(
                segment_id='s1',
                order=0,
                text=text,
                claim_mode='transition',
                scene_intent='intro',
                source_refs=(),
                disclosure=None,
                word_count=2,
                estimated_seconds=1.0,
            ),
        ),
        pronunciation_hints=(),
        speech_rate=2.0,
        estimated_duration_seconds=1.0,
    )


def _plan(production_plan_id: str = 'plan-1', fingerprint: str = 'c' * 64) -> ProductionPlan:
    return ProductionPlan(
        production_plan_id=production_plan_id,
        script_version_id='script-1',
        script_fingerprint='a' * 64,
        preset_revision_ref='preset-1',
        selection_fingerprint='b' * 64,
        timeline={},
        hook_placement={},
        thumbnail_overlay_intent='overlay',
        voice_profile_intent={},
        music_cues=(),
        sfx_cues=(),
        subtitle_style_intent={},
        allowed_fallbacks=(),
        output_metadata_ref=None,
        output_metadata_requirement='required',
        plan_fingerprint=fingerprint,
    )


def _validation(registry_revision: int = 3, valid: bool = True) -> VariantValidationResult:
    return VariantValidationResult(
        valid=valid,
        same_run_angle_distinct=True,
        exact_duplicate=False,
        distinct_factors=('voice',),
        nearest_prior_refs=(),
        reason_codes=('variant_distinct',),
        input_hashes={'candidate': 'a' * 64},
        registry_revision=registry_revision,
        phase='plan',
        variation_policy_revision='vp-1',
        own_reservation_id=None,
        output_hash=None,
    )


def _metadata(source_job_ref: str = 'job-1', revision: int = 1) -> OutputMetadata:
    return OutputMetadata(
        title='Title',
        caption='Caption',
        hashtags=('#one', '#two', '#three'),
        language='en',
        source_job_ref=source_job_ref,
        source_output_refs=('vv-1',),
        metadata_revision=revision,
    )


def _invocation(attempt: int = 1) -> AIInvocationRecord:
    return AIInvocationRecord(
        ai_role='analyst',
        provider_ref='p',
        model_ref='m',
        account_ref='a',
        route_revision='r1',
        prompt_revision='pr1',
        config_revision='c1',
        input_fingerprint='a' * 64,
        usage=InvocationUsage(1, 1, 'low'),
        latency_ms=5,
        attempt=attempt,
        fallback_path=('p',),
        validation_result='passed',
        output_fingerprint='b' * 64,
    )


def _receipt(key: str = 'k-1', workspace_id: str = 'ws-1') -> repositories.CommandReceipt:
    return repositories.CommandReceipt(
        workspace_id=workspace_id,
        idempotency_key=key,
        request_hash='a' * 64,
        aggregate_ref='snap-1',
        aggregate_revision=1,
    )

APPEND_CASES = {
    'analyses': (repositories.KIND_ANALYSIS, 'cp_content_analyses', 'analysis-1', lambda n: _analysis('analysis-1', n)),
    'angle_sets': (repositories.KIND_ANGLE_SET, 'cp_story_angle_sets', 'k-1', lambda n: _angle_set(f'set-{n}')),
    'scripts': (repositories.KIND_SCRIPT, 'cp_script_versions', 'k-1', lambda n: _script(f'script-{n}', f'hello world {n}')),
    'plans': (repositories.KIND_PLAN, 'cp_production_plans', 'k-1', lambda n: _plan(f'plan-{n}')),
    'variant_validations': (repositories.KIND_VARIANT_VALIDATION, 'cp_variant_validations', 'k-1', lambda n: _validation(n)),
    'output_metadata': (repositories.KIND_OUTPUT_METADATA, 'cp_output_metadata', 'job-1', lambda n: _metadata('job-1', n)),
    'invocations': (repositories.KIND_INVOCATION, 'cp_ai_invocation_records', 'k-1', lambda n: _invocation(n)),
}


def test_tables_and_columns_exist_in_the_real_schema(database):
    columns = {}
    for table, name in rows(database, "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'controlplane'"):
        columns.setdefault(table, set()).add(name)
    for table, names in TABLES.items():
        assert set(names) <= columns.get(table, set()), table
    outbox = {'event_id', 'workspace_id', 'event_name', 'aggregate_type', 'aggregate_id', 'aggregate_revision', 'producer', 'schema_version', 'payload', 'published'}
    assert outbox <= columns['cp_outbox_events']
    forward = [p for p in MIGRATIONS_DIR.glob('[0-9][0-9][0-9][0-9]_*.sql') if not p.name.endswith('.rollback.sql')]
    assert len(forward) == 19
    adapter_text = ' '.join(path.read_text(encoding='utf-8') for path in sorted(ADAPTER_DIR.rglob('*.py')))
    assert set(re.findall(r'cp_[a-z_]+', adapter_text)) == set(TABLES) | {'cp_outbox_events'}


def test_uow_exposes_ports_and_interfaces(manager):
    uow = uow_for(manager)
    assert isinstance(uow, IUnitOfWork)
    assert isinstance(uow.outbox, IOutboxWriter)
    assert isinstance(uow.snapshots, repositories.SnapshotRepository)
    assert isinstance(uow.receipts, repositories.ReceiptStore)
    protocols = {
        'analyses': repositories.AnalysisRepository,
        'angle_sets': repositories.AngleSetRepository,
        'scripts': repositories.ScriptRepository,
        'plans': repositories.PlanRepository,
        'variant_validations': repositories.VariantValidationRepository,
        'output_metadata': repositories.OutputMetadataRepository,
        'invocations': repositories.InvocationRecordRepository,
    }
    for attr, protocol in protocols.items():
        assert isinstance(getattr(uow, attr), protocol), attr
        assert isinstance(getattr(uow, attr), repositories.AppendOnlyRepository), attr

def test_snapshot_round_trip_and_immutability(database, manager):
    snapshot = _snapshot('snap-1')
    with uow_for(manager) as uow:
        assert uow.snapshots.get('snap-1') is None
        uow.snapshots.add(snapshot)
        assert uow.snapshots.get('snap-1') == snapshot
        with pytest.raises(TypeError):
            uow.snapshots.add('snap-1')
        uow.commit()
    with uow_for(manager) as uow:
        read = uow.snapshots.get('snap-1')
        assert read == snapshot and type(read) is type(snapshot)
        assert uow.snapshots.list_snapshots() == (snapshot,)
        with pytest.raises(repositories.DuplicateSnapshotError):
            uow.snapshots.add(snapshot)
        with pytest.raises(repositories.DuplicateSnapshotError):
            uow.snapshots.add(_snapshot('snap-1', ref_id='a2'))
        uow.snapshots.add(_snapshot('snap-2'))
        uow.commit()
    stored = rows(database, 'SELECT snapshot_id, payload FROM controlplane.cp_production_snapshots ORDER BY snapshot_id')
    assert [row[0] for row in stored] == ['snap-1', 'snap-2']
    assert stored[0][1]['source_refs'][0]['ref_id'] == 'a1'
    with uow_for(manager, OTHER_WORKSPACE) as uow:
        assert uow.snapshots.get('snap-1') is None
        assert uow.snapshots.list_snapshots() == ()


@pytest.mark.parametrize('attr', list(APPEND_CASES))
def test_append_round_trip_keeps_every_field(database, manager, attr):
    kind, table, key, make = APPEND_CASES[attr]
    first, second = make(1), make(2)
    with uow_for(manager) as uow:
        repo = getattr(uow, attr)
        written = repo.append(key, 1, first)
        repo.append(key, 2, second)
        uow.commit()
    assert written == repositories.StoredRecord(kind, key, 1, first)
    with uow_for(manager) as uow:
        repo = getattr(uow, attr)
        expected = (repositories.StoredRecord(kind, key, 1, first), repositories.StoredRecord(kind, key, 2, second))
        assert repo.revisions(key) == expected
        assert repo.latest(key) == expected[1]
        assert type(repo.latest(key).record) is type(second)
        assert repo.latest('khong-co') is None
        assert repo.revisions('khong-co') == ()
    assert count(database, table) == 2


def test_angle_rows_are_indexed_per_set(database, manager):
    with uow_for(manager) as uow:
        uow.angle_sets.append('k-1', 1, _angle_set('set-1'))
        uow.angle_sets.append('k-2', 1, _angle_set('set-2'))
        uow.commit()
    stored = rows(database, 'SELECT angle_id, set_id, payload FROM controlplane.cp_story_angles ORDER BY angle_id')
    assert [(row[0], row[1]) for row in stored] == [('set-1:angle-1', 'set-1'), ('set-2:angle-1', 'set-2')]
    assert stored[0][2]['angle_id'] == 'angle-1'

def test_append_accepts_only_latest_plus_one(database, manager):
    with uow_for(manager) as uow:
        with pytest.raises(RevisionConflictError) as skipped:
            uow.analyses.append('analysis-1', 2, _analysis('analysis-1', 2))
        assert skipped.value.current_revision == 0
        uow.analyses.append('analysis-1', 1, _analysis('analysis-1', 1))
        with pytest.raises(RevisionConflictError) as repeated:
            uow.analyses.append('analysis-1', 1, _analysis('analysis-1', 1))
        assert repeated.value.current_revision == 1
        with pytest.raises(RevisionConflictError) as jumped:
            uow.analyses.append('analysis-1', 3, _analysis('analysis-1', 3))
        assert jumped.value.current_revision == 1
        with pytest.raises(ValueError):
            uow.analyses.append('other', 1, _analysis('analysis-1', 1))
        with pytest.raises(TypeError):
            uow.scripts.append('k-1', 1, _analysis())
        with pytest.raises(ValueError):
            uow.scripts.append(' ', 1, _script())
        with pytest.raises(ValueError):
            uow.scripts.append('k-1', 0, _script())
        uow.commit()
    assert count(database, 'cp_content_analyses') == 1
    assert count(database, 'cp_script_versions') == 0


@pytest.mark.parametrize('attr', ['angle_sets', 'scripts', 'plans'])
def test_record_id_is_unique_per_workspace(database, manager, attr):
    kind, table, key, make = APPEND_CASES[attr]
    with uow_for(manager) as uow:
        repo = getattr(uow, attr)
        repo.append('k-1', 1, make(1))
        with pytest.raises(repositories.DuplicateRecordError):
            repo.append('k-2', 1, make(1))
        repo.append('k-3', 1, make(3))
        uow.commit()
    assert count(database, table) == 2
    with uow_for(manager) as uow:
        with pytest.raises(repositories.DuplicateRecordError):
            getattr(uow, attr).append('k-1', 2, make(1))
    with uow_for(manager, OTHER_WORKSPACE) as uow:
        getattr(uow, attr).append('k-1', 1, make(1))
        uow.commit()
    assert count(database, table) == 3

def test_receipt_store_is_unique_and_workspace_scoped(database, manager):
    receipt = _receipt('k-1', WORKSPACE)
    with uow_for(manager) as uow:
        assert uow.receipts.get(WORKSPACE, 'k-1') is None
        uow.receipts.put(receipt)
        with pytest.raises(repositories.DuplicateReceiptError):
            uow.receipts.put(dataclasses.replace(receipt, request_hash='f' * 64))
        with pytest.raises(TypeError):
            uow.receipts.put(object())
        with pytest.raises(ValueError):
            uow.receipts.put(_receipt('k-2', OTHER_WORKSPACE))
        with pytest.raises(ValueError):
            uow.receipts.get(OTHER_WORKSPACE, 'k-1')
        uow.commit()
    with uow_for(manager) as uow:
        assert uow.receipts.get(WORKSPACE, 'k-1') == receipt
    with uow_for(manager, OTHER_WORKSPACE) as uow:
        uow.receipts.put(_receipt('k-1', OTHER_WORKSPACE))
        uow.commit()
    assert count(database, 'cp_creative_receipts') == 2
    assert rows(database, 'SELECT request_hash FROM controlplane.cp_creative_receipts WHERE workspace_id = %s', (WORKSPACE,)) == [('a' * 64,)]


def test_history_tables_reject_update_and_delete(database, manager):
    with uow_for(manager) as uow:
        uow.snapshots.add(_snapshot('snap-1'))
        for attr, (kind, table, key, make) in APPEND_CASES.items():
            getattr(uow, attr).append(key, 1, make(1))
        uow.receipts.put(_receipt('k-1', WORKSPACE))
        for name in ('snapshots', 'receipts', *APPEND_CASES):
            members = dir(getattr(uow, name))
            assert [m for m in members if m.startswith(('update', 'delete', 'remove', 'replace', 'overwrite'))] == []
        uow.commit()
    with psycopg.connect(database.dsn, autocommit=True) as connection:
        for table in TABLES:
            before = connection.execute(f'SELECT count(*) FROM controlplane.{table}').fetchone()[0]
            assert before >= 1, table
            for statement in (f'UPDATE controlplane.{table} SET workspace_id = workspace_id', f'DELETE FROM controlplane.{table}'):
                with pytest.raises(psycopg.errors.RaiseException):
                    connection.execute(statement)
            assert connection.execute(f'SELECT count(*) FROM controlplane.{table}').fetchone()[0] == before

def snapshot_event(uow, snapshot, revision=1):
    context = repositories.EventContext(workspace_id=WORKSPACE, correlation_id='corr-1', actor='worker-d', occurred_at='2026-10-19T00:00:00Z', recovery_epoch='epoch-0001', event_id='evt-1', message_id='msg-1')
    event = repositories.build_production_snapshot_committed(context, aggregate_id=snapshot.snapshot_id, aggregate_revision=revision, snapshot=snapshot)
    dedup = repositories.deduplication_id_for(event)
    return uow.outbox.append_event(event.event_name, event.aggregate_id, dict(event.payload), dedup), dedup


def test_commit_writes_records_and_outbox_on_one_connection(database, manager):
    counting = CountingManager(manager)
    snapshot = _snapshot('snap-1')
    uow = PostgresCreativeUnitOfWork(counting, workspace_id=WORKSPACE)
    with uow:
        uow.snapshots.add(snapshot)
        uow.analyses.append('analysis-1', 1, _analysis())
        uow.receipts.put(_receipt('k-1', WORKSPACE))
        event_id, dedup = snapshot_event(uow, snapshot)
        assert count(database, 'cp_production_snapshots') == 0
        assert count(database, 'cp_outbox_events') == 0
        uow.commit()
    assert counting.borrowed == 1
    assert dedup == f'{WORKSPACE}:ProductionSnapshotCommitted:snap-1:1'
    assert event_id == str(uuid.uuid5(uuid.NAMESPACE_URL, dedup))
    assert count(database, 'cp_production_snapshots') == 1
    assert count(database, 'cp_content_analyses') == 1
    assert count(database, 'cp_creative_receipts') == 1
    stored = rows(database, 'SELECT event_id::text, workspace_id::text, event_name, aggregate_type, aggregate_id, aggregate_revision, producer, schema_version, recovery_epoch, published, payload FROM controlplane.cp_outbox_events')
    assert len(stored) == 1
    assert stored[0][:9] == (event_id, WORKSPACE, 'ProductionSnapshotCommitted', 'ProductionSnapshot', 'snap-1', 1, 'D', 1, None)
    assert stored[0][9] is False and stored[0][10]['snapshot_id'] == 'snap-1'


def test_rollback_discards_records_and_outbox(database, manager):
    snapshot = _snapshot('snap-1')
    with pytest.raises(RuntimeError):
        with uow_for(manager) as uow:
            uow.snapshots.add(snapshot)
            snapshot_event(uow, snapshot)
            raise RuntimeError('boom')
    with uow_for(manager) as uow:
        uow.snapshots.add(snapshot)
        snapshot_event(uow, snapshot)
    uow = uow_for(manager)
    uow.begin()
    uow.snapshots.add(snapshot)
    snapshot_event(uow, snapshot)
    uow.rollback()
    assert uow.active is False
    with pytest.raises(ValueError):
        with uow_for(manager) as uow:
            uow.snapshots.add(snapshot)
            uow.outbox.append_event('ProductionSnapshotCommitted', 'snap-1', {'secret': 'x'}, f'{WORKSPACE}:ProductionSnapshotCommitted:snap-1:1')
            uow.commit()
    assert count(database, 'cp_production_snapshots') == 0
    assert count(database, 'cp_outbox_events') == 0
    with uow_for(manager) as uow:
        uow.snapshots.add(snapshot)
        snapshot_event(uow, snapshot)
        uow.commit()
    assert count(database, 'cp_production_snapshots') == 1
    assert count(database, 'cp_outbox_events') == 1

def test_outbox_deduplicates_and_stays_in_workspace(database, manager):
    snapshot = _snapshot('snap-1')
    with uow_for(manager) as uow:
        first, dedup = snapshot_event(uow, snapshot)
        assert snapshot_event(uow, snapshot)[0] == first
        uow.commit()
    with uow_for(manager) as uow:
        assert snapshot_event(uow, snapshot)[0] == first
        uow.commit()
    assert count(database, 'cp_outbox_events') == 1
    with uow_for(manager, OTHER_WORKSPACE) as uow:
        with pytest.raises(ValueError):
            uow.outbox.append_event('ProductionSnapshotCommitted', 'snap-1', {'snapshot_id': 'snap-1'}, dedup)
    bad_calls = (
        ('NoSuchEvent', 'snap-1', {'a': 'b'}, f'{WORKSPACE}:NoSuchEvent:snap-1:1'),
        ('ProductionSnapshotCommitted', 'snap-1', {'a': 'b'}, 'd-1'),
        ('ProductionSnapshotCommitted', 'snap-1', ['a'], dedup),
        ('ProductionSnapshotCommitted', ' ', {'a': 'b'}, dedup),
    )
    with uow_for(manager) as uow:
        for args in bad_calls:
            with pytest.raises(ValueError):
                uow.outbox.append_event(*args)
    assert count(database, 'cp_outbox_events') == 1


def test_uow_state_machine_and_workspace_validation(database, manager):
    uow = uow_for(manager)
    assert uow.active is False
    with pytest.raises(TransactionNotActiveError):
        uow.snapshots.get('snap-1')
    with pytest.raises(TransactionNotActiveError):
        uow.commit()
    with pytest.raises(TransactionNotActiveError):
        uow.rollback()
    uow.begin()
    assert uow.active is True
    with pytest.raises(TransactionAlreadyActiveError):
        uow.begin()
    uow.snapshots.add(_snapshot('snap-1'))
    uow.commit()
    assert uow.active is False
    with pytest.raises(TransactionNotActiveError):
        uow.snapshots.add(_snapshot('snap-2'))
    for _ in range(8):
        with uow:
            assert uow.snapshots.get('snap-1') is not None
    for bad in ('', 'not-a-uuid', None, 7):
        with pytest.raises(ValueError):
            PostgresCreativeUnitOfWork(manager, workspace_id=bad)
    assert count(database, 'cp_production_snapshots') == 1


def test_adapter_source_has_no_ddl_and_no_src_prefix():
    files = sorted(ADAPTER_DIR.rglob('*.py'))
    assert {path.name for path in files} >= {'__init__.py', 'codec.py', 'outbox.py', 'repositories.py', 'uow.py'}
    text = ' '.join(path.read_text(encoding='utf-8') for path in files)
    for banned in ('CREATE TABLE', 'ALTER TABLE', 'DROP TABLE', 'from src.', 'import src'):
        assert banned not in text, banned