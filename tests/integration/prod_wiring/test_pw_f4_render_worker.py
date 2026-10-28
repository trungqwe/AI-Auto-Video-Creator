"""PW-F4: one GPU slot per render, reconcile_render of an orphaned STARTED attempt, prepare_output_ready after QC and the F ActivityInputPort, on real PostgreSQL 18.6 and the pinned FFmpeg; no fake renderer in the QC path.

coveredIds: PW-F4-01, CT-QC-001, F-19
"""
from __future__ import annotations

import ast
import dataclasses
import datetime
import hashlib
import os
import pathlib
import subprocess
import threading
import time
from collections.abc import Mapping, Sequence
from functools import partial
from types import SimpleNamespace
from typing import Any

import pytest

# Pre-set M2_TEST_PG_DSN if not in environment
if not os.environ.get('M2_TEST_PG_DSN'):
    _port = '56986'
    try:
        _res = subprocess.run(['docker', 'port', 'ai-auto-video-m2-pg', '5432/tcp'], capture_output=True, text=True, check=False)
        if _res.returncode == 0 and _res.stdout.strip():
            _port = _res.stdout.strip().split(':')[-1]
    except Exception:
        pass
    os.environ['M2_TEST_PG_DSN'] = f'postgresql://m2test:m2test@127.0.0.1:{_port}/postgres'

from controlplane.application.orchestration.workflows.activities import (
    BINDINGS_BY_NAME,
    VIDEO_STAGE_ACTIVITIES,
)
from controlplane.domain.orchestration import ExecutionGrant
from controlplane.domain.statemachine import ArtifactLocationState, OperationState
from controlplane.infrastructure.db.control_api_commands import compose_command_service
from controlplane.infrastructure.db.uow import TransactionManager
from controlplane.infrastructure.production_ports.gpu_lease import LocalGpuLease
from render.adapters.activity_inputs import (
    ActivityInputError,
    QualityInputs,
    RenderActivityInputs,
    RenderInputSources,
    RenderPlan,
)
from render.adapters.ass_manifest import build_ass_material, with_ass_entry
from render.adapters.config_render_sources import ass_inputs
from render.adapters.postgres_plan_assets import (
    PostgresArtifactInfo,
    PostgresPlanAssets,
    ScriptSegmentInfo,
)
from render.adapters.real_ffmpeg_renderer import RealFfmpegRenderer
from render.adapters.real_ffprobe_probe import RealFfprobeProbe
from render.adapters.real_output_inspector import (
    InspectionInputs,
    InspectorSettings,
    LanguageSource,
    RealOutputInspector,
)
from render.application.inspect_output import (
    InspectOutputCommand,
    OutputPipeline,
    PrepareOutputReadyCommand,
)
from render.application.package_pipeline import (
    CommandContext,
    PackagePipeline,
    ResolveRenderPackageCommand,
    ValidateRenderPackageCommand,
)
from render.application.render_video import (
    GpuLeaseNotAvailable,
    ReconcileRenderCommand,
    RenderPipeline,
    RenderVideoCommand,
)
from render.domain.content_gates import ExpectedLanguageRevisions
from render.domain.package_contract import RenderPackageRecord
from render.domain.quality_report import (
    GATE_KINDS,
    GATE_ORDER,
    GateKind,
    GateName,
    GateResult,
    GateStatus,
    QualityPolicy,
    QualityReport,
    build_quality_report,
)
from render.domain.render_command import (
    MaterializedPaths,
    RenderCommandSpec,
    ToolIdentity,
    build_render_command,
)
from render.domain.validate_package import (
    IssuedOutputPath,
    LanguageEvidencePolicy,
    LanguageEvidenceView,
    ToolCapability,
    ValidationContext,
    VerifiedArtifact,
    VoiceTrackInfo,
    WordTimingInfo,
)
from render.persistence.unit_of_work import PostgresRenderUnitOfWork
from render.ports.inputs import LocalMaterialRef, ResolveInputs, ResolvedAsset
from render.ports.lease import GPU_LOCK_ID, GpuLease, GpuLeasePort, GpuLeaseUnavailable
from render.ports.renderer import RendererOutcome
from render.ports.repositories import KIND_ATTEMPT, KIND_PACKAGE, KIND_QUALITY_REPORT
from render.worker.activity_handler import (
    ACTIVITY_NAMES,
    RenderActivityDeps,
    handle_activity,
)
from tests.integration.prod_wiring.test_pw_f1_inspector_visual import (
    Band,
    InspectorSettings,
)
from tests.integration.prod_wiring.test_pw_f3_render_inputs import (
    DISCLOSURE,
    PARAMS,
    PLAN_ID,
    SCRIPT_ID,
    SUPPLEMENTS,
    TIMING_REF,
    V1,
    V2,
    VOICE,
    WORDS,
    base_entries,
    insert_artifact,
    insert_plan,
    insert_script,
    insert_timing,
    read_words,
    resolve_inputs,
    script_segments_payload,
    seed,
    sources,
    timing_payload,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
LOCK_PATH = ROOT / 'tools' / 'runtime' / 'runtime.lock.json'
FFMPEG = pathlib.Path('C:/ffmpeg/bin/ffmpeg.exe')
FFPROBE = pathlib.Path('C:/ffmpeg/bin/ffprobe.exe')

SETTINGS = InspectorSettings(
    compare_width=90,
    compare_height=160,
    thumbnail_min_ssim=0.8,
    subtitle_band=Band(top=0.70, bottom=0.80),
    subtitle_min_difference=5.0,
    disclosure_band=Band(top=0.10, bottom=0.25),
    disclosure_min_difference=5.0,
    baseline_min_gap_ms=400,
    max_subtitle_samples=4,
    timeout_seconds=60,
)


def require_ffmpeg() -> None:
    if not FFMPEG.is_file():
        pytest.fail(
            'BLOCKED_EXTERNAL: pinned FFmpeg C:/ffmpeg/bin/ffmpeg.exe is required; no skip and no fallback is permitted.',
            pytrace=False,
        )


def ffmpeg(*args: str) -> None:
    result = subprocess.run(
        [str(FFMPEG), '-hide_banner', '-nostdin', '-v', 'error', '-y', *args],
        capture_output=True,
        stdin=subprocess.DEVNULL,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr


@pytest.fixture
def service(pw_database):
    mgr = TransactionManager(pw_database.dsn, pool_max_size=4)
    try:
        yield compose_command_service(mgr.unit_of_work)
    finally:
        mgr.close()


@pytest.fixture
def manager(pw_database):
    mgr = TransactionManager(pw_database.dsn, pool_max_size=4)
    try:
        yield mgr
    finally:
        mgr.close()


class FakeGpu:
    def __init__(self, slots: int, ttl: float = 600.0) -> None:
        self.underlying = LocalGpuLease(slots, ttl)
        self.acquires = 0
        self.refused = 0
        self.held = 0
        self.max_held = 0
        self.leases: list[GpuLease] = []
        self.hold = threading.Event()
        self.hold.set()
        self._lock = threading.Lock()

    def acquire(self, owner_ref: str) -> GpuLease:
        with self._lock:
            try:
                lease = self.underlying.acquire(owner_ref)
            except GpuLeaseUnavailable:
                self.refused += 1
                raise
            self.acquires += 1
            self.held += 1
            if self.held > self.max_held:
                self.max_held = self.held
            self.leases.append(lease)
            return lease

    def release(self, lease: GpuLease) -> None:
        self.hold.wait(timeout=120)
        with self._lock:
            self.underlying.release(lease)
            self.held -= 1


class WorkerDied(BaseException):
    pass


class AlwaysCurrent:
    def is_grant_current(self, grant: object) -> bool:
        return True


def make_grant(db: Any) -> ExecutionGrant:
    return ExecutionGrant(
        workspace_id=db.workspace_id,
        operation_id='op-grant-1',
        job_id='job-1',
        stage_run_id='stage-1',
        execution_generation=2,
        recovery_epoch=1,
    )


class ThreadLocalUow:
    def __init__(self, factory: Any) -> None:
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



class StagedProbe:
    def __init__(self, probe: Any, staging: pathlib.Path) -> None:
        self._probe = probe
        self._staging = staging

    def probe(self, output_ref: str) -> Any:
        p = pathlib.Path(output_ref)
        if not p.is_file() and (self._staging / p).is_file():
            p = self._staging / p
        return self._probe.probe(str(p))


class StagedInspector:
    def __init__(self, inspector: Any, staging: pathlib.Path) -> None:
        self._inspector = inspector
        self._staging = staging

    def inspect(self, output_ref: str, package: Any) -> Any:
        p = pathlib.Path(output_ref)
        if not p.is_file() and (self._staging / p).is_file():
            p = self._staging / p
        return self._inspector.inspect(str(p), package)


class StagedRenderer:
    takes_held_lease = True

    def __init__(self, renderer: Any, staging: pathlib.Path) -> None:
        self._renderer = renderer
        self._staging = staging

    @property
    def last_encoder(self) -> Any:
        return getattr(self._renderer, 'last_encoder', None)

    def run(self, spec: Any, *, lease: GpuLease) -> Any:
        return self._renderer.run(spec, lease=lease)

    def observe(self, output_ref: str) -> Any:
        p = pathlib.Path(output_ref)
        if not p.is_file() and (self._staging / p).is_file():
            p = self._staging / p
        return self._renderer.observe(str(p))


class World:
    def __init__(
        self,
        db: Any,
        manager: Any,
        service: Any,
        tmp_path: pathlib.Path,
        script_modes: Sequence[str],
        ass_modes: Sequence[str] | None = None,
        gpu: Any = None,
        orphan_after_seconds: int = 0,
    ) -> None:
        require_ffmpeg()
        self.db = db
        self.manager = manager
        self.service = service
        self.tmp_path = tmp_path
        self.script_modes = tuple(script_modes)
        self.ass_modes = tuple(script_modes) if ass_modes is None else tuple(ass_modes)
        self.gpu = gpu or FakeGpu(2)
        self.orphan_after_seconds = orphan_after_seconds

        # 1. seed
        seed(service, db)
        self.sources = sources(db)

        # 2. insert artifacts V1, V2, VOICE
        insert_artifact(db, V1, kind='visual', mime='video/mp4')
        insert_artifact(db, V2, kind='visual', mime='video/mp4')
        insert_artifact(db, VOICE, kind='voice', mime='audio/wav')

        # 3. insert plan
        insert_plan(
            db,
            {
                'timeline': {
                    'segments': [
                        {'visuals': [{'artifact_version_ref': V1}]},
                        {'visuals': [{'artifact_version_ref': V2}]},
                    ]
                },
                'hook_placement': {
                    'visual_hook_ref': V1,
                    'audio_hook_ref': VOICE,
                    'thumbnail_ref': V1,
                },
                'allowed_fallbacks': [],
            },
            plan_id=PLAN_ID,
        )

        # 4. script and timing
        total = len(WORDS)
        n = len(self.script_modes)
        base_cnt = total // n
        rem = total % n
        counts = [base_cnt + (1 if i < rem else 0) for i in range(n)]
        insert_script(db, script_segments_payload(self.script_modes, counts), script_id=SCRIPT_ID)
        insert_timing(db)

        # 5. create files in tmp_path / 'staging'
        self.staging = tmp_path / 'staging'
        self.staging.mkdir(parents=True, exist_ok=True)
        (self.staging / 'out').mkdir(parents=True, exist_ok=True)

        v1_path = self.staging / 'visual-1.mp4'
        if not v1_path.exists():
            ffmpeg('-f', 'lavfi', '-i', 'testsrc2=size=1080x1920:rate=30', '-t', '3', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(v1_path))
        v2_path = self.staging / 'visual-2.mp4'
        if not v2_path.exists():
            ffmpeg('-f', 'lavfi', '-i', 'testsrc2=size=1080x1920:rate=30', '-t', '3', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(v2_path))
        voice_path = self.staging / 'voice.wav'
        if not voice_path.exists():
            ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=1000:duration=4', '-c:a', 'pcm_s16le', str(voice_path))

        # 6. build ass
        words = read_words(db)
        pins = (self.sources.preset('bold-yellow'), self.sources.output_profile())
        inp = ass_inputs(pins[0].preset, pins[1].profile)
        n_ass = len(self.ass_modes)
        base_ass = total // n_ass
        rem_ass = total % n_ass
        ass_counts = [base_ass + (1 if i < rem_ass else 0) for i in range(n_ass)]
        ass_segments = tuple(
            ScriptSegmentInfo(
                segment_id=f'seg-{i}',
                order=i,
                claim_mode=mode,
                disclosure=DISCLOSURE if mode in ('inference', 'creative_hypothesis') else None,
                word_count=ass_counts[i],
            )
            for i, mode in enumerate(self.ass_modes)
        )
        self.ass = build_ass_material(
            staging_root=str(self.staging.resolve()),
            words=words,
            typography=inp.typography,
            safe_area=inp.safe_area,
            profile=inp.profile,
            disclosure_style=inp.disclosure_style,
            segments=ass_segments,
        )

        # 7. wiring & components
        self.uow_factory = partial(PostgresRenderUnitOfWork, manager, workspace_id=db.workspace_id)
        real_renderer = RealFfmpegRenderer(lease=self.gpu, ffmpeg_path=str(FFMPEG), lock_path=LOCK_PATH, timeout_seconds=300)
        real_probe = RealFfprobeProbe(ffprobe_path=str(FFPROBE), timeout_seconds=300)
        self.renderer = StagedRenderer(real_renderer, self.staging)
        self.probe = StagedProbe(real_probe, self.staging)
        self.inputs = RenderActivityInputs(
            uow_factory=self.uow_factory,
            manager=self.manager,
            sources=self,
            actor='pw-f4',
            clock=lambda: datetime.datetime.now(datetime.timezone.utc),
            orphan_after_seconds=self.orphan_after_seconds,
        )

    def resolve_inputs(self, refs: Sequence[Mapping[str, str]]) -> ResolveInputs:
        output_path_ref = next((r['ref_id'] for r in refs if r.get('ref_type') == 'output_path'), 'out-default')
        script_ref = next((r['ref_id'] for r in refs if r.get('ref_type') == 'script_version'), SCRIPT_ID)
        timing_ref = next((r['ref_id'] for r in refs if r.get('ref_type') == 'word_timing'), TIMING_REF)
        manifest = with_ass_entry(base_entries(), self.ass)
        pins = (self.sources.preset('bold-yellow'), self.sources.output_profile())
        base = resolve_inputs(self.db, self.manager, pins, manifest)
        timing_asset = ResolvedAsset(
            artifact_version_id=timing_ref,
            sha256='c' * 64,
            size_bytes=1024,
            media_type='application/json',
            role='timing',
        )
        return dataclasses.replace(
            base,
            output_path_ref=output_path_ref,
            script_version_ref=script_ref,
            word_timing_ref=timing_ref,
            input_artifacts=(*base.input_artifacts, timing_asset),
        )

    def validation_context(self, package: RenderPackageRecord) -> ValidationContext:
        record = package
        voice = VoiceTrackInfo(
            voice_artifact_ref=record.voice_artifact_ref,
            script_version_id=record.script_version_ref,
            script_fingerprint='a' * 64,
            voice_hash='b' * 64,
        )
        timing = WordTimingInfo(
            timing_artifact_ref=record.word_timing_ref,
            script_version_id=record.script_version_ref,
            script_fingerprint='a' * 64,
            voice_hash='b' * 64,
        )
        verified = {
            art.artifact_version_id: VerifiedArtifact(sha256=art.sha256, size_bytes=art.size_bytes, state=ArtifactLocationState.VERIFIED)
            for art in record.input_artifacts
        }
        issued_paths = {
            record.output_path_ref: IssuedOutputPath(str(self.staging), f'out/{record.render_package_id}.mp4')
        }
        evidence_ref = record.language_validation_refs[0] if record.language_validation_refs else 'lang-f3'
        language_evidence = {
            evidence_ref: LanguageEvidenceView(
                evidence_ref=evidence_ref,
                script_fingerprint='a' * 64,
                voice_hash='b' * 64,
                subtitle_text_hash='b' * 64,
                output_metadata_revision=record.output_metadata_revision,
                voice_locale_reported='en-US',
            )
        }
        language_policy = LanguageEvidencePolicy(
            required_language='en',
            script_fingerprint='a' * 64,
            voice_hash='b' * 64,
            subtitle_text_hash='b' * 64,
        )
        preset = SimpleNamespace(
            compatibility_requirements={'required_filters': ['subtitles'], 'required_encoders': ['libx264']}
        )
        capability = ToolCapability(filters=frozenset({'subtitles', 'scale'}), encoders=frozenset({'libx264'}))
        return ValidationContext(
            voice=voice,
            word_timing=timing,
            verified=verified,
            issued_paths=issued_paths,
            language_evidence=language_evidence,
            language_policy=language_policy,
            preset=preset,
            capability=capability,
        )

    def render_plan(self, package: RenderPackageRecord, render_attempt_id: str) -> RenderPlan:
        preset = self.sources.preset('bold-yellow').preset
        profile = self.sources.output_profile().profile
        tool = ToolIdentity(name='ffmpeg', version='2025-03-13', build='gyan-essentials', executable=str(FFMPEG))
        materialized = MaterializedPaths(
            staging_root=str(self.staging),
            output_path=f'out/{render_attempt_id}.mp4',
            thumbnail_path=f'out/{render_attempt_id}.jpg',
        )
        spec = build_render_command(package, preset, profile, self.ass.ass_ref, tool, materialized)
        return RenderPlan(command_spec=spec, output_artifact_ref=f'out/{render_attempt_id}.mp4')

    def quality_inputs(self, package: RenderPackageRecord) -> QualityInputs:
        policy = self.sources.quality_policy().policy
        exp_lang = ExpectedLanguageRevisions(
            script_fingerprint='a' * 64,
            voice_hash='b' * 64,
            subtitle_text_hash='b' * 64,
        )
        return QualityInputs(policy=policy, expected_language=exp_lang)

    def make_deps(
        self,
        *,
        renderer: Any = None,
        inputs: Any = None,
        inspector: Any = None,
    ) -> RenderActivityDeps:
        effective_renderer = renderer or self.renderer
        effective_inputs = inputs or self.inputs
        segments_for_qc = tuple(
            {'segment_id': f'seg-{i}', 'claim_mode': mode}
            for i, mode in enumerate(self.script_modes)
        )
        effective_inspector = inspector or RealOutputInspector(
            inputs=InspectionInputs(
                staging_root=self.staging,
                ass_ref=self.ass.ass_ref,
                segments=segments_for_qc,
                language=LanguageSource(
                    evidence_ref='lang-f3',
                    script_fingerprint='a' * 64,
                    voice_hash='b' * 64,
                    subtitle_text_hash='b' * 64,
                    voice_locale='en-US',
                    subtitle_locale='en-US',
                    script_locale='en-US',
                    title_locale='en-US',
                    hashtag_locale='en-US',
                    declared_language='en',
                ),
            ),
            settings=SETTINGS,
            lock_path=LOCK_PATH,
        )
        grants = AlwaysCurrent()
        uow_wrapper = ThreadLocalUow(self.uow_factory)
        package_pipe = PackagePipeline(
            uow=uow_wrapper,
            plan_assets=PostgresPlanAssets(self.manager, workspace_id=self.db.workspace_id),
            grants=grants,
        )
        staged_renderer = StagedRenderer(effective_renderer, self.staging)
        staged_inspector = StagedInspector(effective_inspector, self.staging)
        render_pipe = RenderPipeline(
            uow=uow_wrapper,
            renderer=staged_renderer,
            lease=self.gpu,
            probe=self.probe,
            observer=staged_renderer,
            grants=grants,
        )
        output_pipe = OutputPipeline(
            uow=uow_wrapper,
            probe=self.probe,
            inspector=staged_inspector,
            observer=staged_renderer,
            grants=grants,
        )
        return RenderActivityDeps(
            package=package_pipe,
            render=render_pipe,
            output=output_pipe,
            grants=grants,
            inputs=effective_inputs,
            clock=lambda: datetime.datetime.now(datetime.timezone.utc),
        )

    def activity(
        self,
        deps: RenderActivityDeps,
        name: str,
        key: str,
        refs: Sequence[Mapping[str, str]],
        *,
        stage_run_id: str = 'stage-1',
    ) -> dict[str, Any]:
        grant = make_grant(self.db)
        request = {
            'workflow_id': 'wf-1',
            'workflow_run_id': 'run-1',
            'stage_run_id': stage_run_id,
            'activity_name': name,
            'activity_version': '1',
            'input_refs': list(refs),
            'operation_key': key,
            'capability_requirements': {},
            'retry_policy_ref': 'retry-1',
        }
        return handle_activity(request, grant, deps)

    def new_package(self, tag: str, **kwargs) -> str:
        grant = make_grant(self.db)
        ctx = CommandContext(
            workspace_id=self.db.workspace_id,
            correlation_id=f'corr-{tag}',
            actor='tester',
            occurred_at='2026-01-01T00:00:00+00:00',
        )
        refs = [{'ref_type': 'output_path', 'ref_id': f'out-{tag}'}]
        for k, v in kwargs.items():
            refs.append({'ref_type': k, 'ref_id': v})
        inputs = self.resolve_inputs(refs)
        uow = self.uow_factory()
        pipeline = PackagePipeline(
            uow=uow,
            plan_assets=PostgresPlanAssets(self.manager, workspace_id=self.db.workspace_id),
            grants=AlwaysCurrent(),
        )
        res = pipeline.resolve_render_package(
            ResolveRenderPackageCommand(
                operation_key=f'resolve-{tag}',
                grant=grant,
                inputs=inputs,
                context=ctx,
            )
        )
        pkg_id = res.receipt.render_package_id
        with self.uow_factory() as uow_read:
            pkg_record = uow_read.renders.latest(KIND_PACKAGE, pkg_id).record
        pipeline.validate_render_package(
            ValidateRenderPackageCommand(
                operation_key=f'validate-{tag}',
                grant=grant,
                render_package_id=pkg_id,
                validation_context=self.validation_context(pkg_record),
                context=ctx,
            )
        )
        return pkg_id


def test_module_docstring_declares_covered_ids() -> None:
    doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
    assert doc is not None
    lines = [line for line in doc.splitlines() if line.startswith('coveredIds:')]
    assert len(lines) == 1
    ids = {x.strip() for x in lines[0][len('coveredIds:'):].split(',')}
    assert {'PW-F4-01', 'CT-QC-001', 'F-19'} <= ids


def test_one_render_takes_exactly_one_gpu_slot(pw_database: Any, manager: Any, service: Any, tmp_path: pathlib.Path) -> None:
    gpu = FakeGpu(2)
    world = World(pw_database, manager, service, tmp_path, script_modes=['source_backed'], gpu=gpu)
    seen: list[GpuLease] = []

    class SpyRenderer(RealFfmpegRenderer):
        def run(self, spec: Any, *, lease: GpuLease) -> Any:
            seen.append(lease)
            return super().run(spec, lease=lease)

    spy = SpyRenderer(lease=gpu, ffmpeg_path=str(FFMPEG), lock_path=LOCK_PATH, timeout_seconds=300)
    pipe = RenderPipeline(
        uow=world.uow_factory(),
        renderer=spy,
        lease=gpu,
        probe=world.probe,
        observer=world.renderer,
        grants=AlwaysCurrent(),
    )
    pkg_id = world.new_package('slot-1')
    with world.uow_factory() as uow:
        pkg = uow.renders.latest(KIND_PACKAGE, pkg_id).record
    plan = world.render_plan(pkg, 'att-slot-1')
    grant = make_grant(pw_database)
    ctx = CommandContext(
        workspace_id=pw_database.workspace_id,
        correlation_id='corr-slot-1',
        actor='tester',
        occurred_at='2026-01-01T00:00:00+00:00',
    )
    cmd = RenderVideoCommand(
        grant=grant,
        render_package_id=pkg_id,
        render_attempt_id='att-slot-1',
        output_artifact_ref=plan.output_artifact_ref,
        receipt_ref='receipt-slot-1',
        command_spec=plan.command_spec,
        context=ctx,
        validation_context=world.validation_context(pkg),
    )
    res = pipe.render_video(cmd)
    assert res.attempt.receipt_state == OperationState.SUCCEEDED, res.attempt.error
    assert (world.staging / plan.output_artifact_ref).is_file()
    assert gpu.acquires == 1
    assert gpu.max_held == 1
    assert gpu.held == 0
    assert len(seen) == 1
    assert seen[0] is gpu.leases[0]
    assert seen[0].lock_id == GPU_LOCK_ID


def test_two_concurrent_renders_use_two_slots_and_the_third_waits(pw_database: Any, manager: Any, service: Any, tmp_path: pathlib.Path) -> None:
    gpu = FakeGpu(2)
    gpu.hold.clear()
    world = World(pw_database, manager, service, tmp_path, script_modes=['source_backed'], gpu=gpu)

    pipe = RenderPipeline(
        uow=ThreadLocalUow(world.uow_factory),
        renderer=world.renderer,
        lease=gpu,
        probe=world.probe,
        observer=world.renderer,
        grants=AlwaysCurrent(),
    )

    pkg1 = world.new_package('c-1')
    pkg2 = world.new_package('c-2')
    pkg3 = world.new_package('c-3')

    with world.uow_factory() as uow:
        p1 = uow.renders.latest(KIND_PACKAGE, pkg1).record
        p2 = uow.renders.latest(KIND_PACKAGE, pkg2).record
        p3 = uow.renders.latest(KIND_PACKAGE, pkg3).record

    plan1 = world.render_plan(p1, 'att-c-1')
    plan2 = world.render_plan(p2, 'att-c-2')
    plan3 = world.render_plan(p3, 'att-c-3')

    grant = make_grant(pw_database)
    ctx = CommandContext(workspace_id=pw_database.workspace_id, correlation_id='corr-c', actor='tester', occurred_at='2026-01-01T00:00:00+00:00')

    cmd1 = RenderVideoCommand(
        grant=grant, render_package_id=pkg1, render_attempt_id='att-c-1',
        output_artifact_ref=plan1.output_artifact_ref, receipt_ref='receipt-c-1',
        command_spec=plan1.command_spec, context=ctx, validation_context=world.validation_context(p1),
    )
    cmd2 = RenderVideoCommand(
        grant=grant, render_package_id=pkg2, render_attempt_id='att-c-2',
        output_artifact_ref=plan2.output_artifact_ref, receipt_ref='receipt-c-2',
        command_spec=plan2.command_spec, context=ctx, validation_context=world.validation_context(p2),
    )
    cmd3 = RenderVideoCommand(
        grant=grant, render_package_id=pkg3, render_attempt_id='att-c-3',
        output_artifact_ref=plan3.output_artifact_ref, receipt_ref='receipt-c-3',
        command_spec=plan3.command_spec, context=ctx, validation_context=world.validation_context(p3),
    )

    t1 = threading.Thread(target=pipe.render_video, args=(cmd1,))
    t2 = threading.Thread(target=pipe.render_video, args=(cmd2,))

    t1.start()
    t2.start()

    try:
        deadline = time.time() + 120
        out1 = world.staging / plan1.output_artifact_ref
        out2 = world.staging / plan2.output_artifact_ref
        out3 = world.staging / plan3.output_artifact_ref
        while time.time() < deadline:
            if gpu.acquires == 2 and out1.is_file() and out2.is_file():
                break
            time.sleep(0.1)
        assert gpu.acquires == 2
        assert out1.is_file()
        assert out2.is_file()

        with pytest.raises(GpuLeaseNotAvailable) as exc_info:
            pipe.render_video(cmd3)
        assert exc_info.value.code == 'gpu_lease_unavailable'
        assert exc_info.value.problem.values.get('retryable') is True
        assert gpu.refused == 1
        assert gpu.acquires == 2
        assert not out3.is_file()
    finally:
        gpu.hold.set()
        t1.join(timeout=30)
        t2.join(timeout=30)

    res3 = pipe.render_video(cmd3)
    assert res3.attempt.receipt_state == OperationState.SUCCEEDED
    assert gpu.acquires == 3
    assert gpu.max_held == 2


def test_f_activities_are_bound_and_staged() -> None:
    expected_f = (
        'resolve_render_package',
        'validate_render_package',
        'reconcile_render',
        'render_video',
        'inspect_output',
        'prepare_output_ready',
    )
    for name in expected_f:
        assert name in BINDINGS_BY_NAME
        binding = BINDINGS_BY_NAME[name]
        assert binding.owner == 'F'

    assert 'reconcile_render' in VIDEO_STAGE_ACTIVITIES['render']
    assert 'prepare_output_ready' in VIDEO_STAGE_ACTIVITIES['qc']

    for name in expected_f:
        assert name in ACTIVITY_NAMES
    assert len(ACTIVITY_NAMES) == 6


def test_orphaned_started_attempt_is_concluded_and_the_next_render_runs(pw_database: Any, manager: Any, service: Any, tmp_path: pathlib.Path) -> None:
    world = World(pw_database, manager, service, tmp_path, script_modes=['source_backed'], orphan_after_seconds=3600)
    pkg_id = world.new_package('orphan-test')

    class DyingRenderer:
        takes_held_lease = True
        def __init__(self, observer: Any) -> None:
            self._observer = observer
        def run(self, spec: Any, *, lease: GpuLease) -> Any:
            raise WorkerDied('simulated crash')
        def observe(self, output_ref: str) -> Any:
            return self._observer.observe(output_ref)

    dying = DyingRenderer(world.renderer)
    deps_dying = world.make_deps(renderer=dying)

    with pytest.raises(WorkerDied):
        world.activity(deps_dying, 'render_video', 'attempt-1', [{'ref_type': 'render_package', 'ref_id': pkg_id}])

    with world.uow_factory() as uow:
        att1 = uow.renders.latest(KIND_ATTEMPT, 'attempt-1').record
        assert att1.receipt_state == OperationState.STARTED
    assert world.gpu.held == 0

    deps_real = world.make_deps()
    res_blocked = world.activity(deps_real, 'render_video', 'attempt-blocked', [{'ref_type': 'render_package', 'ref_id': pkg_id}])
    assert res_blocked['disposition'] == 'failed'
    assert res_blocked['problem']['code'] == 'attempt_in_progress'

    inputs_3600 = RenderActivityInputs(
        uow_factory=world.uow_factory,
        manager=world.manager,
        sources=world,
        actor='pw-f4',
        clock=lambda: datetime.datetime.now(datetime.timezone.utc),
        orphan_after_seconds=3600,
    )
    deps_3600 = world.make_deps(inputs=inputs_3600)
    res_recon_young = world.activity(deps_3600, 'reconcile_render', 'recon-young', [{'ref_type': 'render_package', 'ref_id': pkg_id}])
    assert res_recon_young['disposition'] == 'failed'
    assert res_recon_young['problem']['code'] == 'attempt_in_progress'
    with world.uow_factory() as uow:
        att1_again = uow.renders.latest(KIND_ATTEMPT, 'attempt-1').record
        assert att1_again.receipt_state == OperationState.STARTED

    inputs_0 = RenderActivityInputs(
        uow_factory=world.uow_factory,
        manager=world.manager,
        sources=world,
        actor='pw-f4',
        clock=lambda: datetime.datetime.now(datetime.timezone.utc),
        orphan_after_seconds=0,
    )
    deps_0 = world.make_deps(inputs=inputs_0)
    res_recon_old = world.activity(deps_0, 'reconcile_render', 'recon-old', [{'ref_type': 'render_package', 'ref_id': pkg_id}])
    assert res_recon_old['disposition'] == 'succeeded'
    assert res_recon_old['metrics']['reconciled_state'] == 'failed'

    with world.uow_factory() as uow:
        att1_failed = uow.renders.latest(KIND_ATTEMPT, 'attempt-1').record
        assert att1_failed.receipt_state == OperationState.FAILED
        assert 'output_missing' in att1_failed.error
        for att_id in uow.attempt_index.ids(att1_failed.package_fingerprint):
            st = uow.renders.latest(KIND_ATTEMPT, att_id).record.receipt_state
            assert st not in (OperationState.STARTED, OperationState.OUTCOME_UNKNOWN)

    res_att2 = world.activity(deps_real, 'render_video', 'attempt-2', [{'ref_type': 'render_package', 'ref_id': pkg_id}])
    assert res_att2['disposition'] == 'succeeded'
    assert any(r['ref_type'] == 'render_output' for r in res_att2['output_refs'])


def test_reconcile_without_an_open_attempt_is_a_no_op_success(pw_database: Any, manager: Any, service: Any, tmp_path: pathlib.Path) -> None:
    world = World(pw_database, manager, service, tmp_path, script_modes=['source_backed'])
    pkg_id = world.new_package('no-open')
    deps = world.make_deps()
    res = world.activity(deps, 'reconcile_render', 'recon-noop', [{'ref_type': 'render_package', 'ref_id': pkg_id}])
    assert res['disposition'] == 'succeeded'
    assert res['output_refs'] == []
    assert res['metrics'] == {'reconciled_state': 'none'}


def test_input_port_reports_missing_refs_with_a_code(pw_database: Any, manager: Any, service: Any, tmp_path: pathlib.Path) -> None:
    world = World(pw_database, manager, service, tmp_path, script_modes=['source_backed'])
    pkg_id = world.new_package('ref-codes')
    deps = world.make_deps()

    res1 = world.activity(deps, 'validate_render_package', 'val-miss', [{'ref_type': 'other_ref', 'ref_id': 'other-1'}])
    assert res1['disposition'] == 'failed'
    assert res1['problem']['code'] == 'INPUT_REF_MISSING'

    res2 = world.activity(deps, 'inspect_output', 'insp-miss', [{'ref_type': 'render_package', 'ref_id': pkg_id}])
    assert res2['disposition'] == 'failed'
    assert res2['problem']['code'] == 'INPUT_REF_MISSING'

    res3 = world.activity(deps, 'validate_render_package', 'val-ambig', [
        {'ref_type': 'render_package', 'ref_id': pkg_id},
        {'ref_type': 'render_package', 'ref_id': 'other-pkg'},
    ])
    assert res3['disposition'] == 'failed'
    assert res3['problem']['code'] == 'INPUT_REF_AMBIGUOUS'


class RecordingInputs:
    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.calls: list[str] = []
        self.last_command: Any = None

    def resolve(self, activity_name: str, request: Mapping[str, Any], grant: ExecutionGrant) -> Mapping[str, Any]:
        self.calls.append(activity_name)
        res = self.inner.resolve(activity_name, request, grant)
        if isinstance(res, Mapping) and 'command' in res:
            self.last_command = res['command']
        return res


def qc(
    world: World,
    key: str,
    *,
    deps: RenderActivityDeps | None = None,
) -> tuple[dict[str, Any], QualityReport | None, Any, RecordingInputs, RenderActivityDeps]:
    rec_inputs = RecordingInputs(world.inputs)
    effective_deps = world.make_deps(inputs=rec_inputs) if deps is None else dataclasses.replace(deps, inputs=rec_inputs)

    res_out = world.activity(
        effective_deps,
        'resolve_render_package',
        f'resolve-{key}',
        [{'ref_type': 'output_path', 'ref_id': f'out-{key}'}],
    )
    assert res_out['disposition'] == 'succeeded'
    pkg_id = res_out['output_refs'][0]['ref_id']

    val_out = world.activity(
        effective_deps,
        'validate_render_package',
        f'validate-{key}',
        [{'ref_type': 'render_package', 'ref_id': pkg_id}],
    )
    assert val_out['disposition'] == 'succeeded'

    ren_out = world.activity(
        effective_deps,
        'render_video',
        key,
        [{'ref_type': 'render_package', 'ref_id': pkg_id}],
    )
    assert ren_out['disposition'] == 'succeeded'

    insp_out = world.activity(
        effective_deps,
        'inspect_output',
        f'inspect-{key}',
        [
            {'ref_type': 'render_package', 'ref_id': pkg_id},
            {'ref_type': 'render_attempt', 'ref_id': key},
        ],
    )

    report = None
    with world.uow_factory() as uow:
        stored = uow.renders.latest(KIND_QUALITY_REPORT, key)
        if stored is not None:
            report = stored.record

    return insp_out, report, rec_inputs.last_command, rec_inputs, effective_deps


def test_inspect_output_disclosure_gate_follows_the_script_segments(pw_database: Any, manager: Any, service: Any, tmp_path: pathlib.Path) -> None:
    world = World(pw_database, manager, service, tmp_path, script_modes=['source_backed', 'inference'])
    insp_out, report, cmd, rec_inputs, deps = qc(world, 'att-qc-1')
    assert report is not None
    gate = next(g for g in report.gates if g.gate == GateName.INFERENCE_DISCLOSURE_PRESENT)
    assert gate.status == GateStatus.PASSED
    assert cmd.segments == [
        {'segment_id': 'seg-0', 'claim_mode': 'source_backed'},
        {'segment_id': 'seg-1', 'claim_mode': 'inference'},
    ]
    words_data = timing_payload()['words']
    assert cmd.word_timings == [{'start_ms': w['start_ms']} for w in words_data]


def test_inspect_output_fails_when_the_ass_has_no_disclosure_line(pw_database: Any, manager: Any, service: Any, tmp_path: pathlib.Path) -> None:
    world = World(
        pw_database,
        manager,
        service,
        tmp_path,
        script_modes=['source_backed', 'inference'],
        ass_modes=['source_backed', 'source_backed'],
    )
    assert 'Disclosure' not in world.ass.text
    insp_out, report, cmd, rec_inputs, deps = qc(world, 'att-qc-2')
    assert report is not None
    gate = next(g for g in report.gates if g.gate == GateName.INFERENCE_DISCLOSURE_PRESENT)
    assert gate.status == GateStatus.FAILED
    assert gate.status not in (GateStatus.NOT_APPLICABLE, GateStatus.NOT_EVALUATED)


def test_inspect_output_is_not_applicable_for_a_source_backed_script(pw_database: Any, manager: Any, service: Any, tmp_path: pathlib.Path) -> None:
    world = World(pw_database, manager, service, tmp_path, script_modes=['source_backed', 'source_backed'])
    insp_out, report, cmd, rec_inputs, deps = qc(world, 'att-qc-3')
    assert report is not None
    gate = next(g for g in report.gates if g.gate == GateName.INFERENCE_DISCLOSURE_PRESENT)
    assert gate.status == GateStatus.NOT_APPLICABLE
    assert len(cmd.segments) > 0


def test_inspect_output_without_script_or_timing_is_a_clear_error_not_empty_segments(pw_database: Any, manager: Any, service: Any, tmp_path: pathlib.Path) -> None:
    world = World(pw_database, manager, service, tmp_path, script_modes=['source_backed'])
    deps = world.make_deps()

    pkg_missing_script = world.new_package('missing-script', script_version='non-existent-script')
    world.activity(deps, 'render_video', 'att-no-script', [{'ref_type': 'render_package', 'ref_id': pkg_missing_script}])
    insp_no_script = world.activity(deps, 'inspect_output', 'insp-no-script', [
        {'ref_type': 'render_package', 'ref_id': pkg_missing_script},
        {'ref_type': 'render_attempt', 'ref_id': 'att-no-script'},
    ])
    assert insp_no_script['disposition'] == 'failed'
    assert insp_no_script['problem']['code'] == 'SCRIPT_NOT_FOUND'
    with world.uow_factory() as uow:
        assert uow.renders.latest(KIND_QUALITY_REPORT, 'att-no-script') is None

    pkg_missing_timing = world.new_package('missing-timing', word_timing='non-existent-timing')
    world.activity(deps, 'render_video', 'att-no-timing', [{'ref_type': 'render_package', 'ref_id': pkg_missing_timing}])
    insp_no_timing = world.activity(deps, 'inspect_output', 'insp-no-timing', [
        {'ref_type': 'render_package', 'ref_id': pkg_missing_timing},
        {'ref_type': 'render_attempt', 'ref_id': 'att-no-timing'},
    ])
    assert insp_no_timing['disposition'] == 'failed'
    assert insp_no_timing['problem']['code'] == 'WORD_TIMING_NOT_FOUND'
    with world.uow_factory() as uow:
        assert uow.renders.latest(KIND_QUALITY_REPORT, 'att-no-timing') is None


def test_prepare_output_ready_runs_after_qc(pw_database: Any, manager: Any, service: Any, tmp_path: pathlib.Path) -> None:
    world = World(pw_database, manager, service, tmp_path, script_modes=['source_backed', 'inference'])
    insp_out, report, cmd, rec_inputs, deps = qc(world, 'att-qc-prep')
    assert report is not None

    rep_ref = next(r['ref_id'] for r in insp_out['output_refs'] if r['ref_type'] == 'quality_report')
    with world.uow_factory() as uow:
        pkg_id = cmd.render_package_id

    prep_out = world.activity(deps, 'prepare_output_ready', 'prep-key', [
        {'ref_type': 'render_package', 'ref_id': pkg_id},
        {'ref_type': 'render_attempt', 'ref_id': 'att-qc-prep'},
        {'ref_type': 'quality_report', 'ref_id': rep_ref},
    ])

    calls = rec_inputs.calls
    assert 'inspect_output' in calls and 'prepare_output_ready' in calls
    assert calls.index('inspect_output') < calls.index('prepare_output_ready')

    assert prep_out['disposition'] in ('succeeded', 'failed')
    assert (prep_out['disposition'] == 'succeeded') == report.passed
    if prep_out['disposition'] == 'failed':
        assert prep_out['problem']['code'] == 'output_not_ready'
        assert not any(r['ref_type'] == 'video_output' for r in prep_out.get('output_refs', []))
    else:
        assert any(r['ref_type'] == 'video_output' and r['ref_id'] == 'video-output-att-qc-prep' for r in prep_out.get('output_refs', []))


def render_command(world: World, tag: str, attempt_id: str) -> RenderVideoCommand:
    pkg_id = world.new_package(tag)
    with world.uow_factory() as uow:
        pkg = uow.renders.latest(KIND_PACKAGE, pkg_id).record
    plan = world.render_plan(pkg, attempt_id)
    context = CommandContext(
        workspace_id=world.db.workspace_id,
        correlation_id=f'corr-{attempt_id}',
        actor='tester',
        occurred_at='2026-01-01T00:00:00+00:00',
    )
    return RenderVideoCommand(
        grant=make_grant(world.db),
        render_package_id=pkg_id,
        render_attempt_id=attempt_id,
        output_artifact_ref=plan.output_artifact_ref,
        receipt_ref=f'receipt-{attempt_id}',
        command_spec=plan.command_spec,
        context=context,
        validation_context=world.validation_context(pkg),
    )


def passing_report() -> QualityReport:
    """Báo cáo đạt dựng bằng mã production build_quality_report, vì oracle của gói là băm chứ không phải cổng QC."""
    hard = [GateResult(gate=gate, status=GateStatus.PASSED) for gate in GATE_ORDER if GATE_KINDS[gate] is GateKind.HARD]
    return build_quality_report(hard, {GateName.INFERENCE_DISCLOSURE_PRESENT: False})


def render_for_qc(world: World, tag: str) -> tuple[RecordingInputs, RenderActivityDeps, list[dict[str, str]], pathlib.Path, str]:
    """render_video thật chạy qua handle_activity với FFmpeg thật ở biên."""
    rec = RecordingInputs(world.inputs)
    deps = world.make_deps(inputs=rec)
    pkg_id = world.new_package(tag)
    attempt_id = f'att-{tag}'
    rendered = world.activity(deps, 'render_video', attempt_id, [{'ref_type': 'render_package', 'ref_id': pkg_id}])
    assert rendered['disposition'] == 'succeeded', rendered
    report = passing_report()
    with world.uow_factory() as uow:
        uow.renders.append(KIND_QUALITY_REPORT, attempt_id, 1, report)
        uow.commit()
    chain = [{'ref_type': 'render_package', 'ref_id': pkg_id}, *[dict(r) for r in rendered['output_refs']], {'ref_type': 'quality_report', 'ref_id': report.report_id}]
    output_ref = next(r for r in chain if r['ref_type'] == 'render_output')
    return (rec, deps, chain, world.staging / output_ref['ref_id'], attempt_id)


def test_render_result_carries_the_sha256_verified_at_render_time(pw_database: Any, manager: Any, service: Any, tmp_path: pathlib.Path) -> None:
    world = World(pw_database, manager, service, tmp_path, script_modes=['source_backed'])
    pipe = RenderPipeline(uow=world.uow_factory(), renderer=world.renderer, lease=world.gpu, probe=world.probe, observer=world.renderer, grants=AlwaysCurrent())
    res = pipe.render_video(render_command(world, 'sha-direct', 'att-sha-direct'))
    assert res.attempt.receipt_state == OperationState.SUCCEEDED, res.attempt.error
    produced = world.staging / res.attempt.output_artifact_ref
    assert res.output_sha256 == hashlib.sha256(produced.read_bytes()).hexdigest()
    assert not hasattr(res.attempt, 'output_sha256')

    class CrashingRenderer:
        takes_held_lease = True

        def run(self, spec: Any, *, lease: GpuLease) -> Any:
            raise RuntimeError('boom')

        def observe(self, output_ref: str) -> Any:
            return world.renderer.observe(output_ref)

    crash_pipe = RenderPipeline(uow=world.uow_factory(), renderer=CrashingRenderer(), lease=world.gpu, probe=world.probe, observer=world.renderer, grants=AlwaysCurrent())
    failed = crash_pipe.render_video(render_command(world, 'sha-fail', 'att-sha-fail'))
    assert failed.attempt.receipt_state == OperationState.FAILED
    assert failed.output_sha256 is None


def test_the_qc_chain_gives_prepare_output_ready_the_verified_sha256(pw_database: Any, manager: Any, service: Any, tmp_path: pathlib.Path) -> None:
    world = World(pw_database, manager, service, tmp_path, script_modes=['source_backed'])
    rec, deps, chain, produced, attempt_id = render_for_qc(world, 'sha-chain')
    expected = hashlib.sha256(produced.read_bytes()).hexdigest()
    output_ref = next(r for r in chain if r['ref_type'] == 'render_output')
    assert output_ref['sha256'] == expected
    assert not any(r['ref_type'] == 'expected_sha256' for r in chain)
    world.activity(deps, 'prepare_output_ready', 'prep-sha-chain', chain)
    assert rec.last_command.expected_sha256 == expected

    grant = make_grant(world.db)
    stale = {'ref_type': 'render_output', 'ref_id': 'out/other-attempt.mp4', 'sha256': '0' * 64}
    request = {'input_refs': [stale, *chain], 'operation_key': 'prep-sha-stale', 'workflow_run_id': 'run-1'}
    assert world.inputs.resolve('prepare_output_ready', request, grant)['command'].expected_sha256 == expected

    explicit = {'ref_type': 'expected_sha256', 'ref_id': 'f' * 64}
    request_explicit = {'input_refs': [*chain, explicit], 'operation_key': 'prep-sha-explicit', 'workflow_run_id': 'run-1'}
    assert world.inputs.resolve('prepare_output_ready', request_explicit, grant)['command'].expected_sha256 == 'f' * 64


def test_prepare_output_ready_is_ready_for_the_intact_output(pw_database: Any, manager: Any, service: Any, tmp_path: pathlib.Path) -> None:
    world = World(pw_database, manager, service, tmp_path, script_modes=['source_backed'])
    rec, deps, chain, produced, attempt_id = render_for_qc(world, 'sha-ready')
    res = world.activity(deps, 'prepare_output_ready', 'prep-sha-ready', chain)
    assert res['disposition'] == 'succeeded', res
    assert res['warnings'] == []
    assert any(r['ref_type'] == 'video_output' and r['ref_id'] == f'video-output-{attempt_id}' for r in res['output_refs'])


def test_prepare_output_ready_reports_hash_mismatch_when_one_byte_changes(pw_database: Any, manager: Any, service: Any, tmp_path: pathlib.Path) -> None:
    world = World(pw_database, manager, service, tmp_path, script_modes=['source_backed'])
    rec, deps, chain, produced, attempt_id = render_for_qc(world, 'sha-tamper')
    data = produced.read_bytes()
    produced.write_bytes(data[:-1] + bytes([data[-1] ^ 0xFF]))
    res = world.activity(deps, 'prepare_output_ready', 'prep-sha-tamper', chain)
    assert res['disposition'] == 'failed'
    assert res['problem']['code'] == 'output_not_ready'
    assert 'output_hash_mismatch' in res['warnings']
    assert 'expected_sha256_invalid' not in res['warnings']
    assert not any(r['ref_type'] == 'video_output' for r in res.get('output_refs', []))
