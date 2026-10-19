"""G-13: audit nhất quán chỉ đọc (R5 no-silent-failure; INV-010, INV-017, INV-018)."""
import ast
import copy
import dataclasses
import inspect
import pathlib

import pytest

from controlplane.domain.orchestration import ReservationState
from controlplane.domain.orchestration import consistency_audit as ca
from controlplane.domain.orchestration.consistency_audit import BatchRecord, ConsistencySnapshot, Finding, GrantRecord, JobRecord, LedgerRecord, ReservationRecord, StageRunRecord, audit_consistency
from controlplane.domain.orchestration.job_waiting import WaitReason
from controlplane.domain.statemachine import JobState, StageRunState

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'domain' / 'orchestration' / 'consistency_audit.py'
JOB_IDS = ('job-1', 'job-2', 'job-3')


def job(job_id, state=JobState.ACTIVE, reason=None, logs=('log-1',)):
    return JobRecord(job_id, state, reason, logs)


def batch(count=1):
    return BatchRecord('b-1', count, JOB_IDS)


def snapshot(**override):
    fields = {
        'batches': (batch(),),
        'jobs': (job('job-1', JobState.COMPLETED), job('job-2'), job('job-3', JobState.WAITING, WaitReason.DESKTOP_OFFLINE)),
        'reservations': (
            ReservationRecord('res-1', 'job-1', ReservationState.CONVERTED),
            ReservationRecord('res-2', 'job-2', ReservationState.ACTIVE),
            ReservationRecord('res-3', 'job-3', ReservationState.ACTIVE),
        ),
        'ledgers': (LedgerRecord('led-1', 'b-1', 'job-1'),),
        'stage_runs': (StageRunRecord('run-1', 'job-2', StageRunState.RUNNING),),
        'grants': (GrantRecord('run-1', True),),
    }
    return ConsistencySnapshot(**(fields | override))


def finding(code, ref):
    return Finding(code, ref)


def test_finding_codes_are_the_six_spec_codes_in_order():
    assert ca.FINDING_CODES == ('LEDGER_COUNT_MISMATCH', 'ORPHAN_ACTIVE_RESERVATION', 'LEDGER_WITHOUT_COMPLETED_JOB', 'WAITING_JOB_WITHOUT_REASON', 'RUNNING_STAGE_WITHOUT_ACTIVE_GRANT', 'JOB_WITHOUT_STATE_OR_LOG')


def test_consistent_snapshot_returns_empty_tuple():
    result = audit_consistency(snapshot())
    assert result == () and isinstance(result, tuple)
    assert audit_consistency(ConsistencySnapshot()) == ()


@pytest.mark.parametrize('count', [0, 2])
def test_batch_counter_differing_from_ledger_is_reported(count):
    result = audit_consistency(snapshot(batches=(batch(count),)))
    assert result == (finding('LEDGER_COUNT_MISMATCH', 'b-1'),)


def test_ledger_count_is_compared_per_batch():
    other = BatchRecord('b-2', 0)
    assert audit_consistency(snapshot(batches=(batch(), other))) == ()


def test_active_reservation_for_missing_job_is_orphan():
    reservations = snapshot().reservations + (ReservationRecord('res-9', 'job-x', ReservationState.ACTIVE),)
    assert audit_consistency(snapshot(reservations=reservations)) == (finding('ORPHAN_ACTIVE_RESERVATION', 'res-9'),)


def test_active_reservation_for_completed_job_is_orphan():
    reservations = snapshot().reservations + (ReservationRecord('res-9', 'job-1', ReservationState.ACTIVE),)
    assert audit_consistency(snapshot(reservations=reservations)) == (finding('ORPHAN_ACTIVE_RESERVATION', 'res-9'),)

def test_active_reservation_for_failed_final_job_is_orphan():
    jobs = snapshot().jobs + (job('job-4', JobState.FAILED_FINAL),)
    reservations = snapshot().reservations + (ReservationRecord('res-9', 'job-4', ReservationState.ACTIVE),)
    assert audit_consistency(snapshot(jobs=jobs, reservations=reservations)) == (finding('ORPHAN_ACTIVE_RESERVATION', 'res-9'),)


@pytest.mark.parametrize('state', [ReservationState.RELEASED, ReservationState.CONVERTED])
def test_non_active_reservation_is_never_orphan(state):
    reservations = snapshot().reservations + (ReservationRecord('res-9', 'job-x', state),)
    assert audit_consistency(snapshot(reservations=reservations)) == ()


@pytest.mark.parametrize('job_id', ['job-2', 'job-x'])
def test_ledger_for_missing_or_not_completed_job_is_reported(job_id):
    ledgers = snapshot().ledgers + (LedgerRecord('led-2', 'b-1', job_id),)
    assert audit_consistency(snapshot(batches=(batch(2),), ledgers=ledgers)) == (finding('LEDGER_WITHOUT_COMPLETED_JOB', 'led-2'),)


@pytest.mark.parametrize('reason', [None, '', 'bogus', 5])
def test_waiting_job_without_valid_reason_is_reported(reason):
    jobs = (job('job-1', JobState.COMPLETED), job('job-2'), job('job-3', JobState.WAITING, reason))
    assert audit_consistency(snapshot(jobs=jobs)) == (finding('WAITING_JOB_WITHOUT_REASON', 'job-3'),)


@pytest.mark.parametrize('reason', list(WaitReason) + [member.value for member in WaitReason])
def test_waiting_job_with_every_known_reason_is_consistent(reason):
    jobs = (job('job-1', JobState.COMPLETED), job('job-2'), job('job-3', JobState.WAITING, reason))
    assert audit_consistency(snapshot(jobs=jobs)) == ()


@pytest.mark.parametrize('grants', [(), (GrantRecord('run-1', False),), (GrantRecord('run-2', True),)], ids=['no_grant', 'inactive_grant', 'grant_of_other_run'])
def test_running_stage_without_active_grant_is_reported(grants):
    assert audit_consistency(snapshot(grants=grants)) == (finding('RUNNING_STAGE_WITHOUT_ACTIVE_GRANT', 'run-1'),)


def test_running_stage_state_given_as_string_is_still_checked():
    runs = (StageRunRecord('run-1', 'job-2', 'RUNNING'),)
    assert audit_consistency(snapshot(stage_runs=runs, grants=())) == (finding('RUNNING_STAGE_WITHOUT_ACTIVE_GRANT', 'run-1'),)


@pytest.mark.parametrize('state', [state for state in StageRunState if state != StageRunState.RUNNING])
def test_non_running_stage_without_grant_is_consistent(state):
    runs = (StageRunRecord('run-1', 'job-2', state),)
    assert audit_consistency(snapshot(stage_runs=runs, grants=())) == ()

@pytest.mark.parametrize('state', [None, 'bogus', 5])
def test_job_without_valid_state_is_reported(state):
    jobs = (job('job-1', JobState.COMPLETED), job('job-2', state), job('job-3', JobState.WAITING, WaitReason.DESKTOP_OFFLINE))
    assert audit_consistency(snapshot(jobs=jobs)) == (finding('JOB_WITHOUT_STATE_OR_LOG', 'job-2'),)


def test_job_without_log_is_reported():
    jobs = (job('job-1', JobState.COMPLETED), job('job-2', logs=()), job('job-3', JobState.WAITING, WaitReason.DESKTOP_OFFLINE))
    assert audit_consistency(snapshot(jobs=jobs)) == (finding('JOB_WITHOUT_STATE_OR_LOG', 'job-2'),)


def test_job_without_state_and_log_is_reported_once():
    jobs = (job('job-1', JobState.COMPLETED), job('job-2', None, logs=()), job('job-3', JobState.WAITING, WaitReason.DESKTOP_OFFLINE))
    assert audit_consistency(snapshot(jobs=jobs)) == (finding('JOB_WITHOUT_STATE_OR_LOG', 'job-2'),)


def test_job_vanished_from_jobs_but_listed_in_batch_is_reported():
    jobs = (job('job-1', JobState.COMPLETED), job('job-3', JobState.WAITING, WaitReason.DESKTOP_OFFLINE))
    result = audit_consistency(snapshot(jobs=jobs))
    assert result == (finding('JOB_WITHOUT_STATE_OR_LOG', 'job-2'), finding('ORPHAN_ACTIVE_RESERVATION', 'res-2'))


def faulty():
    reservations = (
        ReservationRecord('res-9', 'job-x', ReservationState.ACTIVE),
        ReservationRecord('res-5', 'job-y', ReservationState.ACTIVE),
    ) + snapshot().reservations
    return snapshot(batches=(batch(3),), reservations=reservations)


def test_findings_are_sorted_by_code_then_ref():
    result = audit_consistency(faulty())
    assert result == (finding('LEDGER_COUNT_MISMATCH', 'b-1'), finding('ORPHAN_ACTIVE_RESERVATION', 'res-5'), finding('ORPHAN_ACTIVE_RESERVATION', 'res-9'))
    assert result == tuple(sorted(result, key=lambda item: (item.code, item.ref)))


def test_result_does_not_depend_on_input_order():
    base = faulty()
    reordered = dataclasses.replace(base, reservations=tuple(reversed(base.reservations)), jobs=tuple(reversed(base.jobs)))
    assert audit_consistency(reordered) == audit_consistency(base)


def test_two_calls_are_equal_and_snapshot_is_unchanged():
    target = faulty()
    before = copy.deepcopy(target)
    first = audit_consistency(target)
    second = audit_consistency(target)
    assert first == second and first != ()
    assert target == before


def test_finding_and_snapshot_are_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        finding('X', 'y').code = 'Z'
    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot().batches = ()

@pytest.mark.parametrize('bad', [None, {}, (), 'text', [BatchRecord('b', 0)]])
def test_non_snapshot_argument_raises_type_error(bad):
    with pytest.raises(TypeError):
        audit_consistency(bad)


@pytest.mark.parametrize(
    'factory',
    [
        lambda: BatchRecord('', 1),
        lambda: BatchRecord(5, 1),
        lambda: BatchRecord('b', True),
        lambda: BatchRecord('b', -1),
        lambda: BatchRecord('b', '1'),
        lambda: BatchRecord('b', 1, ['job-1']),
        lambda: BatchRecord('b', 1, ('',)),
        lambda: JobRecord('', JobState.ACTIVE),
        lambda: JobRecord('j', None, None, ['x']),
        lambda: ReservationRecord(' ', 'j', ReservationState.ACTIVE),
        lambda: LedgerRecord('l', '', 'j'),
        lambda: StageRunRecord('r', None, StageRunState.RUNNING),
        lambda: GrantRecord('r', 1),
        lambda: GrantRecord(None, True),
        lambda: ConsistencySnapshot(batches=[BatchRecord('b', 0)]),
        lambda: ConsistencySnapshot(jobs=(object(),)),
    ],
)
def test_malformed_records_raise_type_error(factory):
    with pytest.raises(TypeError):
        factory()


def test_signature_takes_only_the_snapshot():
    assert list(inspect.signature(audit_consistency).parameters) == ['snapshot']


def test_module_is_pure_and_imports_only_domain():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.add(node.module.split('.')[0])
            if node.module.startswith('controlplane'):
                assert node.module.startswith('controlplane.domain')
    assert roots <= {'__future__', 'dataclasses', 'controlplane'}
    attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert attributes & {'now', 'utcnow', 'today', 'open', 'read_text', 'write_text'} == set()
