"""F-07: artifact verify, output path, bằng chứng ngôn ngữ và tool (CT-RND-003 số 5, 7, 8, 9).

coveredIds: TST-INT-INV-008 (phía F), TST-QC-INV-019 (phía F), TST-SEC-INV-020 (phía F), CT-RND-003 số 5, 7, 8, 9, CT-RND-006 (phía F)
"""
import ast
import copy
import dataclasses
import json
import pathlib
from types import SimpleNamespace

import pytest

from controlplane.domain.statemachine import ArtifactLocationState
from render.domain.package_contract import validate_render_package_payload
from render.domain.preconditions_artifacts import (
    ARTIFACT_HASH_MISMATCH, ARTIFACT_NOT_VERIFIED, ARTIFACT_SIZE_MISMATCH, INPUT_NOT_READY,
    LANGUAGE_EVIDENCE_MISSING, LANGUAGE_EVIDENCE_REVISION_MISMATCH, LANGUAGE_EVIDENCE_UNRESOLVED,
    LANGUAGE_MISMATCH, OUTPUT_PATH_NOT_ISSUED, OUTPUT_PATH_OUTSIDE_STAGING_ROOT,
    REQUIRED_ARTIFACT_NOT_IN_INPUTS, TOOL_CAPABILITY_INCOMPATIBLE, Finding, IssuedOutputPath,
    LanguageEvidencePolicy, LanguageEvidenceView, ToolCapability, VerifiedArtifact,
    check_artifacts_verified, check_language_evidence, check_output_path, check_preset_tool_compat,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / 'tests' / 'fixtures' / 'contracts' / 'f-render-package' / 'payloads.json'
MODULE_PATH = ROOT / 'src' / 'render' / 'domain' / 'preconditions_artifacts.py'
VOICE_ID = '00000000-0000-4000-8000-000000000034'
TIMING_ID = '00000000-0000-4000-8000-000000000036'
IMAGE_ID = '00000000-0000-4000-8000-000000000053'
VOICE_SHA, TIMING_SHA, IMAGE_SHA = 'a' * 64, 'b' * 64, 'c' * 64
SCRIPT_FP, VOICE_HASH, SUBTITLE_HASH = 'd' * 64, 'e' * 64, 'f' * 64
VERIFIED = ArtifactLocationState.VERIFIED


def _artifact(version_id, sha, size, media):
    return {'artifact_version_id': version_id, 'sha256': sha, 'size_bytes': size, 'media_type': media}


def _payload(**changes):
    fixture = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))
    payload = copy.deepcopy(fixture['entities']['RenderPackage']['valid'][0])
    payload['input_artifacts'] = [
        _artifact(VOICE_ID, VOICE_SHA, 100, 'audio/wav'),
        _artifact(TIMING_ID, TIMING_SHA, 50, 'application/json'),
        _artifact(IMAGE_ID, IMAGE_SHA, 2048, 'image/png'),
    ]
    payload.update(changes)
    return payload


def _record(**changes):
    return validate_render_package_payload(_payload(**changes))


def _verified(overrides=None):
    entries = {
        VOICE_ID: VerifiedArtifact(VOICE_SHA, 100, VERIFIED),
        TIMING_ID: VerifiedArtifact(TIMING_SHA, 50, VERIFIED),
        IMAGE_ID: VerifiedArtifact(IMAGE_SHA, 2048, VERIFIED),
    }
    entries.update(overrides or {})
    return entries


def test_all_verified_has_no_finding():
    assert check_artifacts_verified(_record(), _verified()) == []


@pytest.mark.parametrize('state', [s for s in ArtifactLocationState if s != VERIFIED])
def test_state_other_than_verified_is_not_verified(state):
    findings = check_artifacts_verified(_record(), _verified({VOICE_ID: VerifiedArtifact(VOICE_SHA, 100, state)}))
    assert findings == [Finding(7, ARTIFACT_NOT_VERIFIED, 'input_artifacts[0]')]


def test_missing_entries_report_each_artifact_in_order():
    assert check_artifacts_verified(_record(), {}) == [Finding(7, ARTIFACT_NOT_VERIFIED, f'input_artifacts[{i}]') for i in range(3)]


def test_non_verified_state_skips_hash_and_size_comparison():
    stale = VerifiedArtifact('0' * 64, 1, ArtifactLocationState.AVAILABLE_UNVERIFIED)
    assert check_artifacts_verified(_record(), _verified({IMAGE_ID: stale})) == [Finding(7, ARTIFACT_NOT_VERIFIED, 'input_artifacts[2]')]


def test_hash_mismatch():
    entry = VerifiedArtifact('0' * 64, 2048, VERIFIED)
    assert check_artifacts_verified(_record(), _verified({IMAGE_ID: entry})) == [Finding(7, ARTIFACT_HASH_MISMATCH, 'input_artifacts[2].sha256')]


def test_size_mismatch():
    entry = VerifiedArtifact(IMAGE_SHA, 1, VERIFIED)
    assert check_artifacts_verified(_record(), _verified({IMAGE_ID: entry})) == [Finding(7, ARTIFACT_SIZE_MISMATCH, 'input_artifacts[2].size_bytes')]


def test_hash_and_size_mismatch_report_both_in_order():
    entry = VerifiedArtifact('0' * 64, 1, VERIFIED)
    assert check_artifacts_verified(_record(), _verified({IMAGE_ID: entry})) == [
        Finding(7, ARTIFACT_HASH_MISMATCH, 'input_artifacts[2].sha256'),
        Finding(7, ARTIFACT_SIZE_MISMATCH, 'input_artifacts[2].size_bytes'),
    ]


def test_entry_that_is_not_a_verified_artifact_is_not_verified():
    entry = (VOICE_SHA, 100, VERIFIED)
    assert check_artifacts_verified(_record(), _verified({VOICE_ID: entry})) == [Finding(7, ARTIFACT_NOT_VERIFIED, 'input_artifacts[0]')]


def test_verified_none_is_input_not_ready():
    assert check_artifacts_verified(_record(), None) == [Finding(7, INPUT_NOT_READY, 'verified')]


def test_voice_and_timing_must_be_among_inputs():
    record = _record(input_artifacts=[_artifact(IMAGE_ID, IMAGE_SHA, 2048, 'image/png')])
    assert check_artifacts_verified(record, _verified()) == [
        Finding(7, REQUIRED_ARTIFACT_NOT_IN_INPUTS, 'voice_artifact_ref'),
        Finding(7, REQUIRED_ARTIFACT_NOT_IN_INPUTS, 'word_timing_ref'),
    ]


def test_only_missing_word_timing_is_reported_alone():
    record = _record(input_artifacts=[_artifact(VOICE_ID, VOICE_SHA, 100, 'audio/wav')])
    assert check_artifacts_verified(record, _verified()) == [Finding(7, REQUIRED_ARTIFACT_NOT_IN_INPUTS, 'word_timing_ref')]


ROOT_DIR = r'D:\staging'
OUTSIDE = [Finding(8, OUTPUT_PATH_OUTSIDE_STAGING_ROOT, 'output_path_ref')]


def _path_findings(path, root=ROOT_DIR):
    record = _record()
    return check_output_path(record, {record.output_path_ref: IssuedOutputPath(staging_root=root, path=path)})


@pytest.mark.parametrize('path', [r'out\final.mp4', r'D:\staging\out\final.mp4', r'd:\STAGING\out\final.mp4', 'D:/staging/out/final.mp4', 'final.mp4'])
def test_output_path_inside_staging_root_passes(path):
    assert _path_findings(path) == []


@pytest.mark.parametrize('path', [
    r'..\x', r'out\..\..\x', r'D:\staging\..\x.mp4', r'E:\staging\x.mp4', r'\\server\share\x.mp4',
    r'\\?\D:\staging\x.mp4', r'D:\other\x.mp4', r'D:\staging2\x.mp4', r'D:\staging', r'\x', 'D:x.mp4',
    r'out\CON.mp4', r'out\nul', r'out\com1.txt', r'out\LPT9', r'out\a<b.mp4', r'out\a.mp4:stream',
    'out' + chr(0) + 'a.mp4', 'out' + chr(10) + 'a.mp4', 'out' + chr(31) + 'a.mp4',
    'https://host/x.mp4', 'file://x/y.mp4', '',
])
def test_output_path_outside_staging_root_is_rejected(path):
    assert _path_findings(path) == OUTSIDE


@pytest.mark.parametrize('root', ['staging', r'\\srv\share\staging', r'D:\staging\..', '', 'https://host/staging'])
def test_invalid_staging_root_is_rejected(root):
    assert _path_findings(r'out\final.mp4', root=root) == OUTSIDE


def test_unissued_ref_is_not_issued():
    record = _record()
    other = {'00000000-0000-4000-8000-0000000000ff': IssuedOutputPath(ROOT_DIR, r'out\a.mp4')}
    assert check_output_path(record, other) == [Finding(8, OUTPUT_PATH_NOT_ISSUED, 'output_path_ref')]
    assert check_output_path(record, {}) == [Finding(8, OUTPUT_PATH_NOT_ISSUED, 'output_path_ref')]


def test_entry_that_is_not_issued_output_path_is_not_issued():
    record = _record()
    assert check_output_path(record, {record.output_path_ref: r'D:\staging\out\a.mp4'}) == [Finding(8, OUTPUT_PATH_NOT_ISSUED, 'output_path_ref')]


def test_issued_paths_none_is_input_not_ready():
    assert check_output_path(_record(), None) == [Finding(8, INPUT_NOT_READY, 'issued_paths')]


REF = 'lang-val-0001'
POLICY_FIELDS = ('required_language', 'script_fingerprint', 'voice_hash', 'subtitle_text_hash')


def _policy(**changes):
    values = {'required_language': 'en', 'script_fingerprint': SCRIPT_FP, 'voice_hash': VOICE_HASH, 'subtitle_text_hash': SUBTITLE_HASH}
    return LanguageEvidencePolicy(**{**values, **changes})


def _evidence(**changes):
    values = {
        'evidence_ref': REF, 'script_fingerprint': SCRIPT_FP, 'voice_hash': VOICE_HASH, 'subtitle_text_hash': SUBTITLE_HASH,
        'output_metadata_revision': 'out-meta-v1', 'voice_locale_reported': 'en-US',
    }
    return LanguageEvidenceView(**{**values, **changes})


def _language(evidence=None, policy=None, record=None):
    evidence = _evidence() if evidence is None else evidence
    return check_language_evidence(record or _record(), {REF: evidence}, policy or _policy())


def test_matching_evidence_passes():
    assert _language() == []


def test_empty_refs_is_evidence_missing():
    assert check_language_evidence(_record(language_validation_refs=[]), {}, _policy()) == [Finding(5, LANGUAGE_EVIDENCE_MISSING, 'language_validation_refs')]


def test_self_declared_language_is_not_evidence():
    record = _record(language_validation_refs=[], language='en')
    assert check_language_evidence(record, {}, _policy()) == [Finding(5, LANGUAGE_EVIDENCE_MISSING, 'language_validation_refs')]
    assert check_language_evidence(_record(language='en'), {REF: {'language': 'en'}}, _policy()) == [Finding(5, LANGUAGE_EVIDENCE_UNRESOLVED, 'language_validation_refs[0]')]


def test_unknown_ref_is_unresolved():
    assert check_language_evidence(_record(), {}, _policy()) == [Finding(5, LANGUAGE_EVIDENCE_UNRESOLVED, 'language_validation_refs[0]')]


def test_evidence_ref_must_equal_its_key():
    assert _language(_evidence(evidence_ref='other')) == [Finding(5, LANGUAGE_EVIDENCE_UNRESOLVED, 'language_validation_refs[0]')]


@pytest.mark.parametrize('name', ['script_fingerprint', 'voice_hash', 'subtitle_text_hash', 'output_metadata_revision'])
def test_stale_revision_is_mismatch(name):
    assert _language(_evidence(**{name: 'stale'})) == [Finding(5, LANGUAGE_EVIDENCE_REVISION_MISMATCH, f'language_validation_refs[0].{name}')]


def test_evidence_of_old_voice_is_rejected_after_voice_changes():
    assert _language(policy=_policy(voice_hash='9' * 64)) == [Finding(5, LANGUAGE_EVIDENCE_REVISION_MISMATCH, 'language_validation_refs[0].voice_hash')]


def test_mismatches_are_reported_in_fixed_order():
    evidence = _evidence(output_metadata_revision='old', script_fingerprint='old', voice_locale_reported='de-DE')
    assert [f.field for f in _language(evidence)] == [
        'language_validation_refs[0].script_fingerprint', 'language_validation_refs[0].output_metadata_revision', 'language_validation_refs[0].voice_locale_reported',
    ]


@pytest.mark.parametrize('locale', ['de-DE', 'english', 'fr', ''])
def test_other_locale_is_language_mismatch(locale):
    assert _language(_evidence(voice_locale_reported=locale)) == [Finding(5, LANGUAGE_MISMATCH, 'language_validation_refs[0].voice_locale_reported')]


@pytest.mark.parametrize('locale', ['en', 'en-US', 'EN_us', ' en-GB '])
def test_bare_required_language_matches_primary_subtag(locale):
    assert _language(_evidence(voice_locale_reported=locale)) == []


def test_regional_required_language_needs_same_region():
    policy = _policy(required_language='en-US')
    assert _language(_evidence(voice_locale_reported='en_US'), policy) == []
    assert len(_language(_evidence(voice_locale_reported='en-GB'), policy)) == 1
    assert len(_language(_evidence(voice_locale_reported='en'), policy)) == 1


def test_policy_none_is_input_not_ready_even_when_refs_empty():
    assert check_language_evidence(_record(language_validation_refs=[]), {}, None) == [Finding(5, INPUT_NOT_READY, 'policy')]
    assert check_language_evidence(_record(), {REF: _evidence()}, None) == [Finding(5, INPUT_NOT_READY, 'policy')]


def test_evidence_by_ref_none_is_input_not_ready():
    assert check_language_evidence(_record(), None, _policy()) == [Finding(5, INPUT_NOT_READY, 'evidence_by_ref')]


@pytest.mark.parametrize('name', POLICY_FIELDS)
def test_blank_policy_field_is_input_not_ready(name):
    assert _language(policy=_policy(**{name: ' '})) == [Finding(5, INPUT_NOT_READY, f'policy.{name}')]


def test_each_ref_is_checked_and_flagged_by_index():
    record = _record(language_validation_refs=[REF, 'lang-val-0002'])
    assert check_language_evidence(record, {REF: _evidence()}, _policy()) == [Finding(5, LANGUAGE_EVIDENCE_UNRESOLVED, 'language_validation_refs[1]')]


CAPABILITY = ToolCapability(filters=('scale', 'subtitles'), encoders=('libx264', 'aac'))
FILTERS_FIELD = 'compatibility_requirements.required_filters'
ENCODERS_FIELD = 'compatibility_requirements.required_encoders'


def _preset(**requirements):
    return SimpleNamespace(compatibility_requirements=requirements)


def test_capability_is_frozen_and_normalized():
    assert CAPABILITY.filters == frozenset({'scale', 'subtitles'}) and isinstance(CAPABILITY.encoders, frozenset)
    with pytest.raises(dataclasses.FrozenInstanceError):
        CAPABILITY.filters = frozenset()
    with pytest.raises(TypeError):
        ToolCapability(filters='scale')


def test_compatible_preset_passes():
    assert check_preset_tool_compat(_preset(required_filters=['scale'], required_encoders=('libx264',)), CAPABILITY) == []


def test_missing_filter_and_encoder_are_reported_in_order():
    preset = _preset(required_filters=['scale', 'zoompan'], required_encoders=['h264_nvenc'])
    assert check_preset_tool_compat(preset, CAPABILITY) == [Finding(9, TOOL_CAPABILITY_INCOMPATIBLE, FILTERS_FIELD), Finding(9, TOOL_CAPABILITY_INCOMPATIBLE, ENCODERS_FIELD)]
    assert check_preset_tool_compat(_preset(required_encoders=['h264_nvenc']), CAPABILITY) == [Finding(9, TOOL_CAPABILITY_INCOMPATIBLE, ENCODERS_FIELD)]


def test_absent_requirement_keys_need_nothing():
    assert check_preset_tool_compat(_preset(note='x'), CAPABILITY) == []


@pytest.mark.parametrize('capability', [None, {'filters': ['scale']}])
def test_capability_none_or_wrong_type_is_input_not_ready(capability):
    assert check_preset_tool_compat(_preset(required_filters=['scale']), capability) == [Finding(9, INPUT_NOT_READY, 'capability')]


@pytest.mark.parametrize('preset', [None, SimpleNamespace()])
def test_preset_without_requirements_is_input_not_ready(preset):
    assert check_preset_tool_compat(preset, CAPABILITY) == [Finding(9, INPUT_NOT_READY, 'preset.compatibility_requirements')]


def test_malformed_requirement_is_input_not_ready():
    assert check_preset_tool_compat(_preset(required_filters='scale'), CAPABILITY) == [Finding(9, INPUT_NOT_READY, FILTERS_FIELD)]
    assert check_preset_tool_compat(_preset(required_encoders=[1]), CAPABILITY) == [Finding(9, INPUT_NOT_READY, ENCODERS_FIELD)]


def test_real_preset_revision_is_supported():
    from render.domain.preset import build_preset_revision
    section = {'k': 'v'}
    preset = build_preset_revision({
        'preset_key': 'p1', 'revision': 1, 'visual_rhythm': section, 'layout_rules': section, 'thumbnail_overlay_style': section,
        'typography_karaoke_style': section, 'hook_treatment': section, 'mix_rules': section, 'color_effect_rules': section,
        'output_profile_ref': 'out-prof-v1', 'fallback_constraints': section,
        'compatibility_requirements': {'required_filters': ['scale'], 'required_encoders': ['libx264']},
    })
    assert check_preset_tool_compat(preset, CAPABILITY) == []
    assert len(check_preset_tool_compat(preset, ToolCapability(filters=('scale',)))) == 1


def test_finding_is_frozen_with_three_fields():
    assert [f.name for f in dataclasses.fields(Finding)] == ['condition', 'code', 'field']
    with pytest.raises(dataclasses.FrozenInstanceError):
        Finding(7, 'x', 'y').code = 'z'


def test_codes_are_stable_literals():
    assert (INPUT_NOT_READY, ARTIFACT_NOT_VERIFIED, OUTPUT_PATH_OUTSIDE_STAGING_ROOT, LANGUAGE_MISMATCH) == (
        'INPUT_NOT_READY', 'artifact_not_verified', 'output_path_outside_staging_root', 'language_mismatch')


def test_module_imports_only_allowed_modules():
    found = set()
    for node in ast.walk(ast.parse(MODULE_PATH.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.add(node.module)
    assert found == {'__future__', 'collections.abc', 'dataclasses', 'pathlib', 'controlplane.domain.statemachine', 'render.domain.package_contract'}


def test_module_declares_covered_ids():
    doc = ast.get_docstring(ast.parse(MODULE_PATH.read_text(encoding='utf-8'))) or ''
    for covered in ('TST-INT-INV-008', 'TST-QC-INV-019', 'TST-SEC-INV-020', 'CT-RND-006'):
        assert covered in doc
