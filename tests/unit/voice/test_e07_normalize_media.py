"""E-07: NormalizeMedia và rendition có lineage (CT-PROC-007).

coveredIds: CT-PROC-007
"""
import ast
import dataclasses
import enum
import pathlib
import re

import pytest

from controlplane.application.idempotency.canonicalization import request_hash
from voice.domain.normalize import (
    FocusRegion,
    NormalizeOperation,
    NormalizeSpec,
    NormalizeStep,
    RenditionPlan,
    compute_spec_fingerprint,
    plan_rendition,
    verify_tool_outcome,
)
from voice.domain.processing import ArtifactRef, Disposition, OutputClass, ProcessingContractError
from voice.ports.media_tool import MediaToolPort, ToolOutcome

ROOT = pathlib.Path(__file__).resolve().parents[3]
SOURCES = (
    ROOT / 'src' / 'voice' / 'domain' / 'normalize.py',
    ROOT / 'src' / 'voice' / 'ports' / 'media_tool.py',
)
SHA_A = 'a' * 64
SHA_B = 'b' * 64
RESIZE = {'width': 1080, 'height': 1920}


def crop_step(x=0, y=0, width=100, height=100):
    return NormalizeStep('crop', {'x': x, 'y': y, 'width': width, 'height': height})


def make_spec(steps=None, tool_version='tool-1', spec_revision='spec-1', seed=None):
    operations = [NormalizeStep('resize', RESIZE)] if steps is None else steps
    return NormalizeSpec(operations, tool_version, spec_revision, seed)


def make_input(ref='in-1', sha=SHA_A):
    return ArtifactRef(ref, sha)


def make_plan(steps=None, kind='image', focus=None, **spec_kwargs):
    return plan_rendition(make_input(), make_spec(steps, **spec_kwargs), kind, focus)


def assert_error(code, call):
    with pytest.raises(ProcessingContractError) as info:
        call()
    assert info.value.code == code
    return info.value


def test_operation_enum_has_exactly_eight_values():
    assert issubclass(NormalizeOperation, enum.StrEnum)
    assert [e.value for e in NormalizeOperation] == [
        'crop', 'resize', 'pad', 'color_conversion', 'transcode', 'audio_normalize', 'extract_frame', 'duration_trim',
    ]


def test_step_maps_known_operation_to_enum_and_keeps_unknown_text():
    assert NormalizeStep('crop', {}).operation is NormalizeOperation.CROP
    assert NormalizeStep('sharpen', {}).operation == 'sharpen'


def test_spec_and_steps_are_frozen_and_immutable():
    spec = make_spec([crop_step(), NormalizeStep('pad', {'color': '#000000'})])
    assert isinstance(spec.operations, tuple)
    assert [str(step.operation) for step in spec.operations] == ['crop', 'pad']
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.tool_version = 'x'
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.operations[0].operation = 'pad'
    with pytest.raises(TypeError):
        spec.operations[0].params['x'] = 1


def test_spec_copies_params_so_caller_mutation_cannot_change_fingerprint():
    params = dict(RESIZE)
    spec = make_spec([NormalizeStep('resize', params)])
    before = spec.spec_fingerprint
    params['width'] = 720
    assert spec.spec_fingerprint == before
    assert spec.operations[0].params['width'] == 1080


def test_spec_fingerprint_is_request_hash_of_spec_payload():
    spec = make_spec(seed=7)
    expected = request_hash({
        'operations': [{'operation': 'resize', 'params': RESIZE}],
        'tool_version': 'tool-1',
        'spec_revision': 'spec-1',
        'seed': 7,
    })
    assert re.fullmatch(r'[0-9a-f]{64}', expected)
    assert compute_spec_fingerprint(spec) == expected
    assert spec.spec_fingerprint == expected


def test_same_spec_same_fingerprint_and_any_change_alters_it():
    base = compute_spec_fingerprint(make_spec(seed=1))
    assert compute_spec_fingerprint(make_spec(seed=1)) == base
    others = (
        make_spec(tool_version='tool-2', seed=1),
        make_spec(spec_revision='spec-2', seed=1),
        make_spec(seed=2),
        make_spec(seed=None),
        make_spec([NormalizeStep('resize', {'width': 720, 'height': 1280})], seed=1),
    )
    for other in others:
        assert compute_spec_fingerprint(other) != base


def test_operation_order_changes_fingerprint_but_params_key_order_does_not():
    first, second = crop_step(), NormalizeStep('resize', RESIZE)
    assert compute_spec_fingerprint(make_spec([first, second])) != compute_spec_fingerprint(make_spec([second, first]))
    reordered = NormalizeStep('resize', {'height': 1920, 'width': 1080})
    assert compute_spec_fingerprint(make_spec([reordered])) == compute_spec_fingerprint(make_spec([second]))


@pytest.mark.parametrize('kwargs, code', [
    ({'steps': []}, 'missing_required'),
    ({'steps': None}, 'missing_required'),
    ({'steps': 'crop'}, 'wrong_type'),
    ({'steps': ['crop']}, 'wrong_type'),
    ({'tool_version': None}, 'missing_required'),
    ({'tool_version': ''}, 'constraint_violation'),
    ({'spec_revision': ' '}, 'constraint_violation'),
    ({'seed': True}, 'wrong_type'),
    ({'seed': 1.5}, 'wrong_type'),
    ({'seed': 2**53}, 'constraint_violation'),
])
def test_spec_rejects_invalid_fields(kwargs, code):
    assert_error(code, lambda: NormalizeSpec(
        kwargs.get('steps', [crop_step()]),
        kwargs.get('tool_version', 'tool-1'),
        kwargs.get('spec_revision', 'spec-1'),
        kwargs.get('seed'),
    ))


@pytest.mark.parametrize('operation, params, code', [
    (None, {}, 'missing_required'),
    ('', {}, 'constraint_violation'),
    ('crop', None, 'missing_required'),
    ('resize', ['width'], 'wrong_type'),
    ('resize', {1: 2}, 'wrong_type'),
    ('resize', {'width': object()}, 'wrong_type'),
    ('resize', {'width': float('nan')}, 'constraint_violation'),
    ('resize', {'width': 2**53}, 'constraint_violation'),
])
def test_step_rejects_invalid_fields(operation, params, code):
    assert_error(code, lambda: NormalizeStep(operation, params))


def test_plan_is_frozen_with_lineage_and_new_output_ref():
    source = make_input()
    plan = plan_rendition(source, make_spec(), 'image', None)
    assert isinstance(plan, RenditionPlan)
    assert plan.input_ref == source
    assert plan.lineage_refs == ('in-1',)
    assert plan.output_ref != source.ref
    assert plan.output_ref == f'rendition:{plan.plan_fingerprint}'
    assert plan.spec_fingerprint == compute_spec_fingerprint(make_spec())
    assert plan.output_class is OutputClass.REUSABLE
    with pytest.raises(dataclasses.FrozenInstanceError):
        plan.output_ref = 'in-1'
    assert (source.ref, source.content_sha256) == ('in-1', SHA_A)


def test_output_ref_equal_to_input_is_rejected():
    assert_error('constraint_violation', lambda: plan_rendition(make_input(), make_spec(), 'image', None, output_ref='in-1'))
    assert_error('constraint_violation', lambda: dataclasses.replace(make_plan(), output_ref='in-1'))
    assert plan_rendition(make_input(), make_spec(), 'image', None, output_ref='out-1').output_ref == 'out-1'


def test_plan_rejects_inconsistent_lineage_or_fingerprints():
    good = make_plan()
    changes = (
        {'spec': make_spec(tool_version='tool-2')},
        {'spec_fingerprint': SHA_B},
        {'plan_fingerprint': SHA_B},
        {'input_ref': make_input(sha=SHA_B)},
        {'lineage_refs': ('other',)},
        {'lineage_refs': ('in-1', good.output_ref)},
    )
    for change in changes:
        assert_error('constraint_violation', lambda change=change: dataclasses.replace(good, **change))


def test_same_input_spec_tool_version_gives_same_fingerprints_and_output_ref():
    first = make_plan(seed=1)
    second = make_plan(seed=1)
    assert first.plan_fingerprint == second.plan_fingerprint
    assert first.spec_fingerprint == second.spec_fingerprint
    assert first.output_ref == second.output_ref
    assert first == second


def test_different_tool_version_or_seed_changes_every_fingerprint():
    base = make_plan(seed=1)
    for other in (make_plan(seed=1, tool_version='tool-2'), make_plan(seed=2), make_plan(seed=None)):
        assert other.spec_fingerprint != base.spec_fingerprint
        assert other.plan_fingerprint != base.plan_fingerprint
        assert other.output_ref != base.output_ref


def test_different_input_changes_plan_fingerprint_but_not_spec_fingerprint():
    base = make_plan()
    for source in (make_input('in-2'), make_input(sha=SHA_B)):
        other = plan_rendition(source, make_spec(), 'image', None)
        assert other.spec_fingerprint == base.spec_fingerprint
        assert other.plan_fingerprint != base.plan_fingerprint
        assert other.output_ref != base.output_ref


@pytest.mark.parametrize('media_kind', ['video', '', None, 'IMAGE'])
def test_plan_rejects_unknown_media_kind(media_kind):
    assert_error('enum_violation', lambda: plan_rendition(make_input(), make_spec(), media_kind, None))


def test_plan_requires_artifact_ref_spec_and_focus_region_types():
    assert_error('wrong_type', lambda: plan_rendition('in-1', make_spec(), 'image', None))
    assert_error('wrong_type', lambda: plan_rendition(make_input(), {'operations': []}, 'image', None))
    assert_error('wrong_type', lambda: plan_rendition(make_input(), make_spec(), 'image', {'x': 1}))


@pytest.mark.parametrize('kind', ['image', 'audio'])
def test_plan_rejects_operations_outside_the_enum(kind):
    for step in (
        NormalizeStep('sharpen', {}),
        NormalizeStep('blur', {'radius': 5}),
        NormalizeStep('resize', {'width': 10, 'height': 10, 'blur': 3}),
    ):
        assert_error('enum_violation', lambda step=step: plan_rendition(make_input(), make_spec([step]), kind, None))


@pytest.mark.parametrize('args, code', [
    ((-1, 0, 1, 1), 'constraint_violation'),
    ((0, 0, 0, 1), 'constraint_violation'),
    ((0, 0, 1, 0), 'constraint_violation'),
    ((0, 0, 1.5, 1), 'wrong_type'),
    ((True, 0, 1, 1), 'wrong_type'),
    ((None, 0, 1, 1), 'missing_required'),
])
def test_focus_region_validates_fields(args, code):
    assert_error(code, lambda: FocusRegion(*args))


FOCUS = FocusRegion(100, 100, 200, 200)


def test_crop_containing_focus_region_is_accepted():
    assert make_plan([crop_step(0, 0, 500, 500)], focus=FOCUS).focus_region == FOCUS
    assert make_plan([crop_step(100, 100, 200, 200)], focus=FOCUS) is not None


@pytest.mark.parametrize('rect', [
    (0, 0, 150, 500), (0, 0, 500, 150), (150, 100, 500, 500), (100, 150, 500, 500),
    (300, 300, 50, 50), (0, 0, 299, 500), (0, 0, 500, 299),
])
def test_crop_that_loses_focus_region_is_rejected(rect):
    error = assert_error('focus_rule_violation', lambda: make_plan([crop_step(*rect)], focus=FOCUS))
    assert error.field == 'operations[0].params'
    assert_error('focus_rule_violation', lambda: make_plan([crop_step(*rect)], kind='clip', focus=FOCUS))


def test_second_crop_losing_focus_is_rejected_with_its_index():
    steps = [NormalizeStep('resize', RESIZE), crop_step(0, 0, 150, 150)]
    error = assert_error('focus_rule_violation', lambda: make_plan(steps, focus=FOCUS))
    assert error.field == 'operations[1].params'


def test_crop_without_focus_region_has_no_focus_constraint():
    assert make_plan([crop_step(0, 0, 10, 10)], focus=None) is not None


def test_focus_rule_is_also_checked_on_direct_plan_construction():
    good = make_plan([crop_step(0, 0, 500, 500)], focus=FOCUS)
    assert_error('focus_rule_violation', lambda: dataclasses.replace(good, focus_region=FocusRegion(450, 450, 100, 100)))


@pytest.mark.parametrize('params, code', [
    ({}, 'missing_required'),
    ({'x': 0, 'y': 0, 'width': 10}, 'missing_required'),
    ({'x': -1, 'y': 0, 'width': 10, 'height': 10}, 'constraint_violation'),
    ({'x': 0, 'y': 0, 'width': 0, 'height': 10}, 'constraint_violation'),
    ({'x': 0, 'y': 0, 'width': 10.5, 'height': 10}, 'wrong_type'),
    ({'x': True, 'y': 0, 'width': 10, 'height': 10}, 'wrong_type'),
    ({'x': '0', 'y': 0, 'width': 10, 'height': 10}, 'wrong_type'),
])
def test_crop_params_are_validated(params, code):
    assert_error(code, lambda: make_plan([NormalizeStep('crop', params)]))


@pytest.mark.parametrize('step', [
    NormalizeStep('blur', {'radius': 5}),
    NormalizeStep('recolor', {'target': 'blood'}),
    NormalizeStep('BLUR', {}),
    NormalizeStep('resize', {'width': 10, 'height': 10, 'blur': 3}),
    NormalizeStep('color_conversion', {'recolor': 'red'}),
])
def test_clip_with_blur_or_recolor_is_rejected(step):
    spec = make_spec([NormalizeStep('resize', RESIZE), step])
    error = assert_error('safety_transform_not_applicable', lambda: plan_rendition(make_input(), spec, 'clip', None))
    assert error.field == 'operations'


def test_clip_technical_normalization_is_accepted():
    steps = [NormalizeStep(op, params) for op, params in (
        ('crop', {'x': 0, 'y': 0, 'width': 100, 'height': 100}),
        ('resize', RESIZE),
        ('pad', {'color': '#000000'}),
        ('color_conversion', {'pixel_format': 'yuv420p'}),
        ('transcode', {'codec': 'h264', 'container': 'mp4'}),
        ('audio_normalize', {'preset': 'audio-policy-1'}),
        ('extract_frame', {'at_ms': 1000}),
        ('duration_trim', {'start_ms': 0, 'end_ms': 5000}),
    )]
    plan = make_plan(steps, kind='clip')
    assert [str(step.operation) for step in plan.spec.operations] == [e.value for e in NormalizeOperation]


@pytest.mark.parametrize('text', [
    'ffmpeg -i in.mp4 out.mp4', 'a; rm -rf /', 'a && b', 'a | b', 'echo `id`', '$(whoami)',
    'a > out.txt', 'a < in.txt', 'line\nbreak', 'bash -c x', 'FFMPEG -y',
])
def test_shell_command_strings_are_rejected_everywhere(text):
    assert_error('shell_command_rejected', lambda: NormalizeStep('resize', {'note': text}))
    assert_error('shell_command_rejected', lambda: NormalizeStep('resize', {text: 1}))
    assert_error('shell_command_rejected', lambda: NormalizeStep('resize', {'args': [text]}))
    assert_error('shell_command_rejected', lambda: make_spec(tool_version=text))
    assert_error('shell_command_rejected', lambda: make_spec(spec_revision=text))
    assert_error('shell_command_rejected', lambda: plan_rendition(make_input(), make_spec(), 'image', None, output_ref=text))


@pytest.mark.parametrize('text', ['h264', 'yuv420p', '9:16', '1080x1920', '#000000', 'bt709', 'audio-policy-1', 'sh', 'convert'])
def test_ordinary_technical_values_are_not_mistaken_for_shell(text):
    assert NormalizeStep('transcode', {'value': text}).params['value'] == text


def test_plan_has_no_command_like_fields_or_values():
    plan = make_plan([crop_step()])
    names = {item.name for item in dataclasses.fields(plan)}
    assert names.isdisjoint({'command', 'cmd', 'argv', 'args', 'shell', 'script', 'command_line'})
    for value in (plan.output_ref, plan.plan_fingerprint, plan.spec_fingerprint, *plan.lineage_refs):
        assert isinstance(value, str)
        assert not any(ch in value for ch in ';&|`$<>()\n')


SUCCESS = {'status': 'succeeded', 'output_ref': 'rendition:x', 'output_sha256': SHA_B}


def test_tool_outcome_is_frozen_with_four_fields():
    assert [item.name for item in dataclasses.fields(ToolOutcome)] == ['status', 'output_ref', 'output_sha256', 'error']
    outcome = ToolOutcome(**SUCCESS)
    assert outcome.status is Disposition.SUCCEEDED
    with pytest.raises(dataclasses.FrozenInstanceError):
        outcome.error = 'x'


@pytest.mark.parametrize('kwargs, code', [
    ({'status': 'bogus'}, 'enum_violation'),
    ({'status': None}, 'missing_required'),
    ({'status': 5}, 'wrong_type'),
    ({'status': 'succeeded'}, 'missing_required'),
    ({'status': 'succeeded', 'output_ref': 'o'}, 'missing_required'),
    ({'status': 'succeeded', 'output_ref': 'o', 'output_sha256': 'ABC'}, 'wrong_type'),
    ({**SUCCESS, 'error': 'boom'}, 'constraint_violation'),
    ({'status': 'failed'}, 'missing_required'),
    ({'status': 'failed', 'error': 'boom', 'output_ref': 'o'}, 'constraint_violation'),
    ({'status': 'failed', 'error': 'boom', 'output_sha256': SHA_B}, 'constraint_violation'),
    ({'status': 'outcome_unknown', 'error': 3}, 'wrong_type'),
])
def test_tool_outcome_rejects_inconsistent_fields(kwargs, code):
    assert_error(code, lambda: ToolOutcome(**kwargs))


def test_non_success_outcomes_carry_no_output():
    assert ToolOutcome('failed', error='boom').status is Disposition.FAILED
    assert ToolOutcome(Disposition.OUTCOME_UNKNOWN).error is None
    assert ToolOutcome('waiting').output_ref is None


class FakeTool:
    def __init__(self):
        self.plans = []

    def run(self, plan):
        self.plans.append(plan)
        return ToolOutcome('succeeded', plan.output_ref, SHA_B)


def test_media_tool_port_is_runtime_protocol_and_fake_conforms():
    assert getattr(MediaToolPort, '_is_protocol', False)
    assert isinstance(FakeTool(), MediaToolPort)
    assert not isinstance(object(), MediaToolPort)
    plan = make_plan()
    tool = FakeTool()
    outcome = tool.run(plan)
    assert isinstance(outcome, ToolOutcome)
    assert tool.plans == [plan]
    verify_tool_outcome(plan, outcome)


def test_verify_tool_outcome_rejects_overwriting_original_or_wrong_output():
    plan = make_plan()
    assert_error('constraint_violation', lambda: verify_tool_outcome(plan, ToolOutcome('succeeded', 'in-1', SHA_B)))
    assert_error('constraint_violation', lambda: verify_tool_outcome(plan, ToolOutcome('succeeded', 'other', SHA_B)))
    verify_tool_outcome(plan, ToolOutcome('failed', error='boom'))
    assert_error('wrong_type', lambda: verify_tool_outcome(None, ToolOutcome('failed', error='x')))
    assert_error('wrong_type', lambda: verify_tool_outcome(plan, {}))


ALLOWED_ROOTS = {'__future__', 'collections', 'dataclasses', 'enum', 'math', 're', 'types', 'typing', 'controlplane', 'voice'}
FORBIDDEN_CALLS = {'system', 'popen', 'Popen', 'check_call', 'check_output', 'exec', 'eval', 'compile', '__import__', 'import_module'}


def imported_names(tree):
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            names.append(node.module)
    return names


def called_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            names.add(func.attr if isinstance(func, ast.Attribute) else getattr(func, 'id', ''))
    return names


@pytest.mark.parametrize('path', SOURCES, ids=lambda path: path.name)
def test_sources_are_pure_and_never_run_processes(path):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    names = imported_names(tree)
    assert {name.split('.')[0] for name in names} <= ALLOWED_ROOTS
    for name in names:
        if name.startswith('controlplane'):
            assert name == 'controlplane.application.idempotency.canonicalization'
    assert not called_names(tree) & FORBIDDEN_CALLS
