'''PERSIST-F: kiểm adapter PostgreSQL của render trên PostgreSQL 18.6, cơ sở dữ liệu tạm riêng mỗi test.'''
from __future__ import annotations

import dataclasses
import datetime
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import uuid

import psycopg
import psycopg.errors
import pytest

from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.statemachine import OperationState
from controlplane.infrastructure.db.migration_runner import MigrationRunner
from controlplane.infrastructure.db.uow import TransactionManager
from render.application.package_pipeline import CommandReceipt, CommandTrace
from render.domain.package_contract import validate_render_package_payload
from render.domain.quality_report import GATE_KINDS, GateKind, GateName, GateResult, build_quality_report
from render.domain.render_attempt import fail_attempt, mark_outcome_unknown, prepare_attempt, start_attempt, succeed_attempt
from render.domain.render_command import RenderCommandSpec, ToolIdentity
from render.domain.validate_package import PackageValidationReport, _compute_report_id, validate_render_package
from render.persistence import PostgresRenderUnitOfWork, UnitOfWorkAlreadyActiveError, UnitOfWorkNotActiveError
from render.ports.repositories import KIND_ATTEMPT, KIND_PACKAGE, KIND_QUALITY_REPORT, DuplicateRecordError, ImmutableFieldError, StoredRecord

REPO_ROOT = Path(__file__).resolve().parents[4]
MIGRATIONS_DIR = REPO_ROOT / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'migrations'
PERSISTENCE_DIR = REPO_ROOT / 'src' / 'render' / 'persistence'
PACKAGE_FIXTURE = REPO_ROOT / 'tests' / 'fixtures' / 'contracts' / 'f-render-package' / 'payloads.json'

try:
    _port = subprocess.check_output(
        ['docker', 'port', 'ai-auto-video-m2-pg', '5432/tcp'],
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip().split(':')[-1]
    _DEFAULT_DSN = f'postgresql://m2test:m2test@127.0.0.1:{_port}/postgres'
except Exception:
    _DEFAULT_DSN = 'postgresql://m2test:m2test@127.0.0.1:57027/postgres'
PG_DSN = os.environ.get('M2_TEST_PG_DSN', _DEFAULT_DSN)


def add_workspace(dsn: str) -> str:
    workspace_id = uuid.uuid4()
    with psycopg.connect(dsn, autocommit=True) as seed:
        seed.execute(
            'INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES (%s, %s, %s)',
            (workspace_id, 'w', 'ACTIVE'),
        )
    return str(workspace_id)


@pytest.fixture
def db():
    name = f'persist_f_{uuid.uuid4().hex[:8]}'
    admin = psycopg.connect(PG_DSN, autocommit=True)
    try:
        assert 'PostgreSQL 18.6' in admin.execute('SELECT version()').fetchone()[0]
        admin.execute(f'CREATE DATABASE {name}')
        dsn = PG_DSN.rsplit('/', 1)[0] + f'/{name}'
        MigrationRunner(dsn, MIGRATIONS_DIR, is_test_env=True, expected_database_name=name).migrate_up()
        with psycopg.connect(dsn, autocommit=True) as connection:
            assert [r[0] for r in connection.execute('SELECT version FROM controlplane.cp_schema_migrations ORDER BY version').fetchall()] == list(range(1, 20))
        yield dsn, add_workspace(dsn)
    finally:
        admin.execute(f'DROP DATABASE IF EXISTS {name} WITH (FORCE)')
        admin.close()


@pytest.fixture
def manager(db):
    tm = TransactionManager(db[0], pool_max_size=4)
    yield tm
    tm.close()


def new_uow(manager, ws):
    return PostgresRenderUnitOfWork(manager, workspace_id=ws, correlation_id='corr-1', actor='tester')


def count(dsn: str, table: str, where: str = 'true', params: tuple = ()) -> int:
    with psycopg.connect(dsn, autocommit=True) as conn:
        return conn.execute(f'SELECT count(*) FROM controlplane.{table} WHERE {where}', params).fetchone()[0]


def assert_rejected(dsn: str, statement: str, params: tuple = ()) -> None:
    with psycopg.connect(dsn) as conn:
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute(statement, params)
        conn.rollback()


def test_schema_matches_render_migration(db):
    dsn = db[0]
    expected_tables = {
        'cp_render_preset_revisions': {'workspace_id', 'record_key', 'revision', 'payload'},
        'cp_package_validation_reports': {'workspace_id', 'record_key', 'revision', 'payload'},
        'cp_quality_reports': {'workspace_id', 'record_key', 'revision', 'payload'},
        'cp_quality_gate_results': {'workspace_id', 'record_key', 'revision', 'payload'},
        'cp_render_packages': {'workspace_id', 'record_key', 'revision', 'payload', 'package_fingerprint'},
        'cp_render_attempts': {'workspace_id', 'record_key', 'revision', 'payload', 'render_attempt_id'},
        'cp_video_outputs': {'output_artifact_ref', 'workspace_id', 'render_attempt_id', 'payload'},
        'cp_render_operation_receipts': {'workspace_id', 'idempotency_key', 'request_hash', 'aggregate_ref', 'aggregate_revision'},
        'cp_audit_records': {'audit_id', 'workspace_id', 'actor_ref', 'action', 'resource_ref', 'occurred_at', 'correlation_id', 'outcome', 'redacted_reason'},
        'cp_outbox_events': {'event_id', 'workspace_id', 'event_name', 'aggregate_type', 'aggregate_id', 'producer', 'payload'},
    }
    with psycopg.connect(dsn, autocommit=True) as conn:
        for table, expected_cols in expected_tables.items():
            rows = conn.execute(
                'SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s',
                ('controlplane', table),
            ).fetchall()
            cols = {r[0] for r in rows}
            assert expected_cols <= cols, f'Table {table} missing expected columns: {expected_cols - cols}'

        indexes = {
            r[0]
            for r in conn.execute(
                'SELECT indexname FROM pg_indexes WHERE schemaname = %s',
                ('controlplane',),
            ).fetchall()
        }
        assert 'cp_render_packages_fingerprint_unique' in indexes
        assert 'cp_render_attempts_attempt_id_unique' in indexes


CANARY = 'CANARY-7f3a9c-SECRET'
NOW = datetime(2026, 10, 19, 8, 0, 0, tzinfo=timezone.utc)
OUTPUT_REF = 'artifact/render/attempt-1/out.mp4'
SECOND_REF = 'artifact/render/attempt-2/out.mp4'
THIRD_REF = 'artifact/render/attempt-3/out.mp4'


def at(seconds: int) -> datetime:
    return NOW + timedelta(seconds=seconds)


def spec() -> RenderCommandSpec:
    return RenderCommandSpec(
        kind='render',
        argv=('C:/tools/ffmpeg.exe', '-i', f'C:/staging/{CANARY}/a.mp4'),
        redacted_argv=('{:tool}', '-i', '{asset:0}'),
        spec_fingerprint='f' * 64,
        tool_identity=ToolIdentity(name='ffmpeg', version='6.1', build='test-build', executable='C:/tools/ffmpeg.exe'),
    )


def prepared(attempt_id: str = 'attempt-1', output: str = OUTPUT_REF, fingerprint: str = 'a' * 64):
    return prepare_attempt(
        render_attempt_id=attempt_id,
        package_fingerprint=fingerprint,
        output_artifact_ref=output,
        command_spec=spec(),
        receipt_ref='receipt-1',
    )


def started(**kw):
    return start_attempt(prepared(**kw), expected_revision=0, started_at=at(0))


def succeeded(**kw):
    return succeed_attempt(
        started(**kw),
        expected_revision=1,
        finished_at=at(60),
        wall_time_ms=60000,
        warnings=[f'password={CANARY}', f'note {CANARY}'],
        secret_values=[CANARY],
    )


def failed(**kw):
    return fail_attempt(started(**kw), expected_revision=1, finished_at=at(30), error='ffmpeg exited with code 1')


def unknown(**kw):
    return mark_outcome_unknown(started(**kw), expected_revision=1, reason='worker timeout after render')


def report(failing=()):
    hard = [n for n in GateName if GATE_KINDS[n] is GateKind.HARD]
    results = [
        GateResult(
            gate=n,
            status='failed' if n in failing else 'passed',
            reason='gate_failed' if n in failing else None,
        )
        for n in hard
    ]
    return build_quality_report(results, {GateName.INFERENCE_DISCLOSURE_PRESENT: False})


def package(pid: str = 'pkg-1', char: str = 'a'):
    raw = json.loads(PACKAGE_FIXTURE.read_text(encoding='utf-8'))['entities']['RenderPackage']['valid'][0]
    return dataclasses.replace(
        validate_render_package_payload(raw),
        render_package_id=pid,
        package_fingerprint=char * 64,
    )


def receipt(ws: str, command: str = 'ResolveRenderPackage', key: str = 'op-1', report_id: str | None = None) -> CommandReceipt:
    return CommandReceipt(
        command=command,
        workspace_id=ws,
        operation_key=key,
        request_hash='h' * 64,
        receipt_ref='receipt-1',
        state=OperationState.SUCCEEDED,
        revision=2,
        render_package_id='pkg-1',
        package_fingerprint='a' * 64,
        report_id=report_id,
    )


def trace(ws: str, key: str = 'op-1', outcome: str = 'package_resolved') -> CommandTrace:
    return CommandTrace(
        sequence=0,
        command='ResolveRenderPackage',
        workspace_id=ws,
        operation_key=key,
        correlation_id='corr-1',
        actor='tester',
        occurred_at='2026-10-19T08:00:00+00:00',
        receipt_ref='receipt-1',
        grant_id='grant-1',
        execution_generation=1,
        subject_ref='pkg-1',
        outcome=outcome,
    )


def test_package_round_trip_and_reads_outside_uow(db, manager):
    ws = db[1]
    pkg = package()
    uow = new_uow(manager, ws)
    with uow:
        stored = uow.renders.append(KIND_PACKAGE, 'pkg-1', 1, pkg)
        assert stored == StoredRecord(KIND_PACKAGE, 'pkg-1', 1, pkg)
        assert uow.renders.latest(KIND_PACKAGE, 'pkg-1') == stored
        uow.commit()

    assert not uow.active
    latest = uow.renders.latest(KIND_PACKAGE, 'pkg-1')
    assert latest == stored
    assert uow.renders.revisions(KIND_PACKAGE, 'pkg-1') == (stored,)
    assert uow.renders.latest(KIND_PACKAGE, 'none') is None
    assert uow.renders.revisions(KIND_PACKAGE, 'none') == ()
    assert count(db[0], 'cp_render_packages') == 1
    with psycopg.connect(db[0], autocommit=True) as conn:
        fp_col = conn.execute('SELECT package_fingerprint FROM controlplane.cp_render_packages WHERE record_key = %s', ('pkg-1',)).fetchone()[0]
        assert fp_col == 'a' * 64


def test_package_revision_two_keeps_history(db, manager):
    ws = db[1]
    pkg1 = package()
    pkg2 = dataclasses.replace(package(), output_metadata_revision='out-meta-v2')
    with new_uow(manager, ws) as uow:
        s1 = uow.renders.append(KIND_PACKAGE, 'pkg-1', 1, pkg1)
        s2 = uow.renders.append(KIND_PACKAGE, 'pkg-1', 2, pkg2)
        uow.commit()

    uow2 = new_uow(manager, ws)
    revs = uow2.renders.revisions(KIND_PACKAGE, 'pkg-1')
    assert len(revs) == 2
    assert revs[0] == s1
    assert revs[1] == s2
    assert uow2.renders.latest(KIND_PACKAGE, 'pkg-1').revision == 2

    with new_uow(manager, ws) as uow3:
        with pytest.raises(RevisionConflictError):
            uow3.renders.append(KIND_PACKAGE, 'pkg-1', 4, pkg2)

    with new_uow(manager, ws) as uow4:
        with pytest.raises(RevisionConflictError):
            uow4.renders.append(KIND_PACKAGE, 'pkg-1', 1, pkg1)


def test_package_input_validation(db, manager):
    ws = db[1]
    with new_uow(manager, ws) as uow:
        with pytest.raises(ValueError):
            uow.renders.append(KIND_PACKAGE, 'other', 1, package())
        with pytest.raises(ValueError):
            uow.renders.append('nope', 'pkg-1', 1, package())
        with pytest.raises(TypeError):
            uow.renders.append(KIND_PACKAGE, 'pkg-1', 1, prepared())
        with pytest.raises(ValueError):
            uow.renders.append(KIND_PACKAGE, 'pkg-1', 0, package())
        with pytest.raises(ValueError):
            uow.renders.append(KIND_PACKAGE, 'pkg-1', True, package())
        with pytest.raises(ValueError):
            uow.renders.append(KIND_PACKAGE, '', 1, package())
        uow.commit()
    assert count(db[0], 'cp_render_packages') == 0


def test_package_fingerprint_unique_and_immutable(db, manager):
    ws = db[1]
    with new_uow(manager, ws) as uow:
        uow.renders.append(KIND_PACKAGE, 'pkg-1', 1, package(pid='pkg-1', char='a'))
        with pytest.raises(DuplicateRecordError):
            uow.renders.append(KIND_PACKAGE, 'pkg-2', 1, package(pid='pkg-2', char='a'))
        uow.renders.append(KIND_PACKAGE, 'pkg-3', 1, package(pid='pkg-3', char='c'))
        uow.commit()
    assert count(db[0], 'cp_render_packages') == 2

    with new_uow(manager, ws) as uow:
        pkg_changed_fp = dataclasses.replace(package(pid='pkg-1', char='a'), package_fingerprint='b' * 64)
        with pytest.raises(ImmutableFieldError):
            uow.renders.append(KIND_PACKAGE, 'pkg-1', 2, pkg_changed_fp)

    ws2 = add_workspace(db[0])
    with new_uow(manager, ws2) as uow2:
        with pytest.raises(DuplicateRecordError):
            uow2.renders.append(KIND_PACKAGE, 'pkg-9', 1, package(pid='pkg-9', char='a'))


def test_attempt_round_trip_through_states(db, manager):
    ws = db[1]
    a1_prep = prepared()
    a1_start = started()
    a1_succ = succeeded()
    a2_fail = failed(attempt_id='attempt-2', output=SECOND_REF)
    a3_unk = unknown(attempt_id='attempt-3', output=THIRD_REF)

    with new_uow(manager, ws) as uow:
        uow.renders.append(KIND_ATTEMPT, 'attempt-1', 1, a1_prep)
        uow.renders.append(KIND_ATTEMPT, 'attempt-1', 2, a1_start)
        uow.renders.append(KIND_ATTEMPT, 'attempt-1', 3, a1_succ)
        uow.renders.append(KIND_ATTEMPT, 'attempt-2', 1, a2_fail)
        uow.renders.append(KIND_ATTEMPT, 'attempt-3', 1, a3_unk)
        uow.commit()

    fresh_manager = TransactionManager(db[0], pool_max_size=2)
    try:
        fresh_uow = new_uow(fresh_manager, ws)
        rec1 = fresh_uow.renders.latest(KIND_ATTEMPT, 'attempt-1')
        assert rec1.record == a1_succ
        revs1 = fresh_uow.renders.revisions(KIND_ATTEMPT, 'attempt-1')
        assert len(revs1) == 3
        assert revs1[0].revision == 1 and revs1[0].record == a1_prep
        assert revs1[1].revision == 2 and revs1[1].record == a1_start
        assert revs1[2].revision == 3 and revs1[2].record == a1_succ

        rec2 = fresh_uow.renders.latest(KIND_ATTEMPT, 'attempt-2')
        assert rec2.record == a2_fail
        assert rec2.record.receipt_state == OperationState.FAILED

        rec3 = fresh_uow.renders.latest(KIND_ATTEMPT, 'attempt-3')
        assert rec3.record == a3_unk
        assert rec3.record.receipt_state == OperationState.OUTCOME_UNKNOWN
    finally:
        fresh_manager.close()


def test_attempt_key_and_uniques(db, manager):
    ws = db[1]
    with new_uow(manager, ws) as uow:
        with pytest.raises(ValueError):
            uow.renders.append(KIND_ATTEMPT, 'x', 1, prepared(attempt_id='attempt-1'))
        uow.renders.append(KIND_ATTEMPT, 'attempt-1', 1, prepared(attempt_id='attempt-1', output=OUTPUT_REF))
        with pytest.raises(DuplicateRecordError):
            uow.renders.append(KIND_ATTEMPT, 'attempt-2', 1, prepared(attempt_id='attempt-2', output=OUTPUT_REF))
        uow.renders.append(KIND_ATTEMPT, 'attempt-2', 1, prepared(attempt_id='attempt-2', output=SECOND_REF))
        uow.commit()

    ws2 = add_workspace(db[0])
    with new_uow(manager, ws2) as uow2:
        with pytest.raises(DuplicateRecordError):
            uow2.renders.append(KIND_ATTEMPT, 'attempt-1', 1, prepared(attempt_id='attempt-1', output=THIRD_REF))
    assert count(db[0], 'cp_video_outputs') == 2


def test_attempt_identity_fields_are_immutable(db, manager):
    ws = db[1]
    with new_uow(manager, ws) as uow:
        uow.renders.append(KIND_ATTEMPT, 'attempt-1', 1, prepared())
        uow.commit()

    with new_uow(manager, ws) as uow:
        bad_out = dataclasses.replace(started(), output_artifact_ref=SECOND_REF)
        with pytest.raises(ImmutableFieldError):
            uow.renders.append(KIND_ATTEMPT, 'attempt-1', 2, bad_out)
        bad_fp = dataclasses.replace(started(), package_fingerprint='b' * 64)
        with pytest.raises(ImmutableFieldError):
            uow.renders.append(KIND_ATTEMPT, 'attempt-1', 2, bad_fp)
        uow.renders.append(KIND_ATTEMPT, 'attempt-1', 2, started())
        uow.commit()


def test_video_output_row_written_once_per_attempt(db, manager):
    ws = db[1]
    with new_uow(manager, ws) as uow:
        uow.renders.append(KIND_ATTEMPT, 'attempt-1', 1, prepared())
        uow.renders.append(KIND_ATTEMPT, 'attempt-1', 2, started())
        uow.renders.append(KIND_ATTEMPT, 'attempt-1', 3, succeeded())
        uow.commit()
    assert count(db[0], 'cp_video_outputs') == 1
    with psycopg.connect(db[0], autocommit=True) as conn:
        row = conn.execute('SELECT output_artifact_ref, render_attempt_id FROM controlplane.cp_video_outputs').fetchone()
        assert row == (OUTPUT_REF, 'attempt-1')
    assert count(db[0], 'cp_render_attempts') == 3


def test_quality_report_round_trip(db, manager):
    ws = db[1]
    rev1 = report()
    rev2 = report(failing=(GateName.FILE_PLAYABLE,))
    with new_uow(manager, ws) as uow:
        uow.renders.append(KIND_QUALITY_REPORT, 'qr-1', 1, rev1)
        uow.renders.append(KIND_QUALITY_REPORT, 'qr-1', 2, rev2)
        uow.commit()

    fresh_manager = TransactionManager(db[0], pool_max_size=2)
    try:
        fresh_uow = new_uow(fresh_manager, ws)
        latest = fresh_uow.renders.latest(KIND_QUALITY_REPORT, 'qr-1')
        assert latest.record == rev2
        assert latest.record.passed is False
        revs = fresh_uow.renders.revisions(KIND_QUALITY_REPORT, 'qr-1')
        assert len(revs) == 2
        assert revs[0].revision == 1 and revs[0].record == rev1 and revs[0].record.passed is True
        assert revs[1].revision == 2 and revs[1].record == rev2 and revs[1].record.passed is False
    finally:
        fresh_manager.close()

    assert count(db[0], 'cp_quality_reports') == 2
    assert count(db[0], 'cp_quality_gate_results') == 2
    with psycopg.connect(db[0], autocommit=True) as conn:
        rows = conn.execute('SELECT payload FROM controlplane.cp_quality_gate_results').fetchall()
        for r in rows:
            assert 'gates' in r[0] and len(r[0]['gates']) == 13

    with new_uow(manager, ws) as uow:
        with pytest.raises(TypeError):
            uow.renders.append(KIND_QUALITY_REPORT, 'qr-2', 1, package())


def test_validation_reports_are_append_only_by_fingerprint(db, manager):
    ws = db[1]
    first = validate_render_package(package())
    second = PackageValidationReport(
        package_fingerprint='a' * 64,
        findings=(),
        passed=True,
        report_id=_compute_report_id('a' * 64, ()),
    )
    assert first.report_id != second.report_id, 'first and second report_id must differ'

    uow = new_uow(manager, ws)
    with uow:
        r1 = uow.reports.append(first)
        assert r1 == 1
        r1_dup = uow.reports.append(first)
        assert r1_dup == 1
        r2 = uow.reports.append(second)
        assert r2 == 2
        uow.commit()

    assert not uow.active
    assert uow.reports.latest('a' * 64) == second
    assert uow.reports.revisions('a' * 64) == (first, second)
    assert uow.reports.by_id('a' * 64, first.report_id) == first
    assert uow.reports.by_id('a' * 64, 'missing') is None
    assert uow.reports.latest('c' * 64) is None
    assert count(db[0], 'cp_package_validation_reports') == 2

    with uow:
        with pytest.raises(TypeError):
            uow.reports.append('not-a-report')


def test_receipts_round_trip_and_unique(db, manager):
    ws = db[1]
    r1 = receipt(ws)
    r2 = receipt(ws, command='ValidateRenderPackage', report_id='rep-1')
    uow = new_uow(manager, ws)
    with uow:
        uow.receipts.add(r1)
        uow.receipts.add(r2)
        with pytest.raises(DuplicateRecordError):
            uow.receipts.add(r1)
        uow.commit()

    assert not uow.active
    assert uow.receipts.get(ws, 'ResolveRenderPackage', 'op-1') == r1
    res2 = uow.receipts.get(ws, 'ValidateRenderPackage', 'op-1')
    assert res2 == r2
    assert res2.report_id == 'rep-1'
    assert res2.state == OperationState.SUCCEEDED
    assert uow.receipts.get(ws, 'ResolveRenderPackage', 'none') is None
    records = uow.receipts.records()
    assert len(records) == 2
    assert set(records) == {r1, r2}

    with psycopg.connect(db[0], autocommit=True) as conn:
        row = conn.execute(
            'SELECT idempotency_key, request_hash, aggregate_revision FROM controlplane.cp_render_operation_receipts WHERE workspace_id = %s AND idempotency_key = %s',
            (ws, 'ResolveRenderPackage:op-1'),
        ).fetchone()
        assert row == ('ResolveRenderPackage:op-1', 'h' * 64, 2)


def test_traces_get_a_sequence_and_persist(db, manager):
    ws = db[1]
    t1 = trace(ws, key='op-1', outcome='package_resolved')
    t2 = trace(ws, key='op-2', outcome='validation_failed')
    uow = new_uow(manager, ws)
    with uow:
        uow.traces.append(t1)
        uow.traces.append(t2)
        uow.commit()

    records = uow.traces.records()
    assert len(records) == 2
    assert records[0].sequence == 1
    assert records[1].sequence == 2
    assert dataclasses.replace(records[0], sequence=0) == t1
    assert dataclasses.replace(records[1], sequence=0) == t2

    assert count(db[0], 'cp_audit_records', where="starts_with(audit_id, 'render-trace:')") == 2
    with psycopg.connect(db[0], autocommit=True) as conn:
        rows = dict(conn.execute(
            "SELECT action || ':' || (redacted_reason::jsonb->>'operation_key'), outcome FROM controlplane.cp_audit_records WHERE workspace_id = %s AND starts_with(audit_id, 'render-trace:')",
            (ws,),
        ).fetchall())
        assert rows.get('ResolveRenderPackage:op-1') == 'succeeded'
        assert rows.get('ResolveRenderPackage:op-2') == 'failed'


def test_attempt_index_lists_attempt_ids_by_package_fingerprint(db, manager):
    ws = db[1]
    fp_a = 'a' * 64
    fp_b = 'b' * 64
    fp_c = 'c' * 64
    att1 = prepared(attempt_id='attempt-1', output=OUTPUT_REF, fingerprint=fp_a)
    att2 = prepared(attempt_id='attempt-2', output=SECOND_REF, fingerprint=fp_a)
    att3 = prepared(attempt_id='attempt-3', output=THIRD_REF, fingerprint=fp_b)

    uow = new_uow(manager, ws)
    with uow:
        uow.renders.append(KIND_ATTEMPT, 'attempt-1', 1, att1)
        uow.renders.append(KIND_ATTEMPT, 'attempt-2', 1, att2)
        uow.renders.append(KIND_ATTEMPT, 'attempt-3', 1, att3)
        uow.attempt_index.add(fp_a, 'attempt-1')
        uow.attempt_index.add(fp_a, 'attempt-2')
        uow.attempt_index.add(fp_b, 'attempt-3')
        uow.commit()

    assert not uow.active
    assert uow.attempt_index.ids(fp_a) == ('attempt-1', 'attempt-2')
    assert uow.attempt_index.ids(fp_b) == ('attempt-3',)
    assert uow.attempt_index.ids(fp_c) == ()

    with pytest.raises(UnitOfWorkNotActiveError):
        uow.attempt_index.add(fp_a, 'attempt-4')


def test_history_tables_reject_update_and_delete(db, manager):
    ws = db[1]
    dsn = db[0]
    with new_uow(manager, ws) as uow:
        uow.renders.append(KIND_PACKAGE, 'pkg-1', 1, package())
        uow.renders.append(KIND_ATTEMPT, 'attempt-1', 1, prepared())
        uow.renders.append(KIND_QUALITY_REPORT, 'qr-1', 1, report())
        uow.reports.append(validate_render_package(package()))
        uow.receipts.add(receipt(ws))
        uow.commit()

    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            'INSERT INTO controlplane.cp_render_preset_revisions (workspace_id, record_key, revision, payload) VALUES (%s, %s, %s, %s::jsonb)',
            (ws, 'preset-1', 1, '{}'),
        )

    tables = [
        'cp_render_preset_revisions',
        'cp_render_packages',
        'cp_package_validation_reports',
        'cp_render_attempts',
        'cp_quality_reports',
        'cp_quality_gate_results',
        'cp_video_outputs',
        'cp_render_operation_receipts',
    ]
    for table in tables:
        before = count(dsn, table)
        assert before > 0, f'{table} should have rows'
        assert_rejected(dsn, f'UPDATE controlplane.{table} SET created_at = created_at')
        assert_rejected(dsn, f'DELETE FROM controlplane.{table}')
        assert count(dsn, table) == before


def test_record_and_outbox_commit_together(db, manager):
    ws = db[1]
    dsn = db[0]
    pkg = package()
    payload = {
        'render_attempt_id': 'attempt-1',
        'package_fingerprint': 'a' * 64,
        'output_artifact_ref': OUTPUT_REF,
        'receipt_ref': 'receipt-1',
        'revision': 3,
    }
    with new_uow(manager, ws) as uow:
        uow.renders.append(KIND_PACKAGE, 'pkg-1', 1, pkg)
        event_id = uow.outbox.append_event('RenderCompleted', 'attempt-1', payload, 'dedup-1')
        assert count(dsn, 'cp_render_packages') == 0
        assert count(dsn, 'cp_outbox_events') == 0
        uow.commit()

    assert count(dsn, 'cp_render_packages') == 1
    assert count(dsn, 'cp_outbox_events') == 1
    with psycopg.connect(dsn, autocommit=True) as conn:
        row = conn.execute(
            'SELECT producer, event_name, aggregate_id, workspace_id FROM controlplane.cp_outbox_events WHERE event_id = %s',
            (event_id,),
        ).fetchone()
        assert row == ('F', 'RenderCompleted', 'attempt-1', uuid.UUID(ws))

    with new_uow(manager, ws) as uow2:
        second_event_id = uow2.outbox.append_event('RenderCompleted', 'attempt-1', payload, 'dedup-1')
        assert second_event_id == event_id
        uow2.commit()
    assert count(dsn, 'cp_outbox_events') == 1

    with new_uow(manager, ws) as uow3:
        with pytest.raises(ValueError):
            uow3.outbox.append_event('RenderCompleted', 'attempt-1', {'secret_value': 'shh'}, 'dedup-bad')
        with pytest.raises(ValueError):
            uow3.outbox.append_event('RenderCompleted', 'attempt-1', 'not-a-mapping', 'dedup-bad2')


def test_exception_and_missing_commit_roll_back_everything(db, manager):
    ws = db[1]
    dsn = db[0]
    uow = new_uow(manager, ws)
    with pytest.raises(RuntimeError):
        with uow:
            uow.renders.append(KIND_PACKAGE, 'pkg-1', 1, package())
            uow.renders.append(KIND_ATTEMPT, 'attempt-1', 1, prepared())
            uow.reports.append(validate_render_package(package()))
            uow.receipts.add(receipt(ws))
            uow.traces.append(trace(ws))
            uow.outbox.append_event('RenderCompleted', 'attempt-1', {'render_attempt_id': 'attempt-1', 'package_fingerprint': 'a'*64, 'output_artifact_ref': OUTPUT_REF, 'receipt_ref': 'receipt-1', 'revision': 1}, 'dedup-rb1')
            raise RuntimeError('boom')

    for table in ('cp_render_packages', 'cp_render_attempts', 'cp_video_outputs', 'cp_package_validation_reports', 'cp_render_operation_receipts', 'cp_outbox_events'):
        assert count(dsn, table) == 0, f'{table} should be empty after exception rollback'
    assert count(dsn, 'cp_audit_records', where="starts_with(audit_id, 'render-trace:')") == 0

    # Repeat but exit without commit and without exception
    with uow:
        uow.renders.append(KIND_PACKAGE, 'pkg-1', 1, package())
        uow.renders.append(KIND_ATTEMPT, 'attempt-1', 1, prepared())
        uow.reports.append(validate_render_package(package()))
        uow.receipts.add(receipt(ws))
        uow.traces.append(trace(ws))
        uow.outbox.append_event('RenderCompleted', 'attempt-1', {'render_attempt_id': 'attempt-1', 'package_fingerprint': 'a'*64, 'output_artifact_ref': OUTPUT_REF, 'receipt_ref': 'receipt-1', 'revision': 1}, 'dedup-rb2')

    for table in ('cp_render_packages', 'cp_render_attempts', 'cp_video_outputs', 'cp_package_validation_reports', 'cp_render_operation_receipts', 'cp_outbox_events'):
        assert count(dsn, table) == 0, f'{table} should be empty after exit without commit'
    assert count(dsn, 'cp_audit_records', where="starts_with(audit_id, 'render-trace:')") == 0

    # Reuse the same uow: with + append + commit -> cp_render_packages == 1
    with uow:
        uow.renders.append(KIND_PACKAGE, 'pkg-1', 1, package())
        uow.commit()
    assert count(dsn, 'cp_render_packages') == 1


def test_unit_of_work_uses_one_connection(db):
    ws = db[1]
    dsn = db[0]
    single_manager = TransactionManager(dsn, pool_max_size=1)
    try:
        uow = new_uow(single_manager, ws)
        with uow:
            uow.renders.append(KIND_PACKAGE, 'pkg-1', 1, package())
            latest = uow.renders.latest(KIND_PACKAGE, 'pkg-1')
            assert latest is not None
            uow.reports.append(validate_render_package(package()))
            uow.receipts.add(receipt(ws))
            uow.traces.append(trace(ws))
            ids = uow.attempt_index.ids('a' * 64)
            assert isinstance(ids, tuple)
            uow.outbox.append_event('RenderCompleted', 'attempt-1', {'render_attempt_id': 'attempt-1', 'package_fingerprint': 'a'*64, 'output_artifact_ref': OUTPUT_REF, 'receipt_ref': 'receipt-1', 'revision': 1}, 'dedup-single')
            uow.commit()
    finally:
        single_manager.close()
    assert count(dsn, 'cp_render_packages') == 1


def test_unit_of_work_lifecycle(db, manager):
    ws = db[1]
    uow = new_uow(manager, ws)
    with pytest.raises(UnitOfWorkNotActiveError):
        uow.renders.append(KIND_PACKAGE, 'pkg-1', 1, package())
    with pytest.raises(UnitOfWorkNotActiveError):
        uow.reports.append(validate_render_package(package()))
    with pytest.raises(UnitOfWorkNotActiveError):
        uow.receipts.add(receipt(ws))
    with pytest.raises(UnitOfWorkNotActiveError):
        uow.traces.append(trace(ws))
    with pytest.raises(UnitOfWorkNotActiveError):
        uow.outbox.append_event('RenderCompleted', 'attempt-1', {}, 'dedup-life')
    with pytest.raises(UnitOfWorkNotActiveError):
        uow.commit()

    with uow:
        with pytest.raises(UnitOfWorkAlreadyActiveError):
            with uow:
                pass

    no_ws_uow = PostgresRenderUnitOfWork(manager)
    with no_ws_uow:
        with pytest.raises(ValueError):
            no_ws_uow.renders.append(KIND_PACKAGE, 'pkg-1', 1, package())


def test_source_has_no_ddl_foreign_imports():
    fs = list(PERSISTENCE_DIR.rglob('*.py'))
    assert fs, 'Persistence directory must have Python files'
    for f in fs:
        text = f.read_text(encoding='utf-8')
        assert 'CREATE TABLE' not in text, f'{f.name} contains CREATE TABLE'
        assert 'ALTER TABLE' not in text, f'{f.name} contains ALTER TABLE'
        assert 'from src.' not in text, f'{f.name} contains from src.'
        assert 'import src.' not in text, f'{f.name} contains import src.'
        match = re.search(r'^\s*(from|import)\s+(source_ingestion|ingestion|catalog|creative|voice)\b', text, re.MULTILINE)
        assert match is None, f'{f.name} imports foreign module: {match.group(0) if match else None}'