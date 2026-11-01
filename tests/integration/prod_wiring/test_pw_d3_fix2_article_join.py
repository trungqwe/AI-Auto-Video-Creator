"""PW-D3-FIX2: ảnh bài (article_ref = collected_document_id) vào ứng viên của D qua resolve_documents của launcher, trên PostgreSQL thật và FFmpeg ghim; chỉ transport HTTP được tiêm.

coveredIds: PW-D3-02, PW-D3-04, OI-ADAPT-10
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from psycopg.types.json import Jsonb

from catalog.application.media_discovery_handler import MediaDiscoveryDeps, register_media_discovery
from controlplane.api.wiring import workflow
from controlplane.infrastructure.db.uow import TransactionManager
from creative.adapters.media_candidates import MAX_ARTICLE_IMAGES, PostgresMediaCandidates
from creative.domain.asset_selection import (
    HookCandidate, SafetyRightsPolicy, ScoringWeights, SelectionRejected, ThumbnailCandidate, select_creative_assets)
from ingestion.application.production_deps import DEFAULT_DEDUP_POLICY, PostgresSourceTierLookup, new_id
from ingestion.application.resolve_document import resolve_collected_document
from ingestion.application.source_set import SINGLE_ARTICLE, build_source_set
from ingestion.persistence.uow import PostgresIngestionUnitOfWork
from source_ingestion.adapters.real_media_fetch import RealMediaFetcher
from source_ingestion.adapters.secure_fetch import FetchPolicy, SecureFetcher, TransportResponse
from source_ingestion.adapters.stdlib_html_extractor import StdlibHtmlExtractor
from source_ingestion.application.package_builder import PackageContext, build_package
from source_ingestion.ports.source_adapter import FetchedDocument, FetchObservation
from source_ingestion.worker.production_deps import DEFAULT_EXTRACTION_POLICY

ROOT = pathlib.Path(__file__).resolve().parents[3]
PROD = ROOT / 'tools' / 'launcher' / 'prod'
LAUNCHER = ROOT / 'tools' / 'launcher' / 'launcher.py'
HOOKS = json.loads((PROD / 'hooks.json').read_text(encoding='utf-8'))
SEED_IDS = ['seed-' + item['id'] for item in HOOKS['background_images']]
POLICY_REVISION = 'safe-v1'

SOURCE_ID = 'src-a'
PUBLIC = '93.184.216.34'
NOW = datetime(2026, 10, 27, 3, 0, tzinfo=timezone.utc)
FFMPEG = pathlib.Path('C:/ffmpeg/bin/ffmpeg.exe')
CLAIMS = SimpleNamespace(stage_run_id='enrich:doc:media:r1', grant_id='grant-1', execution_generation=1, recovery_epoch='5')


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
    return load_module('pw_d3_fix2_import_seed', PROD / 'seed' / 'import_seed.py')


@pytest.fixture(scope='module')
def launcher():
    return load_module('pw_d3_fix2_launcher', LAUNCHER)


def sha_of(name):
    return hashlib.sha256(name.encode('utf-8')).hexdigest()


def stage_image(manager, workspace_id, root, name):
    """Đăng ký version thật bằng register_staged_artifact; nội dung tệp là chính `name` nên sha256 của nó là sha_of(name)."""
    from controlplane.application.storage_meta.handlers import register_staged_artifact
    digest = sha_of(name)
    path = root / 'media' / (digest + '.png')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(name.encode('utf-8'))
    return register_staged_artifact(manager, workspace_id=workspace_id, staging_root=root, owner_ref='job-1', relative_ref='media/' + digest + '.png', retention_ref='durable')


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


def make_jpeg(path, colour):
    if not FFMPEG.is_file():
        pytest.fail('BLOCKED_EXTERNAL: pinned FFmpeg C:/ffmpeg/bin/ffmpeg.exe is required; no skip and no fallback is permitted.', pytrace=False)
    subprocess.run([str(FFMPEG), '-hide_banner', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'color=c={colour}:s=1200x630:d=1', '-frames:v', '1', str(path)], check=True)


@pytest.fixture(scope='module')
def jpeg(tmp_path_factory):
    root = tmp_path_factory.mktemp('jpeg')
    cache = {}

    def get(n):
        if n not in cache:
            path = root / f'{n}.jpg'
            if not path.exists():
                make_jpeg(path, f'0x{(n * 37) % 256:02x}{(n * 91) % 256:02x}{(n * 53 + 17) % 256:02x}')
            data = path.read_bytes()
            assert data[:2] == b'\xff\xd8'
            cache[n] = data
        return cache[n]

    return get


class ImageSite:
    """Transport HTTP tiêm duy nhất: trả JPEG theo locator."""

    def __init__(self, routes):
        self.routes = routes
        self.requests = []

    def send(self, request):
        self.requests.append(request.locator)
        return TransportResponse(200, (('Content-Type', 'image/jpeg'),), [self.routes[request.locator]])


def page(name, urls):
    body = ' '.join(f'{name}w{i}' for i in range(120))
    imgs = ''.join(f"<img src='{u}' alt='x'>" for u in urls[1:])
    html = (
        f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>Tin {name}</title>"
        f"<meta property='og:image' content='{urls[0]}'></head><body><article><h1>Tin {name}</h1><p>{body}</p>{imgs}</article></body></html>")
    return html.encode('utf-8')


class World:
    def __init__(self, launcher, manager, db, staging, jpeg):
        self.launcher = launcher
        self.manager = manager
        self.db = db
        self.staging = staging
        self.jpeg = jpeg
        self.routes = {}
        self.site = ImageSite(self.routes)
        self.packages = {}
        with db.connect() as conn:
            conn.execute(
                'INSERT INTO controlplane.cp_sources (workspace_id, source_id, canonical_locator, status, revision, payload) VALUES (%s, %s, %s, %s, %s, %s)',
                (db.workspace_id, SOURCE_ID, 'https://news.example/feed', 'ACTIVE', 1, Jsonb({'tier': 'tier_1'})))

    def add_article(self, name, images):
        for url, data in images:
            self.routes[url] = data
        html = page(name, [u for u, _ in images])
        url = f'https://news.example/{name}'
        document = FetchedDocument(
            FetchObservation(url, url, (url,), 200, 'text/html', len(html), (('content-type', 'text/html; charset=utf-8'),), 'pw-d3-fix2'), html)
        package = build_package(document, StdlibHtmlExtractor(), PackageContext(SOURCE_ID, 1, 'run-' + name, NOW), extraction_policy=DEFAULT_EXTRACTION_POLICY, source_kind='rss_feed')
        ws = self.db.workspace_id
        resolution = resolve_collected_document(
            package, DEFAULT_DEDUP_POLICY, PostgresIngestionUnitOfWork(self.manager, workspace_id=ws),
            PostgresSourceTierLookup(self.db.connect, ws), lambda: NOW, new_id)
        assert isinstance(resolution['article_id'], str) and resolution['article_id']
        assert isinstance(resolution['article_revision_id'], str) and resolution['article_revision_id']
        article_id = resolution['article_id']
        document_id = package['collected_document_id']
        self.packages[document_id] = package
        assert uuid.UUID(document_id).version == 5
        assert uuid.UUID(article_id).version == 4
        assert article_id != document_id
        fetcher = SecureFetcher(self.site, lambda host: [PUBLIC])
        media = RealMediaFetcher(
            fetcher,
            image_policy=FetchPolicy(revision='pw-d3-fix2', max_redirects=2, max_body_bytes=1 << 20, allowed_media_types=frozenset({'image/jpeg'}), timeout_seconds=10.0),
            staging_root=self.staging / 'media', max_images_per_article=30, utc_now=lambda: NOW)
        deps = MediaDiscoveryDeps(
            ws, lambda ref: self.packages[ref['ref_id']], media, workflow.media_assets_opener(self.manager),
            workflow.staged_artifact_registrar(self.manager, ws, self.staging))
        result = register_media_discovery(
            {'input_refs': [{'ref_type': 'collected_document', 'ref_id': document_id}], 'operation_key': 'op-' + name}, CLAIMS, deps, lambda: NOW)
        assert result['disposition'] == 'succeeded'
        return SimpleNamespace(
            name=name, article_id=article_id, revision_id=resolution['article_revision_id'], document_id=document_id,
            asset_ids=[r['ref_id'] for r in result['output_refs']],
            sha={u: hashlib.sha256(b).hexdigest() for u, b in images}, metrics=result['metrics'])

    def snapshot(self, article):
        ws = self.db.workspace_id
        with PostgresIngestionUnitOfWork(self.manager, workspace_id=ws) as uow:
            built = build_source_set(SINGLE_ARTICLE, article.article_id, uow)
        ref = f'{SINGLE_ARTICLE}:{article.article_id}:{built.source_set_fingerprint}'
        pin = self.launcher.build_source_sets(self.manager, ws).source_set(workspace_id=ws, source_set_ref=ref)
        return SimpleNamespace(snapshot_id='snap-' + article.name, source_refs=pin.source_refs)

    def candidates(self, snapshot, manager=None):
        ws = self.db.workspace_id
        port = self.launcher.build_media_candidates(manager or self.manager, workspace_id=ws, safety_policy_revision=POLICY_REVISION)
        return port.media_candidates(workspace_id=ws, snapshot=snapshot)


@pytest.fixture
def world(launcher, pw_database, seeded, staging, jpeg):
    return World(launcher, seeded, pw_database, staging, jpeg)


def test_article_images_of_the_pinned_revision_enter_before_the_seeds_and_other_articles_do_not(world, jpeg):
    a = world.add_article('a', [('https://img.example/a/hero.jpg', jpeg(1)), ('https://img.example/a/inline.jpg', jpeg(2))])
    b = world.add_article('b', [('https://img.example/b/hero.jpg', jpeg(3)), ('https://img.example/b/inline.jpg', jpeg(4))])
    assert len(a.asset_ids) == 2 and len(b.asset_ids) == 2
    candidates = world.candidates(world.snapshot(a))
    assert {c.media_asset_id for c in candidates[:2]} == set(a.asset_ids)
    assert [c.media_asset_id for c in candidates[2:]] == SEED_IDS
    assert not ({c.media_asset_id for c in candidates} & set(b.asset_ids))
    for c in candidates[:2]:
        assert c.provenance['origin'] == 'article'
        assert c.provenance['article_ref'] == a.document_id
        assert c.provenance['article_ref'] != a.article_id
        assert c.provenance['sha256'] == a.sha[c.provenance['source_url']]
        assert 'TOPIC_MATCH' in c.reason_codes
        assert c.semantic_match_components['topic'] == 1.0
        status = dict(c.safety_rights_status)
        assert status['needs_image_safety'] is True
        assert status['rights_cleared'] is True
        assert status['rights_basis'] == 'OI-ADAPT-10'
    for c in candidates[2:]:
        assert dict(c.safety_rights_status)['needs_image_safety'] is False
    assert {c.media_asset_id for c in world.candidates(world.snapshot(b))[:2]} == set(b.asset_ids)


def test_the_same_bytes_in_two_articles_carry_the_provenance_of_the_article_in_the_snapshot(world, jpeg):
    same = jpeg(5)
    a = world.add_article('a', [('https://img.example/a/shared.jpg', same)])
    b = world.add_article('b', [('https://img.example/b/shared.jpg', same)])
    assert b.metrics['provenance_added'] == 1
    assert b.asset_ids == a.asset_ids
    ca = world.candidates(world.snapshot(a))[0]
    cb = world.candidates(world.snapshot(b))[0]
    assert ca.media_asset_id == cb.media_asset_id == a.asset_ids[0]
    assert ca.provenance['article_ref'] == a.document_id
    assert cb.provenance['article_ref'] == b.document_id
    assert ca.provenance['source_url'] == 'https://img.example/a/shared.jpg'


def test_thirty_article_images_are_capped_at_24_and_all_seeds_stay(world, jpeg):
    images = [(f'https://img.example/a/{n}.jpg', jpeg(100 + n)) for n in range(30)]
    a = world.add_article('a', images)
    assert len(a.asset_ids) == 30
    candidates = world.candidates(world.snapshot(a))
    articles = [c for c in candidates if c.provenance['origin'] == 'article']
    assert MAX_ARTICLE_IMAGES == 24 and len(articles) == 24
    assert [c.media_asset_id for c in candidates[:24]] == [c.media_asset_id for c in articles]
    assert [c.media_asset_id for c in candidates[24:]] == SEED_IDS
    assert len(candidates) == 36


def test_an_unknown_revision_gives_only_the_seeds(world, jpeg):
    a = world.add_article('a', [('https://img.example/a/hero.jpg', jpeg(7))])
    snapshot = SimpleNamespace(snapshot_id='snap-unknown', source_refs=({'ref_type': 'article_revision', 'ref_id': a.article_id, 'revision_id': 'revision-unknown'},))
    assert [c.media_asset_id for c in world.candidates(snapshot)] == SEED_IDS
    missing = SimpleNamespace(snapshot_id='snap-missing', source_refs=({'ref_type': 'article_revision', 'ref_id': '00000000-0000-4000-8000-0000000000aa', 'revision_id': a.revision_id},))
    assert [c.media_asset_id for c in world.candidates(missing)] == SEED_IDS


def test_an_article_image_in_scene_one_leaves_only_seeds_in_fallback_candidates(world, jpeg, pw_database):
    ws = pw_database.workspace_id
    a = world.add_article('a', [('https://img.example/a/hero.jpg', jpeg(9))])
    media = world.candidates(world.snapshot(a))
    hero = media[0]
    assert hero.provenance['origin'] == 'article'

    def hook(kind, hook_id):
        return HookCandidate(
            hook_kind=kind, hook_id=hook_id, revision_id=hook_id + '-r1', availability='AVAILABLE',
            safety_rights_status={'rights_cleared': True}, semantic_match_components={'topic': 0.7}, provenance={'source': 'user_imported'})

    def ref(ref_type, ref_id, revision_id):
        return {'workspace_id': ws, 'ref_type': ref_type, 'ref_id': ref_id, 'revision_id': revision_id}

    visual = hook('visual_hook', 'vh-1')
    audio = hook('audio_hook', 'ah-1')
    thumb = ThumbnailCandidate(
        thumbnail_id='th-1', revision_id='th-1-r1', subject_refs=('entity-1',), crop_focus={'x': 0.5, 'y': 0.4}, overlay_intent='question_mark',
        availability='AVAILABLE', safety_rights_status={'rights_cleared': True}, semantic_match_components={'entity': 0.8}, provenance={'source': 'catalog'})
    proposal = {
        'visual_hook': ref('visual_hook', visual.hook_id, visual.revision_id),
        'audio_hook': ref('audio_hook', audio.hook_id, audio.revision_id),
        'thumbnail': ref('thumbnail', thumb.thumbnail_id, thumb.revision_id),
        'scenes': [{'scene_id': 'sc-1', 'ref': ref('media_asset', hero.media_asset_id, hero.artifact_version_ref), 'rationale': 'image that came with the article'}],
        'music_intents': [{'cue': 'intro_pad', 'description': 'soft pad'}],
        'sfx_intents': [{'cue': 'whoosh', 'description': 'short whoosh'}],
        'rationale': 'article image first',
    }
    selection = select_creative_assets(
        workspace_id=ws, snapshot_ref='snap-a', script_ref='script-1', angle_ref='angle-a', media_candidates=media,
        visual_hook_candidates=[visual], audio_hook_candidates=[audio], thumbnail_candidates=[thumb], proposal=proposal,
        safety_policy=SafetyRightsPolicy(revision=POLICY_REVISION, allowed_availability=('AVAILABLE',), required_flags=('rights_cleared',), blocked_flags=('unsafe',)),
        music_sfx_policy_revision='music-v1', preset_registry_revision='preset-v1',
        weights=ScoringWeights(semantic=0.6, technical=0.4, recent_usage_penalty=0.1))
    assert selection.assignments[0].media_asset_id == hero.media_asset_id
    assert [f.media_asset_id for f in selection.fallback_candidates] == SEED_IDS


def test_resolve_documents_must_be_callable_and_return_a_tuple_or_list(pw_database):
    opened = []

    def opener(workspace_id):
        opened.append(workspace_id)
        raise AssertionError('open_assets must not run before resolve_documents')

    snapshot = SimpleNamespace(source_refs=({'ref_type': 'article_revision', 'ref_id': 'art-x', 'revision_id': 'rev-x'},), snapshot_id='snap-x')
    for value in ('abc', None, 5, ['ok', 7]):
        port = PostgresMediaCandidates(opener, resolve_version=lambda sha: None, resolve_documents=lambda a, r, v=value: v, safety_policy_revision=POLICY_REVISION)
        with pytest.raises(TypeError, match='resolve_documents must return'):
            port.media_candidates(workspace_id=pw_database.workspace_id, snapshot=snapshot)
    assert opened == []
    for value in ([], ()):
        port = PostgresMediaCandidates(opener, resolve_version=lambda sha: None, resolve_documents=lambda a, r, v=value: v, safety_policy_revision=POLICY_REVISION)
        with pytest.raises(AssertionError):
            port.media_candidates(workspace_id=pw_database.workspace_id, snapshot=snapshot)
    assert len(opened) == 2
    with pytest.raises(TypeError, match='resolve_documents must be callable'):
        PostgresMediaCandidates(opener, resolve_version=lambda sha: None, resolve_documents='x', safety_policy_revision=POLICY_REVISION)


def test_a_database_error_in_resolve_documents_is_not_swallowed(world, pw_database):
    dead = TransactionManager(pw_database.dsn, pool_max_size=1)
    dead.close()
    snapshot = SimpleNamespace(snapshot_id='snap-d', source_refs=({'ref_type': 'article_revision', 'ref_id': 'art-d', 'revision_id': 'rev-d'},))
    with pytest.raises(Exception) as caught:
        world.candidates(snapshot, manager=dead)
    assert not isinstance(caught.value, SelectionRejected)


def test_module_docstring_declares_covered_ids_and_text_avoids_forbidden_tokens():
    text = pathlib.Path(__file__).read_text(encoding='utf-8')
    doc = ast.get_docstring(ast.parse(text))
    assert 'coveredIds: PW-D3-02, PW-D3-04, OI-ADAPT-10' in doc.splitlines()
    assert 'monkey' + 'patch' not in text
    assert 'article' + '-1' not in text
