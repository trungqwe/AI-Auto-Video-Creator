"""CP7-2 / RG-01: phiên sản xuất thật và bảo mật loopback.

Chạy `launcher.py start` thật hai lần (hồ sơ production), bắt URL /launch qua biến BROWSER (một tệp .cmd tạm ghi URL vào tệp tạm,
không bao giờ in capability), mở phiên bằng tools/real/cp7_browser_probe.js, rồi kiểm TLS loopback, /launch một lần và hết hạn,
/test-driver 404, Host và Origin lạ bị từ chối, CSRF bắt buộc, cờ cookie, canary 0 lần khớp. Phải chạy dưới quyền thường (không
"Run as administrator") vì nó khởi động ứng dụng. Trần chi phí 0 USD, không gọi AI. Cách dừng: `python tools/launcher/launcher.py stop`.
"""
import http.client
import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO / 'tools' / 'real') not in sys.path:
    sys.path.insert(0, str(REPO / 'tools' / 'real'))
if str(REPO / 'src') not in sys.path:
    sys.path.insert(0, str(REPO / 'src'))

import pytest  # noqa: E402

import cp7_common as c  # noqa: E402

LAUNCHER = REPO / 'tools' / 'launcher' / 'launcher.py'
PROBE = REPO / 'tools' / 'real' / 'cp7_browser_probe.js'
HOST, PORT = '127.0.0.1', 8443
DEADLINE = c.Deadline(20 * 60)  # hạn 20 phút cho cả tệp
CANARY_ALIAS = 'cp7-canary-probe'
EVIL = 'evil.example'


def _data_root():
    base = os.environ.get('AIAVC_DATA_DIR')
    return Path(base) if base else Path(os.environ['LOCALAPPDATA']) / 'AIAutoVideoCreator'


def _launcher(command, env):
    proc = subprocess.run([sys.executable, '-B', str(LAUNCHER), command], cwd=str(REPO), env=env, capture_output=True,
                          text=True, encoding='utf-8', errors='replace', timeout=DEADLINE.timeout(300), check=False)
    return proc.returncode, c.redact(proc.stdout + proc.stderr)


def _stop_launcher():
    """Dừng ứng dụng trong `finally`. Không dùng DEADLINE để vẫn dừng được khi hạn 20 phút đã hết; timeout 120 giây lớn hơn STOP_GRACE_SECONDS (60) của launcher."""
    env = dict(os.environ, PYTHONUTF8='1')
    proc = subprocess.run([sys.executable, '-B', str(LAUNCHER), 'stop'], cwd=str(REPO), env=env, capture_output=True, text=True,
                          encoding='utf-8', errors='replace', timeout=120, check=False)
    return proc.returncode, c.redact(proc.stdout + proc.stderr)


def _app_listening():
    try:
        with socket.create_connection((HOST, PORT), timeout=3):
            return True
    except OSError:
        return False


def _start_capturing(work, name):
    """Dừng ứng dụng đang chạy rồi start lại; trả đường dẫn tệp chứa URL /launch (không đọc ra ở đây)."""
    url_file = work / f'{name}.url'
    capture = work / 'capture_launch_url.cmd'
    if not capture.exists():
        capture.write_text('@echo off\r\n>"%CP7_LAUNCH_URL_FILE%" echo(%*\r\nexit /b 0\r\n', encoding='ascii')
    env = dict(os.environ, BROWSER=str(capture), CP7_LAUNCH_URL_FILE=str(url_file), PYTHONUTF8='1')
    rc, out = _launcher('stop', env)
    assert rc == 0, f'launcher stop failed: {out[-400:]}'
    rc, out = _launcher('start', env)
    assert rc == 0, f'launcher start failed: {out[-400:]}'
    for _ in range(120):
        if url_file.is_file() and url_file.stat().st_size > 0:
            return url_file
        time.sleep(1)
        DEADLINE.check()
    pytest.fail('launch URL was not captured within 120 s')


def _request(method, path, *, host_header=None, headers=None, body=None):
    conn = http.client.HTTPSConnection(HOST, PORT, timeout=DEADLINE.timeout(30), context=ssl._create_unverified_context())
    try:
        conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        conn.putheader('Host', host_header or f'{HOST}:{PORT}')
        for key, value in (headers or {}).items():
            conn.putheader(key, value)
        data = body.encode('utf-8') if isinstance(body, str) else body
        if data is not None:
            conn.putheader('Content-Length', str(len(data)))
        conn.endheaders(data)
        response = conn.getresponse()
        return response.status, response.read().decode('utf-8', errors='replace')
    finally:
        conn.close()


def _path_of(url_file):
    url = url_file.read_text(encoding='utf-8').strip()
    return url[url.index('/launch'):]


@pytest.fixture(scope='module')
def real(tmp_path_factory):
    from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore
    from controlplane.infrastructure.security.secret_redaction import SecretValue
    work = Path(tempfile.mkdtemp(prefix='cp7-2-'))
    store = DpapiSecretStore(_data_root() / 'vault')
    canary = f'cp7-canary-{uuid.uuid4().hex}'
    version = store.put(CANARY_ALIAS, SecretValue(canary))
    bodies = []
    try:
        # Lần 1: capability không dùng, để kiểm hết hạn sau 60 giây.
        first = _start_capturing(work, 'first')
        first_seen = time.monotonic()
        # Lần 2: capability dùng ngay qua trình duyệt thật; ứng dụng chạy tiếp từ lần này.
        time.sleep(max(0, 61 - (time.monotonic() - first_seen)))
        status, body = _request('GET', _path_of(first))
        bodies.append(body)
        expiry = status
        second = _start_capturing(work, 'second')
        # Host lạ với capability thật chưa dùng: phải 403 mà không tiêu thụ capability; probe ngay sau với Host đúng vẫn vào được,
        # nên 403 này chỉ có thể do Host.
        launch_evil_status, body = _request('GET', _path_of(second), host_header=f'{EVIL}:{PORT}')
        bodies.append(body)
        out_dir = work / 'probe'
        probe = subprocess.run(['node', str(PROBE), '--url-file', str(second), '--out', str(out_dir)], cwd=str(REPO),
                               capture_output=True, text=True, encoding='utf-8', errors='replace',
                               timeout=DEADLINE.timeout(180), check=False)
        result = json.loads(probe.stdout.strip().splitlines()[-1])
        assert probe.returncode == 0 and result['ok'], f'browser probe failed: {result}'
        yield {'work': work, 'first': first, 'second': second, 'probe': result, 'out': out_dir, 'canary': canary,
               'expiry_status': expiry, 'launch_evil_status': launch_evil_status, 'bodies': bodies,
               'cookies': json.loads((out_dir / 'cookies.json').read_text(encoding='utf-8'))}
    finally:
        try:
            try:
                store.revoke(CANARY_ALIAS, version)
            finally:
                shutil.rmtree(work, ignore_errors=True)
        finally:
            stop_rc, stop_out = _stop_launcher()
            assert stop_rc == 0, f'launcher stop failed in finally: {stop_out[-400:]}'
            assert not _app_listening(), f'launcher still listening on {HOST}:{PORT} after stop'


def _session_headers(real, *, csrf=True, origin=f'https://{HOST}:{PORT}'):
    jar = {cookie['name']: cookie['value'] for cookie in real['cookies']}
    headers = {'Cookie': f"cp_session={jar['cp_session']}; csrf_token={jar['csrf_token']}", 'Content-Type': 'application/json',
               'Idempotency-Key': str(uuid.uuid4())}
    if origin:
        headers['Origin'] = origin
    if csrf:
        headers['X-CSRF-Token'] = jar['csrf_token']
    return headers


def _pass(emit, item, *details):
    emit(c.report_line('RG-01', item, 'PASS'))
    for detail in details:
        emit(f'- {item}: {detail}')


def test_rg01_tls_loopback(real, emit):
    from cryptography import x509
    context = ssl._create_unverified_context()
    with socket.create_connection((HOST, PORT), timeout=DEADLINE.timeout(10)) as raw:
        with context.wrap_socket(raw, server_hostname=HOST) as tls:
            der = tls.getpeercert(binary_form=True)
            version = tls.version()
    cert = x509.load_der_x509_certificate(der)
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    ips = {str(ip) for ip in san.get_values_for_type(x509.IPAddress)}
    names = set(san.get_values_for_type(x509.DNSName))
    assert '127.0.0.1' in ips and 'localhost' in names, f'SAN ips={sorted(ips)} names={sorted(names)}'
    _pass(emit, 'tls_loopback', f'handshake={version} san_ip=127.0.0.1 san_dns=localhost')


def test_rg01_launch_one_time(real, emit):
    assert real['probe']['finalPath'] == '/', real['probe']
    status, body = _request('GET', _path_of(real['second']))
    real['bodies'].append(body)
    assert status == 403, status
    _pass(emit, 'launch_one_time', f"first_use_redirect_path={real['probe']['finalPath']} second_use_status={status}")


def test_rg01_launch_expiry(real, emit):
    assert real['expiry_status'] == 403, real['expiry_status']
    _pass(emit, 'launch_expiry', f"unused_capability_after_61s_status={real['expiry_status']}")


def test_rg01_test_driver_404(real, emit):
    status, body = _request('GET', '/test-driver/issue-capability')
    real['bodies'].append(body)
    assert status == 404, status
    _pass(emit, 'test_driver_404', f'GET /test-driver/issue-capability status={status}')


def test_rg01_host_rejected(real, emit):
    launch_status = real['launch_evil_status']
    api_status, body = _request('GET', '/v1/jobs', host_header=EVIL, headers=_session_headers(real, origin=None))
    real['bodies'].append(body)
    assert launch_status == 403 and api_status == 403, (launch_status, api_status)
    assert real['probe']['finalPath'] == '/', 'capability was consumed by the foreign-Host request'
    _pass(emit, 'host_rejected', f'/launch (capability thật, chưa dùng) status={launch_status}, sau đó Host đúng vẫn vào được; '
          f'/v1/jobs status={api_status} host={EVIL}')


def test_rg01_origin_rejected(real, emit):
    status, body = _request('POST', '/v1/batches', headers=_session_headers(real, origin=f'https://{EVIL}'), body='{}')
    real['bodies'].append(body)
    assert status == 403, status
    _pass(emit, 'origin_rejected', f'POST /v1/batches Origin=https://{EVIL} status={status} (body rỗng, không tạo lô)')


def test_rg01_csrf_required(real, emit):
    status, body = _request('POST', '/v1/batches', headers=_session_headers(real, csrf=False), body='{}')
    real['bodies'].append(body)
    assert status == 403, status
    _pass(emit, 'csrf_required', f'POST /v1/batches without X-CSRF-Token status={status} (body rỗng, không tạo lô)')


def test_rg01_cookie_flags(real, emit):
    flags = {cookie['name']: cookie for cookie in real['probe']['cookies']}
    session, csrf = flags['cp_session'], flags['csrf_token']
    assert session['httpOnly'] and session['secure'] and session['sameSite'] == 'Strict', session
    assert csrf['secure'] and csrf['sameSite'] == 'Strict', csrf
    _pass(emit, 'cookie_flags', 'cp_session=HttpOnly,Secure,SameSite=Strict csrf_token=Secure,SameSite=Strict')


def _texts(real):
    yield 'dom', (real['out'] / 'dom.html').read_text(encoding='utf-8', errors='replace')
    yield 'har', (real['out'] / 'session.har').read_text(encoding='utf-8', errors='replace')
    for i, body in enumerate(real['bodies']):
        yield f'body{i}', body
    logs = _data_root() / 'logs'
    for log in sorted(logs.glob('*.log')) if logs.is_dir() else []:
        yield f'log:{log.name}', log.read_text(encoding='utf-8', errors='replace')


def _real_secret_hits(texts):
    """Đếm số lần các bí mật thật mà ứng dụng đã giải mã xuất hiện trên các bề mặt.

    Canary nằm trong một alias mà ứng dụng không đọc, nên nó chỉ chứng minh kho không bị đổ ra ngoài. Refresh token Drive (ứng dụng
    giải mã khi dựng placement lúc start) và khoá 9Router là bí mật ứng dụng thật sự cầm. Giá trị lấy qua CredentialBroker, chỉ ở
    trong hàm này; kết quả chỉ gồm tên và số đếm.
    """
    from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore
    from controlplane.infrastructure.security.oauth_google_loopback import SECRET_REF as DRIVE_SECRET_REF
    from controlplane.security.broker import CredentialBroker
    ports = json.loads((REPO / 'tools' / 'launcher' / 'prod' / 'ports.json').read_text(encoding='utf-8'))
    aliases = {'drive_refresh_token': DRIVE_SECRET_REF, 'router_api_key': ports['router']['secret_ref']}
    broker = CredentialBroker(DpapiSecretStore(_data_root() / 'vault').export_vault(list(aliases.values())))
    hits, short = {}, []
    for name, alias in aliases.items():
        with broker.acquire_secret(alias) as handle:
            value = handle.get_secret_value()
            if len(value) < 16:
                short.append(name)
                continue
            for surface, text in texts.items():
                hits[f'{name}@{surface}'] = text.count(value)
    return hits, short


def test_rg01_canary_zero_hits(real, emit):
    texts = dict(_texts(real))
    hits = {name: text.count(real['canary']) for name, text in texts.items()}
    assert sum(hits.values()) == 0, {k: v for k, v in hits.items() if v}
    real_hits, short = _real_secret_hits(texts)
    assert not short, f'secret too short to search reliably: {short}'
    assert sum(real_hits.values()) == 0, {k: v for k, v in real_hits.items() if v}
    _pass(emit, 'canary_zero_hits', f'surfaces={len(texts)} (dom, har, response bodies, data-dir logs) canary_hits=0 '
          'real_secret_hits=0 (drive refresh token, 9Router key; giá trị chỉ trong bộ nhớ của test)')


def test_rg01_secret_scan(real, emit):
    found = {name: len(c.scan_secrets(text)) for name, text in _texts(real)}
    report = REPO / 'docs' / 'delivery-evidence' / 'cp7-2' / 'report.md'
    found['report'] = len(c.scan_secrets(report.read_text(encoding='utf-8'))) if report.is_file() else 0
    assert sum(found.values()) == 0, {k: v for k, v in found.items() if v}
    _pass(emit, 'secret_scan', f'surfaces={len(found)} secret_pattern_matches=0')
