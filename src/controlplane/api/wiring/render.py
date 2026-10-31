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
import re
import threading
from collections.abc import Mapping, Sequence
from pathlib import Path

from controlplane.api.wiring.workflow import render_handler
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
from render.adapters.config_render_sources import ConfigRenderSources, ass_inputs, seed_render_config
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
from render.adapters.real_ffmpeg_renderer import RealFfmpegRenderer
from render.adapters.real_ffprobe_probe import RealFfprobeProbe
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

    def _build_ass_material(self, timing_payload: Mapping[str, Any], script_version_ref: str) -> Any:
        scope = FreshScope(self._manager)
        cfg_sources = ConfigRenderSources(scope, self._workspace_id)
        preset_obj = cfg_sources.preset('bold-yellow').preset
        profile_obj = cfg_sources.output_profile().profile
        infos = read_script_segments(self._manager, workspace_id=self._workspace_id, script_version_ref=script_version_ref)
        inputs_ass = ass_inputs(preset_obj, profile_obj)
        return build_ass_material(
            staging_root=str(self._runtime.staging_root),
            words=parse_word_timing(timing_payload),
            typography=inputs_ass.typography,
            safe_area=inputs_ass.safe_area,
            profile=inputs_ass.profile,
            disclosure_style=inputs_ass.disclosure_style,
            segments=infos,
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

    def resolve_inputs(self, input_refs: Sequence[Mapping[str, str]]) -> ResolveInputs:
        output_path_ref = next((r['ref_id'] for r in input_refs if r.get('ref_type') == 'output_path'), 'out-default')
        script_ref = next((r['ref_id'] for r in input_refs if r.get('ref_type') == 'script_version'), None)
        timing_ref = next((r['ref_id'] for r in input_refs if r.get('ref_type') in ('word_timing', 'word_timing_artifact')), None)
        plan_ref = next((r['ref_id'] for r in input_refs if r.get('ref_type') == 'production_plan'), None)
        snapshot_ref = next((r['ref_id'] for r in input_refs if r.get('ref_type') == 'production_snapshot'), 'snap-default')
        meta_ref = next((r['ref_id'] for r in input_refs if r.get('ref_type') == 'output_metadata'), 'meta-default')

        scope = FreshScope(self._manager)
        cfg_sources = ConfigRenderSources(scope, self._workspace_id)
        preset_pin = cfg_sources.preset('bold-yellow')
        profile_pin = cfg_sources.output_profile()

        timeline = {}
        hook_placement = {}
        subtitle_config = {'karaoke': True}
        allowed_fallbacks = ()
        plan_sql = (
            'SELECT payload FROM controlplane.cp_production_plans '
            'WHERE workspace_id = %s::uuid AND production_plan_id = %s '
            'ORDER BY revision DESC LIMIT 1'
        )
        if plan_ref:
            try:
                with self._manager.borrow_connection() as conn:
                    prow = conn.execute(plan_sql, (self._workspace_id, plan_ref)).fetchone()
                if prow is not None:
                    raw_p = prow[0]
                    p_obj = json.loads(raw_p) if isinstance(raw_p, str) else raw_p
                    if isinstance(p_obj, Mapping):
                        timeline = p_obj.get('timeline') or {}
                        hook_placement = p_obj.get('hook_placement') or {}
                        subtitle_config = p_obj.get('subtitle_style_intent') or {'karaoke': True}
                        allowed_fallbacks = tuple(p_obj.get('allowed_fallbacks') or ())
            except Exception:
                pass

        art_info = PostgresArtifactInfo(self._manager, workspace_id=self._workspace_id)
        plan_assets = PostgresPlanAssets(self._manager, workspace_id=self._workspace_id)
        refs_in_plan = plan_assets.asset_refs(plan_ref) if plan_ref else ()
        if refs_in_plan is None:
            refs_in_plan = ()

        input_artifacts = []
        hook_refs = {hook_placement.get(key) for key in _HOOK_PLACEMENT_REFS} if isinstance(hook_placement, Mapping) else set()
        for aref in refs_in_plan:
            if aref in hook_refs:
                continue
            asset = art_info.get_asset(aref)
            if asset is not None:
                input_artifacts.append(asset)
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
        ass = self._build_ass_material(timing_payload, script_version_ref)
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
            timeline=_timeline_for_render(timeline),
            hook_placement=hook_placement,
            subtitle_config=subtitle_config,
            mix_plan={},
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
        preset = cfg_sources.preset('bold-yellow').preset

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
        preset_obj = cfg_sources.preset('bold-yellow').preset
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
        ass_ref = self.ass_material(package).ass_ref
        spec = build_render_command(
            package,
            preset_obj,
            profile_obj,
            ass_ref,
            tool,
            materialized,
        )
        return RenderPlan(command_spec=spec, output_artifact_ref=f'out/{output_name}.mp4')

    def ass_material(self, package: RenderPackageRecord) -> Any:
        p_data = self._read_timing_payload(package.word_timing_ref) or {}
        return self._build_ass_material(p_data, package.script_version_ref)

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
        subtitle_min_difference=5.0,
        disclosure_band=Band(top=0.10, bottom=0.25),
        disclosure_min_difference=5.0,
        baseline_min_gap_ms=400,
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
    output_pipe = OutputPipeline(
        uow=uow,
        probe=probe,
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
    'build_render_services',
    'render_activity_deps',
    'render_activity_handlers',
    'render_supplements',
    'seed_production_render_config',
]
