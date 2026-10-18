import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
BINDINGS_DIR = ROOT / 'docs/parallel-delivery/bindings'
FIXTURES_DIR = ROOT / 'tests/fixtures/contracts'
REGISTRY_PATH = ROOT / 'docs/parallel-delivery/contract-registry.yaml'
MODULES = frozenset('ABCDEFGHIJ')
FIELD_TYPES = {'string', 'integer', 'number', 'boolean', 'object', 'array', 'sha256', 'datetime'}
CONSTRAINTS = {'monotonic_word_timings'}
SHA256_RE = r'[0-9a-f]{64}'
DATETIME_RE = r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})'
SEMVER_RE = r'\d+\.\d+\.\d+'
SEAM_RE = r'[a-z0-9]+(-[a-z0-9]+)+'
ENTRY_RE = re.compile(
    r'^    - id: (\S+)\n'
    r'      seam: (\S+)\n'
    r'      path: (\S+)\n'
    r'      binding_version: "([^"]+)"\n'
    r'      contract_ref: (\S+)\n'
    r'      source_sha256: ([0-9a-f]{64})$',
    re.M,
)


def load_manifests() -> list[tuple[Path, dict]]:
    if not BINDINGS_DIR.is_dir():
        return []
    manifests = []
    for p in sorted(BINDINGS_DIR.glob('*.json')):
        data = json.loads(p.read_text(encoding='utf-8'))
        manifests.append((p, data))
    return manifests


def check_type(value, t: str) -> bool:
    if t == 'string':
        return isinstance(value, str)
    if t == 'integer':
        return isinstance(value, int) and not isinstance(value, bool)
    if t == 'number':
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == 'boolean':
        return isinstance(value, bool)
    if t == 'object':
        return isinstance(value, dict)
    if t == 'array':
        return isinstance(value, list)
    if t == 'sha256':
        return isinstance(value, str) and bool(re.fullmatch(SHA256_RE, value))
    if t == 'datetime':
        return isinstance(value, str) and bool(re.fullmatch(DATETIME_RE, value))
    return False


def _monotonic_word_timings(payload: dict) -> bool:
    words = payload.get('words')
    if not isinstance(words, list):
        return False
    voice_duration_ms = payload.get('voice_duration_ms')
    has_duration = isinstance(voice_duration_ms, int) and not isinstance(voice_duration_ms, bool)

    prev_start = None
    prev_end = None
    for word in words:
        if not isinstance(word, dict):
            return False
        start_ms = word.get('start_ms')
        end_ms = word.get('end_ms')
        if not (isinstance(start_ms, int) and not isinstance(start_ms, bool)):
            return False
        if not (isinstance(end_ms, int) and not isinstance(end_ms, bool)):
            return False
        if not (0 <= start_ms < end_ms):
            return False
        if prev_start is not None and start_ms < prev_start:
            return False
        if prev_end is not None and end_ms < prev_end:
            return False
        if has_duration and end_ms > voice_duration_ms:
            return False
        prev_start = start_ms
        prev_end = end_ms
    return True


def validate_payload(entity: dict, payload) -> list[tuple[str, str]]:
    if not isinstance(payload, dict):
        return [('wrong_type', '$')]

    errors: list[tuple[str, str]] = []
    fields = entity.get('fields', [])
    for f in fields:
        name = f['name']
        req = f.get('required', False)
        ftype = f.get('type')
        if name not in payload:
            if req:
                errors.append(('missing_required', name))
            continue
        val = payload[name]
        if val is None:
            if req:
                errors.append(('wrong_type', name))
            continue
        if not check_type(val, ftype):
            errors.append(('wrong_type', name))
            continue
        if 'items' in f and isinstance(val, list):
            item_type = f['items']
            if any(not check_type(item, item_type) for item in val):
                errors.append(('wrong_type', name))
                continue
        if 'enum' in f:
            if val not in f['enum']:
                errors.append(('enum_violation', name))
                continue

    for f_name in entity.get('forbidden_fields', []):
        if f_name in payload:
            errors.append(('forbidden_field', f_name))

    constraints = set(entity.get('constraints', []))
    if 'monotonic_word_timings' in constraints:
        if isinstance(payload.get('words'), list):
            words_has_error = any(fld == 'words' for _, fld in errors)
            if not words_has_error:
                if not _monotonic_word_timings(payload):
                    errors.append(('constraint_violation', 'words'))

    return errors


def manifest_problems(path: Path, manifest: dict) -> list[str]:
    problems = []
    if not isinstance(manifest, dict):
        return ['manifest is not a dict']

    if manifest.get('schema') != 'contract-binding/v1':
        problems.append("schema != 'contract-binding/v1'")
    seam = manifest.get('seam', '')
    if not (re.fullmatch(SEAM_RE, seam) and seam == path.stem):
        problems.append(f"seam mismatch or invalid: {seam} vs {path.stem}")
    binding_id = manifest.get('binding_id', '')
    if not (isinstance(binding_id, str) and binding_id.startswith('BINDING-')):
        problems.append("binding_id must start with 'BINDING-'")
    binding_version = manifest.get('binding_version', '')
    if not (isinstance(binding_version, str) and re.fullmatch(SEMVER_RE, binding_version)):
        problems.append("binding_version must match SEMVER_RE")

    modules = manifest.get('modules')
    if not (isinstance(modules, list) and len(modules) >= 2 and len(modules) == len(set(modules)) and set(modules).issubset(MODULES)):
        problems.append("modules must be a unique list of >= 2 items in MODULES")
    producer = manifest.get('producer')
    if not (isinstance(producer, str) and len(producer) > 0):
        problems.append("producer must be non-empty string")
    consumers = manifest.get('consumers')
    if not (isinstance(consumers, list) and len(consumers) > 0):
        problems.append("consumers must be non-empty list")
    contract_ref = manifest.get('contract_ref', '')
    if not (isinstance(contract_ref, str) and contract_ref.startswith('CONTRACT-')):
        problems.append("contract_ref must start with 'CONTRACT-'")

    source = manifest.get('source', {})
    if not isinstance(source, dict):
        problems.append("source must be a dict")
        source = {}
    src_path_str = source.get('path', '')
    if not (isinstance(src_path_str, str) and src_path_str.startswith('docs/09-contracts/') and (ROOT / src_path_str).is_file()):
        problems.append("source.path must start with 'docs/09-contracts/' and exist")
    src_sections = source.get('sections')
    if not (isinstance(src_sections, list) and len(src_sections) > 0):
        problems.append("source.sections must be non-empty list")
    else:
        if (ROOT / src_path_str).is_file():
            src_text = (ROOT / src_path_str).read_text(encoding='utf-8')
            for sec in src_sections:
                if sec not in src_text:
                    problems.append(f"section {sec} not found in source {src_path_str}")
    src_sha256 = source.get('sha256', '')
    if not (isinstance(src_sha256, str) and re.fullmatch(SHA256_RE, src_sha256)):
        problems.append("source.sha256 must match SHA256_RE")

    compatibility = manifest.get('compatibility', {})
    if not isinstance(compatibility, dict):
        problems.append("compatibility must be a dict")
        compatibility = {}
    if compatibility.get('mode') != 'additive_optional_only':
        problems.append("compatibility.mode != 'additive_optional_only'")
    breaking_change = compatibility.get('breaking_change', '')
    if 'MIGRATE' not in breaking_change:
        problems.append("'MIGRATE' must be in compatibility.breaking_change")

    entities = manifest.get('entities')
    if not (isinstance(entities, list) and len(entities) > 0):
        problems.append("entities must be non-empty list")
    else:
        entity_names = [e.get('name') for e in entities if isinstance(e, dict)]
        if len(entity_names) != len(set(entity_names)):
            problems.append("entity names must be unique")
        for ent in entities:
            if not isinstance(ent, dict):
                problems.append("entity must be a dict")
                continue
            name = ent.get('name', '')
            section = ent.get('section', '')
            if isinstance(src_sections, list) and section not in src_sections:
                problems.append(f"entity {name} section {section} not in source.sections")
            fields = ent.get('fields')
            if not (isinstance(fields, list) and len(fields) > 0):
                problems.append(f"entity {name} fields must be non-empty list")
                continue
            field_names = [f.get('name') for f in fields if isinstance(f, dict)]
            if len(field_names) != len(set(field_names)):
                problems.append(f"entity {name} field names must be unique")
            has_required = False
            for f in fields:
                if not isinstance(f, dict):
                    problems.append(f"entity {name} field must be a dict")
                    continue
                ftype = f.get('type')
                if ftype not in FIELD_TYPES:
                    problems.append(f"entity {name} field {f.get('name')} type {ftype} not in FIELD_TYPES")
                if 'items' in f and f['items'] not in FIELD_TYPES:
                    problems.append(f"entity {name} field {f.get('name')} items {f.get('items')} not in FIELD_TYPES")
                req = f.get('required')
                if not isinstance(req, bool):
                    problems.append(f"entity {name} field {f.get('name')} required must be bool")
                if req is True:
                    has_required = True
                if 'enum' in f:
                    enum_vals = f['enum']
                    if not (isinstance(enum_vals, list) and len(enum_vals) > 0 and all(isinstance(x, str) and x for x in enum_vals)):
                        problems.append(f"entity {name} field {f.get('name')} enum must be non-empty list of non-empty strings")
            if not has_required:
                problems.append(f"entity {name} must have at least 1 required field")
            forbidden = set(ent.get('forbidden_fields', []))
            if not forbidden.isdisjoint(set(field_names)):
                problems.append(f"entity {name} forbidden_fields overlaps with fields")
            constraints = set(ent.get('constraints', []))
            if not constraints.issubset(CONSTRAINTS):
                problems.append(f"entity {name} constraints must be subset of CONSTRAINTS")

    return problems


def source_drift(manifest: dict, root: Path = ROOT) -> str | None:
    src_rel = manifest.get('source', {}).get('path', '')
    src_path = root / src_rel
    if not src_path.is_file():
        return f"missing source {src_rel}"
    actual = hashlib.sha256(src_path.read_bytes()).hexdigest()
    expected = manifest.get('source', {}).get('sha256', '')
    if actual != expected:
        return f"drift: {src_rel} expected {expected} actual {actual}"
    return None


def load_fixture(seam: str) -> dict | None:
    p = FIXTURES_DIR / seam / 'payloads.json'
    if p.is_file():
        return json.loads(p.read_text(encoding='utf-8'))
    return None


def parse_registry_bindings(text: str) -> tuple[list[dict], int]:
    m = re.search(r'^bindings:\s*$', text, re.M)
    if not m:
        return ([], 0)
    start_pos = m.end()
    rest = text[start_pos:]
    m_next = re.search(r'^\S', rest, re.M)
    if m_next:
        block = rest[:m_next.start()]
    else:
        block = rest

    count = len(re.findall(r'^    - id: ', block, re.M))
    entries = []
    for match in ENTRY_RE.finditer(block):
        entries.append({
            'id': match.group(1),
            'seam': match.group(2),
            'path': match.group(3),
            'binding_version': match.group(4),
            'contract_ref': match.group(5),
            'source_sha256': match.group(6),
        })
    return (entries, count)


def parse_registry_contracts(text: str) -> dict:
    return dict(re.findall(r'^  - id: (CONTRACT-[A-Z0-9-]+)\n    source: (\S+)$', text, re.M))
