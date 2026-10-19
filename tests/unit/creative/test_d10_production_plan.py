"""D-10: ProductionPlan (CT-AI-007) và đầu vào RenderPackage (CT-RND-003).

coveredIds: CT-AI-007, CT-RND-003
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
import json
import pathlib
import re
from types import MappingProxyType

import pytest
from controlplane.application.idempotency import canonicalization
from creative.domain import production_plan as module
from creative.domain.asset_selection import CreativeAssetSelection, FallbackCandidate, SceneAssignment
from creative.domain.production_plan import (
    BINDING_ENTITY,
    CONTEXT_MISMATCH,
    FALLBACK_KINDS,
    FORBIDDEN_CONTENT,
    FORBIDDEN_FIELDS,
    HALLUCINATED_REF,
    INPUT_NOT_READY,
    INVALID_HOOK_PLACEMENT,
    INVALID_TIME_RANGE,
    RENDER_PACKAGE_INPUT_TYPES,
    SCHEMA_VIOLATION,
    TIMELINE_GAP,
    PlanRejected,
    ProductionPlan,
    build_production_plan,
)
from creative.domain.ref_resolver import ResourceRef
from creative.domain.script import ScriptSegment, ScriptVersion

ROOT = pathlib.Path(__file__).resolve().parents[3]
BINDING_PATH = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'f-render-package.json'
FIXTURE_PATH = ROOT / 'tests' / 'fixtures' / 'contracts' / 'f-render-package' / 'payloads.json'
MODULE_SOURCE = ROOT / 'src' / 'creative' / 'domain' / 'production_plan.py'
WS = 'ws-1'


def _binding_entity():
    data = json.loads(BINDING_PATH.read_text(encoding='utf-8'))
    return next(e for e in data['entities'] if e['name'] == 'RenderPackage')


def _binding_types():
    return {f['name']: f['type'] for f in _binding_entity()['fields']}


def _fixture_valid():
    data = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))
    return data['entities']['RenderPackage']['valid'][0]


def _fixture_invalid(case):
    data = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))
    return next(item for item in data['entities']['RenderPackage']['invalid'] if item['case'] == case)


def _script(text='Hello world'):
    words = text.split()
    count = len(words)
    est = count / 2.0
    return ScriptVersion(
        script_version_id='sv-1',
        language='en',
        hook_intent='hook',
        thumbnail_transition='fade',
        segments=(
            ScriptSegment(
                segment_id='s1',
                order=0,
                text=text,
                claim_mode='transition',
                scene_intent='scene 1',
                source_refs=(),
                disclosure=None,
                word_count=count,
                estimated_seconds=est,
            ),
        ),
        pronunciation_hints=(),
        speech_rate=2.0,
        estimated_duration_seconds=est,
    )


def _selection(*, script_ref='sv-1'):
    base = CreativeAssetSelection(
        snapshot_ref='snap-1',
        script_ref=script_ref,
        angle_ref='angle-1',
        safety_policy_revision='safety-r1',
        music_sfx_policy_revision='ms-r1',
        preset_registry_revision='preset-reg-r1',
        visual_hook=ResourceRef(WS, 'visual_hook', 'vh-1', 'vh-r1'),
        audio_hook=ResourceRef(WS, 'audio_hook', 'ah-1', 'ah-r1'),
        thumbnail=ResourceRef(WS, 'thumbnail', 'th-1', 'th-r1'),
        thumbnail_overlay_intent='title card',
        assignments=(
            SceneAssignment(
                order=0,
                scene_id='sc-1',
                media_asset_id='m-1',
                rendition_ref='rend-1',
                artifact_version_ref='av-1',
                rationale='r1',
            ),
            SceneAssignment(
                order=1,
                scene_id='sc-2',
                media_asset_id='m-2',
                rendition_ref='rend-2',
                artifact_version_ref='av-2',
                rationale='r2',
            ),
        ),
        music_intents=(MappingProxyType({'cue': 'intro_pad', 'description': 'soft pad'}),),
        sfx_intents=(MappingProxyType({'cue': 'whoosh', 'description': 'short whoosh'}),),
        fallback_candidates=(
            FallbackCandidate(
                media_asset_id='m-3',
                rendition_ref='rend-3',
                artifact_version_ref='av-3',
                total_score=0.5,
            ),
        ),
        rationale='overall',
        score_components=MappingProxyType({}),
    )
    return dataclasses.replace(base, selection_fingerprint=base.compute_fingerprint())

def _visual(asset, start, end):
    return {
        'media_asset_id': asset,
        'start_ms': start,
        'end_ms': end,
        'crop_intent': 'center on subject',
        'overlay_intent': 'lower third',
        'effect_intent': 'slow push-in',
    }


def _raw():
    return {
        'timeline': {
            'segments': [
                {
                    'scene_id': 'sc-1',
                    'start_ms': 0,
                    'end_ms': 8000,
                    'transition_intent': 'hard cut',
                    'visuals': [_visual('m-1', 0, 8000)],
                },
                {
                    'scene_id': 'sc-2',
                    'start_ms': 8000,
                    'end_ms': 20000,
                    'transition_intent': 'cross dissolve',
                    'visuals': [_visual('m-2', 8000, 12000), _visual('m-1', 12000, 20000)],
                },
            ]
        },
        'hook_placement': {
            'hook_time_range': {'start_ms': 0, 'end_ms': 5000},
            'thumbnail_time_range': {'start_ms': 1200, 'end_ms': 2400},
        },
        'voice_profile_intent': {'direction': 'warm and confident', 'pace': 'steady', 'emotion': 'curious'},
        'music_cues': [{'cue': 'intro_pad', 'start_ms': 0, 'end_ms': 20000}],
        'sfx_cues': [{'cue': 'whoosh', 'start_ms': 7800, 'end_ms': 8200}],
        'subtitle_style_intent': {'style': 'bold white captions', 'karaoke': True, 'highlight_intent': 'active word turns yellow'},
        'allowed_fallbacks': [
            {'rule_id': 'fb-1', 'kind': 'replace_asset', 'scene_id': 'sc-2', 'replacement_media_asset_id': 'm-3'},
            {'rule_id': 'fb-2', 'kind': 'simplify_transition', 'scene_id': 'sc-1'},
        ],
        'output_metadata_requirement': 'english title, caption and 3-4 hashtags (CT-AI-009)',
    }


def _with(path, value, raw=None):
    data = _raw() if raw is None else copy.deepcopy(raw)
    node = data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return data


def _without(path):
    data = _raw()
    node = data
    for key in path[:-1]:
        node = node[key]
    del node[path[-1]]
    return data


def _build(raw=None, **overrides):
    kwargs = {
        'production_plan_id': 'plan-1',
        'script': _script(),
        'selection': _selection(),
        'preset_revision_ref': 'preset-rev-1',
    }
    kwargs.update(overrides)
    return build_production_plan(_raw() if raw is None else raw, **kwargs)


def _rejection(raw=None, **overrides):
    with pytest.raises(PlanRejected) as info:
        _build(raw, **overrides)
    err = info.value
    return (err.code, err.reason, err.field)


def test_module_and_test_docstrings_declare_covered_ids():
    for file_path in (pathlib.Path(__file__), MODULE_SOURCE):
        doc = ast.get_docstring(ast.parse(file_path.read_text(encoding='utf-8')))
        assert doc is not None
        assert 'coveredIds: CT-AI-007, CT-RND-003' in doc.splitlines()


def test_module_imports_stay_inside_allowlist():
    allowed = {
        '__future__',
        're',
        'collections.abc',
        'dataclasses',
        'types',
        'controlplane.application.idempotency.canonicalization',
        'creative.domain.asset_selection',
        'creative.domain.script',
    }
    for node in ast.walk(ast.parse(MODULE_SOURCE.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name in allowed
        elif isinstance(node, ast.ImportFrom):
            mod = '.' * node.level + (node.module or '')
            assert mod in allowed
    assert getattr(module, 'request_hash', None) is canonicalization.request_hash


def test_valid_plan_records_all_contract_fields():
    plan = _build()
    assert isinstance(plan, ProductionPlan)
    payload = plan.to_payload()
    assert set(payload) == {
        'production_plan_id',
        'script_version_id',
        'script_fingerprint',
        'preset_revision_ref',
        'selection_fingerprint',
        'timeline',
        'hook_placement',
        'thumbnail_overlay_intent',
        'voice_profile_intent',
        'music_cues',
        'sfx_cues',
        'subtitle_style_intent',
        'allowed_fallbacks',
        'output_metadata_ref',
        'output_metadata_requirement',
        'plan_fingerprint',
    }
    assert payload['script_version_id'] == 'sv-1'
    assert payload['script_fingerprint'] == _script().script_fingerprint
    assert payload['preset_revision_ref'] == 'preset-rev-1'
    assert payload['selection_fingerprint'] == _selection().selection_fingerprint
    assert payload['thumbnail_overlay_intent'] == 'title card'
    assert payload['timeline']['duration_ms'] == 20000
    segments = payload['timeline']['segments']
    assert len(segments) == 2
    assert segments[0]['order'] == 0
    assert segments[1]['order'] == 1
    v0 = segments[0]['visuals'][0]
    assert v0['rendition_ref'] == 'rend-1'
    assert v0['artifact_version_ref'] == 'av-1'
    v1_0 = segments[1]['visuals'][0]
    assert v1_0['rendition_ref'] == 'rend-2'
    assert v1_0['artifact_version_ref'] == 'av-2'
    assert payload['hook_placement']['visual_hook_ref'] == 'vh-1'
    assert payload['hook_placement']['audio_hook_ref'] == 'ah-1'
    assert payload['hook_placement']['thumbnail_ref'] == 'th-1'
    assert payload['hook_placement']['hook_time_range'] == {'start_ms': 0, 'end_ms': 5000}
    assert payload['hook_placement']['thumbnail_time_range'] == {'start_ms': 1200, 'end_ms': 2400}
    assert payload['voice_profile_intent']['pace'] == 'steady'
    assert payload['music_cues'][0]['description'] == 'soft pad'
    assert payload['sfx_cues'][0]['description'] == 'short whoosh'
    assert payload['subtitle_style_intent']['karaoke'] is True
    assert payload['allowed_fallbacks'][0]['replacement_rendition_ref'] == 'rend-3'
    assert payload['allowed_fallbacks'][0]['replacement_artifact_version_ref'] == 'av-3'
    assert payload['output_metadata_ref'] is None
    assert payload['output_metadata_requirement'] == _raw()['output_metadata_requirement']


def test_every_time_range_is_integer_ms_with_start_before_end():
    raw_10 = _with(
        ('sfx_cues',),
        [
            {'cue': 'whoosh', 'start_ms': 7800, 'end_ms': 8200},
            {'cue': 'whoosh', 'start_ms': 15000, 'end_ms': 15500},
        ],
    )
    plan = _build(raw_10)
    payload = plan.to_payload()
    count_ranges = 0

    def check(item):
        nonlocal count_ranges
        if isinstance(item, dict):
            for k, v in item.items():
                if k.endswith('_ms'):
                    assert isinstance(v, int) and not isinstance(v, bool)
            if 'start_ms' in item and 'end_ms' in item:
                assert item['start_ms'] < item['end_ms']
                count_ranges += 1
            for v in item.values():
                check(v)
        elif isinstance(item, list):
            for v in item:
                check(v)

    check(payload)
    assert count_ranges >= 10

def test_plan_is_frozen_and_isolated_from_input():
    raw = _raw()
    plan = _build(raw)
    before = plan.to_payload()
    raw['timeline']['segments'][0]['end_ms'] = 1
    raw['music_cues'].clear()
    assert plan.to_payload() == before

    assert ProductionPlan.__dataclass_params__.frozen is True
    with pytest.raises(dataclasses.FrozenInstanceError):
        plan.preset_revision_ref = 'x'
    assert isinstance(plan.timeline, MappingProxyType)
    with pytest.raises(TypeError):
        plan.timeline['x'] = 1
    assert isinstance(plan.music_cues, tuple)

    payload = plan.to_payload()
    assert type(payload['timeline']) is dict
    assert type(payload['music_cues']) is list
    json.dumps(payload)
    payload['timeline']['duration_ms'] = 1
    assert plan.to_payload() != payload
    assert plan.to_payload() == before


def test_fingerprint_is_sha256_over_content():
    plan = _build()
    assert re.fullmatch(r'[0-9a-f]{64}', plan.plan_fingerprint)
    expected_hash = hashlib.sha256(
        json.dumps(plan.fingerprint_basis(), sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    ).hexdigest()
    assert plan.plan_fingerprint == plan.compute_fingerprint() == canonicalization.request_hash(plan.fingerprint_basis()) == expected_hash
    basis = plan.fingerprint_basis()
    assert 'production_plan_id' not in basis
    assert 'plan_fingerprint' not in basis
    assert 'script_fingerprint' in basis
    assert 'preset_revision_ref' in basis
    assert 'timeline' in basis
    assert 'hook_placement' in basis
    assert 'allowed_fallbacks' in basis


def test_fingerprint_ignores_plan_id_and_key_order():
    plan = _build()
    assert _build(production_plan_id='plan-2').plan_fingerprint == plan.plan_fingerprint
    reversed_raw = dict(reversed(list(_raw().items())))
    assert _build(raw=reversed_raw).plan_fingerprint == plan.plan_fingerprint


@pytest.mark.parametrize(
    'path, value',
    [
        (('hook_placement', 'thumbnail_time_range', 'end_ms'), 2500),
        (('timeline', 'segments', 0, 'transition_intent'), 'wipe'),
        (('timeline', 'segments', 0, 'visuals', 0, 'crop_intent'), 'tight crop'),
        (('voice_profile_intent', 'emotion'), 'urgent'),
        (('music_cues', 0, 'end_ms'), 19000),
        (('sfx_cues', 0, 'start_ms'), 7000),
        (('subtitle_style_intent', 'karaoke'), False),
        (('allowed_fallbacks', 1, 'kind'), 'drop_overlay_effect'),
        (('output_metadata_requirement',), 'a different requirement'),
    ],
)
def test_fingerprint_changes_with_any_planned_content(path, value):
    assert _build(_with(path, value)).plan_fingerprint != _build().plan_fingerprint


def test_fingerprint_changes_with_external_context():
    plan = _build()
    assert _build(preset_revision_ref='preset-rev-2').plan_fingerprint != plan.plan_fingerprint
    other_script = _script('Different words here')
    diff_script_plan = _build(script=other_script, selection=_selection(script_ref=other_script.script_version_id))
    assert diff_script_plan.plan_fingerprint != plan.plan_fingerprint
    assert diff_script_plan.to_payload()['script_fingerprint'] == other_script.script_fingerprint
    raw_ref = _without(('output_metadata_requirement',))
    raw_ref['output_metadata_ref'] = 'meta-rev-1'
    assert _build(raw=raw_ref).plan_fingerprint != plan.plan_fingerprint


P = 'timeline.segments'
SEG = ('timeline', 'segments')


@pytest.mark.parametrize(
    'path, value, expected',
    [
        (SEG + (0, 'end_ms'), 8000.5, (SCHEMA_VIOLATION, 'wrong_type', P + '[0].end_ms')),
        (SEG + (0, 'start_ms'), True, (SCHEMA_VIOLATION, 'wrong_type', P + '[0].start_ms')),
        (SEG + (0, 'start_ms'), '0', (SCHEMA_VIOLATION, 'wrong_type', P + '[0].start_ms')),
        (SEG + (0, 'end_ms'), 0, (INVALID_TIME_RANGE, 'start_not_before_end', P + '[0]')),
        (SEG + (0, 'end_ms'), -5, (INVALID_TIME_RANGE, 'negative_ms', P + '[0].end_ms')),
        (SEG + (1, 'start_ms'), 9000, (TIMELINE_GAP, 'scene_gap', P + '[1].start_ms')),
        (SEG + (1, 'start_ms'), 7000, (INVALID_TIME_RANGE, 'scene_overlap', P + '[1].start_ms')),
        (SEG + (0, 'start_ms'), 100, (INVALID_TIME_RANGE, 'timeline_not_from_zero', P + '[0].start_ms')),
        (SEG + (0, 'visuals'), [], (TIMELINE_GAP, 'visual_missing', P + '[0].visuals')),
        (SEG + (0, 'visuals', 0, 'end_ms'), 6000, (TIMELINE_GAP, 'visual_missing', P + '[0].visuals')),
        (SEG + (1, 'visuals', 0, 'start_ms'), 9000, (TIMELINE_GAP, 'visual_missing', P + '[1].visuals')),
        (SEG + (1, 'visuals', 1, 'start_ms'), 13000, (TIMELINE_GAP, 'visual_missing', P + '[1].visuals')),
        (SEG + (0, 'visuals', 0, 'end_ms'), 8500, (INVALID_TIME_RANGE, 'outside_scene', P + '[0].visuals[0]')),
        (SEG + (1, 'scene_id'), 'sc-1', (SCHEMA_VIOLATION, 'duplicate_id', P + '[1].scene_id')),
        (SEG + (1, 'scene_id'), 'sc-9', (HALLUCINATED_REF, 'scene_mismatch', P)),
        (SEG + (0, 'visuals', 0, 'crop_intent'), '', (SCHEMA_VIOLATION, 'empty_value', P + '[0].visuals[0].crop_intent')),
        (('timeline', 'segments'), [], (SCHEMA_VIOLATION, 'empty_value', P)),
        (('timeline',), 'x', (SCHEMA_VIOLATION, 'wrong_type', 'timeline')),
        (SEG, ['x'], (SCHEMA_VIOLATION, 'wrong_type', P + '[0]')),
    ],
)
def test_timeline_rejections(path, value, expected):
    assert _rejection(_with(path, value)) == expected


def test_timeline_missing_visuals():
    assert _rejection(_without(SEG + (0, 'visuals'))) == (SCHEMA_VIOLATION, 'missing_required', P + '[0].visuals')


def test_visual_asset_must_come_from_selection():
    for asset in ('m-99', 'm-3'):
        assert _rejection(_with(SEG + (0, 'visuals', 0, 'media_asset_id'), asset)) == (
            HALLUCINATED_REF,
            'asset_not_in_selection',
            P + '[0].visuals[0].media_asset_id',
        )


def test_overlapping_visuals_are_accepted_when_they_cover_scene():
    assert _build(_with(SEG + (1, 'visuals', 0, 'end_ms'), 13000)) is not None


def test_duration_is_derived_from_last_scene_not_a_constant():
    raw = _with(SEG + (1, 'end_ms'), 30000)
    raw = _with(SEG + (1, 'visuals', 1, 'end_ms'), 30000, raw=raw)
    assert _build(raw).to_payload()['timeline']['duration_ms'] == 30000
    assert _build().to_payload()['timeline']['duration_ms'] == 20000

def _hook(hook, thumb):
    return _with(
        ('hook_placement',),
        {
            'hook_time_range': {'start_ms': hook[0], 'end_ms': hook[1]},
            'thumbnail_time_range': {'start_ms': thumb[0], 'end_ms': thumb[1]},
        },
    )


@pytest.mark.parametrize(
    'hook, thumb',
    [
        ((0, 5000), (1200, 2400)),
        ((2000, 6000), (3500, 4500)),
        ((0, 5000), (0, 5000)),
        ((4000, 9000), (8000, 9000)),
        ((0, 12000), (9000, 11000)),
    ],
)
def test_thumbnail_inside_hook_is_accepted(hook, thumb):
    plan = _build(_hook(hook, thumb))
    assert plan is not None
    payload = plan.to_payload()
    assert payload['hook_placement']['hook_time_range'] == {'start_ms': hook[0], 'end_ms': hook[1]}
    assert payload['hook_placement']['thumbnail_time_range'] == {'start_ms': thumb[0], 'end_ms': thumb[1]}


@pytest.mark.parametrize(
    'hook, thumb',
    [
        ((0, 5000), (5000, 5500)),
        ((0, 5000), (4500, 5500)),
        ((2000, 6000), (1000, 2500)),
        ((2000, 6000), (500, 1500)),
        ((0, 3000), (3000, 3500)),
        ((4000, 9000), (0, 3000)),
    ],
)
def test_thumbnail_outside_hook_is_rejected(hook, thumb):
    assert _rejection(_hook(hook, thumb)) == (
        INVALID_HOOK_PLACEMENT,
        'thumbnail_outside_hook',
        'hook_placement.thumbnail_time_range',
    )


def test_hook_must_stay_inside_timeline():
    assert _rejection(_hook((0, 20001), (1000, 2000))) == (
        INVALID_HOOK_PLACEMENT,
        'hook_outside_timeline',
        'hook_placement.hook_time_range',
    )


def test_hook_time_range_shape_errors():
    assert _rejection(_hook((0, 5000), (2000, 2000))) == (
        INVALID_TIME_RANGE,
        'start_not_before_end',
        'hook_placement.thumbnail_time_range',
    )
    assert _rejection(_with(('hook_placement', 'hook_time_range', 'start_ms'), 1.5)) == (
        SCHEMA_VIOLATION,
        'wrong_type',
        'hook_placement.hook_time_range.start_ms',
    )
    assert _rejection(_without(('hook_placement', 'thumbnail_time_range'))) == (
        SCHEMA_VIOLATION,
        'missing_required',
        'hook_placement.thumbnail_time_range',
    )
    assert _rejection(_without(('hook_placement',))) == (
        SCHEMA_VIOLATION,
        'missing_required',
        'hook_placement',
    )
    assert _rejection(_with(('hook_placement', 'visual_hook_ref'), 'vh-9')) == (
        SCHEMA_VIOLATION,
        'unknown_field',
        'hook_placement.visual_hook_ref',
    )


def test_module_has_no_hardcoded_three_second_hook():
    src = MODULE_SOURCE.read_text(encoding='utf-8')
    assert re.search(r'\b3_?000\b', src) is None


@pytest.mark.parametrize(
    'path, key, expected_field',
    [
        (('timeline', 'segments', 0, 'visuals', 0), 'shell_command', 'timeline.segments[0].visuals[0].shell_command'),
        (('allowed_fallbacks', 0), 'arbitrary_url', 'allowed_fallbacks[0].arbitrary_url'),
        ((), 'shell_command', 'shell_command'),
        ((), 'Shell_Command', 'Shell_Command'),
        (('hook_placement',), 'url', 'hook_placement.url'),
        (('voice_profile_intent',), 'path', 'voice_profile_intent.path'),
        (('subtitle_style_intent',), 'command', 'subtitle_style_intent.command'),
    ],
)
def test_forbidden_field_names_are_rejected(path, key, expected_field):
    raw = _raw()
    node = raw
    for p in path:
        node = node[p]
    node[key] = 'ffmpeg -i x'
    assert _rejection(raw) == (FORBIDDEN_CONTENT, 'forbidden_field', expected_field)


@pytest.mark.parametrize(
    'value',
    [
        'https://example.com/x.png',
        'ftp://h/x',
        'file:///tmp/a',
        'C:' + chr(92) + 'media' + chr(92) + 'a.mp4',
        '/etc/passwd',
        chr(46) * 2 + chr(92) + 'secret.txt',
        'a/../b',
        '~/clip.mp4',
    ],
)
def test_forbidden_values_are_rejected(value):
    seg0 = ('timeline', 'segments', 0, 'visuals', 0, 'crop_intent')
    assert _rejection(_with(seg0, value)) == (
        FORBIDDEN_CONTENT,
        'forbidden_value',
        'timeline.segments[0].visuals[0].crop_intent',
    )
    assert _rejection(_with(('output_metadata_requirement',), value)) == (
        FORBIDDEN_CONTENT,
        'forbidden_value',
        'output_metadata_requirement',
    )
    assert _rejection(_with(('voice_profile_intent', 'direction'), value)) == (
        FORBIDDEN_CONTENT,
        'forbidden_value',
        'voice_profile_intent.direction',
    )


def test_benign_intent_text_is_accepted():
    seg0 = ('timeline', 'segments', 0, 'visuals', 0, 'crop_intent')
    for text in ('center 16:9 frame', 'zoom in/out slowly', 'cut at 1.5x speed', 'wait.. then fade'):
        assert _build(_with(seg0, text)) is not None


def test_forbidden_scan_runs_before_schema_checks():
    raw = _with(('timeline',), 'x')
    raw['shell_command'] = 'echo 1'
    assert _rejection(raw) == (FORBIDDEN_CONTENT, 'forbidden_field', 'shell_command')


def test_unknown_fields_are_rejected():
    assert _rejection(_with(('extra',), 1)) == (SCHEMA_VIOLATION, 'unknown_field', 'extra')
    seg0_rend = ('timeline', 'segments', 0, 'visuals', 0, 'rendition_ref')
    assert _rejection(_with(seg0_rend, 'rend-9')) == (
        SCHEMA_VIOLATION,
        'unknown_field',
        'timeline.segments[0].visuals[0].rendition_ref',
    )


def test_binding_fixture_invalid_case_is_rejected_like_binding():
    case = _fixture_invalid('ai_supplied_shell_command')
    raw = _raw()
    raw[case['expected_error']['field']] = case['payload'][case['expected_error']['field']]
    assert _rejection(raw) == (FORBIDDEN_CONTENT, 'forbidden_field', case['expected_error']['field'])


def test_rendered_payload_has_no_forbidden_key_or_location_string():
    payload = _build().to_payload()
    uri_re = re.compile(r'://')

    def check(item):
        if isinstance(item, dict):
            for k, v in item.items():
                assert k.casefold() not in FORBIDDEN_FIELDS
                check(v)
        elif isinstance(item, list):
            for v in item:
                check(v)
        elif isinstance(item, str):
            assert not uri_re.search(item)
            assert not item.startswith('/')

    check(payload)

def test_context_rejections():
    assert _rejection(script=None) == (INPUT_NOT_READY, 'missing_script_version', 'script')
    assert _rejection(selection=None) == (INPUT_NOT_READY, 'missing_asset_selection', 'selection')
    assert _rejection(preset_revision_ref=None) == (INPUT_NOT_READY, 'missing_preset_revision_ref', 'preset_revision_ref')
    assert _rejection(preset_revision_ref='') == (INPUT_NOT_READY, 'missing_preset_revision_ref', 'preset_revision_ref')
    assert _rejection(production_plan_id='') == (INPUT_NOT_READY, 'missing_production_plan_id', 'production_plan_id')
    assert _rejection(selection=_selection(script_ref='other')) == (CONTEXT_MISMATCH, 'script_ref_mismatch', 'selection.script_ref')


@pytest.mark.parametrize('bad_raw', [[], None, 'x'])
def test_raw_must_be_mapping(bad_raw):
    with pytest.raises(PlanRejected) as info:
        build_production_plan(
            bad_raw,
            production_plan_id='plan-1',
            script=_script(),
            selection=_selection(),
            preset_revision_ref='preset-rev-1',
        )
    err = info.value
    assert (err.code, err.reason, err.field) == (SCHEMA_VIOLATION, 'wrong_type', '$')


@pytest.mark.parametrize(
    'key',
    [
        'timeline',
        'hook_placement',
        'voice_profile_intent',
        'music_cues',
        'sfx_cues',
        'subtitle_style_intent',
        'allowed_fallbacks',
    ],
)
def test_each_required_top_level_field_is_required(key):
    assert _rejection(_without((key,))) == (SCHEMA_VIOLATION, 'missing_required', key)


def test_text_object_and_subtitle_rules():
    assert _rejection(_without(('voice_profile_intent', 'pace'))) == (
        SCHEMA_VIOLATION,
        'missing_required',
        'voice_profile_intent.pace',
    )
    assert _rejection(_with(('voice_profile_intent', 'voice_file'), 'x')) == (
        SCHEMA_VIOLATION,
        'unknown_field',
        'voice_profile_intent.voice_file',
    )
    assert _rejection(_with(('subtitle_style_intent', 'karaoke'), 'yes')) == (
        SCHEMA_VIOLATION,
        'wrong_type',
        'subtitle_style_intent.karaoke',
    )


def test_cues_must_match_selection_and_timeline():
    assert _rejection(_with(('music_cues', 0, 'cue'), 'unknown')) == (
        HALLUCINATED_REF,
        'cue_not_in_selection',
        'music_cues[0].cue',
    )
    assert _rejection(_with(('sfx_cues', 0, 'cue'), 'intro_pad')) == (
        HALLUCINATED_REF,
        'cue_not_in_selection',
        'sfx_cues[0].cue',
    )
    assert _rejection(_with(('music_cues', 0, 'end_ms'), 20001)) == (
        INVALID_TIME_RANGE,
        'outside_timeline',
        'music_cues[0]',
    )
    assert _rejection(_with(('sfx_cues', 0, 'end_ms'), 7800)) == (
        INVALID_TIME_RANGE,
        'start_not_before_end',
        'sfx_cues[0]',
    )
    empty_cues_raw = _with(('music_cues',), [])
    empty_cues_raw = _with(('sfx_cues',), [], raw=empty_cues_raw)
    plan = _build(empty_cues_raw)
    assert plan.to_payload()['music_cues'] == []
    assert plan.to_payload()['sfx_cues'] == []


def test_fallback_rules():
    assert _rejection(_with(('allowed_fallbacks', 0, 'kind'), 'run_shell')) == (
        SCHEMA_VIOLATION,
        'enum_violation',
        'allowed_fallbacks[0].kind',
    )
    assert _rejection(_with(('allowed_fallbacks', 0, 'scene_id'), 'sc-9')) == (
        HALLUCINATED_REF,
        'scene_mismatch',
        'allowed_fallbacks[0].scene_id',
    )
    assert _rejection(_with(('allowed_fallbacks', 0, 'replacement_media_asset_id'), 'm-1')) == (
        HALLUCINATED_REF,
        'fallback_not_in_selection',
        'allowed_fallbacks[0].replacement_media_asset_id',
    )
    assert _rejection(_without(('allowed_fallbacks', 0, 'replacement_media_asset_id'))) == (
        SCHEMA_VIOLATION,
        'missing_required',
        'allowed_fallbacks[0].replacement_media_asset_id',
    )
    assert _rejection(_with(('allowed_fallbacks', 1, 'replacement_media_asset_id'), 'm-3')) == (
        SCHEMA_VIOLATION,
        'unknown_field',
        'allowed_fallbacks[1].replacement_media_asset_id',
    )
    assert _rejection(_with(('allowed_fallbacks', 1, 'rule_id'), 'fb-1')) == (
        SCHEMA_VIOLATION,
        'duplicate_id',
        'allowed_fallbacks[1].rule_id',
    )
    assert _build(_with(('allowed_fallbacks',), [])).to_payload()['allowed_fallbacks'] == []
    assert set(FALLBACK_KINDS) == {'replace_asset', 'drop_overlay_effect', 'simplify_transition'}


def test_output_metadata_exactly_one_of_ref_or_requirement():
    assert _rejection(_with(('output_metadata_ref',), 'meta-rev-1')) == (
        SCHEMA_VIOLATION,
        'exactly_one_required',
        'output_metadata',
    )
    assert _rejection(_without(('output_metadata_requirement',))) == (
        SCHEMA_VIOLATION,
        'exactly_one_required',
        'output_metadata',
    )
    raw_ref = _without(('output_metadata_requirement',))
    raw_ref['output_metadata_ref'] = 'meta-rev-1'
    plan = _build(raw_ref)
    assert plan.to_payload()['output_metadata_ref'] == 'meta-rev-1'
    assert plan.to_payload()['output_metadata_requirement'] is None


def test_binding_constants_match_binding():
    assert BINDING_ENTITY == 'RenderPackage'
    expected_names = {'production_plan_ref', 'script_version_ref', 'hook_placement', 'timeline', 'allowed_fallbacks'}
    assert set(RENDER_PACKAGE_INPUT_TYPES) == expected_names
    assert dict(RENDER_PACKAGE_INPUT_TYPES) == {n: t for n, t in _binding_types().items() if n in expected_names}
    entity_fields = {f['name']: f for f in _binding_entity()['fields']}
    for name in expected_names:
        assert entity_fields[name]['required'] is True
    assert set(_binding_entity()['forbidden_fields']) <= set(FORBIDDEN_FIELDS)


def test_drift_comparison_detects_mutated_binding():
    def derive(fields):
        return {f['name']: f['type'] for f in fields if f['name'] in RENDER_PACKAGE_INPUT_TYPES}

    base_fields = _binding_entity()['fields']
    assert derive(base_fields) == dict(RENDER_PACKAGE_INPUT_TYPES)

    mutated1 = copy.deepcopy(base_fields)
    for f in mutated1:
        if f['name'] == 'hook_placement':
            f['type'] = 'array'
    assert derive(mutated1) != dict(RENDER_PACKAGE_INPUT_TYPES)

    mutated2 = copy.deepcopy(base_fields)
    for f in mutated2:
        if f['name'] == 'allowed_fallbacks':
            f['type'] = 'object'
    assert derive(mutated2) != dict(RENDER_PACKAGE_INPUT_TYPES)

    mutated3 = [f for f in copy.deepcopy(base_fields) if f['name'] != 'timeline']
    assert derive(mutated3) != dict(RENDER_PACKAGE_INPUT_TYPES)


def test_to_render_package_inputs_matches_binding_field_types():
    plan = _build()
    out = plan.to_render_package_inputs()
    assert set(out) == set(RENDER_PACKAGE_INPUT_TYPES)
    for name, expected_type in RENDER_PACKAGE_INPUT_TYPES.items():
        val = out[name]
        if expected_type == 'string':
            assert isinstance(val, str) and val.strip() != ''
        elif expected_type == 'object':
            assert type(val) is dict
        elif expected_type == 'array':
            assert type(val) is list
    assert out['production_plan_ref'] == 'plan-1'
    assert out['script_version_ref'] == 'sv-1'
    assert isinstance(out['timeline']['segments'], list)
    assert len(out['timeline']['segments']) == 2
    assert out['allowed_fallbacks'] == plan.to_payload()['allowed_fallbacks']
    json.dumps(out)
    out['timeline']['segments'].clear()
    out['hook_placement']['x'] = 1
    out2 = plan.to_render_package_inputs()
    assert len(out2['timeline']['segments']) == 2
    assert 'x' not in out2['hook_placement']


def test_hook_placement_has_same_shape_as_binding_fixture():
    fx = _fixture_valid()
    out = _build().to_render_package_inputs()
    assert set(out['hook_placement']) == set(fx['hook_placement'])
    for k in out['hook_placement']:
        assert type(out['hook_placement'][k]) is type(fx['hook_placement'][k])
    assert set(out['hook_placement']['hook_time_range']) == set(fx['hook_placement']['hook_time_range'])
    assert set(out['hook_placement']['thumbnail_time_range']) == set(fx['hook_placement']['thumbnail_time_range'])
    assert isinstance(fx['timeline'], dict)
    assert 'segments' in out['timeline']
    assert isinstance(out['timeline']['segments'], list)
    assert isinstance(fx['allowed_fallbacks'], list)


def test_no_forbidden_field_in_render_package_inputs():
    out = _build().to_render_package_inputs()
    assert not (set(out) & set(FORBIDDEN_FIELDS))

    def check_keys(item):
        if isinstance(item, dict):
            for k, v in item.items():
                assert k.casefold() not in FORBIDDEN_FIELDS
                check_keys(v)
        elif isinstance(item, list):
            for v in item:
                check_keys(v)

    check_keys(out)
