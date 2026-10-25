"""CP7-1 / RG-01: test đơn vị của tools/real/cp7_common.py và tiền kiểm runtime thật."""
import hashlib
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
if str(REPO / 'tools' / 'real') not in sys.path:
    sys.path.insert(0, str(REPO / 'tools' / 'real'))

import pytest  # noqa: E402

import cp7_common as c  # noqa: E402

# Giá trị giả được ghép từ mảnh để mã nguồn không chứa nguyên mẫu bí mật.
FAKE_SECRETS = {
    'google_api_key': 'AI' + 'za' + 'Q' * 35,
    'google_oauth_access_token': 'ya' + '29.' + 'a' * 40,
    'google_oauth_refresh_token': '1/' + '/' + 'b' * 40,
    'google_oauth_client_secret': 'GOC' + 'SPX-' + 'c' * 28,
    'pem_private_key': '-' * 5 + 'BEGIN PRIVATE KEY' + '-' * 5,
    'canary': 'cp7-' + 'canary',
}


@pytest.mark.parametrize('kind', sorted(FAKE_SECRETS))
def test_unit_scan_secrets_detects_each_kind(kind):
    secret = FAKE_SECRETS[kind]
    found = c.scan_secrets(f'trước {secret} sau')
    assert [m.kind for m in found] == [kind]
    assert secret not in repr(found)


def test_unit_scan_secrets_detects_short_api_key_lookalike():
    assert [m.kind for m in c.scan_secrets('AI' + 'za' + 'z' * 20)] == ['google_api_key']


def test_unit_scan_secrets_reports_one_based_line_and_column():
    found = c.scan_secrets('dòng một\nkhóa: ' + FAKE_SECRETS['google_api_key'])
    assert (found[0].line, found[0].column) == (2, 7)


def test_unit_scan_secrets_clean_text_has_no_match():
    assert c.scan_secrets('AIzaShort 1/2 ya29 -----BEGIN CERTIFICATE----- Tiếng Việt có dấu') == []


def test_unit_scan_secrets_rejects_non_text():
    with pytest.raises(TypeError):
        c.scan_secrets(b'bytes')


@pytest.mark.parametrize('kind', sorted(FAKE_SECRETS))
def test_unit_redact_removes_secret_value(kind):
    secret = FAKE_SECRETS[kind]
    out = c.redact(f'a {secret} b')
    assert secret not in out
    assert f'[REDACTED:{kind}]' in out
    assert c.scan_secrets(out) == []


@pytest.mark.parametrize('status', ['PASS', 'FAIL', 'BLOCKED', 'NOT_OBSERVED'])
def test_unit_report_line_format(status):
    assert c.report_line('RG-01', 'ffmpeg_pin', status) == f'RG-01.ffmpeg_pin: {status}'


@pytest.mark.parametrize('gate, item, status', [
    ('RG-1', 'x', 'PASS'), ('rg-01', 'x', 'PASS'), ('RG-01', '', 'PASS'),
    ('RG-01', 'has space', 'PASS'), ('RG-01', 'Upper', 'PASS'),
    ('RG-01', 'x', 'pass'), ('RG-01', 'x', 'OK'),
])
def test_unit_report_line_rejects_invalid_fields(gate, item, status):
    with pytest.raises(ValueError):
        c.report_line(gate, item, status)


def test_unit_report_line_never_echoes_secret_value():
    secret = FAKE_SECRETS['google_api_key']
    with pytest.raises(ValueError) as info:
        c.report_line('RG-01', secret, 'PASS')
    assert secret not in str(info.value)


class _ReadOnlyLedger:
    def __init__(self, records):
        self._records = records
        self.calls = []

    def records(self, workspace_id, window_start, window_end):
        self.calls.append((workspace_id, window_start, window_end))
        return tuple(self._records)

    def append(self, *args, **kwargs):
        raise AssertionError('CostGuard must not write to the ledger')


def _rec(actual, estimated, currency='USD'):
    return SimpleNamespace(actual_cost=actual, estimated_cost=estimated, currency=currency)


def test_unit_cost_guard_zero_ceiling_allows_zero_spend():
    assert c.CostGuard(0, lambda: Decimal(0)).check() == Decimal(0)


def test_unit_cost_guard_stops_when_spend_exceeds_ceiling():
    with pytest.raises(c.CostCeilingExceeded):
        c.CostGuard(0, lambda: Decimal('0.01')).check()


def test_unit_cost_guard_additional_and_remaining():
    guard = c.CostGuard(5, lambda: Decimal(1))
    assert guard.check() == Decimal(4)
    assert guard.check(additional_usd=4) == Decimal(0)
    with pytest.raises(c.CostCeilingExceeded):
        guard.check(additional_usd='4.01')


def test_unit_cost_guard_rejects_negative_amounts():
    with pytest.raises(ValueError):
        c.CostGuard(-1, lambda: Decimal(0))
    with pytest.raises(ValueError):
        c.CostGuard(1, lambda: Decimal(-1)).spent()


def test_unit_cost_guard_from_ledger_read_only():
    ledger = _ReadOnlyLedger([_rec(Decimal('1.5'), Decimal(9)), _rec(None, Decimal('0.25'))])
    guard = c.CostGuard.from_ledger(ledger, 'ws', 'start', 'end', Decimal(2))
    assert guard.spent() == Decimal('1.75')
    assert ledger.calls == [('ws', 'start', 'end')]
    with pytest.raises(c.CostCeilingExceeded):
        c.CostGuard.from_ledger(ledger, 'ws', 'start', 'end', Decimal('1.5')).check()


def test_unit_cost_guard_from_ledger_rejects_non_usd_record():
    ledger = _ReadOnlyLedger([_rec(Decimal(1), Decimal(1), currency='EUR')])
    with pytest.raises(ValueError):
        c.CostGuard.from_ledger(ledger, 'ws', 'start', 'end', Decimal(5)).spent()


class _Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def test_unit_deadline_is_a_hard_stop():
    clock = _Clock()
    deadline = c.Deadline(10, clock=clock)
    assert not deadline.expired()
    assert deadline.remaining() == 10
    deadline.check()
    clock.now += 9.5
    assert deadline.remaining() == pytest.approx(0.5)
    clock.now += 1
    assert deadline.expired()
    assert deadline.remaining() == 0
    with pytest.raises(c.DeadlineExceeded):
        deadline.check()
    with pytest.raises(c.DeadlineExceeded):
        deadline.timeout()


def test_unit_deadline_timeout_is_capped_by_remaining():
    deadline = c.Deadline(10, clock=_Clock())
    assert deadline.timeout(3) == 3
    assert deadline.timeout() == 10
    assert deadline.timeout(30) == 10


@pytest.mark.parametrize('seconds', [0, -1])
def test_unit_deadline_rejects_non_positive_seconds(seconds):
    with pytest.raises(ValueError):
        c.Deadline(seconds)


@pytest.mark.parametrize('args, expected', [
    (['tests'], False), ([], False), (['tests/m2'], False), (['.'], False),
    (['tests/real'], True), (['tests/real/test_cp7_preflight.py'], True),
    (['tests/real/test_cp7_preflight.py::test_x'], True),
    (['-q', '-p', 'no:cacheprovider', 'tests/real/test_cp7_preflight.py'], True),
    (['tests', 'tests/real'], True),
])
def test_unit_explicit_real_request(args, expected):
    assert c.explicit_real_request(args, REPO, REPO / 'tests' / 'real') is expected


def test_unit_explicit_real_request_resolves_against_invocation_dir():
    real = REPO / 'tests' / 'real'
    assert c.explicit_real_request(['test_cp7_preflight.py'], real, real) is True
    assert c.explicit_real_request(['real'], REPO / 'tests', real) is True


def _load_conftest():
    spec = importlib.util.spec_from_file_location('cp7_real_conftest_under_test', Path(__file__).with_name('conftest.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _config(args, invocation_dir=REPO):
    return SimpleNamespace(invocation_params=SimpleNamespace(args=args, dir=invocation_dir))


def test_unit_conftest_ignores_real_tests_without_explicit_path():
    module = _load_conftest()
    target = Path(__file__).resolve()
    assert module.pytest_ignore_collect(target, _config(['tests'])) is True
    assert module.pytest_ignore_collect(target, _config([])) is True
    assert module.pytest_ignore_collect(target, _config(['tests/m2'])) is True


def test_unit_conftest_collects_real_tests_with_explicit_path():
    module = _load_conftest()
    target = Path(__file__).resolve()
    assert module.pytest_ignore_collect(target, _config(['tests/real/test_cp7_preflight.py'])) is None
    assert module.pytest_ignore_collect(target, _config(['tests/real'])) is None


def test_unit_conftest_does_not_ignore_paths_outside_real():
    module = _load_conftest()
    assert module.pytest_ignore_collect(REPO / 'tests' / 'm2' / 'conftest.py', _config(['tests'])) is None


LOCK = REPO / 'tools' / 'runtime' / 'runtime.lock.json'
REPORT = REPO / 'docs' / 'delivery-evidence' / 'cp7-1' / 'report.md'
FFMPEG_EXE = Path('C:/ffmpeg/bin/ffmpeg.exe')
FFMPEG_SHA256 = 'f845a09b5467cf11651385e0be0dd4df6f70519264f8af2115e3acd6ab7f9480'
CONTAINER_PINS = (('aiavc-postgres', 'postgresql_image'), ('aiavc-temporal', 'temporal_server_binary'))
LOOPBACK_PORTS = (57028, 7233, 8443)
ROUTER_ADDRESS = ('127.0.0.1', 20128)
MIN_VRAM_MIB = 12000  # thẻ 12 GB danh định; nvidia-smi thường báo dưới 12288 MiB
MIN_FREE_BYTES = 50 * 1024 ** 3
DEADLINE = c.Deadline(240)  # kiểm tra tự kết thúc dưới 5 phút


def _pins():
    return json.loads(LOCK.read_text(encoding='utf-8'))['pins']


def _run(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=DEADLINE.timeout(30), check=False)
    except FileNotFoundError:
        pytest.fail(f'{args[0]} is not installed or not on PATH')


def _pass(emit, item, *details):
    emit(c.report_line('RG-01', item, 'PASS'))
    for detail in details:
        emit(f'- {item}: {detail}')


def test_rg01_ffmpeg_pin(emit):
    assert _pins()['ffmpeg']['sha256'] == FFMPEG_SHA256
    assert FFMPEG_EXE.is_file(), 'ffmpeg.exe missing at the pinned path'
    digest = hashlib.sha256()
    with FFMPEG_EXE.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    assert digest.hexdigest() == FFMPEG_SHA256
    _pass(emit, 'ffmpeg_pin', f'sha256={digest.hexdigest()} path={FFMPEG_EXE}')


def test_rg01_image_digests(emit):
    pins = _pins()
    details = []
    for container, pin_key in CONTAINER_PINS:
        expected = pins[pin_key]['sha256']
        state = _run(['docker', 'inspect', '--format', '{{.State.Running}} {{.Image}}', container])
        assert state.returncode == 0, f'{container} container not found'
        running, image_id = state.stdout.split()
        assert running == 'true', f'{container} is not running'
        image = _run(['docker', 'image', 'inspect', '--format', '{{json .RepoDigests}}', image_id])
        assert image.returncode == 0, f'{container} image not found'
        digests = json.loads(image.stdout) + [image_id]
        assert any(d.endswith('sha256:' + expected) for d in digests), f'{container} digest differs from runtime.lock.json'
        details.append(f'{container} sha256={expected}')
    _pass(emit, 'image_digests', *details)


def _listening(protocol):
    proc = _run(['netstat', '-ano', '-p', protocol])
    assert proc.returncode == 0, f'netstat {protocol} failed'
    rows = []
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[0] == 'TCP' and parts[3] == 'LISTENING':
            host, _, port = parts[1].rpartition(':')
            rows.append((host, int(port)))
    return rows


def test_rg01_loopback_ports(emit):
    rows = _listening('TCP') + _listening('TCPv6')
    for port in LOOPBACK_PORTS:
        hosts = sorted({host for host, p in rows if p == port})
        assert hosts, f'port {port} is not listening'
        assert hosts == ['127.0.0.1'], f'port {port} binds {hosts}'
    _pass(emit, 'loopback_ports', 'ports=57028,7233,8443 bind=127.0.0.1 only')


def test_rg01_gpu(emit):
    proc = _run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader,nounits'])
    assert proc.returncode == 0, 'nvidia-smi failed'
    cards = [[part.strip() for part in line.split(',')] for line in proc.stdout.splitlines() if line.strip()]
    matches = [card for card in cards if 'RTX 4070 SUPER' in card[0]]
    assert matches, 'RTX 4070 SUPER not reported'
    vram = int(matches[0][1])
    assert vram >= MIN_VRAM_MIB, f'VRAM {vram} MiB below {MIN_VRAM_MIB} MiB'
    _pass(emit, 'gpu', f'name={matches[0][0]} memory_total_mib={vram} threshold_mib={MIN_VRAM_MIB}')


def _data_root():
    base = os.environ.get('AIAVC_DATA_DIR')
    return Path(base) if base else Path(os.environ['LOCALAPPDATA']) / 'AIAutoVideoCreator'


def test_rg01_disk(emit):
    anchor = _data_root().resolve().anchor
    free = shutil.disk_usage(anchor).free
    assert free >= MIN_FREE_BYTES, f'free {free} bytes below {MIN_FREE_BYTES}'
    _pass(emit, 'disk', f'drive={anchor} free_gib={free / 1024 ** 3:.1f} threshold_gib=50')


def test_rg01_router_port(emit):
    with socket.create_connection(ROUTER_ADDRESS, timeout=DEADLINE.timeout(5)):
        pass
    _pass(emit, 'router_port', 'tcp=127.0.0.1:20128 open')


PORTS_CONFIG = REPO / 'tools' / 'launcher' / 'prod' / 'ports.json'


def test_rg01_secret_scan(emit):
    from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore
    from controlplane.infrastructure.security.oauth_google_loopback import SECRET_REF
    # Các alias production cần: token Drive (OAuth) và khóa 9Router (PP-2, tools/launcher/prod/ports.json); chỉ kiểm tồn tại.
    router_ref = json.loads(PORTS_CONFIG.read_text(encoding='utf-8'))['router']['secret_ref']
    store = DpapiSecretStore(_data_root() / 'vault')
    missing = [alias for alias in (SECRET_REF, router_ref) if store.current_version(alias) is None]
    assert not missing, f'DPAPI vault lacks required aliases: {missing}'
    report = REPORT.read_text(encoding='utf-8') if REPORT.is_file() else ''
    assert c.scan_secrets(report) == [], 'report.md contains secret patterns'
    _pass(emit, 'secret_scan', f'dpapi_aliases={SECRET_REF},{router_ref} present (existence only) report_matches=0')
