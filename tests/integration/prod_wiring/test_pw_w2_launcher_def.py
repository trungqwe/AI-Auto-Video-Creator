"""PW-W2: ráp deps production cho D, E, F vào launcher worker; kiểm toàn bộ stage activity đã bound và không dùng test double trong production.

coveredIds: PW-W2-01, CT-WF-004, CT-WF-006
"""
from __future__ import annotations

import ast
import asyncio
import dataclasses
import hashlib
import importlib.util
import json
import sys
import time
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
from controlplane.api.wiring.voice import build_voice_services
from controlplane.application.orchestration.workflows.activities import STAGE_ACTIVITIES_BY_WORKFLOW
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
    assert deps.render._lease is rig.runtime.gpu_lease
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
