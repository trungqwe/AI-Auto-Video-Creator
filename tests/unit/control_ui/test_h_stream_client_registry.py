"""H-14: danh mục event kind phía client và deduper có giới hạn (CT-API-008, GAP-H-02, GAP-H-03).

coveredIds: CT-API-008
"""
import pathlib
import re

import pytest

from controlplane.application.sse.event_catalog import (
    ALL_SNAPSHOT_RESOURCES,
    BASE_STREAM_EVENT_KINDS,
    SNAPSHOT_RESOURCES,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
UI_SRC = ROOT / 'src' / 'controlplane' / 'ui' / 'src'
KINDS_PATH = UI_SRC / 'api' / 'streamEventKinds.ts'
DEDUPER_PATH = UI_SRC / 'features' / 'stream' / 'boundedEventDeduper.ts'
OLD_TEN_KINDS = ('operation.accepted', 'operation.running', 'operation.succeeded', 'operation.failed', 'operation.changed', 'production_batch.start_accepted', 'job.created', 'job.running', 'job.completed', 'job.failed')
MODULE_ONLY_RESOURCES = {'media', 'hooks', 'sessions', 'logs'}


def _read(path):
    return path.read_text(encoding='utf-8')


def _code(path):
    text = re.sub(r'/\*.*?\*/', '', _read(path), flags=re.S)
    return re.sub(r'//[^\n]*', '', text)


def _group(code, pattern):
    match = re.search(pattern, code, re.S)
    assert match is not None, pattern
    return match.group(1)


def _literals(block):
    return re.findall(r"'([^']*)'", block)


def _client_kinds():
    block = _group(_code(KINDS_PATH), r'export const STREAM_EVENT_KINDS = \[(.*?)\] as const;')
    return tuple(_literals(block))


def _client_resource_table():
    body = _group(_code(KINDS_PATH), r'export const RESYNC_SNAPSHOT_RESOURCES: Record<string, readonly string\[\]> = \{(.*?)\n\};')
    entries = re.findall(r'(\w+):\s*\[([^\]]*)\]', body)
    table = {key: tuple(_literals(items)) for key, items in entries}
    assert len(table) == len(entries)
    return table


def _client_fallback():
    block = _group(_code(KINDS_PATH), r'export const ALL_SNAPSHOT_RESOURCES: readonly string\[\] = \[(.*?)\];')
    return tuple(_literals(block))


def test_client_kinds_equal_base_kinds_in_order():
    kinds = _client_kinds()
    assert kinds == BASE_STREAM_EVENT_KINDS
    assert kinds[:10] == OLD_TEN_KINDS
    assert len(kinds) == len(set(kinds)) == 48


def test_client_kind_type_is_derived_from_const_tuple():
    assert 'export type StreamEventKind = (typeof STREAM_EVENT_KINDS)[number];' in _code(KINDS_PATH)


def test_client_resource_table_equals_python_snapshot_resources():
    assert _client_resource_table() == dict(SNAPSHOT_RESOURCES)


def test_client_resource_table_keys_are_kind_prefixes():
    table = _client_resource_table()
    assert set(table) == set(SNAPSHOT_RESOURCES)
    assert len(table) == 6
    assert set(table) <= {kind.partition('.')[0] for kind in _client_kinds()}
    union = {r for rs in table.values() for r in rs}
    assert union == {r for rs in SNAPSHOT_RESOURCES.values() for r in rs}
    assert union <= set(ALL_SNAPSHOT_RESOURCES)
    assert set(ALL_SNAPSHOT_RESOURCES) - union == MODULE_ONLY_RESOURCES


def test_client_fallback_equals_python_all_snapshot_resources():
    assert _client_fallback() == ALL_SNAPSHOT_RESOURCES
    assert len(_client_fallback()) == 11


def test_snapshot_resources_for_signature_and_unknown_fallback():
    body = _group(_code(KINDS_PATH), r'export function snapshotResourcesFor\(resourceType: string\): readonly string\[\] \{(.*?)\n\}')
    assert 'Object.prototype.hasOwnProperty.call(RESYNC_SNAPSHOT_RESOURCES, resourceType)' in body
    assert 'return RESYNC_SNAPSHOT_RESOURCES[resourceType];' in body
    assert body.rstrip().endswith('return ALL_SNAPSHOT_RESOURCES;')


def test_deduper_default_max_seen_is_5000():
    assert re.search(r'^export const DEFAULT_MAX_SEEN = 5000;$', _code(DEDUPER_PATH), re.M)


def test_deduper_factory_signature_and_interface():
    code = _code(DEDUPER_PATH)
    assert 'export function createBoundedEventDeduper(maxSeen: number = DEFAULT_MAX_SEEN): BoundedEventDeduper {' in code
    contract = _group(code, r'export interface BoundedEventDeduper \{(.*?)\n\}')
    for member in ('seenBefore(id: string): boolean;', 'clear(): void;', 'size(): number;'):
        assert member in contract


def test_deduper_rejects_non_integer_or_non_positive_max_seen_before_allocating():
    code = _code(DEDUPER_PATH)
    guard = 'if (!Number.isInteger(maxSeen) || maxSeen < 1) {'
    assert guard in code
    assert 'throw new RangeError(' in code
    assert code.index(guard) < code.index('throw new RangeError(') < code.index('new Set<string>()')


def test_deduper_evicts_oldest_id_in_insertion_order():
    code = _code(DEDUPER_PATH)
    assert re.search(r'seen\.size > maxSeen', code)
    has = code.index('seen.has(id)')
    add = code.index('seen.add(id)')
    oldest = code.index('seen.keys().next()')
    delete = code.index('seen.delete(oldest.value)')
    assert has < add < oldest < delete
    assert 'seen.clear()' in code
    assert 'return seen.size;' in code


@pytest.mark.parametrize('path', [KINDS_PATH, DEDUPER_PATH], ids=lambda p: p.name)
def test_files_are_pure_no_network_no_event_source_no_any(path):
    text = _read(path)
    assert 'fetch(' not in text
    assert 'EventSource' not in text
    assert ': any' not in text
    assert not re.search(r'\bany\b', _code(path))
    assert not re.search(r'^\s*import\s', _code(path), re.M)


@pytest.mark.parametrize('path', [KINDS_PATH, DEDUPER_PATH], ids=lambda p: p.name)
def test_files_are_utf8_without_bom_or_replacement_chars(path):
    raw = path.read_bytes()
    assert not raw.startswith(b'\xef\xbb\xbf')
    assert '\ufffd' not in raw.decode('utf-8')
    assert raw.endswith(b'\n')
    assert not raw.endswith(b'\n\n')
