"""Kiểm đấu nối từng phân hệ với adapter thật trên PostgreSQL 18.6 dùng một lần.

coveredIds: PW-W1-01
"""
from __future__ import annotations

import ast
import dataclasses
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import importlib
import json
import os
from pathlib import Path
import re
from types import SimpleNamespace
import uuid

import psycopg
import pytest

from controlplane.application.config_security.capacity_reservation import (
    InMemoryReservationStore,
    Reservation,
)
from controlplane.domain.config_security.incremental_cost import IncrementalCostRecord
from controlplane.domain.config_security.status_graph import ExternalAccountStatus
from controlplane.infrastructure.db.migration_runner import MigrationRunner
from controlplane.infrastructure.db.storage_meta import PostgresStorageMetaRepository
from controlplane.infrastructure.db.uow import TransactionManager
from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore
from controlplane.infrastructure.security.oauth_drive_token import DriveAccessTokenBroker
from controlplane.infrastructure.security.oauth_google_loopback import DriveOAuthConfig
from controlplane.infrastructure.storage.drive_object_store import DriveObjectStore
from creative.adapters import memory as d_memory
from creative.adapters.fake_ai import FakeAIAdapter, FakeProviderRoute
from creative.adapters.real_ai_invocation import RoutedAIInvocation
from creative.adapters.real_route_executor import (
    InvocationPayloadStore,
    NineRouterExecutor,
)
from creative.persistence.uow import PostgresCreativeUnitOfWork
from ingestion.application.production_deps import ResolveDepsFactory
from ingestion.infrastructure import memory as b_memory
from ingestion.persistence.uow import PostgresIngestionUnitOfWork
from render.adapters import memory as f_memory
from render.adapters.fake_renderer import FakeRenderer
from render.adapters.real_ffmpeg_renderer import RealFfmpegRenderer
from render.adapters.real_ffprobe_probe import RealFfprobeProbe
from render.persistence.unit_of_work import PostgresRenderUnitOfWork
from source_ingestion.adapters import memory as a_memory
from source_ingestion.adapters.real_feed_source import RealFeedSource
from source_ingestion.adapters.real_http_transport import RealHttpTransport
from source_ingestion.adapters.real_media_fetch import RealMediaFetcher
from source_ingestion.persistence.unit_of_work import (
    PostgresSourceIngestionUnitOfWork,
)
from voice.adapters import memory as e_memory
from voice.adapters.fake_aligner import FakeAligner
from voice.adapters.fake_tts import FakeTtsEngine
from voice.adapters.profile_media_policy import build_image_safety_rules
from voice.adapters.real_ffmpeg_media_tool import RealFfmpegMediaTool
from voice.adapters.real_kokoro_tts import RealKokoroTts
from voice.adapters.real_llm_image_safety import LlmImageSafetyDetector
from voice.adapters.real_whisper_aligner import RealWhisperAligner
from voice.domain.processing import ArtifactRef
from voice.persistence.unit_of_work import PostgresVoiceUnitOfWork

ROOT = Path(__file__).resolve().parents[4]
WIRING = ROOT / 'src' / 'controlplane' / 'api' / 'wiring'
PROFILE_PATH = ROOT / 'tools' / 'launcher' / 'prod' / 'profile.json'
MIGRATIONS_DIR = ROOT / 'src' / 'controlplane' / 'infrastructure' / 'db' / 'migrations'
EXPECTED_BUILDERS = {
    'collection': 'build_collection_services',
    'config_security': 'build_config_security_services',
    'creative': 'build_creative_services',
    'ingestion': 'build_ingestion_services',
    'render': 'build_render_services',
    'storage': 'build_storage_services',
    'voice': 'build_voice_services',
}
SUBSYSTEMS = {'source_ingestion', 'creative', 'voice', 'render', 'ingestion', 'catalog'}
OWN_SUBSYSTEM = {
    'collection': 'source_ingestion',
    'creative': 'creative',
    'voice': 'voice',
    'render': 'render',
    'ingestion': 'ingestion',
}

# Mô-đun ghép nhiều phân hệ theo kế hoạch đã duyệt, không phải mô-đun đấu nối của một phân hệ:
# completion.py (CP-5-COMPLETION), workflow.py (CP-6-WORKFLOW, docs/implementation/convergence/plan.md dòng 257, BL-CV-10)
# và production.py (ADAPT-PROD, docs/implementation/adapt/slices.md, mục ADAPT-PROD).
COMPOSITION_MODULES = {'completion', 'workflow', 'production'}


def wiring(name: str):
    return importlib.import_module('controlplane.api.wiring.' + name)


@pytest.fixture
def database():
    dsn = os.environ.get('M2_TEST_PG_DSN', '')
    if not dsn:
        pytest.fail('BLOCKED_EXTERNAL: thiếu M2_TEST_PG_DSN', pytrace=False)
    name = 'adapt_wire_' + uuid.uuid4().hex[:8]
    admin = psycopg.connect(dsn, autocommit=True)
    try:
        assert 'PostgreSQL 18.6' in admin.execute('SELECT version()').fetchone()[0]
        admin.execute(f'CREATE DATABASE {name}')
        new_dsn = dsn.rsplit('/', 1)[0] + '/' + name
        MigrationRunner(new_dsn, MIGRATIONS_DIR, is_test_env=True, expected_database_name=name).migrate_up()
        workspace_id = str(uuid.uuid4())
        with psycopg.connect(new_dsn, autocommit=True) as seed:
            seed.execute(
                'INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES (%s, %s, %s)',
                (workspace_id, 'w', 'ACTIVE'),
            )
        yield (new_dsn, workspace_id)
    finally:
        try:
            admin.execute(f'DROP DATABASE IF EXISTS {name} WITH (FORCE)')
        finally:
            admin.close()


@pytest.fixture
def manager(database):
    mgr = TransactionManager(database[0])
    try:
        yield mgr
    finally:
        mgr.close()


def builder_inventory(wiring_dir: Path) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in sorted(wiring_dir.glob('*.py')):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        names = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and re.fullmatch(r'build_.*_services', node.name)
        ]
        if names:
            found[path.stem] = names
    return found


def inventory_errors(found: dict[str, list[str]]) -> list[tuple[str, object]]:
    errors: list[tuple[str, object]] = []
    per_subsystem = {k: v for k, v in found.items() if k not in COMPOSITION_MODULES}
    if per_subsystem != {k: [v] for k, v in EXPECTED_BUILDERS.items()}:
        errors.append(('inventory', per_subsystem))
    for module in sorted(COMPOSITION_MODULES & found.keys()):
        if found[module] != ['build_' + module + '_services']:
            errors.append((module, found[module]))
    return errors


def test_wiring_builder_inventory():
    assert inventory_errors(builder_inventory(WIRING)) == []


def test_wiring_sources_have_no_forbidden_text():
    text = ' '.join(f.read_text(encoding='utf-8') for f in sorted(WIRING.glob('*.py')))
    assert 'real_' in text
    forbidden = [
        'application.test_driver',
        'from src.',
        'import psycopg',
        'INSERT INTO',
        'PostgresIdempotencyRepository',
        'PostgresOutboxRepository',
        'os.environ',
        'getenv',
        'mock-9router',
        'sqlite3',
        'import os',
    ]
    bad = [s for s in forbidden if s in text]
    assert bad == []


def cross_imports(wiring_dir: Path) -> list[tuple[str, str]]:
    bad: list[tuple[str, str]] = []
    for path in sorted(wiring_dir.glob('*.py')):
        if path.stem in COMPOSITION_MODULES:
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
            for mod in modules:
                prefix = mod.split('.')[0]
                if prefix in SUBSYSTEMS and prefix != OWN_SUBSYSTEM.get(path.stem):
                    bad.append((path.name, mod))
    return bad


def test_wiring_modules_do_not_cross_import_subsystems():
    assert cross_imports(WIRING) == []


def write_wiring_module(directory: Path, name: str, source: str) -> None:
    (directory / (name + '.py')).write_text(source, encoding='utf-8')


def write_expected_wiring(directory: Path) -> None:
    for module, builder in EXPECTED_BUILDERS.items():
        write_wiring_module(directory, module, 'def ' + builder + '():\n    return None\n')


def test_cross_imports_reports_subsystem_module_importing_other_subsystem(tmp_path):
    write_wiring_module(tmp_path, 'voice', 'from creative.adapters import memory\n')
    assert cross_imports(tmp_path) == [('voice.py', 'creative.adapters')]


def test_cross_imports_allows_own_subsystem_import(tmp_path):
    write_wiring_module(tmp_path, 'voice', 'from voice.adapters import memory\n')
    assert cross_imports(tmp_path) == []


def test_cross_imports_ignores_composition_modules(tmp_path):
    source = (
        'from creative.worker.activity_handler import handle_activity\n'
        'from ingestion.application.activity_handler import handle_resolve_activity\n'
        'from render.worker.activity_handler import handle_activity as render_activity\n'
        'from source_ingestion.worker.activity_handler import handle_collect_source_activity\n'
        'from voice.worker.activity_handler import handle_activity as voice_activity\n'
    )
    for module in sorted(COMPOSITION_MODULES):
        write_wiring_module(tmp_path, module, source)
    assert cross_imports(tmp_path) == []


def test_inventory_accepts_expected_builders_and_workflow_builder(tmp_path):
    write_expected_wiring(tmp_path)
    assert inventory_errors(builder_inventory(tmp_path)) == []
    write_wiring_module(tmp_path, 'workflow', 'def build_workflow_services():\n    return None\n')
    assert inventory_errors(builder_inventory(tmp_path)) == []


def test_inventory_rejects_unknown_module_with_builder(tmp_path):
    write_expected_wiring(tmp_path)
    write_wiring_module(tmp_path, 'x', 'def build_x_services():\n    return None\n')
    assert inventory_errors(builder_inventory(tmp_path)) != []


def test_inventory_rejects_composition_module_with_wrong_builder_name(tmp_path):
    write_expected_wiring(tmp_path)
    write_wiring_module(tmp_path, 'workflow', 'def build_other_services():\n    return None\n')
    assert inventory_errors(builder_inventory(tmp_path)) != []


def leaf_names(node, prefix=''):
    for k, child in node.items():
        if isinstance(child, dict) and 'value' in child:
            yield prefix + k
        elif isinstance(child, dict):
            yield from leaf_names(child, prefix + k + '.')


LEAVES = list(leaf_names(json.loads(PROFILE_PATH.read_text(encoding='utf-8'))))


def load_data():
    return json.loads(PROFILE_PATH.read_text(encoding='utf-8'))


def node_at(data, dotted):
    cur = data
    for part in dotted.split('.'):
        cur = cur[part]
    return cur


def remove_leaf(data, dotted):
    parts = dotted.split('.')
    parent = data
    for part in parts[:-1]:
        parent = parent[part]
    del parent[parts[-1]]


def set_leaf(data, dotted, value):
    node_at(data, dotted)['value'] = value


def write_profile(tmp_path, data):
    p = tmp_path / 'profile.json'
    p.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    return p


def test_profile_loads_typed_values():
    pp = wiring('production_profile')
    p = pp.load_production_profile(PROFILE_PATH)
    assert p.profile_name == 'production'
    assert p.revision == 1
    assert p.budget.monthly_limit == Decimal('50')
    assert p.budget.hard_stop is True
    assert p.budget.window_timezone == 'Asia/Ho_Chi_Minh'
    assert p.collection.feed.max_body_bytes == 5242880
    assert p.collection.image.content_types == ('image/jpeg', 'image/png', 'image/webp')
    assert p.collection.user_agent == 'AIAutoVideoCreator/1.0'
    assert p.ai.route_model_refs['script'] == 'ag/gemini-3.8-flash-high'
    assert p.ai.retry.max_attempts == 3
    assert p.ai.reservation_ttl_seconds == 300
    assert p.voice.voice == 'af_heart'
    assert p.voice.sample_rate_hz == 24000
    assert p.aligner.model == 'small.en'
    assert p.render.timeout_seconds == 900
    assert p.drive.chunk_bytes == 8388608
    assert p.credential_max_ttl_seconds == 3300
    assert len(pp.REQUIRED_PARAMETERS) == 78
    assert set(pp.REQUIRED_PARAMETERS) == set(LEAVES)
    assert set(p.parameters) == set(LEAVES)


@pytest.mark.parametrize('name', LEAVES)
def test_missing_parameter_names_it(name, tmp_path):
    pp = wiring('production_profile')
    data = load_data()
    remove_leaf(data, name)
    with pytest.raises(pp.ProductionProfileError) as info:
        pp.load_production_profile(write_profile(tmp_path, data))
    assert info.value.parameter == name and name in str(info.value)


@pytest.mark.parametrize(
    'name,key,expected',
    [
        ('collection.fetch_policy.feed', 'max_body_bytes', 'collection.fetch_policy.feed.max_body_bytes'),
        ('voice.engine', 'voice', 'voice.engine.voice'),
        ('ai.retry', 'max_attempts', 'ai.retry.max_attempts'),
    ],
)
def test_missing_nested_key_names_it(name, key, expected, tmp_path):
    pp = wiring('production_profile')
    data = load_data()
    del node_at(data, name)['value'][key]
    with pytest.raises(pp.ProductionProfileError) as info:
        pp.load_production_profile(write_profile(tmp_path, data))
    assert info.value.parameter == expected


def test_invalid_and_null_values_are_rejected(tmp_path):
    pp = wiring('production_profile')
    cases = [
        ('budget.hard_stop', 'yes', 'budget.hard_stop'),
        ('collection.user_agent', None, 'collection.user_agent'),
        ('meta.profile_name', 'test', 'meta.profile_name'),
    ]
    for param, bad_val, expected_param in cases:
        data = load_data()
        set_leaf(data, param, bad_val)
        with pytest.raises(pp.ProductionProfileError) as info:
            pp.load_production_profile(write_profile(tmp_path, data))
        assert info.value.parameter == expected_param


def test_wiring_config_rules():
    pp = wiring('production_profile')
    valid_id = str(uuid.uuid4())
    cfg = pp.WiringConfig(mode='test', workspace_id=valid_id, profile=None, runtime=None)
    assert cfg.mode == 'test'

    with pytest.raises(pp.ProductionProfileError) as info:
        pp.WiringConfig(mode='production', workspace_id=valid_id, profile=None, runtime=None)
    assert info.value.parameter == 'profile'

    with pytest.raises(pp.ProductionProfileError) as info:
        pp.WiringConfig(mode='other', workspace_id=valid_id, profile=None, runtime=None)
    assert info.value.parameter == 'mode'

    with pytest.raises(pp.ProductionProfileError) as info:
        pp.WiringConfig(mode='test', workspace_id='x', profile=None, runtime=None)
    assert info.value.parameter == 'workspace_id'


def make_runtime(tmp_path):
    pp = wiring('production_profile')
    return pp.ProductionRuntime(
        ffmpeg_path=tmp_path / 'bin' / 'ffmpeg.exe',
        ffprobe_path=tmp_path / 'bin' / 'ffprobe.exe',
        runtime_lock_path=tmp_path / 'runtime.lock.json',
        weights_dir=tmp_path / 'weights',
        weights_lock_path=tmp_path / 'model-weights.lock.json',
        whisper_model_dir=tmp_path / 'whisper',
        staging_root=tmp_path / 'staging',
        secret_store_root=tmp_path / 'vault',
        oauth_client_secrets_path=tmp_path / 'client.json',
        oauth_consent_timeout_seconds=300,
        route_cost_per_request=Decimal('0'),
        tokenization={
            'revision': 'adapt-wire-test',
            'unicode_form': 'NFC',
            'casefold': True,
            'edge_strip_categories': ('P',),
            'gap_tolerance_ms': 500,
            'min_confidence': 0.5,
        },
        drive_placement={
            'original': 'folder-original',
            'reusable': 'folder-reusable',
            'output': 'folder-output',
        },
        drive_fallback_parent_id='folder-root',
        route_catalog=SimpleNamespace(candidates=lambda workspace_id, ai_role: ()),
        provider_credentials=SimpleNamespace(acquire=lambda method, account: None),
        vision_route=SimpleNamespace(invoke_vision=lambda *args, **kwargs: ''),
        artifact_source=SimpleNamespace(open=lambda artifact_version_id: None),
        drive_token_broker=SimpleNamespace(acquire=lambda method, account: None),
        gpu_lease=SimpleNamespace(),
    )


def prod_config(tmp_path, workspace_id):
    pp = wiring('production_profile')
    return pp.WiringConfig(
        mode='production',
        workspace_id=workspace_id,
        profile=pp.load_production_profile(PROFILE_PATH),
        runtime=make_runtime(tmp_path),
    )


def make_test_config(workspace_id):
    pp = wiring('production_profile')
    return pp.WiringConfig(mode='test', workspace_id=workspace_id, profile=None, runtime=None)


def test_collection_production_uses_real_adapters(manager, database, tmp_path):
    s = wiring('collection').build_collection_services(manager, prod_config(tmp_path, database[1]))
    assert s.mode == 'production'
    assert isinstance(s.transport, RealHttpTransport)
    assert set(s.source_adapters) == {'rss_feed', 'atom_feed'}
    assert all(isinstance(v, RealFeedSource) for v in s.source_adapters.values())
    assert isinstance(s.media_fetcher, RealMediaFetcher)
    assert isinstance(s.uow_factory(), PostgresSourceIngestionUnitOfWork)


def test_collection_test_profile_uses_in_memory(manager, database):
    s = wiring('collection').build_collection_services(manager, make_test_config(database[1]))
    assert isinstance(s.uow_factory(), a_memory.InMemoryUnitOfWork)
    assert s.source_adapters == {}
    assert s.transport is None
    assert s.media_fetcher is None


def test_creative_production_uses_real_adapters(manager, database, tmp_path):
    s = wiring('creative').build_creative_services(manager, prod_config(tmp_path, database[1]))
    assert isinstance(s.ai, RoutedAIInvocation)
    assert isinstance(s.executor, NineRouterExecutor)
    assert isinstance(s.route, wiring('creative').RoutedProviderRoute)
    assert isinstance(s.uow_factory(), PostgresCreativeUnitOfWork)
    assert isinstance(s.payload_store, InvocationPayloadStore)


def test_creative_test_profile_uses_fakes(manager, database):
    s = wiring('creative').build_creative_services(manager, make_test_config(database[1]))
    assert isinstance(s.ai, FakeAIAdapter)
    assert isinstance(s.route, FakeProviderRoute)
    assert isinstance(s.uow_factory(), d_memory.InMemoryUnitOfWork)
    assert s.executor is None


def test_voice_production_uses_real_adapters(manager, database, tmp_path):
    cfg = prod_config(tmp_path, database[1])
    s = wiring('voice').build_voice_services(manager, cfg)
    assert isinstance(s.tts, RealKokoroTts)
    assert isinstance(s.aligner, RealWhisperAligner)
    assert isinstance(s.media_tool, RealFfmpegMediaTool)
    assert isinstance(s.uow_factory(), PostgresVoiceUnitOfWork)
    detector = s.image_safety_detector_factory(ArtifactRef('image.png', 'a' * 64))
    assert isinstance(detector, LlmImageSafetyDetector)
    profile, _runtime = cfg.production_parts()
    floor = build_image_safety_rules(profile.parameters).uncertain_min
    assert floor == 0.3 and detector.uncertain_min == floor


def test_voice_test_profile_uses_fakes(manager, database):
    s = wiring('voice').build_voice_services(manager, make_test_config(database[1]))
    assert isinstance(s.tts, FakeTtsEngine)
    assert isinstance(s.aligner, FakeAligner)
    assert isinstance(s.uow_factory(), e_memory.InMemoryUnitOfWork)
    assert s.media_tool is None
    assert s.image_safety_detector_factory is None


@pytest.mark.parametrize(
    'key',
    ['revision', 'unicode_form', 'casefold', 'edge_strip_categories', 'gap_tolerance_ms', 'min_confidence'],
)
def test_voice_missing_tokenization_key_names_it(key, manager, database, tmp_path):
    cfg = prod_config(tmp_path, database[1])
    runtime = dataclasses.replace(
        cfg.runtime,
        tokenization={k: v for k, v in cfg.runtime.tokenization.items() if k != key},
    )
    cfg2 = dataclasses.replace(cfg, runtime=runtime)
    with pytest.raises(wiring('production_profile').ProductionProfileError) as info:
        wiring('voice').build_voice_services(manager, cfg2)
    assert info.value.parameter == 'runtime.tokenization.' + key


def test_render_production_uses_real_adapters(manager, database, tmp_path):
    s = wiring('render').build_render_services(manager, prod_config(tmp_path, database[1]))
    assert isinstance(s.renderer, RealFfmpegRenderer)
    assert isinstance(s.probe, RealFfprobeProbe)
    assert isinstance(s.uow_factory(), PostgresRenderUnitOfWork)


def test_render_test_profile_uses_fakes(manager, database):
    s = wiring('render').build_render_services(manager, make_test_config(database[1]))
    assert isinstance(s.renderer, FakeRenderer)
    assert isinstance(s.uow_factory(), f_memory.InMemoryUnitOfWork)
    assert s.probe is None


def test_storage_production_uses_drive_store(manager, database, tmp_path):
    s = wiring('storage').build_storage_services(manager, prod_config(tmp_path, database[1]))
    assert isinstance(s.cloud_store, DriveObjectStore)
    with manager.borrow_connection() as connection:
        assert isinstance(s.meta_repository_factory(connection), PostgresStorageMetaRepository)


def test_storage_test_profile_uses_in_memory_cloud_store(manager, database):
    s = wiring('storage').build_storage_services(manager, make_test_config(database[1]))
    assert isinstance(s.cloud_store, wiring('storage').InMemoryCloudObjectStore)
    oid = s.cloud_store.reserve_object_id('output')
    assert isinstance(oid, str) and oid


def test_config_security_production_uses_real_adapters(manager, database, tmp_path):
    s = wiring('config_security').build_config_security_services(manager, prod_config(tmp_path, database[1]))
    assert isinstance(s.secret_store, DpapiSecretStore)
    assert isinstance(s.token_broker, DriveAccessTokenBroker)
    assert isinstance(s.oauth_config, DriveOAuthConfig)
    assert s.oauth_config.consent_timeout_seconds == 300

    now = datetime.now(timezone.utc)
    res = Reservation('res-1', 'prov/proj/model', 3, now + timedelta(minutes=5), 'op-1', 'KNOWN')
    s.reservation_store.add(res)
    assert s.reservation_store.get_by_operation('op-1') == res

    rec = IncrementalCostRecord(
        record_id='c-1',
        provider='prov',
        service='model',
        operation_ref='op-c-1',
        job_ref='job-1',
        batch_ref=None,
        quantity=Decimal('2'),
        unit='request',
        estimated_cost=Decimal('0.123456'),
        actual_cost=Decimal('0.120000'),
        currency='USD',
        source='routed_invocation',
        occurred_at=now.isoformat(),
        cost_category='api_paid',
    )
    s.cost_ledger.append(database[1], rec)
    assert tuple(s.cost_ledger.records(database[1], now - timedelta(days=1), now + timedelta(days=1))) == (rec,)

    assert s.account_status.account_status('drive-primary') is ExternalAccountStatus.REVOKED
    with psycopg.connect(database[0], autocommit=True) as conn:
        conn.execute(
            'INSERT INTO controlplane.cp_external_accounts (workspace_id, external_account_id, provider, account_label, status) '
            'VALUES (%s, %s, %s, %s, %s)',
            (database[1], 'drive-primary', 'google', 'drive', 'ENABLED'),
        )
    assert s.account_status.account_status('drive-primary') is ExternalAccountStatus.ENABLED


def test_config_security_test_profile_uses_in_memory(manager, database):
    s = wiring('config_security').build_config_security_services(manager, make_test_config(database[1]))
    assert isinstance(s.secret_store, wiring('config_security').InMemorySecretStore)
    assert isinstance(s.reservation_store, InMemoryReservationStore)
    assert s.token_broker is None
    assert s.oauth_config is None
    assert s.secret_store.current_version('ref') is None


def test_ingestion_production_uses_postgres_adapters(manager, database, tmp_path):
    s = wiring('ingestion').build_ingestion_services(manager, prod_config(tmp_path, database[1]))
    assert s.mode == 'production'
    assert isinstance(s.uow_factory(), PostgresIngestionUnitOfWork)
    assert isinstance(s.resolve_factory, ResolveDepsFactory)
    handlers = wiring('ingestion').ingestion_activity_handlers(s, lambda: datetime.now(timezone.utc))
    assert set(handlers) == {'ResolveCollectedDocument'}


def test_ingestion_test_profile_uses_in_memory(manager, database):
    s = wiring('ingestion').build_ingestion_services(manager, make_test_config(database[1]))
    assert isinstance(s.uow_factory(), b_memory.InMemoryUnitOfWork)
    assert s.resolve_factory is None
