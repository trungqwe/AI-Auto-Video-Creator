"""ProductionPlan (CT-AI-007) và đầu vào RenderPackage (CT-RND-003) phía D.

coveredIds: CT-AI-007, CT-RND-003
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType

from controlplane.application.idempotency.canonicalization import request_hash
from creative.domain.asset_selection import CreativeAssetSelection
from creative.domain.script import ScriptVersion

INPUT_NOT_READY = 'INPUT_NOT_READY'
SCHEMA_VIOLATION = 'plan_schema_violation'
FORBIDDEN_CONTENT = 'forbidden_content'
INVALID_TIME_RANGE = 'invalid_time_range'
TIMELINE_GAP = 'timeline_gap'
INVALID_HOOK_PLACEMENT = 'invalid_hook_placement'
HALLUCINATED_REF = 'hallucinated_ref'
CONTEXT_MISMATCH = 'plan_context_mismatch'
BINDING_ENTITY = 'RenderPackage'
RENDER_PACKAGE_INPUT_TYPES = MappingProxyType({
    'production_plan_ref': 'string',
    'script_version_ref': 'string',
    'hook_placement': 'object',
    'timeline': 'object',
    'allowed_fallbacks': 'array',
})
FORBIDDEN_FIELDS = ('shell_command', 'arbitrary_url', 'url', 'uri', 'command', 'path', 'file_path')
FALLBACK_REPLACE_ASSET = 'replace_asset'
FALLBACK_KINDS = (FALLBACK_REPLACE_ASSET, 'drop_overlay_effect', 'simplify_transition')
_SCENE_KEYS = ('scene_id', 'start_ms', 'end_ms', 'transition_intent', 'visuals')
_VISUAL_KEYS = ('media_asset_id', 'start_ms', 'end_ms', 'crop_intent', 'overlay_intent', 'effect_intent')
_TOP_REQUIRED = ('timeline', 'hook_placement', 'voice_profile_intent', 'music_cues', 'sfx_cues', 'subtitle_style_intent', 'allowed_fallbacks')
_TOP_OPTIONAL = ('output_metadata_ref', 'output_metadata_requirement')
_FORBIDDEN_VALUE = re.compile(
    r'[A-Za-z][A-Za-z0-9+.-]*://'
    r'|^(?:[A-Za-z]:[\x5c/]|[\x5c/]|~[\x5c/]|[.]{1,2}[\x5c/])'
    r'|(?:^|[\x5c/])[.][.](?:[\x5c/]|$)'
)


class PlanRejected(Exception):
    def __init__(self, code: str, reason: str, field: str = '') -> None:
        super().__init__(f'{code}: {reason}' + (f' ({field})' if field else ''))
        self.code = code
        self.reason = reason
        self.field = field


def _reject(code: str, reason: str, field: str = '') -> None:
    raise PlanRejected(code, reason, field)


def _join(path: str, key: str) -> str:
    return key if not path else f'{path}.{key}'


def _item(path: str, index: int) -> str:
    return f'{path}[{index}]'


def _freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value):
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw(item) for item in value]
    return value


def _scan_intent_only(value, path: str = '') -> None:
    """Từ chối khoá shell_command/arbitrary_url/url/path... và giá trị chuỗi là URL hoặc đường dẫn tệp ở mọi vị trí lồng."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                _reject(SCHEMA_VIOLATION, 'wrong_type', path or '$')
            if key.casefold() in FORBIDDEN_FIELDS:
                _reject(FORBIDDEN_CONTENT, 'forbidden_field', _join(path, key))
            _scan_intent_only(item, _join(path, key))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _scan_intent_only(item, _item(path, index))
    elif isinstance(value, str) and _FORBIDDEN_VALUE.search(value.strip()):
        _reject(FORBIDDEN_CONTENT, 'forbidden_value', path or '$')


def _mapping(value, path: str) -> Mapping:
    if not isinstance(value, Mapping):
        _reject(SCHEMA_VIOLATION, 'wrong_type', path)
    return value


def _check_keys(source, required, optional, path: str) -> Mapping:
    source = _mapping(source, path or '$')
    for name in required:
        if name not in source:
            _reject(SCHEMA_VIOLATION, 'missing_required', _join(path, name))
    for name in source:
        if name not in required and name not in optional:
            _reject(SCHEMA_VIOLATION, 'unknown_field', _join(path, name))
    return source


def _text(source: Mapping, key: str, path: str) -> str:
    value = source[key]
    if not isinstance(value, str):
        _reject(SCHEMA_VIOLATION, 'wrong_type', _join(path, key))
    if not value.strip():
        _reject(SCHEMA_VIOLATION, 'empty_value', _join(path, key))
    return value


def _flag(source: Mapping, key: str, path: str) -> bool:
    value = source[key]
    if not isinstance(value, bool):
        _reject(SCHEMA_VIOLATION, 'wrong_type', _join(path, key))
    return value


def _list(source: Mapping, key: str, path: str) -> list:
    value = source[key]
    if not isinstance(value, list):
        _reject(SCHEMA_VIOLATION, 'wrong_type', _join(path, key))
    return value


def _ms(source: Mapping, key: str, path: str) -> int:
    value = source[key]
    if isinstance(value, bool) or not isinstance(value, int):
        _reject(SCHEMA_VIOLATION, 'wrong_type', _join(path, key))
    if value < 0:
        _reject(INVALID_TIME_RANGE, 'negative_ms', _join(path, key))
    return value


def _range(source: Mapping, path: str) -> tuple[int, int]:
    """Đọc start_ms/end_ms nguyên (ms); bắt buộc start < end."""
    start = _ms(source, 'start_ms', path)
    end = _ms(source, 'end_ms', path)
    if start >= end:
        _reject(INVALID_TIME_RANGE, 'start_not_before_end', path)
    return start, end


def _range_object(value, path: str) -> dict[str, int]:
    source = _check_keys(value, ('start_ms', 'end_ms'), (), path)
    start, end = _range(source, path)
    return {'start_ms': start, 'end_ms': end}


def _parse_visuals(value, scene_path: str, scene_start: int, scene_end: int, assigned: Mapping) -> list[dict[str, object]]:
    path = _join(scene_path, 'visuals')
    if not isinstance(value, list):
        _reject(SCHEMA_VIOLATION, 'wrong_type', path)
    if not value:
        _reject(TIMELINE_GAP, 'visual_missing', path)
    visuals: list[dict[str, object]] = []
    for index, item in enumerate(value):
        vpath = _item(path, index)
        item = _check_keys(item, _VISUAL_KEYS, (), vpath)
        asset_id = _text(item, 'media_asset_id', vpath)
        assignment = assigned.get(asset_id)
        if assignment is None:
            _reject(HALLUCINATED_REF, 'asset_not_in_selection', _join(vpath, 'media_asset_id'))
        start, end = _range(item, vpath)
        if start < scene_start or end > scene_end:
            _reject(INVALID_TIME_RANGE, 'outside_scene', vpath)
        visuals.append({
            'media_asset_id': asset_id, 'rendition_ref': assignment.rendition_ref,
            'artifact_version_ref': assignment.artifact_version_ref, 'start_ms': start, 'end_ms': end,
            'crop_intent': _text(item, 'crop_intent', vpath), 'overlay_intent': _text(item, 'overlay_intent', vpath),
            'effect_intent': _text(item, 'effect_intent', vpath),
        })
    cursor = scene_start
    for visual in sorted(visuals, key=lambda v: (v['start_ms'], v['end_ms'])):
        if visual['start_ms'] > cursor:
            _reject(TIMELINE_GAP, 'visual_missing', path)
        cursor = max(cursor, visual['end_ms'])
    if cursor < scene_end:
        _reject(TIMELINE_GAP, 'visual_missing', path)
    return visuals


def _parse_timeline(raw, selection: CreativeAssetSelection) -> dict[str, object]:
    timeline = _check_keys(raw, ('segments',), (), 'timeline')
    scenes = _list(timeline, 'segments', 'timeline')
    if not scenes:
        _reject(SCHEMA_VIOLATION, 'empty_value', 'timeline.segments')
    assigned = {a.media_asset_id: a for a in selection.assignments}
    seen: set[str] = set()
    parsed: list[dict[str, object]] = []
    cursor = 0
    for index, scene in enumerate(scenes):
        path = _item('timeline.segments', index)
        scene = _check_keys(scene, _SCENE_KEYS, (), path)
        scene_id = _text(scene, 'scene_id', path)
        if scene_id in seen:
            _reject(SCHEMA_VIOLATION, 'duplicate_id', _join(path, 'scene_id'))
        seen.add(scene_id)
        start, end = _range(scene, path)
        if index == 0 and start != 0:
            _reject(INVALID_TIME_RANGE, 'timeline_not_from_zero', _join(path, 'start_ms'))
        if index > 0 and start > cursor:
            _reject(TIMELINE_GAP, 'scene_gap', _join(path, 'start_ms'))
        if index > 0 and start < cursor:
            _reject(INVALID_TIME_RANGE, 'scene_overlap', _join(path, 'start_ms'))
        transition = _text(scene, 'transition_intent', path)
        visuals = _parse_visuals(scene['visuals'], path, start, end, assigned)
        parsed.append({'scene_id': scene_id, 'order': index, 'start_ms': start, 'end_ms': end,
                       'transition_intent': transition, 'visuals': visuals})
        cursor = end
    if [s['scene_id'] for s in parsed] != [a.scene_id for a in selection.assignments]:
        _reject(HALLUCINATED_REF, 'scene_mismatch', 'timeline.segments')
    return {'duration_ms': cursor, 'segments': parsed}

def _parse_hook_placement(raw, selection: CreativeAssetSelection, duration_ms: int) -> dict[str, object]:
    source = _check_keys(raw, ('hook_time_range', 'thumbnail_time_range'), (), 'hook_placement')
    hook = _range_object(source['hook_time_range'], 'hook_placement.hook_time_range')
    thumbnail = _range_object(source['thumbnail_time_range'], 'hook_placement.thumbnail_time_range')
    if hook['end_ms'] > duration_ms:
        _reject(INVALID_HOOK_PLACEMENT, 'hook_outside_timeline', 'hook_placement.hook_time_range')
    if thumbnail['start_ms'] < hook['start_ms'] or thumbnail['end_ms'] > hook['end_ms']:
        _reject(INVALID_HOOK_PLACEMENT, 'thumbnail_outside_hook', 'hook_placement.thumbnail_time_range')
    return {
        'visual_hook_ref': selection.visual_hook.ref_id, 'audio_hook_ref': selection.audio_hook.ref_id,
        'thumbnail_ref': selection.thumbnail.ref_id, 'hook_time_range': hook, 'thumbnail_time_range': thumbnail,
    }


def _parse_text_object(value, keys: tuple[str, ...], path: str) -> dict[str, str]:
    source = _check_keys(value, keys, (), path)
    return {key: _text(source, key, path) for key in keys}


def _parse_subtitle(value) -> dict[str, object]:
    path = 'subtitle_style_intent'
    source = _check_keys(value, ('style', 'karaoke', 'highlight_intent'), (), path)
    return {'style': _text(source, 'style', path), 'karaoke': _flag(source, 'karaoke', path),
            'highlight_intent': _text(source, 'highlight_intent', path)}


def _parse_cues(value, field: str, intents, duration_ms: int) -> list[dict[str, object]]:
    if not isinstance(value, list):
        _reject(SCHEMA_VIOLATION, 'wrong_type', field)
    known = {intent['cue']: intent['description'] for intent in intents}
    cues: list[dict[str, object]] = []
    for index, item in enumerate(value):
        path = _item(field, index)
        item = _check_keys(item, ('cue', 'start_ms', 'end_ms'), (), path)
        cue = _text(item, 'cue', path)
        if cue not in known:
            _reject(HALLUCINATED_REF, 'cue_not_in_selection', _join(path, 'cue'))
        start, end = _range(item, path)
        if end > duration_ms:
            _reject(INVALID_TIME_RANGE, 'outside_timeline', path)
        cues.append({'cue': cue, 'description': known[cue], 'start_ms': start, 'end_ms': end})
    return cues


def _parse_fallbacks(value, scene_ids: set[str], selection: CreativeAssetSelection) -> list[dict[str, object]]:
    if not isinstance(value, list):
        _reject(SCHEMA_VIOLATION, 'wrong_type', 'allowed_fallbacks')
    replacements = {c.media_asset_id: c for c in selection.fallback_candidates}
    seen: set[str] = set()
    rules: list[dict[str, object]] = []
    for index, item in enumerate(value):
        path = _item('allowed_fallbacks', index)
        item = _check_keys(item, ('rule_id', 'kind', 'scene_id'), ('replacement_media_asset_id',), path)
        rule_id = _text(item, 'rule_id', path)
        if rule_id in seen:
            _reject(SCHEMA_VIOLATION, 'duplicate_id', _join(path, 'rule_id'))
        seen.add(rule_id)
        kind = _text(item, 'kind', path)
        if kind not in FALLBACK_KINDS:
            _reject(SCHEMA_VIOLATION, 'enum_violation', _join(path, 'kind'))
        scene_id = _text(item, 'scene_id', path)
        if scene_id not in scene_ids:
            _reject(HALLUCINATED_REF, 'scene_mismatch', _join(path, 'scene_id'))
        rule: dict[str, object] = {'rule_id': rule_id, 'kind': kind, 'scene_id': scene_id}
        has_replacement = 'replacement_media_asset_id' in item
        if kind == FALLBACK_REPLACE_ASSET:
            if not has_replacement:
                _reject(SCHEMA_VIOLATION, 'missing_required', _join(path, 'replacement_media_asset_id'))
            asset_id = _text(item, 'replacement_media_asset_id', path)
            candidate = replacements.get(asset_id)
            if candidate is None:
                _reject(HALLUCINATED_REF, 'fallback_not_in_selection', _join(path, 'replacement_media_asset_id'))
            rule['replacement_media_asset_id'] = asset_id
            rule['replacement_rendition_ref'] = candidate.rendition_ref
            rule['replacement_artifact_version_ref'] = candidate.artifact_version_ref
        elif has_replacement:
            _reject(SCHEMA_VIOLATION, 'unknown_field', _join(path, 'replacement_media_asset_id'))
        rules.append(rule)
    return rules


_FROZEN_FIELDS = ('timeline', 'hook_placement', 'voice_profile_intent', 'music_cues', 'sfx_cues', 'subtitle_style_intent', 'allowed_fallbacks')
_PAYLOAD_FIELDS = ('production_plan_id', 'script_version_id', 'script_fingerprint', 'preset_revision_ref', 'selection_fingerprint', 'timeline', 'hook_placement', 'thumbnail_overlay_intent', 'voice_profile_intent', 'music_cues', 'sfx_cues', 'subtitle_style_intent', 'allowed_fallbacks', 'output_metadata_ref', 'output_metadata_requirement', 'plan_fingerprint')


@dataclass(frozen=True, kw_only=True)
class ProductionPlan:
    production_plan_id: str
    script_version_id: str
    script_fingerprint: str
    preset_revision_ref: str
    selection_fingerprint: str
    timeline: Mapping[str, object]
    hook_placement: Mapping[str, object]
    thumbnail_overlay_intent: str
    voice_profile_intent: Mapping[str, object]
    music_cues: tuple[Mapping[str, object], ...]
    sfx_cues: tuple[Mapping[str, object], ...]
    subtitle_style_intent: Mapping[str, object]
    allowed_fallbacks: tuple[Mapping[str, object], ...]
    output_metadata_ref: str | None
    output_metadata_requirement: str | None
    plan_fingerprint: str = ''

    def __post_init__(self) -> None:
        for name in _FROZEN_FIELDS:
            object.__setattr__(self, name, _freeze(getattr(self, name)))

    def to_payload(self) -> dict[str, object]:
        return {name: _thaw(getattr(self, name)) for name in _PAYLOAD_FIELDS}

    def fingerprint_basis(self) -> dict[str, object]:
        """Nội dung kế hoạch; loại production_plan_id và plan_fingerprint nên đổi ID không đổi fingerprint."""
        basis = self.to_payload()
        del basis['production_plan_id']
        del basis['plan_fingerprint']
        return basis

    def compute_fingerprint(self) -> str:
        return request_hash(self.fingerprint_basis())

    def to_render_package_inputs(self) -> dict[str, object]:
        """Đầu vào RenderPackage (binding f-render-package, CT-RND-003): đúng tên và kiểu trường cùng tên."""
        return {
            'production_plan_ref': self.production_plan_id,
            'script_version_ref': self.script_version_id,
            'hook_placement': _thaw(self.hook_placement),
            'timeline': _thaw(self.timeline),
            'allowed_fallbacks': _thaw(self.allowed_fallbacks),
        }


def build_production_plan(raw, *, production_plan_id, script, selection, preset_revision_ref) -> ProductionPlan:
    """Dựng ProductionPlan (CT-AI-007) từ raw không tin cậy; chỉ chứa intent.

    Ref asset/rendition/hook/thumbnail lấy từ selection (D-09), không từ raw; thumbnail phải nằm trọn trong hook;
    mọi khoảng timeline có visual. Raise PlanRejected(code, reason, field). coveredIds: CT-AI-007, CT-RND-003
    """
    if not isinstance(script, ScriptVersion):
        _reject(INPUT_NOT_READY, 'missing_script_version', 'script')
    if not isinstance(selection, CreativeAssetSelection):
        _reject(INPUT_NOT_READY, 'missing_asset_selection', 'selection')
    for name, value in (('production_plan_id', production_plan_id), ('preset_revision_ref', preset_revision_ref)):
        if not isinstance(value, str) or not value.strip():
            _reject(INPUT_NOT_READY, f'missing_{name}', name)
    if selection.script_ref != script.script_version_id:
        _reject(CONTEXT_MISMATCH, 'script_ref_mismatch', 'selection.script_ref')
    if not isinstance(raw, Mapping):
        _reject(SCHEMA_VIOLATION, 'wrong_type', '$')
    _scan_intent_only(raw)
    source = _check_keys(raw, _TOP_REQUIRED, _TOP_OPTIONAL, '')
    if ('output_metadata_ref' in source) == ('output_metadata_requirement' in source):
        _reject(SCHEMA_VIOLATION, 'exactly_one_required', 'output_metadata')
    timeline = _parse_timeline(source['timeline'], selection)
    duration_ms = timeline['duration_ms']
    hook_placement = _parse_hook_placement(source['hook_placement'], selection, duration_ms)
    voice = _parse_text_object(source['voice_profile_intent'], ('direction', 'pace', 'emotion'), 'voice_profile_intent')
    music = _parse_cues(source['music_cues'], 'music_cues', selection.music_intents, duration_ms)
    sfx = _parse_cues(source['sfx_cues'], 'sfx_cues', selection.sfx_intents, duration_ms)
    subtitle = _parse_subtitle(source['subtitle_style_intent'])
    fallbacks = _parse_fallbacks(source['allowed_fallbacks'], {s['scene_id'] for s in timeline['segments']}, selection)
    plan = ProductionPlan(
        production_plan_id=production_plan_id, script_version_id=script.script_version_id,
        script_fingerprint=script.script_fingerprint, preset_revision_ref=preset_revision_ref,
        selection_fingerprint=selection.selection_fingerprint, timeline=timeline, hook_placement=hook_placement,
        thumbnail_overlay_intent=selection.thumbnail_overlay_intent, voice_profile_intent=voice,
        music_cues=music, sfx_cues=sfx, subtitle_style_intent=subtitle, allowed_fallbacks=fallbacks,
        output_metadata_ref=_text(source, 'output_metadata_ref', '') if 'output_metadata_ref' in source else None,
        output_metadata_requirement=_text(source, 'output_metadata_requirement', '') if 'output_metadata_requirement' in source else None,
    )
    return replace(plan, plan_fingerprint=plan.compute_fingerprint())
