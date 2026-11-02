"""IMGGEN-PIPE: activity GenerateIllustrations on the PostgreSQL test database: snapshot, analysis and script of D written by the
real pipeline, catalog and staged versions of C and I, the real sidecar server of IMGGEN-SVC with a scripted engine and a scripted
chat route of the illustration role. No GPU, torch, model call or network beyond 127.0.0.1.

coveredIds: OI-CP7-11-Q2, CT-MED-001, CT-AI-006
"""
from __future__ import annotations

import ast
import datetime
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import threading
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from catalog.application.discovery import DiscoveryObservation, register_discovery
from catalog.domain.identity import CanonicalFingerprint, MediaKind, ProvenanceEntry, ProvenanceRelation
from controlplane.api.wiring import illustrations as module
from controlplane.api.wiring.illustrations import (
    CreativeIllustrationInputs, IllustrationService, illustration_activity_handlers, illustration_count, illustration_job_id)
from controlplane.api.wiring.production_profile import load_production_profile
from controlplane.api.wiring.workflow import media_assets_opener, staged_artifact_registrar
from controlplane.application.storage_meta.handlers import register_staged_artifact, verified_version_for_sha
from controlplane.domain.orchestration.fencing import GrantClaims
from controlplane.infrastructure.db.uow import TransactionManager
from controlplane.infrastructure.production_ports.imagegen_client import ImagegenClient
from creative.adapters.article_context import PostgresArticleContext
from creative.adapters.media_candidates import PostgresMediaCandidates
from creative.adapters.postgres_selection import PostgresSelectionStore
from creative.application.pipeline import AI_ROLES, CreativePipeline
from creative.persistence.uow import PostgresCreativeUnitOfWork
from creative.ports.repositories import EventContext
from tests.integration.prod_wiring.imggen_pipe_support import (
    GOOD_CAPTION, NOT_PROVISIONED, PUP_PROMPT, ScriptedBackend, ScriptedChatRoute, Sidecar, protocol, solid_png)

ROOT = pathlib.Path(__file__).resolve().parents[3]
PROFILE = ROOT / 'tools' / 'launcher' / 'prod' / 'profile.json'
FFMPEG = pathlib.Path('C:/ffmpeg/bin/ffmpeg.exe')
FFPROBE = pathlib.Path('C:/ffmpeg/bin/ffprobe.exe')
NOW = datetime.datetime(2026, 11, 2, 8, 0, 0, tzinfo=datetime.timezone.utc)
KEY = 'wf-1:media_select:GenerateIllustrations:0:r1'
INSTRUCTIONS = {role: f'Return JSON for {role}' for role in AI_ROLES}


def _load_d14():
    path = ROOT / 'tests' / 'integration' / 'creative' / 'test_d14_creative_pipeline.py'
    spec = importlib.util.spec_from_file_location('imggen_pipe_d14_support', path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


D14 = _load_d14()


class StaticGrants:
    def __init__(self, current=True):
        self.current = current
        self.asked = []

    def is_grant_current(self, grant):
        self.asked.append(grant)
        return self.current


@dataclass
class World:
    database: Any
    manager: Any
    staging: pathlib.Path
    endpoint: pathlib.Path
    tmp_path: pathlib.Path
    sidecars: list

    @property
    def ws(self):
        return self.database.workspace_id

    def uow_factory(self):
        return PostgresCreativeUnitOfWork(self.manager, workspace_id=self.ws)

    def media(self):
        def resolve(sha):
            version = verified_version_for_sha(self.manager, workspace_id=self.ws, sha256=sha)
            return None if version is None else version.artifact_version_id
        return PostgresMediaCandidates(media_assets_opener(self.manager), resolve_version=resolve,
                                       resolve_documents=lambda article_id, revision_id: (), safety_policy_revision='safe-r1')

    def add_image(self, name, entry, rgb):
        data = solid_png(64, 64, rgb)
        sha = hashlib.sha256(data).hexdigest()
        (self.staging / 'media').mkdir(parents=True, exist_ok=True)
        (self.staging / 'media' / f'{sha}.png').write_bytes(data)
        register_staged_artifact(self.manager, workspace_id=self.ws, staging_root=self.staging, owner_ref='test',
                                 relative_ref=f'media/{sha}.png', retention_ref='durable')
        with media_assets_opener(self.manager)(self.ws) as assets:
            register_discovery(assets, DiscoveryObservation('test:' + name, MediaKind.IMAGE, entry, CanonicalFingerprint(sha), True), 'ma-' + name)
        return sha

    def add_article_image(self, name, rgb=(10, 200, 30)):
        return self.add_image(name, ProvenanceEntry('src-1', 'a-1', None, f'https://img.example/a-1/{name}.jpg', '2026-11-02T07:30:00Z',
                                                    ProvenanceRelation.HERO_IMAGE), rgb)

    def sidecar(self, backend=None, **kwargs):
        sidecar = Sidecar(self.tmp_path / f'sidecar-{len(self.sidecars)}', self.endpoint, backend, **kwargs)
        self.sidecars.append(sidecar)
        return sidecar

    def service(self, route, *, grants=None, wait=20.0, clock=lambda: NOW, system_prompt=lambda: PUP_PROMPT):
        return IllustrationService(
            workspace_id=self.ws, inputs=CreativeIllustrationInputs(self.uow_factory), media=self.media(), route=route,
            client=ImagegenClient(self.endpoint), system_prompt=system_prompt, preview=lambda path: (path.read_bytes(), 'image/png'),
            register_version=staged_artifact_registrar(self.manager, self.ws, self.staging), open_assets=media_assets_opener(self.manager),
            staging_root=self.staging, grants=grants, clock=clock, wait_seconds=wait, poll_seconds=0.05, min_call_seconds=0.2)

    def candidates(self):
        with self.uow_factory() as uow:
            snapshot = uow.snapshots.get('snap-1')
        return self.media().media_candidates(workspace_id=self.ws, snapshot=snapshot)


def ctx(ws, number):
    return EventContext(workspace_id=ws, correlation_id='corr-1', actor='tester', occurred_at='2026-11-02T08:00:00+00:00',
                        recovery_epoch='1', event_id=f'evt-{number}', message_id=f'msg-{number}')


def seed_article(db):
    revision = {'article_revision_id': 'v1', 'article_id': 'a-1', 'revision_number': 1, 'title': 'Port strike ends',
                'normalized_text': 'The harbor union ended its three day strike.', 'source_id': 'src-1',
                'published_at': '2026-10-17T08:00:00+00:00', 'topic': 'labor'}
    with db.connect() as connection:
        connection.execute(
            'INSERT INTO controlplane.cp_articles (workspace_id, article_id, identity_key, exact_fingerprint, revision, payload) VALUES (%s, %s, %s, %s, 1, %s::jsonb)',
            (db.workspace_id, 'a-1', 'identity-a-1', 'f' * 64, json.dumps({'article_id': 'a-1'})))
        connection.execute(
            'INSERT INTO controlplane.cp_article_revisions (workspace_id, article_id, revision, payload) VALUES (%s, %s, 1, %s::jsonb)',
            (db.workspace_id, 'a-1', json.dumps(revision)))


@pytest.fixture
def world(pw_database, tmp_path, monkeypatch):
    monkeypatch.setattr(D14, 'WS', pw_database.workspace_id)
    seed_article(pw_database)
    manager = TransactionManager(pw_database.dsn, pool_max_size=4)
    staging = tmp_path / 'staging'
    staging.mkdir()
    built = World(pw_database, manager, staging.resolve(), tmp_path / 'data' / 'imagegen' / 'endpoint.json', tmp_path, [])
    route = D14.SpyRoute()
    pipeline = CreativePipeline(
        uow_factory=built.uow_factory, route=route, ai=D14.SelectionSplitAI(route, responses=D14._responses('v1'), config_revision='cfg-fake'),
        instructions=INSTRUCTIONS, articles=PostgresArticleContext(pw_database.connect), selections=PostgresSelectionStore(pw_database.connect))
    ws = pw_database.workspace_id
    pipeline.build_production_snapshot(context=ctx(ws, 1), idempotency_key='k-snap', **D14._snapshot_args())
    pipeline.analyze_content(context=ctx(ws, 2), idempotency_key='k-analysis', snapshot_id='snap-1', analysis_id='an-1', revision=1)
    pipeline.generate_story_angles(context=ctx(ws, 3), idempotency_key='k-angles', snapshot_id='snap-1', analysis_id='an-1',
                                   analysis_revision=1, set_id='set-1', requested_count=2, variation_policy_revision='var-v1')
    pipeline.generate_script(context=ctx(ws, 4), idempotency_key='k-script', **D14.SCRIPT_ARGS)
    for number in (1, 2):
        built.add_image(f'seed-bg-{number:02d}', ProvenanceEntry('seed-import', None, None, f'seed://bg-{number:02d}.png',
                                                               '2026-10-22T00:00:00Z', ProvenanceRelation.USER_IMPORTED), (number, number, number))
    try:
        yield built
    finally:
        for sidecar in built.sidecars:
            gate = getattr(sidecar.backend, 'gate', None)
            if gate is not None:
                gate.set()
            sidecar.stop()
        manager.close()


def request(key=KEY):
    return {'video_job_id': 'job-1', 'operation_key': key, 'stage_run_id': 'job-1:media_select:r1', 'activity_name': 'GenerateIllustrations',
            'input_refs': [{'ref_type': 'production_snapshot', 'ref_id': 'snap-1'},
                           {'ref_type': 'content_analysis', 'ref_id': 'an-1', 'revision_id': '1'},
                           {'ref_type': 'script_version', 'ref_id': 'script-1'}]}


def origins(candidates):
    return [item.provenance['origin'] for item in candidates]


def test_the_illustration_count_caps_at_four_and_targets_five_distinct_non_seed_images():
    assert [illustration_count(s, a) for s, a in ((2, 0), (4, 1), (8, 0), (8, 1), (8, 3), (8, 5), (3, 4), (0, 0))] == [2, 3, 4, 4, 2, 0, 0, 0]
    assert (module.MAX_AI_IMAGES_PER_VIDEO, module.TARGET_DISTINCT_IMAGES, module.ILLUSTRATION_WAIT_SECONDS) == (4, 5, 480.0)
    assert (module.ILLUSTRATION_SERVICE_UNAVAILABLE, module.ILLUSTRATION_GENERATION_FAILED, module.ILLUSTRATION_QUEUED) == (
        'illustration_service_unavailable', 'illustration_generation_failed', 'ILLUSTRATION_QUEUED')
    assert illustration_job_id('ws', KEY) == hashlib.sha256(f'ws:{KEY}'.encode()).hexdigest()[:32]
    assert module.derive_seed('a' * 32, 'shot-0-wide') == protocol.derive_seed('a' * 32, 'shot-0-wide')


def test_a_video_without_article_images_gets_one_ai_image_per_segment_listed_after_articles_and_before_seeds(world):
    sidecar = world.sidecar()
    route = ScriptedChatRoute()
    result = world.service(route)(request(), None)
    assert result['disposition'] == 'succeeded', result
    refs = result['output_refs']
    assert [ref['ref_type'] for ref in refs] == ['ai_illustration', 'ai_illustration']
    assert result['metrics'] == {'segments': 2, 'non_seed_candidates': 0, 'requested': 2, 'generated': 2, 'dropped_captions': 0}
    job_id = illustration_job_id(world.ws, KEY)
    record = sidecar.jobs()[job_id]
    items = record['request']['items']
    assert [(i['item_id'], i['width'], i['height'], i['steps']) for i in items] == [('shot-0-wide', 864, 1536, 16), ('shot-1-medium', 864, 1536, 16)]
    assert all(i['seed'] == protocol.derive_seed(job_id, i['item_id']) and i['caption'] == GOOD_CAPTION for i in items)
    plan, captions = route.plan_calls(), route.caption_calls()
    assert len(plan) == 1 and plan[0]['ai_role'] == 'illustration' and plan[0]['images'] == () and 'Plan exactly 2 photographs' in plan[0]['text']
    assert 'Harbor Union' not in plan[0]['text'] and '- scene one' in plan[0]['text'] and '- scene two' in plan[0]['text']
    assert len(captions) == 2 and all(c['system'] == PUP_PROMPT and c['text'].startswith('TARGET CANVAS: 9:16') for c in captions)
    found = world.candidates()
    assert origins(found) == ['ai_generated', 'ai_generated', 'seed', 'seed']
    by_id = {item.media_asset_id: item for item in found[:2]}
    assert sorted(by_id) == sorted(ref['ref_id'] for ref in refs)
    for ref in refs:
        candidate = by_id[ref['ref_id']]
        sha = candidate.provenance['sha256']
        assert candidate.artifact_version_ref == ref['revision_id']
        assert candidate.provenance['source_url'] == f'aigen://flux-3-image-klein/337337621b85/{sha}'
        assert candidate.provenance['article_ref'] == 'a-1' and candidate.provenance['model_ref'] == 'flux-3-image-klein@337337621b85'
        assert dict(candidate.safety_rights_status)['needs_image_safety'] is True
        assert (world.staging / 'media' / f'{sha}.png').read_bytes()[:8] == b'\x89PNG\r\n\x1a\n'
    stored = json.loads((world.staging / 'illustrations' / f'{job_id}.json').read_text(encoding='utf-8'))
    assert stored['article_id'] == 'a-1' and stored['body']['job_id'] == job_id and len(stored['body']['items']) == 2


def test_article_images_lower_the_count_and_enough_of_them_skip_every_call(world):
    world.sidecar()
    world.add_article_image('img-a-hero')
    route = ScriptedChatRoute()
    one = world.service(route)(request(), None)
    assert one['disposition'] == 'succeeded' and len(one['output_refs']) == 1 and one['metrics']['non_seed_candidates'] == 1
    assert len(route.plan_calls()) == 1 and len(route.plan_calls()[0]['images']) == 1 and len(route.caption_calls()) == 1
    assert 'attached article photographs' in route.plan_calls()[0]['text']
    world.add_article_image('img-a-inline', rgb=(200, 20, 30))
    quiet = ScriptedChatRoute()
    none = world.service(quiet)(request('wf-2:media_select:GenerateIllustrations:0:r1'), None)
    assert none == {'disposition': 'succeeded', 'output_refs': [], 'metrics': {'segments': 2, 'non_seed_candidates': 3, 'requested': 0, 'generated': 0}}
    assert quiet.calls == []
    assert origins(world.candidates()) == ['article', 'article', 'ai_generated', 'seed', 'seed']


def test_images_are_shared_by_the_article_so_a_later_run_of_the_same_article_generates_nothing(world):
    sidecar = world.sidecar()
    route = ScriptedChatRoute()
    first = world.service(route)(request(), None)
    calls = len(route.calls)
    for key in (KEY, 'wf-2:media_select:GenerateIllustrations:0:r1'):
        again = world.service(route)(request(key), None)
        assert again['disposition'] == 'succeeded' and again['output_refs'] == []
        assert again['metrics'] == {'segments': 2, 'non_seed_candidates': 2, 'requested': 0, 'generated': 0}
    assert len(first['output_refs']) == 2 and len(route.calls) == calls and len(sidecar.jobs()) == 1
    assert len(world.candidates()) == 4


def test_an_unfinished_job_waits_with_illustration_queued_and_the_rerun_collects_it(world):
    gate = threading.Event()
    world.sidecar(ScriptedBackend(gate=gate))
    route = ScriptedChatRoute()
    waiting = world.service(route, wait=1.0)(request(), None)
    assert waiting['disposition'] == 'waiting' and waiting['output_refs'] == []
    assert waiting['problem']['code'] == 'ILLUSTRATION_QUEUED' and waiting['problem']['retryable'] is True
    calls = len(route.calls)
    gate.set()
    done = world.service(route)(request(), None)
    assert done['disposition'] == 'succeeded' and len(done['output_refs']) == 2 and len(route.calls) == calls


def test_a_job_older_than_one_hour_gives_up_instead_of_waiting_forever(world):
    gate = threading.Event()
    world.sidecar(ScriptedBackend(gate=gate))
    assert world.service(ScriptedChatRoute(), wait=0.5)(request(), None)['disposition'] == 'waiting'
    late = world.service(ScriptedChatRoute(), wait=0.5, clock=lambda: NOW + datetime.timedelta(hours=2))(request(), None)
    assert late['disposition'] == 'failed' and late['problem']['code'] == 'illustration_generation_failed' and late['problem']['retryable'] is True
    assert late['metrics']['detail'] == 'job_timeout'


def test_without_a_sidecar_a_video_without_article_images_fails_and_one_with_them_goes_on_with_a_warning(world):
    route = ScriptedChatRoute()
    failed = world.service(route)(request(), None)
    assert failed['disposition'] == 'failed' and failed['problem']['code'] == 'illustration_service_unavailable'
    assert failed['problem']['retryable'] is True and failed['metrics']['detail'] == 'endpoint_missing' and route.calls == []
    world.sidecar(verification=NOT_PROVISIONED)
    world.add_article_image('img-a-hero')
    skipped = world.service(route)(request(), None)
    assert skipped['disposition'] == 'succeeded' and skipped['output_refs'] == []
    assert skipped['warnings'] == ['illustration_skipped:illustration_service_unavailable'] and skipped['metrics']['detail'] == 'not_provisioned'
    assert route.calls == []


def test_items_that_keep_failing_are_queued_again_until_the_sidecar_gives_up_then_fail_the_video(world):
    backend = ScriptedBackend(fail=True)
    world.sidecar(backend)
    result = world.service(ScriptedChatRoute())(request(), None)
    assert result['disposition'] == 'failed' and result['problem']['code'] == 'illustration_generation_failed'
    assert result['metrics']['detail'] == 'no_image' and result['warnings'] == ['illustration_item_failed:GENERATION_FAILED']
    assert len(backend.decoded) == 2 * protocol.MAX_ITEM_ATTEMPTS
    assert origins(world.candidates()) == ['seed', 'seed']


def test_captions_are_checked_by_code_retried_once_with_the_reason_then_dropped(world):
    sidecar = world.sidecar()
    with_logo = GOOD_CAPTION.replace('plain gray shipping containers', 'gray shipping containers with a logo')
    named = GOOD_CAPTION.replace('Two small anonymous figures', 'Two members of the Harbor Union')
    route = ScriptedChatRoute(captions=[with_logo, GOOD_CAPTION, named, named])
    result = world.service(route)(request(), None)
    assert result['disposition'] == 'succeeded' and len(result['output_refs']) == 1
    assert result['warnings'] == ['illustration_caption_dropped:medium'] and result['metrics']['dropped_captions'] == 1
    texts = [call['text'] for call in route.caption_calls()]
    assert len(texts) == 4 and 'RETRY REASON: Replace the word logo' in texts[1] and 'RETRY REASON: Replace the name Harbor Union' in texts[3]
    assert [i['item_id'] for i in sidecar.jobs()[illustration_job_id(world.ws, KEY)]['request']['items']] == ['shot-0-wide']


def test_a_stale_grant_does_nothing(world):
    world.sidecar()
    route = ScriptedChatRoute()
    claims = GrantClaims('g-1', 'job-1:media_select:r1', 1, '1', 'lease-1', '2026-11-02T08:00:00Z', '2026-11-02T09:00:00Z', 'GenerateIllustrations', 'fp')
    grants = StaticGrants(current=False)
    result = world.service(route, grants=grants)(request(), claims)
    assert result['disposition'] == 'stale' and route.calls == [] and len(grants.asked) == 1 and grants.asked[0].job_id == 'job-1'


def test_the_production_builder_checks_the_pinned_prompt_and_answers_through_service_handler(world):
    world.sidecar()
    hub = world.tmp_path / 'hub'
    prompts = hub / 'models--black-forest-labs--flux-3-image-klein-pup' / 'snapshots' / module.PUP_REVISION / 'system_prompts.json'
    prompts.parent.mkdir(parents=True)
    prompts.write_text(json.dumps({'t2i': 'not the pinned prompt'}), encoding='utf-8')
    profile = load_production_profile(PROFILE)
    runtime = SimpleNamespace(vision_route=ScriptedChatRoute(), ffmpeg_path=FFMPEG, staging_root=world.staging)
    handlers = illustration_activity_handlers(
        manager=world.manager, workspace_id=world.ws, profile=profile, runtime=runtime, creative_uow_factory=world.uow_factory,
        media=world.media(), grants=StaticGrants(), clock=lambda: NOW, endpoint_file=world.endpoint, hub_dir=hub)
    assert list(handlers) == ['GenerateIllustrations']
    claims = GrantClaims('g-1', 'job-1:media_select:r1', 1, '1', 'lease-1', '2026-11-02T08:00:00Z', '2026-11-02T09:00:00Z', 'GenerateIllustrations', 'fp')
    result = handlers['GenerateIllustrations'](request(), claims)
    assert (result['stage_run_id'], result['grant_id'], result['disposition']) == ('job-1:media_select:r1', 'g-1', 'failed')
    assert result['problem']['code'] == 'illustration_service_unavailable' and result['metrics']['detail'] == 'system_prompts_mismatch'
    assert runtime.vision_route.calls == []
    no_role = SimpleNamespace(ai=SimpleNamespace(route_model_refs={'image_safety': 'ag/gemini-3.8-flash-high'}, request_timeout_seconds=120))
    with pytest.raises(ValueError):
        illustration_activity_handlers(manager=world.manager, workspace_id=world.ws, profile=no_role, runtime=runtime,
                                       creative_uow_factory=world.uow_factory, media=world.media(), grants=None, clock=lambda: NOW,
                                       endpoint_file=None, hub_dir=None)


def test_the_pinned_prompt_values_match_the_sidecar_weights_lock_and_the_style_preview_is_at_most_1024_px(tmp_path):
    lock = json.loads((ROOT / 'tools' / 'imagegen' / 'weights.lock.json').read_text(encoding='utf-8'))
    entry = next(item for item in lock['files'] if item['path'] == 'system_prompts.json')
    assert (entry['repo'], entry['revision'], entry['sha256']) == (module.PUP_REPO, module.PUP_REVISION, module.PUP_SYSTEM_PROMPTS_SHA256)
    assert (protocol.MODEL_REVISION, protocol.DEFAULT_WIDTH, protocol.DEFAULT_HEIGHT, protocol.DEFAULT_STEPS) == (
        module.MODEL_REVISION, module.IMAGE_WIDTH, module.IMAGE_HEIGHT, module.IMAGE_STEPS)
    source = tmp_path / 'wide.png'
    source.write_bytes(solid_png(2000, 1000, (30, 60, 90)))
    data, media_type = module.ffmpeg_preview(FFMPEG)(source)
    out = tmp_path / 'preview.jpg'
    out.write_bytes(data)
    size = subprocess.run([str(FFPROBE), '-v', 'error', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', str(out)],
                          capture_output=True, text=True, check=True).stdout.strip()
    assert media_type == 'image/jpeg' and size == '1024,512'
    assert module.ffmpeg_preview(FFMPEG)(tmp_path / 'missing.png') is None


def test_the_wiring_module_imports_no_tools_and_names_no_test_double():
    source = (ROOT / 'src' / 'controlplane' / 'api' / 'wiring' / 'illustrations.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not {name for name in modules if name.split('.')[0] in ('tools', 'imagegen', 'src')}
    names = {getattr(node, 'id', None) or getattr(node, 'attr', None) for node in ast.walk(tree)}
    assert not {name for name in names if name and name.startswith(('Fake', 'InMemory', 'Memory'))}
    assert 'os.environ' not in source and 'mo' + 'ck' not in source.lower()
