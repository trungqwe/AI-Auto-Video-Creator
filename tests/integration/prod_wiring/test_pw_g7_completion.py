"""PW-G7: CompletionAssembler, reserve_variant_handler và commit_video_completion_handler trên PostgreSQL thử.

coveredIds: PW-G7-01, CT-ORC-012, CT-AI-008, INV-003
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
from psycopg.types.json import Jsonb

from catalog.application.usage import MediaUsageRecorder
from catalog.persistence.usage import media_usage_repository_factory
from controlplane.api.wiring.workflow import service_handler
from controlplane.application.orchestration.completion_assembler import CompletionAssembler
from controlplane.application.orchestration.grant_runtime import build_grant_issuer
from controlplane.application.orchestration.variant_handlers import commit_video_completion_handler, reserve_variant_handler
from controlplane.application.orchestration.workflows.activities import ActivityDispatcher, claims_to_payload
from controlplane.infrastructure.db.orchestration.app_session import PostgresAppSessions
from controlplane.infrastructure.db.orchestration.grants import PostgresGrantStore
from controlplane.infrastructure.db.orchestration.stage_runs import PostgresStageRuns
from controlplane.infrastructure.db.uow import TransactionManager

ROOT = Path(__file__).resolve().parents[3]
ASSEMBLER = ROOT / 'src/controlplane/application/orchestration/completion_assembler.py'
HANDLERS = ROOT / 'src/controlplane/application/orchestration/variant_handlers.py'
NOW = datetime(2026, 10, 26, 1, 2, 3, tzinfo=timezone.utc)


@pytest.fixture
def manager(pw_database):
    tm = TransactionManager(pw_database.dsn, pool_max_size=4)
    try:
        yield tm
    finally:
        tm.close()


@pytest.fixture
def session(pw_database):
    begin_session(pw_database)


@dataclass(frozen=True)
class World:
    job_id: str
    batch_id: str
    sha: str
    artifact_id: str
    location_id: str
    attempt_id: str
    report_id: str
    candidate_hash: str
    validation_key: str
    capacity_id: str


def sha_of(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def seed_world(db, tag, *, candidate_hash=None, location_state='VERIFIED', job_status='READY_FOR_COMPLETION'):
    ws = db.workspace_id
    job_id = 'job-' + tag
    world = World(job_id, 'batch-' + tag, sha_of('mp4-' + tag), str(uuid.uuid4()), str(uuid.uuid4()), 'attempt-' + tag, sha_of('report-' + tag), candidate_hash or sha_of('cand-' + tag), 'variant:' + job_id, 'cap-' + tag)
    with db.connect() as conn:
        conn.execute('INSERT INTO controlplane.cp_production_batches (batch_id, workspace_id, status, target_count) VALUES (%s, %s, %s, %s)', (world.batch_id, ws, 'RUNNING', 3))
        conn.execute('INSERT INTO controlplane.cp_video_jobs (job_id, batch_id, workspace_id, status, snapshot_ref, revision) VALUES (%s, %s, %s, %s, %s, 3)', (job_id, world.batch_id, ws, job_status, 'snap-' + tag))
        conn.execute('INSERT INTO controlplane.cp_batch_capacity_reservations (reservation_id, workspace_id, batch_id, job_id, state) VALUES (%s, %s, %s, %s, %s)', (world.capacity_id, ws, world.batch_id, job_id, 'ACTIVE'))
        conn.execute("INSERT INTO controlplane.cp_artifact_versions (artifact_version_id, workspace_id, artifact_id, sha256_hash, size_bytes, mime_type, artifact_kind, owner_ref, lineage_ref, retention_ref, sensitivity_ref) VALUES (%s, %s, %s, %s, 128, 'video/mp4', 'rendered_video', 'owner-g', 'lineage-g', 'retention-g', 'internal')", (world.artifact_id, ws, 'artifact-' + tag, world.sha))
        conn.execute("INSERT INTO controlplane.cp_artifact_locations (location_id, workspace_id, artifact_version_id, backend_ref, provider_namespace_ref, provider_object_ref, logical_locator, observed_hash, observed_size_bytes, verification_evidence_ref, state) VALUES (%s, %s, %s, 'drive', 'ns', %s, %s, %s, 128, %s, %s)", (world.location_id, ws, world.artifact_id, 'obj-' + tag, 'loc-' + tag, world.sha, 'evidence-' + tag, location_state))
    return world


def seed_documents(db, world, *, qc_passed=True):
    ws, job = db.workspace_id, world.job_id
    with db.connect() as conn:
        conn.execute('INSERT INTO controlplane.cp_quality_reports (workspace_id, record_key, revision, payload) VALUES (%s, %s, 1, %s)', (ws, world.attempt_id, Jsonb({'report_id': world.report_id, 'passed': qc_passed})))
        for revision in (1, 2):
            conn.execute('INSERT INTO controlplane.cp_output_metadata (workspace_id, record_key, revision, payload) VALUES (%s, %s, %s, %s)', (ws, 'meta-' + job, revision, Jsonb({'title': 'title-' + str(revision)})))
        selection = {'preset_registry_revision': 'preset-r1', 'assignments': [{'media_asset_id': 'asset-' + job, 'rendition_ref': 'rend-1', 'artifact_version_ref': 'av-1'}], 'visual_hook': {'ref_id': 'vh-01'}, 'audio_hook': {'ref_id': 'ah-01'}, 'thumbnail': {'ref_id': 'asset-' + job}}
        conn.execute('INSERT INTO controlplane.cp_creative_selections (workspace_id, selection_id, job_id, selection_revision, content_sha256, payload) VALUES (%s, %s, %s, 1, %s, %s)', (ws, 'sel-' + job, job, sha_of('sel-' + job), Jsonb(selection)))


def add_validation(db, world, revision, *, phase, registry_revision, valid=True, output_hash=None):
    payload = {'valid': valid, 'phase': phase, 'registry_revision': registry_revision, 'variation_policy_revision': 'policy-r1', 'input_hashes': {'candidate': world.candidate_hash}, 'output_hash': output_hash, 'own_reservation_id': None, 'exact_duplicate': not valid, 'reason_codes': ['valid' if valid else 'exact_duplicate']}
    with db.connect() as conn:
        conn.execute('INSERT INTO controlplane.cp_variant_validations (workspace_id, record_key, revision, payload) VALUES (%s, %s, %s, %s)', (db.workspace_id, world.validation_key, revision, Jsonb(payload)))


def scalar(db, sql, *params):
    with db.connect() as conn:
        row = conn.execute(sql, (db.workspace_id, *params)).fetchone()
    return None if row is None else row[0]


def count(db, table):
    return scalar(db, 'SELECT count(*) FROM controlplane.' + table + ' WHERE workspace_id = %s')


def job_status(db, world):
    return scalar(db, 'SELECT status FROM controlplane.cp_video_jobs WHERE workspace_id = %s AND job_id = %s', world.job_id)


def variant_state(db, world):
    return scalar(db, 'SELECT state FROM controlplane.cp_variant_reservations WHERE workspace_id = %s AND job_id = %s', world.job_id)


def capacity_state(db, world):
    return scalar(db, 'SELECT state FROM controlplane.cp_batch_capacity_reservations WHERE workspace_id = %s AND job_id = %s', world.job_id)


def registry_revision(db):
    return scalar(db, 'SELECT current_registry_revision FROM controlplane.cp_variant_registry WHERE workspace_id = %s')


def base_refs(world):
    return [
        {'ref_type': 'production_snapshot', 'ref_id': 'snapshot-' + world.job_id},
        {'ref_type': 'script_version', 'ref_id': 'script-' + world.job_id},
        {'ref_type': 'production_plan', 'ref_id': 'plan-' + world.job_id},
        {'ref_type': 'output_metadata', 'ref_id': 'meta-' + world.job_id},
        {'ref_type': 'variant_validation', 'ref_id': world.validation_key},
        {'ref_type': 'render_attempt', 'ref_id': world.attempt_id},
        {'ref_type': 'quality_report', 'ref_id': world.report_id},
        {'ref_type': 'output_artifact_version', 'ref_id': world.artifact_id},
        {'ref_type': 'cloud_location', 'ref_id': world.location_id},
    ]


def reserve_request(world, key=None, stage='plan'):
    return {'video_job_id': world.job_id, 'stage_run_id': f'{world.job_id}:{stage}:r1', 'operation_key': key or f'wf:{world.job_id}:plan:ReserveVariant:0:r1', 'input_refs': base_refs(world)}


def commit_request(world, claims):
    return {'video_job_id': world.job_id, 'stage_run_id': claims.stage_run_id, 'operation_key': f'wf:{world.job_id}:complete:CommitVideoCompletion:0:r1', 'input_refs': base_refs(world)}


def begin_session(db, session_ref='ses-1', epoch='5'):
    with db.connect() as conn:
        PostgresAppSessions(conn, db.workspace_id).begin(session_ref, epoch)


def issue_grant(db, stage_run_id, operation):
    return build_grant_issuer(db.connect, db.workspace_id, None, lambda: NOW)(stage_run_id, operation, 'fp-' + stage_run_id, 'lease-1')


def make_handlers(db, manager):
    recorder = MediaUsageRecorder(media_usage_repository_factory(db.workspace_id))
    reserve = reserve_variant_handler(manager, workspace_id=db.workspace_id)
    commit = commit_video_completion_handler(manager, workspace_id=db.workspace_id, clock=lambda: NOW, usage_recorder=recorder)
    return reserve, commit


def ready_world(db, manager, tag, *, output_valid=True, output_phase=True, qc_passed=True, location_state='VERIFIED'):
    world = seed_world(db, tag, location_state=location_state)
    seed_documents(db, world, qc_passed=qc_passed)
    add_validation(db, world, 1, phase='plan', registry_revision=1)
    reserve, _ = make_handlers(db, manager)
    outcome = reserve(reserve_request(world), None)
    assert outcome['disposition'] == 'succeeded'
    if output_phase:
        add_validation(db, world, 2, phase='output', registry_revision=outcome['metrics']['registry_revision'], valid=output_valid, output_hash=world.sha)
    return world, outcome


def test_reserve_creates_one_active_reservation_and_bumps_the_registry(pw_database, manager):
    world = seed_world(pw_database, 'a')
    add_validation(pw_database, world, 1, phase='plan', registry_revision=1)
    reserve, _ = make_handlers(pw_database, manager)
    outcome = reserve(reserve_request(world), None)
    assert outcome['disposition'] == 'succeeded'
    assert outcome['output_refs'][0]['ref_type'] == 'variant_reservation'
    assert outcome['metrics'] == {'registry_revision': 2}
    assert (variant_state(pw_database, world), count(pw_database, 'cp_variant_reservations'), registry_revision(pw_database)) == ('ACTIVE', 1, 2)


def test_reserve_retry_with_the_same_key_returns_the_old_receipt(pw_database, manager):
    world = seed_world(pw_database, 'a')
    add_validation(pw_database, world, 1, phase='plan', registry_revision=1)
    reserve, _ = make_handlers(pw_database, manager)
    first = reserve(reserve_request(world), None)
    again = reserve(reserve_request(world), None)
    assert again == first
    assert (count(pw_database, 'cp_variant_reservations'), count(pw_database, 'cp_orchestration_receipts'), registry_revision(pw_database)) == (1, 1, 2)


def test_reserve_with_different_input_is_a_variant_conflict(pw_database, manager):
    world = seed_world(pw_database, 'a')
    add_validation(pw_database, world, 1, phase='plan', registry_revision=1)
    reserve, _ = make_handlers(pw_database, manager)
    req = reserve_request(world)
    first = reserve(req, None)
    add_validation(pw_database, replace(world, candidate_hash=sha_of('other')), 2, phase='plan', registry_revision=2)
    again = reserve(req, None)
    assert again['disposition'] == 'failed'
    assert again['problem']['code'] == 'VARIANT_CONFLICT'
    assert again['problem']['retryable'] is False
    assert scalar(pw_database, 'SELECT reservation_id FROM controlplane.cp_variant_reservations WHERE workspace_id = %s') == first['output_refs'][0]['ref_id']
    assert count(pw_database, 'cp_variant_reservations') == 1
    assert registry_revision(pw_database) == 2


def test_reserve_for_another_job_with_the_same_fingerprint_is_a_variant_conflict(pw_database, manager):
    first = seed_world(pw_database, 'a')
    add_validation(pw_database, first, 1, phase='plan', registry_revision=1)
    reserve, _ = make_handlers(pw_database, manager)
    reserve(reserve_request(first), None)
    second = seed_world(pw_database, 'b', candidate_hash=first.candidate_hash)
    add_validation(pw_database, second, 1, phase='plan', registry_revision=2)
    outcome = reserve(reserve_request(second), None)
    assert outcome['disposition'] == 'failed'
    assert outcome['problem']['code'] == 'VARIANT_CONFLICT'
    assert variant_state(pw_database, second) is None
    assert count(pw_database, 'cp_variant_reservations') == 1
    assert registry_revision(pw_database) == 2


def test_reserve_with_a_changed_registry_revision_waits_and_writes_nothing(pw_database, manager):
    world = seed_world(pw_database, 'a')
    add_validation(pw_database, world, 1, phase='plan', registry_revision=1)
    with pw_database.connect() as conn:
        conn.execute('INSERT INTO controlplane.cp_variant_registry (workspace_id, current_registry_revision) VALUES (%s, 5)', (pw_database.workspace_id,))
    reserve, _ = make_handlers(pw_database, manager)
    outcome = reserve(reserve_request(world), None)
    assert outcome['disposition'] == 'waiting'
    assert outcome['problem']['code'] == 'VARIANT_VALIDATION_STALE'
    assert (count(pw_database, 'cp_variant_reservations'), count(pw_database, 'cp_orchestration_receipts'), registry_revision(pw_database)) == (0, 0, 5)


def test_reserve_after_render_is_refused_and_writes_nothing(pw_database, manager):
    world = seed_world(pw_database, 'a')
    add_validation(pw_database, world, 1, phase='plan', registry_revision=1)
    with pw_database.connect() as conn:
        PostgresStageRuns(conn, pw_database.workspace_id).ensure(f'{world.job_id}:render:r1', '5')
    reserve, _ = make_handlers(pw_database, manager)
    late = reserve(reserve_request(world), None)
    assert late['disposition'] == 'failed'
    assert late['problem']['code'] == 'RESERVE_AFTER_RENDER'
    wrong = reserve(reserve_request(world, stage='media_select'), None)
    assert wrong['disposition'] == 'failed'
    assert wrong['problem']['code'] == 'RESERVE_OUT_OF_ORDER'
    assert (count(pw_database, 'cp_variant_reservations'), count(pw_database, 'cp_variant_registry')) == (0, 0)


def test_reserve_refuses_an_invalid_plan_validation(pw_database, manager):
    world = seed_world(pw_database, 'a')
    add_validation(pw_database, world, 1, phase='plan', registry_revision=1, valid=False)
    reserve, _ = make_handlers(pw_database, manager)
    outcome = reserve(reserve_request(world), None)
    assert outcome['disposition'] == 'failed'
    assert outcome['problem']['code'] == 'VARIANT_VALIDATION_INVALID'
    assert count(pw_database, 'cp_variant_reservations') == 0


def test_assembler_builds_the_request_and_context_from_real_rows(pw_database, manager, session):
    world, reserved = ready_world(pw_database, manager, 'a')
    claims = issue_grant(pw_database, f'{world.job_id}:complete:r1', 'CommitVideoCompletion')
    _, commit = make_handlers(pw_database, manager)
    with manager.borrow_connection() as connection:
        request, context = CompletionAssembler(pw_database.workspace_id, lambda: NOW).assemble(connection, commit_request(world, claims), claims)
    assert request['variant_reservation_id'] == reserved['output_refs'][0]['ref_id']
    assert (request['output_artifact_version_id'], request['output_sha256']) == (world.artifact_id, world.sha)
    assert request['cloud_location_verification_ref'] == 'evidence-a'
    assert (request['quality_report_ref'], request['render_attempt_ref']) == (world.report_id, world.attempt_id)
    assert request['variant_validation_ref'] == 'variant:job-a:r2'
    assert request['expected_variant_registry_revision'] == 2
    assert (request['grant_id'], request['execution_generation'], request['recovery_epoch']) == (claims.grant_id, 1, '5')
    assert request['output_metadata_revision'] == '2'
    assert [(m['media_asset_id'], m['role']) for m in request['media_usage_manifest']] == [('asset-job-a', 'scene_media'), ('vh-01', 'visual_hook'), ('ah-01', 'audio_hook'), ('asset-job-a', 'thumbnail')]
    assert context.fencing.accepted is True
    assert context.variant_conflict_confirmed is False
    assert (context.session_ref, context.batch_ref, context.cloud_location_ref, context.preset_revision_ref) == ('ses-1', world.batch_id, world.location_id, 'preset-r1')
    assert context.completed_at == '2026-10-26T01:02:03Z'


def test_commit_writes_one_ledger_and_converts_the_job_and_both_reservations(pw_database, manager, session):
    world, reserved = ready_world(pw_database, manager, 'a')
    claims = issue_grant(pw_database, f'{world.job_id}:complete:r1', 'CommitVideoCompletion')
    _, commit = make_handlers(pw_database, manager)
    outcome = commit(commit_request(world, claims), claims)
    assert outcome['disposition'] == 'succeeded'
    assert outcome['output_refs'][0]['ref_type'] == 'video_completion'
    assert (count(pw_database, 'cp_completion_ledger'), job_status(pw_database, world), variant_state(pw_database, world), capacity_state(pw_database, world), registry_revision(pw_database)) == (1, 'COMPLETED', 'CONVERTED', 'CONVERTED', 3)
    assert (count(pw_database, 'cp_media_usage'), count(pw_database, 'cp_cleanup_eligibility'), count(pw_database, 'cp_outbox_events')) == (4, 1, 1)


def test_rerunning_the_same_request_does_not_write_twice(pw_database, manager, session):
    world, reserved = ready_world(pw_database, manager, 'a')
    claims = issue_grant(pw_database, f'{world.job_id}:complete:r1', 'CommitVideoCompletion')
    _, commit = make_handlers(pw_database, manager)
    req = commit_request(world, claims)
    first = commit(req, claims)
    again = commit(req, claims)
    assert first['disposition'] == 'succeeded'
    assert again['disposition'] == 'succeeded'
    assert again['output_refs'] == first['output_refs']
    assert first['metrics'] == {'replayed': False}
    assert again['metrics'] == {'replayed': True}
    assert (count(pw_database, 'cp_completion_ledger'), count(pw_database, 'cp_media_usage'), count(pw_database, 'cp_outbox_events'), registry_revision(pw_database)) == (1, 4, 1, 3)


def test_a_grant_from_an_older_recovery_epoch_is_rejected_and_nothing_is_written(pw_database, manager, session):
    world, reserved = ready_world(pw_database, manager, 'a')
    claims = issue_grant(pw_database, f'{world.job_id}:complete:r1', 'CommitVideoCompletion')
    _, commit = make_handlers(pw_database, manager)
    begin_session(pw_database, 'ses-2', '6')
    outcome = commit(commit_request(world, claims), claims)
    assert outcome['disposition'] == 'stale'
    assert outcome['problem']['code'] == 'STALE_RECOVERY_EPOCH'
    assert (count(pw_database, 'cp_completion_ledger'), job_status(pw_database, world), variant_state(pw_database, world), registry_revision(pw_database), count(pw_database, 'cp_media_usage')) == (0, 'READY_FOR_COMPLETION', 'ACTIVE', 2, 0)


def test_a_superseded_execution_generation_is_rejected_then_the_new_grant_completes(pw_database, manager, session):
    world, reserved = ready_world(pw_database, manager, 'a')
    _, commit = make_handlers(pw_database, manager)
    sid = f'{world.job_id}:complete:r1'
    old = issue_grant(pw_database, sid, 'CommitVideoCompletion')
    with pw_database.connect() as conn:
        PostgresGrantStore(conn, pw_database.workspace_id).revoke(old.grant_id)
    new = issue_grant(pw_database, sid, 'CommitVideoCompletion')
    assert (old.execution_generation, new.execution_generation) == (1, 2)
    old_outcome = commit(commit_request(world, old), old)
    assert old_outcome['disposition'] == 'stale'
    assert old_outcome['problem']['code'] == 'STALE_EXECUTION_GENERATION'
    assert count(pw_database, 'cp_completion_ledger') == 0
    new_outcome = commit(commit_request(world, new), new)
    assert new_outcome['disposition'] == 'succeeded'
    assert count(pw_database, 'cp_completion_ledger') == 1


def test_a_location_that_is_not_verified_waits_and_writes_no_ledger(pw_database, manager, session):
    world, reserved = ready_world(pw_database, manager, 'a', location_state='AVAILABLE_UNVERIFIED')
    claims = issue_grant(pw_database, f'{world.job_id}:complete:r1', 'CommitVideoCompletion')
    _, commit = make_handlers(pw_database, manager)
    outcome = commit(commit_request(world, claims), claims)
    assert outcome['disposition'] == 'waiting'
    assert outcome['problem']['code'] == 'artifact_not_ready'
    assert (count(pw_database, 'cp_completion_ledger'), job_status(pw_database, world), count(pw_database, 'cp_media_usage')) == (0, 'READY_FOR_COMPLETION', 0)


def test_registry_changed_before_commit_waits_and_writes_nothing(pw_database, manager, session):
    world, reserved = ready_world(pw_database, manager, 'a')
    claims = issue_grant(pw_database, f'{world.job_id}:complete:r1', 'CommitVideoCompletion')
    _, commit = make_handlers(pw_database, manager)
    with pw_database.connect() as conn:
        conn.execute('UPDATE controlplane.cp_variant_registry SET current_registry_revision = 9 WHERE workspace_id = %s', (pw_database.workspace_id,))
    outcome = commit(commit_request(world, claims), claims)
    assert outcome['disposition'] == 'waiting'
    assert outcome['problem']['code'] == 'VARIANT_REGISTRY_STALE'
    assert (count(pw_database, 'cp_completion_ledger'), job_status(pw_database, world), variant_state(pw_database, world), capacity_state(pw_database, world), count(pw_database, 'cp_media_usage'), registry_revision(pw_database)) == (0, 'READY_FOR_COMPLETION', 'ACTIVE', 'ACTIVE', 0, 9)


def test_confirmed_variant_conflict_fails_the_job_and_releases_both_reservations(pw_database, manager, session):
    world, reserved = ready_world(pw_database, manager, 'a', output_valid=False)
    claims = issue_grant(pw_database, f'{world.job_id}:complete:r1', 'CommitVideoCompletion')
    _, commit = make_handlers(pw_database, manager)
    outcome = commit(commit_request(world, claims), claims)
    assert outcome['disposition'] == 'failed'
    assert outcome['problem']['code'] == 'VARIANT_CONFLICT'
    assert outcome['problem']['retryable'] is False
    assert (count(pw_database, 'cp_completion_ledger'), job_status(pw_database, world), variant_state(pw_database, world), capacity_state(pw_database, world)) == (0, 'FAILED_FINAL', 'RELEASED', 'RELEASED')


def test_output_validation_must_match_the_exact_output_hash(pw_database, manager, session):
    world, reserved = ready_world(pw_database, manager, 'a', output_phase=False)
    claims = issue_grant(pw_database, f'{world.job_id}:complete:r1', 'CommitVideoCompletion')
    _, commit = make_handlers(pw_database, manager)
    outcome = commit(commit_request(world, claims), claims)
    assert outcome['disposition'] == 'waiting'
    assert outcome['problem']['code'] == 'VARIANT_VALIDATION_UNAVAILABLE'
    assert count(pw_database, 'cp_completion_ledger') == 0
    add_validation(pw_database, world, 2, phase='output', registry_revision=2, output_hash=sha_of('different'))
    again = commit(commit_request(world, claims), claims)
    assert again['disposition'] == 'waiting'
    assert again['problem']['code'] == 'VARIANT_VALIDATION_UNAVAILABLE'
    assert count(pw_database, 'cp_completion_ledger') == 0


def test_a_failed_quality_report_is_refused(pw_database, manager, session):
    world, reserved = ready_world(pw_database, manager, 'a', qc_passed=False)
    claims = issue_grant(pw_database, f'{world.job_id}:complete:r1', 'CommitVideoCompletion')
    _, commit = make_handlers(pw_database, manager)
    outcome = commit(commit_request(world, claims), claims)
    assert outcome['disposition'] == 'failed'
    assert outcome['problem']['code'] == 'QUALITY_REPORT_NOT_PASSED'
    assert count(pw_database, 'cp_completion_ledger') == 0


def test_a_job_without_an_active_reservation_is_refused(pw_database, manager, session):
    world = seed_world(pw_database, 'a')
    seed_documents(pw_database, world)
    add_validation(pw_database, world, 1, phase='output', registry_revision=1, output_hash=world.sha)
    claims = issue_grant(pw_database, f'{world.job_id}:complete:r1', 'CommitVideoCompletion')
    _, commit = make_handlers(pw_database, manager)
    outcome = commit(commit_request(world, claims), claims)
    assert outcome['disposition'] == 'failed'
    assert outcome['problem']['code'] == 'RESERVATION_MISSING'
    assert count(pw_database, 'cp_completion_ledger') == 0


def full_request(base, claims, activity):
    return {**base, 'workflow_id': 'wf-1', 'workflow_run_id': 'run-1', 'activity_name': activity, 'activity_version': '1', 'capability_requirements': {}, 'retry_policy_ref': 'retry-default', 'execution_grant': claims_to_payload(claims)}


def test_both_handlers_run_through_service_handler_and_the_activity_dispatcher(pw_database, manager, session):
    world = seed_world(pw_database, 'a')
    seed_documents(pw_database, world)
    add_validation(pw_database, world, 1, phase='plan', registry_revision=1)
    reserve, commit = make_handlers(pw_database, manager)
    dispatcher = ActivityDispatcher({'ReserveVariant': service_handler(reserve, lambda: NOW), 'CommitVideoCompletion': service_handler(commit, lambda: NOW)})
    plan_claims = issue_grant(pw_database, f'{world.job_id}:plan:r1', 'ReserveVariant')
    reserved = dispatcher.dispatch(full_request(reserve_request(world), plan_claims, 'ReserveVariant'))
    assert reserved['disposition'] == 'succeeded'
    assert reserved['grant_id'] == plan_claims.grant_id
    add_validation(pw_database, world, 2, phase='output', registry_revision=reserved['metrics']['registry_revision'], output_hash=world.sha)
    claims = issue_grant(pw_database, f'{world.job_id}:complete:r1', 'CommitVideoCompletion')
    done = dispatcher.dispatch(full_request(commit_request(world, claims), claims, 'CommitVideoCompletion'))
    assert done['disposition'] == 'succeeded'
    assert done['recovery_epoch'] == '5'
    assert job_status(pw_database, world) == 'COMPLETED'


def test_sources_use_the_postgres_stores_and_contain_no_forbidden_words():
    assembler, handlers = (path.read_text(encoding='utf-8') for path in (ASSEMBLER, HANDLERS))
    text = (assembler + handlers).lower()
    assert 'inmemory' not in text and 'fake' not in text and 'from src.' not in text
    assert 'PostgresGrantStore' in assembler and 'PostgresRecoveryEpoch' in assembler
    assert 'PostgresCompletionUnitOfWork' in handlers and 'VariantReservationFlow' in handlers and 'CommitVideoCompletion' in handlers
