"""H-03: danh mục event kind và kế hoạch resync của luồng SSE (CT-API-008, CT-EVT-002).

coveredIds: CT-API-008, CT-EVT-002
"""
import ast
import pathlib
import re

import pytest

from controlplane.application.sse.event_catalog import (
    ALL_SNAPSHOT_RESOURCES,
    BASE_STREAM_EVENT_KINDS,
    EVENT_KIND_PATTERN,
    SNAPSHOT_RESOURCES,
    StreamKindRegistry,
    default_registry,
    is_valid_event_kind,
    resync_targets,
    snapshot_resources_for,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'controlplane' / 'application' / 'sse' / 'event_catalog.py'
CLIENT_PATH = ROOT / 'src' / 'controlplane' / 'ui' / 'src' / 'api' / 'client.ts'
EXPECTED_BASE = (
    'operation.accepted',
    'operation.running',
    'operation.succeeded',
    'operation.failed',
    'operation.changed',
    'production_batch.start_accepted',
    'job.created',
    'job.running',
    'job.completed',
    'job.failed',
)
EXPECTED_MODULE = (
    'source.registered', 'source.metadata_updated', 'source.removed', 'source.restored', 'source.candidate_discovered', 'source.candidate_resolved', 'source.collection_run_started', 'source.collected_document_available', 'source.collection_run_completed', 'source.collection_run_failed',
    'ingestion.article_revision_accepted', 'ingestion.duplicate_document_resolved', 'ingestion.event_link_resolved', 'ingestion.event_update_accepted',
    'creative.production_snapshot_committed', 'creative.story_angles_generated', 'creative.script_version_created', 'creative.production_plan_created', 'creative.variant_validated', 'creative.output_metadata_created',
    'voice.image_safety_assessed', 'voice.media_processing_completed', 'voice.voice_ready', 'voice.word_timing_ready',
    'render.render_completed', 'render.output_quality_checked',
    'orchestration.batch_started', 'orchestration.job_allocated', 'orchestration.stage_state_changed', 'orchestration.job_waiting', 'orchestration.job_failed', 'orchestration.video_completed', 'orchestration.batch_target_reached', 'orchestration.batch_exhausted',
    'storage.artifact_location_verified', 'storage.cleanup_completed',
    'config.revision_published', 'config.credential_changed',
)
EXPECTED_PREFIXES = {'operation', 'production_batch', 'job', 'source', 'ingestion', 'creative', 'voice', 'render', 'orchestration', 'storage', 'config'}
EXPECTED_SNAPSHOT_RESOURCES = {
    'operation': ('operations',),
    'production_batch': ('batches',),
    'job': ('jobs',),
    'source': ('sources',),
    'ingestion': ('articles', 'events'),
    'orchestration': ('batches', 'jobs', 'stage-runs'),
}
EXPECTED_ALL_RESOURCES = ('operations', 'batches', 'jobs', 'sources', 'articles', 'events', 'media', 'hooks', 'stage-runs', 'sessions', 'logs')


def _module_tree():
    return ast.parse(MODULE_PATH.read_text(encoding='utf-8'))


def assert_rejected(registry, prefix, kinds, code):
    with pytest.raises(ValueError) as excinfo:
        registry.register(prefix, kinds)
    assert excinfo.value.args == (code,)


def test_pattern_constant_is_exact():
    assert EVENT_KIND_PATTERN == r'[A-Za-z0-9_.-]+'


@pytest.mark.parametrize('kind', ['job.created', 'source.registered', 'production_batch.start_accepted', 'a', 'A-b_c.9'])
def test_valid_kinds_are_accepted(kind):
    assert is_valid_event_kind(kind) is True


@pytest.mark.parametrize('kind', ['', ' ', 'job created', 'job.created\n', '\njob.created', 'job.created\r\nevent: x', 'job.created\t', 'job.créé', 'job.created١', 'job/created', 'job:created', None, 123, b'job.created'])
def test_invalid_kinds_are_rejected(kind):
    assert is_valid_event_kind(kind) is False


def test_validator_uses_fullmatch_with_re_ascii():
    tree = _module_tree()
    called = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert 'fullmatch' in called
    assert 'ASCII' in attrs
    assert not {'match', 'search'} & called


def test_module_imports_only_stdlib():
    names = set()
    for node in ast.walk(_module_tree()):
        if isinstance(node, ast.Import):
            names |= {alias.name.split('.')[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add((node.module or '').split('.')[0])
    assert names <= {'__future__', 're', 'types', 'collections', 'typing'}


def test_base_kinds_are_exactly_the_ten_expected():
    assert BASE_STREAM_EVENT_KINDS[:10] == EXPECTED_BASE
    assert len(set(BASE_STREAM_EVENT_KINDS[:10])) == 10
    assert all(is_valid_event_kind(kind) for kind in BASE_STREAM_EVENT_KINDS)


def test_stream_kinds_are_base_followed_by_38_module_kinds():
    assert len(EXPECTED_MODULE) == 38
    assert BASE_STREAM_EVENT_KINDS == EXPECTED_BASE + EXPECTED_MODULE
    assert len(BASE_STREAM_EVENT_KINDS) == len(set(BASE_STREAM_EVENT_KINDS)) == 48
    assert {kind.partition('.')[0] for kind in EXPECTED_MODULE} == EXPECTED_PREFIXES - {'operation', 'production_batch', 'job'}


def test_default_registry_matches_base_set():
    registry = default_registry()
    assert set(registry.all_kinds()) == set(BASE_STREAM_EVENT_KINDS)
    assert len(registry.all_kinds()) == 48


def test_default_registry_has_exactly_three_prefixes():
    prefixes = {kind.partition('.')[0] for kind in default_registry().all_kinds()}
    assert prefixes == EXPECTED_PREFIXES
    assert len(prefixes) == 11


def test_default_registry_kind_count_per_prefix():
    counts = {}
    for kind in default_registry().all_kinds():
        counts[kind.partition('.')[0]] = counts.get(kind.partition('.')[0], 0) + 1
    assert counts == {'operation': 5, 'production_batch': 1, 'job': 4, 'source': 10, 'ingestion': 4, 'creative': 6, 'voice': 4, 'render': 2, 'orchestration': 8, 'storage': 2, 'config': 2}


def test_default_registry_returns_independent_instances():
    first = default_registry()
    first.register('source', ['source.zz_probe'])
    assert 'source.zz_probe' not in default_registry().all_kinds()


def test_client_event_kinds_are_subset_of_catalog():
    text = CLIENT_PATH.read_text(encoding='utf-8')
    match = re.search(r'const eventKinds = \[(.*?)\];', text, re.S)
    if match is not None:
        kinds = re.findall(r"'([^']+)'", match.group(1))
        assert kinds
        assert set(kinds) <= set(default_registry().all_kinds())
    else:
        assert 'STREAM_EVENT_KINDS' in text
        assert re.search(r"import\s*\{[^}]*\bSTREAM_EVENT_KINDS\b[^}]*\}\s*from\s*'[^']*streamEventKinds(\.ts)?'", text)


def test_new_module_kind_under_its_own_prefix_is_accepted():
    registry = default_registry()
    assert 'source.registered' in registry.all_kinds()
    registry.register('source', ['source.zz_probe'])
    assert 'source.zz_probe' in registry.all_kinds()
    assert len(registry.all_kinds()) == 49


def test_kind_outside_prefix_is_rejected():
    registry = default_registry()
    assert_rejected(registry, 'job', ['source.x'], 'invalid_event_kind')
    assert 'source.x' not in registry.all_kinds()


def test_default_registry_rejects_source_x_under_job_prefix_with_invalid_event_kind():
    registry = default_registry()
    before = registry.all_kinds()
    assert len(before) == 48
    assert_rejected(registry, 'job', ['source.x'], 'invalid_event_kind')
    assert 'source.x' not in registry.all_kinds()
    assert registry.all_kinds() == before


@pytest.mark.parametrize('kind', ['job.cre ated', 'job.created\n', 'job.x\r\nevent: injected', '', 'job.', 'job', 'job.créé'.replace('créé', 'é')])
def test_invalid_kind_for_prefix_is_rejected(kind):
    registry = StreamKindRegistry()
    assert_rejected(registry, 'job', [kind], 'invalid_event_kind')
    assert registry.all_kinds() == ()


@pytest.mark.parametrize('prefix', ['', 'a b', 'job.', 'a.b', 'job\n'])
def test_invalid_prefix_is_rejected(prefix):
    assert_rejected(StreamKindRegistry(), prefix, ['job.created'], 'invalid_event_kind')


def test_bare_string_instead_of_kind_list_is_rejected():
    registry = StreamKindRegistry()
    assert_rejected(registry, 'job', 'job.created', 'invalid_event_kind')
    assert registry.all_kinds() == ()


def test_reregistering_same_prefix_same_kind_is_idempotent():
    registry = default_registry()
    before = registry.all_kinds()
    registry.register('job', ['job.created', 'job.failed'])
    registry.register('job', ['job.created'])
    assert registry.all_kinds() == before


@pytest.mark.parametrize('prefix', ['operation', 'source'])
def test_kind_owned_by_other_prefix_is_rejected(prefix):
    registry = default_registry()
    before = registry.all_kinds()
    assert_rejected(registry, prefix, ['job.created'], 'kind_owned_by_other_prefix')
    assert registry.all_kinds() == before


def test_failed_register_is_atomic():
    registry = default_registry()
    before = registry.all_kinds()
    assert_rejected(registry, 'source', ['source.ok', 'source.bad\n'], 'invalid_event_kind')
    assert_rejected(registry, 'source', ['source.ok', 'job.created'], 'kind_owned_by_other_prefix')
    assert registry.all_kinds() == before


def test_all_kinds_is_sorted_and_independent_of_registration_order():
    first = StreamKindRegistry()
    first.register('x', ['x.b', 'x.a'])
    second = StreamKindRegistry()
    second.register('x', ['x.a'])
    second.register('x', ['x.b', 'x.a'])
    assert first.all_kinds() == second.all_kinds() == ('x.a', 'x.b')
    assert isinstance(first.all_kinds(), tuple)
    assert list(default_registry().all_kinds()) == sorted(BASE_STREAM_EVENT_KINDS)


def test_snapshot_resources_cover_exactly_the_base_prefixes():
    assert dict(SNAPSHOT_RESOURCES) == EXPECTED_SNAPSHOT_RESOURCES
    assert len(SNAPSHOT_RESOURCES) == 6
    assert ALL_SNAPSHOT_RESOURCES == EXPECTED_ALL_RESOURCES
    assert len(ALL_SNAPSHOT_RESOURCES) == 11
    assert ALL_SNAPSHOT_RESOURCES[:3] == ('operations', 'batches', 'jobs')
    union = {r for rs in SNAPSHOT_RESOURCES.values() for r in rs}
    assert union <= set(ALL_SNAPSHOT_RESOURCES)
    assert set(ALL_SNAPSHOT_RESOURCES) - union == {'media', 'hooks', 'sessions', 'logs'}
    assert set(SNAPSHOT_RESOURCES) <= {kind.partition('.')[0] for kind in BASE_STREAM_EVENT_KINDS}


def test_snapshot_resources_is_read_only():
    with pytest.raises(TypeError):
        SNAPSHOT_RESOURCES['x'] = ('xs',)


@pytest.mark.parametrize('resource_type, expected', [
    ('operation', ('operations',)),
    ('production_batch', ('batches',)),
    ('job', ('jobs',)),
])
def test_known_resource_type_maps_to_one_resource(resource_type, expected):
    assert snapshot_resources_for(resource_type) == expected


@pytest.mark.parametrize('resource_type, expected', [
    ('source', ('sources',)),
    ('ingestion', ('articles', 'events')),
    ('orchestration', ('batches', 'jobs', 'stage-runs')),
    ('voice', EXPECTED_ALL_RESOURCES),
    ('config', EXPECTED_ALL_RESOURCES),
])
def test_module_resource_type_maps_to_table_or_falls_back_to_all(resource_type, expected):
    assert snapshot_resources_for(resource_type) == expected


@pytest.mark.parametrize('resource_type', ['zzz', '', 'Job', ' job', None, 5, ['job']])
def test_unknown_resource_type_returns_all_resources(resource_type):
    assert snapshot_resources_for(resource_type) == ALL_SNAPSHOT_RESOURCES


def test_resync_targets_unknown_type_expands_to_all_without_duplicates():
    result = resync_targets(['job', 'zzz'])
    assert result == ('jobs', 'operations', 'batches', 'sources', 'articles', 'events', 'media', 'hooks', 'stage-runs', 'sessions', 'logs')
    assert len(result) == len(set(result)) == 11
    assert set(result) == set(ALL_SNAPSHOT_RESOURCES)


def test_resync_targets_known_type_is_narrow():
    assert resync_targets(['job']) == ('jobs',)
    assert resync_targets(['zzz']) == ALL_SNAPSHOT_RESOURCES


def test_resync_targets_merge_in_first_seen_order_without_duplicates():
    assert resync_targets(['job', 'job', 'operation']) == ('jobs', 'operations')
    assert resync_targets(['operation', 'production_batch', 'job']) == ('operations', 'batches', 'jobs')
    assert resync_targets([]) == ()
    assert resync_targets(iter(['job'])) == ('jobs',)
    assert resync_targets('job') == ('jobs',)
