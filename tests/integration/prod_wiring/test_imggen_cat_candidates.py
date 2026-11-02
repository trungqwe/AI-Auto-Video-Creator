"""IMGGEN-CAT: ảnh minh hoạ AI (provenance ai_generated, quyền D4) trong ứng viên media của SelectCreativeAssets; không DB, không mạng.

coveredIds: OI-CP7-11-Q1
"""
from __future__ import annotations

import ast
import hashlib
import pathlib
import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from catalog.application.discovery import DiscoveryObservation, Disposition, register_discovery
from catalog.domain.identity import (
    CanonicalFingerprint, MediaAsset, MediaKind, ProvenanceEntry, ProvenanceRelation, RightsAssessment, RightsStatus)
from catalog.persistence._db import search_terms
from catalog.persistence.mapping import asset_from_rows, asset_payload, asset_search_text, provenance_from_json, provenance_to_json
from creative.adapters import media_candidates as media_module
from creative.adapters import thumbnail_candidates as thumbnail_module
from creative.adapters.media_candidates import PostgresMediaCandidates
from creative.adapters.thumbnail_candidates import ThumbnailCandidates
from creative.domain.asset_selection import (
    REF_TYPE_AUDIO_HOOK, REF_TYPE_VISUAL_HOOK, HookCandidate, SafetyRightsPolicy, ScoringWeights, SelectionRejected, select_creative_assets)

ROOT = pathlib.Path(__file__).resolve().parents[3]
ADAPTERS = ROOT / 'src' / 'creative' / 'adapters'
CATALOG_ASSETS = ROOT / 'src' / 'catalog' / 'persistence' / 'assets.py'
WORKSPACE = str(uuid.UUID(int=1))
ARTICLE = 'article-1'
MODEL = 'flux-3-image-klein'
REVISION = '337337621b85'
FETCHED_AT = '2026-11-02T07:30:00Z'
POLICY_REVISION = 'safe-v1'
SEED_IDS = ['seed-bg-01.png', 'seed-bg-02.png', 'seed-bg-03.png']
SNAPSHOT = SimpleNamespace(snapshot_id='snap-1', source_refs=({'ref_type': 'article_revision', 'ref_id': ARTICLE, 'revision_id': 'v1'},))


def sha_of(name):
    return hashlib.sha256(name.encode('utf-8')).hexdigest()


def version_of(sha):
    return 'ver-' + sha[:12]


def ai_locator(name, model=MODEL, revision=REVISION):
    return f'aigen://{model}/{revision}/{sha_of(name)}'


def make_asset(asset_id, entries, *, fingerprint=True, kind=MediaKind.IMAGE):
    digest = CanonicalFingerprint(sha_of(asset_id)) if fingerprint else None
    return MediaAsset(asset_id, kind, digest, tuple(entries), RightsAssessment(RightsStatus.UNKNOWN, ()), 1)


def ai_entry(asset_id, *, article_ref=ARTICLE, source_ref='imggen-pipe', locator=None, observed_at=FETCHED_AT, relation=None):
    return ProvenanceEntry(source_ref, article_ref, None, locator or ai_locator(asset_id), observed_at, relation or ProvenanceRelation.AI_GENERATED)


def ai_asset(asset_id):
    return make_asset(asset_id, [ai_entry(asset_id)])


def article_entry(asset_id):
    return ProvenanceEntry('src-1', ARTICLE, None, f'https://img.example/news/{ARTICLE}/{asset_id}.jpg', FETCHED_AT, ProvenanceRelation.HERO_IMAGE)


def article_asset(asset_id):
    return make_asset(asset_id, [article_entry(asset_id)])


def seed_asset(number):
    entry = ProvenanceEntry('seed-import', None, None, f'seed://bg-{number:02d}.png', '2026-10-22T00:00:00Z', ProvenanceRelation.USER_IMPORTED)
    return make_asset(f'seed-bg-{number:02d}.png', [entry])


def seeds(count=3):
    return [seed_asset(number) for number in range(1, count + 1)]


class ScriptedAssetReader:
    """Danh mục trong bộ nhớ: search khớp đúng tập từ của asset_search_text với search_terms, sắp theo media_asset_id như catalog; ghi lại mọi lần search."""

    def __init__(self, assets=()):
        self.assets = {item.media_asset_id: item for item in assets}
        self.discoveries = {}
        self.calls = []

    def get(self, media_asset_id):
        return self.assets.get(media_asset_id)

    def find_by_fingerprint(self, fingerprint):
        return next((item for item in self.assets.values() if item.fingerprint == fingerprint), None)

    def find_by_discovery_id(self, discovery_id):
        asset_id = self.discoveries.get(discovery_id)
        return None if asset_id is None else self.assets[asset_id]

    def save(self, asset, discovery_id=None):
        self.assets[asset.media_asset_id] = asset
        if discovery_id is not None:
            self.discoveries[discovery_id] = asset.media_asset_id

    def search(self, query, limit=20):
        self.calls.append((query, limit))
        terms = set(search_terms(query))
        if not terms:
            return []
        found = [item for item in self.assets.values() if terms <= set(asset_search_text(item).split(' '))]
        return sorted(found, key=lambda item: item.media_asset_id)[:limit]


def port(reader, *, without_version=()):
    missing = {sha_of(name) for name in without_version}

    @contextmanager
    def open_assets(workspace_id):
        yield reader

    return PostgresMediaCandidates(
        open_assets, resolve_version=lambda sha: None if sha in missing else version_of(sha),
        resolve_documents=lambda article_id, revision_id: (), safety_policy_revision=POLICY_REVISION)


def candidates_of(reader, **kwargs):
    return port(reader, **kwargs).media_candidates(workspace_id=WORKSPACE, snapshot=SNAPSHOT)


def ids_of(items):
    return [item.media_asset_id for item in items]


def origins_of(candidates):
    return [item.provenance['origin'] for item in candidates]


def test_catalog_search_by_the_article_id_finds_an_ai_generated_asset_registered_with_that_article_ref():
    asset = ai_asset('ai-1')
    reader = ScriptedAssetReader([asset, article_asset('img-a-hero'), *seeds(2)])
    words = set(asset_search_text(asset).split(' '))
    assert set(search_terms(ARTICLE)) <= words
    assert {'ai', 'generated', 'flux', 'klein', REVISION, sha_of('ai-1')} <= words
    assert ids_of(reader.search(ARTICLE, 200)) == ['ai-1', 'img-a-hero']
    assert reader.search('article-2', 200) == []
    assert "string_to_array(search_text, ' ') @> %s::text[]" in CATALOG_ASSETS.read_text(encoding='utf-8')


def test_an_ai_image_registered_by_register_discovery_is_found_by_the_article_id_and_listed():
    reader = ScriptedAssetReader(seeds())
    observation = DiscoveryObservation('aigen:ai-1', MediaKind.IMAGE, ai_entry('ai-1'), CanonicalFingerprint(sha_of('ai-1')), True)
    result = register_discovery(reader, observation, 'ai-1')
    assert result.disposition is Disposition.NEW_ASSET and result.media_asset_id == 'ai-1'
    assert ids_of(reader.search(ARTICLE, 200)) == ['ai-1']
    found = candidates_of(reader)
    assert ids_of(found) == ['ai-1', *SEED_IDS]
    assert found[0].provenance['origin'] == 'ai_generated' and found[0].provenance['model_ref'] == 'flux-3-image-klein@337337621b85'
    assert found[0].artifact_version_ref == version_of(sha_of('ai-1'))


def test_ai_generated_candidates_follow_the_article_images_and_precede_the_seeds():
    both = make_asset('img-both', [article_entry('img-both'), ai_entry('img-both')])
    reader = ScriptedAssetReader([*seeds(), ai_asset('ai-2'), article_asset('img-a-inline'), ai_asset('ai-1'), both, article_asset('img-a-hero')])
    found = candidates_of(reader)
    assert ids_of(found) == ['img-a-hero', 'img-a-inline', 'img-both', 'ai-1', 'ai-2', *SEED_IDS]
    assert origins_of(found) == ['article'] * 3 + ['ai_generated'] * 2 + ['seed'] * 3
    assert found[2].provenance['relation'] == 'hero_image' and 'model_ref' not in found[2].provenance
    assert reader.calls == [('seed png', 200), (ARTICLE, 200)]


def test_article_and_seed_candidates_keep_exactly_their_provenance_and_flags():
    reader = ScriptedAssetReader([article_asset('img-a-hero'), ai_asset('ai-1'), *seeds(1)])
    article, ai, seed = candidates_of(reader)
    assert dict(article.provenance) == {
        'origin': 'article', 'source_url': f'https://img.example/news/{ARTICLE}/img-a-hero.jpg', 'source_ref': 'src-1',
        'article_ref': ARTICLE, 'sha256': sha_of('img-a-hero'), 'fetched_at': FETCHED_AT, 'relation': 'hero_image'}
    assert dict(article.safety_rights_status) == {
        'rights_status': 'unknown', 'needs_image_safety': True, 'origin': 'article', 'article_image_rights_status': 'UNVERIFIED',
        'rights_cleared': True, 'rights_basis': 'OI-ADAPT-10'}
    assert dict(seed.provenance) == {
        'origin': 'seed', 'source_url': 'seed://bg-01.png', 'source_ref': 'seed-import', 'article_ref': None,
        'sha256': sha_of('seed-bg-01.png'), 'fetched_at': '2026-10-22T00:00:00Z', 'relation': 'user_imported'}
    assert dict(seed.safety_rights_status) == {
        'rights_status': 'unknown', 'needs_image_safety': False, 'origin': 'seed', 'seed_rights_status': 'SELF_GENERATED', 'rights_cleared': True}
    assert dict(ai.provenance) == {
        'origin': 'ai_generated', 'source_url': ai_locator('ai-1'), 'source_ref': 'imggen-pipe', 'article_ref': ARTICLE,
        'sha256': sha_of('ai-1'), 'fetched_at': FETCHED_AT, 'relation': 'ai_generated',
        'model_ref': 'flux-3-image-klein@337337621b85', 'label': 'ai_illustration'}
    assert dict(ai.safety_rights_status) == {
        'rights_status': 'unknown', 'needs_image_safety': True, 'origin': 'ai_generated', 'ai_image_rights_status': 'SELF_GENERATED',
        'rights_cleared': True, 'rights_basis': 'D4'}
    assert [item.semantic_match_components['topic'] for item in (article, ai, seed)] == [1.0, 1.0, 0.0]
    assert all(item.availability == 'AVAILABLE' and item.rendition_ref == 'original:' + item.media_asset_id for item in (article, ai, seed))


def test_an_asset_is_an_ai_illustration_of_this_article_only_with_the_relation_the_locator_and_its_own_bytes():
    def bad(name, **kwargs):
        return make_asset(name, [ai_entry(name, source_ref=ARTICLE, **kwargs)])

    assets = [
        bad('ai-other-article', article_ref='article-2'),
        bad('ai-wrong-relation', relation=ProvenanceRelation.USER_IMPORTED),
        bad('ai-embedded-clip', relation=ProvenanceRelation.EMBEDDED_CLIP),
        bad('ai-digest-differs', locator=ai_locator('someone-else')),
        bad('ai-short-revision', locator=ai_locator('ai-short-revision', revision='33733762')),
        bad('ai-upper-model', locator=ai_locator('ai-upper-model', model='Flux')),
        bad('ai-trailing-text', locator=ai_locator('ai-trailing-text') + '/extra'),
        bad('ai-other-scheme', locator='https://img.example/ai.png'),
        bad('ai-blank-locator', locator='  '),
        bad('ai-no-time', observed_at=''),
        make_asset('ai-no-fingerprint', [ai_entry('ai-no-fingerprint', source_ref=ARTICLE)], fingerprint=False),
        make_asset('ai-clip', [ai_entry('ai-clip', source_ref=ARTICLE)], kind=MediaKind.CLIP),
        bad('ai-no-version'),
        ai_asset('ai-ok'), *seeds()]
    reader = ScriptedAssetReader(assets)
    wanted = set(ids_of(assets)) - set(SEED_IDS)
    assert wanted <= set(ids_of(reader.search(ARTICLE, 200)))
    found = candidates_of(reader, without_version=['ai-no-version'])
    assert ids_of(found) == ['ai-ok', *SEED_IDS]


def test_ai_generated_images_are_capped_after_the_article_images_and_the_pinned_caps_stay():
    articles = [f'img-a-{number:02d}' for number in range(30)]
    illustrations = [f'ai-{number:02d}' for number in range(12)]
    reader = ScriptedAssetReader([*map(article_asset, articles), *map(ai_asset, illustrations), *seeds()])
    found = candidates_of(reader)
    assert (media_module.MAX_ARTICLE_IMAGES, media_module.MAX_AI_IMAGES, media_module.SCAN_LIMIT) == (24, 8, 200)
    assert ids_of(found) == [*articles[:24], *illustrations[:8], *SEED_IDS]
    assert reader.calls == [('seed png', 200), (ARTICLE, 200)]


def test_without_ai_images_the_list_is_the_article_images_then_the_seeds_and_a_seed_is_still_required():
    reader = ScriptedAssetReader([article_asset('img-a-hero'), article_asset('img-a-inline'), *seeds()])
    found = candidates_of(reader)
    assert ids_of(found) == ['img-a-hero', 'img-a-inline', *SEED_IDS]
    assert origins_of(found) == ['article', 'article', 'seed', 'seed', 'seed']
    assert not any('model_ref' in item.provenance or 'label' in item.provenance for item in found)
    only_ai = ScriptedAssetReader([ai_asset('ai-1'), article_asset('img-a-hero')])
    with pytest.raises(SelectionRejected) as caught:
        candidates_of(only_ai)
    assert (caught.value.code, caught.value.reason) == ('INPUT_NOT_READY', 'seed_media_missing')


def ref(ref_type, ref_id, revision_id):
    return {'workspace_id': WORKSPACE, 'ref_type': ref_type, 'ref_id': ref_id, 'revision_id': revision_id}


def test_an_ai_image_in_a_scene_leaves_only_seeds_in_the_fallback_candidates():
    media = candidates_of(ScriptedAssetReader([article_asset('img-a-hero'), ai_asset('ai-1'), *seeds()]))
    flags = {'rights_status': 'unknown', 'rights_cleared': True}
    visual = HookCandidate(
        hook_kind=REF_TYPE_VISUAL_HOOK, hook_id='vh-1', revision_id='hook-rev-1', availability='AVAILABLE',
        safety_rights_status=flags, semantic_match_components={}, provenance={'technical': {'duration_ms': 2000}})
    audio = HookCandidate(
        hook_kind=REF_TYPE_AUDIO_HOOK, hook_id='ah-1', revision_id='hook-rev-1', availability='AVAILABLE',
        safety_rights_status=flags, semantic_match_components={}, provenance={})
    thumbnails = ThumbnailCandidates().thumbnail_candidates(visual_hooks=[visual], media_candidates=media)
    ai = next(item for item in media if item.media_asset_id == 'ai-1')
    policy = SafetyRightsPolicy(revision=POLICY_REVISION, allowed_availability=('AVAILABLE',), required_flags=('rights_cleared',), blocked_flags=('unsafe',))
    assert policy.allows(ai.availability, ai.safety_rights_status)
    proposal = {
        'visual_hook': ref('visual_hook', 'vh-1', 'hook-rev-1'), 'audio_hook': ref('audio_hook', 'ah-1', 'hook-rev-1'),
        'thumbnail': ref('thumbnail', thumbnails[0].thumbnail_id, thumbnails[0].revision_id),
        'scenes': [{'scene_id': 'sc-1', 'ref': ref('media_asset', 'ai-1', ai.artifact_version_ref), 'rationale': 'AI illustration of the article'}],
        'music_intents': [{'cue': 'intro_pad', 'description': 'soft pad'}], 'sfx_intents': [{'cue': 'whoosh', 'description': 'short whoosh'}],
        'rationale': 'AI illustration in the scene, seed images as fallback'}
    selection = select_creative_assets(
        workspace_id=WORKSPACE, snapshot_ref='snap-1', script_ref='script-1', angle_ref='angle-a', media_candidates=media,
        visual_hook_candidates=[visual], audio_hook_candidates=[audio], thumbnail_candidates=thumbnails, proposal=proposal,
        safety_policy=policy, music_sfx_policy_revision='music-v1', preset_registry_revision='preset-v1',
        weights=ScoringWeights(semantic=0.6, technical=0.4, recent_usage_penalty=0.1))
    assert ids_of(selection.assignments) == ['ai-1']
    assert selection.assignments[0].artifact_version_ref == version_of(sha_of('ai-1'))
    assert ids_of(selection.fallback_candidates) == SEED_IDS


def test_thumbnail_candidates_never_use_an_ai_still():
    media = candidates_of(ScriptedAssetReader([article_asset('img-a-hero'), ai_asset('ai-1'), *seeds(2)]))
    assert 'ai-1' in ids_of(media)
    thumbnails = ThumbnailCandidates().thumbnail_candidates(visual_hooks=[], media_candidates=media)
    assert [item.thumbnail_id for item in thumbnails] == ['thumb:img-a-hero', 'thumb:seed-bg-01.png', 'thumb:seed-bg-02.png']
    assert all(item.provenance['source_provenance']['origin'] != 'ai_generated' for item in thumbnails)
    only_ai = [item for item in media if item.provenance['origin'] == 'ai_generated']
    with pytest.raises(SelectionRejected) as caught:
        ThumbnailCandidates().thumbnail_candidates(visual_hooks=[], media_candidates=only_ai)
    assert (caught.value.code, caught.value.reason) == ('INPUT_NOT_READY', 'no_thumbnail_candidates')


def test_a_stored_ai_generated_provenance_loads_back_into_the_asset():
    asset = ai_asset('ai-1')
    entry = asset.provenance[0]
    stored = provenance_to_json(entry)
    assert stored['relation'] == 'ai_generated' and provenance_from_json(stored) == entry
    loaded = asset_from_rows('ai-1', sha_of('ai-1'), 1, asset_payload(asset, ['aigen:ai-1']), [{'seq': 0, 'entry': stored}])
    assert loaded == asset and loaded.provenance[0].relation is ProvenanceRelation.AI_GENERATED
    assert ProvenanceRelation('ai_generated') is ProvenanceRelation.AI_GENERATED


def test_origin_constants_agree_and_the_adapters_keep_the_boundary_to_c():
    assert media_module.ORIGIN_AI_GENERATED == thumbnail_module.ORIGIN_AI_GENERATED == 'ai_generated'
    assert media_module.RELATION_AI_GENERATED == ProvenanceRelation.AI_GENERATED.value == 'ai_generated'
    assert media_module.AI_LOCATOR.fullmatch(ai_locator('ai-1')) is not None and media_module.AI_LOCATOR.fullmatch('aigen://x/y') is None
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
    assert 'sha256:' not in texts['media_candidates'] and 'ingestion' not in texts['media_candidates'].lower()
    doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
    assert doc.splitlines().count('coveredIds: OI-CP7-11-Q1') == 1
