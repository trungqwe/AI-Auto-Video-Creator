"""PW-D3: nguồn ứng viên media, hook, thumbnail từ danh mục của C trên PostgreSQL thật.

coveredIds: PW-D3-01, OI-ADAPT-10, CT-MED-006
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import pathlib
import sys
import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from catalog.application.discovery import DiscoveryObservation, register_discovery
from catalog.application.hooks import import_hook, update_hook_metadata
from catalog.domain.hooks import HookKind
from catalog.domain.identity import (
    CanonicalFingerprint, MediaAsset, MediaKind, ProvenanceEntry, ProvenanceRelation, RightsAssessment, RightsStatus)
from catalog.persistence.assets import PostgresMediaAssetRepository
from catalog.persistence.hooks import PostgresHookHistory
from controlplane.application.storage_meta.handlers import register_staged_artifact
from controlplane.infrastructure.db.uow import TransactionManager
from creative.adapters.hook_candidates import PostgresHookCandidates
from creative.adapters.media_candidates import PostgresMediaCandidates
from creative.adapters.thumbnail_candidates import ThumbnailCandidates
from creative.domain.asset_selection import (
    HookCandidate, SafetyRightsPolicy, ScoringWeights, SelectionRejected, select_creative_assets)

ROOT = pathlib.Path(__file__).resolve().parents[3]
PROD = ROOT / 'tools' / 'launcher' / 'prod'
LAUNCHER = ROOT / 'tools' / 'launcher' / 'launcher.py'
ADAPTERS = ROOT / 'src' / 'creative' / 'adapters'
HOOKS = json.loads((PROD / 'hooks.json').read_text(encoding='utf-8'))
SEED_IDS = ['seed-' + item['id'] for item in HOOKS['background_images']]
POLICY_REVISION = 'safe-v1'
HERO = ProvenanceRelation.HERO_IMAGE
FETCHED_AT = '2026-10-27T07:30:00Z'
SNAPSHOT = SimpleNamespace(
    snapshot_id='snap-1',
    source_refs=({'ref_type': 'article_revision', 'ref_id': 'article-1', 'revision_id': 'v1'},))


def load_module(name, path):
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def load_import_seed():
    return load_module('pw_d3_import_seed', PROD / 'seed' / 'import_seed.py')


@pytest.fixture(scope='module')
def launcher():
    return load_module('pw_d3_launcher', LAUNCHER)


def sha_of(name):
    return hashlib.sha256(name.encode('utf-8')).hexdigest()


def stage_image(manager, workspace_id, root, name):
    """Đăng ký version thật bằng register_staged_artifact; nội dung tệp là chính `name` nên sha256 của nó là sha_of(name)."""
    digest = sha_of(name)
    path = root / 'media' / (digest + '.png')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(name.encode('utf-8'))
    return register_staged_artifact(manager, workspace_id=workspace_id, staging_root=root, owner_ref='job-1', relative_ref='media/' + digest + '.png', retention_ref='durable')


def assert_registered_version(db, ref, name):
    assert str(uuid.UUID(ref)) == ref
    with db.connect() as conn:
        found = conn.execute('SELECT artifact_id, sha256_hash FROM controlplane.cp_artifact_versions WHERE artifact_version_id::text = %s', (ref,)).fetchall()
    assert found == [('media/' + sha_of(name) + '.png', sha_of(name))]


def real_policy():
    return SafetyRightsPolicy(revision=POLICY_REVISION, allowed_availability=('AVAILABLE',), required_flags=('rights_cleared',), blocked_flags=('unsafe',))


def seed_items(tool):
    """Items as ADAPT-SEED builds them from hooks.json; the digest comes from the file name because ffmpeg generates the media files in ADAPT-SEED."""
    items = []
    for group, media_kind, hook_kind in tool._GROUPS:
        for entry in HOOKS[group]:
            sha = sha_of(entry['file_name'])
            technical = tuple((key, str(entry[key])) for key in tool._TECHNICAL_KEYS if key in entry)
            technical += (('media_sha256', sha), ('recipe_template', entry['recipe']['template']), ('seed_rights_status', HOOKS['rights']['seed_rights_status']))
            items.append(tool._SeedItem(entry['id'], media_kind, hook_kind, entry['file_name'], sha, technical, pathlib.Path(entry['file_name'])))
    return items


@pytest.fixture
def manager(pw_database):
    manager = TransactionManager(pw_database.dsn, pool_max_size=4)
    try:
        yield manager
    finally:
        manager.close()


@pytest.fixture
def staging(tmp_path):
    return tmp_path / 'staging'


@pytest.fixture
def imported(pw_database, manager):
    tool = load_import_seed()
    counts = tool._import_items(manager, pw_database.workspace_id, seed_items(tool))
    assert counts == {'assets_new': 22, 'assets_existing': 0, 'hooks_imported': 10, 'hooks_existing': 0}
    return manager


@pytest.fixture
def seeded(pw_database, imported, staging):
    for entry in HOOKS['background_images']:
        stage_image(imported, pw_database.workspace_id, staging, entry['file_name'])
    return imported


def open_hooks(manager):
    @contextmanager
    def scope(workspace_id):
        with manager.borrow_connection() as connection:
            yield PostgresHookHistory(connection, workspace_id)
    return scope


def media_port(launcher, manager, workspace_id):
    return launcher.build_media_candidates(manager, workspace_id=workspace_id, safety_policy_revision=POLICY_REVISION)


def hook_port(manager):
    return PostgresHookCandidates(open_hooks(manager), safety_policy_revision=POLICY_REVISION)


def register_article_image(manager, workspace_id, asset_id, article_ref, locator, relation=HERO, root=None):
    provenance = ProvenanceEntry('src-1', article_ref, None, locator, FETCHED_AT, relation)
    observation = DiscoveryObservation(article_ref + ':' + asset_id, MediaKind.IMAGE, provenance, CanonicalFingerprint(sha_of(asset_id)), True)
    with manager.borrow_connection() as connection:
        result = register_discovery(PostgresMediaAssetRepository(connection, workspace_id), observation, asset_id)
    assert result.media_asset_id == asset_id
    if root is not None:
        stage_image(manager, workspace_id, root, asset_id)


def save_image(manager, workspace_id, asset_id, provenance, with_fingerprint=True):
    fingerprint = CanonicalFingerprint(sha_of(asset_id)) if with_fingerprint else None
    asset = MediaAsset(asset_id, MediaKind.IMAGE, fingerprint, provenance, RightsAssessment(RightsStatus.UNKNOWN, ()), 1)
    with manager.borrow_connection() as connection:
        PostgresMediaAssetRepository(connection, workspace_id).save(asset)


def test_seed_images_bg_01_to_bg_12_are_media_candidates_with_provenance(launcher, pw_database, seeded):
    candidates = media_port(launcher, seeded, pw_database.workspace_id).media_candidates(workspace_id=pw_database.workspace_id, snapshot=SNAPSHOT)
    assert len(SEED_IDS) == 12
    assert [item.media_asset_id for item in candidates] == SEED_IDS
    first = candidates[0]
    assert first.provenance['origin'] == 'seed' and first.provenance['source_url'] == 'seed://bg-01.png'
    assert first.provenance['sha256'] == sha_of('bg-01.png') and first.provenance['fetched_at'] == '2026-10-22T00:00:00Z'
    for item, entry in zip(candidates, HOOKS['background_images']):
        assert_registered_version(pw_database, item.artifact_version_ref, entry['file_name'])
    assert not any(item.artifact_version_ref.startswith('sha256:') for item in candidates)
    assert dict(first.safety_rights_status) == {
        'rights_status': 'unknown', 'needs_image_safety': False, 'origin': 'seed',
        'seed_rights_status': HOOKS['rights']['seed_rights_status'], 'rights_cleared': True}
    assert all(item.availability == 'AVAILABLE' and 'ROLE_MATCH' in item.reason_codes for item in candidates)


def test_article_image_registered_by_register_discovery_enters_with_provenance_and_needs_image_safety(launcher, pw_database, seeded, staging):
    ws = pw_database.workspace_id
    register_article_image(seeded, ws, 'img-article-1-hero', 'article-1', 'https://img.example/news/article-1/hero.jpg', root=staging)
    register_article_image(
        seeded, ws, 'img-article-1-inline', 'article-1', 'https://img.example/news/article-1/inline-1.jpg',
        ProvenanceRelation.INLINE_IMAGE, root=staging)
    register_article_image(seeded, ws, 'img-article-2-hero', 'article-2', 'https://img.example/news/article-2/photo-1.jpg', root=staging)
    candidates = media_port(launcher, seeded, ws).media_candidates(workspace_id=ws, snapshot=SNAPSHOT)
    assert [item.media_asset_id for item in candidates] == ['img-article-1-hero', 'img-article-1-inline', *SEED_IDS]
    hero = candidates[0]
    assert dict(hero.provenance) == {
        'origin': 'article', 'source_url': 'https://img.example/news/article-1/hero.jpg', 'source_ref': 'src-1',
        'article_ref': 'article-1', 'sha256': sha_of('img-article-1-hero'), 'fetched_at': FETCHED_AT, 'relation': 'hero_image'}
    status = dict(hero.safety_rights_status)
    assert status['needs_image_safety'] is True and status['rights_status'] == 'unknown'
    assert status['article_image_rights_status'] == 'UNVERIFIED'
    assert status['rights_cleared'] is True and status['rights_basis'] == 'OI-ADAPT-10'
    assert_registered_version(pw_database, hero.artifact_version_ref, 'img-article-1-hero')
    assert all(dict(item.safety_rights_status)['rights_cleared'] is True for item in candidates)
    assert hero.semantic_match_components['topic'] == 1.0 and 'TOPIC_MATCH' in hero.reason_codes
    assert all(dict(item.safety_rights_status)['needs_image_safety'] is False for item in candidates[2:])


def test_images_without_complete_provenance_or_bytes_are_dropped(launcher, pw_database, seeded, staging):
    ws = pw_database.workspace_id
    register_article_image(seeded, ws, 'img-ok', 'article-1', 'https://img.example/news/article-1/ok.jpg', root=staging)
    base = 'https://img.example/news/article-1/'
    save_image(seeded, ws, 'img-no-locator', (ProvenanceEntry('src-1', 'article-1', None, '  ', FETCHED_AT, HERO),))
    save_image(seeded, ws, 'img-no-time', (ProvenanceEntry('src-1', 'article-1', None, base + 't.jpg', '', HERO),))
    save_image(seeded, ws, 'img-no-provenance', ())
    save_image(
        seeded, ws, 'img-not-acquired', (ProvenanceEntry('src-1', 'article-1', None, base + 'n.jpg', FETCHED_AT, HERO),),
        with_fingerprint=False)
    save_image(
        seeded, ws, 'img-wrong-relation',
        (ProvenanceEntry('src-1', 'article-1', None, base + 'w.jpg', FETCHED_AT, ProvenanceRelation.USER_IMPORTED),))
    for name in ('img-no-locator', 'img-no-time', 'img-no-provenance', 'img-wrong-relation'):
        stage_image(seeded, ws, staging, name)
    candidates = media_port(launcher, seeded, ws).media_candidates(workspace_id=ws, snapshot=SNAPSHOT)
    assert [item.media_asset_id for item in candidates] == ['img-ok', *SEED_IDS]


def test_a_missing_seed_image_is_refused_as_seed_media_missing(launcher, pw_database, manager, staging):
    ws = pw_database.workspace_id
    register_article_image(manager, ws, 'img-ok', 'article-1', 'https://img.example/news/article-1/ok.jpg', root=staging)
    with pytest.raises(SelectionRejected) as caught:
        media_port(launcher, manager, ws).media_candidates(workspace_id=ws, snapshot=SNAPSHOT)
    assert (caught.value.code, caught.value.reason) == ('INPUT_NOT_READY', 'seed_media_missing')


def test_hook_candidates_are_the_five_visual_and_five_audio_seed_hooks(pw_database, seeded):
    ws = pw_database.workspace_id
    port = hook_port(seeded)
    visual = port.visual_hook_candidates(workspace_id=ws, snapshot_ref='snap-1')
    audio = port.audio_hook_candidates(workspace_id=ws, snapshot_ref='snap-1')
    assert [item.hook_id for item in visual] == ['vh-0' + str(n) for n in range(1, 6)]
    assert [item.hook_id for item in audio] == ['ah-0' + str(n) for n in range(1, 6)]
    assert {item.hook_kind for item in visual} == {'visual_hook'} and {item.hook_kind for item in audio} == {'audio_hook'}
    assert visual[0].revision_id == 'vh-01-r1' and visual[0].provenance['technical']['duration_ms'] == 3000
    assert audio[0].provenance['technical']['duration_ms'] == 1500 and audio[0].provenance['sha256'] == sha_of('ah-01.wav')
    expected = {'rights_status': HOOKS['rights']['seed_rights_status'], 'rights_cleared': True}
    assert all(item.availability == 'AVAILABLE' and dict(item.safety_rights_status) == expected for item in visual + audio)


def test_a_disabled_hook_is_not_a_candidate(pw_database, seeded):
    ws = pw_database.workspace_id
    with seeded.borrow_connection() as connection:
        update_hook_metadata(PostgresHookHistory(connection, ws), 'vh-05', 1, enabled=False)
    visual = hook_port(seeded).visual_hook_candidates(workspace_id=ws, snapshot_ref='snap-1')
    assert [item.hook_id for item in visual] == ['vh-0' + str(n) for n in range(1, 5)]
    assert len(hook_port(seeded).audio_hook_candidates(workspace_id=ws, snapshot_ref='snap-1')) == 5


def test_hook_candidates_fail_closed_without_hooks(pw_database, manager):
    ws = pw_database.workspace_id
    for method, reason in (('visual_hook_candidates', 'no_visual_hook_candidates'), ('audio_hook_candidates', 'no_audio_hook_candidates')):
        with pytest.raises(SelectionRejected) as caught:
            getattr(hook_port(manager), method)(workspace_id=ws, snapshot_ref='snap-1')
        assert (caught.value.code, caught.value.reason) == ('INPUT_NOT_READY', reason)


def test_thumbnail_candidates_are_frames_of_hooks_or_images_and_each_has_a_reason(launcher, pw_database, seeded, staging):
    ws = pw_database.workspace_id
    register_article_image(seeded, ws, 'img-article-1-hero', 'article-1', 'https://img.example/news/article-1/hero.jpg', root=staging)
    media = media_port(launcher, seeded, ws).media_candidates(workspace_id=ws, snapshot=SNAPSHOT)
    visual = hook_port(seeded).visual_hook_candidates(workspace_id=ws, snapshot_ref='snap-1')
    thumbnails = ThumbnailCandidates().thumbnail_candidates(visual_hooks=visual, media_candidates=media)
    assert len(media) == 13 and len(thumbnails) == 5 + 13
    assert len({item.thumbnail_id for item in thumbnails}) == len(thumbnails)
    for item in thumbnails:
        assert isinstance(item.provenance['reason'], str) and item.provenance['reason'].strip()
    from_hook = thumbnails[0]
    assert from_hook.thumbnail_id == 'thumb:vh-01' and from_hook.subject_refs == ('vh-01',)
    assert from_hook.provenance['source_kind'] == 'visual_hook' and 'vh-01' in from_hook.provenance['reason']
    assert from_hook.crop_focus['frame_ms'] == 1500 and 0 <= from_hook.crop_focus['frame_ms'] < 3000
    from_image = next(item for item in thumbnails if item.thumbnail_id == 'thumb:img-article-1-hero')
    assert from_image.provenance['source_kind'] == 'media_asset' and 'img-article-1-hero' in from_image.provenance['reason']
    assert from_image.provenance['source_provenance']['article_ref'] == 'article-1'
    assert from_image.safety_rights_status['needs_image_safety'] is True
    assert all(item.safety_rights_status['rights_cleared'] is True for item in thumbnails)


def test_a_hook_without_a_frame_window_gives_no_thumbnail_and_an_audio_hook_is_refused():
    def hook(kind, technical):
        return HookCandidate(
            hook_kind=kind, hook_id='h-x', revision_id='h-x-r1', availability='AVAILABLE', safety_rights_status={},
            semantic_match_components={}, provenance={'technical': technical})
    with pytest.raises(SelectionRejected) as caught:
        ThumbnailCandidates().thumbnail_candidates(visual_hooks=[hook('visual_hook', {})], media_candidates=[])
    assert (caught.value.code, caught.value.reason) == ('INPUT_NOT_READY', 'no_thumbnail_candidates')
    with pytest.raises(ValueError):
        ThumbnailCandidates().thumbnail_candidates(visual_hooks=[hook('audio_hook', {'duration_ms': 1500})], media_candidates=[])


def ref(ws, ref_type, ref_id, revision_id):
    return {'workspace_id': ws, 'ref_type': ref_type, 'ref_id': ref_id, 'revision_id': revision_id}


def test_candidates_feed_select_creative_assets_with_a_seed_fallback(launcher, pw_database, seeded, staging):
    ws = pw_database.workspace_id
    register_article_image(seeded, ws, 'img-article-1-hero', 'article-1', 'https://img.example/news/article-1/hero.jpg', root=staging)
    media = media_port(launcher, seeded, ws).media_candidates(workspace_id=ws, snapshot=SNAPSHOT)
    visual = hook_port(seeded).visual_hook_candidates(workspace_id=ws, snapshot_ref='snap-1')
    audio = hook_port(seeded).audio_hook_candidates(workspace_id=ws, snapshot_ref='snap-1')
    thumbnails = ThumbnailCandidates().thumbnail_candidates(visual_hooks=visual, media_candidates=media)
    hero, thumb = media[0], thumbnails[0]
    proposal = {
        'visual_hook': ref(ws, 'visual_hook', visual[0].hook_id, visual[0].revision_id),
        'audio_hook': ref(ws, 'audio_hook', audio[0].hook_id, audio[0].revision_id),
        'thumbnail': ref(ws, 'thumbnail', thumb.thumbnail_id, thumb.revision_id),
        'scenes': [{'scene_id': 'sc-1', 'ref': ref(ws, 'media_asset', hero.media_asset_id, hero.artifact_version_ref), 'rationale': 'image that came with the article'}],
        'music_intents': [{'cue': 'intro_pad', 'description': 'soft pad'}],
        'sfx_intents': [{'cue': 'whoosh', 'description': 'short whoosh'}],
        'rationale': 'article image first, seed images as fallback'}
    selection = select_creative_assets(
        workspace_id=ws, snapshot_ref='snap-1', script_ref='script-1', angle_ref='angle-a', media_candidates=media,
        visual_hook_candidates=visual, audio_hook_candidates=audio, thumbnail_candidates=thumbnails, proposal=proposal,
        safety_policy=real_policy(),
        music_sfx_policy_revision='music-v1', preset_registry_revision='preset-v1',
        weights=ScoringWeights(semantic=0.6, technical=0.4, recent_usage_penalty=0.1))
    assert selection.assignments[0].media_asset_id == 'img-article-1-hero'
    assert [item.media_asset_id for item in selection.fallback_candidates] == SEED_IDS
    assert (selection.visual_hook.ref_id, selection.audio_hook.ref_id) == ('vh-01', 'ah-01')
    assert selection.thumbnail.ref_id == 'thumb:vh-01' and selection.thumbnail_overlay_intent == 'headline_text'
    assert_registered_version(pw_database, selection.assignments[0].artifact_version_ref, 'img-article-1-hero')


def test_media_port_requires_a_callable_resolve_version():
    with pytest.raises(TypeError):
        PostgresMediaCandidates(lambda workspace_id: None, safety_policy_revision=POLICY_REVISION)
    with pytest.raises(TypeError):
        PostgresMediaCandidates(lambda workspace_id: None, resolve_version='x', safety_policy_revision=POLICY_REVISION)


def test_seed_images_without_a_registered_version_are_dropped(launcher, pw_database, imported, staging):
    ws = pw_database.workspace_id
    for entry in HOOKS['background_images'][:2]:
        stage_image(imported, ws, staging, entry['file_name'])
    candidates = media_port(launcher, imported, ws).media_candidates(workspace_id=ws, snapshot=SNAPSHOT)
    assert [item.media_asset_id for item in candidates] == SEED_IDS[:2]


def test_no_registered_seed_version_is_refused_as_seed_media_missing(launcher, pw_database, imported, staging):
    ws = pw_database.workspace_id
    register_article_image(imported, ws, 'img-ok', 'article-1', 'https://img.example/news/article-1/ok.jpg', root=staging)
    with pytest.raises(SelectionRejected) as caught:
        media_port(launcher, imported, ws).media_candidates(workspace_id=ws, snapshot=SNAPSHOT)
    assert (caught.value.code, caught.value.reason) == ('INPUT_NOT_READY', 'seed_media_missing')


def test_article_image_without_a_registered_version_is_dropped(launcher, pw_database, seeded, staging):
    ws = pw_database.workspace_id
    register_article_image(seeded, ws, 'img-staged', 'article-1', 'https://img.example/news/article-1/staged.jpg', root=staging)
    register_article_image(seeded, ws, 'img-unstaged', 'article-1', 'https://img.example/news/article-1/unstaged.jpg')
    candidates = media_port(launcher, seeded, ws).media_candidates(workspace_id=ws, snapshot=SNAPSHOT)
    assert [item.media_asset_id for item in candidates] == ['img-staged', *SEED_IDS]


def test_real_policy_keeps_seed_images_article_images_and_seed_hooks(launcher, pw_database, seeded, staging):
    ws = pw_database.workspace_id
    register_article_image(seeded, ws, 'img-article-1-hero', 'article-1', 'https://img.example/news/article-1/hero.jpg', root=staging)
    media = media_port(launcher, seeded, ws).media_candidates(workspace_id=ws, snapshot=SNAPSHOT)
    visual = hook_port(seeded).visual_hook_candidates(workspace_id=ws, snapshot_ref='snap-1')
    audio = hook_port(seeded).audio_hook_candidates(workspace_id=ws, snapshot_ref='snap-1')
    policy = real_policy()
    assert len(media) == 13
    assert all(policy.allows(item.availability, item.safety_rights_status) for item in [*media, *visual, *audio])


def test_a_hook_without_a_self_generated_seed_status_is_not_rights_cleared(pw_database, seeded):
    ws = pw_database.workspace_id
    with seeded.borrow_connection() as connection:
        import_hook(PostgresHookHistory(connection, ws), hook_id='vh-user', kind=HookKind.VISUAL_HOOK, artifact_version_ref='user:vh-user', tags=('user',), enabled=True, technical_metadata=(('duration_ms', '2000'),))
    visual = hook_port(seeded).visual_hook_candidates(workspace_id=ws, snapshot_ref='snap-1')
    by_id = {item.hook_id: item for item in visual}
    policy = real_policy()
    assert by_id['vh-user'].safety_rights_status['rights_cleared'] is False
    assert not policy.allows(by_id['vh-user'].availability, by_id['vh-user'].safety_rights_status)
    assert all(policy.allows(item.availability, item.safety_rights_status) for item in visual if item.hook_id != 'vh-user')


def test_adapters_keep_the_boundary_to_c_and_name_their_ports():
    texts = {name: (ADAPTERS / (name + '.py')).read_text(encoding='utf-8') for name in ('media_candidates', 'hook_candidates', 'thumbnail_candidates')}
    for name, text in texts.items():
        lowered = text.lower()
        for banned in ('cp_', 'psycopg', 'fake', 'from src.'):
            assert banned not in lowered, (name, banned)
        tree = ast.parse(text)
        modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
        modules |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        catalog = {item for item in modules if item == 'catalog' or item.startswith('catalog.')}
        assert catalog == (set() if name == 'thumbnail_candidates' else {'catalog.application.candidate_query'}), name
    assert 'needs_image_safety' in texts['media_candidates']
    assert 'class PostgresMediaCandidates' in texts['media_candidates']
    assert 'class PostgresHookCandidates' in texts['hook_candidates']
    assert 'class ThumbnailCandidates' in texts['thumbnail_candidates']
    assert 'sha256:' not in texts['media_candidates']
    assert 'resolve_version' in texts['media_candidates']
    assert 'rights_cleared' in texts['media_candidates'] and 'rights_cleared' in texts['hook_candidates']
    launcher_text = LAUNCHER.read_text(encoding='utf-8')
    assert 'verified_version_for_sha' in launcher_text and 'resolve_version=' in launcher_text


def test_module_docstring_declares_covered_ids():
    doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
    assert 'coveredIds: PW-D3-01, OI-ADAPT-10, CT-MED-006' in doc.splitlines()
