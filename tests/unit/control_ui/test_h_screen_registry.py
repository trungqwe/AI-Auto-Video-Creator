"""H-15: registry màn hình theo milestone và quy tắc trường được sửa (D8-H-05).

coveredIds: QR-UX-008, QR-UX-001, CT-API-010
"""
import pathlib
import re
import unicodedata

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
REGISTRY_PATH = ROOT / 'src' / 'controlplane' / 'ui' / 'src' / 'features' / 'screens' / 'screenRegistry.ts'
CONTROL_PATH = ROOT / 'src' / 'controlplane' / 'api' / 'routes' / 'control.py'
ROUTE_CATALOG_PATH = ROOT / 'src' / 'controlplane' / 'application' / 'control_api' / 'route_catalog.py'

MILESTONE_OF = {
    'operations': 'M2', 'batches': 'M2', 'jobs': 'M2', 'configs': 'M2',
    'sources': 'M3', 'articles': 'M3', 'events': 'M3',
    'media': 'M4', 'hooks': 'M4', 'artifacts': 'M4',
    'snapshots': 'M5', 'story-angles': 'M5', 'scripts': 'M5',
    'stage-runs': 'M6',
    'sessions': 'M7', 'logs': 'M7', 'accounts': 'M7', 'cost': 'M7',
}
MODULE_OF = {
    'operations': 'G', 'batches': 'G', 'jobs': 'G', 'configs': 'J',
    'sources': 'A', 'articles': 'B', 'events': 'B',
    'media': 'C', 'hooks': 'C', 'artifacts': 'I',
    'snapshots': 'D', 'story-angles': 'D', 'scripts': 'D',
    'stage-runs': 'G',
    'sessions': 'G', 'logs': 'G', 'accounts': 'J', 'cost': 'J',
}
AVAILABLE_IDS = ('operations', 'batches', 'jobs', 'configs', 'sources', 'stage-runs')
PENDING_IDS = (
    'articles', 'events', 'media', 'hooks', 'artifacts', 'snapshots',
    'story-angles', 'scripts', 'sessions', 'logs', 'accounts', 'cost',
)
READ_ONLY_IDS = ('articles', 'events', 'snapshots', 'story-angles', 'scripts')
REVISION_COLUMN_IDS = ('sources', 'media', 'hooks')
EDITABLE_ALLOWLIST = {
    'sources': ('tier', 'topic_tags', 'notes', 'enabled'),
    'hooks': ('tags', 'description', 'enabled', 'notes'),
    'media': ('tags', 'notes'),
}
FORBIDDEN_EDITABLE = (
    'article_body', 'body', 'script', 'script_text',
    'event_relation', 'event_links', 'secret', 'secret_value',
)
FORBIDDEN_ENDPOINTS = ('/scripts', '/event-relations', '/article-body')


def _code(path):
    text = re.sub(r'/\*.*?\*/', '', path.read_text(encoding='utf-8'), flags=re.S)
    return re.sub(r'//[^\n]*', '', text)


def _one(value):
    assert len(value) >= 2 and value[0] == value[-1] == chr(39), value
    return value[1:-1]


def _list(value):
    assert value.startswith('[') and value.endswith(']'), value
    return tuple(_one(item.strip()) for item in value[1:-1].split(',') if item.strip())


def _registry_body(code):
    match = re.search(r'export const SCREEN_REGISTRY: readonly ScreenSpec\[\] = \[(.*?)\n\];', code, re.S)
    assert match is not None
    return match.group(1)


def parse_screens(body):
    screens = []
    for block in re.findall(r'\{[^{}]*\}', body):
        raw = dict(re.findall(r'^[ \t]*(\w+):[ \t]*(.+?),[ \t]*$', block, re.M))
        inner = raw['resourcePath']
        assert inner.startswith('v1(') and inner.endswith(')'), inner
        screens.append({
            'id': _one(raw['id']),
            'titleVi': _one(raw['titleVi']),
            'milestone': _one(raw['milestone']),
            'module': _one(raw['module']),
            'resourcePath': '/v1/' + _one(inner[3:-1]),
            'columns': _list(raw['columns']),
            'editableFields': _list(raw['editableFields']),
            'readOnly': raw['readOnly'] == 'true',
            'backendStatus': _one(raw['backendStatus']),
        })
    return screens


def forbidden_overlap(editable_fields):
    return sorted(set(editable_fields) & set(FORBIDDEN_EDITABLE))


def catalog_listing_prefixes():
    text = ROUTE_CATALOG_PATH.read_text(encoding='utf-8')
    prefixes = set(re.findall(r'ListingResource\(\s*"[a-z0-9-]+",\s*"(/v1/[a-z0-9-]+)"', text))
    assert prefixes, 'route_catalog.py không có ListingResource nào'
    return prefixes


def catalog_metadata_fields():
    text = ROUTE_CATALOG_PATH.read_text(encoding='utf-8')
    found = {}
    for prefix, fields in re.findall(r'MetadataResource\(\s*"[a-z0-9-]+",\s*"(/v1/[a-z0-9-]+)",\s*frozenset\(\{([^}]*)\}\)', text):
        found[prefix] = set(re.findall(r'"([a-z_]+)"', fields))
    assert found, 'route_catalog.py không có MetadataResource nào'
    return found


def router_get_paths():
    text = CONTROL_PATH.read_text(encoding='utf-8')
    prefix = re.search(r'APIRouter\(prefix=.(/[a-z0-9/]*).\)', text)
    assert prefix is not None
    paths = re.findall(r'^@router\.get\(.(/[a-z0-9-]+).\)', text, re.M)
    listings = re.findall(r'^\s*QueryListing\("(/v1/[a-z0-9-]+)"', text, re.M)
    return {prefix.group(1) + path for path in paths} | set(listings) | catalog_listing_prefixes()


SCREENS = parse_screens(_registry_body(_code(REGISTRY_PATH)))
BY_ID = {screen['id']: screen for screen in SCREENS}


def test_registry_has_exactly_18_unique_ids_in_roadmap_order():
    ids = [screen['id'] for screen in SCREENS]
    assert len(ids) == 18, ids
    assert len(set(ids)) == 18, ids
    assert ids == list(MILESTONE_OF), ids


def test_milestone_and_module_match_roadmap_map():
    assert {s['id']: s['milestone'] for s in SCREENS} == MILESTONE_OF
    assert {s['id']: s['module'] for s in SCREENS} == MODULE_OF
    assert {s['milestone'] for s in SCREENS} == {'M2', 'M3', 'M4', 'M5', 'M6', 'M7'}


def test_control_router_exposes_get_routes_for_available_screens():
    assert {'/v1/' + i for i in AVAILABLE_IDS} <= router_get_paths()


def test_available_screens_match_get_routes_of_control_router():
    available = {s['id']: s['resourcePath'] for s in SCREENS if s['backendStatus'] == 'available'}
    assert available == {i: '/v1/' + i for i in AVAILABLE_IDS}
    assert set(available.values()) <= router_get_paths()


def test_every_other_screen_is_pending_module():
    others = [s for s in SCREENS if s['id'] not in AVAILABLE_IDS]
    assert len(others) == 12
    assert all(s['backendStatus'] == 'pending_module' for s in others)


def test_resource_path_is_v1_prefix_plus_id():
    assert SCREENS
    for screen in SCREENS:
        assert screen['resourcePath'] == '/v1/' + screen['id'], screen['id']


def test_v1_helper_returns_v1_prefixed_string():
    code = _code(REGISTRY_PATH)
    helper = re.findall(r'^const v1 = .*$', code, re.M)
    assert helper == ['const v1 = (segment: string): string => `/v1/${segment}`;'], helper


SYNTHETIC_BLOCK = '''
  {
    id: 'fake-scripts',
    titleVi: 'Kịch bản giả',
    milestone: 'M5',
    module: 'D',
    resourcePath: v1('fake-scripts'),
    columns: ['a', 'b', 'c'],
    editableFields: ['script', 'notes'],
    readOnly: false,
    backendStatus: 'pending_module',
  },
'''


def test_each_screen_has_at_least_three_distinct_columns_without_forbidden_names():
    assert SCREENS
    for screen in SCREENS:
        columns = screen['columns']
        assert len(columns) >= 3 and len(set(columns)) == len(columns), screen['id']
        assert not set(columns) & set(FORBIDDEN_EDITABLE), screen['id']


def test_editable_fields_never_intersect_forbidden_set():
    assert SCREENS
    for screen in SCREENS:
        assert forbidden_overlap(screen['editableFields']) == [], screen['id']


def test_forbidden_detector_flags_synthetic_script_block():
    synthetic = parse_screens(SYNTHETIC_BLOCK)
    assert len(synthetic) == 1
    assert forbidden_overlap(synthetic[0]['editableFields']) == ['script']
    assert forbidden_overlap(('tier', 'notes')) == []


@pytest.mark.parametrize('screen_id', READ_ONLY_IDS)
def test_read_only_screens_have_no_editable_fields(screen_id):
    screen = BY_ID.get(screen_id)
    assert screen is not None
    assert screen['readOnly'] is True
    assert screen['editableFields'] == ()


@pytest.mark.parametrize('screen_id,allowed', sorted(EDITABLE_ALLOWLIST.items()))
def test_editable_allowlist_is_exact(screen_id, allowed):
    screen = BY_ID.get(screen_id)
    assert screen is not None
    assert screen['readOnly'] is False
    assert screen['editableFields'] == allowed


def test_read_only_flag_is_consistent_and_only_three_screens_editable():
    assert SCREENS
    for screen in SCREENS:
        assert screen['readOnly'] == (not screen['editableFields']), screen['id']
    assert sorted(s['id'] for s in SCREENS if not s['readOnly']) == ['hooks', 'media', 'sources']


def _has_vietnamese_mark(text):
    return any(ch in 'đĐ' or unicodedata.combining(ch) for ch in unicodedata.normalize('NFD', text))


def test_titles_are_vietnamese_with_diacritics():
    assert SCREENS
    for screen in SCREENS:
        assert _has_vietnamese_mark(screen['titleVi']), screen['id']


def test_source_has_no_literal_forbidden_endpoint_for_h16_guard():
    text = REGISTRY_PATH.read_text(encoding='utf-8')
    for endpoint in FORBIDDEN_ENDPOINTS:
        assert endpoint not in text, endpoint


def test_exported_surface_matches_acceptance():
    code = _code(REGISTRY_PATH)
    assert "export type Milestone = 'M2' | 'M3' | 'M4' | 'M5' | 'M6' | 'M7';" in code
    spec = re.search(r'export type ScreenSpec = \{(.*?)\n\};', code, re.S)
    assert spec is not None
    assert re.findall(r'^\s*(\w+): (.+?);$', spec.group(1), re.M) == [
        ('id', 'string'), ('titleVi', 'string'), ('milestone', 'Milestone'),
        ('module', 'string'), ('resourcePath', 'string'),
        ('columns', 'readonly string[]'), ('editableFields', 'readonly string[]'),
        ('readOnly', 'boolean'), ('backendStatus', "'available' | 'pending_module'"),
    ]
    forbidden = re.search(r'export const FORBIDDEN_EDITABLE_FIELDS = \[(.*?)\] as const;', code, re.S)
    assert forbidden is not None
    assert _list('[' + forbidden.group(1) + ']') == FORBIDDEN_EDITABLE
    assert 'export function screensForMilestone(m: Milestone): readonly ScreenSpec[] {' in code
    assert 'SCREEN_REGISTRY.filter((screen) => screen.milestone === m)' in code


def test_source_is_pure_utf8_without_any_fetch_or_import():
    raw = REGISTRY_PATH.read_bytes()
    assert not raw.startswith(b'\xef\xbb\xbf')
    assert '�' not in raw.decode('utf-8')
    assert raw.endswith(b'\n') and not raw.endswith(b'\n\n')
    code = _code(REGISTRY_PATH)
    assert not re.search(r'\bany\b', code)
    assert 'fetch(' not in code
    assert not re.search(r'^\s*import\s', code, re.M)

CLIENT_PATH = ROOT / 'src' / 'controlplane' / 'ui' / 'src' / 'api' / 'client.ts'
QUERIES_ROUTES_TEST = ROOT / 'tests' / 'integration' / 'convergence' / 'test_cp4_queries_routes.py'


def _client_function(name):
    code = _code(CLIENT_PATH)
    match = re.search(r'export async function ' + name + r'\(.*?(?=\nexport |\Z)', code, re.S)
    assert match is not None, name
    return match.group(0)


def test_available_and_pending_ids_partition_the_registry():
    assert set(AVAILABLE_IDS) | set(PENDING_IDS) == set(MILESTONE_OF)
    assert not set(AVAILABLE_IDS) & set(PENDING_IDS)
    assert {s['id'] for s in SCREENS if s['backendStatus'] == 'pending_module'} == set(PENDING_IDS)
    assert {s['id'] for s in SCREENS if s['backendStatus'] == 'available'} == set(AVAILABLE_IDS)


def test_stage_runs_is_available_with_route_and_integration_test_evidence():
    assert BY_ID['stage-runs']['backendStatus'] == 'available'
    assert '/v1/stage-runs' in router_get_paths()
    assert 'stage-runs' in QUERIES_ROUTES_TEST.read_text(encoding='utf-8')


SOURCES_MODULE_TEST = ROOT / 'tests' / 'integration' / 'adapt' / 'prod' / 'test_adapt_prod_sources_module.py'


def test_sources_is_available_with_route_and_integration_test_evidence():
    assert BY_ID['sources']['backendStatus'] == 'available'
    assert '/v1/sources' in router_get_paths()
    assert SOURCES_MODULE_TEST.is_file()
    assert 'sources' in SOURCES_MODULE_TEST.read_text(encoding='utf-8')


def test_editable_fields_are_accepted_by_metadata_allowlist_of_same_prefix():
    catalog = catalog_metadata_fields()
    editable = [s for s in SCREENS if s['editableFields']]
    assert sorted(s['id'] for s in editable) == ['hooks', 'media', 'sources']
    for screen in editable:
        allowed = catalog.get(screen['resourcePath'])
        assert allowed is not None, screen['id']
        assert set(screen['editableFields']) <= allowed, screen['id']
    assert set(BY_ID['sources']['editableFields']) == catalog['/v1/sources'] == {'tier', 'topic_tags', 'notes', 'enabled'}


@pytest.mark.parametrize('screen_id', REVISION_COLUMN_IDS)
def test_editable_screens_expose_revision_column(screen_id):
    assert 'revision' in BY_ID[screen_id]['columns']


def test_client_patch_module_item_sends_patch_if_match_and_idempotency_key():
    body = _client_function('patchModuleItem')
    assert "method: 'PATCH'" in body
    assert "'If-Match'" in body
    assert "'Idempotency-Key'" in body
    assert 'encodeURIComponent(itemId)' in body


def test_client_fetch_module_page_uses_cursor_and_returns_next_cursor():
    body = _client_function('fetchModulePage')
    assert "params.set('cursor', cursor)" in body
    assert 'next_cursor' in body


def test_client_keeps_test_driver_capability_endpoint():
    assert '/test-driver/issue-capability' in _code(CLIENT_PATH)
