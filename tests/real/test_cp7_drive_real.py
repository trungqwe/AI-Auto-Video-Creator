"""CP7-3 / RG-02: Drive, OAuth và toàn vẹn trên tài khoản Google Drive thật.

Dùng DriveObjectStore với broker token thật (refresh token trong kho DPAPI, chỉ giải mã trong tiến trình test). Tải các tệp ngẫu nhiên
1, 9 và 40 MiB vào AI-Auto-Video-Creator/cp7-fixture/<runId>/, đối chiếu md5 và sha256, kiểm 409 khi upload lại cùng file ID, phiên
resumable 404 thật thì mở phiên mới, bearer không hợp lệ trả 401, chốt dự trữ dung lượng tính trên quota thật, phạm vi drive.file và
token không rơi ra ngoài kho; dọn trong finally, chỉ trong thư mục của lần chạy. Phải chạy dưới quyền thường, cùng user với kho DPAPI.
Trần chi phí: 0 USD, ≤ 60 MiB lên Drive, ≤ 200 lời gọi API. Cách dừng: Ctrl+C; hạn 30 phút. Không in token, refresh token hay file ID.
"""
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for _path in (REPO / 'tools' / 'real', REPO / 'src'):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import pytest  # noqa: E402

import cp7_common as c  # noqa: E402

PROFILE_PATH = REPO / 'tools' / 'launcher' / 'prod' / 'profile.json'
DEADLINE = c.Deadline(30 * 60)
DRIVE_API = 'https://www.googleapis.com/drive/v3'
TOKENINFO = 'https://oauth2.googleapis.com/tokeninfo'
DRIVE_FILE_SCOPE = 'https://www.googleapis.com/auth/drive.file'
FOLDER_MIME = 'application/vnd.google-apps.folder'
FIXTURE_FOLDER = 'cp7-fixture'
NAMESPACE = 'cp7-fixture'
MIB = 1024 * 1024
SMALL_CHUNK = 262144
UPLOAD_CAP_BYTES = 60 * MIB
CALL_CAP = 200
SCAN_LIMIT_BYTES = 100 * MIB


def _data_root():
    base = os.environ.get('AIAVC_DATA_DIR')
    return Path(base) if base else Path(os.environ['LOCALAPPDATA']) / 'AIAutoVideoCreator'


class _Meter:
    """Đếm mọi lời gọi HTTP tới Google của test (qua store và qua REST), byte chunk đã PUT, mã trạng thái đã thấy."""

    def __init__(self):
        self.calls = 0
        self.upload_bytes = 0
        self.chunk_puts = 0
        self.statuses = []

    def http_factory(self):
        """Bọc đúng client mặc định của sản phẩm (drive_http) để đếm, không thay nó."""
        from controlplane.infrastructure.storage.drive_object_store import drive_http
        meter = self

        class _CountingHttp:
            def __init__(self, inner):
                self._inner = inner

            def request(self, uri, method='GET', body=None, headers=None, **kwargs):
                meter.calls += 1
                if method == 'PUT' and 'upload_id=' in uri:
                    meter.chunk_puts += 1
                    meter.upload_bytes += int((headers or {}).get('Content-Length') or (headers or {}).get('content-length') or 0)
                response, content = self._inner.request(uri, method=method, body=body, headers=headers, **kwargs)
                meter.statuses.append(int(response.status))
                return response, content

            def close(self):
                self._inner.close()

        return lambda timeout: _CountingHttp(drive_http(timeout))


class _Api:
    """REST Drive tối thiểu bằng stdlib, token lấy từ broker thật cho từng lời gọi; nhãn lỗi không chứa ID hay token."""

    def __init__(self, broker, meter):
        self._broker = broker
        self._meter = meter

    def call(self, method, url, *, label, params=None, body=None, form=None, timeout=60):
        from controlplane.application.config_security.route_resolver import CREDENTIAL_METHOD
        from controlplane.infrastructure.security.oauth_google_loopback import ACCOUNT_REF
        target = url if url.startswith('https://') else DRIVE_API + url
        if params:
            target += '?' + urllib.parse.urlencode(params)
        self._meter.calls += 1
        with self._broker.acquire(CREDENTIAL_METHOD, ACCOUNT_REF) as token:
            headers = {} if form is not None else {'Authorization': 'Bearer ' + token}
            data = None
            if body is not None:
                data = json.dumps(body).encode('utf-8')
                headers['Content-Type'] = 'application/json'
            if form is not None:
                data = urllib.parse.urlencode({**form, 'access_token': token}).encode('ascii')
                headers['Content-Type'] = 'application/x-www-form-urlencoded'
            request = urllib.request.Request(target, data=data, method=method, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=DEADLINE.timeout(timeout)) as response:
                    status, raw = response.status, response.read()
            except urllib.error.HTTPError as exc:
                status, raw = exc.code, exc.read()
        self._meter.statuses.append(status)
        return status, raw

    def json(self, method, url, *, label, **kwargs):
        status, raw = self.call(method, url, label=label, **kwargs)
        assert 200 <= status < 300, f'Drive {label} returned HTTP {status}'
        return json.loads(raw) if raw else {}


def _digest(file_id):
    """File ID chỉ được giữ dưới dạng băm, để assert hay traceback không bao giờ in ID đầy đủ."""
    return hashlib.sha256(file_id.encode('utf-8')).hexdigest()[:16]


def _q(text):
    return text.replace('\\', '\\\\').replace("'", "\\'")


def _ensure_folder(api, name, parent):
    query = f"name = '{_q(name)}' and '{_q(parent)}' in parents and mimeType = '{FOLDER_MIME}' and trashed = false"
    found = api.json('GET', '/files', label='find fixture folder', params={'q': query, 'fields': 'files(id)', 'pageSize': 10})
    if found.get('files'):
        return found['files'][0]['id']
    return api.json('POST', '/files', label='create fixture folder', params={'fields': 'id'},
                    body={'name': name, 'mimeType': FOLDER_MIME, 'parents': [parent]})['id']


def _visible(api):
    """Mọi tệp ứng dụng thấy được (drive.file chỉ thấy tệp do ứng dụng tạo): id -> tuple parents."""
    seen, page_token = {}, None
    while True:
        params = {'q': 'trashed = false', 'fields': 'nextPageToken,files(id,parents)', 'pageSize': 1000}
        if page_token:
            params['pageToken'] = page_token
        page = api.json('GET', '/files', label='list visible files', params=params)
        for item in page.get('files', []):
            seen[item['id']] = tuple(item.get('parents', ()))
        page_token = page.get('nextPageToken')
        if not page_token:
            return seen


def _store_config(drive, run_folder, *, chunk_bytes=None, ratio=None):
    from controlplane.infrastructure.storage.drive_object_store import DriveStoreConfig
    return DriveStoreConfig(
        chunk_bytes=chunk_bytes or drive.chunk_bytes,
        chunk_timeout_seconds=drive.chunk_timeout_seconds,
        retry_max_attempts=drive.retry.max_attempts,
        retry_backoff_base_seconds=drive.retry.backoff_base_seconds,
        retry_backoff_cap_seconds=drive.retry.backoff_max_seconds,
        session_ttl_seconds=drive.session_ttl_seconds,
        quota_reserve_ratio=drive.quota_reserve_ratio if ratio is None else ratio,
        placement={NAMESPACE: run_folder},
        fallback_parent_id=run_folder,
    )


class _FixedBearer:
    """Broker trả một bearer cố định không hợp lệ (không phải credential thật) để Drive thật trả 401."""

    def __init__(self):
        self._value = 'cp7-invalid-' + uuid.uuid4().hex

    def acquire(self, credential_method, account_ref):
        import contextlib

        @contextlib.contextmanager
        def _scope():
            yield self._value
        return _scope()


class _ExpiringSession:
    """Bọc request upload của phiên đầu: sau chunk đầu đổi upload_id thành giá trị không tồn tại, nên chunk sau gặp lỗi thật của Drive."""

    def __init__(self, request):
        self._request = request
        self.tampered = False

    def next_chunk(self):
        status, response = self._request.next_chunk()
        if not self.tampered and response is None and self._request.resumable_uri:
            self._request.resumable_uri = re.sub(r'upload_id=[^&]+', 'upload_id=cp7-' + uuid.uuid4().hex,
                                                 self._request.resumable_uri)
            self.tampered = True
        return status, response


def _write_random(staging, name, size):
    data = os.urandom(size)
    (staging / name).write_bytes(data)
    return {'md5': hashlib.md5(data).hexdigest(), 'sha256': hashlib.sha256(data).hexdigest(), 'size': size}


def _cleanup(api, run_folder, fixture_id):
    """Chỉ xoá tệp có cha đúng thư mục của lần chạy, rồi xoá thư mục đó (cha phải là cp7-fixture); không bao giờ ném lỗi."""
    report = {'deleted': 0, 'refused': 0, 'errors': 0}
    try:
        query = f"'{_q(run_folder)}' in parents and trashed = false"
        page = api.json('GET', '/files', label='list run folder', params={'q': query, 'fields': 'files(id,parents)', 'pageSize': 1000})
        for item in page.get('files', []):
            if tuple(item.get('parents', ())) != (run_folder,):
                report['refused'] += 1
                continue
            status, _ = api.call('DELETE', f"/files/{item['id']}", label='delete fixture file')
            report['deleted' if status in (200, 204) else 'errors'] += 1
        meta = api.json('GET', f'/files/{run_folder}', label='run folder parents', params={'fields': 'parents'})
        if tuple(meta.get('parents', ())) == (fixture_id,):
            status, _ = api.call('DELETE', f'/files/{run_folder}', label='delete run folder')
            report['deleted' if status in (200, 204) else 'errors'] += 1
        else:
            report['refused'] += 1
    except Exception as exc:  # dọn không được làm hỏng bằng chứng đã thu; lỗi được đếm và kiểm ở test cleanup
        report['errors'] += 1
        report['error_kind'] = type(exc).__name__
    return report


def _scan_outside_vault(values, extra_texts):
    """Đếm số lần các giá trị bí mật xuất hiện ngoài kho DPAPI: thư mục dữ liệu (trừ vault/) và các văn bản test đưa vào."""
    needles = [v.encode('utf-8') for v in values if v]
    hits, scanned = 0, 0
    root = _data_root()
    vault = (root / 'vault').resolve()
    for path in root.rglob('*'):
        try:
            if not path.is_file() or vault in path.resolve().parents or path.stat().st_size > SCAN_LIMIT_BYTES:
                continue
            blob = path.read_bytes()
        except OSError:
            continue
        scanned += 1
        hits += sum(blob.count(n) for n in needles)
    for text in extra_texts:
        scanned += 1
        hits += sum(text.encode('utf-8').count(n) for n in needles)
    return hits, scanned


@pytest.fixture(scope='module')
def real():
    from controlplane.api.wiring.production_profile import load_production_profile
    from controlplane.application.storage_meta.cloud_persist import ObjectAlreadyExistsError
    from controlplane.infrastructure.production_ports.artifact_source import StagingArtifactSource
    from controlplane.infrastructure.production_ports.drive_token import build_drive_token_broker
    from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore
    from controlplane.infrastructure.security.oauth_google_loopback import SECRET_REF as DRIVE_SECRET_REF
    from controlplane.infrastructure.storage.drive_object_store import (
        DriveObjectStore,
        DriveObjectStoreError,
        DriveQuotaError,
    )

    root = _data_root()
    vault_store = DpapiSecretStore(root / 'vault')
    obs = {'oauth_present': vault_store.current_version(DRIVE_SECRET_REF) is not None}
    if not obs['oauth_present']:
        pytest.fail('BLOCKED WAITING_USER_OAUTH: chạy `python tools/launcher/launcher.py oauth` trước (điểm dừng 1)')
    profile = load_production_profile(PROFILE_PATH)
    drive = profile.drive
    broker = build_drive_token_broker(root / 'secrets' / 'oauth-client.json', profile.credential_max_ttl_seconds, vault_store,
                                      lambda: datetime.now(timezone.utc))
    meter = _Meter()
    api = _Api(broker, meter)
    staging = Path(tempfile.mkdtemp(prefix='cp7-3-'))
    source = StagingArtifactSource(staging)
    run_id = uuid.uuid4().hex[:12]
    placement_root = json.loads((root / 'state' / 'drive-placement.json').read_text(encoding='utf-8'))['root']['id']
    fixture_id = _ensure_folder(api, FIXTURE_FOLDER, placement_root)
    run_folder = api.json('POST', '/files', label='create run folder', params={'fields': 'id'},
                          body={'name': run_id, 'mimeType': FOLDER_MIME, 'parents': [fixture_id]})['id']

    def make_store(config, token_broker=broker):
        return DriveObjectStore(config, token_broker, source, http_factory=meter.http_factory())

    try:
        visible = _visible(api)
        obs['outside_before'] = {_digest(i) for i, parents in visible.items() if i != run_folder and run_folder not in parents}

        obs['scopes'] = sorted(json.loads(api.call('POST', TOKENINFO, label='tokeninfo', form={})[1] or b'{}').get('scope', '').split())

        files = {}
        for name, size in (('a1', MIB), ('b9', 9 * MIB), ('c40', 40 * MIB), ('d1', MIB), ('e1', MIB)):
            artifact = f'cp7-{name}-{run_id}'
            files[name] = {'artifact': artifact, **_write_random(staging, artifact, size)}
        store = make_store(_store_config(drive, run_folder))

        # 401: bearer cố định không hợp lệ; cùng file ID đã cấp sau đó vẫn upload được (không mất chỗ của tệp).
        files['a1']['id'] = store.reserve_object_id(NAMESPACE)
        bad_store = make_store(_store_config(drive, run_folder), _FixedBearer())
        statuses_before = len(meter.statuses)
        try:
            bad_store.upload(files['a1']['id'], files['a1']['artifact'], files['a1']['sha256'], files['a1']['size'])
            obs['token_invalid_error'] = None
        except DriveObjectStoreError as exc:
            obs['token_invalid_error'] = str(exc)
        obs['token_invalid_statuses'] = meter.statuses[statuses_before:]

        # Ba tệp chính bằng cấu hình production (chunk 8 MiB).
        for name in ('a1', 'b9', 'c40'):
            info = files[name]
            info.setdefault('id', None)
            if info['id'] is None:
                info['id'] = store.reserve_object_id(NAMESPACE)
            puts_before = meter.chunk_puts
            store.upload(info['id'], info['artifact'], info['sha256'], info['size'])
            info['chunk_puts'] = meter.chunk_puts - puts_before
        obs['chunk_bytes'] = drive.chunk_bytes

        # 409: upload lại với file ID đã cấp; Drive giữ đúng một bản.
        try:
            store.upload(files['a1']['id'], files['a1']['artifact'], files['a1']['sha256'], files['a1']['size'])
            obs['conflict'] = 'no-error'
        except ObjectAlreadyExistsError:
            obs['conflict'] = 'ObjectAlreadyExistsError'
        query = f"name = '{_q(files['a1']['artifact'])}' and '{_q(run_folder)}' in parents and trashed = false"
        obs['conflict_copies'] = len(api.json('GET', '/files', label='count a1 copies', params={'q': query, 'fields': 'files(id)'})['files'])

        # md5 Drive so với md5 cục bộ; sha256 qua đường lookup của sản phẩm và qua tải lại thật.
        for name in ('a1', 'b9', 'c40'):
            meta = api.json('GET', f"/files/{files[name]['id']}", label=f'metadata {name}',
                            params={'fields': 'md5Checksum,size,parents'})
            files[name]['drive_md5'] = meta.get('md5Checksum')
            files[name]['drive_size'] = int(meta.get('size', -1))
            files[name]['drive_parents'] = tuple(meta.get('parents', ()))
        observation = store.lookup(files['b9']['id'])
        obs['lookup_b9'] = {'exists': observation.object_present, 'sha256': observation.observed_sha256,
                            'size': observation.observed_size_bytes,
                            'evidence_kind': (observation.evidence_ref or '').rsplit(':', 1)[-1]}
        status, raw = api.call('GET', f"/files/{files['b9']['id']}", label='download b9', params={'alt': 'media'}, timeout=300)
        obs['redownload_b9'] = {'status': status, 'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}

        # Phiên resumable không tồn tại: chunk 256 KiB, sau chunk đầu đổi upload_id; store phải mở phiên mới và hoàn tất.
        expiring_store = make_store(_store_config(drive, run_folder, chunk_bytes=SMALL_CHUNK))
        files['d1']['id'] = expiring_store.reserve_object_id(NAMESPACE)
        original = expiring_store._new_upload_request
        sessions = []

        def _wrapped(*args, **kwargs):
            request = original(*args, **kwargs)
            sessions.append(request)
            return _ExpiringSession(request) if len(sessions) == 1 else request

        expiring_store._new_upload_request = _wrapped
        statuses_before = len(meter.statuses)
        try:
            expiring_store.upload(files['d1']['id'], files['d1']['artifact'], files['d1']['sha256'], files['d1']['size'])
            obs['session_error'] = None
        except Exception as exc:  # ghi loại lỗi để test báo đúng nguyên nhân
            obs['session_error'] = type(exc).__name__ + ': ' + str(exc)[:120]
        obs['session_statuses'] = sorted(set(meter.statuses[statuses_before:]))
        obs['session_count'] = len(sessions)
        meta = api.json('GET', f"/files/{files['d1']['id']}", label='metadata d1', params={'fields': 'md5Checksum'}) \
            if obs['session_error'] is None else {}
        obs['session_md5_ok'] = meta.get('md5Checksum') == files['d1']['md5']

        # Chốt dự trữ: tỷ lệ đặt ngay trên phần trống dự phóng thật, nên upload phải bị từ chối trước khi tạo tệp.
        quota = api.json('GET', '/about', label='storage quota', params={'fields': 'storageQuota'}).get('storageQuota', {})
        limit = int(quota['limit']) if quota.get('limit') else None
        usage = int(quota.get('usage', 0))
        obs['quota'] = {'limit': limit, 'usage': usage}
        if limit:
            free_after = (limit - usage - files['e1']['size']) / limit
            obs['quota']['profile_ratio'] = drive.quota_reserve_ratio
            obs['quota']['free_after_ratio'] = free_after
            # Trung điểm giữa phần trống dự phóng và 1: luôn trên phần trống thật và luôn < 1, kể cả khi tài khoản gần trống.
            guard_ratio = (free_after + 1) / 2
            guard_store = make_store(_store_config(drive, run_folder, ratio=guard_ratio))
            files['e1']['id'] = guard_store.reserve_object_id(NAMESPACE)
            try:
                guard_store.upload(files['e1']['id'], files['e1']['artifact'], files['e1']['sha256'], files['e1']['size'])
                obs['quota']['guard'] = 'uploaded'
            except DriveQuotaError:
                obs['quota']['guard'] = 'DriveQuotaError'
            status, _ = api.call('GET', f"/files/{files['e1']['id']}", label='e1 must not exist', params={'fields': 'id'})
            obs['quota']['guard_file_status'] = status

        obs['files'] = {name: {k: v for k, v in info.items() if k not in ('id', 'artifact')} for name, info in files.items()}
        obs['parents_ok'] = all(files[n]['drive_parents'] == (run_folder,) for n in ('a1', 'b9', 'c40'))
    finally:
        obs['cleanup'] = _cleanup(api, run_folder, fixture_id)
        shutil.rmtree(staging, ignore_errors=True)
    after = _visible(api)
    obs['outside_after'] = {_digest(i) for i in after}
    obs['calls'] = meter.calls
    obs['upload_bytes'] = meter.upload_bytes
    obs['run_id'] = run_id
    obs['broker'] = broker
    yield obs


def _pass(emit, item, *details):
    emit(c.report_line('RG-02', item, 'PASS'))
    for detail in details:
        emit(f'- {item}: {detail}')


def test_rg02_oauth_present(real, emit):
    assert real['oauth_present']
    _pass(emit, 'oauth_present', 'alias OAuth Drive có trong kho DPAPI (chỉ kiểm tồn tại, không đọc giá trị)')


def test_rg02_scope_drive_file(real, emit):
    assert real['scopes'] == [DRIVE_FILE_SCOPE], real['scopes']
    _pass(emit, 'scope_drive_file', f'tokeninfo scope={real["scopes"][0]} (đúng một phạm vi)')


def test_rg02_upload_md5(real, emit):
    files = real['files']
    matched = [n for n in ('a1', 'b9', 'c40') if files[n]['drive_md5'] == files[n]['md5'] and files[n]['drive_size'] == files[n]['size']]
    assert matched == ['a1', 'b9', 'c40'], matched
    assert real['parents_ok'], 'uploaded file is outside the run folder'
    _pass(emit, 'upload_md5', 'md5Checksum Drive = md5 cục bộ 3/3 (1, 9, 40 MiB), kích thước khớp, đúng thư mục cp7-fixture/<runId>')


def test_rg02_resumable_chunks(real, emit):
    files, chunk = real['files'], real['chunk_bytes']
    expected = {n: -(-files[n]['size'] // chunk) for n in ('b9', 'c40')}
    got = {n: files[n]['chunk_puts'] for n in ('b9', 'c40')}
    assert got == expected and got['c40'] >= 5, (got, expected)
    _pass(emit, 'resumable_chunks', f'chunk {chunk // MIB} MiB: 9 MiB → {got["b9"]} PUT, 40 MiB → {got["c40"]} PUT')


def test_rg02_sha256_redownload(real, emit):
    expected = real['files']['b9']['sha256']
    lookup, redownload = real['lookup_b9'], real['redownload_b9']
    assert lookup['exists'] and lookup['sha256'] == expected and lookup['size'] == real['files']['b9']['size'], lookup['evidence_kind']
    assert redownload['status'] == 200 and redownload['sha256'] == expected, redownload['status']
    _pass(emit, 'sha256_redownload', f'lookup của DriveObjectStore ({lookup["evidence_kind"]}) và tải lại 9 MiB đều cho sha256 khớp')


def test_rg02_conflict_409(real, emit):
    assert real['conflict'] == 'ObjectAlreadyExistsError' and real['conflict_copies'] == 1, (real['conflict'], real['conflict_copies'])
    _pass(emit, 'conflict_409', 'upload lại cùng file ID → ObjectAlreadyExistsError (409); Drive giữ đúng 1 bản')


def test_rg02_session_expired(real, emit):
    assert real['session_error'] is None, real['session_error']
    assert 404 in real['session_statuses'] and real['session_count'] == 2 and real['session_md5_ok'], (
        real['session_statuses'], real['session_count'], real['session_md5_ok'])
    _pass(emit, 'session_expired', f'upload_id không tồn tại → HTTP 404 thật; store mở phiên mới (2 phiên), hoàn tất, md5 khớp; '
          f'mã đã thấy {real["session_statuses"]}')


def test_rg02_token_invalid(real, emit):
    assert 401 in real['token_invalid_statuses'], real['token_invalid_statuses']
    assert real['token_invalid_error'] and 'HTTP 401' in real['token_invalid_error'], real['token_invalid_error']
    assert real['files']['a1']['drive_md5'] == real['files']['a1']['md5'], 'reserved file id was lost after 401'
    emit(c.report_line('RG-02', 'token_invalid', 'BLOCKED'))
    emit('- token_invalid: adapter: bearer cố định không hợp lệ → HTTP 401 thật, DriveObjectStoreError, file ID đã cấp vẫn upload được '
         'sau đó (không mất). Phần "job chuyển chờ credential" chưa đo được: activity PersistVideoOutput chưa được nối vào worker '
         'production (launcher start_worker handlers={}).')
    pytest.fail('BLOCKED: job-level credential wait needs the PersistVideoOutput activity wired into the production worker')


def test_rg02_quota_reserve(real, emit):
    quota = real['quota']
    if not quota['limit']:
        emit(c.report_line('RG-02', 'quota_reserve', 'BLOCKED'))
        pytest.fail('BLOCKED: Drive storageQuota has no limit, the reserve guard cannot be measured on this account')
    assert quota['free_after_ratio'] >= quota['profile_ratio'], 'account is already below the profile reserve'
    assert quota['guard'] == 'DriveQuotaError' and quota['guard_file_status'] == 404, (quota['guard'], quota['guard_file_status'])
    _pass(emit, 'quota_reserve', f'quota thật: trống dự phóng {quota["free_after_ratio"]:.6f} ≥ ngưỡng profile {quota["profile_ratio"]}; '
          'đặt ngưỡng ngay trên phần trống dự phóng → DriveQuotaError, không tệp nào được tạo (404)')


def test_rg02_token_outside_vault(real, emit):
    from controlplane.application.config_security.route_resolver import CREDENTIAL_METHOD
    from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore
    from controlplane.infrastructure.security.oauth_google_loopback import ACCOUNT_REF, SECRET_REF as DRIVE_SECRET_REF
    from controlplane.security.broker import CredentialBroker
    report = REPO / 'docs' / 'delivery-evidence' / 'cp7-3' / 'report.md'
    extra = [report.read_text(encoding='utf-8')] if report.is_file() else []
    vault = DpapiSecretStore(_data_root() / 'vault')
    with real['broker'].acquire(CREDENTIAL_METHOD, ACCOUNT_REF) as access_token:
        with CredentialBroker(vault.export_vault([DRIVE_SECRET_REF])).acquire_secret(DRIVE_SECRET_REF) as handle:
            hits, scanned = _scan_outside_vault([access_token, handle.get_secret_value()], extra)
    assert hits == 0, f'token found outside the vault: hits={hits}'
    _pass(emit, 'token_outside_vault', f'access token và refresh token: 0 lần xuất hiện trong {scanned} tệp của thư mục dữ liệu (trừ vault) '
          'và báo cáo')


def test_rg02_cleanup_namespace(real, emit):
    cleanup = real['cleanup']
    assert cleanup['errors'] == 0 and cleanup['refused'] == 0 and cleanup['deleted'] >= 5, cleanup
    assert real['outside_after'] == real['outside_before'], (len(real['outside_before']), len(real['outside_after']))
    _pass(emit, 'cleanup_namespace', f'xoá {cleanup["deleted"]} mục, chỉ trong cp7-fixture/<runId>; '
          f'{len(real["outside_before"])} tệp ngoài thư mục đó không đổi')


def test_rg02_secret_scan(real, emit):
    report = REPO / 'docs' / 'delivery-evidence' / 'cp7-3' / 'report.md'
    found = len(c.scan_secrets(report.read_text(encoding='utf-8'))) if report.is_file() else 0
    assert found == 0, found
    assert real['calls'] <= CALL_CAP and real['upload_bytes'] <= UPLOAD_CAP_BYTES, (real['calls'], real['upload_bytes'])
    _pass(emit, 'secret_scan', f'báo cáo 0 mẫu bí mật; trần: {real["calls"]} lời gọi API ≤ {CALL_CAP}, '
          f'{real["upload_bytes"] / MIB:.2f} MiB lên Drive ≤ {UPLOAD_CAP_BYTES // MIB}')
