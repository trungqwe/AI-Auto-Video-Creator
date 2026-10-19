"""G-06: StageRun theo attempt và áp kết quả activity (CT-ORC-003, CT-STATE-008; D8-G-01, D8-G-02).

coveredIds: CT-ORC-003, CT-STATE-008, CT-WF-006
"""
from __future__ import annotations

import ast
import dataclasses
import pathlib

import pytest

from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.orchestration.stage_run_plan import (
    ATTEMPT_NOT_ALLOWED, FENCING_REJECTED, INVALID_STAGE_RUN_ID, STAGE_NOT_COMMITTED, STAGE_NOT_RUNNING, UNKNOWN_DISPOSITION,
    StageResultPlan, StageRun, StageRunPlanError, apply_activity_result, dependencies_ready, plan_attempt,
)
from controlplane.domain.statemachine import ForbiddenTransitionError, StageRunState

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'domain' / 'orchestration' / 'stage_run_plan.py'
S = StageRunState


def _run(**changes):
    base = dict(stage_run_id='sr-1', job_id='job-1', stage_type='script', input_refs=('in-1', 'in-2'), state=S.FAILED_RETRYABLE, attempt=1, dependency_refs=('collect',), revision=4)
    base.update(changes)
    return StageRun(**base)


def _apply(**changes):
    base = dict(current_state=S.RUNNING, current_revision=4, expected_revision=4, disposition='succeeded', fencing_accepted=True, owner_commit_confirmed=True)
    base.update(changes)
    return apply_activity_result(**base)


@pytest.mark.parametrize('state', [S.WAITING_DEPENDENCY, S.WAITING_CAPABILITY, S.FAILED_RETRYABLE, S.STALE])
def test_plan_attempt_creates_new_pending_row_keeping_identity(state):
    previous = _run(state=state)
    new = plan_attempt(previous, 'sr-2')
    assert new.stage_run_id == 'sr-2' and new is not previous
    assert (new.attempt, new.state, new.revision) == (2, S.PENDING, 0)
    assert (new.job_id, new.stage_type, new.input_refs, new.dependency_refs) == (previous.job_id, previous.stage_type, previous.input_refs, previous.dependency_refs)
    assert previous.state == state and previous.stage_run_id == 'sr-1' and previous.attempt == 1


def test_plan_attempt_chain_increments_attempt_each_time():
    second = plan_attempt(_run(), 'sr-2')
    third = plan_attempt(dataclasses.replace(second, state=S.FAILED_RETRYABLE), 'sr-3')
    assert (third.attempt, third.state, third.stage_run_id) == (3, S.PENDING, 'sr-3')


@pytest.mark.parametrize('state', [S.PENDING, S.RUNNING, S.SUCCEEDED, S.FAILED_FINAL, S.OUTCOME_UNKNOWN])
def test_plan_attempt_rejects_states_that_must_not_get_a_new_attempt(state):
    with pytest.raises(StageRunPlanError) as exc:
        plan_attempt(_run(state=state), 'sr-2')
    assert exc.value.code == ATTEMPT_NOT_ALLOWED


@pytest.mark.parametrize('bad_id', ['', '   ', None, 5, 'sr-1'])
def test_plan_attempt_rejects_invalid_or_reused_stage_run_id(bad_id):
    with pytest.raises(StageRunPlanError) as exc:
        plan_attempt(_run(), bad_id)
    assert exc.value.code == INVALID_STAGE_RUN_ID


def _dep(stage_run_id, stage_type, state, attempt=1, job_id='job-1'):
    return _run(stage_run_id=stage_run_id, stage_type=stage_type, state=state, attempt=attempt, job_id=job_id, dependency_refs=())


def test_dependencies_ready_true_without_dependencies():
    assert dependencies_ready(_run(dependency_refs=()), []) is True


def test_dependencies_ready_true_only_when_every_dependency_succeeded():
    stage = _run(dependency_refs=('collect', 'media'))
    runs = [_dep('a', 'collect', S.SUCCEEDED), _dep('b', 'media', S.SUCCEEDED)]
    assert dependencies_ready(stage, runs) is True
    runs[1] = _dep('b', 'media', S.RUNNING)
    assert dependencies_ready(stage, runs) is False


@pytest.mark.parametrize('state', [s for s in StageRunState if s != StageRunState.SUCCEEDED])
def test_dependencies_ready_false_for_any_non_succeeded_state(state):
    assert dependencies_ready(_run(), [_dep('a', 'collect', state)]) is False


def test_dependencies_ready_false_when_dependency_missing_or_in_other_job():
    assert dependencies_ready(_run(), []) is False
    assert dependencies_ready(_run(), [_dep('a', 'collect', S.SUCCEEDED, job_id='job-2')]) is False


def test_dependencies_ready_uses_latest_attempt_of_each_dependency():
    stage = _run()
    assert dependencies_ready(stage, [_dep('a', 'collect', S.FAILED_RETRYABLE, attempt=1), _dep('b', 'collect', S.PENDING, attempt=2)]) is False
    assert dependencies_ready(stage, [_dep('a', 'collect', S.FAILED_RETRYABLE, attempt=1), _dep('b', 'collect', S.SUCCEEDED, attempt=2)]) is True


def test_four_milestones_render_qc_sync_complete_are_gated_in_order():
    render = _dep('r', 'render', S.SUCCEEDED)
    qc = _run(stage_run_id='q', stage_type='qc', state=S.PENDING, dependency_refs=('render',))
    sync = _run(stage_run_id='s', stage_type='sync', state=S.PENDING, dependency_refs=('qc',))
    complete = _run(stage_run_id='c', stage_type='complete', state=S.PENDING, dependency_refs=('sync',))
    runs = [render, qc, sync, complete]
    assert dependencies_ready(qc, runs) is True
    assert dependencies_ready(sync, runs) is False
    assert dependencies_ready(complete, runs) is False
    runs[1] = dataclasses.replace(qc, state=S.SUCCEEDED)
    assert dependencies_ready(sync, runs) is True
    assert dependencies_ready(complete, runs) is False


@pytest.mark.parametrize('fencing, commit', [(True, False), (False, True), (False, False)])
def test_succeeded_without_fencing_or_owner_commit_is_rejected(fencing, commit):
    with pytest.raises(StageRunPlanError) as exc:
        _apply(fencing_accepted=fencing, owner_commit_confirmed=commit)
    assert exc.value.code == STAGE_NOT_COMMITTED


def test_succeeded_with_fencing_and_owner_commit():
    assert _apply() == StageResultPlan(state=S.SUCCEEDED, revision=5, changed=True, job_waiting=False)


def test_succeeded_from_outcome_unknown_needs_reconciliation_evidence():
    with pytest.raises(ForbiddenTransitionError):
        _apply(current_state=S.OUTCOME_UNKNOWN)
    assert _apply(current_state=S.OUTCOME_UNKNOWN, evidence_ref='recon-1').state == S.SUCCEEDED


@pytest.mark.parametrize('retryable, expected', [(True, S.FAILED_RETRYABLE), (False, S.FAILED_FINAL)])
def test_failed_maps_by_retryable_flag(retryable, expected):
    plan = _apply(disposition='failed', retryable=retryable)
    assert (plan.state, plan.revision, plan.changed, plan.job_waiting) == (expected, 5, True, False)


def test_outcome_unknown_and_stale_dispositions():
    assert _apply(disposition='outcome_unknown').state == S.OUTCOME_UNKNOWN
    assert _apply(disposition='stale', fencing_accepted=False, owner_commit_confirmed=False).state == S.STALE


@pytest.mark.parametrize('disposition', ['failed', 'outcome_unknown', 'waiting'])
def test_unfenced_result_other_than_stale_is_rejected(disposition):
    with pytest.raises(StageRunPlanError) as exc:
        _apply(disposition=disposition, fencing_accepted=False)
    assert exc.value.code == FENCING_REJECTED


def test_waiting_on_running_keeps_stage_and_requests_job_wait():
    assert _apply(disposition='waiting') == StageResultPlan(state=S.RUNNING, revision=4, changed=False, job_waiting=True)


@pytest.mark.parametrize('retryable', [True, False])
def test_waiting_is_never_failed(retryable):
    plan = _apply(disposition='waiting', retryable=retryable, owner_commit_confirmed=False)
    assert plan.state not in {S.FAILED_RETRYABLE, S.FAILED_FINAL}


@pytest.mark.parametrize('state', [s for s in StageRunState if s != StageRunState.RUNNING])
def test_waiting_when_stage_not_running_is_rejected(state):
    with pytest.raises(StageRunPlanError) as exc:
        _apply(disposition='waiting', current_state=state)
    assert exc.value.code == STAGE_NOT_RUNNING


def test_stale_revision_conflicts_for_waiting_and_succeeded():
    with pytest.raises(RevisionConflictError):
        _apply(disposition='waiting', expected_revision=3)
    with pytest.raises(RevisionConflictError):
        _apply(expected_revision=3)


@pytest.mark.parametrize('disposition', ['succeeded', 'failed', 'outcome_unknown', 'stale'])
def test_succeeded_stage_is_never_rerun_by_a_result(disposition):
    with pytest.raises(ForbiddenTransitionError):
        _apply(current_state=S.SUCCEEDED, disposition=disposition)


def test_unknown_disposition_is_rejected():
    with pytest.raises(StageRunPlanError) as exc:
        _apply(disposition='done')
    assert exc.value.code == UNKNOWN_DISPOSITION


@pytest.mark.parametrize('field', ['fencing_accepted', 'owner_commit_confirmed', 'retryable'])
def test_non_bool_flags_raise_type_error(field):
    with pytest.raises(TypeError):
        _apply(**{field: 'yes'})


def test_dataclasses_are_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        _run().state = S.SUCCEEDED
    with pytest.raises(dataclasses.FrozenInstanceError):
        _apply().changed = False


def test_functions_are_pure():
    previous = _run()
    snapshot = dataclasses.replace(previous)
    runs = [_dep('a', 'collect', S.SUCCEEDED)]
    runs_before = list(runs)
    plan_attempt(previous, 'sr-2')
    dependencies_ready(previous, runs)
    assert previous == snapshot and runs == runs_before
    assert _apply() == _apply()


def test_module_imports_only_stdlib_and_controlplane_domain():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    roots, internal = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split('.')[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.add((node.module or '').split('.')[0])
            if (node.module or '').startswith('controlplane'):
                internal.add(node.module)
    assert roots <= {'__future__', 'collections', 'dataclasses', 'controlplane'}
    assert internal == {
        'controlplane.domain.concurrency',
        'controlplane.domain.orchestration.activity_binding',
        'controlplane.domain.statemachine',
    }
