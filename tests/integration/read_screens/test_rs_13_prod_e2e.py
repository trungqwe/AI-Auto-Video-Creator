"""RS-13: kiểm đầu cuối mười tài nguyên đọc trên ứng dụng build_production_app (PostgreSQL thử, TestClient, hai workspace).

Dữ liệu tạo bằng repository của phân hệ (như RS-2 đến RS-11); chỉ sessions và accounts dùng INSERT SQL tối thiểu vì src/ chưa có hàm ghi (BL-RS-04).
"""
from __future__ import annotations

import hashlib
import importlib
import itertools
import json
import uuid
from dataclasses import dataclass
from datetime import timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from catalog.domain.identity import CanonicalFingerprint, MediaAsset, MediaKind, ProvenanceEntry, ProvenanceRelation, RightsAssessment, RightsStatus
from catalog.persistence.assets import PostgresMediaAssetRepository
from controlplane.domain.config_security.incremental_cost import IncrementalCostRecord
from controlplane.domain.statemachine import ArtifactLocationState
from controlplane.infrastructure.db.config_security.stores import PostgresCostLedger
from controlplane.infrastructure.db.storage_meta import PostgresStorageMetaRepository
from controlplane.infrastructure.read_screens.compose import compose_read_screens
from creative.domain.analysis import parse_content_analysis
from creative.domain.angles import StoryAngle, build_story_angle_set
from creative.domain.ref_resolver import RefResolver, ResourceRef
from creative.domain.script import ScriptSegment, ScriptVersion
from creative.domain.snapshot import build_production_snapshot
from creative.persistence.repositories import PostgresAnalysisRepository, PostgresAngleSetRepository, PostgresScriptRepository, PostgresSnapshotRepository
from ingestion.domain.article import Article, ArticleRevision
from ingestion.persistence.repositories import PostgresArticleRepository, PostgresEventRepository

import rs_support

ROOT = Path(__file__).resolve().parents[3]
PROFILE_PATH = ROOT / 'tools' / 'launcher' / 'prod' / 'profile.json'
ACTOR_ID = '00000000-0000-0000-0000-0000000013a2'
PORT = 8443
BASE = f'https://127.0.0.1:{PORT}'
COUNTER = itertools.count(1)
RESOURCES = ('articles', 'events', 'media', 'artifacts', 'snapshots', 'story-angles', 'scripts', 'sessions', 'accounts', 'cost')

ID_KEY = {'articles': 'article_id', 'events': 'event_id', 'media': 'media_id', 'artifacts': 'version', 'snapshots': 'snapshot_id', 'story-angles': 'angle_id', 'scripts': 'script_id', 'sessions': 'session_id', 'accounts': 'account_ref', 'cost': 'cost_id'}
ROW_KEYS = {
    'articles': {'article_id', 'source_id', 'title', 'published_at', 'fetch_evidence_ref', 'revision', 'updated_at'},
    'events': {'event_id', 'title', 'status', 'source_id', 'fetch_evidence_ref', 'revision', 'updated_at'},
    'media': {'media_id', 'kind', 'rights_status', 'status', 'revision', 'updated_at'},
    'artifacts': {'artifact_id', 'version', 'state', 'kind', 'created_at'},
    'snapshots': {'snapshot_id', 'job_id', 'model', 'prompt_ref', 'config_revision_ref', 'created_at'},
    'story-angles': {'angle_id', 'snapshot_id', 'title', 'suitability', 'created_at'},
    'scripts': {'script_id', 'language', 'estimated_duration_seconds', 'revision', 'created_at'},
    'sessions': {'session_id', 'status', 'started_at', 'finished_at'},
    'accounts': {'account_ref', 'provider', 'account_label', 'status', 'updated_at'},
    'cost': {'cost_id', 'job_id', 'provider', 'amount', 'currency', 'amount_basis', 'recorded_at'},
}
# Khóa cấm của mục 4 plan.md: không khóa JSON nào trong phản hồi được trùng tên này.
FORBIDDEN_KEYS = ('normalized_text', 'requested_url', 'final_url', 'provenance_chain', 'member_refs', 'effective_time_range', 'topic', 'fingerprint', 'discovery_ids', 'original_locator', 'sha256_hash', 'owner_ref', 'provider_object_ref', 'logical_locator', 'verification_evidence_ref', 'source_refs', 'index_revision_refs', 'recent_variant_exclusions', 'summary', 'narrative_question', 'evidence_refs', 'segments', 'hook_intent', 'pronunciation_hints', 'recovery_epoch', 'token_hash', 'capabilities_json', 'credential_version', 'project_ref', 'quota_observation_ref', 'health', 'operation_ref', 'batch_ref', 'payload', 'workspace_id')
SOURCE_TABLES = ('cp_articles', 'cp_article_revisions', 'cp_events', 'cp_media_assets', 'cp_artifact_versions', 'cp_artifact_locations', 'cp_production_snapshots', 'cp_content_analyses', 'cp_story_angle_sets', 'cp_story_angles', 'cp_script_versions', 'cp_app_sessions', 'cp_external_accounts', 'cp_cost_records')


def utc(moment: Any) -> str:
    return moment.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def wiring(name: str) -> Any:
    return importlib.import_module('controlplane.api.wiring.' + name)


def make_runtime(root: Path) -> Any:
    return wiring('production_profile').ProductionRuntime(
        ffmpeg_path=root / 'bin' / 'ffmpeg.exe',
        ffprobe_path=root / 'bin' / 'ffprobe.exe',
        runtime_lock_path=root / 'runtime.lock.json',
        weights_dir=root / 'weights',
        weights_lock_path=root / 'model-weights.lock.json',
        whisper_model_dir=root / 'whisper',
        staging_root=root / 'staging',
        secret_store_root=root / 'vault',
        oauth_client_secrets_path=root / 'client.json',
        oauth_consent_timeout_seconds=300,
        route_cost_per_request=Decimal('0'),
        tokenization={'revision': 'adapt-wire-test', 'unicode_form': 'NFC', 'casefold': True, 'edge_strip_categories': ('P',), 'gap_tolerance_ms': 500, 'min_confidence': 0.5},
        drive_placement={'original': 'folder-original', 'reusable': 'folder-reusable', 'output': 'folder-output'},
        drive_fallback_parent_id='folder-root',
        route_catalog=SimpleNamespace(candidates=lambda workspace_id, ai_role: ()),
        provider_credentials=SimpleNamespace(acquire=lambda method, account: None),
        vision_route=SimpleNamespace(invoke_vision=lambda *args, **kwargs: ''),
        artifact_source=SimpleNamespace(open=lambda artifact_version_id: None),
        drive_token_broker=SimpleNamespace(acquire=lambda method, account: None),
        gpu_lease=SimpleNamespace(),
    )


def build_app(manager: Any, workspace_id: str, root: Path) -> Any:
    pp = wiring('production_profile')
    config = pp.WiringConfig(mode='production', workspace_id=workspace_id, profile=pp.load_production_profile(PROFILE_PATH), runtime=make_runtime(root))
    return wiring('production').build_production_app(manager=manager, config=config, port=PORT)


def cookie_value(response: Any, name: str) -> str:
    for header in response.headers.get_list('set-cookie'):
        if header.startswith(name + '='):
            return header.split(';', 1)[0].split('=', 1)[1]
    raise AssertionError('missing cookie ' + name)


def launch_headers(app: Any) -> dict[str, str]:
    path = app.launch_url(actor_id=ACTOR_ID, ttl_seconds=60)[len(BASE):]
    launched = TestClient(app, base_url=BASE, follow_redirects=False).get(path)
    assert launched.status_code == 303 and launched.headers['location'] == '/'
    session, csrf = cookie_value(launched, 'cp_session'), cookie_value(launched, 'csrf_token')
    return {'Cookie': f'cp_session={session}; csrf_token={csrf}', 'X-CSRF-Token': csrf, 'Origin': BASE}


def created_map(manager: Any, sql: str, params: tuple[Any, ...]) -> dict[str, str]:
    with manager.borrow_connection() as connection:
        return {key: utc(moment) for key, moment in connection.execute(sql, params).fetchall()}


def increasing(values: list[str]) -> list[str]:
    assert values == sorted(set(values)), values
    return values


def secret_values(manager: Any) -> list[str]:
    with manager.borrow_connection() as connection:
        hashes = connection.execute('SELECT sha256_hash FROM controlplane.cp_artifact_versions').fetchall()
        prints = connection.execute('SELECT fingerprint FROM controlplane.cp_media_assets WHERE fingerprint ~ %s', ('^[0-9a-f]{64}$',)).fetchall()
    return [str(row[0]) for row in (*hashes, *prints)]


def make_revision(article_id: str, number: int, **overrides: Any) -> ArticleRevision:
    data: dict[str, Any] = {
        'article_revision_id': f'{article_id}-r{number}', 'article_id': article_id, 'revision_number': number,
        'title': f'Title {article_id} v{number}', 'normalized_text': 'CANARY-NORMALIZED-TEXT', 'source_id': 'src-a',
        'source_revision': 1, 'collection_run_id': 'run-1', 'collected_document_id': f'doc-{article_id}-{number}',
        'requested_url': 'https://canary.example/requested', 'final_url': 'https://canary.example/final',
        'provenance_chain': ({'step': 'CANARY-PROVENANCE'},), 'raw_snapshot_ref': f'snap-{article_id}-{number}',
        'published_at': '2026-10-20T00:00:00Z', 'published_at_confidence': 'HIGH', 'fetched_at': '2026-10-22T00:00:00Z',
        'topic': 'tech', 'topic_uncertain': False, 'exact_fingerprint': f'fp-{article_id}-{number}',
        'media_discovery_refs': (), 'extractor_version': '1.0', 'normalizer_version': '1.0', 'is_complete': True,
        'uncertain_fields': (),
    }
    data.update(overrides)
    return ArticleRevision(**data)


def save_article(manager: Any, workspace_id: str, article_id: str, *revisions: ArticleRevision, updated_at: str) -> None:
    article = Article(article_id=article_id, identity_key=f'idk-{article_id}', representative_source_id='src-a', revisions=tuple(revisions))
    with manager.borrow_connection() as connection:
        PostgresArticleRepository(lambda: connection, workspace_id).save(article)
        # save() đóng dấu updated_at bằng giờ giao dịch; ghim lại để thứ tự và hoà điểm xác định.
        connection.execute('UPDATE controlplane.cp_articles SET updated_at = %s::timestamptz WHERE workspace_id = %s::uuid AND article_id = %s', (updated_at, workspace_id, article_id))


def save_event(manager: Any, workspace_id: str, event_id: str, *, status: str, revision: int, member_refs: Any, updated_at: str) -> None:
    event = {'event_id': event_id, 'status': status, 'revision': revision, 'topic': 'CANARY-TOPIC', 'member_refs': member_refs, 'effective_time_range': ('CANARY-RANGE-START', 'CANARY-RANGE-END'), 'event_link_policy_revision': 'elp-1', 'created_at': '2026-09-30T00:00:00Z', 'updated_at': '2000-01-01T00:00:00Z'}
    with manager.borrow_connection() as connection:
        PostgresEventRepository(lambda: connection, workspace_id).save(event)
        connection.execute('UPDATE controlplane.cp_events SET updated_at = %s::timestamptz WHERE workspace_id = %s::uuid AND event_id = %s', (updated_at, workspace_id, event_id))


def seed_ingestion(manager: Any, w1: str, w2: str) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    d1, d2, d3 = '2026-10-01T00:00:00.000000Z', '2026-10-02T00:00:00.000000Z', '2026-10-03T00:00:00.000000Z'
    rev = make_revision
    save_article(manager, w1, 'a-1', rev('a-1', 1, title='Alpha', source_id='src-a', raw_snapshot_ref='snap-a-1'), updated_at=d1)
    save_article(manager, w1, 'a-2', rev('a-2', 1, title='Beta v1', source_id='src-old', raw_snapshot_ref='snap-b-1'), rev('a-2', 2, title='Beta v2', source_id='src-b', raw_snapshot_ref='snap-b-2'), updated_at=d2)
    save_article(manager, w1, 'a-3', rev('a-3', 1, title='Gamma', source_id='src-a', published_at=None, raw_snapshot_ref=None), updated_at=d3)
    save_article(manager, w2, 'w2-only-article', rev('w2-only-article', 1, title='W2-ONLY-ARTICLE'), updated_at='2026-10-09T00:00:00.000000Z')
    save_event(manager, w1, 'e-1', status='candidate', revision=1, member_refs=(('a-1', 'a-1-r1'),), updated_at=d1)
    save_event(manager, w1, 'e-2', status='confirmed', revision=2, member_refs=(('a-2', 'a-2-r2'),), updated_at=d2)
    save_event(manager, w1, 'e-3', status='candidate', revision=1, member_refs=(('a-3', 'a-3-r1'),), updated_at=d3)
    save_event(manager, w2, 'w2-only-event', status='confirmed', revision=1, member_refs=(('a-1', 'a-1-r1'),), updated_at='2026-10-09T00:00:00.000000Z')
    rows = {
        'articles': [
            {'article_id': 'a-3', 'source_id': 'src-a', 'title': 'Gamma', 'published_at': None, 'fetch_evidence_ref': None, 'revision': 1, 'updated_at': d3},
            {'article_id': 'a-2', 'source_id': 'src-b', 'title': 'Beta v2', 'published_at': '2026-10-20T00:00:00Z', 'fetch_evidence_ref': 'snap-b-2', 'revision': 2, 'updated_at': d2},
            {'article_id': 'a-1', 'source_id': 'src-a', 'title': 'Alpha', 'published_at': '2026-10-20T00:00:00Z', 'fetch_evidence_ref': 'snap-a-1', 'revision': 1, 'updated_at': d1},
        ],
        'events': [
            {'event_id': 'e-3', 'title': 'Gamma', 'status': 'candidate', 'source_id': 'src-a', 'fetch_evidence_ref': None, 'revision': 1, 'updated_at': d3},
            {'event_id': 'e-2', 'title': 'Beta v2', 'status': 'confirmed', 'source_id': 'src-b', 'fetch_evidence_ref': 'snap-b-2', 'revision': 2, 'updated_at': d2},
            {'event_id': 'e-1', 'title': 'Alpha', 'status': 'candidate', 'source_id': 'src-a', 'fetch_evidence_ref': 'snap-a-1', 'revision': 1, 'updated_at': d1},
        ],
    }
    return rows, {'articles': 'w2-only-article', 'events': 'w2-only-event'}


def save_asset(manager: Any, workspace_id: str, asset_id: str, kind: str, fingerprinted: bool, rights: str, revision: int, updated_at: str) -> None:
    entry = ProvenanceEntry(source_ref='CANARY-SOURCE-REF', article_ref=None, event_ref=None, original_locator='https://canary.example/CANARY-LOCATOR', observed_at='2026-10-20T00:00:00Z', relation=ProvenanceRelation.HERO_IMAGE)
    fingerprint = CanonicalFingerprint(hashlib.sha256(f'{workspace_id}/{asset_id}'.encode('utf-8')).hexdigest()) if fingerprinted else None
    asset = MediaAsset(media_asset_id=asset_id, kind=MediaKind(kind), fingerprint=fingerprint, provenance=(entry,), rights=RightsAssessment(RightsStatus(rights), ('CANARY-EVIDENCE',)), index_revision=revision)
    with manager.borrow_connection() as connection:
        PostgresMediaAssetRepository(connection, workspace_id).save(asset, discovery_id=f'CANARY-DISCOVERY-{asset_id}')
        connection.execute('UPDATE controlplane.cp_media_assets SET updated_at = %s::timestamptz WHERE workspace_id = %s::uuid AND media_asset_id = %s', (updated_at, workspace_id, asset_id))


def seed_artifact(manager: Any, workspace_id: str, artifact_id: str, kind: str, state: str | None) -> str:
    number = next(COUNTER)
    version_id = str(uuid.uuid4())
    with manager.borrow_connection() as connection:
        repository = PostgresStorageMetaRepository(connection)
        digest = hashlib.sha256(f'{workspace_id}/{artifact_id}/{number}'.encode('utf-8')).hexdigest()
        version = repository.insert_version(version_id, {'workspace_id': workspace_id, 'artifact_id': artifact_id, 'sha256_hash': digest, 'size_bytes': 1024, 'mime_type': 'video/mp4', 'artifact_kind': kind, 'owner_ref': f'CANARY-OWNER-{number}', 'retention_ref': 'retention-rs13', 'sensitivity_ref': 'internal'})
        assert version is not None
        if state is not None:
            location = repository.insert_location(str(uuid.uuid4()), {'workspace_id': workspace_id, 'artifact_version_id': version_id, 'backend_ref': 'local-disk', 'provider_namespace_ref': 'ns-rs13', 'provider_object_ref': f'CANARY-OBJECT-{number}', 'logical_locator': f'loc/CANARY-LOCATOR-{number}'})
            assert location is not None
            location = repository.update_location(location, location.revision, ArtifactLocationState(state), 'CANARY-EVIDENCE')
            assert location is not None and location.state.value == state
    return version_id


def seed_catalog(manager: Any, w1: str, w2: str) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    save_asset(manager, w1, 'alpha', 'image', True, 'known', 1, '2026-10-03T00:00:00.000000Z')
    save_asset(manager, w1, 'bravo', 'clip', True, 'unknown', 2, '2026-10-01T00:00:00.000000Z')
    save_asset(manager, w1, 'charlie', 'audio', False, 'disputed', 1, '2026-10-05T00:00:00.123456Z')
    save_asset(manager, w2, 'w2-only-media', 'clip', True, 'known', 1, '2026-10-09T00:00:00.000000Z')
    alpha = seed_artifact(manager, w1, 'art-alpha', 'rendered_video', 'VERIFIED')
    bravo = seed_artifact(manager, w1, 'art-bravo', 'thumbnail', None)
    charlie = seed_artifact(manager, w1, 'art-charlie', 'subtitle', 'AVAILABLE_UNVERIFIED')
    foreign = seed_artifact(manager, w2, 'w2-only-art', 'thumbnail', 'VERIFIED')
    stamps = created_map(manager, 'SELECT artifact_version_id::text, created_at FROM controlplane.cp_artifact_versions WHERE workspace_id = %s::uuid', (w1,))
    increasing([stamps[alpha], stamps[bravo], stamps[charlie]])
    rows = {
        'media': [
            {'media_id': 'charlie', 'kind': 'audio', 'rights_status': 'disputed', 'status': 'DISCOVERED', 'revision': 1, 'updated_at': '2026-10-05T00:00:00.123456Z'},
            {'media_id': 'alpha', 'kind': 'image', 'rights_status': 'known', 'status': 'CATALOGED', 'revision': 1, 'updated_at': '2026-10-03T00:00:00.000000Z'},
            {'media_id': 'bravo', 'kind': 'clip', 'rights_status': 'unknown', 'status': 'CATALOGED', 'revision': 2, 'updated_at': '2026-10-01T00:00:00.000000Z'},
        ],
        'artifacts': [
            {'artifact_id': 'art-charlie', 'version': charlie, 'state': 'AVAILABLE_UNVERIFIED', 'kind': 'subtitle', 'created_at': stamps[charlie]},
            {'artifact_id': 'art-bravo', 'version': bravo, 'state': None, 'kind': 'thumbnail', 'created_at': stamps[bravo]},
            {'artifact_id': 'art-alpha', 'version': alpha, 'state': 'VERIFIED', 'kind': 'rendered_video', 'created_at': stamps[alpha]},
        ],
    }
    return rows, {'media': 'w2-only-media', 'artifacts': foreign}


def build_snapshot(snapshot_id: str, job_ref: str | None) -> Any:
    number = next(COUNTER)
    return build_production_snapshot(
        snapshot_id=snapshot_id, production_mode='single_article',
        source_refs=[{'ref_type': 'article', 'ref_id': f'CANARY-SOURCE-{number}', 'revision_id': 'rev-1'}],
        index_revision_refs=[{'ref_type': 'index', 'ref_id': f'CANARY-INDEX-{number}', 'revision_id': 'rev-1'}],
        configuration_revision_refs=[{'ref_type': 'config_bundle', 'ref_id': f'cfg-{number}', 'revision_id': 'rev-1'}],
        content_ref_types=['article'], eligibility_reason='eligible', snapshot_timestamp='2026-10-01T00:00:00+00:00',
        video_job_ref=job_ref, recent_variant_exclusions=[f'CANARY-EXCLUSION-{number}'],
    )


def seed_snapshot(manager: Any, workspace_id: str, snapshot_id: str, job_ref: str | None) -> Any:
    snapshot = build_snapshot(snapshot_id, job_ref)
    with manager.borrow_connection() as connection:
        PostgresSnapshotRepository(lambda: connection, workspace_id).add(snapshot)
    return snapshot


def append_analysis(manager: Any, workspace_id: str, snapshot: Any, analysis_id: str, revision: int, model: str, prompt_id: str, prompt_revision: str) -> None:
    analysis = make_analysis(workspace_id, snapshot, analysis_id, revision, model, prompt_id, prompt_revision)
    with manager.borrow_connection() as connection:
        PostgresAnalysisRepository(lambda: connection, workspace_id).append(analysis_id, revision, analysis)


def make_analysis(workspace_id: str, snapshot: Any, analysis_id: str, revision: int, model: str, prompt_id: str, prompt_revision: str) -> Any:
    source = dict(snapshot.source_refs[0])
    prompt = {'workspace_id': workspace_id, 'ref_type': 'prompt_revision', 'ref_id': prompt_id, 'revision_id': prompt_revision}
    resolver = RefResolver(
        workspace_id=workspace_id,
        allowed_refs=[ResourceRef(workspace_id, source['ref_type'], source['ref_id'], source['revision_id']), ResourceRef(**prompt)],
        allowed_ref_types=['article', 'prompt_revision'],
    )
    raw = {
        'analysis_id': analysis_id, 'revision': revision, 'topic': f'topic of {analysis_id}',
        'entities': [], 'timeline': [], 'locations': [],
        'facts': [{'id': 'f-1', 'text': 'CANARY-FACT', 'evidence_refs': [{'workspace_id': workspace_id, **source}]}],
        'uncertainties': [], 'contradictions': [], 'event_relation': 'standalone', 'update_context': '',
        'risk_flags': [], 'narrative_opportunities': [], 'media_needs': [],
        'trace': {'provider': 'fake-provider', 'model': model, 'prompt_ref': prompt, 'policy_revision': 'pol-1'},
    }
    return parse_content_analysis(raw, snapshot, resolver)


def append_angle_set(manager: Any, workspace_id: str, set_id: str, analysis_id: str, specs: list[tuple[str, str, str]]) -> None:
    ref = ResourceRef(workspace_id, 'article', 'CANARY-EVIDENCE-1', 'rev-1')
    candidates = [
        StoryAngle(
            angle_id=angle_id, title=title, summary=f'CANARY-SUMMARY {angle_id}',
            narrative_question=f'CANARY-QUESTION {set_id} {angle_id}?', focus_entities=[f'CANARY-ENTITY {angle_id}'],
            timeframe='2026-10', evidence_refs=[ref], planned_inference_elements=['inference'],
            planned_creative_elements=['creative'], suitability=suitability, risk_flags=[],
        )
        for angle_id, title, suitability in specs
    ]
    angle_set = build_story_angle_set(set_id=set_id, analysis_id=analysis_id, analysis_revision=1, requested_count=len(candidates), candidates=candidates, variation_policy_revision='var-1')
    with manager.borrow_connection() as connection:
        PostgresAngleSetRepository(lambda: connection, workspace_id).append(set_id, 1, angle_set)


def append_script(manager: Any, workspace_id: str, script_id: str, language: str, duration: float) -> None:
    ref = ResourceRef(workspace_id, 'article', 'CANARY-REF', 'rev-1')
    segment = ScriptSegment(
        segment_id=f'seg-{script_id}', order=0, text=f'CANARY-NARRATION {script_id}', claim_mode='inference',
        scene_intent='CANARY-SCENE', source_refs=(ref,), disclosure='CANARY-DISCLOSURE', word_count=2, estimated_seconds=1.0,
    )
    script = ScriptVersion(
        script_version_id=script_id, language=language, hook_intent='CANARY-HOOK', thumbnail_transition='CANARY-THUMBNAIL',
        segments=(segment,), pronunciation_hints=({'term': 'CANARY-TERM', 'pronunciation': 'CANARY-SOUND'},),
        speech_rate=2.5, estimated_duration_seconds=duration,
    )
    with manager.borrow_connection() as connection:
        PostgresScriptRepository(lambda: connection, workspace_id).append(script_id, 1, script)


def seed_creative_data(manager: Any, w1: str, w2: str) -> tuple[Any, Any, Any]:
    s1 = seed_snapshot(manager, w1, 'snap-a-1', 'job-1')
    append_analysis(manager, w1, s1, 'an-1', 1, 'model-old', 'prompt-old', 'rev-old')
    append_analysis(manager, w1, s1, 'an-1', 2, 'model-new', 'prompt-new', 'rev-new')
    s2 = seed_snapshot(manager, w1, 'snap-a-2', 'job-2')
    s3 = seed_snapshot(manager, w1, 'snap-a-3', None)
    append_analysis(manager, w1, s3, 'an-3', 1, 'model-three', 'prompt-three', 'rev-three')
    other = seed_snapshot(manager, w2, 'w2-only-snap', 'job-1')
    append_analysis(manager, w2, other, 'an-w2', 1, 'model-other', 'prompt-other', 'rev-other')
    append_analysis(manager, w2, s2, 'an-snap-leak', 1, 'model-leak', 'prompt-leak', 'rev-leak')
    append_analysis(manager, w1, build_snapshot('ang-snap-1', None), 'an-ang-1', 1, 'model-ang', 'prompt-ang', 'rev-ang')
    append_analysis(manager, w2, build_snapshot('ang-snap-leak', None), 'an-ang-leak', 1, 'model-ang', 'prompt-ang', 'rev-ang')
    append_angle_set(manager, w1, 'set-a', 'an-ang-1', [('a-1', 'Title A1', 'high')])
    append_angle_set(manager, w1, 'set-b', 'an-ang-leak', [('b-1', 'Title B1', 'low')])
    append_angle_set(manager, w1, 'set-c', 'an-ang-1', [('c-1', 'Title C1', 'medium')])
    append_angle_set(manager, w2, 'w2-only-set', 'an-ang-leak', [('w-1', 'W2-ONLY-ANGLE', 'low')])
    for script_id, language, duration in (('sv-c', 'en', 45.0), ('sv-a', 'vi', 30.5), ('sv-b', 'vi', 12.0)):
        append_script(manager, w1, script_id, language, duration)
    append_script(manager, w2, 'w2-only-script', 'fr', 20.0)
    return s1, s2, s3


def seed_creative(manager: Any, w1: str, w2: str) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    s1, s2, s3 = seed_creative_data(manager, w1, w2)
    snaps = created_map(manager, 'SELECT snapshot_id, created_at FROM controlplane.cp_production_snapshots WHERE workspace_id = %s::uuid', (w1,))
    angles = created_map(manager, 'SELECT angle_id, created_at FROM controlplane.cp_story_angles WHERE workspace_id = %s::uuid', (w1,))
    scripts = created_map(manager, 'SELECT script_version_id, created_at FROM controlplane.cp_script_versions WHERE workspace_id = %s::uuid', (w1,))
    increasing([snaps['snap-a-1'], snaps['snap-a-2'], snaps['snap-a-3']])
    increasing([angles['set-a:a-1'], angles['set-b:b-1'], angles['set-c:c-1']])
    increasing([scripts['sv-c'], scripts['sv-a'], scripts['sv-b']])

    def snapshot_row(snapshot: Any, job_id: str | None, model: str | None, prompt_ref: str | None) -> dict[str, Any]:
        return {'snapshot_id': snapshot.snapshot_id, 'job_id': job_id, 'model': model, 'prompt_ref': prompt_ref, 'config_revision_ref': snapshot.configuration_bundle_fingerprint, 'created_at': snaps[snapshot.snapshot_id]}

    def angle_row(angle_id: str, snapshot_id: str | None, title: str, suitability: str) -> dict[str, Any]:
        return {'angle_id': angle_id, 'snapshot_id': snapshot_id, 'title': title, 'suitability': suitability, 'created_at': angles[angle_id]}

    def script_row(script_id: str, language: str, duration: float) -> dict[str, Any]:
        return {'script_id': script_id, 'language': language, 'estimated_duration_seconds': duration, 'revision': 1, 'created_at': scripts[script_id]}

    rows = {
        'snapshots': [snapshot_row(s3, None, 'model-three', 'prompt-three@rev-three'), snapshot_row(s2, 'job-2', None, None), snapshot_row(s1, 'job-1', 'model-new', 'prompt-new@rev-new')],
        'story-angles': [angle_row('set-c:c-1', 'ang-snap-1', 'Title C1', 'medium'), angle_row('set-b:b-1', None, 'Title B1', 'low'), angle_row('set-a:a-1', 'ang-snap-1', 'Title A1', 'high')],
        'scripts': [script_row('sv-b', 'vi', 12.0), script_row('sv-a', 'vi', 30.5), script_row('sv-c', 'en', 45.0)],
    }
    return rows, {'snapshots': 'w2-only-snap', 'story-angles': 'w2-only-set:w-1', 'scripts': 'w2-only-script'}


def seed_control_data(manager: Any, w1: str, w2: str) -> None:
    with manager.borrow_connection() as connection:
        for workspace_id, ref, status, started_at, ended_at in (
            (w1, 'ses-c', 'ENDED', '2026-10-01T08:00:00+00:00', '2026-10-01T09:30:00+00:00'),
            (w1, 'ses-a', 'ACTIVE', '2026-10-02T08:00:00+00:00', None),
            (w1, 'ses-b', 'ABANDONED', '2026-10-03T08:00:00+00:00', '2026-10-03T08:10:00+00:00'),
            (w2, 'w2-only-ses', 'ACTIVE', '2026-10-05T08:00:00+00:00', None),
        ):
            connection.execute('INSERT INTO controlplane.cp_app_sessions (workspace_id, session_ref, status, recovery_epoch, started_at, ended_at) VALUES (%s::uuid, %s, %s, %s, %s::timestamptz, %s::timestamptz)', (workspace_id, ref, status, f'CANARY-EPOCH-{ref}', started_at, ended_at))
        for workspace_id, ref, provider, label, status, updated_at in (
            (w1, 'acc-c', 'drive', 'Drive main', 'ENABLED', '2026-10-01T08:00:00+00:00'),
            (w1, 'acc-a', 'drive', 'Drive backup', 'DEGRADED', '2026-10-02T08:00:00+00:00'),
            (w1, 'acc-b', 'router', 'Router main', 'ENABLED', '2026-10-03T08:00:00+00:00'),
            (w2, 'w2-only-acc', 'router', 'W2-ONLY-ROUTER', 'INVALID', '2026-10-05T08:00:00+00:00'),
        ):
            connection.execute('INSERT INTO controlplane.cp_external_accounts (workspace_id, external_account_id, provider, account_label, status, project_ref, capabilities_json, credential_version, credential_updated_at, credential_expires_at, quota_observation_ref, health, updated_at) VALUES (%s::uuid, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::timestamptz, %s::timestamptz, %s, %s, %s::timestamptz)', (workspace_id, ref, provider, label, status, f'CANARY-PROJECT-{ref}', json.dumps([f'CANARY-CAPABILITY-{ref}']), 7, '2026-10-20T00:00:00+00:00', '2027-10-20T00:00:00+00:00', f'CANARY-QUOTA-{ref}', f'CANARY-HEALTH-{ref}', updated_at))
        ledger = PostgresCostLedger(connection)
        for workspace_id, ref, provider, job, estimated, actual, currency, occurred_at in (
            (w1, 'cost-c', 'router', 'job-1', '0.50', '0.40', 'USD', '2026-10-01T08:00:00+00:00'),
            (w1, 'cost-a', 'router', 'job-1', '0.200000', None, 'USD', '2026-10-02T08:00:00+00:00'),
            (w1, 'cost-b', 'drive', None, '1.25', '1.30', 'VND', '2026-10-03T08:00:00+00:00'),
            (w2, 'w2-only-cost', 'drive', 'job-9', '3.50', '3.25', 'USD', '2026-10-04T08:00:00+00:00'),
        ):
            ledger.append(workspace_id, IncrementalCostRecord(ref, provider, f'CANARY-SERVICE-{ref}', f'CANARY-OPERATION-{ref}', job, f'CANARY-BATCH-{ref}', Decimal('1'), 'CANARY-UNIT', Decimal(estimated), None if actual is None else Decimal(actual), currency, f'CANARY-SOURCE-{ref}', occurred_at, 'api_paid'))


def seed_control(manager: Any, w1: str, w2: str) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    seed_control_data(manager, w1, w2)
    z = '.000000Z'
    rows = {
        'sessions': [
            {'session_id': 'ses-b', 'status': 'ABANDONED', 'started_at': '2026-10-03T08:00:00' + z, 'finished_at': '2026-10-03T08:10:00' + z},
            {'session_id': 'ses-a', 'status': 'ACTIVE', 'started_at': '2026-10-02T08:00:00' + z, 'finished_at': None},
            {'session_id': 'ses-c', 'status': 'ENDED', 'started_at': '2026-10-01T08:00:00' + z, 'finished_at': '2026-10-01T09:30:00' + z},
        ],
        'accounts': [
            {'account_ref': 'acc-b', 'provider': 'router', 'account_label': 'Router main', 'status': 'ENABLED', 'updated_at': '2026-10-03T08:00:00' + z},
            {'account_ref': 'acc-a', 'provider': 'drive', 'account_label': 'Drive backup', 'status': 'DEGRADED', 'updated_at': '2026-10-02T08:00:00' + z},
            {'account_ref': 'acc-c', 'provider': 'drive', 'account_label': 'Drive main', 'status': 'ENABLED', 'updated_at': '2026-10-01T08:00:00' + z},
        ],
        'cost': [
            {'cost_id': 'cost-b', 'job_id': None, 'provider': 'drive', 'amount': '1.30', 'currency': 'VND', 'amount_basis': 'actual', 'recorded_at': '2026-10-03T08:00:00' + z},
            {'cost_id': 'cost-a', 'job_id': 'job-1', 'provider': 'router', 'amount': '0.200000', 'currency': 'USD', 'amount_basis': 'estimated', 'recorded_at': '2026-10-02T08:00:00' + z},
            {'cost_id': 'cost-c', 'job_id': 'job-1', 'provider': 'router', 'amount': '0.40', 'currency': 'USD', 'amount_basis': 'actual', 'recorded_at': '2026-10-01T08:00:00' + z},
        ],
    }
    return rows, {'sessions': 'w2-only-ses', 'accounts': 'w2-only-acc', 'cost': 'w2-only-cost'}


@dataclass(frozen=True)
class World:
    client: TestClient
    headers: dict[str, str]
    manager: Any
    workspace_id: str
    other_workspace_id: str
    served: frozenset[str]
    rows: dict[str, list[dict[str, Any]]]
    foreign_ids: dict[str, str]
    secrets: list[str]


def seed_all(manager: Any, w1: str, w2: str) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    rows: dict[str, list[dict[str, Any]]] = {}
    foreign: dict[str, str] = {}
    for seed in (seed_ingestion, seed_catalog, seed_creative, seed_control):
        part_rows, part_foreign = seed(manager, w1, w2)
        rows.update(part_rows)
        foreign.update(part_foreign)
    assert set(rows) == set(RESOURCES) and set(foreign) == set(RESOURCES)
    return rows, foreign


@pytest.fixture(scope='module')
def world(tmp_path_factory):
    with rs_support.temp_database() as (manager, w1, w2):
        with manager.borrow_connection() as connection:
            connection.execute('INSERT INTO controlplane.cp_actors (actor_id, workspace_id, actor_type, display_name, status) VALUES (%s, %s, %s, %s, %s)', (ACTOR_ID, w1, 'user', 'rs-13', 'ACTIVE'))
        rows, foreign = seed_all(manager, w1, w2)
        app = build_app(manager, w1, tmp_path_factory.mktemp('rs13'))
        client = TestClient(app, base_url=BASE, follow_redirects=False)
        yield World(client, launch_headers(app), manager, w1, w2, frozenset(app.api_app.state.module_services), rows, foreign, secret_values(manager))


def get(world: World, path: str, **params: str) -> Any:
    return world.client.get(path, params=params or None, headers=world.headers)


def item_path(resource: str, item_id: str) -> str:
    return '/v1/' + resource + '/' + quote(item_id, safe='')


def walk(world: World, resource: str, limit: int) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    cursor = None
    for _ in range(10):
        params = {'limit': str(limit)} if cursor is None else {'limit': str(limit), 'cursor': cursor}
        response = get(world, '/v1/' + resource, **params)
        assert response.status_code == 200, (resource, response.status_code, response.text)
        body = response.json()
        assert set(body) == {'items', 'next_cursor'}, resource
        pages.append(body)
        cursor = body['next_cursor']
        if cursor is None:
            return pages
    raise AssertionError('pagination did not terminate: ' + resource)


def table_state(manager: Any) -> dict[str, tuple[int, str]]:
    # Số hàng và md5 của toàn bộ nội dung từng bảng nguồn: bắt cả INSERT, UPDATE lẫn DELETE.
    state: dict[str, tuple[int, str]] = {}
    with manager.borrow_connection() as connection:
        for table in SOURCE_TABLES:
            sql = 'SELECT count(*), md5(coalesce(string_agg(r::text, chr(124) ORDER BY r::text), chr(32))) FROM controlplane.' + table + ' r'
            count, digest = connection.execute(sql).fetchone()
            state[table] = (count, digest)
    return state


def sweep(world: World) -> list[str]:
    texts: list[str] = []
    for resource in RESOURCES:
        texts.append(get(world, '/v1/' + resource, limit='100').text)
        cursor = None
        for _ in range(5):
            params = {'limit': '1'} if cursor is None else {'limit': '1', 'cursor': cursor}
            response = get(world, '/v1/' + resource, **params)
            texts.append(response.text)
            cursor = response.json()['next_cursor']
            if cursor is None:
                break
        for item_id in [row[ID_KEY[resource]] for row in world.rows[resource]] + ['does-not-exist', world.foreign_ids[resource]]:
            texts.append(get(world, item_path(resource, item_id)).text)
    texts.append(get(world, '/v1/logs').text)
    texts.append(world.client.patch('/v1/media/alpha', json={'tags': ['a']}, headers={**world.headers, 'Idempotency-Key': 'rs13-sweep', 'If-Match': '1'}).text)
    return texts


def test_ten_read_services_are_attached_and_logs_is_not(world):
    assert world.served == {'sources', 'hooks', *RESOURCES}
    assert 'logs' not in world.served


@pytest.mark.parametrize('resource', RESOURCES)
def test_foreign_rows_exist_in_the_other_workspace(world, resource):
    service = compose_read_screens(world.manager)[resource]
    other, mine = world.other_workspace_id, world.workspace_id
    assert service.fetch_one(rs_support.FakeRequest(other), other, world.foreign_ids[resource]) is not None
    assert service.fetch_one(rs_support.FakeRequest(mine), mine, world.foreign_ids[resource]) is None


@pytest.mark.parametrize('resource', RESOURCES)
def test_list_returns_the_seeded_rows_newest_first(world, resource):
    response = get(world, '/v1/' + resource, limit='100')
    assert response.status_code == 200, (resource, response.status_code, response.text)
    body = response.json()
    assert body == {'items': world.rows[resource], 'next_cursor': None}, resource
    assert all(set(item) == ROW_KEYS[resource] for item in body['items']), resource


@pytest.mark.parametrize('resource', RESOURCES)
def test_first_page_has_one_row_and_a_cursor(world, resource):
    expected = world.rows[resource]
    assert len(expected) == 3
    response = get(world, '/v1/' + resource, limit='1')
    assert response.status_code == 200, (resource, response.status_code, response.text)
    body = response.json()
    assert body['items'] == expected[:1], resource
    assert body['next_cursor'], resource


@pytest.mark.parametrize('resource', RESOURCES)
def test_cursor_returns_the_remaining_rows(world, resource):
    first = get(world, '/v1/' + resource, limit='1').json()
    rest = get(world, '/v1/' + resource, limit='100', cursor=first['next_cursor'])
    assert rest.status_code == 200, (resource, rest.status_code, rest.text)
    assert rest.json() == {'items': world.rows[resource][1:], 'next_cursor': None}, resource


@pytest.mark.parametrize('resource', RESOURCES)
def test_walking_with_limit_one_visits_every_row_once(world, resource):
    pages = walk(world, resource, 1)
    assert [page['items'] for page in pages] == [[row] for row in world.rows[resource]], resource
    assert all(page['next_cursor'] for page in pages[:-1]) and pages[-1]['next_cursor'] is None, resource


@pytest.mark.parametrize('resource', RESOURCES)
def test_detail_returns_the_listed_row(world, resource):
    for row in world.rows[resource]:
        response = get(world, item_path(resource, row[ID_KEY[resource]]))
        assert response.status_code == 200, (resource, row, response.status_code, response.text)
        assert response.json() == row, resource


@pytest.mark.parametrize('resource', RESOURCES)
def test_unknown_and_foreign_ids_are_not_found(world, resource):
    for item_id in ('does-not-exist', world.foreign_ids[resource]):
        response = get(world, item_path(resource, item_id))
        assert response.status_code == 404, (resource, item_id, response.status_code, response.text)
        assert response.json()['code'] == 'NOT_FOUND', (resource, item_id)


@pytest.mark.parametrize('resource', RESOURCES)
def test_requests_without_a_session_are_rejected(world, resource):
    assert world.client.get('/v1/' + resource, params={'limit': '1'}).status_code == 403, resource


@pytest.mark.parametrize('item_id', ['x', 'alpha', 'does-not-exist'])
def test_patch_media_is_unavailable(world, item_id):
    response = world.client.patch('/v1/media/' + item_id, json={'tags': ['a']}, headers={**world.headers, 'Idempotency-Key': 'media-' + item_id, 'If-Match': '1'})
    assert response.status_code == 503, (item_id, response.status_code, response.text)
    assert response.json()['code'] == 'CAPABILITY_UNAVAILABLE'


def test_logs_has_no_route(world):
    # /v1/logs không có nguồn đọc thật (plan.md mục 5.11): vẫn 404, không bị nối ngầm.
    assert get(world, '/v1/logs').status_code == 404
    assert get(world, '/v1/logs', limit='1').status_code == 404
    assert get(world, '/v1/logs/log-1').status_code == 404


def test_sources_and_hooks_keep_their_state(world):
    assert world.client.get('/v1/sources', params={'limit': '1'}).status_code == 403
    for name in ('sources', 'hooks'):
        response = get(world, '/v1/' + name, limit='1')
        assert response.status_code == 200 and response.json() == {'items': [], 'next_cursor': None}, name
    assert world.client.get('/v1/secrets/secret-1', headers=world.headers).status_code in (404, 405)


def test_no_response_leaks_a_canary_a_forbidden_field_or_the_other_workspace(world):
    texts = sweep(world)
    assert world.secrets
    assert any('Alpha' in text for text in texts) and any('Title C1' in text for text in texts)
    for text in texts:
        lowered = text.lower()
        assert 'canary' not in lowered and 'w2-only' not in lowered, text
        assert not [name for name in FORBIDDEN_KEYS if chr(34) + name + chr(34) in text], text
        assert not [value for value in world.secrets if value in text], text


def test_requests_do_not_change_source_tables(world):
    before = table_state(world.manager)
    assert all(count > 0 for count, _ in before.values()), before
    sweep(world)
    assert table_state(world.manager) == before
