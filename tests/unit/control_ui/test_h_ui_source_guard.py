"""H-16: guard tĩnh nguồn UI (XSS sink, secret hằng, fetch, endpoint cấm).

coveredIds: CT-API-010, TST-SEC-INV-012, QR-UX-001
"""
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
UI_SRC = ROOT / 'src' / 'controlplane' / 'ui' / 'src'
COMP = 'src/components/A.tsx'


SINK_RULES = (
    ('dangerouslySetInnerHTML', re.compile(r'dangerouslySetInnerHTML')),
    ('innerHTML', re.compile(r'\.innerHTML\b')),
    ('eval', re.compile(r'\beval\s*\(')),
    ('new Function', re.compile(r'\bnew\s+Function\s*\(')),
    ('document.write', re.compile(r'\bdocument\.write(?:ln)?\b')),
    ('localStorage', re.compile(r'\blocalStorage\b')),
    ('sessionStorage', re.compile(r'\bsessionStorage\b')),
)
FETCH_RE = re.compile(r'\bfetch\s*\(')
SECRET_RE = re.compile(
    r"""(?:api_?key|secret|token)\w*['"]?\s*(?::\s*\w+\s*)?[:=]\s*['"][A-Za-z0-9]{16,}['"]""",
    re.IGNORECASE,
)
FORBIDDEN_ENDPOINTS = ('/scripts', '/event-relations', '/article-body')
REPLACEMENT_CHAR = '\ufffd'
BOM = '\ufeff'


def scan_ui_source(path: str, text: str) -> list[str]:
    norm = '/' + path.replace('\\', '/').lstrip('/')
    in_api = '/src/api/' in norm
    in_features = '/src/features/' in norm
    found = []

    def add(index, code):
        found.append(f'{path}:{text.count(chr(10), 0, index) + 1}: {code}')

    if text.startswith(BOM):
        add(0, 'bom')
    for code, pattern in SINK_RULES:
        for m in pattern.finditer(text):
            add(m.start(), code)
    if not in_api:
        for m in FETCH_RE.finditer(text):
            add(m.start(), 'fetch_outside_api')
    for m in SECRET_RE.finditer(text):
        add(m.start(), 'hardcoded_secret')
    for m in re.finditer(REPLACEMENT_CHAR, text):
        add(m.start(), 'replacement_char')
    if in_api or in_features:
        for endpoint in FORBIDDEN_ENDPOINTS:
            for m in re.finditer(re.escape(endpoint), text):
                add(m.start(), f'forbidden_endpoint:{endpoint}')
    return found


VIOLATIONS = [
    (COMP, '<div dangerouslySetInnerHTML={{ __html: x }} />', 'dangerouslySetInnerHTML'),
    (COMP, 'el.innerHTML = x;', 'innerHTML'),
    (COMP, 'eval(code);', 'eval'),
    (COMP, "const f = new Function('return 1');", 'new Function'),
    (COMP, 'document.write(x);', 'document.write'),
    (COMP, "localStorage.setItem('a', 'b');", 'localStorage'),
    (COMP, "sessionStorage.getItem('a');", 'sessionStorage'),
    (COMP, "await fetch('/v1/jobs');", 'fetch_outside_api'),
    (COMP, "const apiKey = 'abcdefgh12345678';", 'hardcoded_secret'),
    (COMP, "const cfg = { token: 'ABCDEFGH12345678' };", 'hardcoded_secret'),
    (COMP, 'const client_secret: string = "abcdefgh12345678";', 'hardcoded_secret'),
    (COMP, 'const s = "bad \ufffd text";', 'replacement_char'),
    ('src/api/client.ts', "const u = '/scripts/1';", 'forbidden_endpoint:/scripts'),
    ('src/features/x.ts', "const u = '/event-relations';", 'forbidden_endpoint:/event-relations'),
    ('src/api/client.ts', "const u = '/article-body';", 'forbidden_endpoint:/article-body'),
    (COMP, '\ufeffexport const a = 1;', 'bom'),
]

CLEAN = [
    ('src/api/client.ts', "const r = await fetch(path, { method: 'GET' });"),
    (COMP, 'const label = "Danh sách tác vụ";'),
    (COMP, 'const token = data.capability;'),
    (COMP, "const token = 'short';"),
    (COMP, 'const secret = process.env.X;'),
    (COMP, "const url = '/scripts';"),
    (COMP, 'const m = document.cookie.match(/csrf_token=([^;]+)/);'),
]


@pytest.mark.parametrize('path,text,code', VIOLATIONS)
def test_violation_is_reported(path, text, code):
    found = scan_ui_source(path, text)
    codes = [item.rsplit(': ', 1)[1] for item in found]
    assert code in codes, found


@pytest.mark.parametrize('path,text', CLEAN)
def test_clean_text_is_not_reported(path, text):
    assert scan_ui_source(path, text) == []


def test_simulated_bom_file_is_reported():
    raw = b'\xef\xbb\xbfexport const a = 1;\n'
    found = scan_ui_source('src/a.ts', raw.decode('utf-8'))
    assert any(item.endswith(': bom') for item in found), found


def _ui_files():
    skipped = {'node_modules', 'dist'}
    return sorted(
        p
        for p in UI_SRC.rglob('*')
        if p.is_file() and p.suffix in ('.ts', '.tsx') and not skipped & set(p.relative_to(UI_SRC).parts)
    )


def _rel(p):
    return 'src/' + p.relative_to(UI_SRC).as_posix()


def test_current_ui_tree_has_no_violation():
    files = _ui_files()
    assert 'src/api/client.ts' in [_rel(p) for p in files]
    violations = []
    for p in files:
        violations += scan_ui_source(_rel(p), p.read_bytes().decode('utf-8'))
    assert violations == []


def test_fetch_only_in_api_client():
    hits = [_rel(p) for p in _ui_files() if re.search(r'\bfetch\s*\(', p.read_text(encoding='utf-8'))]
    assert hits == ['src/api/client.ts']
