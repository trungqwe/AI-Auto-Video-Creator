"""H-17: guard tĩnh form tạo lô cho chọn số luồng video song song (CP-4B-UI-SCREENS-FIX5).

coveredIds: CT-API-010, QR-UX-001
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[3]
UI = ROOT / 'src' / 'controlplane' / 'ui'
SRC = UI / 'src'
ASSETS = UI / 'dist' / 'assets'


def _read(*parts):
    return SRC.joinpath(*parts).read_text(encoding='utf-8')


def test_form_has_concurrency_select_and_loads_settings_once():
    form = _read('components', 'CommandForm.tsx')
    assert 'id="max-concurrent-select"' in form
    assert 'data-testid="max-concurrent-select"' in form
    assert 'useEffect' in form
    assert len(re.findall(r'fetchBatchSettings\(\)', form)) == 1


def test_form_locks_submit_while_settings_load():
    form = _read('components', 'CommandForm.tsx')
    assert re.search(r'const \[settingsLoading, setSettingsLoading\] = useState<boolean>\(true\)', form)
    assert 'setSettingsLoading(false)' in form
    assert 'disabled={loading || settingsLoading}' in form


def test_form_hides_select_when_max_not_above_one_and_sends_only_when_loaded():
    form = _read('components', 'CommandForm.tsx')
    assert re.search(r'\.max > 1', form)
    assert 'limits ? maxConcurrent : undefined' in form


def test_client_exposes_batch_settings_and_optional_concurrency():
    client = _read('api', 'client.ts')
    assert "'/v1/batch-settings'" in client
    assert re.search(r'fetchBatchSettings\(\): Promise<BatchSettings>', client)
    assert 'max_concurrent_videos' in client
    assert re.search(
        r'startProductionBatch\(\s*targetCount: number,\s*idempotencyKey: string,\s*maxConcurrentVideos\?: number\s*\)',
        client,
    )
    assert 'maxConcurrentVideos !== undefined' in client


def test_types_declare_batch_settings_without_any():
    types = _read('types', 'api.ts')
    match = re.search(r'export interface BatchSettings \{(.*?)\n\}', types, re.S)
    assert match, 'BatchSettings'
    body = match.group(1)
    assert 'max_concurrent_videos' in body
    for key in ('default', 'min', 'max'):
        assert re.search(rf'\b{key}: number;', body), key
    assert not re.search(r':\s*any\b|<any>|\bas any\b', types)


def test_bundle_contains_select_and_settings_endpoint():
    js = ' '.join(f.read_text(encoding='utf-8') for f in ASSETS.glob('*.js'))
    assert 'max-concurrent-select' in js
    assert '/v1/batch-settings' in js
