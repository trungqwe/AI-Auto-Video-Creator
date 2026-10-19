"""H-11: trình bày trạng thái operation và artifact bằng tiếng Việt (CT-API-007).

coveredIds: QR-UX-001, QR-UX-003, CT-API-007
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from controlplane.application.projections.operation_view_model import OPERATION_STATUSES

ROOT = Path(__file__).resolve().parents[3]
PRESENTATION_TS = (
    ROOT / 'src' / 'controlplane' / 'ui' / 'src' / 'features' / 'operations' / 'statusPresentation.ts'
)
STATUS_HEADER = 'export const STATUS_PRESENTATION: Record<OperationStatus, StatusPresentation>'
ARTIFACT_HEADER = (
    'export const ARTIFACT_AVAILABILITY_PRESENTATION: '
    'Record<ArtifactAvailability, ArtifactAvailabilityPresentation>'
)
STATUS_ENTRY = re.compile(
    r"^  (\w+): \{ label: '([^']+)', cssClass: '([^']+)', terminal: (true|false), attention: (true|false) \},$",
    re.MULTILINE,
)
ARTIFACT_ENTRY = re.compile(r"^  (\w+): \{ label: '([^']+)' \},$", re.MULTILINE)
ANY_PATTERNS = (r':\s*any\b', r'\bas\s+any\b', r'<\s*any\s*>', r'\bany\b')
UNKNOWN_LABEL = 'Không nhận diện được'
EXPECTED_STATUS = {
    'accepted': ('Đã tiếp nhận', 'pill-accepted', False, False),
    'running': ('Đang chạy', 'pill-running', False, False),
    'waiting': ('Đang chờ', 'pill-waiting', False, True),
    'outcome_unknown': ('Chưa xác định kết quả', 'pill-outcome-unknown', False, True),
    'succeeded': ('Thành công', 'pill-succeeded', True, False),
    'failed': ('Thất bại', 'pill-failed', True, True),
}
EXPECTED_ARTIFACT = {
    'original': 'Bản gốc',
    'processed': 'Đã xử lý',
    'uncertain': 'Chưa chắc chắn',
    'failed': 'Lỗi',
    'unavailable': 'Không khả dụng',
}


def _read() -> str:
    return PRESENTATION_TS.read_text(encoding='utf-8')


def _block(source: str, header: str) -> str:
    match = re.search(re.escape(header) + r' = \{\n(.*?)\n\};', source, re.DOTALL)
    assert match, header
    return match.group(1)


def _function_body(source: str, signature: str) -> str:
    match = re.search(re.escape(signature) + r' \{\n(.*?)\n\}', source, re.DOTALL)
    assert match, signature
    return match.group(1)


def _status_rows() -> dict[str, tuple[str, str, bool, bool]]:
    body = _block(_read(), STATUS_HEADER)
    rows = {
        name: (label, css, terminal == 'true', attention == 'true')
        for name, label, css, terminal, attention in STATUS_ENTRY.findall(body)
    }
    assert len(rows) == len(body.splitlines())
    return rows


def _artifact_rows() -> dict[str, str]:
    body = _block(_read(), ARTIFACT_HEADER)
    rows = dict(ARTIFACT_ENTRY.findall(body))
    assert len(rows) == len(body.splitlines())
    return rows


def _has_vietnamese_mark(label: str) -> bool:
    marks = any(unicodedata.category(ch) == 'Mn' for ch in unicodedata.normalize('NFD', label))
    return marks or 'đ' in label.lower()


def test_status_keys_equal_h01() -> None:
    assert tuple(_status_rows()) == tuple(OPERATION_STATUSES)


def test_status_rows_match_acceptance() -> None:
    assert _status_rows() == EXPECTED_STATUS


def test_labels_distinct_with_vietnamese_marks() -> None:
    labels = [row[0] for row in _status_rows().values()]
    assert len(set(labels)) == len(labels) == len(OPERATION_STATUSES)
    for label in labels:
        assert _has_vietnamese_mark(label), label


def test_css_classes_distinct_and_flags() -> None:
    rows = _status_rows()
    css = [row[1] for row in rows.values()]
    assert len(set(css)) == len(css)
    assert {name for name, row in rows.items() if row[2]} == {'succeeded', 'failed'}
    assert {name for name, row in rows.items() if row[3]} == {'waiting', 'outcome_unknown', 'failed'}


def test_unrecognized_status_has_pill_unknown_branch() -> None:
    source = _read()
    assert (
        'export const UNRECOGNIZED_STATUS_PRESENTATION: StatusPresentation = {\n'
        f"  label: '{UNKNOWN_LABEL}',\n"
        "  cssClass: 'pill-unknown',\n"
        '  terminal: false,\n'
        '  attention: true,\n'
        '};'
    ) in source
    normalize = _function_body(source, 'function normalize(value: string | null | undefined): string')
    assert '.toLowerCase()' in normalize
    signature = 'export function presentStatus(value: string | null | undefined): StatusPresentation'
    body = _function_body(source, signature)
    assert 'hasOwnProperty' in body
    assert body.rstrip().endswith('return UNRECOGNIZED_STATUS_PRESENTATION;')
    assert 'accepted' not in body.lower()


def test_no_accepted_fallback() -> None:
    source = _read()
    assert "?? 'ACCEPTED'" not in source and "|| 'ACCEPTED'" not in source
    assert not re.search(r'(\?\?|\|\|)[^\n;]*accepted', source, re.IGNORECASE)


def test_artifact_availability_five_states() -> None:
    source = _read()
    rows = _artifact_rows()
    assert rows == EXPECTED_ARTIFACT
    states = re.search(r'export const ARTIFACT_AVAILABILITY_STATES = \[(.*?)\] as const;', source, re.DOTALL)
    assert states
    assert tuple(re.findall(r"'([a-z_]+)'", states.group(1))) == tuple(EXPECTED_ARTIFACT)
    assert 'export type ArtifactAvailability = (typeof ARTIFACT_AVAILABILITY_STATES)[number];' in source
    signature = (
        'export function presentArtifactAvailability(value: string | null | undefined): '
        'ArtifactAvailabilityPresentation'
    )
    body = _function_body(source, signature)
    assert 'hasOwnProperty' in body
    assert body.rstrip().endswith('return { label: UNRECOGNIZED_STATUS_PRESENTATION.label };')
    assert 'accepted' not in body.lower()
    for label in rows.values():
        assert _has_vietnamese_mark(label), label


def test_imports_and_interfaces() -> None:
    source = _read()
    assert "import type { OperationStatus } from '../../types/operationView.ts';" in source
    assert (
        'export interface StatusPresentation {\n  label: string;\n  cssClass: string;\n'
        '  terminal: boolean;\n  attention: boolean;\n}'
    ) in source
    assert 'export interface ArtifactAvailabilityPresentation {\n  label: string;\n}' in source


def test_no_any_and_no_replacement_char() -> None:
    source = _read()
    for pattern in ANY_PATTERNS:
        assert not re.search(pattern, source), pattern
    assert '�' not in source
