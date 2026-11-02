"""PW-W2-FIX8: render dùng đúng ảnh NormalizeMedia của E chọn theo AssessImageSafety (gốc khi SAFE, bản che khi TRANSFORM rồi SAFE, ảnh dùng được khác của job khi bị loại, seed cùng hạng khi job không còn ảnh nào dùng được), trên PostgreSQL thật và FFmpeg ghim.

coveredIds: DQ-11, OI-ADAPT-10, CT-RND-002, CT-PROC-005
"""
from __future__ import annotations

import base64
import dataclasses
import hashlib
import json
from pathlib import Path
import subprocess
from types import MappingProxyType, SimpleNamespace
from typing import Any
import uuid

import pytest

from catalog.domain.hooks import HookKind
from controlplane.api.wiring.production_profile import WiringConfig, load_production_profile
from controlplane.api.wiring.render import ProductionRenderSources
from controlplane.api.wiring.voice import build_voice_services, voice_activity_deps
from controlplane.domain.orchestration import ExecutionGrant
from creative.adapters.postgres_selection import PostgresSelectionStore
from creative.domain.asset_selection import CreativeAssetSelection, FallbackCandidate, SceneAssignment
from creative.domain.ref_resolver import ResourceRef
from render.adapters.activity_inputs import ActivityInputError
from render.adapters.postgres_plan_assets import PostgresPlanAssets
from render.domain.resolve_package import resolve_render_package
from render.domain.validate_package import validate_render_package
from voice.domain.processing import Disposition

from tests.integration.prod_wiring.test_pw_f3_render_inputs import (
    AUDIO_HOOK_ID,
    HOOK_AUDIO_BYTES,
    HOOK_AUDIO_SHA,
    HOOK_VIDEO_BYTES,
    HOOK_VIDEO_SHA,
    NOW,
    PLAN_ID,
    SCRIPT_ID,
    TIMING_REF,
    VISUAL_HOOK_ID,
    VOICE_BYTES,
    VOICE_REF_F3,
    creative_plan,
    insert_artifact,
    insert_plan,
    insert_script,
    insert_timing,
    manager,
    pinned,
    render_runtime,
    script_segments_payload,
    seed_hook,
    service,
    stage_and_register,
)
from tests.integration.prod_wiring.test_pw_w2_launcher_def import R4_JOB, R4_STAGE_RUN, r4_request, run_media

ROOT = Path(__file__).resolve().parents[3]
FFMPEG = Path("C:/ffmpeg/bin/ffmpeg.exe")
LOCK_PATH = ROOT / "tools" / "runtime" / "runtime.lock.json"
PROFILE_PATH = ROOT / "tools" / "launcher" / "prod" / "profile.json"
JOB = R4_JOB
REGION = {"x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5}
SAFE = {"confidence": 0.9, "detections": []}
UNCERTAIN = {"confidence": 0.4, "detections": []}
WEAPON = {"confidence": 0.9, "detections": [{"category": "weapon", "confidence": 0.9, "region": REGION}]}
NUDITY = {"confidence": 0.9, "detections": [{"category": "nudity_sexual", "confidence": 0.9, "region": REGION}]}
LAVFI = ("testsrc", "testsrc2", "smptebars", "rgbtestsrc")


class ShaVision:
    def __init__(self) -> None:
        self.answers: dict[str, dict[str, Any]] = {}
        self.default: dict[str, Any] = SAFE

    def invoke_vision(
        self,
        ai_role: str,
        instructions: str,
        image_base64: str,
        media_type: str,
        timeout_seconds: float,
    ) -> str:
        sha = hashlib.sha256(base64.b64decode(image_base64)).hexdigest()
        answer = self.answers.get(sha, self.default)
        return json.dumps(answer)


def make_png(path: Path, source: str) -> bytes:
    res = subprocess.run(
        [
            str(FFMPEG),
            "-hide_banner",
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"{source}=s=96x96:r=1:d=1",
            "-frames:v",
            "1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, res.stderr
    return path.read_bytes()


def stage_png(manager: Any, db: Any, runtime: Any, work: Path, name: str, source: str) -> SimpleNamespace:
    data = make_png(work / (name + ".png"), source)
    sha = hashlib.sha256(data).hexdigest()
    version = stage_and_register(manager, db, runtime, f"media/{sha}.png", data)
    return SimpleNamespace(id=version.artifact_version_id, sha=sha, data=data, version=version)


def fix8_world(db: Any, manager: Any, pinned: tuple[Any, Any], tmp_path: Path, *, seed_mode: str = "verified") -> SimpleNamespace:
    if not FFMPEG.is_file():
        pytest.fail("BLOCKED_EXTERNAL: pinned FFmpeg C:/ffmpeg/bin/ffmpeg.exe is required; no skip and no fallback is permitted.", pytrace=False)
    vision = ShaVision()
    profile = load_production_profile(PROFILE_PATH)
    runtime = dataclasses.replace(render_runtime(tmp_path), ffmpeg_path=FFMPEG, runtime_lock_path=LOCK_PATH, vision_route=vision)
    work = tmp_path / "work"
    work.mkdir()
    v1 = stage_png(manager, db, runtime, work, "m1", LAVFI[0])
    v2 = stage_png(manager, db, runtime, work, "m2", LAVFI[1])
    if seed_mode == "verified":
        s1 = stage_png(manager, db, runtime, work, "s1", LAVFI[2])
        s2 = stage_png(manager, db, runtime, work, "s2", LAVFI[3])
        seed_ids = [s1.id, s2.id]
    elif seed_mode == "unverified":
        seed_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        for seed_id in seed_ids:
            insert_artifact(db, seed_id, kind="render_input_media", mime="image/png", states=("DECLARED",))
    elif seed_mode == "none":
        seed_ids = []
    else:
        raise ValueError(f"Unknown seed_mode: {seed_mode}")

    voice_version = stage_and_register(manager, db, runtime, "voice/" + VOICE_REF_F3, VOICE_BYTES)
    stage_and_register(manager, db, runtime, f"media/{HOOK_VIDEO_SHA}.mp4", HOOK_VIDEO_BYTES)
    stage_and_register(manager, db, runtime, f"media/{HOOK_AUDIO_SHA}.wav", HOOK_AUDIO_BYTES)
    seed_hook(manager, db, VISUAL_HOOK_ID, HookKind.VISUAL_HOOK, HOOK_VIDEO_SHA)
    seed_hook(manager, db, AUDIO_HOOK_ID, HookKind.AUDIO_HOOK, HOOK_AUDIO_SHA)
    insert_script(db, script_segments_payload(["source_backed", "source_backed"], [4, 4]))
    insert_timing(db)
    plan = creative_plan(db, pinned, v1.id, v2.id, "thumb:m-1")
    insert_plan(db, plan.to_payload())

    base = CreativeAssetSelection(
        snapshot_ref="snap-1",
        script_ref=SCRIPT_ID,
        angle_ref="angle-1",
        safety_policy_revision="safety-r1",
        music_sfx_policy_revision="ms-r1",
        preset_registry_revision="preset-reg-r1",
        visual_hook=ResourceRef(db.workspace_id, "visual_hook", VISUAL_HOOK_ID, "vh-r1"),
        audio_hook=ResourceRef(db.workspace_id, "audio_hook", AUDIO_HOOK_ID, "ah-r1"),
        thumbnail=ResourceRef(db.workspace_id, "thumbnail", "thumb:m-1", "th-r1"),
        thumbnail_overlay_intent="title card",
        assignments=(
            SceneAssignment(order=0, scene_id="sc-1", media_asset_id="m-1", rendition_ref="rend-1", artifact_version_ref=v1.id, rationale="r1"),
            SceneAssignment(order=1, scene_id="sc-2", media_asset_id="m-2", rendition_ref="rend-2", artifact_version_ref=v2.id, rationale="r2"),
        ),
        music_intents=(),
        sfx_intents=(),
        fallback_candidates=tuple(
            FallbackCandidate(media_asset_id=f"seed-{i}", rendition_ref=f"rend-s{i}", artifact_version_ref=sid, total_score=1.0 - i / 10)
            for i, sid in enumerate(seed_ids, start=1)
        ),
        rationale="fix8",
        score_components=MappingProxyType({}),
    )
    selection = dataclasses.replace(base, selection_fingerprint=base.compute_fingerprint())
    stored = PostgresSelectionStore(manager.borrow_connection).save(workspace_id=db.workspace_id, job_id=JOB, selection=selection)

    config = WiringConfig(mode="production", workspace_id=db.workspace_id, profile=profile, runtime=runtime)
    services = build_voice_services(manager, config)
    deps, inputs = voice_activity_deps(services, manager=manager, workspace_id=db.workspace_id, profile=profile, runtime=runtime, grants=None, clock=lambda: NOW)
    grant = ExecutionGrant(db.workspace_id, "op-fix8", JOB, R4_STAGE_RUN, 1, 0)
    sources = ProductionRenderSources(manager=manager, workspace_id=db.workspace_id, profile=profile, runtime=runtime, clock=lambda: NOW)
    plan_port = PostgresPlanAssets(manager, workspace_id=db.workspace_id)

    selected = [
        {"ref_type": "selected_media", "ref_id": "m-1", "revision_id": v1.id},
        {"ref_type": "selected_media", "ref_id": "m-2", "revision_id": v2.id},
    ]
    base_refs = [{"ref_type": "creative_asset_selection", "ref_id": stored.selection_id}]
    render_refs = [
        {"ref_type": "production_plan", "ref_id": PLAN_ID},
        {"ref_type": "script_version", "ref_id": SCRIPT_ID},
        {"ref_type": "word_timing", "ref_id": TIMING_REF},
        {"ref_type": "voice_artifact", "ref_id": VOICE_REF_F3},
        {"ref_type": "artifact_version", "ref_id": voice_version.artifact_version_id, "source_ref_id": "voice/" + VOICE_REF_F3},
        {"ref_type": "output_path", "ref_id": "out-f8"},
        {"ref_type": "production_snapshot", "ref_id": "snap-f8"},
        {"ref_type": "output_metadata", "ref_id": "meta-f8"},
        *base_refs,
    ]
    return SimpleNamespace(
        database=db,
        manager=manager,
        runtime=runtime,
        vision=vision,
        deps=deps,
        inputs=inputs,
        grant=grant,
        sources=sources,
        plan_port=plan_port,
        v1=v1,
        v2=v2,
        seed_ids=seed_ids,
        selected=selected,
        base_refs=base_refs,
        render_refs=render_refs,
    )


@pytest.fixture
def world(pw_database: Any, manager: Any, pinned: tuple[Any, Any], tmp_path: Path) -> SimpleNamespace:
    return fix8_world(pw_database, manager, pinned, tmp_path)


def merged(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, Any]] = set()
    result: list[dict[str, Any]] = []
    for group in groups:
        for ref in group:
            key = (ref.get("ref_type"), ref.get("ref_id"))
            if key not in seen:
                seen.add(key)
                result.append(dict(ref))
    return result


def run_chain(world: Any, first_answer: dict[str, Any], *, after_blur: dict[str, Any] = SAFE, second_answer: dict[str, Any] = SAFE) -> list[dict[str, Any]]:
    world.vision.answers = {world.v1.sha: first_answer, world.v2.sha: second_answer}
    world.vision.default = after_blur
    produced: list[dict[str, Any]] = []
    for index, item in enumerate(world.selected):
        key = f"{JOB}:process:AssessImageSafety:{index}:r1"
        refs = merged([item], world.base_refs, world.selected, produced)
        result = run_media(world, "AssessImageSafety", "assess_image_safety", key, refs)
        assert result.receipt.disposition is Disposition.SUCCEEDED
        produced.extend(world.inputs.assessment_refs(r4_request("AssessImageSafety", key, refs)))

    for index, item in enumerate([r for r in produced if r["ref_type"] == "sensitive_image"]):
        key = f"{JOB}:process:TransformSensitiveImage:{index}:r1"
        refs = merged([item], world.base_refs, world.selected, produced)
        result = run_media(world, "TransformSensitiveImage", "transform_sensitive_image", key, refs)
        made = [{"ref_type": "media_artifact", "ref_id": ref} for ref in result.receipt.output_refs]
        produced.extend(world.inputs.transform_refs(r4_request("TransformSensitiveImage", key, refs), made))

    return produced


def e_choice(world: Any, produced: list[dict[str, Any]], item: dict[str, Any]) -> Any:
    return world.inputs.normalize_source(world.database.workspace_id, merged([item], world.base_refs, world.selected, produced))


def version_of(world: Any, ref: str) -> str:
    if ref.startswith("processed:"):
        with world.database.connect() as conn:
            row = conn.execute(
                "SELECT artifact_version_id::text FROM controlplane.cp_artifact_versions WHERE workspace_id = %s::uuid AND artifact_id = %s",
                (world.database.workspace_id, "media/" + ref.replace(":", "_") + ".png"),
            ).fetchone()
        assert row is not None, ref
        return row[0]
    return ref


def assert_render_follows_e(world: Any, produced: list[dict[str, Any]], *, replaced: tuple[str, ...] = ()) -> tuple[Any, dict[str, str]]:
    refs = merged(world.render_refs, world.selected, produced)
    inputs = world.sources.resolve_inputs(refs)
    record = resolve_render_package(inputs, world.plan_port)
    report = validate_render_package(record, world.sources.validation_context(record))
    assert report.passed is True, report.findings
    chosen = {item["ref_id"]: version_of(world, e_choice(world, produced, item).artifact.ref) for item in world.selected}
    assert [segment["visual_asset_refs"] for segment in inputs.timeline["segments"]] == [[chosen["m-1"]], [chosen["m-2"]]]
    manifest = record.materialization_manifest
    assert manifest["thumb:m-1"]["local_ref"] == chosen["m-1"]
    ids = {a.artifact_version_id for a in record.input_artifacts}
    assert chosen["m-1"] in ids and chosen["m-2"] in ids
    plan = world.sources.render_plan(record, "render:att:fix8")
    argv_text = json.dumps(list(plan.command_spec.argv))
    originals = {"m-1": world.v1.id, "m-2": world.v2.id}
    for media in replaced:
        original = originals[media]
        assert original not in ids
        assert original not in manifest
        assert not any(entry.get("local_ref") == original for entry in manifest.values())
        assert original not in argv_text
        assert original not in json.dumps(inputs.timeline)
        rules = [r for r in record.allowed_fallbacks if r.get("rule_id") == f"image-safety:{media}"]
        assert len(rules) == 1
        assert rules[0]["kind"] == "replace_asset"
        assert rules[0]["replaced_media_asset_id"] == media
        assert rules[0]["replaced_artifact_version_ref"] == original
        assert rules[0]["artifact_version_id"] == chosen[media]
    if not replaced:
        assert not any(str(r.get("rule_id", "")).startswith("image-safety:") for r in record.allowed_fallbacks)
    return (record, chosen)


def test_a_safe_image_renders_as_the_original(world: Any) -> None:
    produced = run_chain(world, SAFE)
    record, chosen = assert_render_follows_e(world, produced, replaced=())
    assert chosen == {"m-1": world.v1.id, "m-2": world.v2.id}


def test_a_blurred_image_that_is_safe_renders_as_the_registered_blurred_copy(world: Any) -> None:
    produced = run_chain(world, WEAPON, after_blur=SAFE)
    made = [r for r in produced if r.get("produced_by") == "TransformSensitiveImage"]
    assert len(made) == 1
    processed_ref = made[0]["ref_id"]
    record, chosen = assert_render_follows_e(world, produced, replaced=("m-1",))
    source = e_choice(world, produced, world.selected[0])
    assert source.reason == "blurred" and source.artifact.ref == processed_ref
    assert chosen["m-2"] == world.v2.id and chosen["m-1"] != world.v1.id
    with world.database.connect() as conn:
        row = conn.execute(
            "SELECT artifact_id, sha256_hash, retention_ref, owner_ref FROM controlplane.cp_artifact_versions WHERE workspace_id = %s::uuid AND artifact_version_id = %s::uuid",
            (world.database.workspace_id, chosen["m-1"]),
        ).fetchone()
    assert row is not None
    artifact_id, sha256_hash, retention_ref, owner_ref = row
    assert artifact_id == "media/" + processed_ref.replace(":", "_") + ".png"
    assert sha256_hash == source.artifact.content_sha256
    assert retention_ref == "durable"
    assert owner_ref == "m-1"
    disk_file = world.runtime.staging_root / artifact_id
    assert disk_file.is_file()
    assert hashlib.sha256(disk_file.read_bytes()).hexdigest() == source.artifact.content_sha256
    assert hashlib.sha256(disk_file.read_bytes()).hexdigest() != world.v1.sha


def test_a_blurred_copy_that_is_still_flagged_renders_as_the_blurred_copy_with_a_warning(world: Any) -> None:
    produced = run_chain(world, WEAPON, after_blur=WEAPON)
    record, chosen = assert_render_follows_e(world, produced, replaced=("m-1",))
    source = e_choice(world, produced, world.selected[0])
    assert source.reason == "blurred_with_warning" and source.artifact.ref.startswith("processed:")
    assert chosen["m-1"] not in (world.v1.id, *world.seed_ids) and chosen["m-2"] == world.v2.id


def test_an_unsure_image_renders_as_the_original(world: Any) -> None:
    produced = run_chain(world, UNCERTAIN)
    record, chosen = assert_render_follows_e(world, produced, replaced=())
    assert chosen == {"m-1": world.v1.id, "m-2": world.v2.id}
    assert e_choice(world, produced, world.selected[0]).reason == "uncertain"


@pytest.mark.parametrize(
    "first_answer,after_blur",
    [(NUDITY, SAFE)],
    ids=["nudity_sexual"],
)
def test_an_excluded_image_renders_as_another_usable_image_of_the_job(world: Any, first_answer: dict[str, Any], after_blur: dict[str, Any]) -> None:
    produced = run_chain(world, first_answer, after_blur=after_blur)
    record, chosen = assert_render_follows_e(world, produced, replaced=("m-1",))
    assert chosen["m-1"] == world.v2.id and chosen["m-2"] == world.v2.id
    rule = next(r for r in record.allowed_fallbacks if r.get("rule_id") == "image-safety:m-1")
    assert rule["reason"] == "image_fallback"
    assert not set(world.seed_ids) & {a.artifact_version_id for a in record.input_artifacts}
    with world.database.connect() as conn:
        count = conn.execute(
            "SELECT count(*) FROM controlplane.cp_artifact_versions WHERE workspace_id = %s::uuid AND artifact_id LIKE %s",
            (world.database.workspace_id, "media/processed%"),
        ).fetchone()[0]
    assert count == 0


def test_every_image_excluded_with_only_seed_replacements_fails_with_no_illustration_available(world: Any) -> None:
    produced = run_chain(world, NUDITY, second_answer=NUDITY)
    assert all(e_choice(world, produced, item).reason == "seed_fallback" for item in world.selected)
    with pytest.raises(ActivityInputError) as raised:
        world.sources.resolve_inputs(merged(world.render_refs, world.selected, produced))
    assert raised.value.code == "no_illustration_available"
    assert "seed_share_above_max" in str(raised.value)


def test_an_excluded_image_without_a_seed_fails_with_image_excluded(pw_database: Any, manager: Any, pinned: tuple[Any, Any], tmp_path: Path) -> None:
    world = fix8_world(pw_database, manager, pinned, tmp_path, seed_mode="none")
    produced = run_chain(world, NUDITY, second_answer=NUDITY)
    refs = merged(world.render_refs, world.selected, produced)
    with pytest.raises(ActivityInputError) as raised:
        world.sources.resolve_inputs(refs)
    assert raised.value.code == "INPUT_NOT_READY"
    assert "image_excluded:reject_category:m-1" in str(raised.value)


def test_a_media_without_an_assessment_decision_fails_with_image_not_assessed(world: Any) -> None:
    refs = merged(world.render_refs, [world.selected[1]])
    with pytest.raises(ActivityInputError) as raised:
        world.sources.resolve_inputs(refs)
    assert raised.value.code == "INPUT_NOT_READY"
    assert "image_not_assessed:m-1" in str(raised.value)


def test_a_replacement_version_that_is_not_verified_fails_closed(pw_database: Any, manager: Any, pinned: tuple[Any, Any], tmp_path: Path) -> None:
    world = fix8_world(pw_database, manager, pinned, tmp_path, seed_mode="unverified")
    produced = run_chain(world, NUDITY, second_answer=NUDITY)
    with pytest.raises(ActivityInputError) as raised:
        world.sources.resolve_inputs(merged(world.render_refs, world.selected, produced))
    assert raised.value.code == "INPUT_NOT_READY"
    assert "image_version_not_verified:m-1" in str(raised.value)


def test_without_selected_media_the_package_is_unchanged(world: Any) -> None:
    inputs = world.sources.resolve_inputs(world.render_refs)
    assert [s["visual_asset_refs"] for s in inputs.timeline["segments"]] == [[world.v1.id], [world.v2.id]]
    assert not [r for r in inputs.allowed_fallbacks if str(r.get("rule_id", "")).startswith("image-safety:")]
    ids = {a.artifact_version_id for a in inputs.input_artifacts}
    assert world.v1.id in ids and world.v2.id in ids
    record = resolve_render_package(inputs, world.plan_port)
    assert validate_render_package(record, world.sources.validation_context(record)).passed is True
