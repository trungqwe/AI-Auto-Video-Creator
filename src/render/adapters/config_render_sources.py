"""Reads RenderPresetRevision, the output profile and QualityPolicy from published ConfigRevision of scopes preset and policy and seeds them from the production profile parameters (PW-F3, CT-RND-001, CT-QC-001).

PRS-LAYOUT-CONFIG: a preset variant may name its presentation layout (render.presets.variants.<name>.layout, one of render.domain.layout.LAYOUT_KEYS, each layout
at most once); its layout_rules then carry presentation = {layout_key, accent_colour} with the variant highlight colour as accent. A variant without layout keeps the
old layout_rules. seed_render_config with a scope publishes a new revision when the payload of a seeded scope changed, and nothing when it is unchanged.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, fields
from typing import Any, Protocol

from controlplane.application.idempotency.canonicalization import request_hash
from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.config_security import ConfigRevisionStatus
from render.domain.karaoke_plan import KaraokeStyle
from render.domain.layout import LAYOUT_KEYS
from render.domain.preset import RenderPresetRevision, build_preset_revision
from render.domain.quality_report import GateName, QualityPolicy
from render.domain.render_command import OutputProfile

PRESET_SCOPE_KIND = 'preset'
POLICY_SCOPE_KIND = 'policy'
OUTPUT_PROFILE_SCOPE_KEY = 'output-profile'
QUALITY_POLICY_SCOPE_KEY = 'quality'
_COLOUR_RE = re.compile(r'#[0-9A-Fa-f]{6}')


class RenderConfigMissing(LookupError):
    def __init__(self, parameter: str) -> None:
        self.parameter = parameter
        super().__init__(f'missing render config: {parameter}')


class RenderConfigNotSeeded(LookupError):
    def __init__(self, scope_kind: str, scope_key: str) -> None:
        self.scope_kind = scope_kind
        self.scope_key = scope_key
        super().__init__(f'render config not seeded: {scope_kind}/{scope_key}')


class ConfigCommandPort(Protocol):
    def put_config(
        self,
        *,
        workspace_id: str,
        actor_id: str,
        idempotency_key: str,
        scope_kind: str,
        scope_key: str,
        expected_revision: int,
        payload: dict[str, object],
    ) -> dict[str, object]:
        ...


class ConfigScopePort(Protocol):
    def current(
        self, *, workspace_id: str, scope_kind: str, scope_key: str
    ) -> Any | None:
        ...


def _need(source: object, name: str, label: str) -> Any:
    if not isinstance(source, Mapping):
        raise RenderConfigMissing(label)
    if name not in source:
        raise RenderConfigMissing(label)
    val = source[name]
    if val is None:
        raise RenderConfigMissing(label)
    if isinstance(val, (str, Mapping)) and len(val) == 0:
        raise RenderConfigMissing(label)
    return val


def ass_colour(value: str) -> str:
    if not isinstance(value, str) or not _COLOUR_RE.fullmatch(value):
        raise ValueError('invalid colour')
    rr = value[1:3].upper()
    gg = value[3:5].upper()
    bb = value[5:7].upper()
    return f'&H00{bb}{gg}{rr}'


def render_config_payloads(
    parameters: Mapping, supplements: Mapping
) -> list[tuple[str, str, dict]]:
    prof = _need(parameters, 'render.profile', 'render.profile')
    supp_op = _need(supplements, 'output_profile', 'supplements.output_profile')
    output_payload = {
        'width': _need(prof, 'width', 'render.profile.width'),
        'height': _need(prof, 'height', 'render.profile.height'),
        'fps': _need(prof, 'fps', 'render.profile.fps'),
        'container': _need(prof, 'container', 'render.profile.container'),
        'audio_codec': _need(prof, 'audio_codec', 'render.profile.audio_codec'),
        'encoder': _need(prof, 'video_codec', 'render.profile.video_codec'),
        'video_codec': _need(supp_op, 'video_codec', 'supplements.output_profile.video_codec'),
        'pixel_format': _need(supp_op, 'pixel_format', 'supplements.output_profile.pixel_format'),
    }

    presets = _need(parameters, 'render.presets', 'render.presets')
    common = _need(presets, 'common', 'render.presets.common')
    variants = _need(presets, 'variants', 'render.presets.variants')
    layout = _need(supplements, 'layout', 'supplements.layout')
    sections = _need(supplements, 'sections', 'supplements.sections')
    ass_style = _need(supplements, 'ass_style', 'supplements.ass_style')
    render_nvenc = _need(parameters, 'render.nvenc', 'render.nvenc')
    render_fallback = _need(parameters, 'render.fallback', 'render.fallback')
    audio_loudness = _need(parameters, 'audio.loudness', 'audio.loudness')
    audio_bed_gain_db = _need(parameters, 'audio.bed_gain_db', 'audio.bed_gain_db')

    layout_rules = {
        'safe_area': {
            'margin_left': _need(layout, 'margin_left', 'supplements.layout.margin_left'),
            'margin_right': _need(layout, 'margin_right', 'supplements.layout.margin_right'),
            'margin_vertical': _need(common, 'margin_v', 'render.presets.common.margin_v'),
        },
        'line_limits': {
            'max_words_per_line': _need(layout, 'max_words_per_line', 'supplements.layout.max_words_per_line'),
            'max_chars_per_line': _need(layout, 'max_chars_per_line', 'supplements.layout.max_chars_per_line'),
        },
        'disclosure': {
            'font_size': _need(layout, 'disclosure_font_size', 'supplements.layout.disclosure_font_size'),
            'alignment': _need(layout, 'disclosure_alignment', 'supplements.layout.disclosure_alignment'),
            'margin_v': _need(layout, 'disclosure_margin_v', 'supplements.layout.disclosure_margin_v'),
        },
    }

    preset_items: list[tuple[str, str, dict]] = []
    layouts_seen: set[str] = set()
    for name, variant in variants.items():
        rules = dict(layout_rules)
        if isinstance(variant, Mapping) and 'layout' in variant:
            layout_key = variant['layout']
            if layout_key not in LAYOUT_KEYS or layout_key in layouts_seen:
                raise ValueError(f'invalid render.presets.variants.{name}.layout')
            layouts_seen.add(layout_key)
            rules['presentation'] = {
                'layout_key': layout_key,
                'accent_colour': _need(variant, 'highlight_color', f'render.presets.variants.{name}.highlight_color'),
            }
        typography = {
            'font_name': _need(common, 'font', 'render.presets.common.font'),
            'font_size': _need(common, 'font_size', 'render.presets.common.font_size'),
            'bold': -1 if _need(common, 'bold', 'render.presets.common.bold') is True else 0,
            'outline': _need(common, 'outline_width', 'render.presets.common.outline_width'),
            'primary_colour': ass_colour(_need(variant, 'highlight_color', f'render.presets.variants.{name}.highlight_color')),
            'outline_colour': ass_colour(_need(variant, 'outline_color', f'render.presets.variants.{name}.outline_color')),
        }
        for f in fields(KaraokeStyle):
            if f.name not in typography:
                typography[f.name] = _need(ass_style, f.name, f'supplements.ass_style.{f.name}')

        preset_payload = {
            'preset_key': name,
            'visual_rhythm': dict(_need(sections, 'visual_rhythm', 'supplements.sections.visual_rhythm')),
            'layout_rules': rules,
            'thumbnail_overlay_style': dict(_need(sections, 'thumbnail_overlay_style', 'supplements.sections.thumbnail_overlay_style')),
            'typography_karaoke_style': typography,
            'hook_treatment': dict(_need(sections, 'hook_treatment', 'supplements.sections.hook_treatment')),
            'mix_rules': {
                'loudness': dict(audio_loudness),
                'bed_gain_db': audio_bed_gain_db,
            },
            'color_effect_rules': dict(_need(sections, 'color_effect_rules', 'supplements.sections.color_effect_rules')),
            'output_profile_ref': OUTPUT_PROFILE_SCOPE_KEY,
            'fallback_constraints': {
                'nvenc': dict(render_nvenc),
                'fallback': dict(render_fallback),
            },
            'compatibility_requirements': dict(prof),
        }
        preset_items.append((PRESET_SCOPE_KIND, name, preset_payload))

    dur = _need(parameters, 'qc.duration_range_ms', 'qc.duration_range_ms')
    qt = _need(supplements, 'quality_thresholds', 'supplements.quality_thresholds')
    thresholds = {
        GateName.DURATION_RANGE.value: {
            'duration_range_ms': [
                _need(dur, 'min', 'qc.duration_range_ms.min'),
                _need(dur, 'max', 'qc.duration_range_ms.max'),
            ],
        },
        GateName.VISUAL_HOOK_PRESENT.value: {
            'min_similarity': _need(parameters, 'qc.hook_similarity_min', 'qc.hook_similarity_min'),
        },
        GateName.AUDIO_HOOK_PRESENT.value: {
            'min_level_db': _need(parameters, 'qc.hook_audio_min_dbfs', 'qc.hook_audio_min_dbfs'),
        },
        GateName.KARAOKE_TIMING_VALID.value: {
            'tolerance_ms': _need(parameters, 'qc.karaoke_tolerance_ms', 'qc.karaoke_tolerance_ms'),
        },
        GateName.ENGLISH_OUTPUT_VALID.value: {
            'required_language': _need(parameters, 'qc.required_language', 'qc.required_language'),
        },
        GateName.OUTPUT_PROFILE_VALID.value: {
            'container': output_payload['container'],
            'video_codec': output_payload['video_codec'],
            'audio_codec': output_payload['audio_codec'],
            'width': output_payload['width'],
            'height': output_payload['height'],
            'fps': output_payload['fps'],
        },
        GateName.AUDIO_MIX_QUALITY.value: {
            'target_lufs': _need(audio_loudness, 'integrated_lufs', 'audio.loudness.integrated_lufs'),
            'tolerance_lu': _need(audio_loudness, 'warn_tolerance_lu', 'audio.loudness.warn_tolerance_lu'),
            'max_true_peak_dbtp': _need(audio_loudness, 'true_peak_dbtp', 'audio.loudness.true_peak_dbtp'),
        },
        GateName.VISUAL_CONTINUITY.value: {
            'min_continuity': _need(parameters, 'qc.visual_continuity_min', 'qc.visual_continuity_min'),
        },
        GateName.SUBTITLE_BURNED_IN.value: dict(
            _need(qt, 'SUBTITLE_BURNED_IN', 'supplements.quality_thresholds.SUBTITLE_BURNED_IN')
        ),
        GateName.VOICE_AUDIBLE.value: dict(
            _need(qt, 'VOICE_AUDIBLE', 'supplements.quality_thresholds.VOICE_AUDIBLE')
        ),
    }

    result = [
        (PRESET_SCOPE_KIND, OUTPUT_PROFILE_SCOPE_KEY, output_payload),
        *preset_items,
        (POLICY_SCOPE_KIND, QUALITY_POLICY_SCOPE_KEY, {'thresholds': thresholds}),
    ]
    return result


def seed_render_config(
    config_service: ConfigCommandPort,
    *,
    workspace_id: str,
    actor_id: str,
    parameters: Mapping,
    supplements: Mapping,
    scope: ConfigScopePort | None = None,
) -> tuple[str, ...]:
    """Publish every render config payload of the profile; without scope only scopes never seeded (expected revision 0). With scope
    (PRS-LAYOUT-CONFIG) a scope whose current payload hashes like the new one is skipped and a changed one gets a new revision
    on top of the current one (idempotency key suffixed with :r<revision>)."""
    items = render_config_payloads(parameters, supplements)
    seeded: list[str] = []
    for kind, key, payload in items:
        digest = request_hash(payload)[:16]
        idempotency_key = f'seed-render-config:{kind}:{key}:{digest}'
        expected = 0
        if scope is not None:
            current = scope.current(workspace_id=workspace_id, scope_kind=kind, scope_key=key)
            if current is not None:
                if request_hash(dict(current.payload)) == request_hash(payload):
                    continue
                expected = current.revision
                idempotency_key = f'{idempotency_key}:r{expected}'
        try:
            receipt = config_service.put_config(
                workspace_id=workspace_id,
                actor_id=actor_id,
                idempotency_key=idempotency_key,
                scope_kind=kind,
                scope_key=key,
                expected_revision=expected,
                payload=payload,
            )
        except RevisionConflictError:
            continue
        if receipt.get('disposition') == 'accepted':
            seeded.append(f'{kind}:{key}')
    return tuple(seeded)


@dataclass(frozen=True)
class PinnedPreset:
    revision_ref: str
    preset: RenderPresetRevision


@dataclass(frozen=True)
class PinnedOutputProfile:
    revision_ref: str
    profile: OutputProfile


@dataclass(frozen=True)
class PinnedQualityPolicy:
    revision_ref: str
    policy: QualityPolicy


class ConfigRenderSources:
    def __init__(self, scope: ConfigScopePort, workspace_id: str) -> None:
        self._scope = scope
        self._workspace_id = workspace_id

    def _published(self, kind: str, key: str) -> Any:
        revision = self._scope.current(
            workspace_id=self._workspace_id, scope_kind=kind, scope_key=key
        )
        if revision is None or revision.status is not ConfigRevisionStatus.PUBLISHED:
            raise RenderConfigNotSeeded(kind, key)
        return revision

    def preset(self, preset_key: str) -> PinnedPreset:
        rev = self._published(PRESET_SCOPE_KIND, preset_key)
        preset_obj = build_preset_revision(
            {**dict(rev.payload), 'revision': rev.config_revision_number}
        )
        return PinnedPreset(rev.config_revision_id, preset_obj)

    def output_profile(self) -> PinnedOutputProfile:
        rev = self._published(PRESET_SCOPE_KIND, OUTPUT_PROFILE_SCOPE_KEY)
        payload = rev.payload
        profile_obj = OutputProfile(
            **{f.name: payload.get(f.name) for f in fields(OutputProfile)}
        )
        return PinnedOutputProfile(rev.config_revision_id, profile_obj)

    def quality_policy(self) -> PinnedQualityPolicy:
        rev = self._published(POLICY_SCOPE_KIND, QUALITY_POLICY_SCOPE_KEY)
        if 'thresholds' not in rev.payload:
            raise RenderConfigMissing('thresholds')
        policy_obj = QualityPolicy(
            revision=rev.config_revision_id, thresholds=rev.payload['thresholds']
        )
        return PinnedQualityPolicy(rev.config_revision_id, policy_obj)


@dataclass(frozen=True, kw_only=True)
class AssInputs:
    typography: dict
    safe_area: dict
    profile: dict
    disclosure_style: dict


def ass_inputs(preset: RenderPresetRevision, profile: OutputProfile) -> AssInputs:
    layout = preset.layout_rules
    safe = _need(layout, 'safe_area', 'layout_rules.safe_area')
    limits = _need(layout, 'line_limits', 'layout_rules.line_limits')
    disclosure = _need(layout, 'disclosure', 'layout_rules.disclosure')
    return AssInputs(
        typography=dict(preset.typography_karaoke_style),
        safe_area=dict(safe),
        profile={**dict(limits), 'play_res_x': profile.width, 'play_res_y': profile.height},
        disclosure_style=dict(disclosure),
    )


__all__ = (
    'AssInputs',
    'ConfigCommandPort',
    'ConfigRenderSources',
    'ConfigScopePort',
    'OUTPUT_PROFILE_SCOPE_KEY',
    'POLICY_SCOPE_KIND',
    'PRESET_SCOPE_KIND',
    'PinnedOutputProfile',
    'PinnedPreset',
    'PinnedQualityPolicy',
    'QUALITY_POLICY_SCOPE_KEY',
    'RenderConfigMissing',
    'RenderConfigNotSeeded',
    'ass_colour',
    'ass_inputs',
    'render_config_payloads',
    'seed_render_config',
)
