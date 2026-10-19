"""A-19: every A-RULE and test ID of the collection subsystem maps to a real test file (IMPL-PLAN-A).

Only the stdlib is used. The module docstring of each tests/unit/collection/test_a*.py and
tests/integration/collection/test_a*.py file (this file excluded) is the single source of covered IDs.
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
SELF_NAME = pathlib.Path(__file__).name
NL = chr(10)
TEST_DIRS = (ROOT / 'tests' / 'unit' / 'collection', ROOT / 'tests' / 'integration' / 'collection')
REQUIRED_IDS = (
    tuple(f'A-RULE-{n:03d}' for n in range(1, 17))
    + tuple(f'TST-COL-END-{n:03d}' for n in range(1, 5))
    + tuple(f'TST-COL-PKG-{n:03d}' for n in range(1, 5))
    + tuple(f'TST-SRC-RACE-{n:03d}' for n in range(1, 5))
    + ('TST-INT-INV-015',)
)
ID_PATTERN = re.compile(r'\b((?:[A-Z]+-)+)(\d{3})(?:\.\.(\d{3}))?')


def covered_ids(docstring):
    ids = set()
    for line in (docstring or '').splitlines():
        if not line.startswith('coveredIds:'):
            continue
        for prefix, first, last in ID_PATTERN.findall(line):
            ids.update(f'{prefix}{n:03d}' for n in range(int(first), int(last or first) + 1))
    return ids


def has_test_function(tree):
    functions = (ast.FunctionDef, ast.AsyncFunctionDef)
    return any(isinstance(node, functions) and node.name.startswith('test_') for node in ast.walk(tree))


def build_catalog(paths):
    catalog = {}
    for path in paths:
        tree = ast.parse(path.read_text(encoding='utf-8'))
        if not has_test_function(tree):
            continue
        for code in covered_ids(ast.get_docstring(tree)):
            catalog.setdefault(code, []).append(path.name)
    return {code: sorted(names) for code, names in catalog.items()}


def collection_test_files():
    return sorted(
        path for directory in TEST_DIRS for path in directory.glob('test_a*.py') if path.name != SELF_NAME
    )


CATALOG = build_catalog(collection_test_files())


def test_scan_covers_the_test_file_of_every_slice_a01_to_a18_and_skips_a19():
    names = [path.name for path in collection_test_files()]
    assert {name[5:8] for name in names} == {f'a{n:02d}' for n in range(1, 19)}
    assert SELF_NAME not in names


@pytest.mark.parametrize('code', REQUIRED_IDS)
def test_required_id_is_covered_by_a_test_file_with_a_test_function(code):
    assert CATALOG.get(code), f'{code} has no collection test file with a test_ function'


def test_catalog_never_lists_the_a19_file():
    assert all(SELF_NAME not in names for names in CATALOG.values())


def test_covered_ids_expands_a_range_and_reads_only_coveredids_lines():
    docstring = NL.join(['A-90: prose may mention A-RULE-009.', '', 'coveredIds: TST-COL-END-001..003, A-RULE-004'])
    assert covered_ids(docstring) == {'TST-COL-END-001', 'TST-COL-END-002', 'TST-COL-END-003', 'A-RULE-004'}
    assert covered_ids(None) == set()


def test_file_without_a_test_function_covers_no_id(tmp_path):
    docstring_only = tmp_path / 'test_a90_docstring_only.py'
    docstring_only.write_text(NL.join(['"""A-90.', '', 'coveredIds: A-RULE-001', '"""', '', 'def helper():', '    return 1', '']), encoding='utf-8')
    with_test = tmp_path / 'test_a91_with_test.py'
    with_test.write_text(NL.join(['"""A-91.', '', 'coveredIds: A-RULE-002', '"""', '', 'def test_x():', '    assert True', '']), encoding='utf-8')
    assert build_catalog([docstring_only, with_test]) == {'A-RULE-002': ['test_a91_with_test.py']}


REPORT = ROOT / 'docs' / 'delivery-evidence' / 'a-19' / 'report.md'
FILE_NAME = re.compile(r'test_a\d{2}_\w+\.py')


@pytest.mark.parametrize('code', REQUIRED_IDS)
def test_report_maps_the_id_to_exactly_the_files_that_cover_it(code):
    lines = REPORT.read_text(encoding='utf-8').splitlines()
    rows = [line for line in lines if line.startswith(f'| `{code}` |')]
    assert len(rows) == 1
    assert sorted(set(FILE_NAME.findall(rows[0]))) == CATALOG[code]
