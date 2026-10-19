"""D-08: ScriptVersion, claim_mode, disclosure và đầu vào VoiceTrackRequest (CT-AI-004, CT-TTS-001).

coveredIds: CT-AI-004, CT-TTS-001
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import json
import pathlib
import re
import unicodedata

import pytest

from controlplane.application.idempotency import canonicalization
from creative.domain import ref_resolver, script as module
from creative.domain.ref_resolver import RefResolver, ResourceRef
from creative.domain.script import (
    BINDING_ENTITY,
    CLAIM_CREATIVE_HYPOTHESIS,
    CLAIM_INFERENCE,
    CLAIM_MODES,
    CLAIM_SOURCE_BACKED,
    CLAIM_TRANSITION,
    DISCLOSURE_MODES,
    DUPLICATE_ID,
    DURATION_OUT_OF_RANGE,
    EMPTY_VALUE,
    ENUM_VIOLATION,
    HALLUCINATED_REF,
    INPUT_NOT_READY,
    LANGUAGE_MISMATCH,
    MISSING_DISCLOSURE,
    MISSING_REQUIRED,
    MISSING_SOURCE_REF,
    SCHEMA_VIOLATION,
    VOICE_TRACK_INPUT_TYPES,
    WRONG_TYPE,
    LanguageVoicePolicy,
    ScriptRejected,
    ScriptSegment,
    ScriptVersion,
    TargetRange,
    build_script_version,
    count_words,
    normalize_narration,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
BINDING_PATH = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'd-e-f-voice-timing.json'
FIXTURE_PATH = ROOT / 'tests' / 'fixtures' / 'contracts' / 'd-e-f-voice-timing' / 'payloads.json'
MODULE_SOURCE = ROOT / 'src' / 'creative' / 'domain' / 'script.py'


def _binding_fields(entity: str) -> list[dict[str, object]]:
    data = json.loads(BINDING_PATH.read_text(encoding='utf-8'))
    for ent in data.get('entities', []):
        if ent.get('name') == entity:
            return ent.get('fields', [])
    return []


def _fixture_valid() -> dict[str, object]:
    data = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))
    return data['entities']['VoiceTrackRequest']['valid'][0]


WORKSPACE = 'ws-1'
REF_TYPE = 'source_article'


def _ref(ref_id: str, *, workspace_id: str = WORKSPACE, ref_type: str = REF_TYPE, revision_id: str | None = None) -> dict[str, str]:
    return {
        'workspace_id': workspace_id,
        'ref_type': ref_type,
        'ref_id': ref_id,
        'revision_id': revision_id if revision_id is not None else f'{ref_id}-r1',
    }


class SpyResolver(RefResolver):
    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.calls: list[object] = []

    def resolve(self, proposed):
        self.calls.append(proposed)
        return super().resolve(proposed)


def _resolver(cls=RefResolver) -> RefResolver:
    return cls(
        workspace_id=WORKSPACE,
        allowed_refs=[
            ResourceRef(WORKSPACE, REF_TYPE, 'a1', 'a1-r1'),
            ResourceRef(WORKSPACE, REF_TYPE, 'a2', 'a2-r1'),
        ],
        allowed_ref_types=[REF_TYPE],
    )


POLICY = LanguageVoicePolicy(language='en', speech_rate=2.0)
RANGE = TargetRange(min_seconds=61, max_seconds=70)
UNSET = object()


def _words(count: int, prefix: str = 'w') -> str:
    return ' '.join(f'{prefix}{i}' for i in range(count))


def _raw(total_words: int = 130) -> dict[str, object]:
    counts = [total_words // 5] * 4
    counts.append(total_words - sum(counts))
    segments = [
        {
            'segment_id': 's1',
            'order': 0,
            'text': _words(counts[0], 's1_'),
            'claim_mode': CLAIM_SOURCE_BACKED,
            'scene_intent': 'scene 1',
            'source_refs': [_ref('a1')],
        },
        {
            'segment_id': 's2',
            'order': 1,
            'text': _words(counts[1], 's2_'),
            'claim_mode': CLAIM_INFERENCE,
            'scene_intent': 'scene 2',
            'source_refs': [_ref('a2')],
            'disclosure': 'This is an inference from the sources.',
        },
        {
            'segment_id': 's3',
            'order': 2,
            'text': _words(counts[2], 's3_'),
            'claim_mode': CLAIM_CREATIVE_HYPOTHESIS,
            'scene_intent': 'scene 3',
            'source_refs': [],
            'disclosure': 'This is a creative hypothesis, not a reported fact.',
        },
        {
            'segment_id': 's4',
            'order': 3,
            'text': _words(counts[3], 's4_'),
            'claim_mode': CLAIM_TRANSITION,
            'scene_intent': 'scene 4',
            'source_refs': [],
        },
        {
            'segment_id': 's5',
            'order': 4,
            'text': _words(counts[4], 's5_'),
            'claim_mode': CLAIM_SOURCE_BACKED,
            'scene_intent': 'scene 5',
            'source_refs': [_ref('a2')],
        },
    ]
    return {
        'script_version_id': 'sv-1',
        'language': 'en',
        'hook_intent': 'Open with the surprising number',
        'thumbnail_transition': 'Cut from the thumbnail frame to the first scene',
        'pronunciation_hints': [{'term': 'Nguyen', 'pronunciation': 'win'}],
        'segments': segments,
    }


def _build(raw=UNSET, resolver=None, policy=UNSET, target_range=UNSET):
    target_raw = _raw() if raw is UNSET else raw
    target_resolver = _resolver() if resolver is None else resolver
    target_policy = POLICY if policy is UNSET else policy
    target_range_val = RANGE if target_range is UNSET else target_range
    return module.build_script_version(
        target_raw,
        resolver=target_resolver,
        language_policy=target_policy,
        target_range=target_range_val,
    )


def _rejected(raw=UNSET, **kw) -> ScriptRejected:
    with pytest.raises(ScriptRejected) as excinfo:
        _build(raw, **kw)
    return excinfo.value


def _code(err: ScriptRejected) -> tuple[str, str, str]:
    return (err.code, err.reason, err.field)
# ---------------------------------------------------------------------------
# Phần 2: Binding và hằng
# ---------------------------------------------------------------------------


def test_test_module_declares_covered_ids() -> None:
    source = pathlib.Path(__file__).read_text(encoding='utf-8')
    doc = ast.get_docstring(ast.parse(source))
    assert doc is not None
    assert 'coveredIds: CT-AI-004, CT-TTS-001' in doc.splitlines()


def test_claim_modes_are_exactly_the_four_contract_values() -> None:
    assert set(CLAIM_MODES) == {'source_backed', 'inference', 'creative_hypothesis', 'transition'}
    assert len(CLAIM_MODES) == 4


def test_voice_track_input_types_match_binding() -> None:
    fields = _binding_fields('VoiceTrackRequest')
    by_name = {f['name']: f for f in fields}
    for name, expected_type in VOICE_TRACK_INPUT_TYPES.items():
        assert name in by_name
        assert by_name[name]['type'] == expected_type
    assert set(VOICE_TRACK_INPUT_TYPES) == {'script_version_id', 'script_fingerprint', 'pronunciation_hints'}
    assert by_name['script_version_id']['required'] is True
    assert by_name['script_fingerprint']['required'] is True
    assert by_name['pronunciation_hints']['required'] is False


def test_drift_comparison_detects_mutated_binding() -> None:
    def derive(fields: list[dict[str, object]]) -> dict[str, object]:
        return {f['name']: f['type'] for f in fields if f['name'] in VOICE_TRACK_INPUT_TYPES}

    fields = _binding_fields('VoiceTrackRequest')
    assert derive(fields) == dict(VOICE_TRACK_INPUT_TYPES)

    # Mutation 1: đổi type script_fingerprint thành 'string'
    m1 = copy.deepcopy(fields)
    for f in m1:
        if f['name'] == 'script_fingerprint':
            f['type'] = 'string'
    assert derive(m1) != dict(VOICE_TRACK_INPUT_TYPES)

    # Mutation 2: đổi type pronunciation_hints thành 'object'
    m2 = copy.deepcopy(fields)
    for f in m2:
        if f['name'] == 'pronunciation_hints':
            f['type'] = 'object'
    assert derive(m2) != dict(VOICE_TRACK_INPUT_TYPES)

    # Mutation 3: xoá field script_version_id
    m3 = [f for f in copy.deepcopy(fields) if f['name'] != 'script_version_id']
    assert derive(m3) != dict(VOICE_TRACK_INPUT_TYPES)


def test_module_imports_stay_inside_allowlist_and_reuse_d03_and_request_hash() -> None:
    allowed_imports = {
        '__future__',
        'copy',
        'math',
        'unicodedata',
        'collections.abc',
        'dataclasses',
        'types',
        'controlplane.application.idempotency.canonicalization',
        'creative.domain.ref_resolver',
    }
    tree = ast.parse(MODULE_SOURCE.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name in allowed_imports, f'forbidden import {alias.name}'
        elif isinstance(node, ast.ImportFrom):
            mod = '.' * node.level + (node.module or '')
            assert mod in allowed_imports, f'forbidden import {mod}'

    assert module.request_hash is canonicalization.request_hash
    assert module.RefResolver is ref_resolver.RefResolver
    assert module.ResourceRef is ref_resolver.ResourceRef
# ---------------------------------------------------------------------------
# Phần 3: Cấu trúc và disclosure
# ---------------------------------------------------------------------------


def test_valid_script_builds_frozen_ordered_version() -> None:
    raw_source = _raw()
    v = _build(copy.deepcopy(raw_source))
    assert isinstance(v, ScriptVersion)
    assert ScriptVersion.__dataclass_params__.frozen is True
    assert ScriptSegment.__dataclass_params__.frozen is True
    assert isinstance(v.segments, tuple)
    assert [s.segment_id for s in v.segments] == ['s1', 's2', 's3', 's4', 's5']
    assert [s.order for s in v.segments] == [0, 1, 2, 3, 4]
    assert [s.claim_mode for s in v.segments] == [
        CLAIM_SOURCE_BACKED,
        CLAIM_INFERENCE,
        CLAIM_CREATIVE_HYPOTHESIS,
        CLAIM_TRANSITION,
        CLAIM_SOURCE_BACKED,
    ]
    assert v.hook_intent == raw_source['hook_intent']
    assert v.thumbnail_transition == raw_source['thumbnail_transition']
    assert v.language == 'en'
    assert v.scene_intents == ('scene 1', 'scene 2', 'scene 3', 'scene 4', 'scene 5')
    assert v.pronunciation_hints[0]['term'] == 'Nguyen'
    with pytest.raises(TypeError):
        v.pronunciation_hints[0]['term'] = 'other'  # type: ignore[index]

    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(v, 'language', 'vi')
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(v.segments[0], 'text', 'other')

    raw_mutable = _raw()
    v_from_mutable = _build(raw_mutable)
    raw_mutable['segments'][0]['text'] = 'completely changed'
    raw_mutable['pronunciation_hints'].pop()
    assert v_from_mutable == _build()


def test_all_inference_and_creative_segments_carry_disclosure() -> None:
    v = _build()
    for s in v.segments:
        if s.claim_mode in DISCLOSURE_MODES:
            assert isinstance(s.disclosure, str) and bool(s.disclosure.strip())
        else:
            # source_backed, transition dựng được dù không có disclosure
            pass

    # Duyệt 100% segment có disclosure modes
    target_indices = [i for i, s in enumerate(_raw()['segments']) if s['claim_mode'] in DISCLOSURE_MODES]
    missing_variants = ['delete', None, '', '   ', '\n\t']

    for i in target_indices:
        for variant in missing_variants:
            raw = copy.deepcopy(_raw())
            if variant == 'delete':
                raw['segments'][i].pop('disclosure', None)
            else:
                raw['segments'][i]['disclosure'] = variant
            err = _rejected(raw)
            assert _code(err) == (MISSING_DISCLOSURE, 'disclosure_required', f'segments[{i}].disclosure')

        # Disclosure sai kiểu
        raw_bad_type = copy.deepcopy(_raw())
        raw_bad_type['segments'][i]['disclosure'] = 123
        err_bad_type = _rejected(raw_bad_type)
        assert _code(err_bad_type) == (SCHEMA_VIOLATION, WRONG_TYPE, f'segments[{i}].disclosure')


def test_model_self_assessment_fields_never_decide_validity() -> None:
    raw = copy.deepcopy(_raw())
    raw['validated'] = True
    for s in raw['segments']:
        s['disclosure_ok'] = True
        s['source_verified'] = True
        s['model_confidence'] = 1.0

    # Segment inference không có disclosure vẫn phải bị từ chối
    raw_inference_missing = copy.deepcopy(raw)
    raw_inference_missing['segments'][1]['disclosure'] = None
    assert _code(_rejected(raw_inference_missing)) == (
        MISSING_DISCLOSURE,
        'disclosure_required',
        'segments[1].disclosure',
    )

    # Segment source_backed với source_refs=[] vẫn phải bị từ chối
    raw_source_empty = copy.deepcopy(raw)
    raw_source_empty['segments'][0]['source_refs'] = []
    assert _code(_rejected(raw_source_empty)) == (
        MISSING_SOURCE_REF,
        'source_backed_requires_ref',
        'segments[0].source_refs',
    )

    # Ngược lại raw hợp lệ kèm cờ False vẫn dựng được
    raw_false = copy.deepcopy(_raw())
    raw_false['validated'] = False
    for s in raw_false['segments']:
        s['disclosure_ok'] = False
        s['source_verified'] = False
    v = _build(raw_false)
    assert isinstance(v, ScriptVersion)
# ---------------------------------------------------------------------------
# Phần 4: Claim mode và source ref
# ---------------------------------------------------------------------------


def test_claim_mode_outside_contract_is_rejected() -> None:
    for invalid_val in ['fact', 'SOURCE_BACKED', '', 'creative', 'inference ']:
        raw = copy.deepcopy(_raw())
        raw['segments'][2]['claim_mode'] = invalid_val
        err = _rejected(raw)
        assert _code(err) == (SCHEMA_VIOLATION, ENUM_VIOLATION, 'segments[2].claim_mode')

    raw_bad_type = copy.deepcopy(_raw())
    raw_bad_type['segments'][2]['claim_mode'] = 123
    assert _code(_rejected(raw_bad_type)) == (SCHEMA_VIOLATION, WRONG_TYPE, 'segments[2].claim_mode')


def test_source_backed_requires_resolved_source_ref() -> None:
    raw_empty = copy.deepcopy(_raw())
    raw_empty['segments'][0]['source_refs'] = []
    assert _code(_rejected(raw_empty)) == (
        MISSING_SOURCE_REF,
        'source_backed_requires_ref',
        'segments[0].source_refs',
    )

    raw_missing_key = copy.deepcopy(_raw())
    del raw_missing_key['segments'][0]['source_refs']
    assert _code(_rejected(raw_missing_key)) == (
        SCHEMA_VIOLATION,
        MISSING_REQUIRED,
        'segments[0].source_refs',
    )

    v = _build()
    assert v.segments[0].source_refs == (ResourceRef(WORKSPACE, REF_TYPE, 'a1', 'a1-r1'),)


def test_every_source_ref_goes_through_the_d03_resolver() -> None:
    spy = _resolver(SpyResolver)
    _build(resolver=spy)
    assert spy.calls == [_ref('a1'), _ref('a2'), _ref('a2')]


@pytest.mark.parametrize(
    ('proposed', 'reason'),
    [
        (_ref('zzz'), 'unknown_ref'),
        (_ref('a1', workspace_id='ws-2'), 'workspace_mismatch'),
        (_ref('a1', revision_id='a1-old'), 'revision_mismatch'),
        (_ref('a1', ref_type='media_asset'), 'not_allowlisted'),
        ({}, 'unknown_ref'),
    ],
)
def test_hallucinated_ref_is_rejected(proposed: dict[str, object], reason: str) -> None:
    for seg_idx in [0, 1]:
        raw = copy.deepcopy(_raw())
        raw['segments'][seg_idx]['source_refs'] = [proposed]
        err = _rejected(raw)
        assert _code(err) == (HALLUCINATED_REF, reason, f'segments[{seg_idx}].source_refs[0]')

    # Phần tử source_refs không phải Mapping
    raw_not_map = copy.deepcopy(_raw())
    raw_not_map['segments'][0]['source_refs'] = ['a1']
    assert _code(_rejected(raw_not_map)) == (
        SCHEMA_VIOLATION,
        WRONG_TYPE,
        'segments[0].source_refs[0]',
    )
# ---------------------------------------------------------------------------
# Phần 5: Schema
# ---------------------------------------------------------------------------

SCHEMA_TEST_CASES = [
    # bỏ từng khoá cấp raw
    (lambda d: d.pop('script_version_id'), (MISSING_REQUIRED, 'script_version_id')),
    (lambda d: d.pop('language'), (MISSING_REQUIRED, 'language')),
    (lambda d: d.pop('hook_intent'), (MISSING_REQUIRED, 'hook_intent')),
    (lambda d: d.pop('thumbnail_transition'), (MISSING_REQUIRED, 'thumbnail_transition')),
    (lambda d: d.pop('pronunciation_hints'), (MISSING_REQUIRED, 'pronunciation_hints')),
    (lambda d: d.pop('segments'), (MISSING_REQUIRED, 'segments')),
    # rỗng / None cấp raw
    (lambda d: d.__setitem__('script_version_id', '   '), (EMPTY_VALUE, 'script_version_id')),
    (lambda d: d.__setitem__('script_version_id', None), (WRONG_TYPE, 'script_version_id')),
    (lambda d: d.__setitem__('hook_intent', '   '), (EMPTY_VALUE, 'hook_intent')),
    (lambda d: d.__setitem__('hook_intent', None), (WRONG_TYPE, 'hook_intent')),
    (lambda d: d.__setitem__('thumbnail_transition', '   '), (EMPTY_VALUE, 'thumbnail_transition')),
    (lambda d: d.__setitem__('thumbnail_transition', None), (WRONG_TYPE, 'thumbnail_transition')),
    # segments
    (lambda d: d.__setitem__('segments', []), (EMPTY_VALUE, 'segments')),
    (lambda d: d.__setitem__('segments', 'x'), (WRONG_TYPE, 'segments')),
    (lambda d: d.__setitem__('segments', ['x']), (WRONG_TYPE, 'segments[0]')),
    # segment 0 thiếu trường / rỗng
    (lambda d: d['segments'][0].pop('segment_id'), (MISSING_REQUIRED, 'segments[0].segment_id')),
    (lambda d: d['segments'][0].pop('text'), (MISSING_REQUIRED, 'segments[0].text')),
    (lambda d: d['segments'][0].pop('scene_intent'), (MISSING_REQUIRED, 'segments[0].scene_intent')),
    (lambda d: d['segments'][0].__setitem__('text', '  \n '), (EMPTY_VALUE, 'segments[0].text')),
    (lambda d: d['segments'][0].__setitem__('scene_intent', ''), (EMPTY_VALUE, 'segments[0].scene_intent')),
    # duplicate segment_id
    (lambda d: d['segments'][1].__setitem__('segment_id', d['segments'][0]['segment_id']), (DUPLICATE_ID, 'segments[1].segment_id')),
    # hints
    (lambda d: d['pronunciation_hints'][0].pop('term'), (MISSING_REQUIRED, 'pronunciation_hints[0].term')),
    (lambda d: d['pronunciation_hints'][0].__setitem__('pronunciation', ''), (EMPTY_VALUE, 'pronunciation_hints[0].pronunciation')),
    (lambda d: d.__setitem__('pronunciation_hints', ['x']), (WRONG_TYPE, 'pronunciation_hints[0]')),
]


@pytest.mark.parametrize(('mutate', 'expected'), SCHEMA_TEST_CASES)
def test_schema_violations_report_field(mutate, expected: tuple[str, str]) -> None:
    raw = copy.deepcopy(_raw())
    mutate(raw)
    err = _rejected(raw)
    reason, field = expected
    assert _code(err) == (SCHEMA_VIOLATION, reason, field)


@pytest.mark.parametrize('bad_raw', [None, [], 'x'])
def test_raw_not_mapping_is_wrong_type(bad_raw: object) -> None:
    err = _rejected(bad_raw)
    assert _code(err) == (SCHEMA_VIOLATION, WRONG_TYPE, '$')


def test_schema_is_checked_before_refs_and_duration() -> None:
    raw = copy.deepcopy(_raw())
    raw['segments'][0]['source_refs'] = [_ref('zzz')]
    del raw['hook_intent']
    err = _rejected(raw)
    assert _code(err) == (SCHEMA_VIOLATION, MISSING_REQUIRED, 'hook_intent')
# ---------------------------------------------------------------------------
# Phần 6: Policy và thời lượng
# ---------------------------------------------------------------------------


def test_missing_policy_or_target_range_is_input_not_ready() -> None:
    assert _code(_rejected(policy=None)) == (
        INPUT_NOT_READY,
        'missing_language_policy',
        'language_policy',
    )
    assert _code(_rejected(target_range=None)) == (
        INPUT_NOT_READY,
        'missing_target_range',
        'target_range',
    )

    with pytest.raises(ScriptRejected) as excinfo:
        LanguageVoicePolicy(language='en', speech_rate=None)  # type: ignore[arg-type]
    assert (excinfo.value.code, excinfo.value.reason, excinfo.value.field) == (
        INPUT_NOT_READY,
        'missing_speech_rate',
        'speech_rate',
    )

    for bad_lang in [None, '']:
        with pytest.raises(ScriptRejected) as excinfo:
            LanguageVoicePolicy(language=bad_lang, speech_rate=2.0)  # type: ignore[arg-type]
        assert (excinfo.value.code, excinfo.value.reason, excinfo.value.field) == (
            INPUT_NOT_READY,
            'missing_language',
            'language',
        )

    with pytest.raises(ScriptRejected) as excinfo:
        TargetRange(min_seconds=None, max_seconds=70)  # type: ignore[arg-type]
    assert (excinfo.value.code, excinfo.value.reason, excinfo.value.field) == (
        INPUT_NOT_READY,
        'missing_target_range',
        'min_seconds',
    )

    with pytest.raises(ScriptRejected) as excinfo:
        TargetRange(min_seconds=61, max_seconds=None)  # type: ignore[arg-type]
    assert (excinfo.value.code, excinfo.value.reason, excinfo.value.field) == (
        INPUT_NOT_READY,
        'missing_target_range',
        'max_seconds',
    )

    # Thiếu policy được báo TRƯỚC khi đọc raw
    assert _code(_rejected('garbage', policy=None)) == (
        INPUT_NOT_READY,
        'missing_language_policy',
        'language_policy',
    )


def test_malformed_policy_values_raise_value_error() -> None:
    for bad_rate in [0, -1, True, float('nan'), float('inf'), '2']:
        with pytest.raises(ValueError):
            LanguageVoicePolicy(language='en', speech_rate=bad_rate)  # type: ignore[arg-type]

    for bad_range in [
        (70, 61),  # min > max
        (0, 70),   # min = 0
        (-1, 70),  # min < 0
        (True, 70),
        (61, True),
        (float('nan'), 70),
        (61, float('nan')),
    ]:
        with pytest.raises(ValueError):
            TargetRange(min_seconds=bad_range[0], max_seconds=bad_range[1])  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ('rate', 'words', 'reason'),
    [
        (2.0, 122, None),
        (2.0, 121, 'below_target_range'),
        (2.0, 140, None),
        (2.0, 141, 'above_target_range'),
        (3.0, 183, None),
        (3.0, 182, 'below_target_range'),
        (3.0, 210, None),
        (3.0, 211, 'above_target_range'),
        (2.5, 153, None),
        (2.5, 150, 'below_target_range'),
        (1.0, 150, 'above_target_range'),
    ],
)
def test_duration_is_word_count_divided_by_speech_rate(
    rate: float,
    words: int,
    reason: str | None,
) -> None:
    pol = LanguageVoicePolicy(language='en', speech_rate=rate)
    raw = _raw(words)
    if reason is None:
        v = _build(raw, policy=pol, target_range=RANGE)
        assert isinstance(v, ScriptVersion)
        assert v.estimated_duration_seconds == pytest.approx(words / rate)
        assert sum(s.estimated_seconds for s in v.segments) == pytest.approx(v.estimated_duration_seconds)
        assert sum(s.word_count for s in v.segments) == words
        assert v.speech_rate == rate
    else:
        err = _rejected(raw, policy=pol, target_range=RANGE)
        assert _code(err) == (DURATION_OUT_OF_RANGE, reason, 'segments')


def test_hardcoded_word_band_and_model_claimed_duration_do_not_decide() -> None:
    # 150 từ ở rate 3.0 (50 s) và ở rate 1.0 (150 s) đều DURATION_OUT_OF_RANGE
    pol3 = LanguageVoicePolicy(language='en', speech_rate=3.0)
    err3 = _rejected(_raw(150), policy=pol3, target_range=RANGE)
    assert _code(err3) == (DURATION_OUT_OF_RANGE, 'below_target_range', 'segments')

    pol1 = LanguageVoicePolicy(language='en', speech_rate=1.0)
    err1 = _rejected(_raw(150), policy=pol1, target_range=RANGE)
    assert _code(err1) == (DURATION_OUT_OF_RANGE, 'above_target_range', 'segments')

    # _raw(90) ở rate 2.0 (45 s) bị DURATION_OUT_OF_RANGE dù raw chứa claimed duration
    raw90 = _raw(90)
    raw90['estimated_duration_seconds'] = 65
    for s in raw90['segments']:
        s['estimated_seconds'] = 65
    err90 = _rejected(raw90, policy=POLICY, target_range=RANGE)
    assert _code(err90) == (DURATION_OUT_OF_RANGE, 'below_target_range', 'segments')

    # TargetRange(30, 40) với _raw(70) ở rate 2.0 (35 s) hợp lệ
    custom_range = TargetRange(min_seconds=30, max_seconds=40)
    v_custom = _build(_raw(70), policy=POLICY, target_range=custom_range)
    assert isinstance(v_custom, ScriptVersion)
    assert v_custom.estimated_duration_seconds == pytest.approx(35.0)


def test_language_follows_policy() -> None:
    raw_vi = _raw()
    raw_vi['language'] = 'vi'
    err = _rejected(raw_vi, policy=POLICY)
    assert _code(err) == (LANGUAGE_MISMATCH, 'policy_language_mismatch', 'language')

    pol_vi = LanguageVoicePolicy(language='vi', speech_rate=2.0)
    v_vi = _build(raw_vi, policy=pol_vi)
    assert isinstance(v_vi, ScriptVersion)
    assert v_vi.language == 'vi'
# ---------------------------------------------------------------------------
# Phần 7: Normalization, fingerprint, voice track inputs
# ---------------------------------------------------------------------------


def test_normalization_and_word_count() -> None:
    assert normalize_narration('  Hello\n\tworld  ') == 'Hello world'
    nfd_e = unicodedata.normalize('NFD', 'café')
    nfc_e = unicodedata.normalize('NFC', 'café')
    assert normalize_narration(nfd_e) == normalize_narration(nfc_e)
    assert count_words('a  b\nc') == 3
    assert count_words('') == 0
    assert normalize_narration('AbC') == 'AbC'


def test_fingerprint_is_sha256_over_normalized_narration_in_segment_order() -> None:
    v = _build()
    fp = v.script_fingerprint
    assert re.fullmatch(r'[0-9a-f]{64}', fp)
    expected_basis = {'narration': [module.normalize_narration(s['text']) for s in _raw()['segments']]}
    assert fp == canonicalization.request_hash(expected_basis)
    assert fp == canonicalization.request_hash(v.fingerprint_basis())
    assert fp == _build().script_fingerprint

    # KHÔNG đổi khi chỉ đổi:
    # script_version_id, segment_ids, scene_intent, hook_intent, thumbnail_transition,
    # disclosure, source_refs (a1 <-> a2), pronunciation_hints
    raw_subtle = copy.deepcopy(_raw())
    raw_subtle['script_version_id'] = 'sv-other-999'
    raw_subtle['hook_intent'] = 'Completely different hook intent'
    raw_subtle['thumbnail_transition'] = 'Different transition'
    raw_subtle['pronunciation_hints'] = [{'term': 'Other', 'pronunciation': 'oth'}]
    for idx, s in enumerate(raw_subtle['segments']):
        s['segment_id'] = f'seg-changed-{idx}'
        s['scene_intent'] = f'changed scene {idx}'
        if s.get('disclosure'):
            s['disclosure'] = 'Different disclosure text that is valid'
        if s['source_refs']:
            # đổi a1 <-> a2
            s['source_refs'] = [_ref('a2') if r['ref_id'] == 'a1' else _ref('a1') for r in s['source_refs']]
    v_subtle = _build(raw_subtle)
    assert v_subtle.script_fingerprint == fp

    # KHÔNG đổi khi chèn khoảng trắng/xuống dòng thừa vào text hoặc đổi NFC <-> NFD
    raw_spaces = copy.deepcopy(_raw())
    raw_spaces['segments'][0]['text'] = '   ' + raw_spaces['segments'][0]['text'].replace(' ', '  \n\t  ') + '   '
    v_spaces = _build(raw_spaces)
    assert v_spaces.script_fingerprint == fp

    # ĐỔI khi đổi một từ
    raw_word = copy.deepcopy(_raw())
    raw_word['segments'][0]['text'] = raw_word['segments'][0]['text'] + ' extra'
    v_word = _build(raw_word)
    assert v_word.script_fingerprint != fp

    # ĐỔI khi hoán đổi thứ tự hai segment (giữ nguyên số từ)
    raw_swap = copy.deepcopy(_raw())
    raw_swap['segments'][0]['text'], raw_swap['segments'][1]['text'] = (
        raw_swap['segments'][1]['text'],
        raw_swap['segments'][0]['text'],
    )
    v_swap = _build(raw_swap)
    assert v_swap.script_fingerprint != fp

    # ĐỔI khi tách một segment thành hai
    raw_split = copy.deepcopy(_raw())
    seg0_words = raw_split['segments'][0]['text'].split()
    half = len(seg0_words) // 2
    raw_split['segments'][0]['text'] = ' '.join(seg0_words[:half])
    split_seg = {
        'segment_id': 's1_bis',
        'order': 5,
        'text': ' '.join(seg0_words[half:]),
        'claim_mode': CLAIM_TRANSITION,
        'scene_intent': 'split scene',
        'source_refs': [],
    }
    raw_split['segments'].insert(1, split_seg)
    v_split = _build(raw_split)
    assert v_split.script_fingerprint != fp


def test_to_voice_track_inputs_matches_binding_field_types() -> None:
    v = _build()
    out = v.to_voice_track_inputs()
    assert set(out) == set(VOICE_TRACK_INPUT_TYPES)

    fields = _binding_fields('VoiceTrackRequest')
    type_from_binding = {f['name']: f['type'] for f in fields}
    fixture_valid = _fixture_valid()
    assert re.fullmatch(r'[0-9a-f]{64}', fixture_valid['script_fingerprint'])

    for name, value in out.items():
        binding_type = type_from_binding[name]
        if binding_type == 'string':
            assert isinstance(value, str) and len(value) > 0
        elif binding_type == 'sha256':
            assert isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value)
        elif binding_type == 'array':
            assert isinstance(value, list)

    assert out['script_version_id'] == 'sv-1'
    assert out['script_fingerprint'] == v.script_fingerprint
    assert out['pronunciation_hints'] == [{'term': 'Nguyen', 'pronunciation': 'win'}]
    assert json.dumps(out)
    assert type(out['pronunciation_hints'][0]) is dict

    # Sửa out không ảnh hưởng lần gọi sau
    out['script_version_id'] = 'mutated'
    out['pronunciation_hints'].append({'term': 'x', 'pronunciation': 'y'})
    assert v.to_voice_track_inputs()['script_version_id'] == 'sv-1'
    assert len(v.to_voice_track_inputs()['pronunciation_hints']) == 1

    assert (set(out) - {"pronunciation_hints"}) <= set(fixture_valid)
    assert set(out) <= {f["name"] for f in fields}

    # raw có pronunciation_hints=[]
    raw_empty_hints = copy.deepcopy(_raw())
    raw_empty_hints['pronunciation_hints'] = []
    v_empty = _build(raw_empty_hints)
    assert v_empty.to_voice_track_inputs()['pronunciation_hints'] == []