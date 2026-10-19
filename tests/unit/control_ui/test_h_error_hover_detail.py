"""H-13: component ErrorHoverDetail (hover và focus, không stack trace).

coveredIds: QR-UX-004, QR-UX-001, CT-API-010
"""
import pathlib
import re
import unicodedata

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
TSX_PATH = ROOT / 'src' / 'controlplane' / 'ui' / 'src' / 'components' / 'ErrorHoverDetail.tsx'
REQUIRED = ('tabIndex={0}', 'aria-describedby', 'onMouseEnter', 'onMouseLeave', 'onFocus', 'onBlur', 'Escape', 'MAX_DETAIL_CHARS = 300', 'onOpenTechnicalDetail')
FORBIDDEN = ('dangerouslysetinnerhtml', 'innerhtml', 'api/client', 'fetch', 'internal_detail', 'stack')
ALLOWED_FIELDS = {'title', 'code', 'correlation_id', 'detail', 'technical_detail_ref'}


def read_source():
    raw = TSX_PATH.read_bytes()
    assert not raw.startswith(b'\xef\xbb\xbf')
    return raw.decode('utf-8')


def find_violations(text):
    lowered = text.lower()
    found = [f'forbidden:{token}' for token in FORBIDDEN if token in lowered]
    found += [f'missing:{token}' for token in REQUIRED if token not in text]
    if '\uFFFD' in text:
        found.append('replacement_char')
    found += [f'import:{src}' for src in re.findall(r"^import\s.*?from\s+'([^']+)'", text, re.MULTILINE) if src != 'react']
    found += [f'field:{name}' for name in sorted(set(re.findall(r'\bproblem\.(\w+)', text)) - ALLOWED_FIELDS)]
    return found


def test_source_has_no_violation():
    assert find_violations(read_source()) == []


def test_signature_and_null_guard():
    text = read_source()
    assert 'export const ErrorHoverDetail: React.FC<' in text
    assert 'problem: ErrorHoverProblem | null | undefined;' in text
    assert 'onOpenTechnicalDetail?: (ref: string) => void;' in text
    assert 'if (!problem) return null;' in text
    assert 'export const MAX_DETAIL_CHARS = 300;' in text
    assert '.slice(0, MAX_DETAIL_CHARS)' in text


def test_trigger_is_keyboard_focusable_and_described_by_tooltip():
    text = read_source()
    assert text.count('tabIndex={0}') == 1
    assert 'aria-describedby={tooltipId}' in text
    assert 'id={tooltipId}' in text
    assert 'role="tooltip"' in text


def test_show_and_hide_handlers():
    text = read_source()
    assert 'onMouseEnter={() => setOpen(true)}' in text
    assert 'onFocus={() => setOpen(true)}' in text
    assert 'onMouseLeave={() => setOpen(false)}' in text
    assert 'onBlur={handleBlur}' in text
    assert 'onKeyDown={handleKeyDown}' in text
    assert "if (event.key === 'Escape') setOpen(false);" in text
    assert 'event.currentTarget.contains(event.relatedTarget as Node | null)' in text


def test_tooltip_renders_only_allowed_fields_through_jsx():
    text = read_source()
    for expr in ('{problem.title}', '{problem.code}', '{problem.correlation_id}', '{detailText}'):
        assert expr in text
    assert '{technicalRef}' not in text
    assert set(re.findall(r'\bproblem\.(\w+)', text)) == ALLOWED_FIELDS


def test_technical_button_calls_callback_with_ref_and_has_vietnamese_label():
    text = read_source()
    assert 'onClick={() => openTechnical(technicalRef)}' in text
    assert '{TECHNICAL_DETAIL_LABEL}' in text
    match = re.search(r"const TECHNICAL_DETAIL_LABEL = '([^']+)';", text)
    assert match is not None
    assert any(ord(ch) > 127 and unicodedata.category(ch).startswith('L') for ch in match.group(1))


BAD_APPENDS = (
    ('<div dangerouslySetInnerHTML={{ __html: x }} />', 'forbidden:dangerouslysetinnerhtml'),
    ('el.innerHTML = x;', 'forbidden:innerhtml'),
    ("await fetch('/v1/jobs');", 'forbidden:fetch'),
    ("import { x } from '../api/client.ts';", 'forbidden:api/client'),
    ("import { x } from '../api/client.ts';", 'import:../api/client.ts'),
    ('{problem.internal_detail}', 'forbidden:internal_detail'),
    ('{problem.internal_detail}', 'field:internal_detail'),
    ('{problem.stack_trace}', 'forbidden:stack'),
    ('{problem.stack_trace}', 'field:stack_trace'),
    ('{problem.extra}', 'field:extra'),
    ('const s = "bad \uFFFD";', 'replacement_char'),
)


@pytest.mark.parametrize('extra,code', BAD_APPENDS)
def test_violation_is_reported(extra, code):
    assert code in find_violations(read_source() + '\n' + extra)


@pytest.mark.parametrize('token', ['tabIndex={0}', 'onFocus', 'onBlur', 'Escape', 'onOpenTechnicalDetail', 'MAX_DETAIL_CHARS = 300'])
def test_removed_token_is_reported_missing(token):
    mutated = read_source().replace(token, 'removed')
    assert f'missing:{token}' in find_violations(mutated)


def test_hover_only_source_is_reported():
    hover_only = 'export const ErrorHoverDetail = () => <span onMouseEnter={() => 1} onMouseLeave={() => 2} />;'
    found = find_violations(hover_only)
    assert 'missing:tabIndex={0}' in found
    assert 'missing:onFocus' in found
    assert 'missing:Escape' in found
