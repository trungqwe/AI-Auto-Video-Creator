"""E-08: VoiceTrack, ràng buộc script và kiểm thời lượng (CT-TTS-001).

coveredIds: CT-TTS-001
"""
import ast
import copy
import dataclasses
import hashlib
import json
import pathlib
import re

import pytest

from voice.domain.voice_track import (
    BINDING_VERSION,
    INPUT_NOT_READY,
    MISSING_REQUIRED,
    SCRIPT_FINGERPRINT_MISMATCH,
    SCRIPT_VERSION_MISMATCH,
    VOICE_DURATION_OUT_OF_RANGE,
    VOICE_TRACK_REQUEST_OPTIONAL,
    VOICE_TRACK_REQUEST_REQUIRED,
    VOICE_TRACK_RESULT_OPTIONAL,
    VOICE_TRACK_RESULT_REQUIRED,
    WRONG_TYPE,
    ScriptBindingError,
    VoiceTrack,
    VoiceTrackRejected,
    VoiceTrackValidationError,
    check_duration,
    compute_voice_hash,
    matches_type,
    validate_voice_track_request,
    validate_voice_track_result,
    verify_script_binding,
)
from voice.ports.script_text import ScriptText, ScriptTextPort

ROOT = pathlib.Path(__file__).resolve().parents[3]
BINDING_PATH = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'd-e-f-voice-timing.json'
FIXTURE_PATH = ROOT / 'tests' / 'fixtures' / 'contracts' / 'd-e-f-voice-timing' / 'payloads.json'
VOICE_TRACK_SOURCE = ROOT / 'src' / 'voice' / 'domain' / 'voice_track.py'
SCRIPT_TEXT_SOURCE = ROOT / 'src' / 'voice' / 'ports' / 'script_text.py'
SHA = '0123456789abcdef' * 4
OTHER_SHA = 'fedcba9876543210' * 4
VERSION_ID = '00000000-0000-4000-8000-000000000030'
# test-only policy fixture (GIẢ ĐỊNH, IMPL-PLAN-E §7): khoảng thời lượng là input policy, không là hằng trong src/
TEST_ONLY_DURATION_RANGE = (61000, 70000)
ENTITY_VALIDATORS = (
    ('VoiceTrackRequest', validate_voice_track_request),
    ('VoiceTrackResult', validate_voice_track_result),
)


def _binding_fields(entity: str) -> list[dict]:
    binding = json.loads(BINDING_PATH.read_text(encoding='utf-8'))
    return next(item for item in binding['entities'] if item['name'] == entity)['fields']


def _fixture(entity: str) -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))['entities'][entity]


def _valid(entity: str) -> dict:
    return copy.deepcopy(_fixture(entity)['valid'][0])


def _derive(fields: list[dict]) -> tuple[dict, dict]:
    return (
        {f['name']: f['type'] for f in fields if f['required']},
        {f['name']: f['type'] for f in fields if not f['required']},
    )


def _field(fields: list[dict], name: str) -> dict:
    return next(f for f in fields if f['name'] == name)


def _issues(validator, payload: object) -> list[tuple[str, str]]:
    return [(issue.code, issue.field) for issue in validator(payload)]


def test_binding_version_constant_matches_binding() -> None:
    assert BINDING_VERSION == json.loads(BINDING_PATH.read_text(encoding='utf-8'))['binding_version']


@pytest.mark.parametrize(
    ('entity', 'required', 'optional'),
    [
        ('VoiceTrackRequest', VOICE_TRACK_REQUEST_REQUIRED, VOICE_TRACK_REQUEST_OPTIONAL),
        ('VoiceTrackResult', VOICE_TRACK_RESULT_REQUIRED, VOICE_TRACK_RESULT_OPTIONAL),
    ],
)
def test_constants_match_binding(entity, required, optional) -> None:
    assert required, entity
    assert (dict(required), dict(optional)) == _derive(_binding_fields(entity))


def test_drift_comparison_detects_mutated_binding() -> None:
    expected = (dict(VOICE_TRACK_REQUEST_REQUIRED), dict(VOICE_TRACK_REQUEST_OPTIONAL))
    assert expected[0], 'VOICE_TRACK_REQUEST_REQUIRED must not be empty'
    mutations = {
        'fingerprint_optional': lambda fs: _field(fs, 'script_fingerprint').update(required=False),
        'fingerprint_as_string': lambda fs: _field(fs, 'script_fingerprint').update(type='string'),
        'hints_required': lambda fs: _field(fs, 'pronunciation_hints').update(required=True),
        'required_field_added': lambda fs: fs.append({'name': 'x_new', 'type': 'string', 'required': True}),
    }
    for name, mutate in mutations.items():
        fields = _binding_fields('VoiceTrackRequest')
        mutate(fields)
        assert _derive(fields) != expected, name


def test_fixture_valid_cases_pass() -> None:
    for entity, validator in ENTITY_VALIDATORS:
        cases = _fixture(entity)['valid']
        assert cases, entity
        for payload in cases:
            assert validator(payload) == [], entity


def test_fixture_invalid_cases_report_expected_error() -> None:
    ran = []
    for entity, validator in ENTITY_VALIDATORS:
        for case in _fixture(entity)['invalid']:
            error = case['expected_error']
            assert _issues(validator, case['payload']) == [(error['code'], error['field'])], case['case']
            ran.append(case['case'])
    assert sorted(ran) == ['duration_as_boolean', 'duration_as_text', 'missing_script_fingerprint']


def test_missing_script_fingerprint_is_missing_required() -> None:
    payload = _valid('VoiceTrackRequest')
    del payload['script_fingerprint']
    assert _issues(validate_voice_track_request, payload) == [(MISSING_REQUIRED, 'script_fingerprint')]


@pytest.mark.parametrize('value', ['65s', True, False, 65000.0, None, [65000]])
def test_duration_must_be_integer_not_text_or_bool(value) -> None:
    payload = _valid('VoiceTrackResult')
    payload['actual_duration_ms'] = value
    assert _issues(validate_voice_track_result, payload) == [(WRONG_TYPE, 'actual_duration_ms')]


@pytest.mark.parametrize('value', [SHA.upper(), SHA[:-1], SHA + '0', 'g' * 64, 123, ''])
def test_sha256_fields_require_lowercase_hex(value) -> None:
    request = _valid('VoiceTrackRequest')
    request['script_fingerprint'] = value
    assert _issues(validate_voice_track_request, request) == [(WRONG_TYPE, 'script_fingerprint')]
    result = _valid('VoiceTrackResult')
    result['voice_hash'] = value
    assert _issues(validate_voice_track_result, result) == [(WRONG_TYPE, 'voice_hash')]


def test_non_mapping_payload_is_wrong_type() -> None:
    for _entity, validator in ENTITY_VALIDATORS:
        for bad in (None, [], 'text', 7):
            assert _issues(validator, bad) == [(WRONG_TYPE, '$')]


def test_unknown_fields_are_ignored() -> None:
    for entity, validator in ENTITY_VALIDATORS:
        payload = _valid(entity)
        payload['x_additive_field'] = {'any': 1}
        assert validator(payload) == [], entity


def test_optional_hints_and_style_are_accepted_and_kept() -> None:
    payload = _valid('VoiceTrackRequest')
    payload['pronunciation_hints'] = [{'word': 'GIF', 'respelling': 'jif'}]
    payload['style_parameters'] = {'pace': 'fast', 'emotion': {'level': 2}}
    snapshot = copy.deepcopy(payload)
    assert validate_voice_track_request(payload) == []
    assert payload == snapshot
    payload['pronunciation_hints'] = 'GIF'
    assert _issues(validate_voice_track_request, payload) == [(WRONG_TYPE, 'pronunciation_hints')]
    payload['pronunciation_hints'] = []
    payload['style_parameters'] = 'fast'
    assert _issues(validate_voice_track_request, payload) == [(WRONG_TYPE, 'style_parameters')]


def test_compute_voice_hash_is_lowercase_sha256_hex() -> None:
    audio = b'RIFF fake wave bytes'
    digest = compute_voice_hash(audio)
    assert digest == hashlib.sha256(audio).hexdigest()
    assert re.fullmatch(r'[0-9a-f]{64}', digest)
    assert matches_type(digest, 'sha256')
    assert compute_voice_hash(bytearray(audio)) == digest
    assert compute_voice_hash(memoryview(audio)) == digest
    assert compute_voice_hash(b'') == hashlib.sha256(b'').hexdigest()
    assert compute_voice_hash(audio + b'x') != digest


@pytest.mark.parametrize('value', ['text', None, 12, [1, 2]])
def test_compute_voice_hash_rejects_non_bytes(value) -> None:
    with pytest.raises(TypeError):
        compute_voice_hash(value)


class FakeScriptTextPort:
    """Fake phía D (test-only): trả văn bản kèm fingerprint do test chọn, như D tính."""

    def __init__(self, texts: dict[str, ScriptText]) -> None:
        self.texts = texts
        self.calls: list[str] = []

    def get_text(self, script_version_id: str) -> ScriptText:
        self.calls.append(script_version_id)
        return self.texts[script_version_id]


def _script(fingerprint: str = SHA, version_id: str = VERSION_ID, text: str = 'Breaking news') -> ScriptText:
    return ScriptText(script_version_id=version_id, text=text, script_fingerprint=fingerprint)


def test_script_text_port_is_runtime_protocol() -> None:
    assert getattr(ScriptTextPort, '_is_protocol', False) is True
    port = FakeScriptTextPort({VERSION_ID: _script()})
    assert isinstance(port, ScriptTextPort)
    assert not isinstance(object(), ScriptTextPort)
    assert port.get_text(VERSION_ID) == _script()
    assert port.calls == [VERSION_ID]


def test_script_text_is_frozen() -> None:
    script = _script()
    with pytest.raises(dataclasses.FrozenInstanceError):
        script.script_fingerprint = OTHER_SHA


def test_verify_script_binding_accepts_matching_fingerprint() -> None:
    assert verify_script_binding(_valid('VoiceTrackRequest'), _script()) is None


def test_verify_script_binding_rejects_mismatched_fingerprint() -> None:
    request = _valid('VoiceTrackRequest')
    port = FakeScriptTextPort({VERSION_ID: _script(fingerprint=OTHER_SHA)})
    with pytest.raises(ScriptBindingError) as info:
        verify_script_binding(request, port.get_text(request['script_version_id']))
    assert info.value.code == SCRIPT_FINGERPRINT_MISMATCH
    assert SCRIPT_FINGERPRINT_MISMATCH == 'script_fingerprint_mismatch'


def test_verify_script_binding_rejects_other_script_version() -> None:
    with pytest.raises(ScriptBindingError) as info:
        verify_script_binding(_valid('VoiceTrackRequest'), _script(version_id='other-version'))
    assert info.value.code == SCRIPT_VERSION_MISMATCH


def test_verify_script_binding_rejects_invalid_request() -> None:
    request = _valid('VoiceTrackRequest')
    del request['script_fingerprint']
    with pytest.raises(VoiceTrackValidationError) as info:
        verify_script_binding(request, _script())
    assert [(i.code, i.field) for i in info.value.issues] == [(MISSING_REQUIRED, 'script_fingerprint')]


def test_verify_script_binding_trusts_fingerprint_from_d_and_never_recomputes() -> None:
    text = 'Breaking news'
    own = hashlib.sha256(text.encode('utf-8')).hexdigest()
    assert own not in (SHA, OTHER_SHA)
    request = _valid('VoiceTrackRequest')
    # D báo SHA (khác sha256 của text): bằng fingerprint của D là đủ, E không tự tính lại
    assert verify_script_binding(request, _script(fingerprint=SHA, text=text)) is None
    # request mang sha256(text) nhưng D báo fingerprint khác: vẫn phải bị từ chối
    request['script_fingerprint'] = own
    with pytest.raises(ScriptBindingError) as info:
        verify_script_binding(request, _script(fingerprint=SHA, text=text))
    assert info.value.code == SCRIPT_FINGERPRINT_MISMATCH


RESULT_NAMES = tuple(VOICE_TRACK_RESULT_REQUIRED)


def test_voice_track_is_frozen_with_result_fields_and_per_video_retention() -> None:
    expected = _valid('VoiceTrackResult')
    track = VoiceTrack.from_payload(expected)
    assert isinstance(track, VoiceTrack)
    assert [f.name for f in dataclasses.fields(VoiceTrack)] == [*RESULT_NAMES, 'retention_class']
    assert track.retention_class == 'per_video'
    for name in RESULT_NAMES:
        if name not in ('usage_metrics', 'warnings'):
            assert getattr(track, name) == expected[name], name
    assert dict(track.usage_metrics) == expected['usage_metrics']
    assert list(track.warnings) == expected['warnings']
    with pytest.raises(dataclasses.FrozenInstanceError):
        track.voice_hash = OTHER_SHA
    with pytest.raises(dataclasses.FrozenInstanceError):
        track.retention_class = 'reusable'


def test_voice_track_rejects_non_per_video_retention() -> None:
    payload = _valid('VoiceTrackResult')
    for value in ('reusable', 'diagnostic', '', None):
        with pytest.raises(ValueError):
            VoiceTrack(**payload, retention_class=value)


def test_voice_track_copies_mutable_inputs() -> None:
    payload = _valid('VoiceTrackResult')
    track = VoiceTrack.from_payload(payload)
    assert isinstance(track, VoiceTrack)
    payload['usage_metrics']['billed_characters'] = 1
    payload['warnings'].append('late')
    assert track.usage_metrics['billed_characters'] == 120
    assert track.warnings == ()
    assert isinstance(track.warnings, tuple)
    with pytest.raises(TypeError):
        track.usage_metrics['billed_characters'] = 2


def test_voice_track_from_payload_rejects_fixture_invalid_cases() -> None:
    cases = _fixture('VoiceTrackResult')['invalid']
    assert cases
    for case in cases:
        with pytest.raises(VoiceTrackValidationError) as info:
            VoiceTrack.from_payload(case['payload'])
        error = case['expected_error']
        assert [(i.code, i.field) for i in info.value.issues] == [(error['code'], error['field'])], case['case']


def test_voice_track_direct_construction_is_validated() -> None:
    payload = _valid('VoiceTrackResult')
    payload['actual_duration_ms'] = True
    with pytest.raises(VoiceTrackValidationError):
        VoiceTrack(**payload)


def test_voice_track_to_payload_round_trips() -> None:
    original = _valid('VoiceTrackResult')
    track = VoiceTrack.from_payload(original)
    assert isinstance(track, VoiceTrack)
    payload = track.to_payload()
    assert payload == original
    assert 'retention_class' not in payload
    assert validate_voice_track_result(payload) == []
    payload['usage_metrics']['billed_characters'] = 1
    assert track.usage_metrics['billed_characters'] == 120


def test_voice_track_ignores_unknown_fields_in_payload() -> None:
    payload = _valid('VoiceTrackResult')
    payload['x_additive_field'] = 1
    track = VoiceTrack.from_payload(payload)
    assert isinstance(track, VoiceTrack)
    assert 'x_additive_field' not in track.to_payload()


def test_check_duration_without_policy_is_input_not_ready() -> None:
    for policy in (None, (None, 70000), (61000, None), (None, None), [None, None]):
        with pytest.raises(VoiceTrackRejected) as info:
            check_duration(65000, policy)
        assert info.value.code == INPUT_NOT_READY, policy


def test_check_duration_inside_range_has_no_finding() -> None:
    for value in (61000, 65000, 70000):
        assert check_duration(value, TEST_ONLY_DURATION_RANGE) is None, value


def test_check_duration_outside_range_reports_finding() -> None:
    for value in (0, 60999, 70001, 120000):
        finding = check_duration(value, TEST_ONLY_DURATION_RANGE)
        assert finding is not None, value
        assert finding.code == VOICE_DURATION_OUT_OF_RANGE
        assert (finding.actual_duration_ms, finding.min_duration_ms, finding.max_duration_ms) == (value, 61000, 70000)
    assert VOICE_DURATION_OUT_OF_RANGE == 'voice_duration_out_of_range'


def test_check_duration_range_comes_only_from_policy() -> None:
    assert check_duration(65000, (1000, 2000)).code == VOICE_DURATION_OUT_OF_RANGE
    assert check_duration(1500, (1000, 2000)) is None
    assert check_duration(65000, [60000, 66000]) is None


@pytest.mark.parametrize('value', [True, False, '65s', 65000.0, None])
def test_check_duration_rejects_non_integer_duration(value) -> None:
    with pytest.raises(ValueError):
        check_duration(value, TEST_ONLY_DURATION_RANGE)


@pytest.mark.parametrize('policy', [(70000, 61000), (61000,), (61000, 65000, 70000), (True, 70000), ('61000', '70000'), 61000])
def test_check_duration_rejects_malformed_policy(policy) -> None:
    with pytest.raises(ValueError):
        check_duration(65000, policy)


HASH_CALLS = frozenset({'sha1', 'sha256', 'sha512', 'md5', 'blake2b', 'request_hash', 'canonicalize_json'})
ALLOWED_IMPORT_ROOTS = frozenset({'__future__', 'collections', 'copy', 'dataclasses', 'hashlib', 're', 'types', 'typing', 'voice'})


def find_range_constants(source: str) -> list:
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Constant):
            continue
        value = node.value
        if isinstance(value, int) and not isinstance(value, bool) and 61000 <= value <= 70000:
            found.append(value)
        elif isinstance(value, str) and ('61000' in value or '70000' in value):
            found.append(value)
    return found


def imported_modules(source: str) -> list[str]:
    names = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.append('.' * node.level + (node.module or ''))
    return names


def _roots(source: str) -> set[str]:
    return {name.split('.')[0] for name in imported_modules(source)}


def _hash_calls(node: ast.AST) -> list[ast.Call]:
    calls = []
    for item in ast.walk(node):
        if isinstance(item, ast.Call):
            func = item.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, 'id', None)
            if name in HASH_CALLS:
                calls.append(item)
    return calls


def test_range_detector_flags_counterexamples() -> None:
    for source, expected in (
        ('LOW = 61000', [61000]),
        ('HIGH = 70000', [70000]),
        ('RANGE = (61000, 70000)', [61000, 70000]),
        ('MID = 65000', [65000]),
        ("TEXT = '61000-70000'", ['61000-70000']),
    ):
        assert find_range_constants(source) == expected, source
    assert find_range_constants('X = 5\nY = 64') == []


@pytest.mark.parametrize('path', [VOICE_TRACK_SOURCE, SCRIPT_TEXT_SOURCE])
def test_sources_have_no_duration_range_constant(path) -> None:
    assert find_range_constants(path.read_text(encoding='utf-8')) == []


def test_import_detector_flags_counterexamples() -> None:
    for source in ('import socket', 'from src.voice import x', 'import controlplane.domain', 'from . import x', 'import creative'):
        assert _roots(source) - ALLOWED_IMPORT_ROOTS, source
    for source in ('import hashlib', 'from voice.ports.script_text import ScriptText', 'from collections.abc import Mapping'):
        assert not _roots(source) - ALLOWED_IMPORT_ROOTS, source


def test_sources_import_only_stdlib_and_voice_ports() -> None:
    track_source = VOICE_TRACK_SOURCE.read_text(encoding='utf-8')
    port_source = SCRIPT_TEXT_SOURCE.read_text(encoding='utf-8')
    assert _roots(track_source) <= ALLOWED_IMPORT_ROOTS
    assert _roots(port_source) <= ALLOWED_IMPORT_ROOTS
    assert 'voice.ports.script_text' in imported_modules(track_source)
    assert not [name for name in imported_modules(port_source) if name.startswith('voice')]


def test_only_compute_voice_hash_hashes_in_voice_track_source() -> None:
    tree = ast.parse(VOICE_TRACK_SOURCE.read_text(encoding='utf-8'))
    every = {id(call) for call in _hash_calls(tree)}
    inside = {
        id(call)
        for fn in ast.walk(tree)
        if isinstance(fn, ast.FunctionDef) and fn.name == 'compute_voice_hash'
        for call in _hash_calls(fn)
    }
    assert inside, 'compute_voice_hash must hash with sha256'
    assert every == inside, 'E must not recompute the script fingerprint or hash anywhere else'


def test_module_declares_covered_ids() -> None:
    doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
    assert 'coveredIds: CT-TTS-001' in (doc or '').splitlines()
