"""H-12: component StatusPill (nhãn chữ, ARIA, testid, không HTML thô, không gọi API).

coveredIds: CT-API-007, EG-M2-H-4
"""
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
TSX_PATH = ROOT / 'src' / 'controlplane' / 'ui' / 'src' / 'components' / 'StatusPill.tsx'
STATUS_IMPORT = "import { presentStatus } from '../features/operations/statusPresentation.ts';"
ROLE = 'role="status"'
REQUIRED = (STATUS_IMPORT, ROLE, 'aria-label=', 'data-testid=', 'testIdPrefix', '{presentation.label}', 'presentation.cssClass')
FORBIDDEN = ('dangerouslysetinnerhtml', 'innerhtml', 'ag-grid', 'api/client', 'fetch')
ALLOWED_IMPORTS = {'react', '../features/operations/statusPresentation.ts'}


def read_source():
    raw = TSX_PATH.read_bytes()
    assert not raw.startswith(b'\xef\xbb\xbf')
    return raw.decode('utf-8')


def find_violations(text):
    lowered = text.lower()
    found = [f'forbidden:{t}' for t in FORBIDDEN if t in lowered]
    found += [f'missing:{t}' for t in REQUIRED if t not in text]
    if '\ufffd' in text:
        found.append('replacement_char')
    found += [f'import:{s}' for s in re.findall(r"^import\s.*?from\s+'([^']+)'", text, re.MULTILINE) if s not in ALLOWED_IMPORTS]
    return found


def test_source_has_no_violation():
    assert find_violations(read_source()) == []


def test_signature_and_presenter():
    text = read_source()
    assert 'export const StatusPill: React.FC<{ status: string | null | undefined; testIdPrefix?: string }>' in text
    assert 'presentStatus(status)' in text


def test_span_carries_class_role_label_and_testid():
    text = read_source()
    assert '<span' in text
    assert 'className={`pill ${presentation.cssClass}`}' in text
    assert ROLE in text
    assert 'aria-label={presentation.label}' in text
    assert "data-testid={`${testIdPrefix ?? 'status'}-${suffix}`}" in text
    assert "status.trim().toLowerCase()" in text
    assert "normalized === '' ? 'unknown' : normalized" in text


def test_label_text_is_rendered_as_jsx_content():
    assert re.search(r'>\s*\{presentation\.label\}\s*</span>', read_source()) is not None


BAD_APPENDS = (
    ('<div dangerouslySetInnerHTML={{ __html: x }} />', 'forbidden:dangerouslysetinnerhtml'),
    ('el.innerHTML = x;', 'forbidden:innerhtml'),
    ("import { A } from 'ag-grid-react';", 'forbidden:ag-grid'),
    ("import { A } from 'ag-grid-react';", 'import:ag-grid-react'),
    ("import { x } from '../api/client.ts';", 'forbidden:api/client'),
    ("import { x } from '../api/client.ts';", 'import:../api/client.ts'),
    ("await fetch('/v1/operations');", 'forbidden:fetch'),
    ('const s = "bad \ufffd";', 'replacement_char'),
)


@pytest.mark.parametrize('extra,code', BAD_APPENDS)
def test_violation_is_reported(extra, code):
    assert code in find_violations(read_source() + '\n' + extra)


@pytest.mark.parametrize('token', [STATUS_IMPORT, ROLE, 'aria-label=', 'data-testid=', 'testIdPrefix', '{presentation.label}'])
def test_removed_token_is_reported_missing(token):
    assert f'missing:{token}' in find_violations(read_source().replace(token, 'removed'))


def test_color_only_pill_is_reported():
    found = find_violations("export const StatusPill = ({ status }) => <span className={'pill pill-' + status} />;")
    assert 'missing:{presentation.label}' in found
    assert 'missing:aria-label=' in found
    assert f'missing:{ROLE}' in found


def test_raw_html_and_self_fetching_components_are_reported():
    assert 'forbidden:dangerouslysetinnerhtml' in find_violations('const C = () => <span dangerouslySetInnerHTML={{ __html: s }} />;')
    found = find_violations("import { api } from '../api/client.ts';")
    assert 'forbidden:api/client' in found
    assert 'import:../api/client.ts' in found
