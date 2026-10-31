"""PW-W2-FIX5: khởi động production tự tạo staging voice và media, seed render config từ hồ sơ production.

coveredIds: PW-W2-FIX5, OI-PW-F3-01
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

import controlplane.api.wiring.production_profile as profile_wiring
from controlplane.api.wiring.render import FreshScope
from controlplane.api.wiring.voice import build_voice_services
from controlplane.infrastructure.db.uow import TransactionManager
from controlplane.infrastructure.production_ports.gpu_lease import LocalGpuLease
from render.adapters.config_render_sources import OUTPUT_PROFILE_SCOPE_KEY, POLICY_SCOPE_KIND, PRESET_SCOPE_KIND, QUALITY_POLICY_SCOPE_KEY, ConfigRenderSources

ROOT = Path(__file__).resolve().parents[3]
LAUNCHER_PATH = ROOT / 'tools' / 'launcher' / 'launcher.py'
PROFILE_PATH = ROOT / 'tools' / 'launcher' / 'prod' / 'profile.json'
FFMPEG_BYTES = b'pinned-ffmpeg-bytes'
PRESET_KEYS = ('bold-yellow', 'clean-white', 'neon-cyan', 'news-red', 'soft-shadow')


def make_runtime(tmp_path):
    ffmpeg = tmp_path / 'ffmpeg.exe'
    ffmpeg.write_bytes(FFMPEG_BYTES)
    lock = tmp_path / 'runtime.lock.json'
    lock.write_text(json.dumps({'pins': {'ffmpeg': {'status': 'PINNED', 'sha256': hashlib.sha256(FFMPEG_BYTES).hexdigest()}}}), encoding='utf-8')
    return profile_wiring.ProductionRuntime(
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
        tokenization={'revision': 'pw-w2-fix5', 'unicode_form': 'NFC', 'casefold': True, 'edge_strip_categories': ('P',), 'gap_tolerance_ms': 500, 'min_confidence': 0.5},
        drive_placement={'original': 'folder-original', 'reusable': 'folder-reusable', 'output': 'folder-output'},
        drive_fallback_parent_id='folder-root',
        route_catalog=SimpleNamespace(candidates=lambda workspace_id, ai_role: ()),
        provider_credentials=SimpleNamespace(acquire=lambda method, account: None),
        vision_route=SimpleNamespace(invoke_vision=lambda *args, **kwargs: ''),
        artifact_source=SimpleNamespace(open=lambda artifact_version_id: None),
        drive_token_broker=SimpleNamespace(acquire=lambda method, account: None),
        gpu_lease=LocalGpuLease(2, 60.0),
    )


@pytest.fixture(scope='module')
def launcher():
    spec = importlib.util.spec_from_file_location('pw_w2_fix5_launcher', LAUNCHER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build(pw_database, runtime):
    profile = profile_wiring.load_production_profile(PROFILE_PATH)
    config = profile_wiring.WiringConfig(mode='production', workspace_id=pw_database.workspace_id, profile=profile, runtime=runtime)
    manager = TransactionManager(pw_database.dsn, pool_max_size=2)
    try:
        return build_voice_services(manager, config)
    finally:
        manager.close()


def test_production_voice_build_creates_voice_and_media_dirs_and_keeps_files(pw_database, tmp_path):
    runtime = make_runtime(tmp_path)
    runtime.staging_root.mkdir()
    voice_dir = runtime.staging_root / 'voice'
    media_dir = runtime.staging_root / 'media'
    assert not voice_dir.exists()
    assert not media_dir.exists()
    build(pw_database, runtime)
    assert voice_dir.is_dir()
    assert media_dir.is_dir()
    (voice_dir / 'keep.wav').write_bytes(b'keep')
    (media_dir / 'keep.png').write_bytes(b'keep')
    build(pw_database, runtime)
    assert (voice_dir / 'keep.wav').read_bytes() == b'keep'
    assert (media_dir / 'keep.png').read_bytes() == b'keep'


@pytest.mark.parametrize('relative', ('src/controlplane/api/wiring/render.py', 'tools/launcher/launcher.py'))
def test_render_wiring_and_launcher_hold_no_render_literals(relative):
    text = (ROOT / relative).read_text(encoding='utf-8')
    for literal in ('min_voice_level', 'max_words_per_line', '&H00FFFFFF', 'pw-f3'):
        assert literal not in text


def test_seed_defaults_seeds_render_config_from_the_profile_once(launcher, pw_database, monkeypatch):
    import controlplane.api.wiring.collection as collection_wiring

    monkeypatch.setattr(collection_wiring, 'system_dns_resolver', lambda host: ['93.184.216.34'])
    for _ in range(2):
        launcher.seed_defaults(pw_database.dsn, pw_database.workspace_id, pw_database.actor_id, '1')
    raw = json.loads(PROFILE_PATH.read_text(encoding='utf-8'))
    manager = TransactionManager(pw_database.dsn, pool_max_size=2)
    try:
        sources = ConfigRenderSources(FreshScope(manager), pw_database.workspace_id)
        for key in PRESET_KEYS:
            color = raw['render']['presets']['value']['variants'][key]['highlight_color']
            expected_colour = '&H00' + (color[5:7] + color[3:5] + color[1:3]).upper()
            assert sources.preset(key).preset.typography_karaoke_style['primary_colour'] == expected_colour
        output = sources.output_profile().profile
        stream = raw['render']['output_stream']['value']
        assert (output.video_codec, output.pixel_format) == (stream['video_codec'], stream['pixel_format'])
        thresholds = sources.quality_policy().policy.thresholds
        assert dict(thresholds['VOICE_AUDIBLE']) == raw['qc']['quality_thresholds']['value']['VOICE_AUDIBLE']
        with manager.borrow_connection() as conn:
            rows = conn.execute(
                'SELECT scope_kind, scope_key, count(*) FROM controlplane.cp_config_revisions WHERE workspace_id = %s::uuid AND scope_kind IN (%s, %s) GROUP BY scope_kind, scope_key',
                (pw_database.workspace_id, PRESET_SCOPE_KIND, POLICY_SCOPE_KIND),
            ).fetchall()
    finally:
        manager.close()
    expected = {(PRESET_SCOPE_KIND, k) for k in PRESET_KEYS} | {(PRESET_SCOPE_KIND, OUTPUT_PROFILE_SCOPE_KEY), (POLICY_SCOPE_KIND, QUALITY_POLICY_SCOPE_KEY)}
    assert {(r[0], r[1]): r[2] for r in rows} == {scope: 1 for scope in expected}
