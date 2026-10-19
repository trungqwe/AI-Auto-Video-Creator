"""F-06: điều kiện hook, thumbnail, voice, timing, timeline theo CT-RND-003 số 1-4 và 6.

coveredIds: CT-RND-003 (1-4, 6), TST-MEDIA-INV-007 (phía F)
"""
import ast
import copy
import dataclasses
import json
import pathlib
import types

import pytest

from render.domain.package_contract import validate_render_package_payload
from render.domain.preconditions_media import (
    AUDIO_HOOK_MISSING,
    CONDITION_AUDIO_HOOK,
    CONDITION_THUMBNAIL,
    CONDITION_TIMELINE,
    CONDITION_VISUAL_HOOK,
    CONDITION_VOICE_TIMING,
    THUMBNAIL_MISSING,
    THUMBNAIL_OUTSIDE_HOOK_RANGE,
    TIME_RANGE_INVALID,
    TIMELINE_SEGMENT_WITHOUT_VISUAL,
    TIMELINE_SEGMENTS_INVALID,
    VISUAL_HOOK_MISSING,
    VOICE_MISSING,
    VOICE_TIMING_BINDING_MISMATCH,
    WORD_TIMING_MISSING,
    Finding,
    VoiceTrackInfo,
    WordTimingInfo,
    check_hook_preconditions,
    check_timeline_coverage,
    check_voice_timing_binding,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
PACKAGE_FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'f-render-package' / 'payloads.json'
VOICE_FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'd-e-f-voice-timing' / 'payloads.json'
VOICE_BINDING = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'd-e-f-voice-timing.json'
MODULE_PATH = ROOT / 'src' / 'render' / 'domain' / 'preconditions_media.py'
DELETE = object()


def _record(**changes: object) -> object:
    raw = json.loads(PACKAGE_FIXTURE.read_text(encoding='utf-8'))
    payload = copy.deepcopy(raw['entities']['RenderPackage']['valid'][0])
    for key, value in changes.items():
        if value is DELETE:
            payload.pop(key, None)
        else:
            payload[key] = value
    return validate_render_package_payload(payload)


def _placement(**changes: object) -> dict:
    raw = json.loads(PACKAGE_FIXTURE.read_text(encoding='utf-8'))
    valid_payload = raw['entities']['RenderPackage']['valid'][0]
    placement = copy.deepcopy(valid_payload['hook_placement'])
    for key, value in changes.items():
        if value is DELETE:
            placement.pop(key, None)
        else:
            placement[key] = value
    return placement


def _hook(**changes: object) -> tuple[Finding, ...]:
    return check_hook_preconditions(_record(hook_placement=_placement(**changes)))


def _pairs(findings: tuple[Finding, ...] | list[Finding]) -> list[tuple[str, str]]:
    return [(f.code, f.field) for f in findings]


def _voice(**changes: object) -> VoiceTrackInfo:
    raw = json.loads(VOICE_FIXTURE.read_text(encoding='utf-8'))
    valid = raw['entities']['VoiceTrackResult']['valid'][0]
    field_names = {f.name for f in dataclasses.fields(VoiceTrackInfo)}
    init_kwargs = {k: v for k, v in valid.items() if k in field_names}
    obj = VoiceTrackInfo(**init_kwargs)
    if changes:
        obj = dataclasses.replace(obj, **changes)
    return obj


def _timing(**changes: object) -> WordTimingInfo:
    raw = json.loads(VOICE_FIXTURE.read_text(encoding='utf-8'))
    valid = raw['entities']['WordTiming']['valid'][0]
    field_names = {f.name for f in dataclasses.fields(WordTimingInfo)}
    init_kwargs = {k: v for k, v in valid.items() if k in field_names}
    obj = WordTimingInfo(**init_kwargs)
    if changes:
        obj = dataclasses.replace(obj, **changes)
    return obj


def _range(start: object, end: object) -> dict:
    return {'start_ms': start, 'end_ms': end}


def _segment(**changes: object) -> dict:
    seg = {'start_ms': 0, 'end_ms': 1000, 'visual_asset_refs': ['asset-1']}
    for key, value in changes.items():
        if value is DELETE:
            seg.pop(key, None)
        else:
            seg[key] = value
    return seg


def test_valid_fixture_has_no_hook_findings() -> None:
    assert _hook() == ()


def test_finding_is_frozen() -> None:
    assert [f.name for f in dataclasses.fields(Finding)] == ['condition', 'code', 'field']
    assert Finding.__dataclass_params__.frozen is True
    finding = Finding(1, 'code', 'field')
    with pytest.raises(dataclasses.FrozenInstanceError):
        finding.code = 'other'  # type: ignore[misc]


def test_codes_and_conditions_are_stable() -> None:
    assert VISUAL_HOOK_MISSING == 'visual_hook_missing'
    assert AUDIO_HOOK_MISSING == 'audio_hook_missing'
    assert THUMBNAIL_MISSING == 'thumbnail_missing'
    assert THUMBNAIL_OUTSIDE_HOOK_RANGE == 'thumbnail_outside_hook_range'
    assert TIME_RANGE_INVALID == 'time_range_invalid'
    assert VOICE_MISSING == 'voice_missing'
    assert WORD_TIMING_MISSING == 'word_timing_missing'
    assert VOICE_TIMING_BINDING_MISMATCH == 'voice_timing_binding_mismatch'
    assert TIMELINE_SEGMENT_WITHOUT_VISUAL == 'timeline_segment_without_visual'
    assert TIMELINE_SEGMENTS_INVALID == 'timeline_segments_invalid'

    assert CONDITION_VISUAL_HOOK == 1
    assert CONDITION_AUDIO_HOOK == 2
    assert CONDITION_THUMBNAIL == 3
    assert CONDITION_VOICE_TIMING == 4
    assert CONDITION_TIMELINE == 6


@pytest.mark.parametrize('value', [DELETE, '', '   ', None, 5])
def test_visual_hook_missing(value: object) -> None:
    assert _hook(visual_hook_ref=value) == (
        Finding(CONDITION_VISUAL_HOOK, VISUAL_HOOK_MISSING, 'hook_placement.visual_hook_ref'),
    )


@pytest.mark.parametrize('value', [DELETE, '', '   ', None, 5])
def test_audio_hook_missing(value: object) -> None:
    assert _hook(audio_hook_ref=value) == (
        Finding(CONDITION_AUDIO_HOOK, AUDIO_HOOK_MISSING, 'hook_placement.audio_hook_ref'),
    )


@pytest.mark.parametrize('value', [DELETE, '', '   ', None, 5])
def test_thumbnail_missing(value: object) -> None:
    assert _hook(thumbnail_ref=value) == (
        Finding(CONDITION_THUMBNAIL, THUMBNAIL_MISSING, 'hook_placement.thumbnail_ref'),
    )


@pytest.mark.parametrize(
    ('hook', 'thumb', 'outside'),
    [
        ((0, 8000), (5000, 6000), False),
        ((0, 3000), (2500, 3500), True),
        ((4000, 9000), (0, 3000), True),
        ((0, 3000), (500, 1500), False),
    ],
)
def test_thumbnail_range_is_inside_hook_range_not_fixed_three_seconds(
    hook: tuple[int, int],
    thumb: tuple[int, int],
    outside: bool,
) -> None:
    result = _hook(hook_time_range=_range(*hook), thumbnail_time_range=_range(*thumb))
    if outside:
        assert result == (
            Finding(CONDITION_THUMBNAIL, THUMBNAIL_OUTSIDE_HOOK_RANGE, 'hook_placement.thumbnail_time_range'),
        )
    else:
        assert result == ()


def test_thumbnail_range_bounds_are_inclusive() -> None:
    hook = (1000, 5000)
    for thumb in [(1000, 5000), (1000, 2000), (4000, 5000)]:
        assert _hook(hook_time_range=_range(*hook), thumbnail_time_range=_range(*thumb)) == ()
    for thumb in [(999, 2000), (2000, 5001)]:
        assert _hook(hook_time_range=_range(*hook), thumbnail_time_range=_range(*thumb)) == (
            Finding(CONDITION_THUMBNAIL, THUMBNAIL_OUTSIDE_HOOK_RANGE, 'hook_placement.thumbnail_time_range'),
        )


@pytest.mark.parametrize('field_name', ['hook_time_range', 'thumbnail_time_range'])
@pytest.mark.parametrize(
    'bad',
    [
        _range(100, 100),
        _range(200, 100),
        _range(-1, 100),
        _range(True, 100),
        _range(0, True),
        _range('0', 100),
        _range(0.0, 100),
        _range(0, 100.5),
        {'start_ms': 0},
        {'end_ms': 100},
        None,
        'x',
        DELETE,
    ],
)
def test_invalid_range_is_time_range_invalid(field_name: str, bad: object) -> None:
    assert _hook(**{field_name: bad}) == (
        Finding(CONDITION_THUMBNAIL, TIME_RANGE_INVALID, f'hook_placement.{field_name}'),
    )


def test_both_ranges_invalid_report_hook_first() -> None:
    result = _hook(hook_time_range=_range(5, 5), thumbnail_time_range=_range(9, 1))
    assert _pairs(result) == [
        ('time_range_invalid', 'hook_placement.hook_time_range'),
        ('time_range_invalid', 'hook_placement.thumbnail_time_range'),
    ]


def test_thumbnail_range_not_checked_when_thumbnail_missing() -> None:
    result = _hook(thumbnail_ref=DELETE, thumbnail_time_range=DELETE)
    assert _pairs(result) == [('thumbnail_missing', 'hook_placement.thumbnail_ref')]


def test_findings_follow_fixed_order() -> None:
    result1 = _hook(
        visual_hook_ref=DELETE,
        audio_hook_ref=DELETE,
        thumbnail_ref=DELETE,
        hook_time_range=_range(9, 9),
    )
    assert [f.code for f in result1] == [
        'visual_hook_missing',
        'audio_hook_missing',
        'thumbnail_missing',
        'time_range_invalid',
    ]

    result2 = _hook(
        visual_hook_ref=DELETE,
        audio_hook_ref=DELETE,
        hook_time_range=_range(0, 3000),
        thumbnail_time_range=_range(2500, 3500),
    )
    assert [f.code for f in result2] == [
        'visual_hook_missing',
        'audio_hook_missing',
        'thumbnail_outside_hook_range',
    ]


@pytest.mark.parametrize('value', [{}, None, 'x'])
def test_empty_or_non_mapping_placement_reports_every_missing(value: object) -> None:
    result = check_hook_preconditions(types.SimpleNamespace(hook_placement=value))
    assert _pairs(result) == [
        ('visual_hook_missing', 'hook_placement.visual_hook_ref'),
        ('audio_hook_missing', 'hook_placement.audio_hook_ref'),
        ('thumbnail_missing', 'hook_placement.thumbnail_ref'),
        ('time_range_invalid', 'hook_placement.hook_time_range'),
    ]


def test_valid_fixture_has_no_voice_timing_findings() -> None:
    assert check_voice_timing_binding(_record(), _voice(), _timing()) == ()


@pytest.mark.parametrize(
    ('voice', 'timing', 'expected'),
    [
        (None, _timing(), [('voice_missing', 'voice_artifact_ref')]),
        (_voice(), None, [('word_timing_missing', 'word_timing_ref')]),
        (None, None, [('voice_missing', 'voice_artifact_ref'), ('word_timing_missing', 'word_timing_ref')]),
        ({'voice_artifact_ref': 'x'}, _timing(), [('voice_missing', 'voice_artifact_ref')]),
    ],
)
def test_missing_voice_or_timing(
    voice: object,
    timing: object,
    expected: list[tuple[str, str]],
) -> None:
    result = check_voice_timing_binding(_record(), voice, timing)
    assert _pairs(result) == expected
    for f in result:
        assert f.condition == CONDITION_VOICE_TIMING


def test_record_without_ref_is_missing() -> None:
    assert _pairs(check_voice_timing_binding(_record(voice_artifact_ref=''), _voice(), _timing())) == [
        ('voice_missing', 'voice_artifact_ref'),
    ]
    assert _pairs(check_voice_timing_binding(_record(word_timing_ref='   '), _voice(), _timing())) == [
        ('word_timing_missing', 'word_timing_ref'),
    ]


@pytest.mark.parametrize(
    ('voice_changes', 'timing_changes', 'field'),
    [
        ({'voice_hash': 'e' * 64}, {}, 'voice_hash'),
        ({}, {'voice_hash': 'e' * 64}, 'voice_hash'),
        ({'script_fingerprint': 'f' * 64}, {}, 'script_fingerprint'),
        ({}, {'script_fingerprint': 'f' * 64}, 'script_fingerprint'),
        (
            {'script_fingerprint': '', 'voice_hash': 'e' * 64},
            {'script_fingerprint': '', 'voice_hash': 'e' * 64},
            'script_fingerprint',
        ),
    ],
)
def test_changed_hash_or_fingerprint_is_mismatch(
    voice_changes: dict,
    timing_changes: dict,
    field: str,
) -> None:
    result = check_voice_timing_binding(_record(), _voice(**voice_changes), _timing(**timing_changes))
    assert result == (
        Finding(CONDITION_VOICE_TIMING, VOICE_TIMING_BINDING_MISMATCH, field),
    )


@pytest.mark.parametrize(
    ('voice_changes', 'timing_changes', 'field'),
    [
        ({'voice_artifact_ref': 'other'}, {}, 'voice_artifact_ref'),
        ({}, {'timing_artifact_ref': 'other'}, 'word_timing_ref'),
        ({'script_version_id': 'other'}, {}, 'script_version_id'),
        ({}, {'script_version_id': 'other'}, 'script_version_id'),
        ({'script_version_id': 'a'}, {'script_version_id': 'b'}, 'script_version_id'),
    ],
)
def test_ref_and_version_mismatch_with_package(
    voice_changes: dict,
    timing_changes: dict,
    field: str,
) -> None:
    result = check_voice_timing_binding(_record(), _voice(**voice_changes), _timing(**timing_changes))
    assert result == (
        Finding(CONDITION_VOICE_TIMING, VOICE_TIMING_BINDING_MISMATCH, field),
    )


def test_every_finding_is_returned_in_fixed_order() -> None:
    voice = _voice(
        voice_artifact_ref='v',
        script_version_id='s',
        script_fingerprint='a' * 64,
        voice_hash='c' * 64,
    )
    timing = _timing(
        timing_artifact_ref='t',
        script_fingerprint='b' * 64,
        voice_hash='d' * 64,
    )
    result = check_voice_timing_binding(_record(), voice, timing)
    assert [f.field for f in result] == [
        'voice_artifact_ref',
        'word_timing_ref',
        'script_version_id',
        'script_fingerprint',
        'voice_hash',
    ]
    for f in result:
        assert f.code == VOICE_TIMING_BINDING_MISMATCH

    result_missing = check_voice_timing_binding(_record(), None, _timing(script_version_id='other'))
    assert _pairs(result_missing) == [
        ('voice_missing', 'voice_artifact_ref'),
        ('voice_timing_binding_mismatch', 'script_version_id'),
    ]


def test_dtos_are_frozen_subsets_of_binding() -> None:
    binding_data = json.loads(VOICE_BINDING.read_text(encoding='utf-8'))
    entities = {e['name']: {f['name'] for f in e['fields']} for e in binding_data['entities']}
    voice_fields = {f.name for f in dataclasses.fields(VoiceTrackInfo)}
    timing_fields = {f.name for f in dataclasses.fields(WordTimingInfo)}
    assert voice_fields <= entities['VoiceTrackResult']
    assert timing_fields <= entities['WordTiming']

    v = _voice()
    with pytest.raises(dataclasses.FrozenInstanceError):
        v.voice_artifact_ref = 'mod'  # type: ignore[misc]

    t = _timing()
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.timing_artifact_ref = 'mod'  # type: ignore[misc]


def test_empty_segments_is_valid() -> None:
    assert check_timeline_coverage({'segments': []}) == ()
    assert check_timeline_coverage(_record().timeline) == ()


def test_segment_with_visual_is_valid() -> None:
    assert check_timeline_coverage(
        {
            'segments': [
                _segment(),
                _segment(start_ms=1000, end_ms=2500, visual_asset_refs=['a', 'b']),
                _segment(visual_asset_refs=('a',)),
            ]
        }
    ) == ()


@pytest.mark.parametrize('value', [DELETE, [], (), '', ['  '], [None], None, 'asset-1', {'a': 1}])
def test_segment_without_visual(value: object) -> None:
    assert check_timeline_coverage({'segments': [_segment(visual_asset_refs=value)]}) == (
        Finding(CONDITION_TIMELINE, TIMELINE_SEGMENT_WITHOUT_VISUAL, 'timeline.segments[0].visual_asset_refs'),
    )


@pytest.mark.parametrize(
    ('start', 'end'),
    [
        (5, 5),
        (9, 3),
        (-1, 10),
        (True, 10),
        (0, True),
        ('0', 10),
        (0.5, 10),
        (DELETE, 10),
        (0, DELETE),
    ],
)
def test_segment_invalid_range(start: object, end: object) -> None:
    assert check_timeline_coverage({'segments': [_segment(start_ms=start, end_ms=end)]}) == (
        Finding(CONDITION_TIMELINE, TIME_RANGE_INVALID, 'timeline.segments[0]'),
    )


def test_every_segment_reports_all_findings() -> None:
    segments = [
        _segment(),
        _segment(visual_asset_refs=[]),
        _segment(start_ms=7, end_ms=7, visual_asset_refs=DELETE),
    ]
    result = check_timeline_coverage({'segments': segments})
    assert _pairs(result) == [
        ('timeline_segment_without_visual', 'timeline.segments[1].visual_asset_refs'),
        ('timeline_segment_without_visual', 'timeline.segments[2].visual_asset_refs'),
        ('time_range_invalid', 'timeline.segments[2]'),
    ]


def test_non_mapping_segment_is_reported() -> None:
    segments = ['x']
    result = check_timeline_coverage({'segments': segments})
    assert _pairs(result) == [
        ('timeline_segment_without_visual', 'timeline.segments[0].visual_asset_refs'),
        ('time_range_invalid', 'timeline.segments[0]'),
    ]


@pytest.mark.parametrize('value', [{}, {'segments': None}, {'segments': 'abc'}, {'segments': {'a': 1}}, None, []])
def test_malformed_segments_container(value: object) -> None:
    assert check_timeline_coverage(value) == (
        Finding(CONDITION_TIMELINE, TIMELINE_SEGMENTS_INVALID, 'timeline.segments'),
    )


def test_frozen_record_timeline_is_checked() -> None:
    rec = _record(timeline={'segments': [_segment(visual_asset_refs=DELETE)]})
    assert _pairs(check_timeline_coverage(rec.timeline)) == [
        ('timeline_segment_without_visual', 'timeline.segments[0].visual_asset_refs'),
    ]


def test_module_imports_only_pure_stdlib() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    assert imports <= {'__future__', 'collections.abc', 'dataclasses'}


def test_test_module_declares_covered_ids() -> None:
    doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
    assert any(line.strip().startswith('coveredIds:') for line in (doc or '').splitlines())
