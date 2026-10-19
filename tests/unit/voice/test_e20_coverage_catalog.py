"""E-20: coverage matrix of test IDs and contract 07 acceptance for stage E (CT-PROC-001..008, CT-TTS-001, CT-SUB-001, CT-AUD-001).

coveredIds: acceptance §10 mục 1 đến 6 của contract 07
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
SELF = pathlib.Path(__file__).resolve()
SCAN_DIRS = ('tests/unit/voice', 'tests/integration/voice')
ID_PATTERN = re.compile(r'\b(?:TST|CT)(?:-[A-Z0-9]+)+-\d{3}\b')
FORBIDDEN_PREFIX = re.compile(r'TST-(?:VOI|MED|RND|EF)-')
REQUIRED_IDS = (
    'TST-MEDIA-INV-007',
    'TST-INT-INV-008',
    'TST-QC-INV-019',
    'TST-SEC-INV-012',
    'TST-E2E-001',
    'TST-E2E-011',
    'TST-E2E-014',
    *(f'CT-PROC-{n:03d}' for n in range(1, 9)),
    'CT-TTS-001',
    'CT-SUB-001',
    'CT-AUD-001',
)


def scan_files() -> list[pathlib.Path]:
    return sorted(p for d in SCAN_DIRS for p in (ROOT / d).glob('test_e*.py') if p.resolve() != SELF)


def covered_ids(text: str) -> set[str]:
    doc = ast.get_docstring(ast.parse(text)) or ''
    ids: set[str] = set()
    for line in doc.splitlines():
        if line.strip().startswith('coveredIds:'):
            ids.update(ID_PATTERN.findall(line))
    return ids


def has_test_function(text: str) -> bool:
    tree = ast.parse(text)
    return any(
        isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith('test_')
        for n in ast.walk(tree)
    )


def coverage_index() -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for p in scan_files():
        text = p.read_text(encoding='utf-8')
        if has_test_function(text):
            rel = p.relative_to(ROOT).as_posix()
            for cid in covered_ids(text):
                index.setdefault(cid, []).append(rel)
    return index


def test_scan_covers_e01_to_e19_and_excludes_e20() -> None:
    files = scan_files()
    assert {p.name.split('_')[1] for p in files} == {f'e{n:02d}' for n in range(1, 20)}
    assert SELF not in [p.resolve() for p in files]


@pytest.mark.parametrize('required_id', REQUIRED_IDS)
def test_required_id_is_declared_in_a_file_with_test_functions(required_id: str) -> None:
    files = coverage_index().get(required_id, [])
    assert files, f'{required_id} is not in coveredIds of any tests/**/voice/test_e*.py that has a test_ function'


def test_no_scanned_file_uses_forbidden_prefix() -> None:
    violations = [p.name for p in scan_files() if FORBIDDEN_PREFIX.search(p.read_text(encoding='utf-8'))]
    assert violations == []


def test_tst_ids_used_in_docstrings_exist_in_catalog() -> None:
    catalog = (ROOT / 'docs/10-test-strategy.md').read_text(encoding='utf-8')
    tst_ids: set[str] = set()
    for p in scan_files():
        tst_ids.update(cid for cid in covered_ids(p.read_text(encoding='utf-8')) if cid.startswith('TST-'))
    tst_ids.update(rid for rid in REQUIRED_IDS if rid.startswith('TST-'))
    for tst_id in sorted(tst_ids):
        assert tst_id in catalog, f'{tst_id} is not documented in docs/10-test-strategy.md'


def test_checker_ignores_ids_outside_module_docstring() -> None:
    text = '"""x\n\ncoveredIds: CT-PROC-001\n"""\nOTHER = "CT-PROC-002"\n# CT-PROC-003\n'
    assert covered_ids(text) == {'CT-PROC-001'}


def test_checker_requires_a_real_test_function() -> None:
    assert has_test_function('"""x"""\ndef helper():\n    pass\n') is False
    assert has_test_function('def test_a():\n    pass\n') is True
    assert has_test_function('class T:\n    def test_b(self):\n        pass\n') is True


def test_checker_detects_forbidden_prefix_but_not_catalog_ids() -> None:
    assert FORBIDDEN_PREFIX.search('TST-' + 'VOI-001')
    assert FORBIDDEN_PREFIX.search('TST-MEDIA-INV-007') is None


def test_required_ids_list_has_the_expected_size() -> None:
    assert len(REQUIRED_IDS) == 18
    assert len(set(REQUIRED_IDS)) == 18
