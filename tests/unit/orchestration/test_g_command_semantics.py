"""G-11: ngữ nghĩa retry, biến thể, regenerate và debug (CT-ORC-004/005/006, CT-WF-008; TST-E2E-010, TST-E2E-014).

coveredIds: CT-ORC-004, CT-ORC-005, CT-ORC-006, CT-WF-008
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import pathlib

import pytest

from controlplane.domain.orchestration.command_semantics import (
    CommandSemanticsError,
    DEBUG_AUTO_ADVANCE_FORBIDDEN,
    DEPENDENCY_CYCLE,
    DebugDecision,
    INVALID_NEW_JOB_ID,
    JobContext,
    RETRY_NOT_ALLOWED,
    RegenerateDecision,
    RetryDecision,
    STAGE_JOB_MISMATCH,
    UNKNOWN_STAGE,
    USE_REGENERATE_OR_VARIANT,
    VariantDecision,
    decide_new_variant,
    decide_regenerate,
    decide_retry_stage,
    validate_debug_request,
)
from controlplane.domain.orchestration.stage_run_plan import ATTEMPT_SOURCE_STATES, StageRun
from controlplane.domain.statemachine import StageRunState

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'domain' / 'orchestration' / 'command_semantics.py'
S = StageRunState
JOB = JobContext(
    video_job_id='job-1',
    snapshot_ref='snap-1',
    intent='intent-1',
    input_fingerprint='fp-1',
    parent_article_ref='art-1',
    parent_event_ref='evt-1',
)
RETRYABLE = sorted(ATTEMPT_SOURCE_STATES, key=str)
NON_RETRYABLE = [S.PENDING, S.RUNNING, S.SUCCEEDED, S.FAILED_FINAL, S.OUTCOME_UNKNOWN]


def make_stage(state=S.FAILED_RETRYABLE, attempt=1, job_id='job-1', stage_type='tts'):
    return StageRun(stage_run_id='sr-1', job_id=job_id, stage_type=stage_type, input_refs=('in-1',), state=state, attempt=attempt)


@pytest.mark.parametrize('state', RETRYABLE)
@pytest.mark.parametrize('attempt', (1, 2, 5))
def test_retry_keeps_job_snapshot_intent_and_fingerprint(state, attempt):
    d = decide_retry_stage(JOB, make_stage(state, attempt), 'fp-1')
    assert d.video_job_id == 'job-1'
    assert d.snapshot_ref == 'snap-1'
    assert d.intent == 'intent-1'
    assert d.input_fingerprint == 'fp-1'
    assert d.stage_type == 'tts'
    assert d.attempt == attempt + 1
    assert d.completed_count_delta == 0
    assert d.creates_new_job is False


def test_retry_is_not_a_variant():
    d = decide_retry_stage(JOB, make_stage(), 'fp-1')
    assert not isinstance(d, VariantDecision)
    assert not hasattr(d, 'parent_article_ref')
    assert d.video_job_id == JOB.video_job_id


@pytest.mark.parametrize('state', RETRYABLE + NON_RETRYABLE)
def test_retry_changed_fingerprint_is_rejected(state):
    with pytest.raises(CommandSemanticsError) as exc_info:
        decide_retry_stage(JOB, make_stage(state), 'fp-2')
    assert exc_info.value.code == USE_REGENERATE_OR_VARIANT
    assert exc_info.value.code == 'USE_REGENERATE_OR_VARIANT'


@pytest.mark.parametrize('state', NON_RETRYABLE)
def test_retry_rejects_states_without_new_attempt(state):
    with pytest.raises(CommandSemanticsError) as exc_info:
        decide_retry_stage(JOB, make_stage(state), 'fp-1')
    assert exc_info.value.code == RETRY_NOT_ALLOWED


def test_retry_rejects_stage_of_other_job():
    with pytest.raises(CommandSemanticsError) as exc_info:
        decide_retry_stage(JOB, make_stage(job_id='job-9'), 'fp-1')
    assert exc_info.value.code == STAGE_JOB_MISMATCH


@pytest.mark.parametrize('bad_fp', ('', '  ', None, 5))
def test_retry_invalid_arguments(bad_fp):
    with pytest.raises(ValueError):
        decide_retry_stage(JOB, make_stage(), bad_fp)
    with pytest.raises(TypeError):
        decide_retry_stage('x', make_stage(), 'fp-1')
    with pytest.raises(TypeError):
        decide_retry_stage(JOB, 'x', 'fp-1')


@pytest.mark.parametrize('field', ('video_job_id', 'snapshot_ref', 'intent', 'input_fingerprint', 'parent_article_ref', 'parent_event_ref'))
@pytest.mark.parametrize('bad', ('', '  ', None))
def test_job_context_requires_every_field(field, bad):
    with pytest.raises(ValueError):
        dataclasses.replace(JOB, **{field: bad})


def test_variant_creates_new_job_with_parent_refs():
    prior = ['v-1', 'v-2']
    d = decide_new_variant(JOB, prior, 'job-2')
    assert d.video_job_id == 'job-2'
    assert d.parent_job_id == 'job-1'
    assert d.parent_article_ref == 'art-1'
    assert d.parent_event_ref == 'evt-1'
    assert d.prior_variant_refs == ('v-1', 'v-2')
    assert d.counts_toward_target is False
    assert d.difference_validation_required is True
    assert prior == ['v-1', 'v-2']
    assert not hasattr(d, 'snapshot_ref')
    assert not hasattr(d, 'intent')
    d_empty = decide_new_variant(JOB, (), 'job-2')
    assert d_empty.prior_variant_refs == ()


def test_variant_invalid_arguments():
    with pytest.raises(CommandSemanticsError) as exc_info:
        decide_new_variant(JOB, ['v-1'], 'job-1')
    assert exc_info.value.code == INVALID_NEW_JOB_ID
    for bad_id in ('', '  ', None):
        with pytest.raises(ValueError):
            decide_new_variant(JOB, ['v-1'], bad_id)
    with pytest.raises(ValueError):
        decide_new_variant(JOB, 'abc', 'job-2')
    with pytest.raises(ValueError):
        decide_new_variant(JOB, ['v-1', ''], 'job-2')
    with pytest.raises(TypeError):
        decide_new_variant('x', ['v-1'], 'job-2')


GRAPH = {
    'collect': (),
    'media': ('collect',),
    'script': ('collect',),
    'tts': ('script',),
    'render': ('tts', 'media'),
    'qc': ('render',),
}


@pytest.mark.parametrize(
    ('stage_type', 'expected'),
    [
        ('collect', ('collect', 'media', 'script', 'tts', 'render', 'qc')),
        ('script', ('script', 'tts', 'render', 'qc')),
        ('media', ('media', 'render', 'qc')),
        ('qc', ('qc',)),
    ],
)
def test_regenerate_creates_downstream_revision_only(stage_type, expected):
    stage = make_stage(state=S.SUCCEEDED, stage_type=stage_type)
    d = decide_regenerate(stage, GRAPH)
    assert d.video_job_id == 'job-1'
    assert d.from_stage_type == stage_type
    assert d.revision_stage_types == expected
    assert d.invalidates_downstream_refs is True
    assert d.rewrites_history is False
    assert d.completed_count_delta == 0


def test_regenerate_does_not_mutate_inputs():
    graph = {k: list(v) for k, v in GRAPH.items()}
    before = copy.deepcopy(graph)
    stage = make_stage(state=S.SUCCEEDED, stage_type='script')
    d = decide_regenerate(stage, graph)
    assert graph == before
    assert d == decide_regenerate(stage, GRAPH)
    assert stage.state == S.SUCCEEDED
    assert stage.attempt == 1


def test_regenerate_rejects_bad_graphs():
    with pytest.raises(CommandSemanticsError) as exc_info:
        decide_regenerate(make_stage(stage_type='zzz'), GRAPH)
    assert exc_info.value.code == UNKNOWN_STAGE

    with pytest.raises(CommandSemanticsError) as exc_info:
        decide_regenerate(make_stage(stage_type='a'), {'a': ('ghost',)})
    assert exc_info.value.code == UNKNOWN_STAGE

    for cycle_graph in ({'a': ('b',), 'b': ('a',)}, {'a': ('a',)}):
        with pytest.raises(CommandSemanticsError) as exc_info:
            decide_regenerate(make_stage(stage_type='a'), cycle_graph)
        assert exc_info.value.code == DEPENDENCY_CYCLE

    with pytest.raises(ValueError):
        decide_regenerate(make_stage(stage_type='collect'), [])

    with pytest.raises(ValueError):
        decide_regenerate(make_stage(stage_type='a'), {'a': 'b', 'b': ()})

    with pytest.raises(TypeError):
        decide_regenerate('x', GRAPH)


def test_debug_auto_advance_false_runs_nothing_next():
    d = validate_debug_request(False)
    assert d == DebugDecision(auto_advance=False, auto_run_stage_types=())
    assert d.auto_run_stage_types == ()


def test_debug_auto_advance_true_is_rejected():
    with pytest.raises(CommandSemanticsError) as exc_info:
        validate_debug_request(True)
    assert exc_info.value.code == DEBUG_AUTO_ADVANCE_FORBIDDEN


@pytest.mark.parametrize('bad', (None, 0, 1, 'false', ''))
def test_debug_auto_advance_requires_bool(bad):
    with pytest.raises(TypeError):
        validate_debug_request(bad)


def test_decisions_are_frozen():
    d = RetryDecision(
        video_job_id='job-1',
        snapshot_ref='snap-1',
        intent='intent-1',
        input_fingerprint='fp-1',
        stage_type='tts',
        attempt=2,
        completed_count_delta=0,
        creates_new_job=False,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.attempt = 9
    with pytest.raises(dataclasses.FrozenInstanceError):
        JOB.intent = 'x'


def test_error_exposes_code():
    err = CommandSemanticsError('X')
    assert err.code == 'X'
    assert str(err) == 'X'


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
    assert internal == {'controlplane.domain.orchestration.stage_run_plan'}
