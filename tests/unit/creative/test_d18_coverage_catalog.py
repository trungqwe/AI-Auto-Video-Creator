"""D-18: Ma trận phủ test ID và acceptance contract của phân hệ D, đối chiếu docstring test D-01..D-17.

coveredIds: không
"""
from __future__ import annotations

import ast
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[3]
SELF = pathlib.Path(__file__).resolve()
SCAN_DIRS = (('tests', 'unit', 'creative'), ('tests', 'integration', 'creative'))
REPORT = ROOT / 'docs' / 'delivery-evidence' / 'd-18' / 'report.md'
REQUIRED_TST = (
    'TST-INT-INV-004',
    'TST-INT-INV-005',
    'TST-CTR-INV-006',
    'TST-AI-INV-013',
    'TST-AI-INV-014',
    'TST-SEC-INV-012',
    'TST-SEC-INV-020',
    'TST-WF-VAR-004',
)
REQUIRED_CT = tuple(f'CT-AI-{number:03d}' for number in range(11))
REQUIRED_IDS = REQUIRED_TST + REQUIRED_CT
ID_PATTERN = re.compile(r'\b[A-Z]{2,}(?:-[A-Z0-9]+)+\b')


def scan_files() -> list[pathlib.Path]:
    found: list[pathlib.Path] = []
    for parts in SCAN_DIRS:
        found.extend(ROOT.joinpath(*parts).glob('test_d*.py'))
    return sorted(path for path in found if path.resolve() != SELF)


def parse(path: pathlib.Path) -> ast.Module:
    return ast.parse(path.read_text(encoding='utf-8'))


def relative(path: pathlib.Path) -> str:
    return path.relative_to(ROOT).as_posix()


def declared_ids(tree: ast.Module) -> list[str]:
    doc = ast.get_docstring(tree) or ''
    line = next((item for item in doc.splitlines() if item.startswith('coveredIds:')), '')
    return ID_PATTERN.findall(line.removeprefix('coveredIds:'))


def has_test_function(tree: ast.Module) -> bool:
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_')
        for node in ast.walk(tree)
    )


def collect_coverage() -> dict[str, list[str]]:
    coverage: dict[str, list[str]] = {}
    for path in scan_files():
        tree = parse(path)
        if not has_test_function(tree):
            continue
        for code in declared_ids(tree):
            files = coverage.setdefault(code, [])
            if relative(path) not in files:
                files.append(relative(path))
    return coverage


def test_scan_covers_every_creative_test_file() -> None:
    names = {relative(path) for path in scan_files()}
    assert len(names) >= 17, sorted(names)
    assert relative(SELF) not in names
    assert any(name.startswith('tests/unit/creative/') for name in names)
    assert any(name.startswith('tests/integration/creative/') for name in names)


def test_required_catalog_is_complete() -> None:
    assert len(REQUIRED_TST) == 8
    assert len(REQUIRED_CT) == 11
    assert REQUIRED_CT[0] == 'CT-AI-000'
    assert REQUIRED_CT[-1] == 'CT-AI-010'
    assert len(set(REQUIRED_IDS)) == 19


def test_every_required_id_has_a_test_file() -> None:
    coverage = collect_coverage()
    missing = [code for code in REQUIRED_IDS if not coverage.get(code)]
    assert not missing, f'Mã chưa có tệp test trực tiếp: {missing}'


def test_every_declaring_file_has_a_test_function() -> None:
    for path in scan_files():
        tree = parse(path)
        required = sorted(set(declared_ids(tree)) & set(REQUIRED_IDS))
        if required:
            assert has_test_function(tree), f'{relative(path)} khai báo {required} nhưng không có hàm test_'


def test_no_file_uses_cre_prefix() -> None:
    offenders = [relative(path) for path in scan_files() if 'TST-CRE-' in path.read_text(encoding='utf-8')]
    assert not offenders, f'Tệp dùng tiền tố TST-CRE-: {offenders}'


def test_no_test_id_outside_catalog() -> None:
    for path in scan_files():
        outside = sorted(
            code for code in declared_ids(parse(path)) if code.startswith('TST-') and code not in REQUIRED_TST
        )
        assert not outside, f'{relative(path)} dùng test ID ngoài catalog: {outside}'


def test_own_docstring_declares_no_covered_ids() -> None:
    doc = ast.get_docstring(parse(SELF)) or ''
    assert 'coveredIds: không' in doc.splitlines()
    assert not set(ID_PATTERN.findall(doc)) & set(REQUIRED_IDS)


def test_report_table_matches_docstring_coverage() -> None:
    coverage = collect_coverage()
    rows: dict[str, set[str]] = {}
    for line in REPORT.read_text(encoding='utf-8').splitlines():
        cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
        if len(cells) >= 2 and cells[0] in REQUIRED_IDS:
            rows[cells[0]] = {item.strip() for item in cells[1].split(',')}
    assert sorted(rows) == sorted(REQUIRED_IDS), f'Bảng report thiếu hoặc thừa mã: {sorted(rows)}'
    for code in REQUIRED_IDS:
        assert rows[code] == set(coverage[code]), f'Bảng report lệch docstring ở {code}'
