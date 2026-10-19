"""E-06: TransformSensitiveImage (CT-PROC-006).

coveredIds: CT-PROC-006, TST-E2E-011 (phía E, mức domain)
"""
import ast
import dataclasses
import pathlib
import re

import pytest

from voice.domain.image_safety import (
    DetectionStatus,
    ImageDetection,
    ImageSafetyAssessment,
    ImageSafetyError,
    ImageSafetyPolicy,
    SafetyNotApplicable,
    SafetyOutcome,
    assess_image_safety,
)
from voice.domain.image_transform import (
    TransformOutput,
    TransformPolicy,
    TransformPort,
    TransformRegion,
    TransformRequest,
    TransformResult,
    TransformSkipped,
    TransformStatus,
    transform_sensitive_image,
)
from voice.domain.processing import ArtifactRef

ROOT = pathlib.Path(__file__).resolve().parents[3]
# GIẢ ĐỊNH: revision, tên hành động và profile chỉ dùng trong fixture; policy thật chờ ROADMAP-OPEN-006 (CP7-E-03).
SAFETY_POLICY = ImageSafetyPolicy('safety-test-1', 0.8, ('child', 'gore', 'weapon'), True)
TRANSFORM_POLICY = TransformPolicy(
    'transform-test-1', {'child': 'action-child-a', 'gore': 'action-gore-b', 'weapon': 'action-weapon-c'}
)
ORIGINAL = ArtifactRef('artifact://image/original-1', 'a' * 64)
PROCESSED = ArtifactRef('artifact://image/processed-1', 'b' * 64)
PROFILE = {'format': 'png', 'max_edge_px': 1024}


def assessed(*categories: str, confidence: float = 0.95) -> ImageSafetyAssessment:
    detection = ImageDetection(DetectionStatus.COMPLETED, categories, confidence)
    return assess_image_safety('image', detection, SAFETY_POLICY)


UNREADABLE_POST = assess_image_safety('image', ImageDetection(DetectionStatus.UNREADABLE), SAFETY_POLICY)
FAILED_POST = ImageSafetyAssessment(SafetyOutcome.TRANSFORM_FAILED, True, 'x', ('x',))


def region(category: str) -> TransformRegion:
    return TransformRegion(category, 0.9, f'artifact://mask/{category}')


class FakeTransformPort:
    def __init__(self, post=None, processed=PROCESSED, raises=None, bad_result=None) -> None:
        self.post = assessed() if post is None else post
        self.processed = processed
        self.raises = raises
        self.bad_result = bad_result
        self.calls: list = []

    def transform(self, request):
        self.calls.append(request)
        if self.raises is not None:
            raise self.raises
        if self.bad_result is not None:
            return self.bad_result
        return TransformOutput(self.processed, 'artifact://evidence/1', 'fake-processor-1', self.post)


def run(port, *categories, kind='image', hook=False, policy=TRANSFORM_POLICY, assessment=None):
    categories = categories or ('weapon',)
    assessment = assessed(*categories) if assessment is None else assessment
    regions = tuple(region(c) for c in categories)
    return transform_sensitive_image(kind, hook, assessment, ORIGINAL, regions, policy, PROFILE, port)


def test_weapon_request_carries_category_policy_revision_and_policy_action() -> None:
    port = FakeTransformPort()
    result = run(port, 'weapon')
    assert isinstance(result, TransformResult)
    assert len(port.calls) == 1
    request = port.calls[0]
    assert isinstance(request, TransformRequest)
    assert request.categories == ('weapon',)
    assert request.transform_policy_revision == 'transform-test-1'
    assert request.actions == (('weapon', 'action-weapon-c'),)
    assert request.source_ref is ORIGINAL
    assert request.output_profile == PROFILE
    assert [item.category for item in request.regions] == ['weapon']


def test_actions_come_from_policy_not_from_constants() -> None:
    other = TransformPolicy('transform-test-2', {'weapon': 'action-weapon-z', 'child': 'action-child-y'})
    port = FakeTransformPort()
    run(port, 'weapon', policy=other)
    run(port, 'child', 'weapon')
    assert port.calls[0].actions == (('weapon', 'action-weapon-z'),)
    assert port.calls[0].transform_policy_revision == 'transform-test-2'
    assert port.calls[1].actions == (('child', 'action-child-a'), ('weapon', 'action-weapon-c'))


@pytest.mark.parametrize(
    ('policy_actions', 'categories', 'missing'),
    [
        ({'child': 'x'}, ('weapon',), 'weapon'),
        ({'child': 'x'}, ('child', 'weapon'), 'weapon'),
        ({'weapon': 'x'}, ('child', 'gore'), 'child'),
    ],
)
def test_category_without_action_is_input_not_ready(policy_actions: dict, categories: tuple, missing: str) -> None:
    port = FakeTransformPort()
    with pytest.raises(ImageSafetyError) as exc:
        run(port, *categories, policy=TransformPolicy('transform-test-1', policy_actions))
    assert (exc.value.code, exc.value.reason) == ('INPUT_NOT_READY', f'missing_action:{missing}')
    assert port.calls == []


def test_missing_policy_or_port_is_input_not_ready() -> None:
    port = FakeTransformPort()
    with pytest.raises(ImageSafetyError) as exc:
        run(port, policy=None)
    assert (exc.value.code, exc.value.reason) == ('INPUT_NOT_READY', 'missing_policy')
    with pytest.raises(ImageSafetyError) as exc:
        run(None)
    assert (exc.value.code, exc.value.reason) == ('INPUT_NOT_READY', 'missing_port')
    assert port.calls == []


def test_success_result_references_original_and_processed() -> None:
    result = run(FakeTransformPort())
    assert result.status is TransformStatus.SUCCESS
    assert result.outcome is SafetyOutcome.SAFE
    assert result.original_ref is ORIGINAL
    assert result.processed_ref == PROCESSED
    assert result.evidence_ref == 'artifact://evidence/1'
    assert result.processor_version == 'fake-processor-1'
    assert result.lineage == (ORIGINAL,)
    assert result.warnings == ()


@pytest.mark.parametrize('kind', ['clip', 'audio', 'video', ''])
def test_non_image_is_not_applicable_and_port_is_not_called(kind: str) -> None:
    port = FakeTransformPort()
    expected = SafetyNotApplicable(media_kind=kind)
    assert run(port, kind=kind) == expected
    assert run(port, kind=kind, hook=True) == expected
    assert run(port, kind=kind, policy=None) == expected
    assert run(None, kind=kind) == expected
    assert port.calls == []


@pytest.mark.parametrize('kind', [None, 3, b'image'])
def test_media_kind_must_be_text(kind: object) -> None:
    with pytest.raises(ImageSafetyError) as exc:
        run(FakeTransformPort(), kind=kind)
    assert (exc.value.code, exc.value.reason) == ('wrong_type', 'media_kind')


def test_user_visual_hook_is_skipped_but_source_thumbnail_still_runs() -> None:
    port = FakeTransformPort()
    skipped = run(port, hook=True)
    assert skipped == TransformSkipped('hook_already_blurred')
    assert skipped.reason == 'hook_already_blurred'
    assert run(port, hook=True, policy=None) == skipped
    assert port.calls == []
    thumbnail = run(port, hook=False)
    assert isinstance(thumbnail, TransformResult)
    assert len(port.calls) == 1


@pytest.mark.parametrize('flag', [None, 'yes', 1])
def test_user_visual_hook_flag_must_be_bool(flag: object) -> None:
    with pytest.raises(ImageSafetyError) as exc:
        run(FakeTransformPort(), hook=flag)
    assert (exc.value.code, exc.value.reason) == ('wrong_type', 'user_visual_hook')


def test_assessment_must_require_transform() -> None:
    port = FakeTransformPort()
    for assessment in (assessed(), assessed('weapon', confidence=0.4)):
        with pytest.raises(ImageSafetyError) as exc:
            run(port, assessment=assessment)
        assert (exc.value.code, exc.value.reason) == ('constraint_violation', 'assessment_not_transform_required')
    with pytest.raises(ImageSafetyError) as exc:
        run(port, assessment={'outcome': 'TRANSFORM_REQUIRED'})
    assert (exc.value.code, exc.value.reason) == ('wrong_type', 'assessment')
    assert port.calls == []


def assert_failed_and_original_kept(result: object, reason: str) -> None:
    assert isinstance(result, TransformResult)
    assert result.status is TransformStatus.FAILURE
    assert result.status is not TransformStatus.SUCCESS
    assert result.outcome is SafetyOutcome.TRANSFORM_FAILED
    assert result.post_assessment.original_usable is True
    assert result.processed_ref is None
    assert result.original_ref is ORIGINAL
    assert result.lineage == (ORIGINAL,)
    assert result.post_assessment.categories == ('weapon',)
    assert reason in result.warnings
    assert reason in result.post_assessment.warnings
    assert result.post_assessment.policy_revision == 'transform-test-1'


def test_transform_raising_is_failure_and_does_not_leak_text() -> None:
    result = run(FakeTransformPort(raises=RuntimeError('canary-secret-token')))
    assert_failed_and_original_kept(result, 'transform_raised')
    assert 'canary-secret-token' not in repr(result)


FAILING_OUTPUTS = (
    ('still_required', {'post': assessed('weapon')}, 'post_assessment_still_transform_required'),
    ('unreadable', {'post': UNREADABLE_POST}, 'processed_unreadable'),
    ('post_transform_failed', {'post': FAILED_POST}, 'post_assessment_transform_failed'),
    ('bad_result', {'bad_result': {'processed_ref': PROCESSED}}, 'transform_bad_result'),
    ('replaces_original', {'processed': ORIGINAL}, 'processed_replaces_original'),
    ('same_ref_new_hash', {'processed': ArtifactRef(ORIGINAL.ref, 'c' * 64)}, 'processed_replaces_original'),
)


@pytest.mark.parametrize(
    ('kwargs', 'reason'), [case[1:] for case in FAILING_OUTPUTS], ids=[case[0] for case in FAILING_OUTPUTS]
)
def test_bad_transform_outputs_are_failure_never_success(kwargs: dict, reason: str) -> None:
    assert_failed_and_original_kept(run(FakeTransformPort(**kwargs)), reason)


def test_inconclusive_post_assessment_is_warning_not_success() -> None:
    cases = (
        (assessed(confidence=0.4), SafetyOutcome.UNCERTAIN),
        (assess_image_safety('image', None, SAFETY_POLICY), SafetyOutcome.DETECTION_FAILED),
    )
    for post, expected in cases:
        result = run(FakeTransformPort(post=post))
        assert result.status is TransformStatus.WARNING
        assert result.outcome is expected
        assert result.processed_ref == PROCESSED
        assert result.original_ref is ORIGINAL
        assert result.warnings == (f'post_assessment_{expected.value.lower()}',)


def test_only_safe_post_assessment_yields_success() -> None:
    posts = (
        assessed(),
        assessed('weapon'),
        assessed(confidence=0.4),
        assess_image_safety('image', None, SAFETY_POLICY),
        UNREADABLE_POST,
    )
    statuses = {post.outcome: run(FakeTransformPort(post=post)).status for post in posts}
    assert statuses == {
        SafetyOutcome.SAFE: TransformStatus.SUCCESS,
        SafetyOutcome.TRANSFORM_REQUIRED: TransformStatus.FAILURE,
        SafetyOutcome.UNCERTAIN: TransformStatus.WARNING,
        SafetyOutcome.DETECTION_FAILED: TransformStatus.WARNING,
        SafetyOutcome.UNREADABLE: TransformStatus.FAILURE,
    }


def test_original_ref_is_never_replaced() -> None:
    snapshot = ArtifactRef(ORIGINAL.ref, ORIGINAL.content_sha256)
    ports = (
        FakeTransformPort(),
        FakeTransformPort(raises=RuntimeError('x')),
        FakeTransformPort(post=assessed('weapon')),
    )
    for port in ports:
        result = run(port)
        assert port.calls[0].source_ref is ORIGINAL
        assert result.original_ref is ORIGINAL
        assert result.original_ref != result.processed_ref
    assert ORIGINAL == snapshot


def test_models_are_frozen_and_normalized() -> None:
    port = FakeTransformPort()
    result = run(port, 'weapon', 'child')
    request = port.calls[0]
    frozen_targets = (
        (request, 'source_ref'),
        (result, 'status'),
        (TRANSFORM_POLICY, 'revision'),
        (region('child'), 'category'),
        (TransformOutput(PROCESSED, 'e', 'v', assessed()), 'processed_ref'),
        (TransformSkipped(), 'reason'),
    )
    for obj, field in frozen_targets:
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(obj, field, 'x')
    assert request.categories == ('child', 'weapon')
    assert isinstance(request.regions, tuple)
    assert isinstance(request.actions, tuple)
    assert isinstance(TRANSFORM_POLICY.actions, tuple)
    assert isinstance(result.warnings, tuple)


def test_output_profile_is_copied_and_read_only() -> None:
    profile = {'format': 'png', 'nested': {'k': 1}}
    request = TransformRequest(ORIGINAL, [region('weapon')], ['weapon'], {'weapon': 'a'}, 'rev-1', profile)
    profile['nested']['k'] = 2
    profile['format'] = 'jpg'
    assert request.output_profile == {'format': 'png', 'nested': {'k': 1}}
    with pytest.raises(TypeError):
        request.output_profile['format'] = 'jpg'


@pytest.mark.parametrize(
    'kwargs',
    [
        {'revision': ''},
        {'revision': None},
        {'actions': {}},
        {'actions': 'weapon'},
        {'actions': {'weapon': ''}},
        {'actions': {'': 'a'}},
        {'actions': {'weapon': 3}},
        {'actions': [('weapon', 'a'), ('weapon', 'b')]},
    ],
)
def test_policy_rejects_invalid_values(kwargs: dict) -> None:
    with pytest.raises(ImageSafetyError):
        TransformPolicy(**{'revision': 'r', 'actions': {'weapon': 'a'}, **kwargs})


@pytest.mark.parametrize(
    'kwargs',
    [
        {'category': ''},
        {'confidence': 1.5},
        {'confidence': True},
        {'confidence': float('nan')},
        {'confidence': '0.9'},
        {'mask_ref': ''},
        {'mask_ref': None},
    ],
)
def test_region_rejects_invalid_values(kwargs: dict) -> None:
    with pytest.raises(ImageSafetyError):
        TransformRegion(**{'category': 'weapon', 'confidence': 0.9, 'mask_ref': 'm', **kwargs})


REQUEST_BASE = {
    'source_ref': ORIGINAL,
    'regions': (region('weapon'),),
    'categories': ('weapon',),
    'actions': {'weapon': 'a'},
    'transform_policy_revision': 'rev-1',
    'output_profile': PROFILE,
}
REQUEST_BAD_CASES = (
    ({'source_ref': 'x'}, 'wrong_type', 'source_ref'),
    ({'regions': ()}, 'constraint_violation', 'regions'),
    ({'regions': (region('gore'),)}, 'constraint_violation', 'regions'),
    ({'regions': 'x'}, 'wrong_type', 'regions'),
    ({'regions': [1]}, 'wrong_type', 'regions'),
    ({'categories': ()}, 'constraint_violation', 'categories'),
    ({'actions': {}}, 'constraint_violation', 'actions'),
    ({'actions': {'gore': 'a'}}, 'constraint_violation', 'actions'),
    ({'transform_policy_revision': ''}, 'constraint_violation', 'transform_policy_revision'),
    ({'output_profile': {}}, 'constraint_violation', 'output_profile'),
    ({'output_profile': 'x'}, 'wrong_type', 'output_profile'),
)


@pytest.mark.parametrize(('override', 'code', 'reason'), REQUEST_BAD_CASES)
def test_request_constructor_rejects_invalid_values(override: dict, code: str, reason: str) -> None:
    with pytest.raises(ImageSafetyError) as exc:
        TransformRequest(**{**REQUEST_BASE, **override})
    assert (exc.value.code, exc.value.reason) == (code, reason)


def result_kwargs(**override: object) -> dict:
    base = {
        'status': 'success',
        'original_ref': ORIGINAL,
        'processed_ref': PROCESSED,
        'evidence_ref': 'e',
        'processor_version': 'v',
        'post_assessment': assessed(),
        'warnings': (),
    }
    return {**base, **override}


NO_PROCESSED = {'processed_ref': None, 'evidence_ref': None, 'processor_version': None}
SAME_REF = ArtifactRef(ORIGINAL.ref, 'c' * 64)
BAD = 'constraint_violation'
RESULT_BAD_CASES = (
    ('success_failed_post', {'post_assessment': FAILED_POST}, BAD, 'post_assessment'),
    ('success_required_post', {'post_assessment': assessed('weapon')}, BAD, 'post_assessment'),
    ('success_no_processed', {'processed_ref': None}, 'wrong_type', 'processed_ref'),
    ('success_processed_is_original', {'processed_ref': SAME_REF}, BAD, 'processed_ref'),
    ('success_empty_evidence', {'evidence_ref': ''}, BAD, 'evidence_ref'),
    ('success_no_version', {'processor_version': None}, 'wrong_type', 'processor_version'),
    ('success_with_warnings', {'warnings': ('w',)}, BAD, 'warnings'),
    ('warning_safe_post', {'status': 'warning', 'warnings': ('w',)}, BAD, 'post_assessment'),
    ('warning_no_warnings', {'status': 'warning', 'post_assessment': assessed(confidence=0.4)}, BAD, 'warnings'),
    ('failure_safe_post', {'status': 'failure', 'warnings': ('w',), **NO_PROCESSED}, BAD, 'post_assessment'),
    (
        'failure_with_processed',
        {'status': 'failure', 'post_assessment': FAILED_POST, 'warnings': ('w',), 'evidence_ref': None, 'processor_version': None},
        BAD,
        'processed_ref',
    ),
    ('bad_status', {'status': 'ok'}, 'enum_violation', 'status'),
    ('status_not_text', {'status': 3}, 'wrong_type', 'status'),
    ('original_not_ref', {'original_ref': 'x'}, 'wrong_type', 'original_ref'),
    ('post_not_assessment', {'post_assessment': {}}, 'wrong_type', 'post_assessment'),
)


@pytest.mark.parametrize(
    ('override', 'code', 'reason'), [case[1:] for case in RESULT_BAD_CASES], ids=[case[0] for case in RESULT_BAD_CASES]
)
def test_result_constructor_enforces_status_invariants(override: dict, code: str, reason: str) -> None:
    with pytest.raises(ImageSafetyError) as exc:
        TransformResult(**result_kwargs(**override))
    assert (exc.value.code, exc.value.reason) == (code, reason)


def test_result_constructor_accepts_valid_success_warning_failure() -> None:
    assert TransformResult(**result_kwargs()).status is TransformStatus.SUCCESS
    warning = result_kwargs(status='warning', post_assessment=assessed(confidence=0.4), warnings=('w',))
    assert TransformResult(**warning).status is TransformStatus.WARNING
    failure = result_kwargs(status='failure', post_assessment=FAILED_POST, warnings=('w',), **NO_PROCESSED)
    assert TransformResult(**failure).status is TransformStatus.FAILURE


def test_transform_port_is_runtime_checkable_protocol() -> None:
    assert isinstance(FakeTransformPort(), TransformPort)
    assert not isinstance(object(), TransformPort)
    with pytest.raises(ImageSafetyError) as exc:
        run(object())
    assert (exc.value.code, exc.value.reason) == ('wrong_type', 'port')


def test_module_has_no_action_constant_no_io_cleanup_or_foreign_imports() -> None:
    path = ROOT / 'src' / 'voice' / 'domain' / 'image_transform.py'
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    allowed = {
        '__future__', 'collections.abc', 'copy', 'dataclasses', 'enum', 'math', 'types', 'typing',
        'voice.domain.image_safety', 'voice.domain.processing',
    }
    forbidden = re.compile(r'delete|remove|cleanup|clean_up|purge|unlink|rmtree|evict', re.I)
    action_words = re.compile(r'blur|gaussian|recolor|pixel|mosaic', re.I)
    names: set[str] = set()
    texts: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            texts.add(node.value)
        elif isinstance(node, ast.Import):
            assert {alias.name for alias in node.names} <= allowed, node.names
        elif isinstance(node, ast.ImportFrom):
            assert node.module in allowed, node.module
    assert not {'open', 'exec', 'eval', 'compile', '__import__'} & names
    for name in names:
        assert not forbidden.search(name), name
    for text in names | texts:
        assert not action_words.search(text.lower().replace('hook_already_blurred', '')), text