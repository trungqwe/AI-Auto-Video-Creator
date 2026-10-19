"""F-11: RenderAttempt, receipt and reconcile of OUTCOME_UNKNOWN (CT-RND-004, CT-STATE-011).

coveredIds: CT-RND-004, CT-STATE-011, TST-SEC-INV-012
"""
import ast
import dataclasses
import json
import pathlib
import re
from datetime import datetime, timedelta, timezone

import pytest

from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.statemachine import ForbiddenTransitionError, OperationState, ReconciliationEvidence
from render.domain import render_attempt as module
from render.domain.render_attempt import (
    INVALID_INPUT,
    OUTPUT_ARTIFACT_REUSED,
    ProbeEvidence,
    RenderAttempt,
    RenderAttemptRejected,
    can_retry_directly,
    fail_attempt,
    mark_outcome_unknown,
    prepare_attempt,
    reconcile_attempt,
    start_attempt,
    succeed_attempt,
)
from render.domain.render_command import RenderCommandSpec, ToolIdentity

ROOT = pathlib.Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'src' / 'render' / 'domain' / 'render_attempt.py'
BACKSLASH = chr(92)
CANARY = 'CANARY-7f3a9c-SECRET'
NOW = datetime(2026, 10, 19, 8, 0, 0, tzinfo=timezone.utc)
OUTPUT_REF = 'artifact/render/attempt-1/out.mp4'
SECOND_REF = 'artifact/render/attempt-2/out.mp4'
S = OperationState
OPERATIONS = ('start', 'succeed', 'fail', 'unknown')


def at(seconds):
    return NOW + timedelta(seconds=seconds)


def spec(redacted=('{tool}', '-i', '{asset:0}'), kind='render'):
    identity = ToolIdentity(name='ffmpeg', version='6.1', build='test-build', executable='C:/tools/ffmpeg.exe')
    argv = ('C:/tools/ffmpeg.exe', '-i', 'C:/staging/job1/media/a.mp4')
    return RenderCommandSpec(kind=kind, argv=argv, redacted_argv=tuple(redacted), spec_fingerprint='f' * 64, tool_identity=identity)


def prepared(**changes):
    args = {'render_attempt_id': 'attempt-1', 'package_fingerprint': 'a' * 64, 'output_artifact_ref': OUTPUT_REF, 'command_spec': spec(), 'receipt_ref': 'receipt-1'}
    args.update(changes)
    return prepare_attempt(**args)


def started():
    return start_attempt(prepared(), expected_revision=0, started_at=at(0))


def succeeded():
    return succeed_attempt(started(), expected_revision=1, finished_at=at(60), wall_time_ms=60000)


def failed():
    return fail_attempt(started(), expected_revision=1, finished_at=at(30), error='ffmpeg exited with code 1')


def unknown():
    return mark_outcome_unknown(started(), expected_revision=1, reason='worker timeout after render')


BUILDERS = {S.PREPARED: prepared, S.STARTED: started, S.SUCCEEDED: succeeded, S.FAILED: failed, S.OUTCOME_UNKNOWN: unknown}


def probe(attempt, **changes):
    values = {'output_artifact_ref': attempt.output_artifact_ref, 'exists': True, 'sha256': 'b' * 64, 'expected_sha256': 'b' * 64, 'playable': True, 'evidence_ref': 'probe-1', 'observed_at': at(90)}
    values.update(changes)
    return ProbeEvidence(**values)


def apply(operation, attempt, expected_revision=None):
    revision = attempt.revision if expected_revision is None else expected_revision
    if operation == 'start':
        return start_attempt(attempt, expected_revision=revision, started_at=at(0))
    if operation == 'succeed':
        return succeed_attempt(attempt, expected_revision=revision, finished_at=at(60), wall_time_ms=60000)
    if operation == 'fail':
        return fail_attempt(attempt, expected_revision=revision, finished_at=at(60), error='boom')
    return mark_outcome_unknown(attempt, expected_revision=revision, reason='timeout')


@pytest.fixture
def calls(monkeypatch):
    seen = []
    real = module.transition_operation

    def spy(**kwargs):
        seen.append(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(module, 'transition_operation', spy)
    return seen


FIELDS = (
    'render_attempt_id', 'package_fingerprint', 'output_artifact_ref', 'tool_name', 'tool_version', 'build_version',
    'started_at', 'finished_at', 'wall_time_ms', 'cpu_metrics', 'gpu_metrics', 'peak_disk_bytes', 'command_spec',
    'warnings', 'receipt_state', 'receipt_ref', 'revision',
)
BAD_REFS = ('C:/out/a.mp4', '/abs/a.mp4', '//server/share/a.mp4', 'a/../b.mp4', 'https://x/y.mp4', 'C:rel/a.mp4', '', ' ', None, 7, BACKSLASH * 2 + 'server' + BACKSLASH + 'share')
BAD_PREPARE = (
    {'render_attempt_id': ''}, {'render_attempt_id': 'a b'}, {'render_attempt_id': None}, {'package_fingerprint': None},
    {'package_fingerprint': ''}, {'receipt_ref': ''}, {'receipt_ref': None}, {'command_spec': None},
    {'command_spec': spec(kind='thumbnail')}, {'previous_output_artifact_refs': 'artifact'},
)


def test_attempt_is_frozen_and_has_the_ct_rnd_004_fields():
    attempt = prepared()
    assert set(FIELDS) <= {item.name for item in dataclasses.fields(RenderAttempt)}
    assert isinstance(attempt.receipt_state, OperationState) and attempt.receipt_state is S.PREPARED
    assert attempt.revision == 0 and attempt.started_at is None and attempt.finished_at is None
    assert (attempt.render_attempt_id, attempt.package_fingerprint, attempt.receipt_ref) == ('attempt-1', 'a' * 64, 'receipt-1')
    assert (attempt.tool_name, attempt.tool_version, attempt.build_version) == ('ffmpeg', '6.1', 'test-build')
    assert attempt.warnings == ()
    with pytest.raises(dataclasses.FrozenInstanceError):
        attempt.revision = 5
    with pytest.raises(dataclasses.FrozenInstanceError):
        started().receipt_state = S.SUCCEEDED


@pytest.mark.parametrize('ref', BAD_REFS)
def test_output_artifact_ref_must_be_a_relative_ref(ref):
    with pytest.raises(RenderAttemptRejected) as caught:
        prepared(output_artifact_ref=ref)
    assert caught.value.code == INVALID_INPUT


@pytest.mark.parametrize('changes', BAD_PREPARE)
def test_prepare_rejects_invalid_inputs(changes):
    with pytest.raises(RenderAttemptRejected) as caught:
        prepared(**changes)
    assert caught.value.code == INVALID_INPUT


def test_new_attempt_gets_its_own_output_and_never_overwrites_the_old_one():
    first = succeeded()
    with pytest.raises(RenderAttemptRejected) as caught:
        prepared(render_attempt_id='attempt-2', previous_output_artifact_refs=[first.output_artifact_ref])
    assert caught.value.code == OUTPUT_ARTIFACT_REUSED
    second = prepared(render_attempt_id='attempt-2', output_artifact_ref=SECOND_REF, previous_output_artifact_refs=[first.output_artifact_ref])
    start_attempt(second, expected_revision=0, started_at=at(100))
    assert second.output_artifact_ref == SECOND_REF != first.output_artifact_ref
    assert (first.receipt_state, first.revision, first.output_artifact_ref) == (S.SUCCEEDED, 2, OUTPUT_REF)
    assert first == succeeded()


ALLOWED = {(S.PREPARED, 'start'), (S.STARTED, 'succeed'), (S.STARTED, 'fail'), (S.STARTED, 'unknown')}
FORBIDDEN = [(state, op) for state in S for op in OPERATIONS if (state, op) not in ALLOWED]
BAD_FINISH = (
    {'finished_at': datetime(2026, 10, 19, 8, 5, 0)}, {'finished_at': at(-5)}, {'finished_at': None}, {'finished_at': '2026-10-19'},
    {'finished_at': at(5), 'wall_time_ms': -1}, {'finished_at': at(5), 'wall_time_ms': True},
    {'finished_at': at(5), 'peak_disk_bytes': 1.5}, {'finished_at': at(5), 'cpu_metrics': {'Bad Key': 1}},
    {'finished_at': at(5), 'gpu_metrics': {'gpu': -1}}, {'finished_at': at(5), 'cpu_metrics': {'cpu': float('nan')}},
    {'finished_at': at(5), 'cpu_metrics': [1]}, {'finished_at': at(5), 'warnings': 'one string'},
)


def test_every_state_change_goes_through_transition_operation(calls):
    attempt = started()
    succeed_attempt(attempt, expected_revision=1, finished_at=at(5))
    fail_attempt(attempt, expected_revision=1, finished_at=at(5), error='boom')
    mark_outcome_unknown(attempt, expected_revision=1, reason='timeout')
    seen = [(c['current_state'], c['requested_state'], c['expected_revision']) for c in calls]
    assert seen == [(S.PREPARED, S.STARTED, 0), (S.STARTED, S.SUCCEEDED, 1), (S.STARTED, S.FAILED, 1), (S.STARTED, S.OUTCOME_UNKNOWN, 1)]
    assert all(c['reconciliation_evidence'] is None and 'current_revision' in c for c in calls)


def test_lifecycle_results_carry_the_inputs():
    one = started()
    assert (one.receipt_state, one.revision, one.started_at) == (S.STARTED, 1, at(0))
    cpu, gpu = {'cpu_percent_avg': 71.5}, {'gpu_percent_avg': 40, 'gpu_memory_peak_bytes': 123}
    done = succeed_attempt(one, expected_revision=1, finished_at=at(60), wall_time_ms=60000, cpu_metrics=cpu, gpu_metrics=gpu, peak_disk_bytes=2048, warnings=['low disk headroom'])
    assert (done.receipt_state, done.revision, done.finished_at, done.wall_time_ms, done.peak_disk_bytes) == (S.SUCCEEDED, 2, at(60), 60000, 2048)
    assert dict(done.cpu_metrics) == cpu and dict(done.gpu_metrics) == gpu and done.warnings == ('low disk headroom',) and done.error is None
    bad = fail_attempt(one, expected_revision=1, finished_at=at(30), error='ffmpeg exited with code 1', wall_time_ms=30000)
    assert (bad.receipt_state, bad.revision, bad.error, bad.wall_time_ms) == (S.FAILED, 2, 'ffmpeg exited with code 1', 30000)
    lost = mark_outcome_unknown(one, expected_revision=1, reason='worker timeout after render')
    assert (lost.receipt_state, lost.revision, lost.finished_at, lost.error) == (S.OUTCOME_UNKNOWN, 2, None, 'worker timeout after render')
    assert (one.receipt_state, one.revision) == (S.STARTED, 1)


@pytest.mark.parametrize(('state', 'operation'), FORBIDDEN)
def test_forbidden_edges_raise(state, operation):
    attempt = BUILDERS[state]()
    with pytest.raises(ForbiddenTransitionError) as caught:
        apply(operation, attempt)
    assert caught.value.current_state == state
    assert attempt == BUILDERS[state]()


@pytest.mark.parametrize('operation', OPERATIONS)
def test_wrong_expected_revision_raises(operation):
    attempt = BUILDERS[S.PREPARED if operation == 'start' else S.STARTED]()
    for wrong in (attempt.revision + 1, attempt.revision + 7, -1):
        with pytest.raises(RevisionConflictError) as caught:
            apply(operation, attempt, expected_revision=wrong)
        assert caught.value.current_revision == attempt.revision


@pytest.mark.parametrize('case', BAD_FINISH)
def test_finish_inputs_are_validated(case):
    with pytest.raises(RenderAttemptRejected) as caught:
        succeed_attempt(started(), expected_revision=1, **case)
    assert caught.value.code == INVALID_INPUT


def test_start_and_error_inputs_are_validated():
    with pytest.raises(RenderAttemptRejected):
        start_attempt(prepared(), expected_revision=0, started_at=datetime(2026, 10, 19, 8, 0, 0))
    for error in ('', '   ', None, 5):
        with pytest.raises(RenderAttemptRejected):
            fail_attempt(started(), expected_revision=1, finished_at=at(5), error=error)
        with pytest.raises(RenderAttemptRejected):
            mark_outcome_unknown(started(), expected_revision=1, reason=error)


MISSING = {'exists': False, 'sha256': None, 'playable': None}
INCONCLUSIVE = (
    {'exists': None}, {'exists': 1}, {'evidence_ref': None}, {'evidence_ref': ' '}, {'evidence_ref': 'bad ref'},
    {'playable': None}, {'sha256': None}, {'expected_sha256': None}, {'sha256': 'xyz'}, {'expected_sha256': 'short'},
    {'output_artifact_ref': 'artifact/render/other/out.mp4'}, {'output_artifact_ref': None},
)


def test_reconcile_succeeds_only_for_present_playable_matching_output():
    attempt = unknown()
    result = reconcile_attempt(attempt, probe(attempt))
    assert (result.receipt_state, result.revision, result.error, result.finished_at) == (S.SUCCEEDED, 3, None, at(90))
    assert (attempt.receipt_state, attempt.revision) == (S.OUTCOME_UNKNOWN, 2)


@pytest.mark.parametrize(('changes', 'reason'), [
    (MISSING, 'reconcile_output_missing'),
    ({'playable': False}, 'reconcile_output_corrupt'),
    ({'sha256': 'c' * 64}, 'reconcile_output_corrupt'),
])
def test_reconcile_missing_or_corrupt_output_fails(changes, reason):
    attempt = unknown()
    result = reconcile_attempt(attempt, probe(attempt, **changes))
    assert (result.receipt_state, result.revision, result.error) == (S.FAILED, 3, reason)
    assert can_retry_directly(result) is True


@pytest.mark.parametrize('changes', INCONCLUSIVE)
def test_reconcile_stays_outcome_unknown_when_the_probe_cannot_conclude(changes):
    attempt = unknown()
    result = reconcile_attempt(attempt, probe(attempt, **changes))
    assert result == attempt and result.receipt_state is S.OUTCOME_UNKNOWN and result.revision == 2
    assert can_retry_directly(result) is False


@pytest.mark.parametrize('bad_probe', [None, object(), 'probe-1'])
def test_reconcile_ignores_a_value_that_is_not_probe_evidence(bad_probe):
    attempt = unknown()
    assert reconcile_attempt(attempt, bad_probe) == attempt


@pytest.mark.parametrize('state', [S.PREPARED, S.STARTED, S.SUCCEEDED, S.FAILED])
def test_reconcile_only_applies_to_outcome_unknown(state):
    attempt = BUILDERS[state]()
    with pytest.raises(ForbiddenTransitionError):
        reconcile_attempt(attempt, probe(attempt))
    assert attempt == BUILDERS[state]()


def test_reconcile_passes_reconciliation_evidence_to_transition_operation(calls):
    attempt = unknown()
    calls.clear()
    reconcile_attempt(attempt, probe(attempt))
    assert len(calls) == 1
    assert calls[0]['reconciliation_evidence'] == ReconciliationEvidence(reference='probe-1')
    assert (calls[0]['current_state'], calls[0]['requested_state']) == (S.OUTCOME_UNKNOWN, S.SUCCEEDED)


def test_reconcile_with_a_stale_revision_raises():
    attempt = unknown()
    for changes in ({}, {'exists': None}):
        with pytest.raises(RevisionConflictError) as caught:
            reconcile_attempt(attempt, probe(attempt, **changes), expected_revision=attempt.revision - 1)
        assert caught.value.current_revision == attempt.revision


def test_outcome_unknown_is_never_retried_directly():
    attempt = unknown()
    assert can_retry_directly(attempt) is False
    assert can_retry_directly(reconcile_attempt(attempt, probe(attempt, exists=None))) is False
    for state in (S.PREPARED, S.STARTED, S.SUCCEEDED):
        assert can_retry_directly(BUILDERS[state]()) is False
    reconciled = reconcile_attempt(attempt, probe(attempt, **MISSING))
    assert reconciled.receipt_state is S.FAILED and can_retry_directly(reconciled) is True
    retry = prepared(render_attempt_id='attempt-2', output_artifact_ref=SECOND_REF, previous_output_artifact_refs=[reconciled.output_artifact_ref])
    assert retry.output_artifact_ref != reconciled.output_artifact_ref and retry.receipt_state is S.PREPARED


UNC = BACKSLASH * 2 + 'server' + BACKSLASH + 'admin' + BACKSLASH
ERROR_TEXTS = (
    'render failed: password=' + CANARY,
    'render failed: api_key: ' + CANARY,
    'upstream said Authorization: Bearer ' + CANARY,
    'failed writing C:/Users/admin/work/out.mp4',
    'failed writing C:/Users/admin/' + CANARY + '/out.mp4',
    'failed writing C:' + BACKSLASH + 'Users' + BACKSLASH + 'admin' + BACKSLASH + CANARY + BACKSLASH + 'out.mp4',
    'failed writing /home/admin/' + CANARY + '/out.mp4',
    'failed writing ' + UNC + CANARY + BACKSLASH + 'out.mp4',
    'x' * 2000,
)


def leaks(attempt):
    views = (repr(attempt), json.dumps(attempt.to_dict(), default=str), attempt.to_json(), str(attempt.error), str(attempt.warnings), attempt.command_spec)
    return [marker for marker in (CANARY, 'admin', 'C:/', '/home') for view in views if marker in view]


@pytest.mark.parametrize('text', ERROR_TEXTS)
def test_error_and_warning_text_is_redacted_in_every_view(text):
    bad = fail_attempt(started(), expected_revision=1, finished_at=at(5), error=text, warnings=[text])
    lost = mark_outcome_unknown(started(), expected_revision=1, reason=text, warnings=[text])
    ok = succeed_attempt(started(), expected_revision=1, finished_at=at(5), warnings=[text])
    for attempt in (bad, lost, ok):
        assert leaks(attempt) == []
    assert len(bad.error) <= 500 and len(lost.error) <= 500 and bad.error


def test_declared_secret_values_are_removed_wherever_they_appear():
    text = 'tool said ' + CANARY + ' while writing out.mp4'
    bad = fail_attempt(started(), expected_revision=1, finished_at=at(5), error=text, secret_values=[CANARY])
    ok = succeed_attempt(started(), expected_revision=1, finished_at=at(5), warnings=[text], secret_values=(CANARY,))
    lost = mark_outcome_unknown(started(), expected_revision=1, reason=text, secret_values=[CANARY])
    for attempt in (bad, ok, lost):
        assert leaks(attempt) == []
    assert '[REDACTED]' in bad.error and 'out.mp4' in bad.error


def test_command_spec_is_redacted_and_never_holds_argv():
    attempt = prepared(command_spec=spec(redacted=('{tool}', '-i', 'C:/Users/admin/in.mp4', 'token=' + CANARY)))
    assert leaks(attempt) == []
    for view in (repr(attempt), attempt.to_json(), attempt.command_spec):
        assert 'C:/tools' not in view and 'C:/staging' not in view
    parsed = json.loads(attempt.command_spec)
    assert parsed['kind'] == 'render' and parsed['spec_fingerprint'] == 'f' * 64
    assert attempt.to_dict()['command_spec'] == parsed
    assert attempt.to_dict()['receipt_state'] == 'PREPARED'


def test_attempt_has_no_completed_field_or_function():
    names = set()
    for node in ast.walk(ast.parse(SOURCE.read_text(encoding='utf-8'))):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
    assert [name for name in names if 'complet' in name.lower()] == []
    assert not any('complet' in name.lower() for name in dir(module))
    attempt = succeeded()
    assert attempt.receipt_state is S.SUCCEEDED
    assert not hasattr(attempt, 'completed') and 'completed' not in attempt.to_dict()


def test_module_is_pure_and_reuses_the_shared_state_machine():
    text = SOURCE.read_text(encoding='utf-8')
    assert 'from controlplane.domain.statemachine import' in text and 'transition_operation' in text
    assert re.search(r'class \w*State\b', text) is None
    for banned in ('import os', 'import time', 'import subprocess', 'import socket', 'import shutil', 'datetime.now', 'utcnow', 'open('):
        assert banned not in text
