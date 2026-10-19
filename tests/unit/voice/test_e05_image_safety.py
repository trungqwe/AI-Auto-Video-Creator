"""E-05: image-only safety assessment (CT-PROC-005, CT-STATE-006).

coveredIds: CT-PROC-005, TST-E2E-011 (phía E, mức domain)
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
    original_usable_for,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
CONTRACT_DOC = ROOT / 'docs' / '09-contracts' / '07-media-processing-contracts.md'
# GIẢ ĐỊNH: giá trị policy chỉ dùng trong fixture; ngưỡng thật chờ ROADMAP-OPEN-006 (CP7-E-03).
POLICY = ImageSafetyPolicy('policy-test-1', 0.8, ('child', 'gore', 'weapon'), True)


def detected(*categories: str, confidence: float | None = 0.95) -> ImageDetection:
    return ImageDetection(DetectionStatus.COMPLETED, categories, confidence)


def raising_detector() -> ImageDetection:
    raise RuntimeError('canary-secret-token')


# Sensitive Image Set giả: (case_id, detection, outcome mong đợi, original_usable mong đợi).
SENSITIVE_IMAGE_SET = (
    ('safe', detected(), SafetyOutcome.SAFE, True),
    ('child', detected('child'), SafetyOutcome.TRANSFORM_REQUIRED, False),
    ('gore', detected('gore'), SafetyOutcome.TRANSFORM_REQUIRED, False),
    ('weapon', detected('weapon', 'unlisted_label'), SafetyOutcome.TRANSFORM_REQUIRED, False),
    ('uncertain_clean', detected(confidence=0.40), SafetyOutcome.UNCERTAIN, True),
    ('uncertain_sensitive', detected('child', confidence=0.40), SafetyOutcome.UNCERTAIN, True),
    ('uncertain_no_confidence', ImageDetection(DetectionStatus.COMPLETED), SafetyOutcome.UNCERTAIN, True),
    ('detector_failed', ImageDetection(DetectionStatus.FAILED), SafetyOutcome.DETECTION_FAILED, True),
    ('detector_raises', raising_detector, SafetyOutcome.DETECTION_FAILED, True),
    ('detector_bad_result', lambda: {'status': 'completed'}, SafetyOutcome.DETECTION_FAILED, True),
    ('detection_missing', None, SafetyOutcome.DETECTION_FAILED, True),
    ('unreadable', ImageDetection(DetectionStatus.UNREADABLE), SafetyOutcome.UNREADABLE, False),
)


@pytest.mark.parametrize(
    ('case_id', 'detection', 'outcome', 'usable'),
    SENSITIVE_IMAGE_SET,
    ids=[case[0] for case in SENSITIVE_IMAGE_SET],
)
def test_sensitive_image_set(case_id: str, detection: object, outcome: SafetyOutcome, usable: bool) -> None:
    result = assess_image_safety('image', detection, POLICY)
    assert isinstance(result, ImageSafetyAssessment)
    assert (result.outcome, result.original_usable) == (outcome, usable), case_id
    assert result.policy_revision == 'policy-test-1'
    if outcome in (SafetyOutcome.UNCERTAIN, SafetyOutcome.DETECTION_FAILED):
        assert result.reason in result.warnings
    if outcome is SafetyOutcome.TRANSFORM_REQUIRED:
        assert result.categories and set(result.categories) <= set(POLICY.transform_categories)
    else:
        assert result.categories == ()


def contract_rows() -> dict[str, str]:
    text = CONTRACT_DOC.read_text(encoding='utf-8')
    section = text.split('### CT-PROC-005', 1)[1].split('### CT-PROC-006', 1)[0]
    return dict(re.findall(r'^\| `([A-Z_]+)` \|[^|]*\| ([^|]+?) \|\s*$', section, re.M))


def test_outcome_states_and_usable_table_match_contract_doc() -> None:
    rows = contract_rows()
    assert len(SafetyOutcome) == 6
    assert set(rows) == {m.value for m in SafetyOutcome}
    for state, cell in rows.items():
        outcome = SafetyOutcome(state)
        if outcome is SafetyOutcome.TRANSFORM_REQUIRED:
            assert cell.startswith('Chỉ sau transform')
            assert original_usable_for(outcome, True) is False
            assert original_usable_for(outcome, False) is True
        else:
            assert original_usable_for(outcome) is cell.startswith('Có'), state


def test_only_clean_result_is_safe_and_transform_failed_is_never_produced() -> None:
    produced: dict[SafetyOutcome, list[str]] = {}
    for case_id, detection, _outcome, _usable in SENSITIVE_IMAGE_SET:
        result = assess_image_safety('image', detection, POLICY)
        produced.setdefault(result.outcome, []).append(case_id)
    assert produced[SafetyOutcome.SAFE] == ['safe']
    assert set(produced) == set(SafetyOutcome) - {SafetyOutcome.TRANSFORM_FAILED}


def test_detector_exception_text_is_not_leaked() -> None:
    result = assess_image_safety('image', raising_detector, POLICY)
    assert result.reason == 'detector_raised'
    assert 'canary-secret-token' not in repr(result)


def test_confidence_boundary_follows_policy_threshold() -> None:
    assert assess_image_safety('image', detected(confidence=0.8), POLICY).outcome is SafetyOutcome.SAFE
    assert assess_image_safety('image', detected(confidence=0.79), POLICY).outcome is SafetyOutcome.UNCERTAIN
    strict = dataclasses.replace(POLICY, confidence_threshold=0.99)
    assert assess_image_safety('image', detected(confidence=0.95), strict).outcome is SafetyOutcome.UNCERTAIN


def test_transform_required_original_usable_follows_policy_flag() -> None:
    lenient = dataclasses.replace(POLICY, require_transform_before_use=False)
    result = assess_image_safety('image', detected('gore'), lenient)
    assert (result.outcome, result.original_usable) == (SafetyOutcome.TRANSFORM_REQUIRED, True)


class CountingDetector:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> ImageDetection:
        self.calls += 1
        return detected()


@pytest.mark.parametrize('kind', ['clip', 'audio', 'video', ''])
def test_non_image_is_not_applicable_and_detector_is_not_called(kind: str) -> None:
    detector = CountingDetector()
    for policy in (POLICY, None):
        result = assess_image_safety(kind, detector, policy)
        assert result == SafetyNotApplicable(media_kind=kind)
        assert not isinstance(result, ImageSafetyAssessment)
    assert detector.calls == 0


@pytest.mark.parametrize('kind', [None, 3, b'image'])
def test_media_kind_must_be_text(kind: object) -> None:
    with pytest.raises(ImageSafetyError) as exc:
        assess_image_safety(kind, detected(), POLICY)
    assert (exc.value.code, exc.value.reason) == ('wrong_type', 'media_kind')


def test_missing_policy_is_input_not_ready_and_detector_is_not_called() -> None:
    detector = CountingDetector()
    with pytest.raises(ImageSafetyError) as exc:
        assess_image_safety('image', detector, None)
    assert (exc.value.code, exc.value.reason) == ('INPUT_NOT_READY', 'missing_policy')
    assert detector.calls == 0


def test_policy_of_wrong_type_is_rejected() -> None:
    with pytest.raises(ImageSafetyError) as exc:
        assess_image_safety('image', detected(), {'revision': 'policy-test-1'})
    assert (exc.value.code, exc.value.reason) == ('wrong_type', 'policy')


def test_callable_detector_result_is_used_once() -> None:
    detector = CountingDetector()
    assert assess_image_safety('image', detector, POLICY).outcome is SafetyOutcome.SAFE
    assert detector.calls == 1


def test_assessment_constructor_enforces_table_and_warnings() -> None:
    ok = {'reason': 'r', 'warnings': ('r',)}
    bare = {'reason': 'r'}
    assert ImageSafetyAssessment(SafetyOutcome.UNCERTAIN, True, **ok).original_usable is True
    bad_cases = [
        (SafetyOutcome.UNREADABLE, True, ok, 'original_usable'),
        (SafetyOutcome.UNCERTAIN, False, ok, 'original_usable'),
        (SafetyOutcome.DETECTION_FAILED, True, bare, 'warnings'),
        (SafetyOutcome.UNCERTAIN, True, bare, 'warnings'),
        (SafetyOutcome.TRANSFORM_FAILED, True, bare, 'warnings'),
        (SafetyOutcome.SAFE, True, ok, 'safe_not_clean'),
        (SafetyOutcome.SAFE, False, bare, 'original_usable'),
        (SafetyOutcome.TRANSFORM_REQUIRED, False, bare, 'categories'),
    ]
    for outcome, usable, extra, field in bad_cases:
        with pytest.raises(ImageSafetyError) as exc:
            ImageSafetyAssessment(outcome, usable, **extra)
        assert (exc.value.code, exc.value.reason) == ('constraint_violation', field), (outcome, field)


def test_models_are_frozen_and_normalized_to_tuples() -> None:
    assessment = assess_image_safety('image', detected('weapon', 'child'), POLICY)
    assert assessment.categories == ('child', 'weapon')
    frozen_targets = (
        (assessment, 'outcome'),
        (POLICY, 'revision'),
        (detected(), 'status'),
        (SafetyNotApplicable('clip'), 'reason'),
    )
    for obj, field in frozen_targets:
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(obj, field, 'x')
    assert isinstance(assessment.warnings, tuple)
    assert isinstance(POLICY.transform_categories, tuple)


@pytest.mark.parametrize(
    'kwargs',
    [
        {'revision': ''},
        {'revision': None},
        {'confidence_threshold': 0},
        {'confidence_threshold': 1.5},
        {'confidence_threshold': True},
        {'confidence_threshold': float('nan')},
        {'confidence_threshold': '0.8'},
        {'transform_categories': ()},
        {'transform_categories': 'child'},
        {'transform_categories': (1,)},
        {'require_transform_before_use': 'yes'},
    ],
)
def test_policy_rejects_invalid_values(kwargs: dict) -> None:
    with pytest.raises(ImageSafetyError):
        dataclasses.replace(POLICY, **kwargs)


@pytest.mark.parametrize(
    'kwargs',
    [
        {'status': 'bogus'},
        {'status': 3},
        {'categories': 'child'},
        {'categories': (1,)},
        {'confidence': 1.5},
        {'confidence': True},
        {'confidence': -0.1},
        {'confidence': 'high'},
    ],
)
def test_detection_rejects_invalid_values(kwargs: dict) -> None:
    base = {'status': 'completed', 'categories': (), 'confidence': 0.9}
    with pytest.raises(ImageSafetyError):
        ImageDetection(**{**base, **kwargs})


def test_original_usable_for_rejects_bad_arguments() -> None:
    with pytest.raises(ImageSafetyError):
        original_usable_for('NOT_A_STATE')
    with pytest.raises(ImageSafetyError):
        original_usable_for(SafetyOutcome.TRANSFORM_REQUIRED, 'yes')


def test_module_has_no_io_cleanup_or_foreign_imports() -> None:
    path = ROOT / 'src' / 'voice' / 'domain' / 'image_safety.py'
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    allowed = {'__future__', 'dataclasses', 'enum', 'math', 'types'}
    forbidden = re.compile(r'delete|remove|cleanup|clean_up|purge|unlink|rmtree|evict', re.I)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Import):
            assert {alias.name for alias in node.names} <= allowed, node.names
        elif isinstance(node, ast.ImportFrom):
            assert node.module in allowed, node.module
    assert not {'open', 'exec', 'eval', 'compile', '__import__'} & names
    for name in names:
        assert not forbidden.search(name), name
