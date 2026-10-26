"""PW-G3: grant_issuer PostgreSQL, GrantRevokingDispatcher và ExecutionGrantCurrency trên PostgreSQL thử.

coveredIds: PW-G3-01..05, CT-WF-004, INV-003, INV-016
"""
from __future__ import annotations

import asyncio
import re
import threading
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from controlplane.api.wiring.workflow import build_temporal_registration, build_workflow_services
from controlplane.application.orchestration.grant_issuance import ActiveGrantExistsError
from controlplane.application.orchestration.grant_runtime import (
    DEFAULT_TTL_BY_QUEUE,
    ExecutionGrantCurrency,
    GrantRevokingDispatcher,
    build_grant_issuer,
)
from controlplane.application.orchestration.result_recorder import ResultRecordingDispatcher
from controlplane.application.orchestration.workflows.activities import (
    ACTIVITY_BINDINGS,
    ActivityDispatcher,
    ActivityRejected,
    claims_to_payload,
)
from controlplane.domain.orchestration import ExecutionGrant, OrchestrationContractError
from controlplane.domain.orchestration.fencing import GrantClaims
from controlplane.infrastructure.db.orchestration.app_session import PostgresAppSessions

ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 10, 26, 1, 2, 3, tzinfo=timezone.utc)
SID = 'wf-1:process:r1'
GRANT_RUNTIME = ROOT / 'src/controlplane/application/orchestration/grant_runtime.py'
WORKFLOW_WIRING = ROOT / 'src/controlplane/api/wiring/workflow.py'
EXPECTED_TTL = {
    'control-workflows': 300,
    'cloud-io': 900,
    'cloud-ai': 900,
    'desktop-cpu': 900,
    'desktop-gpu': 1800,
    'desktop-render': 3600,
}
GRANT_SQL = (
    'SELECT grant_id, execution_generation, recovery_epoch, revoked_at, expires_at - issued_at '
    'FROM controlplane.cp_execution_grants WHERE workspace_id = %s AND stage_run_id = %s ORDER BY execution_generation'
)


def begin_session(pw_database, session_ref='ses-1', epoch='5'):
    with pw_database.connect() as conn:
        return PostgresAppSessions(conn, pw_database.workspace_id).begin(session_ref, epoch)


def issuer_for(pw_database, ttl_by_queue=None):
    return build_grant_issuer(pw_database.connect, pw_database.workspace_id, ttl_by_queue, lambda: NOW)


def grant_rows(pw_database, stage_run_id=SID):
    with pw_database.connect() as conn:
        return conn.execute(GRANT_SQL, (pw_database.workspace_id, stage_run_id)).fetchall()


def live_grants(pw_database):
    with pw_database.connect() as conn:
        return conn.execute(
            'SELECT count(*) FROM controlplane.cp_execution_grants WHERE workspace_id = %s AND revoked_at IS NULL',
            (pw_database.workspace_id,),
        ).fetchone()[0]


def stage_run_row(pw_database, stage_run_id=SID):
    with pw_database.connect() as conn:
        return conn.execute(
            'SELECT status, recovery_epoch FROM controlplane.cp_stage_runs WHERE workspace_id = %s AND stage_run_id = %s',
            (pw_database.workspace_id, stage_run_id),
        ).fetchone()


def request_for(claims, activity_name='ProbeMedia'):
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
        'execution_grant': asdict(claims),
    }


def result_for(request, disposition, **extra):
    g = request['execution_grant']
    return {
        'stage_run_id': g['stage_run_id'],
        'grant_id': g['grant_id'],
        'execution_generation': g['execution_generation'],
        'recovery_epoch': g['recovery_epoch'],
        'disposition': disposition,
        'output_refs': [],
        'completed_at': '2026-10-26T01:02:03Z',
        **extra,
    }


def build_dispatcher(pw_database, handler):
    inner = ActivityDispatcher({'ProbeMedia': handler, 'NormalizeMedia': handler})
    recorder = ResultRecordingDispatcher(inner, pw_database.connect, lambda: NOW, workspace_id=pw_database.workspace_id)
    return GrantRevokingDispatcher(recorder, pw_database.connect, pw_database.workspace_id)


DISPOSITIONS = [
    ('succeeded', {}),
    ('failed', {'problem': {'code': 'X', 'retryable': True}}),
    ('waiting', {}),
    ('outcome_unknown', {}),
    ('stale', {}),
]


def execution_grant(pw_database, claims, **changes):
    values = dict(
        workspace_id=pw_database.workspace_id,
        operation_id=claims.grant_id,
        job_id='job-1',
        stage_run_id=claims.stage_run_id,
        execution_generation=claims.execution_generation,
        recovery_epoch=int(claims.recovery_epoch),
    )
    values.update(changes)
    return ExecutionGrant(**values)


def currency_for(pw_database, now=NOW):
    return ExecutionGrantCurrency(pw_database.connect, pw_database.workspace_id, lambda: now)


def issue_one(pw_database):
    begin_session(pw_database)
    return issuer_for(pw_database)(SID, 'ProbeMedia', 'fp-1', 'lease-1')


PARAMETERS = {
    'workflow.start_to_close_seconds': {
        'control-workflows': 60,
        'cloud-io': 900,
        'cloud-ai': 240,
        'desktop-cpu': 600,
        'desktop-gpu': 900,
        'desktop-render': 1200,
    },
    'workflow.heartbeat_seconds': 30,
    'workflow.retry': {
        'initial_interval_seconds': 5,
        'backoff_coefficient': 2.0,
        'maximum_interval_seconds': 120,
        'maximum_attempts': 3,
    },
    'workflow.schedule': {'cloud_schedule_enabled': False},
    'ai.quota_wait_poll_seconds': 60,
    'meta.revision': 1,
}


def activity_function(grant_issuer, capability_reader, name):
    services = build_workflow_services(
        parameters=PARAMETERS,
        handlers={},
        clock=lambda: NOW,
        timezone_approved=False,
    )
    registration = build_temporal_registration(
        services,
        grant_issuer=grant_issuer,
        capability_reader=capability_reader,
    )
    for fn in registration.activities_by_queue['control-workflows']:
        if getattr(fn, '__temporal_activity_definition').name == name:
            return fn
    raise AssertionError(name)


async def run_with_ticks(awaitable):
    ticks = []

    async def heartbeat():
        while True:
            ticks.append(time.monotonic())
            await asyncio.sleep(0.01)

    task = asyncio.ensure_future(heartbeat())
    try:
        result = await awaitable
    finally:
        task.cancel()
    return result, len(ticks)


def test_default_ttl_table_matches_the_assumption():
    assert dict(DEFAULT_TTL_BY_QUEUE) == EXPECTED_TTL
    with pytest.raises(TypeError):
        DEFAULT_TTL_BY_QUEUE['cloud-io'] = 1


def test_issuer_ensures_the_stage_run_and_inserts_one_grant_in_one_transaction(pw_database):
    begin_session(pw_database)
    claims = issuer_for(pw_database)(SID, 'ProbeMedia', 'fp-1', 'lease-1')
    assert isinstance(claims, GrantClaims)
    assert (claims.execution_generation, claims.recovery_epoch, claims.worker_lease_id) == (1, '5', 'lease-1')
    assert isinstance(claims.recovery_epoch, str)
    assert grant_rows(pw_database) == [(claims.grant_id, 1, '5', None, timedelta(seconds=900))]
    assert stage_run_row(pw_database) == ('PENDING', '5')


def test_same_operation_returns_the_same_live_grant(pw_database):
    begin_session(pw_database)
    issue = issuer_for(pw_database)
    first = issue(SID, 'ProbeMedia', 'fp-1', 'lease-1')
    assert issue(SID, 'ProbeMedia', 'fp-1', 'lease-1') == first
    assert len(grant_rows(pw_database)) == 1


def test_new_session_epoch_revokes_the_old_grant_and_issues_a_string_epoch(pw_database):
    begin_session(pw_database, 'ses-1', '5')
    issue = issuer_for(pw_database)
    first = issue(SID, 'ProbeMedia', 'fp-1', 'lease-1')
    begin_session(pw_database, 'ses-2', '6')
    second = issue(SID, 'ProbeMedia', 'fp-1', 'lease-1')
    assert (second.execution_generation, second.recovery_epoch) == (2, '6')
    assert second.grant_id != first.grant_id
    assert [(r[1], r[2], r[3] is None) for r in grant_rows(pw_database)] == [(1, '5', False), (2, '6', True)]


def test_issuer_without_an_active_session_fails_and_writes_nothing(pw_database):
    with pytest.raises(OrchestrationContractError) as info:
        issuer_for(pw_database)(SID, 'ProbeMedia', 'fp-1', 'lease-1')
    assert info.value.code == 'NOT_FOUND'
    assert grant_rows(pw_database) == []
    assert stage_run_row(pw_database) is None


def test_issuer_rejects_a_malformed_stage_run_id_and_writes_nothing(pw_database):
    begin_session(pw_database)
    with pytest.raises(OrchestrationContractError) as info:
        issuer_for(pw_database)('bad', 'ProbeMedia', 'fp-1', 'lease-1')
    assert info.value.code == 'INVALID_STAGE_RUN_ID'
    assert grant_rows(pw_database, 'bad') == []


def test_ttl_follows_the_task_queue_of_the_operation(pw_database):
    begin_session(pw_database)
    issue = issuer_for(pw_database)
    seen = set()
    for index, binding in enumerate(ACTIVITY_BINDINGS):
        sid = f'wf-1:s{index}:r1'
        issue(sid, binding.name, 'fp-1', 'lease-1')
        seen.add(binding.queue.value)
        assert grant_rows(pw_database, sid)[0][4] == timedelta(seconds=EXPECTED_TTL[binding.queue.value]), binding.name
    assert {'control-workflows', 'cloud-io', 'desktop-cpu', 'desktop-gpu', 'desktop-render'} <= seen
    issue('wf-1:internal:r1', 'IssueExecutionGrant', 'fp-1', 'lease-1')
    assert grant_rows(pw_database, 'wf-1:internal:r1')[0][4] == timedelta(seconds=300)


def test_profile_overrides_replace_only_the_named_queues(pw_database):
    begin_session(pw_database)
    issue = issuer_for(pw_database, {'desktop-gpu': 7200})
    issue('wf-1:script:r1', 'GenerateScript', 'fp-1', 'lease-1')
    issue('wf-1:process:r1', 'ProbeMedia', 'fp-1', 'lease-1')
    assert grant_rows(pw_database, 'wf-1:script:r1')[0][4] == timedelta(seconds=7200)
    assert grant_rows(pw_database, 'wf-1:process:r1')[0][4] == timedelta(seconds=900)


@pytest.mark.parametrize('overrides', [{'nope': 5}, {'desktop-cpu': 0}, {'desktop-cpu': -1}, {'desktop-cpu': True}, {'desktop-cpu': 1.5}, {'desktop-cpu': '900'}])
def test_invalid_overrides_are_rejected_when_the_issuer_is_built(overrides):
    with pytest.raises(ValueError):
        build_grant_issuer(lambda: None, 'ws', overrides, lambda: NOW)


@pytest.mark.parametrize('disposition, extra', DISPOSITIONS)
def test_grant_is_revoked_after_every_disposition(pw_database, disposition, extra):
    begin_session(pw_database)
    claims = issuer_for(pw_database)(SID, 'ProbeMedia', 'fp-1', 'lease-1')
    seen = []

    def handler(request, grant_claims):
        seen.append(live_grants(pw_database))
        return result_for(request, disposition, **extra)

    request = request_for(claims)
    assert build_dispatcher(pw_database, handler).dispatch(request) == result_for(request, disposition, **extra)
    assert seen == [1]
    assert live_grants(pw_database) == 0
    assert grant_rows(pw_database)[0][3] is not None


@pytest.mark.parametrize('error', [RuntimeError('boom'), ActivityRejected('INVALID_ACTIVITY_RESULT')])
def test_grant_is_revoked_when_the_handler_raises(pw_database, error):
    begin_session(pw_database)
    claims = issuer_for(pw_database)(SID, 'ProbeMedia', 'fp-1', 'lease-1')

    def handler(request, grant_claims):
        raise error

    dispatcher = build_dispatcher(pw_database, handler)
    with pytest.raises(type(error)):
        dispatcher.dispatch(request_for(claims))
    assert live_grants(pw_database) == 0


def test_two_activities_of_one_stage_run_one_after_another_each_get_a_grant(pw_database):
    begin_session(pw_database)
    issue = issuer_for(pw_database)

    def handler(request, grant_claims):
        return result_for(request, 'succeeded')

    dispatcher = build_dispatcher(pw_database, handler)

    first = issue(SID, 'ProbeMedia', 'fp-1', 'lease-1')
    dispatcher.dispatch(request_for(first, 'ProbeMedia'))

    second = issue(SID, 'NormalizeMedia', 'fp-1', 'lease-1')
    dispatcher.dispatch(request_for(second, 'NormalizeMedia'))

    assert (first.execution_generation, second.execution_generation) == (1, 2)
    assert first.grant_id != second.grant_id
    assert live_grants(pw_database) == 0


def test_without_revocation_the_second_activity_hits_active_grant_exists(pw_database):
    begin_session(pw_database)
    issue = issuer_for(pw_database)
    first = issue(SID, 'ProbeMedia', 'fp-1', 'lease-1')
    with pytest.raises(ActiveGrantExistsError):
        issue(SID, 'NormalizeMedia', 'fp-1', 'lease-1')


def test_foreign_or_missing_grants_are_left_alone(pw_database):
    begin_session(pw_database)
    claims = issuer_for(pw_database)(SID, 'ProbeMedia', 'fp-1', 'lease-1')
    dispatcher = build_dispatcher(pw_database, lambda request, c: result_for(request, 'succeeded'))

    no_grant = request_for(claims)
    del no_grant['execution_grant']
    with pytest.raises(ActivityRejected) as info:
        dispatcher.dispatch(no_grant)
    assert info.value.code == 'MISSING_EXECUTION_GRANT'

    foreign = request_for(claims)
    foreign['stage_run_id'] = 'wf-1:process:r2'
    with pytest.raises(ActivityRejected) as info:
        dispatcher.dispatch(foreign)
    assert info.value.code == 'INVALID_EXECUTION_GRANT'
    assert live_grants(pw_database) == 1


def test_live_grant_is_current(pw_database):
    claims = issue_one(pw_database)
    assert currency_for(pw_database).is_grant_current(execution_grant(pw_database, claims)) is True


@pytest.mark.parametrize('changes', [
    {'operation_id': 'other'},
    {'execution_generation': 2},
    {'recovery_epoch': 4},
    {'stage_run_id': 'wf-1:process:r2'},
    {'workspace_id': str(uuid.uuid4())},
])
def test_a_mismatching_field_is_not_current(pw_database, changes):
    claims = issue_one(pw_database)
    assert currency_for(pw_database).is_grant_current(execution_grant(pw_database, claims, **changes)) is False


def test_expiry_is_exclusive(pw_database):
    claims = issue_one(pw_database)
    assert currency_for(pw_database, NOW + timedelta(seconds=899)).is_grant_current(execution_grant(pw_database, claims)) is True
    assert currency_for(pw_database, NOW + timedelta(seconds=900)).is_grant_current(execution_grant(pw_database, claims)) is False
    assert currency_for(pw_database, NOW + timedelta(seconds=901)).is_grant_current(execution_grant(pw_database, claims)) is False


def test_a_revoked_grant_is_not_current(pw_database):
    claims = issue_one(pw_database)
    build_dispatcher(pw_database, lambda request, c: result_for(request, 'succeeded')).dispatch(request_for(claims))
    assert currency_for(pw_database).is_grant_current(execution_grant(pw_database, claims)) is False


def test_old_epoch_is_rejected(pw_database):
    claims = issue_one(pw_database)
    begin_session(pw_database, 'ses-2', '6')
    assert currency_for(pw_database).is_grant_current(execution_grant(pw_database, claims)) is False


def test_inv003_older_generation_grant_is_not_current_once_a_newer_one_is_issued(pw_database):
    first = issue_one(pw_database)
    build_dispatcher(pw_database, lambda request, c: result_for(request, 'succeeded')).dispatch(request_for(first))
    second = issuer_for(pw_database)(SID, 'NormalizeMedia', 'fp-1', 'lease-1')
    currency = currency_for(pw_database)
    assert (first.execution_generation, second.execution_generation) == (1, 2)
    assert currency.is_grant_current(execution_grant(pw_database, first)) is False
    assert currency.is_grant_current(execution_grant(pw_database, second)) is True
    assert currency.is_grant_current(execution_grant(pw_database, second, execution_generation=1)) is False


def test_inv016_grant_from_an_old_recovery_epoch_is_rejected_and_reissued_under_the_new_one(pw_database):
    first = issue_one(pw_database)
    begin_session(pw_database, 'ses-2', '6')
    currency = currency_for(pw_database)
    assert currency.is_grant_current(execution_grant(pw_database, first)) is False
    second = issuer_for(pw_database)(SID, 'ProbeMedia', 'fp-1', 'lease-1')
    assert (second.execution_generation, second.recovery_epoch) == (2, '6')
    assert currency.is_grant_current(execution_grant(pw_database, second)) is True
    assert currency.is_grant_current(execution_grant(pw_database, second, recovery_epoch=5)) is False
    assert currency.is_grant_current(execution_grant(pw_database, first)) is False


def test_no_active_session_means_not_current(pw_database):
    claims = issue_one(pw_database)
    with pw_database.connect() as conn:
        PostgresAppSessions(conn, pw_database.workspace_id).end('ses-1')
    assert currency_for(pw_database).is_grant_current(execution_grant(pw_database, claims)) is False


def test_grant_claims_are_not_accepted_in_place_of_an_execution_grant(pw_database):
    claims = issue_one(pw_database)
    currency = currency_for(pw_database)
    assert currency.is_grant_current(claims) is False
    assert currency.is_grant_current(None) is False


def test_issue_grant_activity_does_not_block_the_event_loop_when_postgres_is_slow(pw_database):
    begin_session(pw_database)
    real = issuer_for(pw_database)
    threads = []

    def slow_issuer(*args):
        threads.append(threading.get_ident())
        time.sleep(0.3)
        return real(*args)

    fn = activity_function(slow_issuer, lambda: {}, 'IssueExecutionGrant')
    request = {
        'stage_run_id': SID,
        'allowed_operation': 'ProbeMedia',
        'input_fingerprint': 'fp-1',
        'worker_lease_id': 'lease-1',
    }
    payload, ticks = asyncio.run(run_with_ticks(fn(request)))
    assert threads and threads[0] != threading.get_ident()
    assert ticks >= 10
    assert payload['execution_generation'] == 1 and payload['recovery_epoch'] == '5'
    assert grant_rows(pw_database)[0][0] == payload['grant_id']


def test_read_capability_view_activity_does_not_block_the_event_loop():
    threads = []

    def slow_reader():
        threads.append(threading.get_ident())
        time.sleep(0.3)
        return {'desktop_production': {'status': 'available'}}

    fn = activity_function(lambda *args: None, slow_reader, 'ReadCapabilityView')
    view, ticks = asyncio.run(run_with_ticks(fn({})))
    assert view == {'desktop_production': {'status': 'available'}}
    assert threads and threads[0] != threading.get_ident()
    assert ticks >= 10


def test_grant_runtime_source_is_synchronous_and_uses_the_real_store():
    text = GRANT_RUNTIME.read_text(encoding='utf-8').lower()
    assert 'grantissuer' in text and 'postgresgrantstore' in text
    for token in ('inmemory', 'from src.', 'import src', 'mock', 'fake', 'asyncio', 'async def', 'await '):
        assert token not in text, token


def test_workflow_activities_call_blocking_collaborators_through_to_thread():
    text = WORKFLOW_WIRING.read_text(encoding='utf-8')
    assert re.search(r'await asyncio\.to_thread\(\s*grant_issuer\s*,', text)
    assert re.search(r'await asyncio\.to_thread\(\s*capability_reader\s*\)', text)
