"""PW-W2: ráp deps production cho D, E, F vào launcher worker; kiểm toàn bộ stage activity đã bound và không dùng test double trong production.

coveredIds: PW-W2-01, CT-WF-004, CT-WF-006
"""
from __future__ import annotations

import base64
import ast
import asyncio
import dataclasses
import hashlib
import importlib.util
import json
import sys
import subprocess
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import controlplane.api.wiring.production as production_wiring
import controlplane.api.wiring.production_profile as profile_wiring
import controlplane.api.wiring.workflow as workflow_wiring
from controlplane.api.wiring.collection import build_collection_services
from controlplane.api.wiring.creative import build_creative_services
from controlplane.api.wiring.render import build_render_services
from controlplane.api.wiring.storage import build_storage_services
from controlplane.api.wiring.voice import build_voice_services, locate_media_file, read_media_image, verify_media_output, voice_activity_deps
from controlplane.application.orchestration.workflows.activities import STAGE_ACTIVITIES_BY_WORKFLOW
from controlplane.application.storage_meta.handlers import register_staged_artifact
from controlplane.domain.orchestration import ExecutionGrant
from voice.application.media_pipeline import VerifiedOutput
from voice.domain.image_safety import SafetyOutcome
from voice.domain.probe import Readability
from voice.domain.processing import Disposition
from voice.domain.voice_track import VoiceTrack
from voice.persistence import PostgresVoiceUnitOfWork
from controlplane.infrastructure.db.uow import TransactionManager
from controlplane.infrastructure.production_ports.gpu_lease import LocalGpuLease

ROOT = Path(__file__).resolve().parents[3]
LAUNCHER_PATH = ROOT / "tools" / "launcher" / "launcher.py"
PROFILE_PATH = ROOT / "tools" / "launcher" / "prod" / "profile.json"
NOW = datetime(2026, 10, 27, 1, 2, 3, tzinfo=timezone.utc)
FFMPEG_BYTES = b"pinned-ffmpeg-bytes"
@pytest.fixture(scope="module")
def launcher():
    spec = importlib.util.spec_from_file_location("pw_w2_launcher", LAUNCHER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_runtime(tmp_path: Path) -> profile_wiring.ProductionRuntime:
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffmpeg.write_bytes(FFMPEG_BYTES)
    lock = tmp_path / "runtime.lock.json"
    lock.write_text(json.dumps({"pins": {"ffmpeg": {"status": "PINNED", "sha256": hashlib.sha256(FFMPEG_BYTES).hexdigest()}}}), encoding="utf-8")
    return profile_wiring.ProductionRuntime(
        ffmpeg_path=ffmpeg,
        ffprobe_path=tmp_path / "ffprobe.exe",
        runtime_lock_path=lock,
        weights_dir=tmp_path / "weights",
        weights_lock_path=tmp_path / "model-weights.lock.json",
        whisper_model_dir=tmp_path / "whisper",
        staging_root=tmp_path / "staging",
        secret_store_root=tmp_path / "vault",
        oauth_client_secrets_path=tmp_path / "client.json",
        oauth_consent_timeout_seconds=300,
        route_cost_per_request=Decimal("0"),
        tokenization={"revision": "pw-w2", "unicode_form": "NFC", "casefold": True, "edge_strip_categories": ("P",), "gap_tolerance_ms": 500, "min_confidence": 0.5},
        drive_placement={"original": "folder-original", "reusable": "folder-reusable", "output": "folder-output"},
        drive_fallback_parent_id="folder-root",
        route_catalog=SimpleNamespace(candidates=lambda workspace_id, ai_role: ()),
        provider_credentials=SimpleNamespace(acquire=lambda method, account: None),
        vision_route=SimpleNamespace(invoke_vision=lambda *args, **kwargs: ""),
        artifact_source=SimpleNamespace(open=lambda artifact_version_id: None),
        drive_token_broker=SimpleNamespace(acquire=lambda method, account: None),
        gpu_lease=LocalGpuLease(2, 60.0),
    )

@pytest.fixture
def rig(pw_database, tmp_path):
    profile = profile_wiring.load_production_profile(PROFILE_PATH)
    runtime = make_runtime(tmp_path)
    config = profile_wiring.WiringConfig(mode="production", workspace_id=pw_database.workspace_id, profile=profile, runtime=runtime)
    manager = TransactionManager(pw_database.dsn, pool_max_size=4)
    try:
        app = SimpleNamespace(
            manager=manager,
            workspace_id=pw_database.workspace_id,
            services={
                "collection": build_collection_services(manager, config),
                "storage": build_storage_services(manager, config),
                "creative": build_creative_services(manager, config),
                "voice": build_voice_services(manager, config),
                "render": build_render_services(manager, config),
            },
            api_app=SimpleNamespace(state=SimpleNamespace(production_runtime=runtime)),
        )
        yield SimpleNamespace(app=app, database=pw_database, manager=manager, profile=profile, runtime=runtime, config=config)
    finally:
        manager.close()


class FakeTemporalClient:
    async def start_workflow(self, *args, **kwargs):
        return SimpleNamespace(id=kwargs.get("id"))


def start_with_spies(launcher, rig, monkeypatch):
    import temporalio.client
    seen = {}
    class FakeClient:
        @staticmethod
        async def connect(target, namespace="default", **kw):
            seen["connect"] = (target, namespace)
            return FakeTemporalClient()
    class FakeGroup:
        def __init__(self, client, registration, *, graceful_shutdown_seconds):
            self.done = None
        async def run(self):
            self.done = asyncio.Event()
            await self.done.wait()
        async def stop(self):
            self.done.set()
    real_registration = workflow_wiring.build_temporal_registration
    def spy_registration(services, **kw):
        seen["services"] = services
        seen["kw"] = kw
        return real_registration(services, **kw)
    monkeypatch.setattr(temporalio.client, "Client", FakeClient)
    monkeypatch.setattr(production_wiring, "TemporalWorkerGroup", FakeGroup)
    monkeypatch.setattr(workflow_wiring, "build_temporal_registration", spy_registration)
    monkeypatch.setattr(launcher, "STOP_GRACE_SECONDS", 5)
    handle = launcher.start_worker(rig.app, None)
    time.sleep(0.3)
    return handle, seen


def unbound_stage_activities(handlers: dict[str, Any]) -> list[str]:
    all_stage_activities = sorted({
        act
        for wf in STAGE_ACTIVITIES_BY_WORKFLOW.values()
        for acts in wf.values()
        for act in acts
    })
    return [
        name
        for name in all_stage_activities
        if name not in handlers or "unbound_handler" in getattr(handlers[name], "__qualname__", "")
    ]

def test_every_stage_activity_has_a_bound_handler(launcher, rig, monkeypatch):
    all_stage_activities = {
        act
        for wf in STAGE_ACTIVITIES_BY_WORKFLOW.values()
        for acts in wf.values()
        for act in acts
    }
    handle, seen = start_with_spies(launcher, rig, monkeypatch)
    try:
        outer = seen["services"].dispatcher
        assert type(outer).__name__ == "GrantRevokingDispatcher"
        recording = outer._inner
        assert type(recording).__name__ == "ResultRecordingDispatcher"
        inner = recording._inner
        assert type(inner).__name__ == "ActivityDispatcher"

        for name in all_stage_activities:
            assert name in inner._handlers, f"activity {name} missing from dispatcher handlers"
            assert "unbound_handler" not in inner._handlers[name].__qualname__, f"activity {name} is unbound"

        d_names = {
            "BuildProductionSnapshot",
            "AnalyzeContent",
            "GenerateStoryAngles",
            "GenerateScript",
            "SelectCreativeAssets",
            "BuildProductionPlan",
            "ValidateVariant",
            "GenerateOutputMetadata",
        }
        e_names = {
            "CreateVoiceTrack",
            "CreateWordTiming",
            "ProbeMedia",
            "AssessImageSafety",
            "TransformSensitiveImage",
            "NormalizeMedia",
            "PrepareAudioBed",
        }
        f_names = {
            "resolve_render_package",
            "validate_render_package",
            "reconcile_render",
            "render_video",
            "inspect_output",
            "prepare_output_ready",
        }
        bound = seen["services"].bound_activities
        assert d_names <= bound
        assert e_names <= bound
        assert f_names <= bound
    finally:
        handle.stop()


def test_a_removed_handler_turns_the_scan_red(launcher, rig, monkeypatch):
    all_stage_activities = sorted({
        act
        for wf in STAGE_ACTIVITIES_BY_WORKFLOW.values()
        for acts in wf.values()
        for act in acts
    })
    handlers = {name: (lambda req: {}) for name in all_stage_activities}
    clock = lambda: NOW
    handlers["render_video"] = workflow_wiring.unbound_handler(clock)
    assert unbound_stage_activities(handlers) == ["render_video"]


def test_production_path_has_no_fake_in_memory_or_memory_names():
    def scan_fn_for_forbidden(fn: ast.FunctionDef) -> list[str]:
        bad = []
        for stmt in fn.body:
            if isinstance(stmt, ast.If) and "PROFILE_PRODUCTION" in ast.dump(stmt.test):
                continue
            for child in ast.walk(stmt):
                name = getattr(child, "id", None) or getattr(child, "attr", None)
                if name and name.startswith(("Fake", "InMemory", "Memory")):
                    bad.append(name)
        return bad

    sample_bad = ast.parse("def sample_prod():\n    x = FakeService()\n").body[0]
    assert "FakeService" in scan_fn_for_forbidden(sample_bad)

    wiring_dir = ROOT / "src" / "controlplane" / "api" / "wiring"
    target_files = list(wiring_dir.glob("*.py")) + [LAUNCHER_PATH]
    for py_file in target_files:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                bad_names = scan_fn_for_forbidden(node)
                assert not bad_names, f"{py_file.name} in function {node.name} has forbidden names: {bad_names}"

def test_one_local_gpu_lease_is_shared(rig):
    from controlplane.api.wiring.render import render_activity_deps
    from controlplane.application.orchestration.grant_runtime import ExecutionGrantCurrency

    clock = lambda: NOW
    grants = ExecutionGrantCurrency(lambda: rig.database.connect(), rig.database.workspace_id, clock)
    deps = render_activity_deps(
        rig.app.services["render"],
        manager=rig.manager,
        workspace_id=rig.database.workspace_id,
        profile=rig.profile,
        runtime=rig.runtime,
        grants=grants,
        clock=clock,
    )
    assert deps.render._lease is rig.runtime.gpu_lease.waiting_port()
    assert rig.app.services["render"].renderer.lease is rig.runtime.gpu_lease

    probes = workflow_wiring.build_capability_probes(
        connection_factory=lambda: rig.database.connect(),
        workspace_id=rig.database.workspace_id,
        ffmpeg_path=rig.runtime.ffmpeg_path,
        runtime_lock_path=rig.runtime.runtime_lock_path,
        gpu_lease=rig.runtime.gpu_lease,
    )
    assert any(cell.cell_contents is rig.runtime.gpu_lease for cell in probes["gpu_lease_ready"].__closure__)


def test_aligner_opens_only_the_voice_artifact_root(rig):
    from voice.adapters.real_kokoro_tts import VoiceArtifactPlacer

    voice_services = rig.app.services["voice"]
    aligner_config = voice_services.aligner._config
    expected_voice_root = rig.runtime.staging_root / "voice"

    assert aligner_config.voice_root == expected_voice_root
    assert aligner_config.resolve_audio is None
    assert isinstance(voice_services.artifact_placer, VoiceArtifactPlacer)
    assert voice_services.artifact_placer._root == expected_voice_root
    assert voice_services.tts._config.staging_dir == expected_voice_root


def test_d_e_f_deps_use_execution_grant_currency(rig):
    from controlplane.api.wiring.creative import creative_activity_deps
    from controlplane.api.wiring.voice import voice_activity_deps
    from controlplane.api.wiring.render import render_activity_deps
    from controlplane.application.orchestration.grant_runtime import ExecutionGrantCurrency

    clock = lambda: NOW
    grants = ExecutionGrantCurrency(lambda: rig.database.connect(), rig.database.workspace_id, clock)

    c_deps = creative_activity_deps(
        rig.app.services["creative"],
        manager=rig.manager,
        workspace_id=rig.database.workspace_id,
        profile=rig.profile,
        runtime=rig.runtime,
        grants=grants,
        sources=SimpleNamespace(source_set=lambda **kw: None),
        selection_inputs=SimpleNamespace(selection_inputs=lambda **kw: {}),
        selections=SimpleNamespace(borrow_connection=lambda: None),
        clock=clock,
    )
    v_deps, _v_inputs = voice_activity_deps(
        rig.app.services["voice"],
        manager=rig.manager,
        workspace_id=rig.database.workspace_id,
        profile=rig.profile,
        runtime=rig.runtime,
        grants=grants,
        clock=clock,
    )
    r_deps = render_activity_deps(
        rig.app.services["render"],
        manager=rig.manager,
        workspace_id=rig.database.workspace_id,
        profile=rig.profile,
        runtime=rig.runtime,
        grants=grants,
        clock=clock,
    )

    assert c_deps.grants is grants
    assert v_deps.grants is grants
    assert r_deps.grants is grants

def test_assembly_reads_no_database_row_and_loads_no_model(launcher, rig):
    clock = lambda: NOW
    handlers = launcher.assemble_dfe_handlers(
        rig.app,
        manager=rig.manager,
        workspace_id=rig.database.workspace_id,
        profile=rig.profile,
        runtime=rig.runtime,
        connection_factory=lambda: rig.database.connect(),
        clock=clock,
    )
    assert len(handlers) == 21


def test_production_py_keeps_module_services_block():
    prod_path = ROOT / "src" / "controlplane" / "api" / "wiring" / "production.py"
    text = prod_path.read_text(encoding="utf-8")
    assert "compose_sources_module(services, config)" in text
    assert "compose_hooks_module(manager)" in text
    tree = ast.parse(text)
    build_app_fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "build_production_app")
    assigned_targets = [
        ast.unparse(target)
        for stmt in build_app_fn.body
        if isinstance(stmt, ast.Assign)
        for target in stmt.targets
    ]
    assert "api_app.state.module_services['sources']" in assigned_targets
    assert "api_app.state.module_services['hooks']" in assigned_targets


def test_module_docstring_declares_covered_ids():
    self_path = Path(__file__).resolve()
    text = self_path.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines()[:12]]
    assert "coveredIds: PW-W2-01, CT-WF-004, CT-WF-006" in lines

FFMPEG = Path("C:/ffmpeg/bin/ffmpeg.exe")
LOCK_PATH = ROOT / "tools" / "runtime" / "runtime.lock.json"
R4_JOB = "job-r4"
R4_STAGE_RUN = "job-r4:process:r1"
R4_PLAN = "plan-r4"


class RecordingVision:
    def __init__(self) -> None:
        self.calls: list[tuple[bytes, str]] = []

    def invoke_vision(self, ai_role, instructions, image_base64, media_type, timeout_seconds):
        self.calls.append((base64.b64decode(image_base64), media_type))
        return {"confidence": 0.9, "detections": []}


@pytest.fixture
def r4(pw_database, tmp_path):
    if not FFMPEG.is_file():
        pytest.fail("BLOCKED_EXTERNAL: pinned FFmpeg C:/ffmpeg/bin/ffmpeg.exe is required; no skip and no fallback is permitted.", pytrace=False)
    vision = RecordingVision()
    profile = profile_wiring.load_production_profile(PROFILE_PATH)
    runtime = dataclasses.replace(make_runtime(tmp_path), ffmpeg_path=FFMPEG, runtime_lock_path=LOCK_PATH, vision_route=vision)
    runtime.staging_root.mkdir(parents=True)
    work = tmp_path / "work"
    work.mkdir()
    ws = pw_database.workspace_id
    config = profile_wiring.WiringConfig(mode="production", workspace_id=ws, profile=profile, runtime=runtime)
    manager = TransactionManager(pw_database.dsn, pool_max_size=4)
    try:
        services = build_voice_services(manager, config)
        deps, inputs = voice_activity_deps(services, manager=manager, workspace_id=ws, profile=profile, runtime=runtime, grants=None, clock=lambda: NOW)
        yield SimpleNamespace(database=pw_database, manager=manager, runtime=runtime, vision=vision, deps=deps, inputs=inputs, work=work, grant=ExecutionGrant(ws, "op-r4", R4_JOB, R4_STAGE_RUN, 1, 0))
    finally:
        manager.close()


def r4_locator(r4):
    return locate_media_file(r4.manager, r4.database.workspace_id, r4.runtime.staging_root)


def write_image(path: Path) -> bytes:
    done = subprocess.run([str(FFMPEG), "-hide_banner", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=64x64:r=1:d=1", "-frames:v", "1", str(path)], capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    return path.read_bytes()


def stage_image(r4, name: str):
    data = write_image(r4.work / name)
    digest = hashlib.sha256(data).hexdigest()
    relative = f"media/{digest}{Path(name).suffix}"
    target = r4.runtime.staging_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    version = register_staged_artifact(r4.manager, workspace_id=r4.database.workspace_id, staging_root=r4.runtime.staging_root, owner_ref=R4_JOB, relative_ref=relative, retention_ref="durable")
    item = {"ref_type": "selected_media", "ref_id": f"media-{name}", "revision_id": version.artifact_version_id}
    return SimpleNamespace(version=version, path=target, data=data, digest=digest, item=item)


def r4_request(name: str, key: str, refs: list) -> dict:
    return {"workflow_id": "wf-r4", "workflow_run_id": "run-r4", "stage_run_id": R4_STAGE_RUN, "activity_name": name, "activity_version": "1", "input_refs": refs, "operation_key": key, "capability_requirements": {"task_queue": "desktop_cpu"}, "retry_policy_ref": "retry-1", "video_job_id": R4_JOB}


def run_media(r4, activity: str, method: str, key: str, refs: list):
    kwargs = r4.inputs.resolve(activity, r4_request(activity, key, refs), r4.grant)
    return getattr(r4.deps.media, method)(operation_key=key, **kwargs)


def test_pw_w2_r4_probe_assess_normalize_read_the_registered_png(r4):
    staged = stage_image(r4, "a.png")
    probe = run_media(r4, "ProbeMedia", "probe_media", "r4:probe", [staged.item])
    assert probe.receipt.disposition is Disposition.SUCCEEDED
    assert probe.record.readability is Readability.READABLE
    assert "unreadable" not in probe.receipt.warnings
    assess = run_media(r4, "AssessImageSafety", "assess_image_safety", "r4:assess", [staged.item])
    assert assess.receipt.disposition is Disposition.SUCCEEDED
    assert assess.record.outcome is SafetyOutcome.SAFE
    assert r4.vision.calls == [(staged.data, "image/png")]
    link = {"ref_type": "image_safety_assessment", "ref_id": "assessment:r4:assess", "source_ref_id": staged.item["ref_id"], "revision_id": staged.version.artifact_version_id}
    normalize = run_media(r4, "NormalizeMedia", "normalize_media", "r4:normalize", [staged.item, link])
    assert normalize.receipt.disposition is Disposition.SUCCEEDED, normalize.receipt.error
    (ref,) = normalize.receipt.output_refs
    assert ref.startswith("rendition:")
    assert normalize.record.input_ref.ref == staged.version.artifact_version_id
    output = r4.runtime.staging_root / "media" / (ref.replace(":", "_") + ".png")
    assert output.is_file()
    assert hashlib.sha256(output.read_bytes()).hexdigest() == normalize.record.output_sha256


def test_pw_w2_r4_jpg_version_is_normalized_and_its_output_is_verified(r4):
    staged = stage_image(r4, "b.jpg")
    assess = run_media(r4, "AssessImageSafety", "assess_image_safety", "r4:assess-jpg", [staged.item])
    assert assess.record.outcome is SafetyOutcome.SAFE
    assert r4.vision.calls == [(staged.data, "image/jpeg")]
    link = {"ref_type": "image_safety_assessment", "ref_id": "assessment:r4:assess-jpg", "source_ref_id": staged.item["ref_id"], "revision_id": staged.version.artifact_version_id}
    normalize = run_media(r4, "NormalizeMedia", "normalize_media", "r4:normalize-jpg", [staged.item, link])
    assert normalize.receipt.disposition is Disposition.SUCCEEDED, normalize.receipt.error
    (ref,) = normalize.receipt.output_refs
    output = r4.runtime.staging_root / "media" / (ref.replace(":", "_") + ".jpg")
    assert output.is_file()
    verified = verify_media_output(r4_locator(r4))(ref)
    assert verified is not None
    assert verified.content_sha256 == normalize.record.output_sha256
    assert verified.size_bytes == output.stat().st_size


def test_pw_w2_r4_locator_returns_a_path_only_when_the_file_matches_the_verified_version(r4):
    ws = r4.database.workspace_id
    media = r4.runtime.staging_root / "media"
    staged = stage_image(r4, "c.png")
    version_id = staged.version.artifact_version_id
    locate = r4_locator(r4)
    read_image = read_media_image(locate)
    verify = verify_media_output(locate)
    assert locate(version_id).samefile(staged.path)
    assert read_image(version_id) == (staged.data, "image/png")
    assert locate(str(uuid.uuid4())) is None
    unverified = media / "unverified.png"
    unverified.write_bytes(staged.data + b"u")
    unverified_id = str(uuid.uuid4())
    with r4.database.connect() as conn:
        conn.execute("INSERT INTO controlplane.cp_artifact_versions (artifact_version_id, workspace_id, artifact_id, sha256_hash, size_bytes, mime_type, artifact_kind, owner_ref, retention_ref, sensitivity_ref) VALUES (%s::uuid, %s::uuid, %s, %s, %s, 'image/png', 'render_input_media', %s, 'durable', 'internal')", (unverified_id, ws, "media/unverified.png", hashlib.sha256(unverified.read_bytes()).hexdigest(), unverified.stat().st_size, R4_JOB))
    assert locate(unverified_id) is None
    (media / "processed_abc12345.png").write_bytes(b"p")
    assert locate("processed:abc12345").samefile(media / "processed_abc12345.png")
    assert locate("rendition:abc12345") is None
    (media / "rendition_abc12345.png").write_bytes(b"1")
    (media / "rendition_abc12345.jpg").write_bytes(b"2")
    assert locate("rendition:abc12345") is None
    assert locate("../outside") is None and locate(f"media/{staged.digest}.png") is None
    staged.path.write_bytes(staged.data + b"x")
    assert locate(version_id) is None
    assert verify(version_id) is None
    with pytest.raises(ValueError):
        read_image(version_id)


def test_pw_w2_r4_audio_bed_is_found_and_prepare_audio_bed_is_verified(r4):
    ws = r4.database.workspace_id
    library = r4.runtime.staging_root / "audio_library"
    library.mkdir()
    body = b"collected-music-bytes"
    digest = hashlib.sha256(body).hexdigest()
    (library / f"music-{digest}.audio").write_bytes(body)
    verify = verify_media_output(r4_locator(r4))
    found = verify(f"music-{digest}")
    assert found is not None and found.content_sha256 == digest and found.size_bytes == len(body)
    assert verify("music-" + "0" * 64) is None
    voice = VoiceTrack(voice_artifact_ref="voice-artifact-" + "a" * 64, script_version_id="sv-r4", script_fingerprint="c" * 64, voice_hash="a" * 64, actual_duration_ms=61000, provider_model_voice_revision="kokoro-v1.0", usage_metrics={}, warnings=(), receipt_ref="receipt-r4")
    with PostgresVoiceUnitOfWork(r4.manager, workspace_id=ws) as uow:
        uow.outputs.append("voice", f"track:{R4_JOB}", 1, voice)
        uow.commit()
    payload = {"music_cues": [{"start_ms": 0, "end_ms": 5000, "mood": "tense", "artifact_ref": "music-tense"}]}
    with r4.database.connect() as conn:
        conn.execute("INSERT INTO controlplane.cp_production_plans (workspace_id, record_key, revision, payload, production_plan_id) VALUES (%s::uuid, %s, 1, %s::jsonb, %s)", (ws, R4_PLAN, json.dumps(payload), R4_PLAN))
    result = run_media(r4, "PrepareAudioBed", "prepare_audio_bed", "r4:bed", [{"ref_type": "production_plan", "ref_id": R4_PLAN}])
    assert result.receipt.disposition is Disposition.SUCCEEDED, result.receipt.error
    (ref,) = result.receipt.output_refs
    assert ref.startswith("bed-none-")
    assert (library / f"{ref}.wav").is_file()
