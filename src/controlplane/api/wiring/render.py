from __future__ import annotations

"""ADAPT-WIRE: wiring cho phân hệ F (render).
Đấu nối RealFfmpegRenderer, RealFfprobeProbe và PostgresRenderUnitOfWork.
Không chạy ffmpeg và không kiểm pin lúc dựng."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any
import datetime
import hashlib
import json
import math
import re
import threading
import wave
from collections.abc import Mapping, Sequence
from pathlib import Path

from controlplane.api.wiring._shared import resolve_under_root
from controlplane.api.wiring.workflow import RenderImage, render_handler, render_image_sources
from controlplane.infrastructure.db.control_api_commands import PostgresConfigScope, compose_command_service
from controlplane.infrastructure.production_ports.gpu_lease import LocalGpuLease
from render.adapters.activity_inputs import (
    INPUT_REF_MISSING,
    ActivityInputError,
    RenderActivityInputs,
    RenderPlan,
    QualityInputs,
)
from render.adapters.ass_manifest import build_ass_material, with_ass_entry
from render.adapters.audio_mix_gate import AudioMixGate
from render.adapters.config_render_sources import ConfigRenderSources, RenderConfigNotSeeded, ass_inputs, seed_render_config
from render.adapters.ffmpeg_capability import read_tool_capability
from render.adapters.postgres_plan_assets import (
    PostgresArtifactInfo,
    PostgresPlanAssets,
    read_script_segments,
)
from render.adapters.real_output_inspector import (
    Band,
    InspectionInputs,
    InspectorSettings,
    LanguageSource,
    RealOutputInspector,
)
from render.application.package_pipeline import PackagePipeline
from render.application.inspect_output import OutputPipeline
from render.application.render_video import RenderPipeline
from render.domain.content_gates import ExpectedLanguageRevisions
from render.domain.preconditions_artifacts import LanguageEvidencePolicy
from render.domain.karaoke_plan import parse_word_timing
from render.domain.package_contract import RenderPackageRecord
from render.domain.preconditions_artifacts import (
    ArtifactLocationState,
    IssuedOutputPath,
    ToolCapability,
    VerifiedArtifact,
)
from render.domain.render_command import (
    MaterializedPaths,
    ToolIdentity,
    build_render_command,
)
from render.domain.validate_package import (
    LanguageEvidenceView,
    ValidationContext,
    VoiceTrackInfo,
    WordTimingInfo,
)
from render.ports.inputs import LocalMaterialRef, ResolveInputs, ResolvedAsset
from render.worker.activity_handler import RenderActivityDeps
from controlplane.application.storage_meta.handlers import STAGED_HOOK_EXTENSIONS, verified_version_for_sha


from controlplane.api.wiring.production_profile import (
    PROFILE_PRODUCTION,
    WiringConfig,
)
from render.adapters.fake_renderer import FakeOutputStorage, FakeRenderer
from render.adapters.memory import InMemoryUnitOfWork
from render.adapters.real_ffmpeg_renderer import RealFfmpegRenderer, sha256_file, verify_ffmpeg_pin
from render.adapters.real_ffprobe_probe import RealFfprobeProbe, measure_loudness
from render.persistence.unit_of_work import PostgresRenderUnitOfWork


@dataclass(frozen=True)
class RenderServices:
    mode: str
    uow_factory: Callable[[], Any]
    renderer: Any
    probe: Any


def build_render_services(manager: Any, config: WiringConfig) -> RenderServices:
    if config.mode != PROFILE_PRODUCTION:
        return RenderServices(
            config.mode,
            InMemoryUnitOfWork,
            FakeRenderer(FakeOutputStorage(), output_ref='memory://render/output.mp4'),
            None,
        )

    profile, runtime = config.production_parts()
    renderer = RealFfmpegRenderer(
        lease=runtime.gpu_lease,
        ffmpeg_path=str(runtime.ffmpeg_path),
        lock_path=runtime.runtime_lock_path,
        timeout_seconds=profile.render.timeout_seconds,
    )
    renderer.lease = runtime.gpu_lease
    probe = RealFfprobeProbe(
        ffprobe_path=str(runtime.ffprobe_path),
        timeout_seconds=profile.render.timeout_seconds,
    )
    uow_factory = partial(PostgresRenderUnitOfWork, manager, workspace_id=config.workspace_id)
    return RenderServices('production', uow_factory, renderer, probe)


_RENDER_SUPPLEMENT_PARAMETERS = (
    ('ass_style', 'render.ass_style'),
    ('layout', 'render.layout'),
    ('sections', 'render.sections'),
    ('output_profile', 'render.output_stream'),
    ('quality_thresholds', 'qc.quality_thresholds'),
)


def render_supplements(profile: Any) -> dict[str, Any]:
    return {name: profile.parameters[parameter] for name, parameter in _RENDER_SUPPLEMENT_PARAMETERS}


def seed_production_render_config(manager: Any, *, workspace_id: str, actor_id: str, profile: Any) -> tuple[str, ...]:
    return seed_render_config(
        compose_command_service(manager.unit_of_work),
        workspace_id=workspace_id,
        actor_id=actor_id,
        parameters=profile.parameters,
        supplements=render_supplements(profile),
        scope=FreshScope(manager),
    )


def _read_tool_version(lock_path: Path | str) -> str:
    try:
        data = json.loads(Path(lock_path).read_text(encoding='utf-8'))
        entry = data.get('pins', {}).get('ffmpeg', {})
        return str(entry.get('archive_name') or entry.get('sha256') or 'ffmpeg-pinned')
    except Exception:
        return 'ffmpeg-pinned'


_VOICE_SOURCE_PREFIX = 'voice/'
_OUTPUT_NAME_UNSAFE = re.compile(r'[^A-Za-z0-9_-]')
_HOOK_PLACEMENT_REFS = ('visual_hook_ref', 'audio_hook_ref', 'thumbnail_ref')
_THUMBNAIL_REF_PREFIX = 'thumb:'
_HOOK_MEDIA_SHA_KEY = 'media_sha256'
# HOOK-QC (FR-HOOK-008): a hook revision whose technical_metadata names a recipe of hooks.json is a generated placeholder
# (gradient vh-01..05, sweep ah-01..05); render refuses it instead of putting a placeholder in the video.
_HOOK_PLACEHOLDER_KEY = 'recipe_template'
# PRS-LAYOUT-RENDER: preset of a plan without a seeded preset_revision_ref (the preset of the default layout HERO_STRIP).
DEFAULT_PRESET_KEY = 'bold-yellow'
HOOK_PLACEHOLDER_REASON = 'hook_placeholder'
_HOOK_LATEST_SQL = ('SELECT r.payload FROM controlplane.cp_hook_revisions r JOIN controlplane.cp_hooks h ON h.workspace_id = r.workspace_id AND h.hook_id = r.hook_id AND h.current_revision = r.revision WHERE h.workspace_id = %s::uuid AND h.hook_id = %s')


@dataclass(frozen=True)
class _StagedSource:
    version_id: str
    sha256: str
    size_bytes: int
    media_type: str
    role: str


def _hook_not_ready(ref: str, reason: str) -> ActivityInputError:
    return ActivityInputError('INPUT_NOT_READY', f'{reason}:{ref}')


def _visual_version_ref(timeline: Mapping[str, Any], media_asset_id: str) -> str | None:
    segments = timeline.get('segments') if isinstance(timeline, Mapping) else None
    if not isinstance(segments, list):
        return None
    for segment in segments:
        if not isinstance(segment, Mapping):
            continue
        visuals = segment.get('visuals')
        if not isinstance(visuals, list):
            continue
        for visual in visuals:
            if isinstance(visual, Mapping) and visual.get('media_asset_id') == media_asset_id:
                version_ref = visual.get('artifact_version_ref')
                if isinstance(version_ref, str) and version_ref:
                    return version_ref
    return None


_SELECTED_MEDIA_REF = 'selected_media'
NO_ILLUSTRATION_AVAILABLE = 'no_illustration_available'
_SEED_FALLBACK_REASON = 'seed_fallback'
_SEED_ORIGIN = 'seed'
_AI_GENERATED_ORIGIN = 'ai_generated'
_IMAGE_FALLBACK_REASON = 'image_fallback'
_IMAGE_SAFETY_RULE_PREFIX = 'image-safety:'
_SEED_SHARE_MAX_PERCENT = 15


def _visual_version_refs(timeline: Mapping[str, Any]) -> set[str]:
    refs: set[str] = set()
    segments = timeline.get('segments')
    if isinstance(segments, list):
        for segment in segments:
            if isinstance(segment, Mapping):
                visuals = segment.get('visuals')
                if isinstance(visuals, list):
                    for visual in visuals:
                        if isinstance(visual, Mapping):
                            ref = visual.get('artifact_version_ref')
                            if isinstance(ref, str) and ref:
                                refs.add(ref.lower())
    return refs


def _image_safe_timeline(
    timeline: Mapping[str, Any],
    images: Mapping[str, RenderImage],
) -> tuple[dict[str, Any], dict[str, tuple[str, RenderImage]]]:
    if not isinstance(timeline, Mapping) or not isinstance(timeline.get('segments'), list):
        return (dict(timeline) if isinstance(timeline, Mapping) else {}, {})
    replaced: dict[str, tuple[str, RenderImage]] = {}
    mapped = []
    for segment in timeline.get('segments', []):
        if not isinstance(segment, Mapping) or not isinstance(segment.get('visuals'), list):
            mapped.append(segment)
            continue
        new_visuals = []
        for visual in segment.get('visuals', []):
            media = visual.get('media_asset_id') if isinstance(visual, Mapping) else None
            if not isinstance(media, str) or not media:
                new_visuals.append(visual)
                continue
            image = images.get(media)
            if image is None:
                raise ActivityInputError('INPUT_NOT_READY', f'image_not_assessed:{media}')
            if image.artifact_version_id is None:
                raise ActivityInputError('INPUT_NOT_READY', f'image_excluded:{image.reason}:{media}')
            original = visual.get('artifact_version_ref')
            if isinstance(original, str) and original.lower() != image.artifact_version_id.lower():
                replaced.setdefault(media, (original, image))
                visual = {**visual, 'artifact_version_ref': image.artifact_version_id}
            new_visuals.append(visual)
        mapped.append({**segment, 'visuals': new_visuals})
    return ({**timeline, 'segments': mapped}, replaced)


def _image_fallback_rule(media: str, original: str, image: RenderImage) -> dict[str, str]:
    return {
        'rule_id': f'image-safety:{media}',
        'kind': 'replace_asset',
        'replaced_media_asset_id': media,
        'replaced_artifact_version_ref': original,
        'artifact_version_id': image.artifact_version_id,
        'reason': image.reason,
    }


# Wiring không import creative: bốn hàm dưới giữ khớp bản ở creative.domain.production_plan (có test đối chiếu).
def _union_ms(spans: list[tuple[int, int]]) -> int:
    total = 0
    reach = 0
    for start, end in sorted(spans):
        start = max(start, reach)
        if end > start:
            total += end - start
            reach = end
    return total


def _int_ms(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def seed_time_ms(segments, shows_seed) -> tuple[int, int]:
    scenes: list[tuple[int, int]] = []
    seeds: list[tuple[int, int]] = []
    for scene in segments:
        if not isinstance(scene, Mapping) or not _int_ms(scene.get('start_ms')) or not _int_ms(scene.get('end_ms')):
            continue
        start, end = scene['start_ms'], scene['end_ms']
        scenes.append((start, end))
        visuals = scene.get('visuals')
        for visual in visuals if isinstance(visuals, (list, tuple)) else ():
            if not isinstance(visual, Mapping) or not _int_ms(visual.get('start_ms')) or not _int_ms(visual.get('end_ms')):
                continue
            if shows_seed(visual):
                seeds.append((max(start, visual['start_ms']), min(end, visual['end_ms'])))
    return _union_ms(seeds), _union_ms(scenes)


def seed_share_within_limit(seed_ms: int, timeline_ms: int) -> bool:
    return seed_ms * 100 <= _SEED_SHARE_MAX_PERCENT * timeline_ms


def require_illustration(timeline: Mapping[str, Any], images: Mapping[str, RenderImage] | None) -> None:
    """Từ chối job khi timeline cuối quá mức ảnh seed cho phép (kể cả toàn seed): không có video chỉ có ảnh nền (RG-13)."""
    segments = timeline.get('segments') if isinstance(timeline, Mapping) else None
    if not isinstance(segments, (list, tuple)):
        return
    chosen = images or {}

    def shows_seed(visual: Mapping[str, Any]) -> bool:
        image = chosen.get(visual.get('media_asset_id'))
        return visual.get('origin') == _SEED_ORIGIN or (image is not None and image.reason == _SEED_FALLBACK_REASON)

    seed_ms, timeline_ms = seed_time_ms(segments, shows_seed)
    if not seed_share_within_limit(seed_ms, timeline_ms):
        raise ActivityInputError(NO_ILLUSTRATION_AVAILABLE, f'seed_share_above_max:{seed_ms}/{timeline_ms}')


def _mappings(value: object) -> list[Mapping[str, Any]]:
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, (list, tuple)) else []


def _ai_image_refs(timeline: object, allowed_fallbacks: object) -> set[str]:
    replaced = {
        rule.get('replaced_media_asset_id')
        for rule in _mappings(allowed_fallbacks)
        if str(rule.get('rule_id', '')).startswith(_IMAGE_SAFETY_RULE_PREFIX)
        and rule.get('reason') in (_SEED_FALLBACK_REASON, _IMAGE_FALLBACK_REASON)
    }
    refs: set[str] = set()
    for scene in _mappings(timeline.get('segments') if isinstance(timeline, Mapping) else None):
        for visual in _mappings(scene.get('visuals')):
            ref = visual.get('artifact_version_ref')
            if visual.get('origin') == _AI_GENERATED_ORIGIN and visual.get('media_asset_id') not in replaced and isinstance(ref, str) and ref:
                refs.add(ref.lower())
    return refs


def _cut_ranges(spans: list[tuple[int, int]], cuts: list[tuple[int, int]]) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    for start, end in spans:
        pieces = [(start, end)]
        for cut_start, cut_end in cuts:
            kept: list[tuple[int, int]] = []
            for a, b in pieces:
                if cut_end <= a or cut_start >= b:
                    kept.append((a, b))
                    continue
                if a < cut_start:
                    kept.append((a, cut_start))
                if cut_end < b:
                    kept.append((cut_end, b))
            pieces = kept
        result.extend(pieces)
    return result


def illustration_windows(timeline: Any, hook_placement: Any, allowed_fallbacks: Any, end_ms: Any = None) -> tuple[tuple[int, int], ...]:
    ai_refs = _ai_image_refs(timeline, allowed_fallbacks)
    if not ai_refs:
        return ()
    scenes = [
        s for s in _mappings(timeline.get('segments') if isinstance(timeline, Mapping) else None)
        if _int_ms(s.get('start_ms')) and _int_ms(s.get('end_ms')) and 0 <= s['start_ms'] < s['end_ms']
    ]
    if not scenes:
        return ()
    last_end = max(s['end_ms'] for s in scenes)
    spans: list[tuple[int, int]] = []
    for scene in scenes:
        refs = scene.get('visual_asset_refs')
        first = refs[0] if isinstance(refs, (list, tuple)) and refs else None
        if not isinstance(first, str) or first.lower() not in ai_refs:
            continue
        end = scene['end_ms']
        if end == last_end and _int_ms(end_ms) and end_ms > end:
            end = end_ms
        spans.append((scene['start_ms'], end))
    merged: list[list[int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    placement = hook_placement if isinstance(hook_placement, Mapping) else {}
    cuts: list[tuple[int, int]] = []
    for name in ('hook_time_range', 'thumbnail_time_range'):
        span = placement.get(name)
        if isinstance(span, Mapping) and _int_ms(span.get('start_ms')) and _int_ms(span.get('end_ms')) and 0 <= span['start_ms'] < span['end_ms']:
            cuts.append((span['start_ms'], span['end_ms']))
    pieces = _cut_ranges([(a, b) for a, b in merged], cuts)
    return tuple(sorted((a, b) for a, b in pieces if a < b))


_REF_AUDIO_BED_CUE = 'audio_bed_cue'
_MUSIC_RENDITION = re.compile(r'music-[0-9a-f]{64}')
_BED_NONE_RENDITION = re.compile(r'bed-none-[0-9a-f]{64}')
_MILLISECONDS = re.compile(r'[0-9]{1,9}')
_BED_ABSOLUTE_GATE_LUFS = -70.0
_BED_ROLE = 'music_bed'
_BED_MEDIA_TYPE = 'audio/wav'


@dataclass(frozen=True)
class _BedCue:
    rendition_ref: str
    start_ms: int
    end_ms: int
    staged_ref: str | None


def _bed_not_ready(ref: str) -> ActivityInputError:
    return ActivityInputError('INPUT_NOT_READY', f'audio_bed_not_ready:{ref}')


def _bed_cues(input_refs: Sequence[Mapping[str, Any]]) -> list[_BedCue]:
    """Music cues of the audio_bed_cue refs; bed-none cues are silent and dropped; any malformed ref is INVALID_INPUT."""
    cues: list[_BedCue] = []
    for item in input_refs:
        if not isinstance(item, Mapping) or item.get('ref_type') != _REF_AUDIO_BED_CUE:
            continue
        rendition, start, end, staged = item.get('rendition_ref'), item.get('start_ms'), item.get('end_ms'), item.get('staged_ref')
        valid = (
            isinstance(rendition, str)
            and bool(_MUSIC_RENDITION.fullmatch(rendition) or _BED_NONE_RENDITION.fullmatch(rendition))
            and isinstance(start, str) and bool(_MILLISECONDS.fullmatch(start))
            and isinstance(end, str) and bool(_MILLISECONDS.fullmatch(end))
            and int(start) < int(end)
            and (staged is None or isinstance(staged, str))
        )
        if not valid:
            raise ActivityInputError('INVALID_INPUT', f"audio_bed_cue:{item.get('ref_id')}")
        if _MUSIC_RENDITION.fullmatch(rendition):
            cues.append(_BedCue(rendition, int(start), int(end), staged or None))
    return cues


def _wav_duration_ms(path: Path, ref: str) -> int:
    try:
        with wave.open(str(path), 'rb') as stream:
            frames, rate = stream.getnframes(), stream.getframerate()
    except (wave.Error, EOFError, OSError):
        raise _bed_not_ready(ref) from None
    if frames < 1 or rate < 1:
        raise _bed_not_ready(ref)
    return frames * 1000 // rate


def _bed_windows(cues: Sequence[_BedCue], durations: Mapping[str, int]) -> list[tuple[str, int, int]]:
    """One bed at a time, each window plays its rendition from the start: the same rendition touching or overlapping the previous window extends it while the window fits the WAV; otherwise the previous window stops where the next cue starts."""
    windows: list[list[Any]] = []
    for cue in sorted(cues, key=lambda item: (item.start_ms, item.end_ms, item.rendition_ref)):
        if windows:
            last = windows[-1]
            if cue.rendition_ref == last[0] and cue.start_ms <= last[2]:
                end = max(last[2], cue.end_ms)
                if end - last[1] <= durations[cue.rendition_ref]:
                    last[2] = end
                    continue
            if cue.start_ms < last[2]:
                last[2] = cue.start_ms
                if last[2] <= last[1]:
                    windows.pop()
        windows.append([cue.rendition_ref, cue.start_ms, cue.end_ms])
    return [(ref, start, end) for ref, start, end in windows]


def _output_name(render_attempt_id: str) -> str:
    return _OUTPUT_NAME_UNSAFE.sub('_', render_attempt_id)


def _timing_digest(payload: Mapping[str, Any]) -> tuple[str, int]:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(canonical).hexdigest(), len(canonical)


def _timeline_for_render(timeline: Mapping[str, Any]) -> dict[str, Any]:
    segments = timeline.get('segments') if isinstance(timeline, Mapping) else None
    if not isinstance(segments, list):
        return dict(timeline) if isinstance(timeline, Mapping) else {}
    mapped: list[Any] = []
    for segment in segments:
        if not isinstance(segment, Mapping) or 'visual_asset_refs' in segment:
            mapped.append(segment)
            continue
        visuals = segment.get('visuals')
        ordered = sorted(
            (v for v in visuals if isinstance(v, Mapping)) if isinstance(visuals, list) else (),
            key=lambda v: (v.get('start_ms', 0), v.get('end_ms', 0)),
        )
        refs = [
            v['artifact_version_ref']
            for v in ordered
            if isinstance(v.get('artifact_version_ref'), str) and v['artifact_version_ref']
        ]
        mapped.append({**segment, 'visual_asset_refs': refs})
    return {**timeline, 'segments': mapped}


class FreshScope:
    def __init__(self, manager: Any) -> None:
        self._manager = manager

    def current(self, *, workspace_id: str, scope_kind: str, scope_key: str) -> Any | None:
        with self._manager.borrow_connection() as connection:
            return PostgresConfigScope(connection).current(
                workspace_id=workspace_id, scope_kind=scope_kind, scope_key=scope_key
            )


class ThreadLocalRenderUow:
    def __init__(self, factory: Callable[[], Any]) -> None:
        self._factory = factory
        self._local = threading.local()

    def _get(self) -> Any:
        if not hasattr(self._local, 'uow'):
            self._local.uow = self._factory()
        return self._local.uow

    def __enter__(self) -> Any:
        return self._get().__enter__()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
        return self._get().__exit__(exc_type, exc_val, exc_tb)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._get(), name)


class StagingResolvingProbe:
    def __init__(self, probe: Any, staging_root: Path) -> None:
        self._probe = probe
        self._staging_root = Path(staging_root)

    def probe(self, output_ref: str) -> Any:
        p = Path(output_ref)
        if not p.is_file() and (self._staging_root / p).is_file():
            p = self._staging_root / p
        return self._probe.probe(str(p))


def build_qc_probe(runtime: Any, *, timeout_seconds: float, voice_windows: Sequence[tuple[int, int]]) -> StagingResolvingProbe:
    return StagingResolvingProbe(
        RealFfprobeProbe(
            ffprobe_path=str(runtime.ffprobe_path),
            timeout_seconds=timeout_seconds,
            ffmpeg_path=runtime.ffmpeg_path,
            lock_path=runtime.runtime_lock_path,
            voice_windows=voice_windows,
        ),
        runtime.staging_root,
    )


class StagingResolvingInspector:
    def __init__(self, inner_factory: Any, staging_root: Path) -> None:
        self._inner_factory = inner_factory
        self._staging_root = Path(staging_root)

    def inspect(self, output_ref: str, package: Any) -> Any:
        p = Path(output_ref)
        if not p.is_file() and (self._staging_root / p).is_file():
            p = self._staging_root / p
        inspector = self._inner_factory(package) if callable(self._inner_factory) else self._inner_factory
        return inspector.inspect(str(p), package)


class StagingResolvingRenderer:
    takes_held_lease = True

    def __init__(self, renderer: Any, staging_root: Path) -> None:
        self._renderer = renderer
        self._staging_root = Path(staging_root)

    @property
    def last_encoder(self) -> Any:
        return getattr(self._renderer, 'last_encoder', None)

    def run(self, spec: Any, *, lease: Any) -> Any:
        return self._renderer.run(spec, lease=lease)

    def observe(self, output_ref: str) -> Any:
        p = Path(output_ref)
        if not p.is_file() and (self._staging_root / p).is_file():
            p = self._staging_root / p
        return self._renderer.observe(str(p))


class ProductionRenderSources:
    def __init__(self, manager: Any, workspace_id: str, profile: Any, runtime: Any, clock: Callable[[], datetime.datetime]) -> None:
        self._manager = manager
        self._workspace_id = workspace_id
        self._profile = profile
        self._runtime = runtime
        self._clock = clock
        self._image_sources: Callable[[Sequence[Mapping[str, Any]]], dict[str, RenderImage]] | None = None

    def _image_decisions(self, input_refs: Sequence[Mapping[str, str]]) -> dict[str, RenderImage] | None:
        if not any(isinstance(ref, Mapping) and ref.get('ref_type') == _SELECTED_MEDIA_REF for ref in input_refs):
            return None
        if self._image_sources is None:
            self._image_sources = render_image_sources(
                self._manager,
                workspace_id=self._workspace_id,
                profile=self._profile,
                staging_root=self._runtime.staging_root,
                clock=self._clock,
            )
        return self._image_sources(input_refs)

    def _read_timing_payload(self, timing_ref: str) -> Mapping[str, Any] | None:
        timing_sql = (
            'SELECT payload FROM controlplane.cp_word_timings '
            'WHERE workspace_id = %s::uuid AND timing_artifact_ref = %s '
            'ORDER BY revision DESC LIMIT 1'
        )
        try:
            with self._manager.borrow_connection() as conn:
                row = conn.execute(timing_sql, (self._workspace_id, timing_ref)).fetchone()
        except Exception:
            return None
        if row is None:
            return None
        payload = row[0]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                return None
        return payload if isinstance(payload, Mapping) else None

    def _build_ass_material(
        self,
        timing_payload: Mapping[str, Any],
        script_version_ref: str,
        *,
        timeline: Mapping[str, Any],
        hook_placement: Mapping[str, Any],
        allowed_fallbacks: Sequence[Mapping[str, Any]],
        plan_ref: str | None = None,
    ) -> Any:
        scope = FreshScope(self._manager)
        cfg_sources = ConfigRenderSources(scope, self._workspace_id)
        preset_obj = self._plan_preset(cfg_sources, plan_ref).preset
        profile_obj = cfg_sources.output_profile().profile
        infos = read_script_segments(self._manager, workspace_id=self._workspace_id, script_version_ref=script_version_ref)
        inputs_ass = ass_inputs(preset_obj, profile_obj)
        labels = illustration_windows(timeline, hook_placement, allowed_fallbacks, timing_payload.get('voice_duration_ms'))
        return build_ass_material(
            staging_root=str(self._runtime.staging_root),
            words=parse_word_timing(timing_payload),
            typography=inputs_ass.typography,
            safe_area=inputs_ass.safe_area,
            profile=inputs_ass.profile,
            disclosure_style=inputs_ass.disclosure_style,
            segments=infos,
            illustration_windows=labels,
        )

    def _hook_source(self, hook_id: str) -> _StagedSource | None:
        with self._manager.borrow_connection() as conn:
            row = conn.execute(_HOOK_LATEST_SQL, (self._workspace_id, hook_id)).fetchone()
        if row is None:
            return None
        payload = row[0]
        if isinstance(payload, str):
            payload = json.loads(payload)
        pairs = payload.get('technical_metadata') if isinstance(payload, Mapping) else None
        if isinstance(pairs, list) and any(isinstance(p, (list, tuple)) and len(p) == 2 and p[0] == _HOOK_PLACEHOLDER_KEY for p in pairs):
            raise _hook_not_ready(hook_id, HOOK_PLACEHOLDER_REASON)
        sha256 = next((p[1] for p in pairs if isinstance(p, (list, tuple)) and len(p) == 2 and p[0] == _HOOK_MEDIA_SHA_KEY), None) if isinstance(pairs, list) else None
        if not isinstance(sha256, str):
            raise _hook_not_ready(hook_id, 'hook_media_sha256_missing')
        version = verified_version_for_sha(self._manager, workspace_id=self._workspace_id, sha256=sha256, extensions=STAGED_HOOK_EXTENSIONS)
        if version is None:
            raise _hook_not_ready(hook_id, 'hook_version_not_verified')
        return _StagedSource(version.artifact_version_id, version.sha256_hash, version.size_bytes, version.mime_type, version.artifact_kind)

    def _thumbnail_source(self, ref: str, timeline: Mapping[str, Any], art_info: PostgresArtifactInfo) -> _StagedSource:
        if not ref.startswith(_THUMBNAIL_REF_PREFIX) or len(ref) <= len(_THUMBNAIL_REF_PREFIX):
            raise _hook_not_ready(ref, 'thumbnail_ref_unresolvable')
        subject = ref[len(_THUMBNAIL_REF_PREFIX):]
        source = self._hook_source(subject)
        if source is not None:
            return source
        version_ref = _visual_version_ref(timeline, subject)
        asset = art_info.get_asset(version_ref) if version_ref else None
        if asset is None:
            raise _hook_not_ready(ref, 'thumbnail_subject_not_found')
        return _StagedSource(asset.artifact_version_id, asset.sha256, asset.size_bytes, asset.media_type, asset.role)

    def _hook_assets(self, hook_placement: Any, timeline: Mapping[str, Any], art_info: PostgresArtifactInfo) -> list[tuple[ResolvedAsset, LocalMaterialRef]]:
        if not isinstance(hook_placement, Mapping):
            return []
        resolved: dict[str, tuple[ResolvedAsset, LocalMaterialRef]] = {}
        for key in _HOOK_PLACEMENT_REFS:
            ref = hook_placement.get(key)
            if not isinstance(ref, str) or not ref or ref in resolved:
                continue
            if key == 'thumbnail_ref':
                source = self._thumbnail_source(ref, timeline, art_info)
            else:
                source = self._hook_source(ref)
                if source is None:
                    raise _hook_not_ready(ref, 'hook_not_found')
            resolved[ref] = (
                ResolvedAsset(artifact_version_id=ref, sha256=source.sha256, size_bytes=source.size_bytes, media_type=source.media_type, role=source.role),
                LocalMaterialRef(artifact_version_id=ref, local_ref=source.version_id),
            )
        return list(resolved.values())

    def _flat_bed(self, rendition: str, staged_ref: str | None) -> Path:
        if staged_ref is None:
            raise _bed_not_ready(rendition)
        expected = rendition[len('music-'):]
        root = Path(self._runtime.staging_root)
        try:
            source = resolve_under_root(root, staged_ref)
            flat = resolve_under_root(root, f'{rendition}.wav')
            if flat.is_file() and sha256_file(flat) == expected:
                return flat
            data = source.read_bytes()
            if hashlib.sha256(data).hexdigest() != expected:
                raise _bed_not_ready(rendition)
            part = flat.with_name(flat.name + '.part')
            part.write_bytes(data)
            part.replace(flat)
        except (OSError, ValueError):
            raise _bed_not_ready(rendition) from None
        return flat

    def _bed_level(self, path: Path, ref: str) -> float:
        timeout = _build_inspector_settings(self._profile).timeout_seconds
        lufs = measure_loudness(Path(self._runtime.ffmpeg_path), path, timeout_seconds=timeout).integrated_lufs
        if lufs is None or not math.isfinite(lufs) or lufs <= _BED_ABSOLUTE_GATE_LUFS:
            raise _bed_not_ready(ref)
        return lufs

    def _bed_mix(self, input_refs: Sequence[Mapping[str, Any]], voice_ref: str, voice_local: str, mix_rules: Any) -> tuple[dict[str, Any], list[ResolvedAsset], list[LocalMaterialRef]]:
        cues = _bed_cues(input_refs)
        if not cues:
            return {}, [], []
        gain = mix_rules.get('bed_gain_db') if isinstance(mix_rules, Mapping) else None
        if isinstance(gain, bool) or not isinstance(gain, (int, float)) or not math.isfinite(gain):
            raise ActivityInputError('INPUT_NOT_READY', 'bed_gain_db_missing')
        try:
            voice_path = resolve_under_root(Path(self._runtime.staging_root), voice_local)
        except ValueError:
            raise _bed_not_ready(voice_ref) from None
        verify_ffmpeg_pin(Path(self._runtime.ffmpeg_path), Path(self._runtime.runtime_lock_path))
        voice_lufs = self._bed_level(voice_path, voice_ref)
        flats: dict[str, Path] = {}
        levels: dict[str, float] = {}
        durations: dict[str, int] = {}
        for cue in cues:
            ref = cue.rendition_ref
            if ref in flats:
                continue
            staged = next((c.staged_ref for c in cues if c.rendition_ref == ref and c.staged_ref), None)
            flats[ref] = self._flat_bed(ref, staged)
            levels[ref] = self._bed_level(flats[ref], ref)
            durations[ref] = _wav_duration_ms(flats[ref], ref)
        beds: list[dict[str, Any]] = []
        assets: list[ResolvedAsset] = []
        entries: list[LocalMaterialRef] = []
        for ref, start, end in _bed_windows(cues, durations):
            beds.append({'rendition_ref': ref, 'start_ms': start, 'end_ms': end, 'integrated_lufs': round(levels[ref], 2), 'gain_db': round(gain + voice_lufs - levels[ref], 1)})
            if all(asset.artifact_version_id != ref for asset in assets):
                assets.append(ResolvedAsset(artifact_version_id=ref, sha256=ref[len('music-'):], size_bytes=flats[ref].stat().st_size, media_type=_BED_MEDIA_TYPE, role=_BED_ROLE))
                entries.append(LocalMaterialRef(artifact_version_id=ref, local_ref=f'{ref}.wav'))
        return {'bed_gain_db': gain, 'voice_integrated_lufs': round(voice_lufs, 2), 'beds': beds}, assets, entries

    def _plan_payload(self, plan_ref: str | None) -> Mapping[str, Any] | None:
        """Payload of the latest revision of the production plan, or None when there is no plan_ref, no row or no readable payload."""
        if not plan_ref:
            return None
        plan_sql = (
            'SELECT payload FROM controlplane.cp_production_plans '
            'WHERE workspace_id = %s::uuid AND production_plan_id = %s '
            'ORDER BY revision DESC LIMIT 1'
        )
        try:
            with self._manager.borrow_connection() as conn:
                prow = conn.execute(plan_sql, (self._workspace_id, plan_ref)).fetchone()
        except Exception:
            return None
        if prow is None:
            return None
        raw_p = prow[0]
        p_obj = json.loads(raw_p) if isinstance(raw_p, str) else raw_p
        return p_obj if isinstance(p_obj, Mapping) else None

    def _plan_preset(self, cfg_sources: ConfigRenderSources, plan_ref: str | None) -> Any:
        """PRS-LAYOUT-RENDER (FR-PRS-003): the preset named by the plan's preset_revision_ref (chosen with the layout at plan time); a plan
        without one, or naming a preset that is not seeded, renders with DEFAULT_PRESET_KEY as before."""
        payload = self._plan_payload(plan_ref)
        key = payload.get('preset_revision_ref') if payload is not None else None
        if isinstance(key, str) and key.strip() and key != DEFAULT_PRESET_KEY:
            try:
                return cfg_sources.preset(key)
            except RenderConfigNotSeeded:
                pass
        return cfg_sources.preset(DEFAULT_PRESET_KEY)

    def resolve_inputs(self, input_refs: Sequence[Mapping[str, str]]) -> ResolveInputs:
        output_path_ref = next((r['ref_id'] for r in input_refs if r.get('ref_type') == 'output_path'), 'out-default')
        script_ref = next((r['ref_id'] for r in input_refs if r.get('ref_type') == 'script_version'), None)
        timing_ref = next((r['ref_id'] for r in input_refs if r.get('ref_type') in ('word_timing', 'word_timing_artifact')), None)
        plan_ref = next((r['ref_id'] for r in input_refs if r.get('ref_type') == 'production_plan'), None)
        snapshot_ref = next((r['ref_id'] for r in input_refs if r.get('ref_type') == 'production_snapshot'), 'snap-default')
        meta_ref = next((r['ref_id'] for r in input_refs if r.get('ref_type') == 'output_metadata'), 'meta-default')

        scope = FreshScope(self._manager)
        cfg_sources = ConfigRenderSources(scope, self._workspace_id)
        preset_pin = self._plan_preset(cfg_sources, plan_ref)
        profile_pin = cfg_sources.output_profile()

        timeline = {}
        hook_placement = {}
        subtitle_config = {'karaoke': True}
        allowed_fallbacks = ()
        p_obj = self._plan_payload(plan_ref)
        if p_obj is not None:
            timeline = p_obj.get('timeline') or {}
            hook_placement = p_obj.get('hook_placement') or {}
            subtitle_config = p_obj.get('subtitle_style_intent') or {'karaoke': True}
            allowed_fallbacks = tuple(p_obj.get('allowed_fallbacks') or ())

        art_info = PostgresArtifactInfo(self._manager, workspace_id=self._workspace_id)
        plan_assets = PostgresPlanAssets(self._manager, workspace_id=self._workspace_id)
        refs_in_plan = plan_assets.asset_refs(plan_ref) if plan_ref else ()
        if refs_in_plan is None:
            refs_in_plan = ()

        images = self._image_decisions(input_refs)
        replaced: dict[str, tuple[str, RenderImage]] = {}
        if images is not None:
            timeline, replaced = _image_safe_timeline(timeline, images)
            allowed_fallbacks = (
                *allowed_fallbacks,
                *(_image_fallback_rule(media, original, image) for media, (original, image) in replaced.items()),
            )

        input_artifacts = []
        hook_refs = {hook_placement.get(key) for key in _HOOK_PLACEMENT_REFS} if isinstance(hook_placement, Mapping) else set()
        dropped = {original.lower() for original, _ in replaced.values()} - _visual_version_refs(timeline)
        for aref in refs_in_plan:
            if aref in hook_refs or aref.lower() in dropped:
                continue
            asset = art_info.get_asset(aref)
            if asset is not None:
                input_artifacts.append(asset)

        present = {art.artifact_version_id.lower() for art in input_artifacts}
        for media, (_original, image) in replaced.items():
            replacement = art_info.get_asset(image.artifact_version_id)
            if replacement is None:
                raise ActivityInputError('INPUT_NOT_READY', f'image_version_not_verified:{media}')
            if replacement.artifact_version_id.lower() not in present:
                input_artifacts.append(replacement)
                present.add(replacement.artifact_version_id.lower())

        require_illustration(timeline, images)

        manifest_entries = [
            LocalMaterialRef(artifact_version_id=art.artifact_version_id, local_ref=art.artifact_version_id)
            for art in input_artifacts
        ]

        voice_ref = next((r['ref_id'] for r in input_refs if r.get('ref_type') in ('voice_artifact', 'voice_track')), None)
        if voice_ref is None:
            raise ActivityInputError(INPUT_REF_MISSING, 'voice_artifact')
        voice_version_id = next(
            (
                r['ref_id']
                for r in input_refs
                if r.get('ref_type') == 'artifact_version' and r.get('source_ref_id') == _VOICE_SOURCE_PREFIX + voice_ref
            ),
            None,
        )
        voice_version = art_info.get_asset(voice_version_id) if voice_version_id else None
        if voice_version is None:
            raise ActivityInputError('INPUT_NOT_READY', 'voice_version_not_verified')
        input_artifacts.append(
            ResolvedAsset(
                artifact_version_id=voice_ref,
                sha256=voice_version.sha256,
                size_bytes=voice_version.size_bytes,
                media_type=voice_version.media_type,
                role=voice_version.role,
            )
        )
        manifest_entries.append(LocalMaterialRef(artifact_version_id=voice_ref, local_ref=voice_version.artifact_version_id))
        for hook_asset, hook_entry in self._hook_assets(hook_placement, timeline, art_info):
            input_artifacts.append(hook_asset)
            manifest_entries.append(hook_entry)

        mix_plan, bed_assets, bed_entries = self._bed_mix(input_refs, voice_ref, voice_version.artifact_version_id, preset_pin.preset.mix_rules)
        input_artifacts.extend(bed_assets)
        manifest_entries.extend(bed_entries)

        if timing_ref is None:
            raise ActivityInputError(INPUT_REF_MISSING, 'word_timing')
        timing_payload = self._read_timing_payload(timing_ref)
        if timing_payload is None:
            raise ActivityInputError('INPUT_NOT_READY', 'word_timing_not_found')
        timing_sha256, timing_size = _timing_digest(timing_payload)
        input_artifacts.append(
            ResolvedAsset(
                artifact_version_id=timing_ref,
                sha256=timing_sha256,
                size_bytes=timing_size,
                media_type='application/json',
                role='word_timing',
            )
        )

        script_version_ref = script_ref or 'script-default'
        render_timeline = _timeline_for_render(timeline)
        ass = self._build_ass_material(
            timing_payload,
            script_version_ref,
            timeline=render_timeline,
            hook_placement=hook_placement,
            allowed_fallbacks=allowed_fallbacks,
            plan_ref=plan_ref,
        )
        entries = with_ass_entry(manifest_entries, ass)

        lang_ref = 'lang-' + str(plan_ref or 'default')

        return ResolveInputs(
            production_snapshot_ref=snapshot_ref,
            script_version_ref=script_version_ref,
            production_plan_ref=plan_ref or 'plan-default',
            preset_revision_ref=preset_pin.revision_ref,
            voice_artifact_ref=voice_ref,
            word_timing_ref=timing_ref,
            output_metadata_revision=meta_ref,
            output_profile_revision=profile_pin.revision_ref,
            language_validation_refs=(lang_ref,),
            input_artifacts=tuple(input_artifacts),
            timeline=render_timeline,
            hook_placement=hook_placement,
            subtitle_config=subtitle_config,
            mix_plan=mix_plan,
            allowed_fallbacks=allowed_fallbacks,
            materialization_manifest=entries,
            output_path_ref=output_path_ref,
        )

    def validation_context(self, package: RenderPackageRecord) -> ValidationContext:
        timing_sql = (
            'SELECT payload FROM controlplane.cp_word_timings '
            'WHERE workspace_id = %s::uuid AND timing_artifact_ref = %s '
            'ORDER BY revision DESC LIMIT 1'
        )
        try:
            with self._manager.borrow_connection() as conn:
                row = conn.execute(timing_sql, (self._workspace_id, package.word_timing_ref)).fetchone()
        except Exception:
            row = None
        if row is None:
            raise ActivityInputError('INPUT_NOT_READY', 'word_timing_not_found')

        payload = row[0]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}
        if not isinstance(payload, Mapping):
            payload = {}

        voice_hash = payload.get('voice_hash')
        script_fingerprint = payload.get('script_fingerprint')
        words = payload.get('words') or []
        texts = [w['text'] if isinstance(w, Mapping) else getattr(w, 'text') for w in words]
        subtitle_text_hash = hashlib.sha256(' '.join(texts).encode('utf-8')).hexdigest() if texts else voice_hash

        if not voice_hash or not script_fingerprint or not subtitle_text_hash:
            raise ActivityInputError('INPUT_NOT_READY', 'timing_hashes_missing')

        timing_sha256, timing_size = _timing_digest(payload)

        voice = VoiceTrackInfo(
            voice_artifact_ref=package.voice_artifact_ref,
            script_version_id=package.script_version_ref,
            script_fingerprint=str(script_fingerprint),
            voice_hash=str(voice_hash),
        )
        timing = WordTimingInfo(
            timing_artifact_ref=package.word_timing_ref,
            script_version_id=package.script_version_ref,
            script_fingerprint=str(script_fingerprint),
            voice_hash=str(voice_hash),
        )

        art_info = PostgresArtifactInfo(self._manager, workspace_id=self._workspace_id)
        bed_items = package.mix_plan.get('beds') if isinstance(package.mix_plan, Mapping) else None
        bed_refs = {item.get('rendition_ref') for item in bed_items if isinstance(item, Mapping)} if isinstance(bed_items, (list, tuple)) else set()
        verified: dict[str, VerifiedArtifact] = {}
        manifest = package.materialization_manifest
        for art in package.input_artifacts:
            ref = art.artifact_version_id
            if ref == package.word_timing_ref:
                verified[ref] = VerifiedArtifact(
                    sha256=timing_sha256,
                    size_bytes=timing_size,
                    state=ArtifactLocationState.VERIFIED,
                )
                continue
            if ref in bed_refs:
                bed_entry = manifest.get(ref) if isinstance(manifest, Mapping) else None
                bed_local = bed_entry.get('local_ref') if isinstance(bed_entry, Mapping) else None
                try:
                    flat = resolve_under_root(Path(self._runtime.staging_root), bed_local)
                    verified[ref] = VerifiedArtifact(sha256=sha256_file(flat), size_bytes=flat.stat().st_size, state=ArtifactLocationState.VERIFIED)
                except (OSError, ValueError):
                    pass
                continue
            entry = manifest.get(ref) if isinstance(manifest, Mapping) else None
            local = entry.get('local_ref') if isinstance(entry, Mapping) else None
            lookup = local if isinstance(local, str) and local else ref
            res_asset = art_info.get_asset(lookup)
            if res_asset is not None:
                verified[ref] = VerifiedArtifact(
                    sha256=res_asset.sha256,
                    size_bytes=res_asset.size_bytes,
                    state=ArtifactLocationState.VERIFIED,
                )

        issued_paths = {
            package.output_path_ref: IssuedOutputPath(
                str(self._runtime.staging_root), f'out/{package.render_package_id}.mp4'
            )
        }

        evidence_ref = package.language_validation_refs[0] if package.language_validation_refs else f'lang-{package.render_package_id}'
        req_lang = 'en'
        qc = getattr(self._profile, 'qc', None)
        if qc is not None and hasattr(qc, 'required_language'):
            req_lang = str(getattr(qc, 'required_language'))
        elif hasattr(self._profile, 'parameters') and isinstance(self._profile.parameters, Mapping):
            if 'qc.required_language' in self._profile.parameters:
                req_lang = str(self._profile.parameters['qc.required_language'])

        language_evidence = {
            evidence_ref: LanguageEvidenceView(
                evidence_ref=evidence_ref,
                script_fingerprint=str(script_fingerprint),
                voice_hash=str(voice_hash),
                subtitle_text_hash=str(subtitle_text_hash),
                output_metadata_revision=package.output_metadata_revision,
                voice_locale_reported=f'{req_lang}-US',
            )
        }

        language_policy = LanguageEvidencePolicy(
            required_language=req_lang,
            script_fingerprint=str(script_fingerprint),
            voice_hash=str(voice_hash),
            subtitle_text_hash=str(subtitle_text_hash),
        )

        scope = FreshScope(self._manager)
        cfg_sources = ConfigRenderSources(scope, self._workspace_id)
        preset = self._plan_preset(cfg_sources, package.production_plan_ref).preset

        cap = read_tool_capability(
            ffmpeg_path=self._runtime.ffmpeg_path,
            lock_path=self._runtime.runtime_lock_path,
        )
        if cap is None:
            cap = ToolCapability(filters=frozenset({'subtitles', 'scale'}), encoders=frozenset({'libx264'}))

        return ValidationContext(
            voice=voice,
            word_timing=timing,
            verified=verified,
            issued_paths=issued_paths,
            language_evidence=language_evidence,
            language_policy=language_policy,
            preset=preset,
            capability=cap,
        )

    def render_plan(self, package: RenderPackageRecord, render_attempt_id: str) -> RenderPlan:
        scope = FreshScope(self._manager)
        cfg_sources = ConfigRenderSources(scope, self._workspace_id)
        preset_obj = self._plan_preset(cfg_sources, package.production_plan_ref).preset
        profile_obj = cfg_sources.output_profile().profile

        tool = ToolIdentity(
            name='ffmpeg',
            version=_read_tool_version(self._runtime.runtime_lock_path),
            build='gyan-essentials',
            executable=str(self._runtime.ffmpeg_path),
        )
        output_name = _output_name(render_attempt_id)
        materialized = MaterializedPaths(
            staging_root=str(self._runtime.staging_root),
            output_path=f'out/{output_name}.mp4',
            thumbnail_path=f'out/{output_name}.jpg',
        )
        timing_payload = self._read_timing_payload(package.word_timing_ref)
        if timing_payload is None:
            raise ActivityInputError('INPUT_NOT_READY', 'word_timing_not_found')
        voice_ms = timing_payload.get('voice_duration_ms')
        if isinstance(voice_ms, bool) or not isinstance(voice_ms, int) or voice_ms <= 0:
            raise ActivityInputError('INPUT_NOT_READY', 'voice_duration_missing')
        ass_ref = self._build_ass_material(
            timing_payload,
            package.script_version_ref,
            timeline=package.timeline,
            hook_placement=package.hook_placement,
            allowed_fallbacks=package.allowed_fallbacks,
            plan_ref=package.production_plan_ref,
        ).ass_ref
        spec = build_render_command(
            package,
            preset_obj,
            profile_obj,
            ass_ref,
            tool,
            materialized,
            voice_duration_ms=voice_ms,
        )
        return RenderPlan(command_spec=spec, output_artifact_ref=f'out/{output_name}.mp4')

    def ass_material(self, package: RenderPackageRecord) -> Any:
        p_data = self._read_timing_payload(package.word_timing_ref) or {}
        return self._build_ass_material(
            p_data,
            package.script_version_ref,
            timeline=package.timeline,
            hook_placement=package.hook_placement,
            allowed_fallbacks=package.allowed_fallbacks,
            plan_ref=package.production_plan_ref,
        )

    def ass_ref_for(self, package: RenderPackageRecord) -> str:
        return self.ass_material(package).ass_ref

    def language_source_for(self, package: RenderPackageRecord) -> LanguageSource:
        timing_sql = (
            'SELECT payload FROM controlplane.cp_word_timings '
            'WHERE workspace_id = %s::uuid AND timing_artifact_ref = %s '
            'ORDER BY revision DESC LIMIT 1'
        )
        try:
            with self._manager.borrow_connection() as conn:
                row = conn.execute(timing_sql, (self._workspace_id, package.word_timing_ref)).fetchone()
        except Exception:
            row = None
        if row is None:
            raise ActivityInputError('INPUT_NOT_READY', 'word_timing_not_found')
        p_data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        if not isinstance(p_data, Mapping):
            p_data = {}

        voice_hash = str(p_data.get('voice_hash') or '')
        script_fingerprint = str(p_data.get('script_fingerprint') or '')
        words = p_data.get('words') or []
        texts = [w['text'] if isinstance(w, Mapping) else getattr(w, 'text') for w in words]
        subtitle_text_hash = hashlib.sha256(' '.join(texts).encode('utf-8')).hexdigest() if texts else voice_hash

        if not voice_hash or not script_fingerprint or not subtitle_text_hash:
            raise ActivityInputError('INPUT_NOT_READY', 'timing_hashes_missing')

        req_lang = 'en'
        qc = getattr(self._profile, 'qc', None)
        if qc is not None and hasattr(qc, 'required_language'):
            req_lang = str(getattr(qc, 'required_language'))
        elif hasattr(self._profile, 'parameters') and isinstance(self._profile.parameters, Mapping):
            if 'qc.required_language' in self._profile.parameters:
                req_lang = str(self._profile.parameters['qc.required_language'])

        loc = f'{req_lang}-US' if '-' not in req_lang else req_lang
        ev_ref = package.language_validation_refs[0] if package.language_validation_refs else f'lang-{package.render_package_id}'
        return LanguageSource(
            evidence_ref=ev_ref,
            script_fingerprint=script_fingerprint,
            voice_hash=voice_hash,
            subtitle_text_hash=subtitle_text_hash,
            voice_locale=loc,
            subtitle_locale=loc,
            script_locale=loc,
            title_locale=loc,
            hashtag_locale=loc,
            declared_language=req_lang,
        )

    def quality_inputs(self, package: RenderPackageRecord) -> QualityInputs:
        scope = FreshScope(self._manager)
        cfg_sources = ConfigRenderSources(scope, self._workspace_id)
        policy = cfg_sources.quality_policy().policy

        timing_sql = (
            'SELECT payload FROM controlplane.cp_word_timings '
            'WHERE workspace_id = %s::uuid AND timing_artifact_ref = %s '
            'ORDER BY revision DESC LIMIT 1'
        )
        try:
            with self._manager.borrow_connection() as conn:
                row = conn.execute(timing_sql, (self._workspace_id, package.word_timing_ref)).fetchone()
        except Exception:
            row = None
        if row is None:
            raise ActivityInputError('INPUT_NOT_READY', 'word_timing_not_found')
        p_data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        if not isinstance(p_data, Mapping):
            p_data = {}

        voice_hash = str(p_data.get('voice_hash') or '')
        script_fingerprint = str(p_data.get('script_fingerprint') or '')
        words = p_data.get('words') or []
        texts = [w['text'] if isinstance(w, Mapping) else getattr(w, 'text') for w in words]
        subtitle_text_hash = hashlib.sha256(' '.join(texts).encode('utf-8')).hexdigest() if texts else voice_hash

        if not voice_hash or not script_fingerprint or not subtitle_text_hash:
            raise ActivityInputError('INPUT_NOT_READY', 'timing_hashes_missing')

        exp_lang = ExpectedLanguageRevisions(
            script_fingerprint=script_fingerprint,
            voice_hash=voice_hash,
            subtitle_text_hash=subtitle_text_hash,
        )
        return QualityInputs(policy=policy, expected_language=exp_lang)


def _build_inspector_settings(profile: Any) -> InspectorSettings:
    hook_sim = 0.85
    qc = getattr(profile, 'qc', None)
    if qc is not None and hasattr(qc, 'hook_similarity_min'):
        hook_sim = float(getattr(qc, 'hook_similarity_min'))
    elif hasattr(profile, 'parameters') and isinstance(profile.parameters, Mapping):
        if 'qc.hook_similarity_min' in profile.parameters:
            hook_sim = float(profile.parameters['qc.hook_similarity_min'])

    timeout_s = 60.0
    r_cfg = getattr(profile, 'render', None)
    if r_cfg is not None and hasattr(r_cfg, 'timeout_seconds'):
        timeout_s = float(getattr(r_cfg, 'timeout_seconds'))
    elif hasattr(profile, 'parameters') and isinstance(profile.parameters, Mapping):
        if 'render.timeout_seconds' in profile.parameters:
            timeout_s = float(profile.parameters['render.timeout_seconds'])

    return InspectorSettings(
        compare_width=90,
        compare_height=160,
        thumbnail_min_ssim=hook_sim,
        subtitle_band=Band(top=0.70, bottom=0.80),
        disclosure_band=Band(top=0.10, bottom=0.25),
        overlay_max_missing_share=0.25,
        max_subtitle_samples=4,
        timeout_seconds=timeout_s,
    )


def render_activity_deps(
    services: RenderServices,
    *,
    manager: Any,
    workspace_id: str,
    profile: Any,
    runtime: Any,
    grants: Any,
    clock: Callable[[], datetime.datetime],
) -> RenderActivityDeps:
    uow = ThreadLocalRenderUow(services.uow_factory)
    renderer = StagingResolvingRenderer(services.renderer, runtime.staging_root)
    probe = StagingResolvingProbe(services.probe, runtime.staging_root)
    package_pipe = PackagePipeline(
        uow=uow,
        plan_assets=PostgresPlanAssets(manager, workspace_id=workspace_id),
        grants=grants,
    )
    lease = runtime.gpu_lease
    if isinstance(lease, LocalGpuLease):
        lease = lease.waiting_port()
    render_pipe = RenderPipeline(
        uow=uow,
        renderer=renderer,
        lease=lease,
        probe=probe,
        observer=renderer,
        grants=grants,
    )
    sources = ProductionRenderSources(
        manager=manager,
        workspace_id=workspace_id,
        profile=profile,
        runtime=runtime,
        clock=clock,
    )

    def inspector_factory(package: RenderPackageRecord) -> RealOutputInspector:
        raw_segments = read_script_segments(
            manager,
            workspace_id=workspace_id,
            script_version_ref=package.script_version_ref,
        )
        segments = [
            {'segment_id': s.segment_id, 'claim_mode': s.claim_mode}
            for s in raw_segments
        ]
        inputs = InspectionInputs(
            staging_root=runtime.staging_root,
            ass_ref=sources.ass_ref_for(package),
            segments=segments,
            language=sources.language_source_for(package),
        )
        settings = _build_inspector_settings(profile)
        return RealOutputInspector(
            inputs=inputs,
            settings=settings,
            ffmpeg_path=runtime.ffmpeg_path,
            lock_path=runtime.runtime_lock_path,
        )

    inspector = StagingResolvingInspector(inspector_factory, runtime.staging_root)

    def qc_probe_for(package: RenderPackageRecord) -> StagingResolvingProbe:
        return build_qc_probe(
            runtime,
            timeout_seconds=_build_inspector_settings(profile).timeout_seconds,
            voice_windows=inspector_factory(package).speech_windows(package),
        )

    output_pipe = OutputPipeline(
        uow=uow,
        probe=probe,
        probe_for=qc_probe_for,
        warning_gates=AudioMixGate(
            ffmpeg_path=runtime.ffmpeg_path,
            lock_path=runtime.runtime_lock_path,
            staging_root=runtime.staging_root,
            timeout_seconds=_build_inspector_settings(profile).timeout_seconds,
        ),
        inspector=inspector,
        observer=renderer,
        grants=grants,
    )

    timeout_s = 60.0
    r_cfg = getattr(profile, 'render', None)
    if r_cfg is not None and hasattr(r_cfg, 'timeout_seconds'):
        timeout_s = float(getattr(r_cfg, 'timeout_seconds'))
    elif hasattr(profile, 'parameters') and isinstance(profile.parameters, Mapping):
        if 'render.timeout_seconds' in profile.parameters:
            timeout_s = float(profile.parameters['render.timeout_seconds'])

    inputs = RenderActivityInputs(
        uow_factory=services.uow_factory,
        manager=manager,
        sources=sources,
        actor='render-worker',
        clock=clock,
        orphan_after_seconds=int(timeout_s + 60),
    )
    return RenderActivityDeps(
        package=package_pipe,
        render=render_pipe,
        output=output_pipe,
        grants=grants,
        inputs=inputs,
        clock=clock,
    )


def render_activity_handlers(
    services: RenderServices,
    *,
    manager: Any,
    workspace_id: str,
    profile: Any,
    runtime: Any,
    grants: Any,
    clock: Callable[[], datetime.datetime],
) -> dict[str, Any]:
    deps = render_activity_deps(
        services,
        manager=manager,
        workspace_id=workspace_id,
        profile=profile,
        runtime=runtime,
        grants=grants,
        clock=clock,
    )
    base = render_handler(deps, workspace_id=workspace_id)
    return {
        'resolve_render_package': base,
        'validate_render_package': base,
        'reconcile_render': base,
        'render_video': base,
        'inspect_output': base,
        'prepare_output_ready': base,
    }


__all__ = [
    'RenderServices',
    'build_qc_probe',
    'build_render_services',
    'render_activity_deps',
    'render_activity_handlers',
    'render_supplements',
    'seed_production_render_config',
]
