"""F-15: VideoOutput, output ready and the four independent milestones (CT-RND-005, TST-E2E-INV-009).

coveredIds: CT-RND-005, TST-E2E-INV-009
"""
import ast
import dataclasses
import itertools
import pathlib
from datetime import datetime, timedelta, timezone

import pytest

from controlplane.domain.statemachine import OperationState
from render.domain import output_ready as module
from render.domain.output_ready import (
    INVALID_INPUT,
    MilestoneState,
    NotReady,
    OutputReady,
    OutputReadyError,
    VideoOutput,
    create_video_output,
    derive_milestones,
    evaluate_output_ready,
)
from render.domain.quality_report import GATE_KINDS, GateKind, GateName, GateResult, GateStatus, build_quality_report
from render.domain.render_attempt import fail_attempt, mark_outcome_unknown, prepare_attempt, start_attempt, succeed_attempt
from render.domain.render_command import RenderCommandSpec, ToolIdentity

ROOT = pathlib.Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'src' / 'render' / 'domain' / 'output_ready.py'
NOW = datetime(2026, 10, 19, 8, 0, 0, tzinfo=timezone.utc)
OUTPUT_REF = 'artifact/render/attempt-1/out.mp4'
GOOD = 'b' * 64
OTHER = 'c' * 64


def at(seconds):
    return NOW + timedelta(seconds=seconds)


def spec():
    identity = ToolIdentity(name='ffmpeg', version='6.1', build='test-build', executable='C:/tools/ffmpeg.exe')
    argv = ('C:/tools/ffmpeg.exe', '-i', 'C:/staging/job1/media/a.mp4')
    return RenderCommandSpec(kind='render', argv=argv, redacted_argv=('{tool}', '-i', '{asset:0}'), spec_fingerprint='f' * 64, tool_identity=identity)


def prepared():
    return prepare_attempt(render_attempt_id='attempt-1', package_fingerprint='a' * 64, output_artifact_ref=OUTPUT_REF, command_spec=spec(), receipt_ref='receipt-1')


def started():
    return start_attempt(prepared(), expected_revision=0, started_at=at(0))


def succeeded():
    return succeed_attempt(started(), expected_revision=1, finished_at=at(60), wall_time_ms=60000)


def failed():
    return fail_attempt(started(), expected_revision=1, finished_at=at(30), error='ffmpeg exited with code 1')


def unknown():
    return mark_outcome_unknown(started(), expected_revision=1, reason='worker timeout after render')


def report(failing=None):
    results = []
    for gate in GateName:
        if gate is failing:
            results.append(GateResult(gate=gate, status=GateStatus.FAILED, reason='gate_failed'))
        elif GATE_KINDS[gate] is not GateKind.WARNING:
            results.append(GateResult(gate=gate, status=GateStatus.PASSED))
    return build_quality_report(results)


def evaluate(**changes):
    args = {'attempt': succeeded(), 'observed_sha256': GOOD, 'report': report(), 'refs_committed': True, 'grant_valid': True, 'expected_sha256': GOOD}
    args.update(changes)
    return evaluate_output_ready(args['attempt'], args['observed_sha256'], args['report'], args['refs_committed'], args['grant_valid'], expected_sha256=args['expected_sha256'])


def output(**changes):
    values = {'video_output_id': 'video-1', 'output_artifact_ref': OUTPUT_REF, 'output_sha256': GOOD, 'quality_report_ref': 'report-1', 'render_attempt_ref': 'attempt-1', 'package_fingerprint': 'a' * 64, 'output_metadata_revision': 'meta-1'}
    values.update(changes)
    return VideoOutput(**values)


TEXT_FIELDS = ('video_output_id', 'output_artifact_ref', 'quality_report_ref', 'render_attempt_ref', 'package_fingerprint', 'output_metadata_revision')


def test_video_output_is_frozen_with_the_ct_rnd_005_fields():
    assert {item.name for item in dataclasses.fields(VideoOutput)} == set(TEXT_FIELDS) | {'output_sha256'}
    item = output(output_sha256=GOOD.upper())
    assert item.output_sha256 == GOOD
    with pytest.raises(dataclasses.FrozenInstanceError):
        item.output_sha256 = OTHER


@pytest.mark.parametrize('field', TEXT_FIELDS)
@pytest.mark.parametrize('bad', ['', ' ', None, 7])
def test_video_output_rejects_blank_or_non_text_fields(field, bad):
    with pytest.raises(OutputReadyError) as caught:
        output(**{field: bad})
    assert caught.value.code == INVALID_INPUT


@pytest.mark.parametrize('bad', ['', 'b' * 63, 'g' * 64, None, 7])
def test_video_output_rejects_malformed_sha256(bad):
    with pytest.raises(OutputReadyError) as caught:
        output(output_sha256=bad)
    assert caught.value.code == INVALID_INPUT


SINGLE_FAILURES = (
    pytest.param({'attempt': prepared()}, 'receipt_not_succeeded', id='receipt_prepared'),
    pytest.param({'attempt': started()}, 'receipt_not_succeeded', id='receipt_started'),
    pytest.param({'attempt': failed()}, 'receipt_not_succeeded', id='receipt_failed'),
    pytest.param({'attempt': unknown()}, 'receipt_not_succeeded', id='receipt_outcome_unknown'),
    pytest.param({'observed_sha256': None}, 'output_missing', id='output_missing'),
    pytest.param({'observed_sha256': OTHER}, 'output_hash_mismatch', id='hash_mismatch'),
    pytest.param({'observed_sha256': 'not-a-hash'}, 'output_hash_mismatch', id='hash_malformed'),
    pytest.param({'expected_sha256': None}, 'expected_sha256_invalid', id='expected_missing'),
    pytest.param({'expected_sha256': 'not-a-hash'}, 'expected_sha256_invalid', id='expected_malformed'),
    pytest.param({'report': report(GateName.VOICE_AUDIBLE)}, 'quality_not_passed', id='qc_voice_failed'),
    pytest.param({'report': report(GateName.DURATION_RANGE)}, 'quality_not_passed', id='qc_duration_failed'),
    pytest.param({'refs_committed': False}, 'refs_not_committed', id='refs_not_committed'),
    pytest.param({'refs_committed': 1}, 'refs_not_committed', id='refs_truthy_int'),
    pytest.param({'grant_valid': False}, 'grant_invalid', id='grant_expired'),
    pytest.param({'grant_valid': None}, 'grant_invalid', id='grant_none'),
    pytest.param({'grant_valid': 'yes'}, 'grant_invalid', id='grant_truthy_text'),
)


def test_ready_only_when_every_condition_holds():
    verdict = evaluate()
    assert isinstance(verdict, OutputReady) and verdict.ready is True
    assert (verdict.render_attempt_ref, verdict.output_artifact_ref, verdict.output_sha256) == ('attempt-1', OUTPUT_REF, GOOD)
    assert verdict.quality_report_ref == report().report_id and verdict.package_fingerprint == 'a' * 64
    with pytest.raises(dataclasses.FrozenInstanceError):
        verdict.output_sha256 = OTHER


def test_hash_compare_ignores_case_and_stores_lower_case():
    assert evaluate(observed_sha256=GOOD.upper()).output_sha256 == GOOD
    assert evaluate(expected_sha256=GOOD.upper()).output_sha256 == GOOD


@pytest.mark.parametrize(('changes', 'reason'), SINGLE_FAILURES)
def test_single_failure_is_not_ready_with_its_reason(changes, reason):
    verdict = evaluate(**changes)
    assert isinstance(verdict, NotReady) and verdict.ready is False
    assert verdict.reasons == (reason,)


def test_every_failed_condition_is_listed_in_order():
    verdict = evaluate(attempt=failed(), observed_sha256=None, report=report(GateName.FILE_PLAYABLE), refs_committed=False, grant_valid=False)
    assert verdict.reasons == ('receipt_not_succeeded', 'output_missing', 'quality_not_passed', 'refs_not_committed', 'grant_invalid')


@pytest.mark.parametrize('changes', [{'attempt': None}, {'attempt': 'attempt-1'}, {'report': None}, {'report': {'passed': True}}])
def test_wrong_input_types_raise_invalid_input(changes):
    with pytest.raises(OutputReadyError) as caught:
        evaluate(**changes)
    assert caught.value.code == INVALID_INPUT


def create(**changes):
    args = {'video_output_id': 'video-1', 'attempt': succeeded(), 'observed_sha256': GOOD, 'expected_sha256': GOOD, 'report': report(), 'refs_committed': True, 'grant_valid': True, 'output_metadata_revision': 'meta-1'}
    args.update(changes)
    return create_video_output(**args)


def test_create_video_output_copies_the_verified_facts():
    item = create()
    assert isinstance(item, VideoOutput)
    assert (item.video_output_id, item.output_artifact_ref, item.output_sha256) == ('video-1', OUTPUT_REF, GOOD)
    assert (item.render_attempt_ref, item.package_fingerprint, item.output_metadata_revision) == ('attempt-1', 'a' * 64, 'meta-1')
    assert item.quality_report_ref == report().report_id


@pytest.mark.parametrize('gate', [GateName.FILE_PLAYABLE, GateName.DURATION_RANGE, GateName.ENGLISH_OUTPUT_VALID, GateName.THUMBNAIL_PRESENT])
def test_qc_fail_never_creates_a_video_output(gate):
    with pytest.raises(OutputReadyError) as caught:
        create(report=report(gate))
    assert caught.value.code == 'quality_not_passed'
    assert caught.value.reasons == ('quality_not_passed',)
    assert str(caught.value).startswith('quality_not_passed')


def test_qc_fail_keeps_its_code_when_other_conditions_also_fail():
    with pytest.raises(OutputReadyError) as caught:
        create(report=report(GateName.VOICE_AUDIBLE), grant_valid=False)
    assert caught.value.code == 'quality_not_passed'
    assert caught.value.reasons == ('quality_not_passed', 'grant_invalid')


@pytest.mark.parametrize('changes', [{'attempt': failed()}, {'observed_sha256': None}, {'observed_sha256': OTHER}, {'refs_committed': False}, {'grant_valid': False}])
def test_other_failed_conditions_raise_output_not_ready(changes):
    with pytest.raises(OutputReadyError) as caught:
        create(**changes)
    assert caught.value.code == 'output_not_ready'
    assert 'quality_not_passed' not in caught.value.reasons


def test_blank_metadata_revision_is_rejected():
    with pytest.raises(OutputReadyError) as caught:
        create(output_metadata_revision=' ')
    assert caught.value.code == INVALID_INPUT


def flags_of(state):
    return (state.render_succeeded, state.qc_passed, state.upload_verified, state.completion_committed)


def test_render_success_with_qc_fail_is_not_ready_and_not_complete():
    attempt, failing = succeeded(), report(GateName.VOICE_AUDIBLE)
    state = derive_milestones(attempt, failing, upload_verified=False, completion_committed=False)
    assert flags_of(state) == (True, False, False, False)
    assert isinstance(evaluate(attempt=attempt, report=failing), NotReady)
    assert state.completion_eligible is False
    assert derive_milestones(attempt, failing, upload_verified=True, completion_committed=False).completion_eligible is False


def test_qc_pass_without_upload_verified_is_ready_but_not_eligible():
    state = derive_milestones(succeeded(), report(), upload_verified=False, completion_committed=False)
    assert isinstance(evaluate(), OutputReady)
    assert flags_of(state) == (True, True, False, False)
    assert state.completion_eligible is False


def test_upload_verified_makes_eligible_without_committing_completion():
    state = derive_milestones(succeeded(), report(), upload_verified=True, completion_committed=False)
    assert flags_of(state) == (True, True, True, False)
    assert state.completion_eligible is True


def test_render_success_is_never_counted_as_completion():
    for attempt in (prepared(), started(), succeeded(), failed(), unknown()):
        state = derive_milestones(attempt, report(), upload_verified=False, completion_committed=False)
        assert state.render_succeeded is (attempt.receipt_state is OperationState.SUCCEEDED)
        assert state.completion_committed is False and state.completion_eligible is False
    committed = derive_milestones(succeeded(), report(), upload_verified=True, completion_committed=True)
    assert committed.completion_committed is True


def test_four_flags_are_independent():
    for flags in itertools.product((False, True), repeat=4):
        state = MilestoneState(render_succeeded=flags[0], qc_passed=flags[1], upload_verified=flags[2], completion_committed=flags[3])
        assert flags_of(state) == flags
        assert state.completion_eligible is (flags[0] and flags[1] and flags[2])


def test_milestone_state_is_frozen_and_strict():
    state = MilestoneState(render_succeeded=True, qc_passed=True, upload_verified=False, completion_committed=False)
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.upload_verified = True
    for bad in (1, 0, None, 'yes'):
        with pytest.raises(OutputReadyError) as caught:
            MilestoneState(render_succeeded=True, qc_passed=True, upload_verified=bad, completion_committed=False)
        assert caught.value.code == INVALID_INPUT
        with pytest.raises(OutputReadyError):
            derive_milestones(succeeded(), report(), upload_verified=True, completion_committed=bad)
    with pytest.raises(OutputReadyError):
        derive_milestones(None, report(), upload_verified=True, completion_committed=False)
    with pytest.raises(OutputReadyError):
        derive_milestones(succeeded(), None, upload_verified=True, completion_committed=False)


FORBIDDEN_PARTS = ('ledger', 'delete', 'remove', 'cleanup', 'unlink', 'rmtree', 'rmdir', 'purge')


def source_tree():
    return ast.parse(SOURCE.read_text(encoding='utf-8'))


def test_module_has_no_completion_ledger_delete_or_cleanup():
    names, functions = set(), set()
    for node in ast.walk(source_tree()):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.add(node.name)
            names.add(node.name)
        elif isinstance(node, ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
    lowered = {name.lower() for name in names}
    assert [name for name in lowered if any(part in name for part in FORBIDDEN_PARTS)] == []
    assert {name for name in lowered if 'complet' in name} <= {'completion_committed', 'completion_eligible'}
    assert [name for name in functions if 'complet' in name.lower() and name != 'completion_eligible'] == []
    assert not any(part in name.lower() for name in dir(module) for part in FORBIDDEN_PARTS)


def test_module_is_pure_and_imports_only_allowed_roots():
    text = SOURCE.read_text(encoding='utf-8')
    for banned in ('import os', 'import time', 'import subprocess', 'import socket', 'import shutil', 'datetime.now', 'utcnow', 'open('):
        assert banned not in text
    roots = set()
    for node in ast.walk(source_tree()):
        if isinstance(node, ast.Import):
            roots |= {item.name.split('.')[0] for item in node.names}
        elif isinstance(node, ast.ImportFrom):
            roots.add(node.module.split('.')[0])
    assert roots <= {'__future__', 're', 'dataclasses', 'controlplane', 'render'}
