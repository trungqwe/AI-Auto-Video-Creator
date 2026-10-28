"""PW-F3: render inputs from ConfigRevision, ASS file with disclosure windows and PostgreSQL plan and artifact ports, on real PostgreSQL 18.6.

coveredIds: PW-F3-01, CT-QC-001, CT-REN-001, CT-AI-004
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import pathlib
import re
import uuid
from typing import Any

import pytest

import dataclasses
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import PureWindowsPath
from types import MappingProxyType, SimpleNamespace

from catalog.application.hooks import import_hook
from catalog.domain.hooks import HookKind
from catalog.persistence.hooks import PostgresHookHistory
from controlplane.api.wiring.production_profile import ProductionRuntime, load_production_profile
from controlplane.api.wiring.render import ProductionRenderSources
from controlplane.application.storage_meta.handlers import register_staged_artifact
from controlplane.infrastructure.production_ports.gpu_lease import LocalGpuLease
from creative.domain.asset_selection import CreativeAssetSelection, SceneAssignment
from creative.domain.production_plan import build_production_plan
from creative.domain.ref_resolver import ResourceRef
from creative.domain.script import ScriptSegment, ScriptVersion
from render.adapters.activity_inputs import ActivityInputError
from render.domain.validate_package import validate_render_package
from controlplane.infrastructure.db.control_api_commands import PostgresConfigScope, compose_command_service
from controlplane.infrastructure.db.uow import TransactionManager
from render.adapters.ass_manifest import (
    AssManifestRejected,
    AssMaterial,
    build_ass_material,
    with_ass_entry,
)
from render.adapters.config_render_sources import (
    ConfigRenderSources,
    RenderConfigMissing,
    RenderConfigNotSeeded,
    ass_colour,
    ass_inputs,
    seed_render_config,
)
from render.adapters.postgres_plan_assets import (
    PlanPayloadInvalid,
    PostgresArtifactInfo,
    PostgresPlanAssets,
    ScriptSegmentInfo,
    ScriptSegmentsError,
    read_script_segments,
)
from render.domain.karaoke_plan import parse_word_timing
from render.domain.render_command import (
    MaterializedPaths,
    RenderCommandRejected,
    ToolIdentity,
    build_render_command,
)
from render.domain.resolve_package import (
    ASSET_OUTSIDE_PLAN_OR_FALLBACK,
    ResolveError,
    resolve_render_package,
)
from render.ports.inputs import (
    ArtifactInfoPort,
    LocalMaterialRef,
    PlanAssetPort,
    ResolveInputs,
    ResolvedAsset,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
PROFILE_PATH = ROOT / 'tools' / 'launcher' / 'prod' / 'profile.json'
PARAMS = dict(load_production_profile(PROFILE_PATH).parameters)
SUPPLEMENTS = {
    'ass_style': {
        'secondary_colour': '&H00FFFFFF',
        'back_colour': '&H80000000',
        'italic': 0,
        'underline': 0,
        'strike_out': 0,
        'scale_x': 100,
        'scale_y': 100,
        'spacing': 0,
        'angle': 0,
        'border_style': 1,
        'shadow': 0,
        'alignment': 2,
        'encoding': 1,
    },
    'layout': {
        'margin_left': 60,
        'margin_right': 60,
        'max_words_per_line': 4,
        'max_chars_per_line': 28,
        'disclosure_font_size': 40,
        'disclosure_alignment': 8,
        'disclosure_margin_v': 240,
    },
    'sections': {
        'visual_rhythm': {'note': 'pw-f3'},
        'thumbnail_overlay_style': {'note': 'pw-f3'},
        'hook_treatment': {'note': 'pw-f3'},
        'color_effect_rules': {'note': 'pw-f3'},
    },
    'quality_thresholds': {
        'SUBTITLE_BURNED_IN': {'min_frames_with_text': 2},
        'VOICE_AUDIBLE': {'min_voice_level': -40.0},
    },
    'output_profile': {
        'video_codec': 'h264',
        'pixel_format': 'yuv420p',
    },
}
WORDS = ['Prices', 'rose', 'sharply', 'today', 'Analysts', 'suspect', 'supply', 'shortage']
V1 = '00000000-0000-4000-8000-0000000000f1'
V2 = '00000000-0000-4000-8000-0000000000f2'
VOICE = '00000000-0000-4000-8000-0000000000f3'
OTHER = '00000000-0000-4000-8000-0000000000f4'
SCRIPT_ID = 'script-f3'
PLAN_ID = 'plan-f3'
TIMING_REF = 'timing-f3'
DISCLOSURE = 'Analyst inference, not confirmed by sources'
_DEFAULT_HASH = object()

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


class FreshScope:
    def __init__(self, database: Any) -> None:
        self._database = database

    def current(self, *, workspace_id: str, scope_kind: str, scope_key: str) -> Any | None:
        with self._database.connect() as connection:
            return PostgresConfigScope(connection).current(
                workspace_id=workspace_id, scope_kind=scope_kind, scope_key=scope_key
            )


def sources(db: Any) -> ConfigRenderSources:
    return ConfigRenderSources(FreshScope(db), db.workspace_id)


def seed(service_inst: Any, db: Any) -> tuple[str, ...]:
    return seed_render_config(
        service_inst,
        workspace_id=db.workspace_id,
        actor_id=db.actor_id,
        parameters=PARAMS,
        supplements=SUPPLEMENTS,
    )


@pytest.fixture
def pinned(pw_database: Any, service: Any) -> tuple[Any, Any]:
    seed(service, pw_database)
    srcs = sources(pw_database)
    return srcs.preset('bold-yellow'), srcs.output_profile()


def insert_artifact(
    db: Any,
    version_id: str,
    kind: str = 'visual',
    size: int = 1000,
    mime: str = 'video/mp4',
    states: tuple[str, ...] = ('VERIFIED',),
    observed_hash: Any = _DEFAULT_HASH,
) -> str:
    sha = hashlib.sha256(version_id.encode()).hexdigest()
    with db.connect() as conn:
        conn.execute(
            'INSERT INTO controlplane.cp_artifact_versions '
            '(artifact_version_id, workspace_id, artifact_id, sha256_hash, size_bytes, mime_type, artifact_kind, owner_ref, retention_ref, sensitivity_ref) '
            'VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s)',
            (version_id, db.workspace_id, f'art-{version_id}', sha, size, mime, kind, 'x', 'x', 'x'),
        )
        for state in states:
            loc_id = str(uuid.uuid4())
            obs = sha if observed_hash is _DEFAULT_HASH else observed_hash
            conn.execute(
                'INSERT INTO controlplane.cp_artifact_locations '
                '(location_id, workspace_id, artifact_version_id, backend_ref, provider_namespace_ref, provider_object_ref, logical_locator, state, observed_hash) '
                'VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s)',
                (loc_id, db.workspace_id, version_id, 'x', 'x', f'obj-{loc_id}', 'x', state, obs),
            )
    return sha


def insert_plan(db: Any, payload: Mapping, plan_id: str = PLAN_ID) -> None:
    with db.connect() as conn:
        conn.execute(
            'INSERT INTO controlplane.cp_production_plans '
            '(workspace_id, record_key, revision, payload, production_plan_id) '
            'VALUES (%s::uuid, %s, 1, %s::jsonb, %s)',
            (db.workspace_id, plan_id, json.dumps(payload), plan_id),
        )


def script_segments_payload(modes: Sequence[str], counts: Sequence[int]) -> list[dict]:
    return [
        {
            'segment_id': f'seg-{i}',
            'order': i,
            'text': 'x',
            'claim_mode': modes[i],
            'scene_intent': 'scene',
            'source_refs': [],
            'disclosure': DISCLOSURE if modes[i] in ('inference', 'creative_hypothesis') else None,
            'word_count': counts[i],
            'estimated_seconds': 1.0,
        }
        for i in range(len(modes))
    ]


def insert_script(db: Any, segments: Sequence[dict], script_id: str = SCRIPT_ID) -> None:
    with db.connect() as conn:
        conn.execute(
            'INSERT INTO controlplane.cp_script_versions '
            '(workspace_id, record_key, revision, payload, script_version_id) '
            'VALUES (%s::uuid, %s, 1, %s::jsonb, %s)',
            (
                db.workspace_id,
                script_id,
                json.dumps({'script_version_id': script_id, 'segments': list(segments)}),
                script_id,
            ),
        )


def timing_payload() -> dict:
    words_data = [
        {'text': word, 'start_ms': i * 500, 'end_ms': i * 500 + 400}
        for i, word in enumerate(WORDS)
    ]
    return {
        'script_version_id': SCRIPT_ID,
        'script_fingerprint': 'a' * 64,
        'voice_hash': 'b' * 64,
        'timing_artifact_ref': TIMING_REF,
        'words': words_data,
        'segment_boundaries': [{'start_ms': 0, 'end_ms': 3900}],
        'validation_report_ref': 'report-f3',
        'voice_duration_ms': 4000,
    }


def insert_timing(db: Any) -> None:
    payload = timing_payload()
    with db.connect() as conn:
        conn.execute(
            'INSERT INTO controlplane.cp_word_timings '
            '(workspace_id, record_key, revision, payload, timing_artifact_ref) '
            'VALUES (%s::uuid, %s, 1, %s::jsonb, %s) '
            'ON CONFLICT (workspace_id, record_key, revision) DO NOTHING',
            (db.workspace_id, TIMING_REF, json.dumps(payload), TIMING_REF),
        )


def read_words(db: Any):
    with db.connect() as conn:
        row = conn.execute(
            'SELECT payload FROM controlplane.cp_word_timings '
            'WHERE workspace_id = %s::uuid AND timing_artifact_ref = %s',
            (db.workspace_id, TIMING_REF),
        ).fetchone()
    raw = json.loads(row[0]) if isinstance(row[0], str) else row[0]
    return parse_word_timing(raw).words


def edit(service_inst: Any, db: Any, kind: str, key: str, change: Any) -> str:
    current = FreshScope(db).current(workspace_id=db.workspace_id, scope_kind=kind, scope_key=key)
    receipt = service_inst.put_config(
        workspace_id=db.workspace_id,
        actor_id=db.actor_id,
        idempotency_key=f'edit-{kind}-{key}-{current.config_revision_number}',
        scope_kind=kind,
        scope_key=key,
        expected_revision=current.revision,
        payload=change(copy.deepcopy(current.payload)),
    )
    return receipt['resource_ref']['config_revision_id']


def base_entries() -> tuple[LocalMaterialRef, ...]:
    return (
        LocalMaterialRef(artifact_version_id=V1, local_ref='visual-1.mp4'),
        LocalMaterialRef(artifact_version_id=V2, local_ref='visual-2.mp4'),
        LocalMaterialRef(artifact_version_id=VOICE, local_ref='voice.wav'),
    )


def resolve_inputs(db: Any, mgr: Any, pins: tuple[Any, Any], entries: Sequence[LocalMaterialRef]) -> ResolveInputs:
    art_info = PostgresArtifactInfo(mgr, workspace_id=db.workspace_id)
    input_artifacts = (
        art_info.get_asset(V1),
        art_info.get_asset(V2),
        art_info.get_asset(VOICE),
    )
    return ResolveInputs(
        production_snapshot_ref='snap-f3',
        script_version_ref=SCRIPT_ID,
        production_plan_ref=PLAN_ID,
        preset_revision_ref=pins[0].revision_ref,
        voice_artifact_ref=VOICE,
        word_timing_ref=TIMING_REF,
        output_metadata_revision='meta-f3',
        output_profile_revision=pins[1].revision_ref,
        language_validation_refs=('lang-f3',),
        input_artifacts=input_artifacts,
        timeline={
            'segments': [
                {'start_ms': 0, 'end_ms': 2000, 'visual_asset_refs': [V1]},
                {'start_ms': 2000, 'end_ms': 4000, 'visual_asset_refs': [V2]},
            ]
        },
        hook_placement={
            'visual_hook_ref': V1,
            'audio_hook_ref': VOICE,
            'thumbnail_ref': V1,
            'hook_time_range': {'start_ms': 0, 'end_ms': 2000},
            'thumbnail_time_range': {'start_ms': 500, 'end_ms': 1500},
        },
        subtitle_config={'karaoke': True},
        mix_plan={},
        allowed_fallbacks=(),
        materialization_manifest=entries,
        output_path_ref='out-f3',
    )


def material(db: Any, tmp_path: pathlib.Path, pins: tuple[Any, Any], segments: Sequence[ScriptSegmentInfo]):
    insert_timing(db)
    words = read_words(db)
    inputs = ass_inputs(pins[0].preset, pins[1].profile)
    return build_ass_material(
        staging_root=str(tmp_path),
        words=words,
        typography=inputs.typography,
        safe_area=inputs.safe_area,
        profile=inputs.profile,
        disclosure_style=inputs.disclosure_style,
        segments=segments,
    )

# --- Step 12: Configuration Tests ---


def test_module_docstring_declares_covered_ids() -> None:
    doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
    assert doc is not None
    lines = [line for line in doc.splitlines() if line.startswith('coveredIds:')]
    assert len(lines) == 1
    ids = {x.strip() for x in lines[0][len('coveredIds:'):].split(',')}
    assert {'PW-F3-01', 'CT-QC-001', 'CT-REN-001', 'CT-AI-004'} <= ids


def test_seed_writes_output_profile_presets_and_policy_once(pw_database: Any, service: Any) -> None:
    variants = PARAMS['render.presets']['variants']
    first_res = seed(service, pw_database)
    assert len(first_res) == 2 + len(variants)

    with pw_database.connect() as conn:
        preset_count = conn.execute(
            'SELECT count(*) FROM controlplane.cp_config_revisions '
            'WHERE workspace_id = %s::uuid AND scope_kind = %s',
            (pw_database.workspace_id, 'preset'),
        ).fetchone()[0]
        policy_count = conn.execute(
            'SELECT count(*) FROM controlplane.cp_config_revisions '
            'WHERE workspace_id = %s::uuid AND scope_kind = %s',
            (pw_database.workspace_id, 'policy'),
        ).fetchone()[0]
        statuses = conn.execute(
            'SELECT status FROM controlplane.cp_config_revisions WHERE workspace_id = %s::uuid',
            (pw_database.workspace_id,),
        ).fetchall()

    assert preset_count == 1 + len(variants)
    assert policy_count == 1
    assert all(row[0] == 'PUBLISHED' for row in statuses)

    second_res = seed(service, pw_database)
    assert second_res == ()

    with pw_database.connect() as conn:
        total_after = conn.execute(
            'SELECT count(*) FROM controlplane.cp_config_revisions WHERE workspace_id = %s::uuid',
            (pw_database.workspace_id,),
        ).fetchone()[0]
    assert total_after == preset_count + policy_count


def test_seeded_values_come_from_the_profile(pw_database: Any, service: Any) -> None:
    seed(service, pw_database)
    srcs = sources(pw_database)

    pinned_preset = srcs.preset('bold-yellow')
    preset = pinned_preset.preset
    common = PARAMS['render.presets']['common']
    assert preset.typography_karaoke_style['font_name'] == common['font']
    assert preset.typography_karaoke_style['primary_colour'] == ass_colour('#FFD400') == '&H0000D4FF'
    assert preset.output_profile_ref == 'output-profile'

    pinned_profile = srcs.output_profile()
    profile = pinned_profile.profile
    rf = PARAMS['render.profile']
    assert profile.width == rf['width']
    assert profile.height == rf['height']
    assert profile.fps == rf['fps']
    assert profile.container == rf['container']
    assert profile.audio_codec == rf['audio_codec']
    assert profile.encoder == rf['video_codec']
    assert profile.video_codec == 'h264'

    pinned_policy = srcs.quality_policy()
    policy = pinned_policy.policy
    assert policy.thresholds['DURATION_RANGE']['duration_range_ms'] == (61000, 70000)
    assert policy.thresholds['KARAOKE_TIMING_VALID']['tolerance_ms'] == PARAMS['qc.karaoke_tolerance_ms']


def test_missing_inputs_name_the_parameter_and_write_nothing(pw_database: Any, service: Any) -> None:
    supp_without_ass = copy.deepcopy(SUPPLEMENTS)
    del supp_without_ass['ass_style']
    with pytest.raises(RenderConfigMissing) as exc_info:
        seed_render_config(service, workspace_id=pw_database.workspace_id, actor_id=pw_database.actor_id, parameters=PARAMS, supplements=supp_without_ass)
    assert exc_info.value.parameter == 'supplements.ass_style'

    params_without_presets = copy.deepcopy(PARAMS)
    del params_without_presets['render.presets']
    with pytest.raises(RenderConfigMissing) as exc_info:
        seed_render_config(service, workspace_id=pw_database.workspace_id, actor_id=pw_database.actor_id, parameters=params_without_presets, supplements=SUPPLEMENTS)
    assert exc_info.value.parameter == 'render.presets'

    supp_without_italic = copy.deepcopy(SUPPLEMENTS)
    del supp_without_italic['ass_style']['italic']
    with pytest.raises(RenderConfigMissing) as exc_info:
        seed_render_config(service, workspace_id=pw_database.workspace_id, actor_id=pw_database.actor_id, parameters=PARAMS, supplements=supp_without_italic)
    assert exc_info.value.parameter == 'supplements.ass_style.italic'

    with pw_database.connect() as conn:
        count = conn.execute(
            'SELECT count(*) FROM controlplane.cp_config_revisions WHERE workspace_id = %s::uuid',
            (pw_database.workspace_id,),
        ).fetchone()[0]
    assert count == 0


def test_unseeded_sources_raise_not_seeded(pw_database: Any) -> None:
    srcs = sources(pw_database)
    with pytest.raises(RenderConfigNotSeeded):
        srcs.preset('bold-yellow')
    with pytest.raises(RenderConfigNotSeeded):
        srcs.output_profile()
    with pytest.raises(RenderConfigNotSeeded):
        srcs.quality_policy()


def test_ass_colour_converts_and_rejects() -> None:
    assert ass_colour('#000000') == '&H00000000'
    assert ass_colour('#FF3B30') == '&H00303BFF'
    for invalid in ('FFD400', '#FFD40', 'red', ''):
        with pytest.raises(ValueError):
            ass_colour(invalid)


def test_no_values_are_constants_in_the_adapter() -> None:
    adapter_text = (ROOT / 'src' / 'render' / 'adapters' / 'config_render_sources.py').read_text(encoding='utf-8')
    assert '1080' not in adapter_text
    assert '1920' not in adapter_text
    assert 'Arial' not in adapter_text
    assert '61000' not in adapter_text


# --- Step 13: Revision Pinning Tests ---


def test_new_preset_revision_is_pinned_by_the_next_render(pw_database: Any, service: Any) -> None:
    seed(service, pw_database)
    first = sources(pw_database).preset('bold-yellow')
    new_rev_id = edit(
        service,
        pw_database,
        'preset',
        'bold-yellow',
        lambda p: {**p, 'typography_karaoke_style': {**p['typography_karaoke_style'], 'font_size': 80}},
    )
    second = sources(pw_database).preset('bold-yellow')
    assert second.revision_ref == new_rev_id
    assert second.revision_ref != first.revision_ref
    assert second.preset.revision == first.preset.revision + 1
    assert second.preset.typography_karaoke_style['font_size'] == 80
    assert first.preset.typography_karaoke_style['font_size'] == PARAMS['render.presets']['common']['font_size']
    assert second.preset.preset_fingerprint != first.preset.preset_fingerprint
    clean_white = sources(pw_database).preset('clean-white')
    assert clean_white.revision_ref != new_rev_id


def test_new_output_profile_revision_is_pinned(pw_database: Any, service: Any) -> None:
    seed(service, pw_database)
    first = sources(pw_database).output_profile()
    new_rev_id = edit(
        service,
        pw_database,
        'preset',
        'output-profile',
        lambda p: {**p, 'fps': 24},
    )
    second = sources(pw_database).output_profile()
    assert second.revision_ref == new_rev_id
    assert second.revision_ref != first.revision_ref
    assert second.profile.fps == 24
    assert first.profile.fps == 30


def test_new_quality_policy_revision_is_pinned(pw_database: Any, service: Any) -> None:
    seed(service, pw_database)
    first = sources(pw_database).quality_policy()
    new_rev_id = edit(
        service,
        pw_database,
        'policy',
        'quality',
        lambda p: {
            **p,
            'thresholds': {
                **p['thresholds'],
                'KARAOKE_TIMING_VALID': {'tolerance_ms': 99},
            },
        },
    )
    second = sources(pw_database).quality_policy()
    assert second.revision_ref == new_rev_id
    assert second.policy.revision == new_rev_id
    assert second.policy.thresholds['KARAOKE_TIMING_VALID']['tolerance_ms'] == 99
    assert first.policy.thresholds['KARAOKE_TIMING_VALID']['tolerance_ms'] == PARAMS['qc.karaoke_tolerance_ms']


def test_seed_does_not_overwrite_an_edited_revision(pw_database: Any, service: Any) -> None:
    seed(service, pw_database)
    edit(
        service,
        pw_database,
        'preset',
        'bold-yellow',
        lambda p: {**p, 'typography_karaoke_style': {**p['typography_karaoke_style'], 'font_size': 80}},
    )
    assert seed(service, pw_database) == ()
    assert sources(pw_database).preset('bold-yellow').preset.typography_karaoke_style['font_size'] == 80


def test_edited_preset_changes_the_ass_style(pw_database: Any, service: Any, tmp_path: pathlib.Path) -> None:
    seed(service, pw_database)
    orig_preset = sources(pw_database).preset('bold-yellow')
    profile = sources(pw_database).output_profile().profile
    insert_timing(pw_database)
    words = read_words(pw_database)
    default_segs = (
        ScriptSegmentInfo(segment_id='s0', order=0, claim_mode='source_backed', disclosure=None, word_count=4),
        ScriptSegmentInfo(segment_id='s1', order=1, claim_mode='source_backed', disclosure=None, word_count=4),
    )

    orig_inputs = ass_inputs(orig_preset.preset, profile)
    mat_orig = build_ass_material(
        staging_root=str(tmp_path / 'orig'),
        words=words,
        typography=orig_inputs.typography,
        safe_area=orig_inputs.safe_area,
        profile=orig_inputs.profile,
        disclosure_style=orig_inputs.disclosure_style,
        segments=default_segs,
    )
    common_font_size = PARAMS['render.presets']['common']['font_size']
    assert f',Arial,{common_font_size},' in mat_orig.text

    edit(
        service,
        pw_database,
        'preset',
        'bold-yellow',
        lambda p: {**p, 'typography_karaoke_style': {**p['typography_karaoke_style'], 'font_size': 80}},
    )
    edited_preset = sources(pw_database).preset('bold-yellow')
    edited_inputs = ass_inputs(edited_preset.preset, profile)
    mat_edited = build_ass_material(
        staging_root=str(tmp_path / 'edited'),
        words=words,
        typography=edited_inputs.typography,
        safe_area=edited_inputs.safe_area,
        profile=edited_inputs.profile,
        disclosure_style=edited_inputs.disclosure_style,
        segments=default_segs,
    )
    assert ',Arial,80,' in mat_edited.text

# --- Step 14: Production Port Tests ---


def test_ports_satisfy_the_render_protocols(pw_database: Any, manager: Any) -> None:
    plan_assets = PostgresPlanAssets(manager, workspace_id=pw_database.workspace_id)
    artifact_info = PostgresArtifactInfo(manager, workspace_id=pw_database.workspace_id)
    assert isinstance(plan_assets, PlanAssetPort)
    assert isinstance(artifact_info, ArtifactInfoPort)


def test_plan_asset_port_returns_the_set_the_plan_allows(pw_database: Any, manager: Any) -> None:
    insert_plan(
        pw_database,
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
    )
    port = PostgresPlanAssets(manager, workspace_id=pw_database.workspace_id)
    assert port.asset_refs(PLAN_ID) == tuple(sorted({V1, V2, VOICE}))
    assert port.asset_refs('plan-unknown') is None

    insert_plan(pw_database, {'timeline': 3}, plan_id='plan-bad')
    with pytest.raises(PlanPayloadInvalid):
        port.asset_refs('plan-bad')


def test_asset_outside_the_plan_is_rejected_by_resolve(pw_database: Any, manager: Any, pinned: tuple[Any, Any]) -> None:
    for vid in (V1, V2, VOICE, OTHER):
        insert_artifact(pw_database, vid)

    insert_plan(
        pw_database,
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
    )

    art_info = PostgresArtifactInfo(manager, workspace_id=pw_database.workspace_id)
    other_asset = art_info.get_asset(OTHER)
    entries = base_entries()
    inputs = resolve_inputs(pw_database, manager, pinned, entries)
    inputs_with_other = ResolveInputs(
        production_snapshot_ref=inputs.production_snapshot_ref,
        script_version_ref=inputs.script_version_ref,
        production_plan_ref=inputs.production_plan_ref,
        preset_revision_ref=inputs.preset_revision_ref,
        voice_artifact_ref=inputs.voice_artifact_ref,
        word_timing_ref=inputs.word_timing_ref,
        output_metadata_revision=inputs.output_metadata_revision,
        output_profile_revision=inputs.output_profile_revision,
        language_validation_refs=inputs.language_validation_refs,
        input_artifacts=(*inputs.input_artifacts, other_asset),
        timeline=inputs.timeline,
        hook_placement=inputs.hook_placement,
        subtitle_config=inputs.subtitle_config,
        mix_plan=inputs.mix_plan,
        allowed_fallbacks=inputs.allowed_fallbacks,
        materialization_manifest=inputs.materialization_manifest,
        output_path_ref=inputs.output_path_ref,
    )
    plan_port = PostgresPlanAssets(manager, workspace_id=pw_database.workspace_id)
    with pytest.raises(ResolveError) as exc_info:
        resolve_render_package(inputs_with_other, plan_port)
    assert exc_info.value.code == ASSET_OUTSIDE_PLAN_OR_FALLBACK

    inputs_unknown_plan = ResolveInputs(
        production_snapshot_ref=inputs.production_snapshot_ref,
        script_version_ref=inputs.script_version_ref,
        production_plan_ref='plan-unknown',
        preset_revision_ref=inputs.preset_revision_ref,
        voice_artifact_ref=inputs.voice_artifact_ref,
        word_timing_ref=inputs.word_timing_ref,
        output_metadata_revision=inputs.output_metadata_revision,
        output_profile_revision=inputs.output_profile_revision,
        language_validation_refs=inputs.language_validation_refs,
        input_artifacts=inputs.input_artifacts,
        timeline=inputs.timeline,
        hook_placement=inputs.hook_placement,
        subtitle_config=inputs.subtitle_config,
        mix_plan=inputs.mix_plan,
        allowed_fallbacks=inputs.allowed_fallbacks,
        materialization_manifest=inputs.materialization_manifest,
        output_path_ref=inputs.output_path_ref,
    )
    with pytest.raises(ResolveError) as exc_info:
        resolve_render_package(inputs_unknown_plan, plan_port)
    assert exc_info.value.field == 'plan_assets'


def test_artifact_info_returns_facts_and_none_when_unknown(pw_database: Any, manager: Any) -> None:
    sha = insert_artifact(pw_database, V1, kind='visual', size=1234, mime='video/mp4')
    port = PostgresArtifactInfo(manager, workspace_id=pw_database.workspace_id)

    asset = port.get_asset(V1)
    assert asset is not None
    assert asset.artifact_version_id == V1
    assert asset.sha256 == sha
    assert asset.size_bytes == 1234
    assert asset.media_type == 'video/mp4'
    assert asset.role == 'visual'

    assert port.get_asset(str(uuid.uuid4())) is None
    assert port.get_asset('not-a-uuid') is None

    no_loc_id = '00000000-0000-4000-8000-000000000010'
    insert_artifact(pw_database, no_loc_id, states=())
    assert port.get_asset(no_loc_id) is None

    corrupt_id = '00000000-0000-4000-8000-000000000011'
    insert_artifact(pw_database, corrupt_id, states=('CORRUPT',))
    assert port.get_asset(corrupt_id) is None

    bad_hash_id = '00000000-0000-4000-8000-000000000012'
    insert_artifact(pw_database, bad_hash_id, states=('VERIFIED',), observed_hash='f' * 64)
    assert port.get_asset(bad_hash_id) is None

    mixed_id = '00000000-0000-4000-8000-000000000013'
    insert_artifact(pw_database, mixed_id, states=('MISSING', 'VERIFIED'))
    assert port.get_asset(mixed_id) is not None


def test_ports_read_the_tables_not_a_cache(pw_database: Any, manager: Any) -> None:
    port = PostgresArtifactInfo(manager, workspace_id=pw_database.workspace_id)
    dynamic_id = '00000000-0000-4000-8000-000000000099'
    insert_artifact(pw_database, dynamic_id, states=())
    assert port.get_asset(dynamic_id) is None

    sha = hashlib.sha256(dynamic_id.encode()).hexdigest()
    with pw_database.connect() as conn:
        loc_id = str(uuid.uuid4())
        conn.execute(
            'INSERT INTO controlplane.cp_artifact_locations '
            '(location_id, workspace_id, artifact_version_id, backend_ref, provider_namespace_ref, provider_object_ref, logical_locator, state, observed_hash) '
            'VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s)',
            (loc_id, pw_database.workspace_id, dynamic_id, 'x', 'x', f'obj-{loc_id}', 'x', 'VERIFIED', sha),
        )
    assert port.get_asset(dynamic_id) is not None


# --- Step 15: Read Script Segments Tests ---


def test_read_script_segments_returns_the_five_fields_sorted_by_order(pw_database: Any, manager: Any) -> None:
    modes = ['source_backed', 'inference', 'source_backed']
    counts = [2, 3, 3]
    segs = script_segments_payload(modes, counts)
    insert_script(pw_database, [segs[2], segs[0], segs[1]])

    result = read_script_segments(manager, workspace_id=pw_database.workspace_id, script_version_ref=SCRIPT_ID)
    assert len(result) == 3
    assert [s.order for s in result] == [0, 1, 2]
    assert [s.segment_id for s in result] == ['seg-0', 'seg-1', 'seg-2']
    assert [s.claim_mode for s in result] == modes
    assert [s.word_count for s in result] == counts
    assert result[0].disclosure is None
    assert result[1].disclosure == DISCLOSURE
    assert result[2].disclosure is None


def test_read_script_segments_unknown_script_has_a_code(pw_database: Any, manager: Any) -> None:
    with pytest.raises(ScriptSegmentsError) as exc_info:
        read_script_segments(manager, workspace_id=pw_database.workspace_id, script_version_ref='script-unknown')
    assert exc_info.value.code == 'SCRIPT_NOT_FOUND'


def test_read_script_segments_rejects_invalid_payload(pw_database: Any, manager: Any) -> None:
    with pw_database.connect() as conn:
        conn.execute(
            'INSERT INTO controlplane.cp_script_versions '
            '(workspace_id, record_key, revision, payload, script_version_id) '
            'VALUES (%s::uuid, %s, 1, %s::jsonb, %s)',
            (pw_database.workspace_id, 'script-no-segs', json.dumps({'script_version_id': 'script-no-segs'}), 'script-no-segs'),
        )
    with pytest.raises(ScriptSegmentsError) as exc_info:
        read_script_segments(manager, workspace_id=pw_database.workspace_id, script_version_ref='script-no-segs')
    assert exc_info.value.code == 'SCRIPT_PAYLOAD_INVALID'

    bad_seg = {'segment_id': 's0', 'order': 0, 'claim_mode': 'source_backed'}
    insert_script(pw_database, [bad_seg], script_id='script-no-wc')
    with pytest.raises(ScriptSegmentsError) as exc_info:
        read_script_segments(manager, workspace_id=pw_database.workspace_id, script_version_ref='script-no-wc')
    assert exc_info.value.code == 'SCRIPT_PAYLOAD_INVALID'

    dup_id_segs = [
        {'segment_id': 'dup', 'order': 0, 'claim_mode': 'source_backed', 'word_count': 1},
        {'segment_id': 'dup', 'order': 1, 'claim_mode': 'source_backed', 'word_count': 1},
    ]
    insert_script(pw_database, dup_id_segs, script_id='script-dup-id')
    with pytest.raises(ScriptSegmentsError) as exc_info:
        read_script_segments(manager, workspace_id=pw_database.workspace_id, script_version_ref='script-dup-id')
    assert exc_info.value.code == 'SCRIPT_PAYLOAD_INVALID'


def test_read_script_segments_is_scoped_to_the_workspace(pw_database: Any, manager: Any) -> None:
    segs = script_segments_payload(['source_backed'], [8])
    insert_script(pw_database, segs, script_id='script-scoped')
    other_ws = str(uuid.uuid4())
    with pytest.raises(ScriptSegmentsError) as exc_info:
        read_script_segments(manager, workspace_id=other_ws, script_version_ref='script-scoped')
    assert exc_info.value.code == 'SCRIPT_NOT_FOUND'

# --- Step 16: ASS and Manifest Tests ---


def test_ass_has_karaoke_events_for_every_word_and_is_written_to_staging(
    pw_database: Any, pinned: tuple[Any, Any], tmp_path: pathlib.Path
) -> None:
    segs = (
        ScriptSegmentInfo(segment_id='seg-0', order=0, claim_mode='source_backed', disclosure=None, word_count=4),
        ScriptSegmentInfo(segment_id='seg-1', order=1, claim_mode='source_backed', disclosure=None, word_count=4),
    )
    mat = material(pw_database, tmp_path, pinned, segs)
    target = pathlib.Path(mat.local_path)
    assert target.is_file()
    text = target.read_text(encoding='utf-8')
    assert text == mat.text

    dialogue_lines = [line for line in text.splitlines() if line.startswith('Dialogue:')]
    assert dialogue_lines
    extracted_words = []
    for line in dialogue_lines:
        parts = line.split(',', 9)
        assert parts[3] == 'Karaoke'
        raw_text = parts[9]
        stripped = re.sub(r'\{[^}]*\}', '', raw_text).strip()
        if stripped:
            extracted_words.extend(stripped.split())

    assert extracted_words == WORDS
    assert text.count('{\\k') >= len(WORDS)
    assert 'Disclosure' not in text
    assert target.name == f'{mat.sha256}.ass'
    assert hashlib.sha256(text.encode('utf-8')).hexdigest() == mat.sha256


def test_ass_enters_the_manifest_and_build_render_command_accepts_it(
    pw_database: Any, manager: Any, pinned: tuple[Any, Any], tmp_path: pathlib.Path
) -> None:
    for vid in (V1, V2, VOICE):
        insert_artifact(pw_database, vid)
    insert_plan(
        pw_database,
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
    )
    segs = (
        ScriptSegmentInfo(segment_id='seg-0', order=0, claim_mode='source_backed', disclosure=None, word_count=4),
        ScriptSegmentInfo(segment_id='seg-1', order=1, claim_mode='source_backed', disclosure=None, word_count=4),
    )
    mat = material(pw_database, tmp_path, pinned, segs)
    entries = with_ass_entry(base_entries(), mat)
    inputs = resolve_inputs(pw_database, manager, pinned, entries)
    plan_port = PostgresPlanAssets(manager, workspace_id=pw_database.workspace_id)
    record = resolve_render_package(inputs, plan_port)

    assert record.materialization_manifest[mat.ass_ref]['local_ref'].endswith('.ass')
    spec = build_render_command(
        record,
        pinned[0].preset,
        pinned[1].profile,
        mat.ass_ref,
        ToolIdentity(name='ffmpeg', version='test', build='test-build', executable='C:/tools/ffmpeg.exe'),
        MaterializedPaths(staging_root=str(tmp_path), output_path='out/final.mp4', thumbnail_path='out/thumb.jpg'),
    )
    assert any(mat.entry.local_ref in arg for arg in spec.argv)


def test_manifest_without_the_ass_entry_is_rejected(
    pw_database: Any, manager: Any, pinned: tuple[Any, Any], tmp_path: pathlib.Path
) -> None:
    for vid in (V1, V2, VOICE):
        insert_artifact(pw_database, vid)
    insert_plan(
        pw_database,
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
    )
    segs = (
        ScriptSegmentInfo(segment_id='seg-0', order=0, claim_mode='source_backed', disclosure=None, word_count=4),
        ScriptSegmentInfo(segment_id='seg-1', order=1, claim_mode='source_backed', disclosure=None, word_count=4),
    )
    mat = material(pw_database, tmp_path, pinned, segs)
    entries = base_entries()
    inputs = resolve_inputs(pw_database, manager, pinned, entries)
    plan_port = PostgresPlanAssets(manager, workspace_id=pw_database.workspace_id)
    record = resolve_render_package(inputs, plan_port)

    with pytest.raises(RenderCommandRejected) as exc_info:
        build_render_command(
            record,
            pinned[0].preset,
            pinned[1].profile,
            mat.ass_ref,
            ToolIdentity(name='ffmpeg', version='test', build='test-build', executable='C:/tools/ffmpeg.exe'),
            MaterializedPaths(staging_root=str(tmp_path), output_path='out/final.mp4', thumbnail_path='out/thumb.jpg'),
        )
    assert exc_info.value.code == 'asset_not_materialized'


def test_ass_material_is_content_addressed_and_idempotent(
    pw_database: Any, pinned: tuple[Any, Any], tmp_path: pathlib.Path
) -> None:
    segs = (
        ScriptSegmentInfo(segment_id='seg-0', order=0, claim_mode='source_backed', disclosure=None, word_count=4),
        ScriptSegmentInfo(segment_id='seg-1', order=1, claim_mode='source_backed', disclosure=None, word_count=4),
    )
    mat1 = material(pw_database, tmp_path, pinned, segs)
    mat2 = material(pw_database, tmp_path, pinned, segs)
    assert mat1.ass_ref == mat2.ass_ref
    assert mat1.local_path == mat2.local_path
    assert mat1.sha256 == mat2.sha256

    entries_with_mat = with_ass_entry(base_entries(), mat1)
    re_added = with_ass_entry(entries_with_mat, mat1)
    assert entries_with_mat == re_added

    words = read_words(pw_database)
    inputs1 = ass_inputs(pinned[0].preset, pinned[1].profile)
    inputs2_typo = {**inputs1.typography, 'font_size': 99}
    mat_diff = build_ass_material(
        staging_root=str(tmp_path / 'diff'),
        words=words,
        typography=inputs2_typo,
        safe_area=inputs1.safe_area,
        profile=inputs1.profile,
        disclosure_style=inputs1.disclosure_style,
        segments=segs,
    )
    assert mat_diff.sha256 != mat1.sha256

    conflict_mat = AssMaterial(
        ass_ref=mat1.ass_ref,
        entry=LocalMaterialRef(artifact_version_id=mat1.ass_ref, local_ref='other.ass'),
        local_path=mat1.local_path,
        sha256=mat1.sha256,
        text=mat1.text,
    )
    with pytest.raises(AssManifestRejected) as exc_info:
        with_ass_entry(entries_with_mat, conflict_mat)
    assert exc_info.value.code == 'MANIFEST_CONFLICT'


def test_invalid_staging_root_is_rejected() -> None:
    with pytest.raises(AssManifestRejected) as exc_info:
        build_ass_material(
            staging_root='relative/dir',
            words=(),
            typography={},
            safe_area={},
            profile={},
            disclosure_style={},
            segments=(),
        )
    assert exc_info.value.code == 'STAGING_ROOT_INVALID'
    assert not pathlib.Path('relative/dir').exists()


# --- Step 17: Disclosure Tests ---


def test_inference_segment_adds_a_disclosure_dialogue_in_the_exact_window(
    pw_database: Any, manager: Any, pinned: tuple[Any, Any], tmp_path: pathlib.Path
) -> None:
    for vid in (V1, V2, VOICE):
        insert_artifact(pw_database, vid)
    insert_plan(
        pw_database,
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
    )
    modes = ['source_backed', 'inference']
    counts = [4, 4]
    segs_payload = script_segments_payload(modes, counts)
    insert_script(pw_database, segs_payload)
    db_segs = read_script_segments(manager, workspace_id=pw_database.workspace_id, script_version_ref=SCRIPT_ID)

    mat = material(pw_database, tmp_path, pinned, db_segs)
    lines = mat.text.strip().splitlines()

    expected_dialogue = f'Dialogue: 0,0:00:02.00,0:00:03.90,Disclosure,seg-1,60,60,240,,{DISCLOSURE}'
    assert lines[-1] == expected_dialogue

    style_disclosure_lines = [l for l in lines if l.startswith('Style: Disclosure,')]
    assert len(style_disclosure_lines) == 1
    disc_idx = lines.index(style_disclosure_lines[0])
    karaoke_idx = [i for i, l in enumerate(lines) if l.startswith('Style: Karaoke,')][0]
    events_idx = [i for i, l in enumerate(lines) if l.startswith('[Events]')][0]
    assert karaoke_idx < disc_idx < events_idx

    assert ',8,60,60,240,' in style_disclosure_lines[0]

    entries = with_ass_entry(base_entries(), mat)
    inputs = resolve_inputs(pw_database, manager, pinned, entries)
    plan_port = PostgresPlanAssets(manager, workspace_id=pw_database.workspace_id)
    record = resolve_render_package(inputs, plan_port)
    spec = build_render_command(
        record,
        pinned[0].preset,
        pinned[1].profile,
        mat.ass_ref,
        ToolIdentity(name='ffmpeg', version='test', build='test-build', executable='C:/tools/ffmpeg.exe'),
        MaterializedPaths(staging_root=str(tmp_path), output_path='out/final.mp4', thumbnail_path='out/thumb.jpg'),
    )
    assert any(mat.entry.local_ref in arg for arg in spec.argv)


def test_creative_hypothesis_segment_also_gets_a_disclosure_row(
    pw_database: Any, manager: Any, pinned: tuple[Any, Any], tmp_path: pathlib.Path
) -> None:
    modes = ['source_backed', 'creative_hypothesis']
    counts = [4, 4]
    insert_script(pw_database, script_segments_payload(modes, counts), script_id='script-ch')
    db_segs = read_script_segments(manager, workspace_id=pw_database.workspace_id, script_version_ref='script-ch')

    mat = material(pw_database, tmp_path, pinned, db_segs)
    assert f'Dialogue: 0,0:00:02.00,0:00:03.90,Disclosure,seg-1,60,60,240,,{DISCLOSURE}' in mat.text


def test_windows_accumulate_word_count_per_order_and_do_not_drift(
    pw_database: Any, manager: Any, pinned: tuple[Any, Any], tmp_path: pathlib.Path
) -> None:
    modes = ['source_backed', 'inference', 'creative_hypothesis']
    counts = [2, 3, 3]
    segs = script_segments_payload(modes, counts)
    insert_script(pw_database, [segs[2], segs[0], segs[1]], script_id='script-drift')
    db_segs = read_script_segments(manager, workspace_id=pw_database.workspace_id, script_version_ref='script-drift')

    mat = material(pw_database, tmp_path, pinned, db_segs)
    assert 'Dialogue: 0,0:00:01.00,0:00:02.40,Disclosure,seg-1,60,60,240,,' in mat.text
    assert 'Dialogue: 0,0:00:02.50,0:00:03.90,Disclosure,seg-2,60,60,240,,' in mat.text


def test_inference_without_disclosure_is_rejected_and_nothing_is_written(
    pw_database: Any, pinned: tuple[Any, Any], tmp_path: pathlib.Path
) -> None:
    insert_timing(pw_database)
    words = read_words(pw_database)
    inputs = ass_inputs(pinned[0].preset, pinned[1].profile)

    for bad_disc in (None, '   '):
        segs = (
            ScriptSegmentInfo(segment_id='s0', order=0, claim_mode='source_backed', disclosure=None, word_count=4),
            ScriptSegmentInfo(segment_id='s1', order=1, claim_mode='inference', disclosure=bad_disc, word_count=4),
        )
        with pytest.raises(AssManifestRejected) as exc_info:
            build_ass_material(
                staging_root=str(tmp_path),
                words=words,
                typography=inputs.typography,
                safe_area=inputs.safe_area,
                profile=inputs.profile,
                disclosure_style=inputs.disclosure_style,
                segments=segs,
            )
        assert exc_info.value.code == 'DISCLOSURE_MISSING'
        assert exc_info.value.reason == 's1'
        assert list(tmp_path.glob('*.ass')) == []


def test_word_count_mismatch_is_rejected_and_nothing_is_written(
    pw_database: Any, pinned: tuple[Any, Any], tmp_path: pathlib.Path
) -> None:
    insert_timing(pw_database)
    words = read_words(pw_database)
    inputs = ass_inputs(pinned[0].preset, pinned[1].profile)

    for total in (7, 9):
        segs = (
            ScriptSegmentInfo(segment_id='s0', order=0, claim_mode='source_backed', disclosure=None, word_count=total),
        )
        with pytest.raises(AssManifestRejected) as exc_info:
            build_ass_material(
                staging_root=str(tmp_path),
                words=words,
                typography=inputs.typography,
                safe_area=inputs.safe_area,
                profile=inputs.profile,
                disclosure_style=inputs.disclosure_style,
                segments=segs,
            )
        assert exc_info.value.code == 'WORD_COUNT_MISMATCH'
        assert list(tmp_path.glob('*.ass')) == []


def test_source_backed_only_script_has_no_disclosure_row(
    pw_database: Any, pinned: tuple[Any, Any], tmp_path: pathlib.Path
) -> None:
    insert_timing(pw_database)
    words = read_words(pw_database)
    inputs = ass_inputs(pinned[0].preset, pinned[1].profile)
    segs = (
        ScriptSegmentInfo(segment_id='s0', order=0, claim_mode='source_backed', disclosure=None, word_count=4),
        ScriptSegmentInfo(segment_id='s1', order=1, claim_mode='source_backed', disclosure=None, word_count=4),
    )
    mat = build_ass_material(
        staging_root=str(tmp_path),
        words=words,
        typography=inputs.typography,
        safe_area=inputs.safe_area,
        profile=inputs.profile,
        disclosure_style=inputs.disclosure_style,
        segments=segs,
    )
    assert 'Disclosure' not in mat.text


def test_disclosure_text_cannot_inject_ass_markup(
    pw_database: Any, pinned: tuple[Any, Any], tmp_path: pathlib.Path
) -> None:
    insert_timing(pw_database)
    words = read_words(pw_database)
    inputs = ass_inputs(pinned[0].preset, pinned[1].profile)
    injected_disclosure = 'a{\\b1}b' + chr(10) + 'c'
    segs = (
        ScriptSegmentInfo(segment_id='s0', order=0, claim_mode='source_backed', disclosure=None, word_count=4),
        ScriptSegmentInfo(segment_id='s1', order=1, claim_mode='inference', disclosure=injected_disclosure, word_count=4),
    )
    mat = build_ass_material(
        staging_root=str(tmp_path),
        words=words,
        typography=inputs.typography,
        safe_area=inputs.safe_area,
        profile=inputs.profile,
        disclosure_style=inputs.disclosure_style,
        segments=segs,
    )
    disc_lines = [l for l in mat.text.splitlines() if 's1' in l]
    assert len(disc_lines) == 1
    assert '{' not in disc_lines[0].split(',,')[-1]
    assert '\\' not in disc_lines[0].split(',,')[-1]


def test_disclosure_style_must_not_overlap_karaoke(
    pw_database: Any, pinned: tuple[Any, Any], tmp_path: pathlib.Path
) -> None:
    insert_timing(pw_database)
    words = read_words(pw_database)
    inputs = ass_inputs(pinned[0].preset, pinned[1].profile)
    segs = (
        ScriptSegmentInfo(segment_id='s0', order=0, claim_mode='source_backed', disclosure=None, word_count=4),
        ScriptSegmentInfo(segment_id='s1', order=1, claim_mode='inference', disclosure=DISCLOSURE, word_count=4),
    )

    bad_style_overlap = {
        'font_size': 40,
        'alignment': 2,
        'margin_v': PARAMS['render.presets']['common']['margin_v'],
    }
    with pytest.raises(AssManifestRejected) as exc_info:
        build_ass_material(
            staging_root=str(tmp_path),
            words=words,
            typography=inputs.typography,
            safe_area=inputs.safe_area,
            profile=inputs.profile,
            disclosure_style=bad_style_overlap,
            segments=segs,
        )
    assert exc_info.value.code == 'DISCLOSURE_STYLE_INVALID'

    bad_style_offscreen = {
        'font_size': 40,
        'alignment': 8,
        'margin_v': pinned[1].profile.height + 10,
    }
    with pytest.raises(AssManifestRejected) as exc_info:
        build_ass_material(
            staging_root=str(tmp_path),
            words=words,
            typography=inputs.typography,
            safe_area=inputs.safe_area,
            profile=inputs.profile,
            disclosure_style=bad_style_offscreen,
            segments=segs,
        )
    assert exc_info.value.code == 'DISCLOSURE_STYLE_INVALID'


def test_unordered_input_gives_the_same_ass(
    pw_database: Any, pinned: tuple[Any, Any], tmp_path: pathlib.Path
) -> None:
    insert_timing(pw_database)
    words = read_words(pw_database)
    inputs = ass_inputs(pinned[0].preset, pinned[1].profile)

    seg0 = ScriptSegmentInfo(segment_id='s0', order=0, claim_mode='source_backed', disclosure=None, word_count=2)
    seg1 = ScriptSegmentInfo(segment_id='s1', order=1, claim_mode='inference', disclosure=DISCLOSURE, word_count=3)
    seg2 = ScriptSegmentInfo(segment_id='s2', order=2, claim_mode='creative_hypothesis', disclosure=DISCLOSURE, word_count=3)

    mat_ordered = build_ass_material(
        staging_root=str(tmp_path / 'ord'),
        words=words,
        typography=inputs.typography,
        safe_area=inputs.safe_area,
        profile=inputs.profile,
        disclosure_style=inputs.disclosure_style,
        segments=[seg0, seg1, seg2],
    )
    mat_reversed = build_ass_material(
        staging_root=str(tmp_path / 'rev'),
        words=words,
        typography=inputs.typography,
        safe_area=inputs.safe_area,
        profile=inputs.profile,
        disclosure_style=inputs.disclosure_style,
        segments=[seg2, seg0, seg1],
    )
    assert mat_ordered.text == mat_reversed.text

# --- PW-W2-FIX3 (R6): g?i render d?ng t? k? ho?ch creative th?t ---
NOW = datetime(2026, 10, 28, 1, 2, 3, tzinfo=timezone.utc)
VOICE_BYTES = b'f3-voice-wav-bytes'
VOICE_REF_F3 = 'voice-artifact-' + hashlib.sha256(VOICE_BYTES).hexdigest()
FFMPEG_BYTES = b'pinned-ffmpeg-bytes'
VISUAL_HOOK_ID = 'vh-1'
AUDIO_HOOK_ID = 'ah-1'
DEFAULT_THUMBNAIL_REF = 'thumb:' + VISUAL_HOOK_ID
HOOK_VIDEO_BYTES = b'f3-hook-video-mp4-bytes'
HOOK_AUDIO_BYTES = b'f3-hook-audio-wav-bytes'
HOOK_VIDEO_SHA = hashlib.sha256(HOOK_VIDEO_BYTES).hexdigest()
HOOK_AUDIO_SHA = hashlib.sha256(HOOK_AUDIO_BYTES).hexdigest()


def render_runtime(tmp_path: pathlib.Path) -> ProductionRuntime:
    ffmpeg = tmp_path / 'ffmpeg.exe'
    ffmpeg.write_bytes(FFMPEG_BYTES)
    lock = tmp_path / 'runtime.lock.json'
    lock.write_text(
        json.dumps({'pins': {'ffmpeg': {'status': 'PINNED', 'sha256': hashlib.sha256(FFMPEG_BYTES).hexdigest()}}}),
        encoding='utf-8',
    )
    runtime = ProductionRuntime(
        ffmpeg_path=ffmpeg,
        ffprobe_path=tmp_path / 'ffprobe.exe',
        runtime_lock_path=lock,
        weights_dir=tmp_path / 'weights',
        weights_lock_path=tmp_path / 'model-weights.lock.json',
        whisper_model_dir=tmp_path / 'whisper',
        staging_root=tmp_path / 'staging',
        secret_store_root=tmp_path / 'vault',
        oauth_client_secrets_path=tmp_path / 'client.json',
        oauth_consent_timeout_seconds=300,
        route_cost_per_request=Decimal('0'),
        tokenization={
            'revision': 'pw-w2',
            'unicode_form': 'NFC',
            'casefold': True,
            'edge_strip_categories': ('P',),
            'gap_tolerance_ms': 500,
            'min_confidence': 0.5,
        },
        drive_placement={'original': 'folder-original', 'reusable': 'folder-reusable', 'output': 'folder-output'},
        drive_fallback_parent_id='folder-root',
        route_catalog=SimpleNamespace(candidates=lambda workspace_id, ai_role: ()),
        provider_credentials=SimpleNamespace(acquire=lambda method, account: None),
        vision_route=SimpleNamespace(invoke_vision=lambda *args, **kwargs: ''),
        artifact_source=SimpleNamespace(open=lambda artifact_version_id: None),
        drive_token_broker=SimpleNamespace(acquire=lambda method, account: None),
        gpu_lease=LocalGpuLease(2, 60.0),
    )
    runtime.staging_root.mkdir(parents=True, exist_ok=True)
    return runtime


def stage_and_register(
    manager: Any, db: Any, runtime: ProductionRuntime, relative_ref: str, data: bytes
) -> Any:
    target = runtime.staging_root / relative_ref
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return register_staged_artifact(
        manager,
        workspace_id=db.workspace_id,
        staging_root=runtime.staging_root,
        owner_ref='job-f3',
        relative_ref=relative_ref,
        retention_ref='durable',
    )


def seed_hook(manager: Any, db: Any, hook_id: str, kind: HookKind, sha256: str) -> None:
    with manager.borrow_connection() as connection:
        import_hook(
            PostgresHookHistory(connection, db.workspace_id),
            hook_id=hook_id,
            kind=kind,
            artifact_version_ref='seed:' + hook_id + ':sha256:' + sha256,
            tags=('seed', kind.value, hook_id),
            description='Seed hook ' + hook_id,
            note='',
            enabled=True,
            technical_metadata=(('duration_ms', '4000'), ('media_sha256', sha256)),
        )
        connection.commit()


def creative_plan(db: Any, pinned: tuple[Any, Any], v1_id: str, v2_id: str, thumbnail_ref: str = DEFAULT_THUMBNAIL_REF) -> Any:
    script_text = ' '.join(WORDS)
    count = len(WORDS)
    est = count / 2.0
    script = ScriptVersion(
        script_version_id=SCRIPT_ID,
        language='en',
        hook_intent='hook',
        thumbnail_transition='fade',
        segments=(
            ScriptSegment(
                segment_id='s1',
                order=0,
                text=script_text,
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
    base = CreativeAssetSelection(
        snapshot_ref='snap-1',
        script_ref=SCRIPT_ID,
        angle_ref='angle-1',
        safety_policy_revision='safety-r1',
        music_sfx_policy_revision='ms-r1',
        preset_registry_revision='preset-reg-r1',
        visual_hook=ResourceRef(db.workspace_id, 'visual_hook', VISUAL_HOOK_ID, 'vh-r1'),
        audio_hook=ResourceRef(db.workspace_id, 'audio_hook', AUDIO_HOOK_ID, 'ah-r1'),
        thumbnail=ResourceRef(db.workspace_id, 'thumbnail', thumbnail_ref, 'th-r1'),
        thumbnail_overlay_intent='title card',
        assignments=(
            SceneAssignment(
                order=0,
                scene_id='sc-1',
                media_asset_id='m-1',
                rendition_ref='rend-1',
                artifact_version_ref=v1_id,
                rationale='r1',
            ),
            SceneAssignment(
                order=1,
                scene_id='sc-2',
                media_asset_id='m-2',
                rendition_ref='rend-2',
                artifact_version_ref=v2_id,
                rationale='r2',
            ),
        ),
        music_intents=(MappingProxyType({'cue': 'intro_pad', 'description': 'soft pad'}),),
        sfx_intents=(MappingProxyType({'cue': 'whoosh', 'description': 'short whoosh'}),),
        fallback_candidates=(),
        rationale='overall',
        score_components=MappingProxyType({}),
    )
    selection = dataclasses.replace(base, selection_fingerprint=base.compute_fingerprint())

    raw = {
        'timeline': {
            'segments': [
                {
                    'scene_id': 'sc-1',
                    'start_ms': 0,
                    'end_ms': 2000,
                    'transition_intent': 'hard cut',
                    'visuals': [
                        {
                            'media_asset_id': 'm-1',
                            'start_ms': 0,
                            'end_ms': 2000,
                            'crop_intent': 'center on subject',
                            'overlay_intent': 'lower third',
                            'effect_intent': 'slow push-in',
                        }
                    ],
                },
                {
                    'scene_id': 'sc-2',
                    'start_ms': 2000,
                    'end_ms': 4000,
                    'transition_intent': 'cross dissolve',
                    'visuals': [
                        {
                            'media_asset_id': 'm-2',
                            'start_ms': 2000,
                            'end_ms': 4000,
                            'crop_intent': 'center on subject',
                            'overlay_intent': 'lower third',
                            'effect_intent': 'slow push-in',
                        }
                    ],
                },
            ]
        },
        'hook_placement': {
            'hook_time_range': {'start_ms': 0, 'end_ms': 2000},
            'thumbnail_time_range': {'start_ms': 500, 'end_ms': 1500},
        },
        'voice_profile_intent': {'direction': 'warm and confident', 'pace': 'steady', 'emotion': 'curious'},
        'music_cues': [{'cue': 'intro_pad', 'start_ms': 0, 'end_ms': 4000}],
        'sfx_cues': [{'cue': 'whoosh', 'start_ms': 1800, 'end_ms': 2200}],
        'subtitle_style_intent': {'style': 'bold white captions', 'karaoke': True, 'highlight_intent': 'active word turns yellow'},
        'allowed_fallbacks': [
            {'rule_id': 'fb-2', 'kind': 'simplify_transition', 'scene_id': 'sc-1'},
        ],
        'output_metadata_requirement': 'english title, caption and 3-4 hashtags (CT-AI-009)',
    }

    return build_production_plan(
        raw,
        production_plan_id=PLAN_ID,
        script=script,
        selection=selection,
        preset_revision_ref=pinned[0].revision_ref,
    )


def build_world(db: Any, manager: Any, pinned: tuple[Any, Any], tmp_path: pathlib.Path, *, hook_catalog: bool = True, hook_media: bool = True, thumbnail_ref: str = DEFAULT_THUMBNAIL_REF) -> SimpleNamespace:
    runtime = render_runtime(tmp_path)
    v1 = stage_and_register(manager, db, runtime, 'media/f3-visual-1.mp4', b'v1-bytes-f3')
    v2 = stage_and_register(manager, db, runtime, 'media/f3-visual-2.mp4', b'v2-bytes-f3')
    voice_version = stage_and_register(manager, db, runtime, 'voice/' + VOICE_REF_F3, VOICE_BYTES)
    hook_video = hook_audio = None
    if hook_media:
        hook_video = stage_and_register(manager, db, runtime, f'media/{HOOK_VIDEO_SHA}.mp4', HOOK_VIDEO_BYTES)
        hook_audio = stage_and_register(manager, db, runtime, f'media/{HOOK_AUDIO_SHA}.wav', HOOK_AUDIO_BYTES)
    if hook_catalog:
        seed_hook(manager, db, VISUAL_HOOK_ID, HookKind.VISUAL_HOOK, HOOK_VIDEO_SHA)
        seed_hook(manager, db, AUDIO_HOOK_ID, HookKind.AUDIO_HOOK, HOOK_AUDIO_SHA)

    insert_script(db, script_segments_payload(['source_backed', 'source_backed'], [4, 4]))
    insert_timing(db)
    plan = creative_plan(db, pinned, v1.artifact_version_id, v2.artifact_version_id, thumbnail_ref)
    insert_plan(db, plan.to_payload())

    sources = ProductionRenderSources(
        manager=manager,
        workspace_id=db.workspace_id,
        profile=load_production_profile(PROFILE_PATH),
        runtime=runtime,
        clock=lambda: NOW,
    )
    plan_port = PostgresPlanAssets(manager, workspace_id=db.workspace_id)

    refs = [
        {'ref_type': 'production_plan', 'ref_id': PLAN_ID},
        {'ref_type': 'script_version', 'ref_id': SCRIPT_ID},
        {'ref_type': 'word_timing', 'ref_id': TIMING_REF},
        {'ref_type': 'voice_artifact', 'ref_id': VOICE_REF_F3},
        {'ref_type': 'artifact_version', 'ref_id': voice_version.artifact_version_id, 'source_ref_id': 'voice/' + VOICE_REF_F3},
        {'ref_type': 'artifact_version', 'ref_id': v1.artifact_version_id, 'source_ref_id': 'media/f3-visual-1.mp4'},
        {'ref_type': 'artifact_version', 'ref_id': v2.artifact_version_id, 'source_ref_id': 'media/f3-visual-2.mp4'},
        {'ref_type': 'output_path', 'ref_id': 'out-f3'},
        {'ref_type': 'production_snapshot', 'ref_id': 'snap-f3'},
        {'ref_type': 'output_metadata', 'ref_id': 'meta-f3'},
    ]

    return SimpleNamespace(
        runtime=runtime,
        v1=v1,
        v2=v2,
        voice_version=voice_version,
        hook_video=hook_video,
        hook_audio=hook_audio,
        sources=sources,
        plan_port=plan_port,
        refs=refs,
    )


def test_resolved_render_package_validates_and_builds_command(
    pw_database: Any, manager: Any, pinned: tuple[Any, Any], tmp_path: pathlib.Path
) -> None:
    w = build_world(pw_database, manager, pinned, tmp_path)
    inputs = w.sources.resolve_inputs(w.refs)
    assert [s['visual_asset_refs'] for s in inputs.timeline['segments']] == [[w.v1.artifact_version_id], [w.v2.artifact_version_id]]
    record = resolve_render_package(inputs, w.plan_port)

    manifest = record.materialization_manifest
    assert manifest[w.v1.artifact_version_id]['local_ref'] == w.v1.artifact_version_id
    assert not manifest[w.v1.artifact_version_id]['local_ref'].endswith('.mp4')
    assert manifest[w.v2.artifact_version_id]['local_ref'] == w.v2.artifact_version_id
    assert not manifest[w.v2.artifact_version_id]['local_ref'].endswith('.mp4')
    assert manifest[VOICE_REF_F3]['local_ref'] == w.voice_version.artifact_version_id
    ass_ref = w.sources.ass_ref_for(record)
    assert manifest[ass_ref]['local_ref'].endswith('.ass')
    for entry in manifest.values():
        assert (w.runtime.staging_root / entry['local_ref']).is_file()

    voice_input = next(a for a in record.input_artifacts if a.artifact_version_id == VOICE_REF_F3)
    assert voice_input.sha256 == hashlib.sha256(VOICE_BYTES).hexdigest()
    assert voice_input.size_bytes == len(VOICE_BYTES)

    timing_input = next(a for a in record.input_artifacts if a.artifact_version_id == TIMING_REF)
    expected_timing_bytes = json.dumps(timing_payload(), sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    assert timing_input.sha256 == hashlib.sha256(expected_timing_bytes).hexdigest()
    assert timing_input.size_bytes == len(expected_timing_bytes)

    report = validate_render_package(record, w.sources.validation_context(record))
    assert report.passed is True, report.findings

    plan = w.sources.render_plan(record, 'render:att:1')
    assert ':' not in plan.output_artifact_ref
    assert PureWindowsPath(plan.command_spec.argv[-1]).name == 'render_att_1.mp4'
    assert str(w.runtime.staging_root / w.v1.artifact_version_id) in plan.command_spec.argv
    assert str(w.runtime.staging_root / w.v2.artifact_version_id) in plan.command_spec.argv
    assert str(w.runtime.staging_root / w.voice_version.artifact_version_id) in plan.command_spec.argv
    assert any(arg.endswith('.ass') or '.ass' in arg for arg in plan.command_spec.argv)

    cmd = build_render_command(
        record,
        pinned[0].preset,
        pinned[1].profile,
        w.sources.ass_ref_for(record),
        ToolIdentity(name='ffmpeg', version='test', build='test-build', executable='C:/tools/ffmpeg.exe'),
        MaterializedPaths(staging_root=str(w.runtime.staging_root), output_path='out/render_att_1.mp4', thumbnail_path='out/render_att_1.jpg'),
    )
    assert cmd is not None


@pytest.mark.parametrize(
    'variant,expected_code',
    [
        ('drop_voice_version_ref', 'INPUT_NOT_READY'),
        ('bad_voice_source_ref', 'INPUT_NOT_READY'),
        ('drop_voice_ref', 'INPUT_REF_MISSING'),
        ('drop_timing_ref', 'INPUT_REF_MISSING'),
    ],
)
def test_resolve_inputs_fails_closed_on_missing_voice_or_timing(
    pw_database: Any, manager: Any, pinned: tuple[Any, Any], tmp_path: pathlib.Path, variant: str, expected_code: str
) -> None:
    w = build_world(pw_database, manager, pinned, tmp_path)
    refs = [copy.deepcopy(r) for r in w.refs]
    if variant == 'drop_voice_version_ref':
        refs = [r for r in refs if not (r.get('ref_type') == 'artifact_version' and str(r.get('source_ref_id', '')).startswith('voice/'))]
    elif variant == 'bad_voice_source_ref':
        for r in refs:
            if r.get('ref_type') == 'artifact_version' and str(r.get('source_ref_id', '')).startswith('voice/'):
                r['source_ref_id'] = 'voice/voice-artifact-' + 'c' * 64
    elif variant == 'drop_voice_ref':
        refs = [r for r in refs if r.get('ref_type') != 'voice_artifact']
    elif variant == 'drop_timing_ref':
        refs = [r for r in refs if r.get('ref_type') != 'word_timing']

    with pytest.raises(ActivityInputError) as exc_info:
        w.sources.resolve_inputs(refs)
    assert exc_info.value.code == expected_code

# --- PW-W2-FIX4 (R10): hook and thumbnail refs resolve to verified staged versions ---


def test_hook_and_thumbnail_refs_resolve_to_verified_staged_versions(pw_database, manager, pinned, tmp_path):
    w = build_world(pw_database, manager, pinned, tmp_path)
    inputs = w.sources.resolve_inputs(w.refs)
    assert inputs.hook_placement['visual_hook_ref'] == VISUAL_HOOK_ID
    assert inputs.hook_placement['audio_hook_ref'] == AUDIO_HOOK_ID
    assert inputs.hook_placement['thumbnail_ref'] == DEFAULT_THUMBNAIL_REF
    record = resolve_render_package(inputs, w.plan_port)
    expected = {
        VISUAL_HOOK_ID: (w.hook_video, HOOK_VIDEO_BYTES, 'video/mp4'),
        AUDIO_HOOK_ID: (w.hook_audio, HOOK_AUDIO_BYTES, 'audio/wav'),
        DEFAULT_THUMBNAIL_REF: (w.hook_video, HOOK_VIDEO_BYTES, 'video/mp4'),
    }
    by_ref = {a.artifact_version_id: a for a in inputs.input_artifacts}
    for ref, (version, data, mime) in expected.items():
        assert by_ref[ref].sha256 == hashlib.sha256(data).hexdigest()
        assert by_ref[ref].size_bytes == len(data)
        assert by_ref[ref].media_type == mime
        assert by_ref[ref].role == version.artifact_kind
        local = record.materialization_manifest[ref]['local_ref']
        assert local == version.artifact_version_id
        assert hashlib.sha256((w.runtime.staging_root / local).read_bytes()).hexdigest() == by_ref[ref].sha256
    report = validate_render_package(record, w.sources.validation_context(record))
    assert report.passed is True, report.findings


def test_thumbnail_of_a_plan_visual_uses_the_visual_version(pw_database, manager, pinned, tmp_path):
    w = build_world(pw_database, manager, pinned, tmp_path, thumbnail_ref='thumb:m-1')
    inputs = w.sources.resolve_inputs(w.refs)
    record = resolve_render_package(inputs, w.plan_port)
    thumb = next(a for a in record.input_artifacts if a.artifact_version_id == 'thumb:m-1')
    assert thumb.sha256 == hashlib.sha256(b'v1-bytes-f3').hexdigest()
    assert record.materialization_manifest['thumb:m-1']['local_ref'] == w.v1.artifact_version_id
    report = validate_render_package(record, w.sources.validation_context(record))
    assert report.passed is True, report.findings


@pytest.mark.parametrize(
    'kwargs,ref',
    [
        ({'hook_media': False}, VISUAL_HOOK_ID),
        ({'hook_catalog': False}, VISUAL_HOOK_ID),
        ({'thumbnail_ref': 'thumb:unknown-subject'}, 'thumb:unknown-subject'),
        ({'thumbnail_ref': 'th-1'}, 'th-1'),
    ],
    ids=[
        'hook_without_version',
        'hook_not_in_catalog',
        'thumbnail_unknown_subject',
        'thumbnail_without_thumb_prefix',
    ],
)
def test_unresolvable_hook_refs_fail_with_input_not_ready(pw_database, manager, pinned, tmp_path, kwargs, ref):
    w = build_world(pw_database, manager, pinned, tmp_path, **kwargs)
    with pytest.raises(ActivityInputError) as exc_info:
        w.sources.resolve_inputs(w.refs)
    assert exc_info.value.code == 'INPUT_NOT_READY'
    assert ref in str(exc_info.value)
