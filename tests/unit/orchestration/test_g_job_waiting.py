"""G-06: job waiting và cổng R18 (CT-ORC-007, CT-WF-007, CT-STATE-009).

coveredIds: CT-ORC-007, CT-WF-007, CT-STATE-009, CT-CAP-003
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.orchestration.job_waiting import (
    Proceed, Wait, WaitReason, evaluate_wait, on_capability_restored, plan_job_transition, stage_requires_desktop,
)
from controlplane.domain.orchestration.stage_run_plan import StageRun
from controlplane.domain.statemachine import ForbiddenTransitionError, JobState, StageRunState, TransitionResult, transition_job

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'domain' / 'orchestration' / 'job_waiting.py'
S = StageRunState
J = JobState
DESKTOP_STAGES = ['script', 'plan', 'tts']
OFFLINE_WAIT = Wait(WaitReason.DESKTOP_OFFLINE)


def _view(status):
    return {'desktop_production': {'status': status}}


def test_wait_reason_has_exactly_the_eight_ct_orc_007_values():
    assert [r.value for r in WaitReason] == [
        'desktop_offline', 'local_ai_unavailable', 'provider_unavailable', 'quota_wait',
        'artifact_not_ready', 'insufficient_disk', 'dependency_wait', 'credential_unavailable',
    ]


@pytest.mark.parametrize('stage_type', DESKTOP_STAGES)
def test_stage_requires_desktop_true_for_r18_stages(stage_type):
    assert stage_requires_desktop(stage_type) is True


@pytest.mark.parametrize('stage_type', ['collect', 'normalize', 'dedup', 'media', 'index'])
def test_stage_requires_desktop_false_for_cloud_stages(stage_type):
    assert stage_requires_desktop(stage_type) is False


@pytest.mark.parametrize('bad', [None, 5, b'script', ['script']])
def test_stage_requires_desktop_rejects_non_str(bad):
    with pytest.raises(TypeError):
        stage_requires_desktop(bad)


@pytest.mark.parametrize('view', [_view('unavailable'), _view('unknown'), {}, None])
def test_collection_proceeds_while_script_waits_desktop_offline(view):
    assert evaluate_wait('collect', view) == Proceed()
    assert evaluate_wait('script', view) == OFFLINE_WAIT


@pytest.mark.parametrize('stage_type', DESKTOP_STAGES)
@pytest.mark.parametrize('view', [
    None, {}, 'available', ['available'], {'desktop_production': None}, {'desktop_production': 'available'},
    {'desktop_production': {}}, {'desktop_production': {'status': []}}, {'desktop_production': {'status': 'garbage'}},
    _view('unavailable'), _view('unknown'), {'other_capability': {'status': 'available'}},
])
def test_desktop_stage_waits_unless_desktop_is_available_or_degraded(stage_type, view):
    assert evaluate_wait(stage_type, view) == OFFLINE_WAIT


@pytest.mark.parametrize('stage_type', DESKTOP_STAGES)
@pytest.mark.parametrize('status', ['available', 'degraded'])
def test_desktop_stage_proceeds_when_desktop_runs(stage_type, status):
    assert evaluate_wait(stage_type, _view(status)) == Proceed()


@pytest.mark.parametrize('state, decision, expected', [(J.ACTIVE, OFFLINE_WAIT, J.WAITING), (J.WAITING, Proceed(), J.ACTIVE)])
def test_plan_job_transition_moves_between_active_and_waiting(state, decision, expected):
    plan = plan_job_transition(current_state=state, current_revision=7, expected_revision=7, decision=decision)
    assert plan == TransitionResult(state=expected, revision=8)


@pytest.mark.parametrize('state, decision', [(J.ACTIVE, Proceed()), (J.WAITING, OFFLINE_WAIT)])
def test_plan_job_transition_is_noop_when_already_in_target(state, decision):
    assert plan_job_transition(current_state=state, current_revision=7, expected_revision=7, decision=decision) is None


@pytest.mark.parametrize('decision', [Proceed(), OFFLINE_WAIT])
@pytest.mark.parametrize('state', [J.CREATED, J.SNAPSHOTTED, J.READY_FOR_COMPLETION, J.COMPLETED, J.FAILED_FINAL])
def test_plan_job_transition_rejects_other_job_states(state, decision):
    with pytest.raises(ForbiddenTransitionError):
        plan_job_transition(current_state=state, current_revision=7, expected_revision=7, decision=decision)


def test_capability_loss_never_fails_the_job():
    for state in (J.ACTIVE, J.WAITING):
        for decision in (Proceed(), OFFLINE_WAIT, evaluate_wait('script', _view('unknown'))):
            plan = plan_job_transition(current_state=state, current_revision=1, expected_revision=1, decision=decision)
            assert plan is None or plan.state in {J.ACTIVE, J.WAITING}


def test_plan_job_transition_revision_conflict_and_bad_decision():
    with pytest.raises(RevisionConflictError):
        plan_job_transition(current_state=J.ACTIVE, current_revision=7, expected_revision=6, decision=OFFLINE_WAIT)
    with pytest.raises(TypeError):
        plan_job_transition(current_state=J.ACTIVE, current_revision=7, expected_revision=7, decision='wait')


def test_ready_for_completion_is_not_completed():
    assert J.READY_FOR_COMPLETION != J.COMPLETED
    with pytest.raises(ForbiddenTransitionError):
        transition_job(current_state=J.ACTIVE, current_revision=1, expected_revision=1, requested_state=J.COMPLETED)
    ready = transition_job(current_state=J.ACTIVE, current_revision=1, expected_revision=1, requested_state=J.READY_FOR_COMPLETION)
    assert ready.state == J.READY_FOR_COMPLETION
    done = transition_job(current_state=J.READY_FOR_COMPLETION, current_revision=ready.revision, expected_revision=ready.revision, requested_state=J.COMPLETED)
    assert done.state == J.COMPLETED


def _run(stage_run_id, stage_type, state, attempt=1, job_id='job-1'):
    return StageRun(stage_run_id=stage_run_id, job_id=job_id, stage_type=stage_type, input_refs=('in-1',), state=state, attempt=attempt)


RUNS = [
    _run('sr-collect', 'collect', S.SUCCEEDED),
    _run('sr-script', 'script', S.WAITING_CAPABILITY),
    _run('sr-tts', 'tts', S.WAITING_CAPABILITY),
    _run('sr-plan', 'plan', S.WAITING_DEPENDENCY),
    _run('sr-index', 'index', S.RUNNING),
]


def test_restored_returns_only_waiting_capability_stages_not_whole_pipeline():
    before = list(RUNS)
    assert on_capability_restored(RUNS, _view('available')) == ('sr-script', 'sr-tts')
    assert RUNS == before


@pytest.mark.parametrize('view', [_view('unavailable'), _view('unknown'), {}, None])
def test_restored_returns_nothing_while_desktop_still_down(view):
    assert on_capability_restored(RUNS, view) == ()


def test_restored_empty_runs():
    assert on_capability_restored([], _view('available')) == ()


def test_restored_skips_superseded_rows_and_other_jobs_are_independent():
    runs = [
        _run('sr-script-1', 'script', S.WAITING_CAPABILITY, attempt=1),
        _run('sr-script-2', 'script', S.PENDING, attempt=2),
        _run('sr-other-script', 'script', S.WAITING_CAPABILITY, attempt=1, job_id='job-2'),
    ]
    assert on_capability_restored(runs, _view('available')) == ('sr-other-script',)


def test_restored_cloud_stage_waiting_capability_is_reevaluated_even_when_desktop_down():
    runs = [_run('sr-collect', 'collect', S.WAITING_CAPABILITY), _run('sr-script', 'script', S.WAITING_CAPABILITY)]
    assert on_capability_restored(runs, _view('unavailable')) == ('sr-collect',)


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
    assert roots <= {'__future__', 'collections', 'dataclasses', 'enum', 'controlplane'}
    assert internal == {'controlplane.domain.orchestration.stage_run_plan', 'controlplane.domain.statemachine'}
