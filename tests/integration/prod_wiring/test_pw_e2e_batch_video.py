"""PW-E2E: một lô qua POST /v1/batches thành video tới completion trên composition production của launcher.

coveredIds: PW-E2E-01, CT-QC-001, CT-WF-004, CT-WF-006, CT-WF-007, CT-ORC-007, CT-ORC-010, CT-SRC-004
"""
from __future__ import annotations

import ast
import asyncio
import json
import pathlib
import re
import subprocess
import tempfile
import time
from temporalio.client import WorkflowExecutionStatus
from typing import Any

import pytest
import pytest_asyncio

from tests.integration.prod_wiring.pw_e2e_support import (
    BASE,
    FFMPEG,
    FFPROBE,
    LAUNCHER_PATH,
    PORT,
    PROFILE_PATH,
    ROOT,
    E2ERig,
    EXPECTED_ACTIVITIES,
    VIDEO_STAGES,
    batch_row,
    count,
    grants_by_stage,
    job_row,
    live_grants,
    scalar,
    stage_runs,
    wait_until,
)


@pytest_asyncio.fixture
async def rig(pw_database: Any, pw_temporal: Any, tmp_path: pathlib.Path, monkeypatch: Any) -> Any:
    r = E2ERig(pw_database, pw_temporal, tmp_path, monkeypatch)
    r.build()
    try:
        yield r
    finally:
        await r.close()


@pytest.mark.asyncio
async def test_the_launcher_composition_binds_every_activity_and_has_no_private_assembly(rig: Any) -> None:
    await rig.start_worker()
    services = rig.seen["services"]
    outer = services.dispatcher
    assert type(outer).__name__ == "Grant" + "RevokingDispatcher"
    recording = outer._inner
    assert type(recording).__name__ == "Result" + "RecordingDispatcher"
    inner = recording._inner
    assert type(inner).__name__ == "Activity" + "Dispatcher"

    from controlplane.application.orchestration.workflows.activities import (
        STAGE_ACTIVITIES_BY_WORKFLOW,
        ACTIVITY_BINDINGS,
    )

    all_stage_activities = {
        act
        for wf in STAGE_ACTIVITIES_BY_WORKFLOW.values()
        for acts in wf.values()
        for act in acts
    }
    binding_names = {b.name for b in ACTIVITY_BINDINGS}
    for b_name in binding_names:
        assert b_name in inner._handlers, f"binding {b_name} missing from dispatcher handlers"

    unbound = []
    for name in all_stage_activities:
        if name not in inner._handlers:
            unbound.append(f"{name}: missing")
        elif "unbound_handler" in inner._handlers[name].__qualname__:
            unbound.append(f"{name}: unbound")
    assert unbound == []

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

    wiring_dir = ROOT / "src" / "controlplane" / "api" / "wiring"
    target_files = list(wiring_dir.glob("*.py")) + [LAUNCHER_PATH]
    for py_file in target_files:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                bad_names = scan_fn_for_forbidden(node)
                assert not bad_names, f"{py_file.name} in function {node.name} has forbidden names: {bad_names}"

    FORBIDDEN_COMPOSITION = {
        "Vertical",
        "build_" + "workflow_services",
        "build_" + "temporal_registration",
        "Result" + "RecordingDispatcher",
        "Grant" + "RevokingDispatcher",
        "Outbox" + "Relay",
        "Capability" + "Reader",
        "build_" + "grant_issuer",
        "Activity" + "Dispatcher",
        "service_" + "handler",
    }
    for target in (
        ROOT / "tests" / "integration" / "prod_wiring" / "pw_e2e_support.py",
        pathlib.Path(__file__).resolve(),
    ):
        tree = ast.parse(target.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in FORBIDDEN_COMPOSITION:
                pytest.fail(f"{target.name} has forbidden AST Name: {node.id}")
            elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_COMPOSITION:
                pytest.fail(f"{target.name} has forbidden AST Attribute: {node.attr}")
            elif isinstance(node, ast.alias) and (node.name in FORBIDDEN_COMPOSITION or (node.asname and node.asname in FORBIDDEN_COMPOSITION)):
                pytest.fail(f"{target.name} has forbidden AST alias: {node.name}")

    assert "grant_issuer" in rig.seen["kw"]
    assert "capability_reader" in rig.seen["kw"]


EDGE_PATCH_ALLOWLIST = frozenset({
    "prod_wiring, 'build_storage_services'",
    "prod_wiring, 'build_creative_services'",
    "prod_wiring, 'build_collection_services'",
    "voice_wiring, 'RealKokoroTts'",
    "voice_wiring, 'RealWhisperAligner'",
    "voice_wiring, 'ProductionHttpsTransport'",
    "voice_wiring, 'load_music_sources'",
    "socket, 'getaddrinfo'",
    "self.launcher, 'build_runtime'",
    "self.launcher, 'STOP_GRACE_SECONDS'",
    "temporalio.client, 'Client'",
    "production_wiring, 'TemporalWorkerGroup'",
    "workflow_wiring, b_tr_name",
})
PRODUCTION_LOGIC_TOKENS = ("rights_cleared", "VerifiedArtifact", "output_hash", "ProductionVariantContext", "ProductionSelectionInputs", "ProductionRenderSources", "RenderActivityInputs", "handle_collect_source_activity", "handle_voice_activity", "materialize_artifact_set_handler", "RealFfmpegMediaTool", "verify_media_output", "start_workflow", "business_date")

def test_the_support_module_patches_only_edge_adapters() -> None:
    target = ROOT / "tests" / "integration" / "prod_wiring" / "pw_e2e_support.py"
    source = target.read_text(encoding="utf-8")
    tree = ast.parse(source)
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name in ("setattr", "delattr", "setitem"):
            found.add(", ".join(ast.unparse(arg) for arg in node.args[:2]))
    assert found, "khong tim thay monkeypatch nao: guard vo hieu"
    assert found <= EDGE_PATCH_ALLOWLIST, sorted(found - EDGE_PATCH_ALLOWLIST)
    for token in PRODUCTION_LOGIC_TOKENS:
        assert token not in source, token
async def wait_for_workflow(client: Any, wf_id: str, timeout: float = 60.0) -> Any:
    deadline = time.monotonic() + timeout
    handle = client.get_workflow_handle(wf_id)
    while time.monotonic() < deadline:
        try:
            await handle.describe()
            return handle
        except Exception:
            await asyncio.sleep(0.2)
    raise TimeoutError(f"Workflow {wf_id} was not started within {timeout}s")


async def wait_for_workflow_result(handle: Any, timeout: float = 900.0, rig: Any = None) -> Any:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if rig is not None:
            reason = await asyncio.to_thread(rig.fail_fast_reason)
            if reason:
                pytest.fail(f'fail-fast: {reason}', pytrace=False)
        desc = await handle.describe()
        if desc.status != WorkflowExecutionStatus.RUNNING:
            return await handle.result()
        await asyncio.sleep(0.5)
    raise TimeoutError(f"Workflow {handle.id} did not finish within {timeout}s")


@pytest.mark.asyncio
async def test_one_batch_posted_to_the_api_reaches_completion_and_a_second_batch_marks_the_gate_not_applicable(
    rig: Any, pw_temporal: Any
) -> None:
    await rig.start_worker()

    def two_articles() -> bool:
        with rig.database.connect() as conn:
            row = conn.execute(
                "SELECT count(*) FROM controlplane.cp_articles WHERE workspace_id = %s",
                (rig.database.workspace_id,),
            ).fetchone()
            return bool(row and row[0] >= 2)

    await wait_until(two_articles, timeout=300.0, interval=0.5, what="two articles collected")

    # (2) First batch: inference disclosure
    rig.router.script_mode = "inference"
    batch_id = await asyncio.to_thread(rig.post_batch, 1)
    assert rig.batch_status_before_setup[batch_id] == "CREATED"

    handle = await wait_for_workflow(pw_temporal, batch_id)
    try:
        batch_result = await wait_for_workflow_result(handle, 900.0, rig=rig)
    except Exception as exc:
        print("HANDLE RESULT ERROR:", type(exc), exc)
        desc = await handle.describe()
        print("HANDLE DESCRIBE:", desc.status)
        try:
            c_desc = await pw_temporal.get_workflow_handle(f"{batch_id}:video:0").describe()
            print("CHILD DESCRIBE:", c_desc.status)
        except Exception as e2:
            print("CHILD DESCRIBE FAILED:+", e2)
        with rig.database.connect() as conn:
            print('STAGE RUNS:', conn.execute('SELECT stage_name, attempt, status, problem FROM controlplane.cp_stage_runs').fetchall())
            print('JOBS:', conn.execute('SELECT job_id, status, wait_reason FROM controlplane.cp_video_jobs').fetchall())
            print('BATCHES:', conn.execute('SELECT batch_id, status, stop_reason FROM controlplane.cp_production_batches').fetchall())
        raise
    child_handle = await wait_for_workflow(pw_temporal, f"{batch_id}:video:0")
    child = await wait_for_workflow_result(child_handle, 900.0, rig=rig)
    print("CHILD SNAPSHOT:", child)
    with rig.database.connect() as conn:
        r = conn.execute("SELECT stage_name, attempt, status, problem FROM controlplane.cp_stage_runs WHERE stage_name = 'media_select'").fetchall()
        print("MEDIA SELECT RUNS:", r)
        print("VALIDATION REPORTS:", conn.execute("SELECT payload FROM controlplane.cp_package_validation_reports").fetchall())
        print('QUALITY REPORTS:', conn.execute('SELECT payload FROM controlplane.cp_quality_reports').fetchall())
        print('QUALITY GATE RESULTS:', conn.execute('SELECT payload FROM controlplane.cp_quality_gate_results').fetchall())
        print('RENDER PACKAGES:', conn.execute('SELECT payload FROM controlplane.cp_render_packages').fetchall())
        print('RENDER ATTEMPTS:', conn.execute('SELECT payload FROM controlplane.cp_render_attempts').fetchall())
        print('COMMAND SPEC ARGV:', [r[0].get('argv') for r in conn.execute("SELECT payload->'command_spec' FROM controlplane.cp_render_attempts").fetchall()])
    assert (
        batch_result["status"],
        batch_result["completed"],
        batch_result["failed"],
        batch_result["allocated"],
        batch_result["finalized"],
    ) == ("TARGET_REACHED", 1, 0, 1, True)

    child_id = f"{batch_id}:video:0"
    child = await asyncio.wait_for(pw_temporal.get_workflow_handle(child_id).result(), 120.0)
    assert child["status"] == "COMPLETED"
    assert child["failed_stage"] is None
    assert child["unbound"] == []
    assert child["rejected_signals"] == []
    assert sorted(child["completed"]) == sorted(VIDEO_STAGES)
    assert child["attempts"] == EXPECTED_ACTIVITIES

    # (3) CSDL
    job_id = f"{batch_id}:job:1"
    j_row = job_row(rig.database, job_id)
    assert j_row == ("COMPLETED", None)

    b_row = batch_row(rig.database, batch_id)
    assert b_row[0] == "COMPLETED_TARGET" and b_row[1].startswith("TARGET_REACHED")
    assert count(rig.database, "cp_completion_ledger") == 1

    s_runs = stage_runs(rig.database, job_id)
    assert len(s_runs) == 11
    for r in s_runs:
        assert r[1] == "SUCCEEDED"
        assert r[2] == 1
        assert re.fullmatch(r"[0-9]+", str(r[3]))
        assert str(r[3]) == "1"

    grants = grants_by_stage(rig.database)
    for stage in VIDEO_STAGES:
        entries = grants[f"{job_id}:{stage}:r1"]
        assert len(entries) == EXPECTED_ACTIVITIES[stage]
        assert all(e[2] for e in entries)
    assert live_grants(rig.database) == 0
    assert len(rig.gpu.render_owners) == 1

    # (4) mp4
    locs = rig.locations(job_id)
    assert any(l[0] in ("local-staging", "local") and l[1] == "VERIFIED" for l in locs)
    assert any(l[0] in ("cloud", "drive") and l[1] == "VERIFIED" for l in locs)
    assert len(rig.drive.uploads) == 1

    mp4_files = list((rig.tmp_path / "staging" / "out").glob("*.mp4"))
    assert len(mp4_files) >= 1
    out_mp4 = mp4_files[0]
    assert out_mp4.is_file()
    probe_res = subprocess.run(
        [
            str(FFPROBE),
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,codec_name",
            "-of", "json",
            str(out_mp4),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    probe_data = json.loads(probe_res.stdout)
    stream = probe_data["streams"][0]
    assert stream["width"] == 1080
    assert stream["height"] == 1920
    assert stream["codec_name"] == "h264"

    # (5) Quality report disclosure gate PASSED
    qr = rig.quality_report(job_id)
    gate = next(g for g in qr["gates"] if g["gate"] == "INFERENCE_DISCLOSURE_PRESENT")
    assert gate["status"].upper() == "PASSED"
    voice = next(g for g in qr["gates"] if g["gate"] == "VOICE_AUDIBLE")
    assert voice["status"].upper() == "PASSED"
    assert voice["reason"] is None
    assert isinstance(voice["measured_value"], (int, float)) and not isinstance(voice["measured_value"], bool)
    assert qr["passed"] is True

    # (6) Second batch: source_backed disclosure gate NOT_APPLICABLE
    rig.router.script_mode = "source_backed"
    batch_id_2 = await asyncio.to_thread(rig.post_batch, 1)
    handle_2 = await wait_for_workflow(pw_temporal, batch_id_2)
    batch_result_2 = await wait_for_workflow_result(handle_2, 900.0, rig=rig)
    assert batch_result_2["status"] == "TARGET_REACHED"

    child_id_2 = f"{batch_id_2}:video:0"
    child_handle_2 = await wait_for_workflow(pw_temporal, child_id_2)
    child_2 = await wait_for_workflow_result(child_handle_2, 120.0, rig=rig)
    assert child_2["status"] == "COMPLETED"

    job_id_2 = f"{batch_id_2}:job:1"
    qr_2 = rig.quality_report(job_id_2)
    gate_2 = next(g for g in qr_2["gates"] if g["gate"] == "INFERENCE_DISCLOSURE_PRESENT")
    assert gate_2["status"].upper() == "NOT_APPLICABLE"
    voice_2 = next(g for g in qr_2["gates"] if g["gate"] == "VOICE_AUDIBLE")
    assert voice_2["status"].upper() == "PASSED"
    assert voice_2["reason"] is None
    assert isinstance(voice_2["measured_value"], (int, float)) and not isinstance(voice_2["measured_value"], bool)
    assert qr_2["passed"] is True

    cand_1 = scalar(
        rig.database,
        "SELECT snapshot_ref FROM controlplane.cp_video_jobs WHERE workspace_id = %s AND job_id = %s",
        job_id,
    )
    cand_2 = scalar(
        rig.database,
        "SELECT snapshot_ref FROM controlplane.cp_video_jobs WHERE workspace_id = %s AND job_id = %s",
        job_id_2,
    )
    assert cand_1 != cand_2, f"Expected distinct candidates, got {cand_1} and {cand_2}"

    # (7) Write timings JSON
    timings_path = pathlib.Path(tempfile.gettempdir()) / "pw-e2e-stage-timings.json"
    timings = {
        job_id: rig.timer.durations(job_id),
        job_id_2: rig.timer.durations(job_id_2),
    }
    timings_path.write_text(json.dumps(timings, indent=2), encoding="utf-8")


@pytest.mark.asyncio
async def test_a_drive_401_waits_then_one_upload_and_the_render_stage_does_not_rerun(
    rig: Any, pw_temporal: Any
) -> None:
    await rig.start_worker()

    def two_articles() -> bool:
        with rig.database.connect() as conn:
            row = conn.execute(
                "SELECT count(*) FROM controlplane.cp_articles WHERE workspace_id = %s",
                (rig.database.workspace_id,),
            ).fetchone()
            return bool(row and row[0] >= 2)

    await wait_until(two_articles, timeout=300.0, interval=0.5, what="two articles collected")

    rig.router.script_mode = "source_backed"
    rig.broker.token = "token-revoked"
    batch_id = await asyncio.to_thread(rig.post_batch, 1)
    job_id = f"{batch_id}:job:1"

    def waiting_on_credential() -> bool:
        reason = rig.fail_fast_reason()
        if reason:
            pytest.fail(f'fail-fast: {reason}', pytrace=False)
        return job_row(rig.database, job_id) == ("WAITING", "credential_unavailable")

    await wait_until(
        waiting_on_credential,
        timeout=900.0,
        interval=0.5,
        what="job WAITING credential_unavailable",
    )

    runs = {r[0]: r for r in stage_runs(rig.database, job_id)}
    assert "render" in runs and runs["render"][1] == "SUCCEEDED" and runs["render"][2] == 1
    assert "sync" not in runs or runs["sync"][1] != "SUCCEEDED"
    assert len(rig.gpu.render_owners) == 1
    assert len(rig.drive.uploads) == 0
    assert rig.drive.rejections >= 1
    assert job_row(rig.database, job_id)[0] != "FAILED"

    rig.broker.token = rig.drive.valid_token = "token-rotated"

    await asyncio.sleep(1.0)
    try:
        from temporalio.api.testservice.v1 import SleepRequest
        from google.protobuf.duration_pb2 import Duration
        await pw_temporal.test_service.unlock_time_skipping_with_sleep(SleepRequest(duration=Duration(seconds=350)))
    except Exception as exc:
        print("UNLOCK_SLEEP_ERROR:", type(exc), exc)

    handle = await wait_for_workflow(pw_temporal, batch_id)
    batch_res = await wait_for_workflow_result(handle, 900.0, rig=rig)
    assert batch_res["status"] == "TARGET_REACHED"

    child_handle = await wait_for_workflow(pw_temporal, f"{batch_id}:video:0")
    child = await wait_for_workflow_result(child_handle, 120.0, rig=rig)
    assert child["status"] == "COMPLETED"

    assert len(rig.drive.uploads) == 1
    assert len(rig.gpu.render_owners) == 1
    runs_after = {r[0]: r for r in stage_runs(rig.database, job_id)}
    assert runs_after["render"][1] == "SUCCEEDED" and runs_after["render"][2] == 1
    assert job_row(rig.database, job_id) == ("COMPLETED", None)

    locs = rig.locations(job_id)
    assert any(l[0] in ("cloud", "drive") and l[1] == "VERIFIED" for l in locs)
    assert live_grants(rig.database) == 0


@pytest.mark.asyncio
async def test_stopping_and_restarting_the_worker_between_render_and_upload_reruns_nothing(
    rig: Any, pw_temporal: Any
) -> None:
    await rig.start_worker()

    def two_articles() -> bool:
        with rig.database.connect() as conn:
            row = conn.execute(
                "SELECT count(*) FROM controlplane.cp_articles WHERE workspace_id = %s",
                (rig.database.workspace_id,),
            ).fetchone()
            return bool(row and row[0] >= 2)

    await wait_until(two_articles, timeout=300.0, interval=0.5, what="two articles collected")

    rig.router.script_mode = "source_backed"
    rig.broker.token = "token-revoked"
    batch_id = await asyncio.to_thread(rig.post_batch, 1)
    job_id = f"{batch_id}:job:1"

    def waiting_on_credential() -> bool:
        reason = rig.fail_fast_reason()
        if reason:
            pytest.fail(f'fail-fast: {reason}', pytrace=False)
        return job_row(rig.database, job_id) == ("WAITING", "credential_unavailable")

    await wait_until(
        waiting_on_credential,
        timeout=900.0,
        interval=0.5,
        what="job WAITING credential_unavailable",
    )

    initial_runs = {r[0]: (r[1], r[2], str(r[3])) for r in stage_runs(rig.database, job_id)}
    assert "render" in initial_runs and initial_runs["render"][0] == "SUCCEEDED"
    gpu_owners_before = len(rig.gpu.render_owners)
    router_calls_before = len(rig.router.calls)
    ledger_before = count(rig.database, "cp_completion_ledger")

    await rig.stop_worker()

    assert job_row(rig.database, job_id) == ("WAITING", "credential_unavailable")
    stopped_runs = {r[0]: (r[1], r[2], str(r[3])) for r in stage_runs(rig.database, job_id)}
    assert stopped_runs == initial_runs

    rig.broker.token = rig.drive.valid_token = "token-rotated"
    t_restart = time.monotonic()
    await rig.start_worker()

    await asyncio.sleep(1.0)
    try:
        from temporalio.api.testservice.v1 import SleepRequest
        from google.protobuf.duration_pb2 import Duration
        await pw_temporal.test_service.unlock_time_skipping_with_sleep(SleepRequest(duration=Duration(seconds=350)))
    except Exception as exc:
        print('UNLOCK_SLEEP_ERROR:', type(exc), exc, flush=True)

    handle = await wait_for_workflow(pw_temporal, batch_id)
    batch_res = await wait_for_workflow_result(handle, 900.0, rig=rig)
    assert batch_res["status"] == "TARGET_REACHED"

    child_handle = await wait_for_workflow(pw_temporal, f"{batch_id}:video:0")
    child = await wait_for_workflow_result(child_handle, 120.0, rig=rig)
    assert child["status"] == "COMPLETED"

    final_runs = {r[0]: (r[1], r[2], str(r[3])) for r in stage_runs(rig.database, job_id)}
    print("FINAL_RUNS:", final_runs)

    for st in ("analyze", "script", "plan", "media_select", "tts", "align", "process", "render", "qc"):
        assert st in final_runs
        assert final_runs[st][0] == "SUCCEEDED"
        assert final_runs[st][1] == 1
        assert final_runs[st][2] == "1"

    assert len(rig.gpu.render_owners) == 1
    assert len(rig.router.calls) == router_calls_before
    assert count(rig.database, "cp_completion_ledger") == ledger_before + 1
    assert len(rig.drive.uploads) == 1
    assert job_row(rig.database, job_id) == ("COMPLETED", None)

    for st in ("sync", "complete"):
        assert st in final_runs
        assert final_runs[st][0] == "SUCCEEDED"
        assert re.fullmatch(r"[0-9]+", final_runs[st][2])

    assert final_runs["complete"][2] == "2"

    elapsed_sync = time.monotonic() - t_restart
    ready_within = rig.profile.parameters.get("resume.ready_within_seconds", 300)
    assert elapsed_sync <= ready_within


@pytest.mark.asyncio
async def test_the_feed_collection_enrichment_and_candidate_chain_feeds_the_second_batch(
    rig: Any, pw_temporal: Any
) -> None:
    t_start = time.monotonic()
    await rig.start_worker()

    def collection_and_enrichment_done() -> bool:
        with rig.database.connect() as conn:
            packages = conn.execute(
                "SELECT count(*) FROM controlplane.cp_collected_document_packages WHERE workspace_id = %s",
                (rig.database.workspace_id,),
            ).fetchone()[0]
            articles = conn.execute(
                "SELECT count(*) FROM controlplane.cp_articles WHERE workspace_id = %s",
                (rig.database.workspace_id,),
            ).fetchone()[0]
            revisions = conn.execute(
                "SELECT count(*) FROM controlplane.cp_article_revisions WHERE workspace_id = %s",
                (rig.database.workspace_id,),
            ).fetchone()[0]
            return bool(packages >= 2 and articles >= 2 and revisions >= 2)

    await wait_until(
        collection_and_enrichment_done,
        timeout=300.0,
        interval=0.5,
        what="collection and enrichment complete",
    )
    t_articles = time.monotonic()

    with rig.database.connect() as conn:
        packages_cnt = conn.execute(
            "SELECT count(*) FROM controlplane.cp_collected_document_packages WHERE workspace_id = %s",
            (rig.database.workspace_id,),
        ).fetchone()[0]
        assert packages_cnt >= 2

        articles_rows = conn.execute(
            "SELECT article_id FROM controlplane.cp_articles WHERE workspace_id = %s",
            (rig.database.workspace_id,),
        ).fetchall()
        assert len(articles_rows) >= 2
        article_ids = {r[0] for r in articles_rows}

        revisions_cnt = conn.execute(
            "SELECT count(*) FROM controlplane.cp_article_revisions WHERE workspace_id = %s",
            (rig.database.workspace_id,),
        ).fetchone()[0]
        assert revisions_cnt >= 2

        run_counts = conn.execute(
            "SELECT source_id, count(*) FROM controlplane.cp_collection_runs WHERE workspace_id = %s GROUP BY source_id",
            (rig.database.workspace_id,),
        ).fetchall()
        assert len(run_counts) == 2
        for s_id, cnt in run_counts:
            assert cnt == 1

        outbox_events = conn.execute(
            "SELECT aggregate_id, published FROM controlplane.cp_outbox_events WHERE workspace_id = %s AND event_name = 'CollectedDocumentAvailable'",
            (rig.database.workspace_id,),
        ).fetchall()
        assert len(outbox_events) == 2
        assert all(row[1] is True for row in outbox_events)

        media_assets = conn.execute(
            "SELECT media_asset_id, payload FROM controlplane.cp_media_assets WHERE workspace_id = %s",
            (rig.database.workspace_id,),
        ).fetchall()
        assert len(media_assets) >= 2
        for m_id, payload in media_assets:
            prov = conn.execute(
                "SELECT count(*) FROM controlplane.cp_media_provenance WHERE workspace_id = %s AND media_asset_id = %s",
                (rig.database.workspace_id, m_id),
            ).fetchone()[0]
            assert prov >= 1

        usage_cnt = conn.execute(
            "SELECT count(*) FROM controlplane.cp_media_usage WHERE workspace_id = %s",
            (rig.database.workspace_id,),
        ).fetchone()[0]
        assert usage_cnt == 0

    rig.router.script_mode = "source_backed"
    t_post = time.monotonic()
    batch_id = await asyncio.to_thread(rig.post_batch, 1)

    def job_allocated() -> bool:
        with rig.database.connect() as conn:
            row = conn.execute(
                "SELECT job_id, candidate_ref FROM controlplane.cp_job_candidates WHERE workspace_id = %s AND batch_id = %s",
                (rig.database.workspace_id, batch_id),
            ).fetchone()
            return row is not None

    await wait_until(job_allocated, timeout=300.0, interval=0.5, what="AllocateJob allocated a job")
    t_allocated = time.monotonic()

    with rig.database.connect() as conn:
        cand_row = conn.execute(
            "SELECT job_id, candidate_ref FROM controlplane.cp_job_candidates WHERE workspace_id = %s AND batch_id = %s",
            (rig.database.workspace_id, batch_id),
        ).fetchone()
        assert cand_row is not None
        assert cand_row[1] in article_ids

        v_job = conn.execute(
            "SELECT job_id, status FROM controlplane.cp_video_jobs WHERE workspace_id = %s AND batch_id = %s",
            (rig.database.workspace_id, batch_id),
        ).fetchone()
        assert v_job is not None

    await rig.close()

    timings_path = pathlib.Path(tempfile.gettempdir()) / "pw-e2e-stage-timings.json"
    timings = {}
    if timings_path.exists():
        try:
            timings = json.loads(timings_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    timings["collection"] = {
        "collect_and_enrich_seconds": round(t_articles - t_start, 2),
        "allocate_seconds": round(t_allocated - t_post, 2),
    }
    timings_path.write_text(json.dumps(timings, indent=2), encoding="utf-8")


def test_the_report_lists_stage_timings_and_the_cp7_conditions() -> None:
    report_path = ROOT / "docs" / "delivery-evidence" / "pw-e2e" / "report.md"
    assert report_path.exists(), "report.md does not exist"
    text = report_path.read_text(encoding="utf-8")
    assert "PW-E2E" in text
    assert "CP7-10" in text
    assert "CP7-11" in text
    assert "OI-PW-02" in text
    assert "OI-PW-E2E-01" in text
    assert "�" not in text
    assert "Điều kiện" in text

    table_lines = [line.strip() for line in text.splitlines() if line.strip().startswith("|")]
    for stage_name in VIDEO_STAGES:
        assert any(stage_name in line for line in table_lines), f"Stage {stage_name} missing from table in report.md"


@pytest.mark.asyncio
async def test_the_seeded_images_resolve_to_verified_versions_through_the_production_lookup(rig: Any) -> None:
    from controlplane.application.storage_meta.handlers import verified_version_for_sha
    from controlplane.infrastructure.db.uow import TransactionManager

    with rig.database.connect() as conn:
        shas = [
            row[0]
            for row in conn.execute(
                "SELECT sha256_hash FROM controlplane.cp_artifact_versions WHERE workspace_id = %s AND left(artifact_id, 6) = 'media/' AND right(artifact_id, 4) = '.png' ORDER BY sha256_hash",
                (rig.database.workspace_id,),
            ).fetchall()
        ]
    assert len(shas) == 2
    sizes: list[str] = []
    mgr = TransactionManager(rig.database.dsn, pool_max_size=4)
    try:
        for sha in shas:
            version = verified_version_for_sha(mgr, workspace_id=rig.database.workspace_id, sha256=sha)
            assert version is not None
            assert version.artifact_id == f"media/{sha}.png"
            size_probe = subprocess.run(
                [
                    str(FFPROBE),
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height",
                    "-of",
                    "csv=p=0",
                    str(rig.tmp_path / "staging" / version.artifact_version_id),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            sizes.append(size_probe.stdout.strip())
    finally:
        mgr.close()
    assert sorted(sizes) == ['1080,1920', '720,1280']


@pytest.mark.asyncio
async def test_the_seeded_hooks_use_production_refs_and_registered_staged_versions(rig: Any) -> None:
    from catalog.persistence.hooks import PostgresHookHistory
    from controlplane.domain.statemachine import ArtifactLocationState
    from controlplane.infrastructure.db.storage_meta import PostgresStorageMetaRepository
    from controlplane.infrastructure.db.uow import TransactionManager

    ws = rig.database.workspace_id
    with rig.database.connect() as conn:
        history = PostgresHookHistory(conn, ws)
        heads = {'vh-01': history.latest('vh-01'), 'ah-01': history.latest('ah-01')}
    mgr = TransactionManager(rig.database.dsn, pool_max_size=4)
    try:
        for hook_id, suffix in (('vh-01', '.mp4'), ('ah-01', '.wav')):
            hook = heads[hook_id]
            sha = dict(hook.technical_metadata)['media_sha256']
            assert hook.artifact_version_ref == f'seed:{hook_id}:sha256:{sha}'
            with PostgresStorageMetaRepository.in_transaction(mgr, ws) as repo:
                version = repo.find_version(ws, f'media/{sha}{suffix}', sha)
                assert version is not None
                locations = repo.list_version_locations(ws, version.artifact_version_id)
            assert any(loc.state is ArtifactLocationState.VERIFIED and loc.observed_hash == sha for loc in locations)
            assert (rig.tmp_path / 'staging' / version.artifact_version_id).is_file()
    finally:
        mgr.close()


def test_module_docstring_declares_covered_ids() -> None:
    self_path = pathlib.Path(__file__).resolve()
    text = self_path.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines()[:12]]
    assert "coveredIds: PW-E2E-01, CT-QC-001, CT-WF-004, CT-WF-006, CT-WF-007, CT-ORC-007, CT-ORC-010, CT-SRC-004" in lines
