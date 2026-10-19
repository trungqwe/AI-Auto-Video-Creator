"""H-10: kiểu TypeScript cho OperationView và ListPage (CT-API-007).

coveredIds: CT-API-007, QR-UX-003
"""
from __future__ import annotations

import re
from pathlib import Path

from controlplane.application.projections.operation_view_model import OPERATION_STATUSES

ROOT = Path(__file__).resolve().parents[3]
TYPES_DIR = ROOT / 'src' / 'controlplane' / 'ui' / 'src' / 'types'
OPERATION_VIEW_TS = TYPES_DIR / 'operationView.ts'
LIST_PAGE_TS = TYPES_DIR / 'listPage.ts'
API_TS = TYPES_DIR / 'api.ts'
CONTRACT = ROOT / 'docs' / '09-contracts' / '01-control-api-and-stream.md'
ANY_PATTERNS = (r':\s*any\b', r'\bas\s+any\b', r'<\s*any\s*>')
OPTIONAL_FIELDS = {'progress', 'started_at', 'updated_at', 'finished_at', 'wait_reason', 'problem'}


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def _interface_body(source: str, header: str) -> str:
    match = re.search(re.escape(header) + r'\s*\{(.*?)\n\}', source, re.DOTALL)
    assert match, header
    return match.group(1)


def _fields(body: str) -> dict[str, bool]:
    return {name: bool(opt) for name, opt in re.findall(r'^  (\w+)(\?)?:', body, re.MULTILINE)}


def _contract_fields() -> list[str]:
    section = re.search(r'### CT-API-007.*?(?=\n##|\Z)', _read(CONTRACT), re.DOTALL)
    assert section
    names: list[str] = []
    for line in section.group(0).splitlines():
        if line.startswith('| `'):
            names.extend(re.findall(r'`([a-z_]+)`', line.split('|')[1]))
    return names


def test_contract_lists_ten_fields_without_status_row_confusion() -> None:
    names = _contract_fields()
    assert len(names) == 10 and len(set(names)) == 10


def test_interface_fields_match_contract() -> None:
    body = _interface_body(_read(OPERATION_VIEW_TS), 'export interface OperationView')
    fields = _fields(body)
    assert set(fields) == set(_contract_fields())
    for name, optional in fields.items():
        assert optional == (name in OPTIONAL_FIELDS), name


def test_status_tuple_equals_h01() -> None:
    source = _read(OPERATION_VIEW_TS)
    match = re.search(r'export const OPERATION_STATUSES\s*=\s*\[(.*?)\]\s*as const;', source, re.DOTALL)
    assert match
    assert tuple(re.findall(r"'([a-z_]+)'", match.group(1))) == tuple(OPERATION_STATUSES)
    assert re.search(r'export type OperationStatus\s*=\s*\(typeof OPERATION_STATUSES\)\[number\];', source)


def test_status_field_uses_operation_status_not_string() -> None:
    body = _interface_body(_read(OPERATION_VIEW_TS), 'export interface OperationView')
    assert re.search(r'^  status: OperationStatus;', body, re.MULTILINE)
    assert not re.search(r'^  status\??:\s*string', body, re.MULTILINE)


def test_problem_uses_problem_detail_import() -> None:
    source = _read(OPERATION_VIEW_TS)
    assert "import type { ProblemDetail } from './api.ts';" in source
    assert re.search(r'^  problem\?: ProblemDetail;', source, re.MULTILINE)


def test_list_page_shape() -> None:
    source = _read(LIST_PAGE_TS)
    body = _interface_body(source, 'export interface ListPage<T>')
    assert re.search(r'^  items: T\[\];', body, re.MULTILINE)
    assert re.search(r'^  next_cursor: string \| null;', body, re.MULTILINE)


def test_no_any_and_no_replacement_char() -> None:
    for path in (OPERATION_VIEW_TS, LIST_PAGE_TS):
        source = _read(path)
        for pattern in ANY_PATTERNS:
            assert not re.search(pattern, source), (path.name, pattern)
        assert '�' not in source


def test_api_ts_unchanged_in_scope() -> None:
    source = _read(API_TS)
    body = _interface_body(source, 'export interface OperationItem')
    assert 'wait_reason' not in body
    assert 'operationView' not in source and 'listPage' not in source
