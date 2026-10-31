"""PW-G2: PostgresStageRuns và ResultRecordingDispatcher trên PostgreSQL thử.

coveredIds: PW-G2-01..06, CT-ORC-003, CT-STATE-009
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from controlplane.application.orchestration.result_recorder import ResultRecordingDispatcher
from controlplane.application.orchestration.workflows.activities import ActivityDispatcher, ActivityRejected
from controlplane.domain.orchestration import OrchestrationContractError
from controlplane.domain.statemachine import ForbiddenTransitionError, StageRunState
from controlplane.infrastructure.db.orchestration.stage_runs import PostgresStageRuns

ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 10, 26, 1, 2, 3, tzinfo=timezone.utc)
LATER = datetime(2026, 10, 26, 1, 2, 9, tzinfo=timezone.utc)
SOURCES = (
    ROOT / 'src/controlplane/infrastructure/db/orchestration/stage_runs.py',
    ROOT / 'src/controlplane/application/orchestration/result_recorder.py',
)
ROW_SQL = (
    'SELECT stage_run_id, status, job_id, workflow_id, stage_name, attempt, recovery_epoch, execution_generation, '
    'wait_reason, problem, started_at, finished_at, updated_at '
    'FROM controlplane.cp_stage_runs WHERE workspace_id = %s ORDER BY stage_run_id'
)
# cột của ROW_SQL: 0 id, 1 status, 2 job_id, 3 workflow_id, 4 stage_name, 5 attempt, 6 epoch, 7 generation, 8 wait_reason, 9 problem, 10 started_at, 11 finished_at, 12 updated_at


def seed_job(conn, ws, job_id='job-1'):
    conn.execute("INSERT INTO controlplane.cp_production_batches (batch_id, workspace_id, status, target_count) VALUES ('batch-1', %s, 'RUNNING', 1)", (ws,))
    conn.execute("INSERT INTO controlplane.cp_video_jobs (job_id, batch_id, workspace_id, status, snapshot_ref, revision) VALUES (%s, 'batch-1', %s, 'ACTIVE', 'snap-1', 1)", (job_id, ws))


def rows(conn, ws):
    return conn.execute(ROW_SQL, (ws,)).fetchall()


def one(conn, ws, stage_run_id):
    found = [r for r in rows(conn, ws) if r[0] == stage_run_id]
    assert len(found) == 1
    return found[0]


def seed(pw_database):
    with pw_database.connect() as conn:
        seed_job(conn, pw_database.workspace_id)


def current(pw_database, stage_run_id):
    with pw_database.connect() as conn:
        return one(conn, pw_database.workspace_id, stage_run_id)


def all_rows(pw_database):
    with pw_database.connect() as conn:
        return rows(conn, pw_database.workspace_id)


def grant_for(stage_run_id, generation=3, epoch='5'):
    return {'grant_id': 'grant-1', 'stage_run_id': stage_run_id, 'execution_generation': generation, 'recovery_epoch': epoch, 'worker_lease_id': 'lease-1', 'issued_at': '2026-10-26T01:00:00Z', 'expires_at': '2026-10-26T02:00:00Z', 'allowed_operation': 'ProbeMedia', 'input_fingerprint': 'fp-1'}


def request_for(stage_run_id, grant=True):
    request = {'workflow_id': 'wf-1', 'workflow_run_id': 'run-1', 'stage_run_id': stage_run_id, 'activity_name': 'ProbeMedia', 'activity_version': '1', 'input_refs': [], 'operation_key': 'op-1', 'capability_requirements': {}, 'retry_policy_ref': 'retry-1'}
    if grant:
        request['execution_grant'] = grant_for(stage_run_id)
    return request


def result_for(request, disposition, **extra):
    claims = request['execution_grant']
    return {'stage_run_id': claims['stage_run_id'], 'grant_id': claims['grant_id'], 'execution_generation': claims['execution_generation'], 'recovery_epoch': claims['recovery_epoch'], 'disposition': disposition, 'output_refs': [], 'completed_at': '2026-10-26T01:02:03Z', **extra}


def build(pw_database, handler, listeners=()):
    inner = ActivityDispatcher({'ProbeMedia': handler})
    return ResultRecordingDispatcher(inner, pw_database.connect, lambda: NOW, listeners, workspace_id=pw_database.workspace_id)


def test_ensure_is_idempotent_and_writes_job_id_for_a_known_job(pw_database):
    with pw_database.connect() as conn:
        ws = pw_database.workspace_id
        seed_job(conn, ws)
        store = PostgresStageRuns(conn, ws)
        assert store.ensure('job-1:render:r2', '7') is True
        assert store.ensure('job-1:render:r2', '9') is False
        assert store.ensure('job-1:render:r3', '7') is True
        extracted = [(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]) for r in rows(conn, ws)]
        assert extracted == [
            ('job-1:render:r2', 'PENDING', 'job-1', None, 'render', 2, '7', 0),
            ('job-1:render:r3', 'PENDING', 'job-1', None, 'render', 3, '7', 0),
        ]


def test_ensure_writes_workflow_id_when_owner_is_not_a_job(pw_database):
    with pw_database.connect() as conn:
        ws = pw_database.workspace_id
        store = PostgresStageRuns(conn, ws)
        assert store.ensure('wf-1:collect:r1') is True
        row = one(conn, ws, 'wf-1:collect:r1')
        assert (row[1], row[2], row[3], row[4], row[5], row[6]) == ('PENDING', None, 'wf-1', 'collect', 1, '0')
        assert store.transition('wf-1:collect:r1', StageRunState.RUNNING, NOW) == StageRunState.RUNNING
        assert one(conn, ws, 'wf-1:collect:r1')[1] == 'RUNNING'


@pytest.mark.parametrize('stage_run_id', [
    'job-1',
    'job-1:render',
    'job-1:render:r0',
    'job-1:render:rx',
    ':render:r1',
    ' :render:r1',
    'job-1: :r1',
    'job-1:render:r1\n',
    'job-1:render:r99999999999',
])
def test_ensure_rejects_malformed_ids_and_writes_nothing(pw_database, stage_run_id):
    with pw_database.connect() as conn:
        ws = pw_database.workspace_id
        store = PostgresStageRuns(conn, ws)
        with pytest.raises(OrchestrationContractError) as info:
            store.ensure(stage_run_id)
        assert info.value.code == 'INVALID_STAGE_RUN_ID'
        assert rows(conn, ws) == []


def test_ensure_rejects_blank_epoch(pw_database):
    with pw_database.connect() as conn:
        ws = pw_database.workspace_id
        store = PostgresStageRuns(conn, ws)
        with pytest.raises(OrchestrationContractError) as info:
            store.ensure('job-1:render:r1', ' ')
        assert info.value.code == 'INVALID_RECOVERY_EPOCH'
        assert rows(conn, ws) == []


def test_transition_updates_columns_through_the_state_machine(pw_database):
    sid = 'job-1:render:r1'
    with pw_database.connect() as conn:
        ws = pw_database.workspace_id
        seed_job(conn, ws)
        store = PostgresStageRuns(conn, ws)
        assert store.ensure(sid, '7') is True
        assert store.transition(sid, StageRunState.RUNNING, NOW, execution_generation=4) == StageRunState.RUNNING
        row = one(conn, ws, sid)
        assert (row[1], row[7], row[10], row[11]) == ('RUNNING', 4, NOW, None)
        assert store.ensure(sid, '7') is False
        problem = {'code': 'RENDER_FAILED', 'retryable': False}
        assert store.transition(sid, StageRunState.FAILED_FINAL, LATER, problem=problem) == StageRunState.FAILED_FINAL
        row = one(conn, ws, sid)
        assert (row[1], row[7], row[9], row[10], row[11], row[12]) == ('FAILED_FINAL', 4, problem, NOW, LATER, LATER)


def test_transition_to_waiting_capability_stores_wait_reason(pw_database):
    sid = 'job-1:tts:r1'
    with pw_database.connect() as conn:
        ws = pw_database.workspace_id
        store = PostgresStageRuns(conn, ws)
        assert store.ensure(sid) is True
        assert store.transition(sid, StageRunState.WAITING_CAPABILITY, NOW, wait_reason='desktop_offline') == StageRunState.WAITING_CAPABILITY
        row = one(conn, ws, sid)
        assert (row[1], row[8], row[10]) == ('WAITING_CAPABILITY', 'desktop_offline', None)


def test_forbidden_edge_raises_and_does_not_write(pw_database):
    sid = 'job-1:render:r1'
    with pw_database.connect() as conn:
        ws = pw_database.workspace_id
        seed_job(conn, ws)
        store = PostgresStageRuns(conn, ws)
        store.ensure(sid)
        store.transition(sid, StageRunState.RUNNING, NOW)
        store.transition(sid, StageRunState.FAILED_FINAL, NOW)
        before = one(conn, ws, sid)
        with pytest.raises(ForbiddenTransitionError):
            store.transition(sid, StageRunState.RUNNING, LATER, execution_generation=9, problem={'code': 'X'})
        assert one(conn, ws, sid) == before


def test_outcome_unknown_exit_needs_evidence(pw_database):
    sid = 'job-1:render:r1'
    with pw_database.connect() as conn:
        ws = pw_database.workspace_id
        seed_job(conn, ws)
        store = PostgresStageRuns(conn, ws)
        store.ensure(sid)
        store.transition(sid, StageRunState.RUNNING, NOW)
        store.transition(sid, StageRunState.OUTCOME_UNKNOWN, NOW)
        with pytest.raises(ForbiddenTransitionError):
            store.transition(sid, StageRunState.SUCCEEDED, LATER)
        assert one(conn, ws, sid)[1] == 'OUTCOME_UNKNOWN'
        assert store.transition(sid, StageRunState.SUCCEEDED, LATER, evidence_ref='reconcile-1') == StageRunState.SUCCEEDED
        assert one(conn, ws, sid)[1] == 'SUCCEEDED'


def test_transition_of_unknown_stage_run_is_rejected(pw_database):
    with pw_database.connect() as conn:
        ws = pw_database.workspace_id
        store = PostgresStageRuns(conn, ws)
        with pytest.raises(OrchestrationContractError) as info:
            store.transition('job-1:render:r1', StageRunState.RUNNING, NOW)
        assert info.value.code == 'NOT_FOUND'


CASES = [
    ('succeeded', {}, 'RUNNING', None, None),
    ('outcome_unknown', {}, 'OUTCOME_UNKNOWN', None, {'activity': 'ProbeMedia'}),
    ('stale', {}, 'RUNNING', None, None),
    ('failed', {'problem': {'code': 'X', 'retryable': True}}, 'RUNNING', None, None),
    ('failed', {'problem': {'code': 'X', 'retryable': False}}, 'FAILED_FINAL', None, {'code': 'X', 'retryable': False, 'activity': 'ProbeMedia'}),
    ('failed', {}, 'FAILED_FINAL', None, {'activity': 'ProbeMedia'}),
    ('waiting', {'problem': {'code': 'quota_wait'}}, 'RUNNING', 'quota_wait', None),
    ('waiting', {}, 'RUNNING', 'provider_unavailable', None),
]


@pytest.mark.parametrize('disposition, extra, status, wait_reason, problem', CASES)
def test_each_disposition_is_committed_in_its_own_transaction(pw_database, disposition, extra, status, wait_reason, problem):
    sid = 'job-1:process:r1'
    seed(pw_database)
    seen = []

    def handler(request, claims):
        seen.append(current(pw_database, sid))
        return result_for(request, disposition, **extra)

    request = request_for(sid)
    assert build(pw_database, handler).dispatch(request) == result_for(request, disposition, **extra)
    before = seen[0]
    assert (before[1], before[6], before[7], before[10], before[11]) == ('RUNNING', '5', 3, NOW, None)
    row = current(pw_database, sid)
    assert (row[1], row[7], row[8], row[9]) == (status, 3, wait_reason, problem)
    assert (row[11] is not None) == (status != 'RUNNING')


def test_activity_rejected_passes_through_and_fails_the_stage_run(pw_database):
    sid = 'job-1:process:r1'
    seed(pw_database)
    dispatcher = build(pw_database, lambda request, claims: {})
    with pytest.raises(ActivityRejected) as info:
        dispatcher.dispatch(request_for(sid, grant=False))
    assert info.value.code == 'MISSING_EXECUTION_GRANT'
    assert [issue['field'] for issue in info.value.issues] == ['execution_grant']
    row = current(pw_database, sid)
    assert (row[1], row[9]) == ('FAILED_FINAL', {'code': 'MISSING_EXECUTION_GRANT', 'retryable': False, 'activity': 'ProbeMedia'})


def test_unrecordable_requests_are_rejected_without_any_row(pw_database):
    dispatcher = build(pw_database, lambda request, claims: {})
    for bad in (42, {'activity_name': 'Nope', 'stage_run_id': 'bad'}):
        with pytest.raises(ActivityRejected) as info:
            dispatcher.dispatch(bad)
        assert info.value.code == 'UNKNOWN_ACTIVITY'
    assert all_rows(pw_database) == []


class Listener:
    def __init__(self, pw_database, stage_run_id):
        self._database = pw_database
        self._stage_run_id = stage_run_id
        self.calls = []

    def on_result(self, request, result):
        self.calls.append((request, result, current(self._database, self._stage_run_id)[1]))


def test_listeners_run_after_the_write_with_request_and_result(pw_database):
    sid = 'job-1:process:r1'
    seed(pw_database)
    first, second = Listener(pw_database, sid), Listener(pw_database, sid)
    request = request_for(sid)
    result = build(pw_database, lambda r, c: result_for(r, 'failed', problem={'code': 'X', 'retryable': False}), [first, second]).dispatch(request)
    for listener in (first, second):
        assert len(listener.calls) == 1
        got_request, got_result, status_at_call = listener.calls[0]
        assert got_request is request and got_result == result and status_at_call == 'FAILED_FINAL'


def test_listeners_are_not_called_when_the_request_is_rejected(pw_database):
    sid = 'job-1:process:r1'
    seed(pw_database)
    listener = Listener(pw_database, sid)
    with pytest.raises(ActivityRejected):
        build(pw_database, lambda r, c: {}, [listener]).dispatch(request_for(sid, grant=False))
    assert listener.calls == []


def test_handler_error_propagates_and_leaves_the_row_running(pw_database):
    sid = 'job-1:process:r1'
    seed(pw_database)

    def handler(request, claims):
        raise RuntimeError('boom')

    with pytest.raises(RuntimeError):
        build(pw_database, handler).dispatch(request_for(sid))
    row = current(pw_database, sid)
    assert (row[1], row[11]) == ('RUNNING', None)


@pytest.mark.parametrize('first, status', [('succeeded', 'SUCCEEDED'), ('failed', 'FAILED_FINAL')])
def test_second_dispatch_of_a_finished_stage_run_keeps_the_row(pw_database, first, status):
    sid = 'job-1:process:r1'
    last = 'PrepareAudioBed'  # activity cuối của stage process; activity không cuối giữ dòng RUNNING nên không tạo dòng đã kết thúc
    seed(pw_database)
    extra = {'problem': {'code': 'X', 'retryable': False}} if first == 'failed' else {}
    queue = [(first, extra), ('succeeded', {})]

    def handler(request, claims):
        disposition, more = queue.pop(0)
        return result_for(request, disposition, **more)

    def last_request():
        request = request_for(sid)
        request['activity_name'] = last
        request['execution_grant']['allowed_operation'] = last
        return request

    listener = Listener(pw_database, sid)
    dispatcher = ResultRecordingDispatcher(ActivityDispatcher({last: handler}), pw_database.connect, lambda: NOW, [listener], workspace_id=pw_database.workspace_id)
    dispatcher.dispatch(last_request())
    before = current(pw_database, sid)
    assert before[1] == status
    assert dispatcher.dispatch(last_request())['disposition'] == 'succeeded'
    assert current(pw_database, sid) == before
    assert len(listener.calls) == 2


def test_sources_have_no_forbidden_tokens_and_stay_synchronous():
    for path in SOURCES:
        text = path.read_text(encoding='utf-8').lower()
        for token in ('from src.', 'import src', 'fake', 'mock', 'asyncio', 'async def', 'await '):
            assert token not in text, (path.name, token)
