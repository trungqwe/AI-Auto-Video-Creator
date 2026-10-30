"""PW-G2-FIX1: dòng cp_stage_runs phản ánh kết quả của cả stage nhiều activity.

coveredIds: PW-G2-FIX1-01..05, CT-ORC-003, CT-STATE-009
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from controlplane.application.orchestration.job_lifecycle import JobLifecycleListener
from controlplane.application.orchestration.result_recorder import ResultRecordingDispatcher
from controlplane.application.orchestration.workflows.activities import ActivityDispatcher, ActivityRejected

NOW = datetime(2026, 10, 26, 1, 2, 3, tzinfo=timezone.utc)
SNAPSHOT, ANALYZE, ANGLES, SCRIPT, VOICE = 'BuildProductionSnapshot', 'AnalyzeContent', 'GenerateStoryAngles', 'GenerateScript', 'CreateVoiceTrack'
STAGE_SQL = 'SELECT status, problem, wait_reason, finished_at FROM controlplane.cp_stage_runs WHERE workspace_id = %s AND stage_run_id = %s'
JOB_SQL = 'SELECT status FROM controlplane.cp_video_jobs WHERE workspace_id = %s AND job_id = %s'
NOT_RETRYABLE = {'problem': {'code': 'ANALYZE_FAILED', 'retryable': False}}


def seed_job(pw_database, status='ACTIVE'):
    ws = pw_database.workspace_id
    with pw_database.connect() as conn:
        conn.execute("INSERT INTO controlplane.cp_production_batches (batch_id, workspace_id, status, target_count) VALUES ('batch-1', %s, 'RUNNING', 1)", (ws,))
        conn.execute("INSERT INTO controlplane.cp_video_jobs (job_id, batch_id, workspace_id, status, snapshot_ref, revision) VALUES ('job-1', 'batch-1', %s, %s, 'snap-1', 1)", (ws, status))


def stage_row(pw_database, stage):
    with pw_database.connect() as conn:
        return conn.execute(STAGE_SQL, (pw_database.workspace_id, f'job-1:{stage}:r1')).fetchone()


def job_status(pw_database):
    with pw_database.connect() as conn:
        return conn.execute(JOB_SQL, (pw_database.workspace_id, 'job-1')).fetchone()[0]


def request_for(activity, stage):
    sid = f'job-1:{stage}:r1'
    grant = {'grant_id': 'grant-' + sid + '-' + activity, 'stage_run_id': sid, 'execution_generation': 1, 'recovery_epoch': '5', 'worker_lease_id': 'lease-1', 'issued_at': '2026-10-26T01:00:00Z', 'expires_at': '2026-10-26T02:00:00Z', 'allowed_operation': activity, 'input_fingerprint': 'fp-1'}
    return {'workflow_id': 'wf-1', 'workflow_run_id': 'run-1', 'stage_run_id': sid, 'activity_name': activity, 'activity_version': '1', 'input_refs': [], 'operation_key': 'op-' + sid + '-' + activity, 'capability_requirements': {}, 'retry_policy_ref': 'retry-1', 'execution_grant': grant}


def build_dispatcher(pw_database, script, bound):
    """script: hàng đợi (disposition, extra) theo thứ tự activity được gọi; bound: tên các activity có handler."""
    def handler(request, claims):
        disposition, extra = script.pop(0)
        g = request['execution_grant']
        return {'stage_run_id': g['stage_run_id'], 'grant_id': g['grant_id'], 'execution_generation': 1, 'recovery_epoch': '5', 'disposition': disposition, 'output_refs': [], 'completed_at': '2026-10-26T01:02:03Z', **extra}

    inner = ActivityDispatcher({name: handler for name in bound})
    listener = JobLifecycleListener(pw_database.connect, workspace_id=pw_database.workspace_id)
    return ResultRecordingDispatcher(inner, pw_database.connect, lambda: NOW, [listener], workspace_id=pw_database.workspace_id)


def test_analyze_failure_after_the_snapshot_fails_the_stage_row_and_the_job(pw_database):
    seed_job(pw_database, 'CREATED')
    dispatcher = build_dispatcher(pw_database, [('succeeded', {}), ('failed', NOT_RETRYABLE)], (SNAPSHOT, ANALYZE))
    dispatcher.dispatch(request_for(SNAPSHOT, 'analyze'))
    assert stage_row(pw_database, 'analyze') == ('RUNNING', None, None, None)
    assert job_status(pw_database) == 'SNAPSHOTTED'
    dispatcher.dispatch(request_for(ANALYZE, 'analyze'))
    assert stage_row(pw_database, 'analyze') == ('FAILED_FINAL', {'code': 'ANALYZE_FAILED', 'retryable': False, 'activity': ANALYZE}, None, NOW)
    assert job_status(pw_database) == 'FAILED_FINAL'


def test_script_stage_row_stays_running_until_the_last_activity_succeeds(pw_database):
    seed_job(pw_database)
    dispatcher = build_dispatcher(pw_database, [('succeeded', {}), ('succeeded', {})], (ANGLES, SCRIPT))
    dispatcher.dispatch(request_for(ANGLES, 'script'))
    assert stage_row(pw_database, 'script') == ('RUNNING', None, None, None)
    assert job_status(pw_database) == 'ACTIVE'
    dispatcher.dispatch(request_for(SCRIPT, 'script'))
    assert stage_row(pw_database, 'script') == ('SUCCEEDED', None, None, NOW)


def test_single_activity_stage_keeps_the_old_behaviour(pw_database):
    seed_job(pw_database)
    dispatcher = build_dispatcher(pw_database, [('succeeded', {})], (VOICE,))
    dispatcher.dispatch(request_for(VOICE, 'tts'))
    assert stage_row(pw_database, 'tts') == ('SUCCEEDED', None, None, NOW)


LATER_RESULTS = [
    ('failed', {'problem': {'code': 'X', 'retryable': True}}, 'FAILED_RETRYABLE', {'code': 'X', 'retryable': True, 'activity': ANALYZE}),
    ('failed', {}, 'FAILED_FINAL', {'activity': ANALYZE}),
    ('outcome_unknown', {}, 'OUTCOME_UNKNOWN', {'activity': ANALYZE}),
    ('stale', {}, 'STALE', {'activity': ANALYZE}),
]


@pytest.mark.parametrize('disposition, extra, status, expected_problem', LATER_RESULTS)
def test_every_non_success_result_of_the_second_activity_is_recorded(pw_database, disposition, extra, status, expected_problem):
    seed_job(pw_database)
    dispatcher = build_dispatcher(pw_database, [('succeeded', {}), (disposition, extra)], (SNAPSHOT, ANALYZE))
    dispatcher.dispatch(request_for(SNAPSHOT, 'analyze'))
    dispatcher.dispatch(request_for(ANALYZE, 'analyze'))
    assert stage_row(pw_database, 'analyze') == (status, expected_problem, None, NOW)


def test_failure_of_the_first_activity_fails_the_row_with_its_name(pw_database):
    seed_job(pw_database)
    dispatcher = build_dispatcher(pw_database, [('failed', NOT_RETRYABLE)], (SNAPSHOT, ANALYZE))
    dispatcher.dispatch(request_for(SNAPSHOT, 'analyze'))
    assert stage_row(pw_database, 'analyze') == ('FAILED_FINAL', {'code': 'ANALYZE_FAILED', 'retryable': False, 'activity': SNAPSHOT}, None, NOW)


def test_activity_rejected_on_the_second_activity_fails_the_row(pw_database):
    seed_job(pw_database, 'CREATED')
    dispatcher = build_dispatcher(pw_database, [('succeeded', {})], (SNAPSHOT,))
    dispatcher.dispatch(request_for(SNAPSHOT, 'analyze'))
    with pytest.raises(ActivityRejected) as info:
        dispatcher.dispatch(request_for(ANALYZE, 'analyze'))
    assert info.value.code == 'ACTIVITY_SERVICE_UNBOUND'
    assert stage_row(pw_database, 'analyze') == ('FAILED_FINAL', {'code': 'ACTIVITY_SERVICE_UNBOUND', 'retryable': False, 'activity': ANALYZE}, None, NOW)
    assert job_status(pw_database) == 'SNAPSHOTTED'


def test_waiting_on_the_second_activity_keeps_the_row_running_with_the_wait_reason(pw_database):
    seed_job(pw_database)
    dispatcher = build_dispatcher(pw_database, [('succeeded', {}), ('waiting', {'problem': {'code': 'quota_wait'}})], (SNAPSHOT, ANALYZE))
    dispatcher.dispatch(request_for(SNAPSHOT, 'analyze'))
    dispatcher.dispatch(request_for(ANALYZE, 'analyze'))
    assert stage_row(pw_database, 'analyze') == ('RUNNING', None, 'quota_wait', None)
    assert job_status(pw_database) == 'WAITING'
