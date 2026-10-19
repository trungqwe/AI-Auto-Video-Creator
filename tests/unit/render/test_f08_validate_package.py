"""F-08: ValidateRenderPackage tổng hợp, fail sớm theo CT-RND-003.

coveredIds: CT-RND-003, TST-INT-INV-008 (phía F)
"""
import ast
import copy
import dataclasses
import json
import pathlib
from types import SimpleNamespace

import pytest

from controlplane.application.idempotency.canonicalization import request_hash
from controlplane.domain.statemachine import ArtifactLocationState
from render.domain.package_contract import validate_render_package_payload
from render.domain.preconditions_artifacts import (
    INPUT_NOT_READY, IssuedOutputPath, LanguageEvidencePolicy, LanguageEvidenceView, ToolCapability, VerifiedArtifact,
)
from render.domain.preconditions_media import VoiceTrackInfo, WordTimingInfo
from render.domain.validate_package import (
    Finding, PackageNotRenderable, PackageValidationReport, ValidationContext, require_valid_package, validate_render_package,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / 'tests' / 'fixtures' / 'contracts' / 'f-render-package' / 'payloads.json'
MODULE_PATH = ROOT / 'src' / 'render' / 'domain' / 'validate_package.py'
VOICE_ID = '00000000-0000-4000-8000-000000000034'
TIMING_ID = '00000000-0000-4000-8000-000000000036'
IMAGE_ID = '00000000-0000-4000-8000-000000000053'
OUTPUT_REF = '00000000-0000-4000-8000-000000000057'
EVIDENCE_REF = 'lang-val-0001'
VOICE_SHA, TIMING_SHA, IMAGE_SHA = 'a' * 64, 'b' * 64, 'c' * 64
SCRIPT_FP, VOICE_HASH, SUBTITLE_HASH = 'd' * 64, 'e' * 64, 'f' * 64
STAGING_ROOT = 'D:/render-staging'
OUTPUT_PATH = 'D:/render-staging/out/video.mp4'
VERIFIED = ArtifactLocationState.VERIFIED


def _fixture_payload():
    raw = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))
    return copy.deepcopy(raw['entities']['RenderPackage']['valid'][0])


def _artifact(version_id, sha, size, media):
    return {'artifact_version_id': version_id, 'sha256': sha, 'size_bytes': size, 'media_type': media}


def _record(placement_drop=(), **changes):
    payload = _fixture_payload()
    payload['input_artifacts'] = [
        _artifact(VOICE_ID, VOICE_SHA, 100, 'audio/wav'),
        _artifact(TIMING_ID, TIMING_SHA, 50, 'application/json'),
        _artifact(IMAGE_ID, IMAGE_SHA, 2048, 'image/png'),
    ]
    for key in placement_drop:
        payload['hook_placement'].pop(key)
    payload.update(changes)
    return validate_render_package_payload(payload)


def _voice():
    return VoiceTrackInfo(voice_artifact_ref=VOICE_ID, script_version_id=_fixture_payload()['script_version_ref'], script_fingerprint=SCRIPT_FP, voice_hash=VOICE_HASH)


def _timing(**changes):
    base = WordTimingInfo(timing_artifact_ref=TIMING_ID, script_version_id=_fixture_payload()['script_version_ref'], script_fingerprint=SCRIPT_FP, voice_hash=VOICE_HASH)
    return dataclasses.replace(base, **changes)


def _evidence(**changes):
    base = LanguageEvidenceView(evidence_ref=EVIDENCE_REF, script_fingerprint=SCRIPT_FP, voice_hash=VOICE_HASH, subtitle_text_hash=SUBTITLE_HASH, output_metadata_revision='out-meta-v1', voice_locale_reported='en-US')
    return dataclasses.replace(base, **changes)


def _verified(overrides=None):
    entries = {VOICE_ID: VerifiedArtifact(VOICE_SHA, 100, VERIFIED), TIMING_ID: VerifiedArtifact(TIMING_SHA, 50, VERIFIED), IMAGE_ID: VerifiedArtifact(IMAGE_SHA, 2048, VERIFIED)}
    entries.update(overrides or {})
    return entries


def _context(**changes):
    values = {
        'voice': _voice(), 'word_timing': _timing(), 'verified': _verified(),
        'issued_paths': {OUTPUT_REF: IssuedOutputPath(STAGING_ROOT, OUTPUT_PATH)},
        'language_evidence': {EVIDENCE_REF: _evidence()},
        'language_policy': LanguageEvidencePolicy(required_language='en', script_fingerprint=SCRIPT_FP, voice_hash=VOICE_HASH, subtitle_text_hash=SUBTITLE_HASH),
        'preset': SimpleNamespace(compatibility_requirements={'required_filters': ['subtitles'], 'required_encoders': ['libx264']}),
        'capability': ToolCapability(filters=frozenset({'subtitles', 'scale'}), encoders=frozenset({'libx264'})),
    }
    values.update(changes)
    return ValidationContext(**values)


def _breakers():
    return {
        1: {'drop': ['visual_hook_ref'], 'expected': [Finding(1, 'visual_hook_missing', 'hook_placement.visual_hook_ref')]},
        2: {'drop': ['audio_hook_ref'], 'expected': [Finding(2, 'audio_hook_missing', 'hook_placement.audio_hook_ref')]},
        3: {'drop': ['thumbnail_ref'], 'expected': [Finding(3, 'thumbnail_missing', 'hook_placement.thumbnail_ref')]},
        4: {'context': {'word_timing': _timing(voice_hash='0' * 64)}, 'expected': [Finding(4, 'voice_timing_binding_mismatch', 'voice_hash')]},
        5: {'context': {'language_evidence': {EVIDENCE_REF: _evidence(voice_locale_reported='fr-FR')}}, 'expected': [Finding(5, 'language_mismatch', 'language_validation_refs[0].voice_locale_reported')]},
        6: {'record': {'timeline': {'segments': [{'start_ms': 0, 'end_ms': 1000, 'visual_asset_refs': []}]}}, 'expected': [Finding(6, 'timeline_segment_without_visual', 'timeline.segments[0].visual_asset_refs')]},
        7: {'context': {'verified': _verified({IMAGE_ID: VerifiedArtifact(IMAGE_SHA, 2048, ArtifactLocationState.AVAILABLE_UNVERIFIED)})}, 'expected': [Finding(7, 'artifact_not_verified', 'input_artifacts[2]')]},
        8: {'context': {'issued_paths': {OUTPUT_REF: IssuedOutputPath(STAGING_ROOT, 'D:/other/video.mp4')}}, 'expected': [Finding(8, 'output_path_outside_staging_root', 'output_path_ref')]},
        9: {'context': {'capability': ToolCapability(filters=frozenset({'scale'}), encoders=frozenset({'libx264'}))}, 'expected': [Finding(9, 'tool_capability_incompatible', 'compatibility_requirements.required_filters')]},
    }


def _broken(conditions):
    drop, record_changes, context_changes, expected = [], {}, {}, []
    for condition in sorted(conditions):
        spec = _breakers()[condition]
        drop += spec.get('drop', [])
        record_changes.update(spec.get('record', {}))
        context_changes.update(spec.get('context', {}))
        expected += spec['expected']
    return _record(placement_drop=drop, **record_changes), _context(**context_changes), expected


def test_valid_package_passes_with_report_id_from_request_hash():
    record = _record()
    report = validate_render_package(record, _context())
    assert isinstance(report, PackageValidationReport)
    assert report.findings == () and report.passed is True
    assert report.package_fingerprint == record.package_fingerprint
    assert report.report_id == request_hash({'package_fingerprint': record.package_fingerprint, 'findings': []})


@pytest.mark.parametrize('condition', range(1, 10))
def test_single_missing_condition_gives_exactly_one_finding(condition):
    record, context, expected = _broken([condition])
    report = validate_render_package(record, context)
    assert list(report.findings) == expected and len(expected) == 1
    assert report.passed is False


@pytest.mark.parametrize('conditions', [(1, 2), (1, 2, 3), (2, 6, 9), (4, 5, 7, 8), tuple(range(1, 10))])
def test_several_missing_conditions_give_several_findings(conditions):
    record, context, expected = _broken(conditions)
    report = validate_render_package(record, context)
    assert list(report.findings) == expected and len(report.findings) == len(conditions)
    assert report.passed is False


def test_findings_are_ordered_by_condition_then_code_then_field():
    record, context, _ = _broken(range(1, 10))
    findings = validate_render_package(record, context).findings
    assert [item.condition for item in findings] == list(range(1, 10))
    mismatch = VerifiedArtifact('0' * 64, 1, VERIFIED)
    report = validate_render_package(_record(), _context(verified=_verified({IMAGE_ID: mismatch})))
    assert list(report.findings) == [Finding(7, 'artifact_hash_mismatch', 'input_artifacts[2].sha256'), Finding(7, 'artifact_size_mismatch', 'input_artifacts[2].size_bytes')]


def test_sort_overrides_the_natural_order_of_the_f06_check():
    other_version = dataclasses.replace(_voice(), script_version_id='other-script-version')
    report = validate_render_package(_record(), _context(voice=other_version, word_timing=None))
    assert list(report.findings) == [Finding(4, 'voice_timing_binding_mismatch', 'script_version_id'), Finding(4, 'word_timing_missing', 'word_timing_ref')]


def test_report_is_deterministic_and_report_id_tracks_findings():
    record, context, _ = _broken([1, 7])
    first, second = validate_render_package(record, context), validate_render_package(record, context)
    assert first == second and first.report_id == second.report_id
    assert first.report_id != validate_render_package(_record(), _context()).report_id
    assert first.report_id != validate_render_package(*_broken([1])[:2]).report_id


def test_findings_are_the_f08_finding_type():
    record, context, _ = _broken([1, 7])
    assert all(type(item) is Finding for item in validate_render_package(record, context).findings)


def test_missing_context_is_input_not_ready_and_never_passes():
    report = validate_render_package(_record(), None)
    assert list(report.findings) == [
        Finding(4, 'voice_missing', 'voice_artifact_ref'),
        Finding(4, 'word_timing_missing', 'word_timing_ref'),
        Finding(5, INPUT_NOT_READY, 'policy'),
        Finding(7, INPUT_NOT_READY, 'verified'),
        Finding(8, INPUT_NOT_READY, 'issued_paths'),
        Finding(9, INPUT_NOT_READY, 'capability'),
    ]
    assert report.passed is False


@pytest.mark.parametrize('bad_context', [{}, [], 'context', object()])
def test_context_of_wrong_type_equals_missing_context(bad_context):
    assert validate_render_package(_record(), bad_context) == validate_render_package(_record(), None)


@pytest.mark.parametrize('name, expected', [
    ('language_policy', Finding(5, INPUT_NOT_READY, 'policy')),
    ('language_evidence', Finding(5, INPUT_NOT_READY, 'evidence_by_ref')),
    ('verified', Finding(7, INPUT_NOT_READY, 'verified')),
    ('issued_paths', Finding(8, INPUT_NOT_READY, 'issued_paths')),
    ('capability', Finding(9, INPUT_NOT_READY, 'capability')),
    ('preset', Finding(9, INPUT_NOT_READY, 'preset.compatibility_requirements')),
])
def test_each_missing_context_part_gives_exactly_one_input_not_ready(name, expected):
    report = validate_render_package(_record(), _context(**{name: None}))
    assert list(report.findings) == [expected]
    assert report.passed is False


@pytest.mark.parametrize('name, value, expected', [
    ('verified', [], Finding(7, INPUT_NOT_READY, 'verified')),
    ('issued_paths', 'paths', Finding(8, INPUT_NOT_READY, 'issued_paths')),
    ('language_evidence', [], Finding(5, INPUT_NOT_READY, 'evidence_by_ref')),
    ('language_policy', 'en', Finding(5, INPUT_NOT_READY, 'policy')),
])
def test_context_part_of_wrong_type_is_input_not_ready(name, value, expected):
    assert list(validate_render_package(_record(), _context(**{name: value})).findings) == [expected]


def test_missing_voice_or_word_timing_is_reported_not_ignored():
    assert list(validate_render_package(_record(), _context(voice=None)).findings) == [Finding(4, 'voice_missing', 'voice_artifact_ref')]
    assert list(validate_render_package(_record(), _context(word_timing=None)).findings) == [Finding(4, 'word_timing_missing', 'word_timing_ref')]


def test_non_record_input_is_rejected():
    with pytest.raises(TypeError):
        validate_render_package({'package_fingerprint': 'x'}, _context())


def test_report_is_frozen_with_tuple_findings():
    record, context, _ = _broken([1, 7])
    report = validate_render_package(record, context)
    assert isinstance(report.findings, tuple)
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.passed = True


def test_report_rejects_inconsistent_construction():
    record, context, _ = _broken([1, 7])
    report = validate_render_package(record, context)
    with pytest.raises(ValueError):
        dataclasses.replace(report, passed=True)
    with pytest.raises(ValueError):
        dataclasses.replace(report, report_id='0' * 64)
    with pytest.raises(ValueError):
        dataclasses.replace(report, findings=tuple(reversed(report.findings)))
    with pytest.raises(ValueError):
        dataclasses.replace(report, findings=(object(),))
    with pytest.raises(ValueError):
        dataclasses.replace(validate_render_package(_record(), _context()), passed=False)


def test_require_valid_package_accepts_passing_report():
    assert require_valid_package(validate_render_package(_record(), _context())) is None


def test_require_valid_package_raises_with_the_report():
    record, context, expected = _broken([2, 9])
    report = validate_render_package(record, context)
    with pytest.raises(PackageNotRenderable) as caught:
        require_valid_package(report)
    assert caught.value.report is report and list(caught.value.report.findings) == expected


def test_require_valid_package_rejects_non_report():
    with pytest.raises(TypeError):
        require_valid_package(None)


class FakeRenderer:
    def __init__(self):
        self.calls = 0

    def render(self, record):
        self.calls += 1
        return 'rendered'


def _render_when_valid(record, context, renderer):
    require_valid_package(validate_render_package(record, context))
    return renderer.render(record)


def test_renderer_is_called_once_for_valid_package():
    renderer = FakeRenderer()
    assert _render_when_valid(_record(), _context(), renderer) == 'rendered'
    assert renderer.calls == 1


@pytest.mark.parametrize('condition', range(1, 10))
def test_invalid_package_makes_zero_renderer_calls(condition):
    record, context, expected = _broken([condition])
    renderer = FakeRenderer()
    with pytest.raises(PackageNotRenderable) as caught:
        _render_when_valid(record, context, renderer)
    assert renderer.calls == 0 and list(caught.value.report.findings) == expected


def test_missing_hook_never_reaches_renderer_and_all_findings_are_reported():
    record, context, expected = _broken([1, 2, 3, 7])
    renderer = FakeRenderer()
    with pytest.raises(PackageNotRenderable) as caught:
        _render_when_valid(record, context, renderer)
    assert renderer.calls == 0 and list(caught.value.report.findings) == expected and len(expected) == 4


def test_missing_context_makes_zero_renderer_calls():
    renderer = FakeRenderer()
    with pytest.raises(PackageNotRenderable):
        _render_when_valid(_record(), None, renderer)
    assert renderer.calls == 0


ALLOWED_IMPORTS = frozenset({
    '__future__', 'collections.abc', 'dataclasses', 'controlplane.application.idempotency.canonicalization',
    'render.domain.package_contract', 'render.domain.preconditions_artifacts', 'render.domain.preconditions_media',
})


def test_module_imports_only_allowed_modules():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module)
    assert names <= ALLOWED_IMPORTS


def test_module_declares_covered_ids():
    doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
    assert any(line.startswith('coveredIds:') for line in (doc or '').splitlines())
