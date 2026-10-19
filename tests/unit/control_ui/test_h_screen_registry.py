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
AVAILABLE_IDS = ('operations', 'batches', 'jobs', 'configs')
READ_ONLY_IDS = ('articles', 'events', 'snapshots', 'story-angles', 'scripts')
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


def router_get_paths():
    text = CONTROL_PATH.read_text(encoding='utf-8')
    prefix = re.search(r'APIRouter\(prefix=.(/[a-z0-9/]*).\)', text)
    assert prefix is not None
    paths = re.findall(r'^@router\.get\(.(/[a-z0-9-]+).\)', text, re.M)
    return {prefix.group(1) + path for path in paths}


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
    assert len(others) == 14
    assert all(s['backendStatus'] == 'pending_module' for s in others)


def test_resource_path_is_v1_prefix_plus_id():
    assert SCREENS
    for screen in SCREENS:
        assert screen['resourcePath'] == '/v1/' + screen['id'], screen['id']


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
