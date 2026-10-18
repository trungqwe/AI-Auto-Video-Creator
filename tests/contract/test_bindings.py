from pathlib import Path
import sys

CONTRACT_DIR = Path(__file__).resolve().parent
if str(CONTRACT_DIR) not in sys.path:
    sys.path.insert(0, str(CONTRACT_DIR))

import pytest
from binding_validator import (
    BINDINGS_DIR,
    REGISTRY_PATH,
    ROOT,
    check_type,
    load_fixture,
    load_manifests,
    manifest_problems,
    parse_registry_bindings,
    parse_registry_contracts,
    source_drift,
    validate_payload,
)

MANIFESTS = load_manifests()
BY_SEAM = {m['seam']: m for _, m in MANIFESTS}

VALID_CASES = []
INVALID_CASES = []
ENTITY_CASES = []


def _entity(seam: str, name: str) -> dict:
    m = BY_SEAM[seam]
    for ent in m['entities']:
        if ent['name'] == name:
            return ent
    raise KeyError(f"Entity {name} not found in seam {seam}")


for _, m in MANIFESTS:
    seam = m['seam']
    fix = load_fixture(seam)
    if fix and isinstance(fix.get('entities'), dict):
        for ent_name, ent_data in fix['entities'].items():
            valid_list = ent_data.get('valid', [])
            for i, p in enumerate(valid_list):
                VALID_CASES.append((seam, ent_name, i, p))
            for case in ent_data.get('invalid', []):
                INVALID_CASES.append((seam, ent_name, case))
            if valid_list:
                ENTITY_CASES.append((seam, ent_name))


def test_inventory_readme_and_minimum_seams():
    readme = BINDINGS_DIR / 'README.md'
    assert readme.is_file(), "bindings/README.md must exist"
    assert len(MANIFESTS) >= 6, "at least six seam manifests are required"
    text = readme.read_text(encoding='utf-8')
    for _, m in MANIFESTS:
        assert m['seam'] in text, f"README must contain seam {m['seam']}"
    assert 'chỉ được thêm trường tuỳ chọn' in text
    assert 'MIGRATE' in text
    assert 'bindingRefs' in text


@pytest.mark.parametrize("path, m", MANIFESTS, ids=[p.stem for p, _ in MANIFESTS])
def test_manifest_structure(path, m):
    problems = manifest_problems(path, m)
    assert problems == []


@pytest.mark.parametrize("path, m", MANIFESTS, ids=[p.stem for p, _ in MANIFESTS])
def test_manifest_sha256_matches_current_contract(path, m):
    drift = source_drift(m)
    assert drift is None


@pytest.mark.parametrize("path, m", MANIFESTS, ids=[p.stem for p, _ in MANIFESTS])
def test_drift_detection_is_not_vacuous(path, m, tmp_path):
    assert len(MANIFESTS) > 0
    src_file = ROOT / m['source']['path']
    dest_file = tmp_path / m['source']['path']
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    dest_file.write_bytes(src_file.read_bytes() + b"\n<!-- drift -->\n")
    assert source_drift(m, tmp_path) is not None
    assert source_drift(m, tmp_path / 'empty') is not None


@pytest.mark.parametrize("path, m", MANIFESTS, ids=[p.stem for p, _ in MANIFESTS])
def test_fixture_covers_every_entity(path, m):
    seam = m['seam']
    fix = load_fixture(seam)
    assert fix is not None, f"Fixture for seam {seam} must exist"
    assert fix.get('seam') == seam
    assert fix.get('binding_version') == m['binding_version']
    manifest_entity_names = {ent['name'] for ent in m['entities']}
    fixture_entity_names = set(fix.get('entities', {}).keys())
    assert fixture_entity_names == manifest_entity_names
    for name in manifest_entity_names:
        ent_fix = fix['entities'][name]
        assert len(ent_fix.get('valid', [])) >= 1, f"Entity {name} must have >= 1 valid payload"
        assert len(ent_fix.get('invalid', [])) >= 1, f"Entity {name} must have >= 1 invalid payload"


@pytest.mark.parametrize(
    "seam, entity_name, i, payload",
    VALID_CASES,
    ids=[f"{s}/{e}/{i}" for s, e, i, _ in VALID_CASES],
)
def test_valid_payload_is_accepted(seam, entity_name, i, payload):
    ent = _entity(seam, entity_name)
    errors = validate_payload(ent, payload)
    assert errors == []


@pytest.mark.parametrize(
    "seam, entity_name",
    ENTITY_CASES,
    ids=[f"{s}/{e}" for s, e in ENTITY_CASES],
)
def test_unknown_optional_field_is_tolerated(seam, entity_name):
    ent = _entity(seam, entity_name)
    fix = load_fixture(seam)
    valid_payload = fix['entities'][entity_name]['valid'][0]
    payload = dict(valid_payload, x_future_optional_field='additive')
    errors = validate_payload(ent, payload)
    assert errors == []


@pytest.mark.parametrize(
    "seam, entity_name, case",
    INVALID_CASES,
    ids=[f"{s}/{e}/{c['case']}" for s, e, c in INVALID_CASES],
)
def test_invalid_payload_is_rejected_for_the_declared_reason(seam, entity_name, case):
    ent = _entity(seam, entity_name)
    errors = validate_payload(ent, case['payload'])
    expected = (case['expected_error']['code'], case['expected_error']['field'])
    assert errors == [expected]


def test_validator_type_rules():
    assert check_type(True, 'integer') is False
    assert check_type(1, 'integer') is True
    assert check_type('A' * 64, 'sha256') is False
    assert check_type('0' * 64, 'sha256') is True
    assert check_type('2026-10-18', 'datetime') is False
    assert check_type('2026-10-18T08:00:00Z', 'datetime') is True
    assert validate_payload({'fields': [{'name': 'a', 'type': 'string', 'required': True}]}, {}) == [('missing_required', 'a')]


def test_registry_binds_every_manifest():
    text = REGISTRY_PATH.read_text(encoding='utf-8')
    entries, count = parse_registry_bindings(text)
    assert len(entries) > 0 and count == len(entries), "registry bindings entries must not be empty and match count"
    ids = [e['id'] for e in entries]
    seams = [e['seam'] for e in entries]
    assert len(ids) == len(set(ids)), "duplicate binding ids in registry"
    assert len(seams) == len(set(seams)), "duplicate binding seams in registry"
    expected_paths = {'docs/parallel-delivery/bindings/' + p.name for p, _ in MANIFESTS}
    assert {e['path'] for e in entries} == expected_paths
    contracts = parse_registry_contracts(text)
    for e in entries:
        assert (ROOT / e['path']).is_file(), f"Binding file {e['path']} does not exist"
        m = BY_SEAM[e['seam']]
        assert m['binding_id'] == e['id']
        assert m['binding_version'] == e['binding_version']
        assert m['source']['sha256'] == e['source_sha256']
        assert m['contract_ref'] == e['contract_ref']
        assert e['contract_ref'] in contracts, f"Contract ref {e['contract_ref']} not in registry contracts"
        assert contracts[e['contract_ref']] == m['source']['path']


def test_errata_cite_canonical_sources():
    errata_dir = ROOT / 'docs/parallel-delivery/errata'
    filenames = ['m3-a.md', 'm4-ci.md', 'm5-d.md', 'm6-ef.md', 'm7-integration.md']
    for fn in filenames:
        p = errata_dir / fn
        assert p.is_file(), f"Errata file {fn} must exist"
        content = p.read_text(encoding='utf-8')
        assert 'Nguồn chuẩn' in content, f"{fn} must contain 'Nguồn chuẩn'"
        assert 'docs/09-contracts/' in content, f"{fn} must contain 'docs/09-contracts/'"
        assert 'docs/10-test-strategy.md' in content, f"{fn} must contain 'docs/10-test-strategy.md'"
        if fn == 'm6-ef.md':
            assert 'không dùng' in content, f"{fn} must contain 'không dùng'"
            assert 'IMPL-PLAN-E' in content, f"{fn} must contain 'IMPL-PLAN-E'"
            assert 'IMPL-PLAN-F' in content, f"{fn} must contain 'IMPL-PLAN-F'"
        if fn == 'm7-integration.md':
            assert 'không phải bằng chứng' in content, f"{fn} must contain 'không phải bằng chứng'"


def test_text_hygiene():
    check_dirs = [
        ROOT / 'docs/parallel-delivery/bindings',
        ROOT / 'docs/parallel-delivery/errata',
        ROOT / 'tests/fixtures/contracts',
        ROOT / 'tests/contract',
        ROOT / 'docs/delivery-evidence/cp1-contract-binding',
    ]
    files = []
    for d in check_dirs:
        if d.is_dir():
            for ext in ('*.md', '*.json', '*.py'):
                files.extend(sorted(d.rglob(ext)))
    for p in files:
        raw = p.read_bytes()
        assert not raw.startswith(b'\xef\xbb\xbf'), f"{p} must not have BOM"
        assert b'\r' not in raw, f"{p} must use LF only, found CR"
        text = raw.decode('utf-8')
        assert raw.endswith(b'\n'), f"{p} must end with newline"
        lines = text.split('\n')
        if lines and lines[-1] == '':
            lines = lines[:-1]
        for line_no, line in enumerate(lines, 1):
            assert not (line.endswith(' ') or line.endswith('\t')), f"{p}:{line_no} trailing whitespace"
