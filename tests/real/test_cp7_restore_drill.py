"""CP7-13 / RG-12: restore drill thật và đối soát Drive.

Chạy theo docs/runbook/runbook-v1.md mục 4 và 5: launcher backup, upload một output nhỏ vào AI-Auto-Video-Creator/cp7-fixture/<runId>/, launcher stop, launcher restore --file <dump> --yes, launcher start. Sau đó kiểm epoch cũ bị từ chối, CSDL cũ còn nguyên, số hàng bằng lúc backup, đối soát Drive thấy output mới hơn backup và cleanup chỉ chạy sau khi đối soát xong.
Thay đổi state/active-db là có chủ đích; test không xoá CSDL nào và không xoá tệp Drive nào ngoài cp7-fixture/<runId>/. Trần: 0 USD, Deadline 60 phút, Drive <= 10 MiB. Lỗi giữa chừng thì dừng (BLOCKED), giữ nguyên CSDL cũ. Không in token, mật khẩu hay file ID.
"""
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
for _path in (REPO / 'tools' / 'real', REPO / 'src'):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import psycopg  # noqa: E402
import pytest  # noqa: E402
from psycopg import sql  # noqa: E402

import cp7_common as c  # noqa: E402

LAUNCHER = REPO / 'tools' / 'launcher' / 'launcher.py'
PROFILE_PATH = REPO / 'tools' / 'launcher' / 'prod' / 'profile.json'
SELF = Path(__file__).resolve()
REPORT = REPO / 'docs' / 'delivery-evidence' / 'cp7-13' / 'report.md'
RUN_ID = uuid.uuid4().hex[:12]
DEADLINE = c.Deadline(3600)
ISSUED = []
DRIVE_API = 'https://www.googleapis.com/drive/v3'
FOLDER_MIME = 'application/vnd.google-apps.folder'
FIXTURE_FOLDER = 'cp7-fixture'
NAMESPACE = 'cp7-fixture'
MIB = 1024 * 1024
UPLOAD_BYTES = 256 * 1024
UPLOAD_CAP_BYTES = 10 * MIB
STOP_ATTEMPTS = 4


def _child_env():
    env = {k: v for k, v in os.environ.items() if k not in ('M2_TEST_PG_DSN', 'CONTROLPLANE_DSN')}
    env.update({'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1', 'BROWSER': 'cmd /c exit 0 %s'})
    return env


def _run(argv, *, timeout, log_dir):
    ISSUED.append(list(argv))
    log = Path(log_dir) / f'run_{len(ISSUED)}.log'
    with log.open('wb') as handle:
        try:
            proc = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=handle, stderr=subprocess.STDOUT, cwd=REPO, env=_child_env(), timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            pytest.fail('BLOCKED: lệnh vượt hạn: ' + ' '.join(argv[:4]))
        except FileNotFoundError:
            pytest.fail('BLOCKED: thiếu lệnh ' + argv[0])
    return proc.returncode, log.read_text(encoding='utf-8', errors='replace')


def _launcher(work, command, cap, *extra):
    assert command in ('start', 'stop', 'backup', 'restore')
    return _run([sys.executable, str(LAUNCHER), command, *extra], timeout=DEADLINE.timeout(cap), log_dir=work)


def _must(work, command, cap):
    rc, text = _launcher(work, command, cap)
    assert rc == 0, f'BLOCKED: launcher {command} rc={rc}: {text[-800:]}'


def _docker(work, *args):
    return _run(['docker', *args], timeout=DEADLINE.timeout(60), log_dir=work)


def _load_launcher():
    spec = importlib.util.spec_from_file_location('cp7_13_launcher_under_test', LAUNCHER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _stop_until_exited(work):
    last = ''
    for attempt in range(1, STOP_ATTEMPTS + 1):
        rc, text = _launcher(work, 'stop', 120)
        if rc == 0:
            return attempt
        last = text[-400:]
    pytest.fail(f'BLOCKED: launcher stop không thoát sau {STOP_ATTEMPTS} lần (không ép tắt): {last}')


def _snapshot(dsn):
    with psycopg.connect(dsn, autocommit=True, connect_timeout=10) as conn:
        names = [row[0] for row in conn.execute('SELECT table_name FROM information_schema.tables WHERE table_schema = %s AND table_type = %s ORDER BY table_name', ('controlplane', 'BASE TABLE')).fetchall()]
        counts = {name: conn.execute(sql.SQL('SELECT count(*) FROM controlplane.{}').format(sql.Identifier(name))).fetchone()[0] for name in names}
        db_oid = conn.execute('SELECT oid FROM pg_database WHERE datname = current_database()').fetchone()[0]
    return SimpleNamespace(counts=counts, db_oid=db_oid)


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _pass(emit, item, *details):
    emit(c.report_line('RG-12', item, 'PASS'))
    for detail in details:
        assert detail.isascii(), f'evidence detail for {item} must be ASCII'
        emit(f'- {item}: {detail}')


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


def _q(text):
    return text.replace('\\', '\\\\').replace("'", "\\'")


def _ensure_folder(api, name, parent):
    query = f"name = '{_q(name)}' and '{_q(parent)}' in parents and mimeType = '{FOLDER_MIME}' and trashed = false"
    found = api.json('GET', '/files', label='find fixture folder', params={'q': query, 'fields': 'files(id)', 'pageSize': 10})
    if found.get('files'):
        return found['files'][0]['id']
    return api.json('POST', '/files', label='create fixture folder', params={'fields': 'id'},
                    body={'name': name, 'mimeType': FOLDER_MIME, 'parents': [parent]})['id']


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


def _dsn(st, name):
    return st.tool.build_dsn(st.password, name)


def _pg_ready(st):
    return _docker(st.work, 'exec', st.tool.POSTGRES_CONTAINER, 'pg_isready', '-U', st.tool.DB_USER, '-d', st.tool.DB_NAME)[0] == 0


def _phase_backup(st):
    st.work = Path(tempfile.mkdtemp(prefix='cp7-13-'))
    st.tool = _load_launcher()
    st.layout = st.tool.resolve_layout(os.environ)
    st.password = st.tool.load_or_create_password(st.layout)
    st.workspace_id = st.tool.load_or_create_identity(st.layout)['workspace_id']
    if not _pg_ready(st):
        _must(st.work, 'start', 900)
    _stop_until_exited(st.work)
    if not _pg_ready(st):
        pytest.fail('BLOCKED: PostgreSQL chưa sẵn sàng sau stop')
    st.old_db = st.tool.active_db_name(st.layout)
    st.history_before = st.tool.read_epoch_history(st.layout)
    if not st.history_before or not re.fullmatch(r'[0-9]+', str(st.history_before[-1].get('epoch', ''))):
        pytest.fail('BLOCKED: state/recovery-epoch.json thiếu hoặc không có epoch thập phân')
    st.old_epoch = str(st.history_before[-1]['epoch'])
    st.before = _snapshot(_dsn(st, st.old_db))
    assert sum(st.before.counts.values()) > 0, 'BLOCKED: bảng chính rỗng, phép so số hàng vô nghĩa'
    st.dump = st.layout.backups_dir / f'cp7-13-{RUN_ID}.dump'
    assert not st.dump.exists(), 'BLOCKED: tệp dump đã tồn tại'
    st.events.append('backup')
    rc, text = _launcher(st.work, 'backup', 600, '--out', str(st.dump))
    st.logs.append(text)
    assert rc == 0, f'BLOCKED: launcher backup rc={rc}: {text[-800:]}'
    st.dump_sha = _sha256_file(st.dump)
    sidecar = st.dump.with_name(st.dump.name + '.sha256').read_text(encoding='utf-8').split()
    st.sidecar_sha = sidecar[0] if sidecar else ''
    st.dump_size = st.dump.stat().st_size
    st.backup_done = datetime.now(timezone.utc)
    time.sleep(2)


def _phase_upload(st):
    from controlplane.api.wiring.production_profile import load_production_profile
    from controlplane.infrastructure.production_ports.artifact_source import StagingArtifactSource
    from controlplane.infrastructure.production_ports.drive_token import build_drive_token_broker
    from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore
    from controlplane.infrastructure.security.oauth_google_loopback import SECRET_REF as DRIVE_SECRET_REF
    from controlplane.infrastructure.storage.drive_object_store import DriveObjectStore

    root = _data_root()
    vault_store = DpapiSecretStore(root / 'vault')
    if vault_store.current_version(DRIVE_SECRET_REF) is None:
        pytest.fail('BLOCKED WAITING_USER_OAUTH: chạy python tools/launcher/launcher.py oauth trước')
    profile = load_production_profile(PROFILE_PATH)
    broker = build_drive_token_broker(root / 'secrets' / 'oauth-client.json', profile.credential_max_ttl_seconds, vault_store, lambda: datetime.now(timezone.utc))
    st.meter = _Meter()
    st.api = _Api(broker, st.meter)
    staging = st.work / 'staging'
    staging.mkdir()
    st.artifact = f'cp7-13-{RUN_ID}'
    data = os.urandom(UPLOAD_BYTES)
    (staging / st.artifact).write_bytes(data)
    st.file_sha = hashlib.sha256(data).hexdigest()
    st.file_size = len(data)
    placement_root = json.loads((root / 'state' / 'drive-placement.json').read_text(encoding='utf-8'))['root']['id']
    st.fixture_id = _ensure_folder(st.api, FIXTURE_FOLDER, placement_root)
    st.run_folder = st.api.json('POST', '/files', label='create run folder', params={'fields': 'id'}, body={'name': RUN_ID, 'mimeType': FOLDER_MIME, 'parents': [st.fixture_id]})['id']
    st.events.append('upload')
    st.store = DriveObjectStore(_store_config(profile.drive, st.run_folder), broker, StagingArtifactSource(staging), http_factory=st.meter.http_factory())
    st.object_id = st.store.reserve_object_id(NAMESPACE)
    st.store.upload(st.object_id, st.artifact, st.file_sha, st.file_size)
    meta = st.api.json('GET', f'/files/{st.object_id}', label='metadata output', params={'fields': 'createdTime,md5Checksum,size,parents'})
    st.drive_created = datetime.fromisoformat(meta['createdTime'].replace('Z', '+00:00'))
    st.drive_md5_ok = meta.get('md5Checksum') == hashlib.md5(data).hexdigest()
    st.drive_size_ok = int(meta.get('size', -1)) == st.file_size
    st.drive_parent_ok = tuple(meta.get('parents', ())) == (st.run_folder,)


def _phase_restore(st):
    st.events.append('stop')
    _stop_until_exited(st.work)
    st.events.append('restore')
    rc, text = _launcher(st.work, 'restore', 900, '--file', str(st.dump), '--yes')
    st.logs.append(text)
    assert rc == 0, f'BLOCKED: launcher restore rc={rc}: {text[-800:]}'
    st.new_db = st.tool.active_db_name(st.layout)
    st.restore_history = st.tool.read_epoch_history(st.layout)
    st.epoch_mtime_ns = st.layout.epoch_file.stat().st_mtime_ns
    st.active_mtime_ns = st.layout.active_db_file.stat().st_mtime_ns
    source = LAUNCHER.read_text(encoding='utf-8')
    body = source[source.index('def cmd_restore'):source.index('def cmd_oauth')]
    st.epoch_write_index = body.index('atomic_write_text(layout.epoch_file')
    st.active_write_index = body.index('atomic_write_text(layout.active_db_file')
    st.restored = _snapshot(_dsn(st, st.new_db))
    st.old_after = _snapshot(_dsn(st, st.old_db))
    with psycopg.connect(_dsn(st, 'postgres'), autocommit=True, connect_timeout=10) as admin:
        st.dbs = [row[0] for row in admin.execute('SELECT datname FROM pg_database').fetchall()]


def _phase_start(st):
    from controlplane.application.orchestration.grant_runtime import ExecutionGrantCurrency
    from controlplane.domain.orchestration import ExecutionGrant
    from controlplane.domain.orchestration.fencing import GrantClaims, evaluate_result_fencing
    from controlplane.infrastructure.db.orchestration.grants import PostgresRecoveryEpoch

    st.events.append('start')
    started = time.monotonic()
    rc, text = _launcher(st.work, 'start', 900)
    st.start_seconds = time.monotonic() - started
    st.start_rc = rc
    st.logs.append(text)
    assert rc == 0, f'BLOCKED: launcher start rc={rc}: {text[-800:]}'
    st.app_open = st.tool.wait_for_tcp(st.tool.LOOPBACK, st.tool.APP_PORT, 10.0)
    st.ready_limit = json.loads(PROFILE_PATH.read_text(encoding='utf-8'))['resume']['ready_within_seconds']['value']
    st.new_epoch = str(st.tool.read_epoch_history(st.layout)[-1]['epoch'])
    st.active_after_start = st.tool.active_db_name(st.layout)
    new_dsn = _dsn(st, st.new_db)
    ws = st.workspace_id
    with psycopg.connect(new_dsn, connect_timeout=10) as conn:
        st.db_epoch = PostgresRecoveryEpoch(conn, ws).current()
        row = conn.execute('SELECT grant_id, stage_run_id, execution_generation FROM controlplane.cp_execution_grants WHERE workspace_id = %s AND revoked_at IS NULL AND recovery_epoch = %s ORDER BY created_at LIMIT 1', (ws, st.old_epoch)).fetchone()
    now = datetime.now(timezone.utc)

    def iso(value):
        return value.isoformat().replace('+00:00', 'Z')

    def claims(epoch):
        return GrantClaims(grant_id='cp7-13-grant', stage_run_id='cp7-13-stage', execution_generation=1, recovery_epoch=epoch, worker_lease_id='cp7-13-lease', issued_at=iso(now - timedelta(minutes=1)), expires_at=iso(now + timedelta(minutes=10)), allowed_operation='cp7-13-op', input_fingerprint='cp7-13-fp')

    def result(epoch):
        return {'recovery_epoch': epoch, 'execution_generation': 1, 'grant_id': 'cp7-13-grant', 'stage_run_id': 'cp7-13-stage'}

    st.old_decision = evaluate_result_fencing(claims(st.old_epoch), 1, st.db_epoch, result(st.old_epoch), 'cp7-13-fp', now, False)
    st.new_decision = evaluate_result_fencing(claims(st.db_epoch), 1, st.db_epoch, result(st.db_epoch), 'cp7-13-fp', now, False)
    st.real_grant_current = None
    if row is not None:
        currency = ExecutionGrantCurrency(lambda: psycopg.connect(new_dsn, connect_timeout=10), ws, lambda: datetime.now(timezone.utc))
        st.real_grant_current = currency.is_grant_current(ExecutionGrant(ws, str(row[0]), 'cp7-13-job', str(row[1]), int(row[2]), int(st.old_epoch)))


def _phase_reconcile(st):
    from controlplane.application.storage_meta.cleanup_evaluation import CleanupEvaluationRequest, evaluate_cleanup
    from controlplane.application.storage_meta.reconciliation import CloudLocationRecord, CloudObjectObservation, JournalEntry, ReconcileSnapshot, VersionRecord, reconcile
    from controlplane.domain.statemachine import ArtifactLocationState

    listing = st.api.json('GET', '/files', label='list run folder', params={'q': f"'{_q(st.run_folder)}' in parents and trashed = false", 'fields': 'files(id)', 'pageSize': 100})['files']
    observed = []
    for item in listing:
        seen = st.store.lookup(item['id'])
        observed.append(CloudObjectObservation(item['id'], seen.observed_sha256, seen.observed_size_bytes))
    st.listed = len(listing)
    with psycopg.connect(_dsn(st, st.new_db), connect_timeout=10) as conn:
        st.db_refs = conn.execute('SELECT count(*) FROM controlplane.cp_artifact_locations WHERE provider_object_ref = %s', (st.object_id,)).fetchone()[0]
    stale = JournalEntry('cp7-13-op', st.artifact, 1, st.old_epoch)
    restored_view = ReconcileSnapshot(current_recovery_epoch=st.new_epoch, cloud_objects=tuple(observed), journal_entries=(stale,), stage_generations={'cp7-13-op': 1})
    st.findings_restored = reconcile(restored_view)
    known_view = ReconcileSnapshot(current_recovery_epoch=st.new_epoch, versions=(VersionRecord(st.artifact, st.file_sha, st.file_size),), cloud_locations=(CloudLocationRecord('cp7-13-loc', st.artifact, st.object_id),), cloud_objects=tuple(observed))
    st.findings_known = reconcile(known_view)
    status, _ = st.api.call('GET', f'/files/{st.object_id}', label='output still present', params={'fields': 'id'})
    st.present_at_reconcile = status == 200

    def cleanup_request(epoch):
        return CleanupEvaluationRequest(storage_class='local_staging', location_state=ArtifactLocationState.VERIFIED, retention_class='per_video', cloud_copy_verified=True, active_lease=False, completion_ref='cp7-13-completion', superseded_ref=None, request_recovery_epoch=epoch, current_recovery_epoch=st.new_epoch)

    st.cleanup_stale = evaluate_cleanup(cleanup_request(st.old_epoch))
    st.cleanup_current = evaluate_cleanup(cleanup_request(st.new_epoch))
    st.events.append('reconcile_done')


@pytest.fixture(scope='module')
def drill():
    st = SimpleNamespace(events=[], logs=[], api=None, run_folder=None, fixture_id=None, work=None, cleanup=None, final_stop=None)
    try:
        for phase in (_phase_backup, _phase_upload, _phase_restore, _phase_start, _phase_reconcile):
            phase(st)
        st.events.append('cleanup')
        st.cleanup = _cleanup(st.api, st.run_folder, st.fixture_id)
        st.final_stop = _stop_until_exited(st.work)
        yield st
    finally:
        if st.work is not None:
            shutil.rmtree(st.work, ignore_errors=True)


def test_rg12_dump_sha256(drill, emit):
    st = drill
    assert re.fullmatch(r'[0-9a-f]{64}', st.dump_sha) and st.dump_size > 0
    assert st.dump_sha == st.sidecar_sha, (st.dump_sha, st.sidecar_sha)
    assert st.restore_history[-1]['source_sha256'] == st.dump_sha
    _pass(emit, 'dump_sha256', f'sha256={st.dump_sha} sidecar_equal=True restore_source_sha256_equal=True size_bytes={st.dump_size}')


def test_rg12_new_db_created(drill, emit):
    st = drill
    assert re.fullmatch(r'controlplane_[0-9]{14}', st.new_db), st.new_db
    assert st.new_db != st.old_db and st.new_db in st.dbs and st.old_db in st.dbs
    assert st.restored.db_oid != st.before.db_oid
    assert st.tool.active_db_name(st.layout) == st.new_db == st.active_after_start
    _pass(emit, 'new_db_created', f'old_db={st.old_db} new_db={st.new_db} oid_differs=True active_db_switched=True restore_did_not_overwrite_active_db=True')


def test_rg12_epoch_before_switch(drill, emit):
    st = drill
    last = st.restore_history[-1]
    assert st.epoch_write_index < st.active_write_index, 'cmd_restore ghi active-db trước epoch'
    assert st.epoch_mtime_ns <= st.active_mtime_ns, (st.epoch_mtime_ns, st.active_mtime_ns)
    assert len(st.restore_history) == len(st.history_before) + 1 and st.restore_history[:-1] == st.history_before
    assert last['epoch'] == str(int(st.old_epoch) + 1) and last['database'] == st.new_db
    _pass(emit, 'epoch_before_switch', f'source_order_epoch_before_active_db=True mtime_epoch_le_active_db=True epoch={st.old_epoch}->{last["epoch"]} history_len={len(st.history_before)}->{len(st.restore_history)} previous_entries_unchanged=True')


def test_rg12_old_epoch_rejected(drill, emit):
    from controlplane.application.storage_meta.cleanup_evaluation import ELIGIBLE, FORBIDDEN
    from controlplane.application.storage_meta.reconciliation import ReconcileAction, ReconcileCode
    from controlplane.domain.orchestration.fencing import ACCEPTED, STALE_RECOVERY_EPOCH

    st = drill
    assert st.db_epoch == st.new_epoch and st.new_epoch != st.old_epoch
    assert (st.old_decision.accepted, st.old_decision.code) == (False, STALE_RECOVERY_EPOCH)
    assert (st.new_decision.accepted, st.new_decision.code) == (True, ACCEPTED)
    assert st.real_grant_current in (False, None)
    stale = [f for f in st.findings_restored if f.code == ReconcileCode.STALE_EPOCH_ENTRY]
    assert len(stale) == 1 and stale[0].action == ReconcileAction.REISSUE_UNDER_NEW_EPOCH
    assert st.cleanup_stale.decision == FORBIDDEN and 'STALE_RECOVERY_EPOCH' in st.cleanup_stale.reason_codes
    assert st.cleanup_current.decision == ELIGIBLE
    _pass(emit, 'old_epoch_rejected', f'old_epoch={st.old_epoch} current_epoch={st.db_epoch} old_result={st.old_decision.code} current_result={st.new_decision.code} real_old_epoch_grant_current={st.real_grant_current} stale_journal_entry_reissue=True cleanup_with_old_epoch={st.cleanup_stale.decision}')


def test_rg12_old_db_kept(drill, emit):
    st = drill
    assert st.old_db in st.dbs and st.old_db != st.new_db
    assert st.old_after.db_oid == st.before.db_oid and st.old_after.counts == st.before.counts
    _pass(emit, 'old_db_kept', f'old_db={st.old_db} still_in_pg_database=True oid_equal=True row_counts_unchanged_after_restore=True tables={len(st.before.counts)}')


def test_rg12_row_counts_equal(drill, emit):
    st = drill
    assert sum(st.before.counts.values()) > 0
    diff = {n: (st.before.counts.get(n), st.restored.counts.get(n)) for n in {*st.before.counts, *st.restored.counts} if st.before.counts.get(n) != st.restored.counts.get(n)}
    assert not diff, diff
    nonzero = ' '.join(f'{n}={k}' for n, k in sorted(st.restored.counts.items()) if k)
    _pass(emit, 'row_counts_equal', f'tables={len(st.restored.counts)} total_rows={sum(st.restored.counts.values())} equal_to_backup_time=True measured=restored_db_before_launcher_start nonzero {nonzero}')


def test_rg12_drive_reconcile_newer(drill, emit):
    from controlplane.application.storage_meta.reconciliation import ReconcileCode

    st = drill
    orphan = [f for f in st.findings_restored if f.code == ReconcileCode.ORPHAN_PROVIDER_OBJECT and f.ref == st.object_id]
    known = [f for f in st.findings_known if f.code == ReconcileCode.ORPHAN_PROVIDER_OBJECT]
    assert len(orphan) == 1 and not known and st.db_refs == 0 and st.listed == 1
    assert st.drive_created > st.backup_done, (st.drive_created, st.backup_done)
    assert st.drive_md5_ok and st.drive_size_ok and st.drive_parent_ok
    assert st.file_size <= UPLOAD_CAP_BYTES and st.meter.upload_bytes <= UPLOAD_CAP_BYTES
    ref = hashlib.sha256(st.object_id.encode('utf-8')).hexdigest()[:16]
    _pass(emit, 'drive_reconcile_newer', f'orphan_finding=ORPHAN_PROVIDER_OBJECT object_digest={ref} created_after_backup=True restored_db_location_rows=0 control_view_with_location_orphans=0 upload_bytes={st.meter.upload_bytes} cap_bytes={UPLOAD_CAP_BYTES}')


def test_rg12_no_cleanup_before_reconcile(drill, emit):
    st = drill
    assert st.events == ['backup', 'upload', 'stop', 'restore', 'start', 'reconcile_done', 'cleanup'], st.events
    assert st.present_at_reconcile
    assert st.cleanup['errors'] == 0 and st.cleanup['refused'] == 0 and st.cleanup['deleted'] >= 2, st.cleanup
    _pass(emit, 'no_cleanup_before_reconcile', f'order={">".join(st.events)} drive_output_present_at_reconcile=True cleanup_deleted={st.cleanup["deleted"]} only_under_cp7_fixture_run_folder=True')


def test_rg12_resume_after_restore(drill, emit):
    st = drill
    assert st.start_rc == 0 and st.app_open
    assert st.ready_limit == 300 and st.start_seconds <= st.ready_limit, (st.start_seconds, st.ready_limit)
    assert st.db_epoch == st.new_epoch == str(int(st.old_epoch) + 1)
    _pass(emit, 'resume_after_restore', f'start_rc=0 ready_seconds={st.start_seconds:.1f} limit_seconds={st.ready_limit} app_port_open=True active_db={st.active_after_start} epoch={st.db_epoch}')


def test_rg12_secret_scan(drill, emit):
    st = drill
    texts = {'test_source': SELF.read_text(encoding='utf-8'), 'launcher_logs': '\n'.join(st.logs)}
    if REPORT.is_file():
        texts['report'] = REPORT.read_text(encoding='utf-8')
    for label, text in texts.items():
        assert c.scan_secrets(text) == [], f'secret pattern in {label}'
        assert st.password not in text, f'postgres password in {label}'
    _pass(emit, 'secret_scan', f'surfaces={len(texts)} secret_pattern_matches=0 postgres_password_hits=0 cost_usd=0 api_calls={st.meter.calls}')


def test_rg12_deadline_budget(emit):
    remaining = DEADLINE.remaining()
    assert remaining > 0
    emit(f'- deadline: limit_s=3600 remaining_s={remaining:.0f}')
