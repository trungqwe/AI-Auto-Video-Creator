"""F-22: ma trận bao phủ test ID và acceptance contract 08 của F.

coveredIds: acceptance §8 mục 1 đến 7 của contract 08
"""
import ast
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
SELF = pathlib.Path(__file__).resolve()
REQUIRED_IDS = (
    'CT-RND-001', 'CT-RND-002', 'CT-RND-003', 'CT-RND-004', 'CT-RND-005', 'CT-RND-006',
    'CT-QC-001', 'CT-QC-002', 'TST-MEDIA-INV-007', 'TST-INT-INV-008', 'TST-E2E-INV-009',
    'TST-SEC-INV-012', 'TST-QC-INV-019', 'TST-SEC-INV-020', 'TST-E2E-001', 'TST-E2E-014',
    'TST-CTR-INV-001', 'TST-CTR-INV-002', 'TST-WF-INV-003',
)
GATES = (
    'FILE_PLAYABLE', 'DURATION_RANGE', 'VISUAL_HOOK_PRESENT', 'AUDIO_HOOK_PRESENT',
    'THUMBNAIL_PRESENT', 'SUBTITLE_BURNED_IN', 'KARAOKE_TIMING_VALID', 'VOICE_AUDIBLE',
    'ENGLISH_OUTPUT_VALID', 'OUTPUT_PROFILE_VALID', 'INFERENCE_DISCLOSURE_PRESENT',
    'VISUAL_CONTINUITY', 'AUDIO_MIX_QUALITY',
)
GATE_TEST_FILES = ('test_f12_quality_report.py', 'test_f13_technical_gates.py', 'test_f14_content_gates.py')
FORBIDDEN_PREFIXES = ('TST-MED-', 'TST-VOI-', 'TST-RND-', 'TST-EF-')


def _scan():
    files = []
    for part in ('unit', 'integration'):
        files.extend((ROOT / 'tests' / part / 'render').glob('test_f*.py'))
    scanned = {}
    for path in sorted(files):
        if path.resolve() == SELF:
            continue
        text = path.read_text(encoding='utf-8')
        tree = ast.parse(text)
        doc = ast.get_docstring(tree) or ''
        covered = '\n'.join(line for line in doc.splitlines() if line.strip().startswith('coveredIds:'))
        has_test = any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_')
            for node in ast.walk(tree)
        )
        scanned[path.name] = (text, covered, has_test)
    return scanned


FILES = _scan()


def test_scan_covers_slices_f01_to_f21_and_excludes_f22():
    assert {name[6:8] for name in FILES} == {f'{i:02d}' for i in range(1, 22)}


@pytest.mark.parametrize('code', REQUIRED_IDS)
def test_required_id_is_declared_by_a_file_with_a_test_function(code):
    pattern = re.compile(r'(?<![A-Za-z0-9-])' + re.escape(code) + r'(?![A-Za-z0-9-])')
    owners = [name for name, (_, covered, has_test) in FILES.items() if has_test and pattern.search(covered)]
    assert owners, f'{code} không có trong dòng coveredIds của tệp test_f nào có hàm test_'


@pytest.mark.parametrize('gate', GATES)
def test_every_qc_gate_name_appears_in_f12_f13_or_f14_tests(gate):
    pattern = re.compile(r'\b' + gate + r'\b')
    assert any(pattern.search(FILES[name][0]) for name in GATE_TEST_FILES), f'gate {gate} thiếu trong test F-12/F-13/F-14'


@pytest.mark.parametrize('name', sorted(FILES))
def test_no_file_uses_an_id_prefix_outside_the_catalog(name):
    text = FILES[name][0]
    assert [prefix for prefix in FORBIDDEN_PREFIXES if prefix in text] == []


def test_module_declares_covered_ids():
    assert any(line.startswith('coveredIds:') for line in (__doc__ or '').splitlines())
