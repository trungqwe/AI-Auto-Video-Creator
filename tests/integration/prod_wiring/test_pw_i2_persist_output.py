"""PW-I2: PersistVideoOutput với receipt bền và credential_unavailable trên PostgreSQL thật, Drive giả loopback ở tầng httplib2.

coveredIds: PW-I2-01, CT-STO-004, CT-ORC-007, F-CP7-3-01
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import urllib.parse
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import httplib2
import pytest

from controlplane.application.orchestration.job_lifecycle import JobLifecycleListener
from controlplane.application.orchestration.workflows.activities import ActivityRejected
from controlplane.application.storage_meta.materialization import release_for_render
from controlplane.application.storage_meta.persist_handler import persist_video_output_handler
from controlplane.infrastructure.db.storage_meta import PostgresStorageMetaRepository
from controlplane.infrastructure.db.uow import TransactionManager
from controlplane.infrastructure.production_ports.artifact_source import StagingArtifactSource
from controlplane.infrastructure.storage.drive_object_store import (
    DRIVE_CREDENTIAL_INVALID,
    DriveCredentialError,
    DriveObjectStore,
    DriveObjectStoreError,
    DriveStoreConfig,
)

NAMESPACE = 'ns-output'
TOKEN_OK = 'token-valid'
TOKEN_BAD = 'token-expired'
CLAIMS = SimpleNamespace(recovery_epoch='epoch-1', grant_id='grant-1')
MP4 = b'\x00\x00\x00\x18ftypmp42' + bytes((i * 7 + 3) % 251 for i in range(3000))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(root: pathlib.Path, name: str, data: bytes) -> pathlib.Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def rows(db: Any, sql: str, params: tuple = ()) -> list[tuple]:
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def count(db: Any, table: str) -> int:
    return rows(db, f'SELECT count(*) FROM controlplane.{table}')[0][0]


def request(refs=(('render_output', 'render/out.mp4'),), key='op-1') -> dict[str, Any]:
    return {
        'video_job_id': 'job-1',
        'operation_key': key,
        'input_refs': [{'ref_type': k, 'ref_id': v} for k, v in refs],
    }


@pytest.fixture
def manager(pw_database: Any):
    pool = TransactionManager(pw_database.dsn, pool_max_size=2)
    try:
        yield pool
    finally:
        pool.close()


class WorkerDied(RuntimeError):
    pass


class TokenBroker:
    token: str = TOKEN_OK

    @contextmanager
    def acquire(self, credential_method: str, account_ref: str):
        yield self.token


class LoopbackDrive:
    def __init__(self, valid_token: str) -> None:
        self.valid_token = valid_token
        self.files: dict[str, bytes] = {}
        self.sessions: dict[str, dict[str, Any]] = {}
        self.calls: list[str] = []
        self.initiates: int = 0
        self.corrupt_next_upload: bool = False
        self.forced_status: int | None = None
        self._auto_id_seq: int = 0
        self._session_seq: int = 0

    def close(self) -> None:
        pass

    def request(
        self,
        uri: str,
        method: str = 'GET',
        body: object = None,
        headers: Mapping[str, str] | None = None,
        **kwargs: object,
    ) -> tuple[httplib2.Response, bytes]:
        headers_lower = {k.lower(): v for k, v in (headers or {}).items()}
        if hasattr(body, 'read'):
            body_bytes = body.read()
        elif isinstance(body, str):
            body_bytes = body.encode('utf-8')
        elif isinstance(body, (bytes, bytearray)):
            body_bytes = bytes(body)
        else:
            body_bytes = b''

        split = urllib.parse.urlsplit(uri)
        path = split.path

        if path.endswith('/drive/v3/files/generateIds'):
            op = 'generate'
        elif path.endswith('/drive/v3/about'):
            op = 'about'
        elif path.endswith('/upload/drive/v3/files') and method == 'POST':
            op = 'initiate'
        elif uri in self.sessions or path.startswith('/session/'):
            op = 'put'
        elif '/drive/v3/files/' in path and method == 'GET':
            op = 'meta'
        else:
            op = 'unknown'

        self.calls.append(op)

        if self.forced_status is not None:
            code = self.forced_status
            resp = httplib2.Response({'status': str(code), 'content-type': 'application/json'})
            return resp, json.dumps({'error': {'code': code, 'message': 'forced', 'errors': []}}).encode('utf-8')

        auth = headers_lower.get('authorization', '')
        if auth != 'Bearer ' + self.valid_token:
            resp = httplib2.Response({'status': '401', 'content-type': 'application/json'})
            return resp, json.dumps({'error': {'code': 401, 'message': 'HTTP 401 Invalid Credentials', 'errors': []}}).encode('utf-8')

        if op == 'generate':
            self._auto_id_seq += 1
            fid = f'drive-id-{self._auto_id_seq}'
            resp = httplib2.Response({'status': '200', 'content-type': 'application/json'})
            return resp, json.dumps({'ids': [fid]}).encode('utf-8')

        if op == 'about':
            resp = httplib2.Response({'status': '200', 'content-type': 'application/json'})
            return resp, json.dumps({'storageQuota': {}}).encode('utf-8')

        if op == 'initiate':
            self.initiates += 1
            body_json = json.loads(body_bytes.decode('utf-8'))
            fid = body_json.get('id')
            if fid in self.files:
                resp = httplib2.Response({'status': '409', 'content-type': 'application/json'})
                return resp, json.dumps({'error': {'code': 409, 'message': f'File already exists: {fid}', 'errors': []}}).encode('utf-8')
            self._session_seq += 1
            session_uri = f'https://loopback.drive/session/{self._session_seq}'
            self.sessions[session_uri] = {'id': fid, 'data': bytearray()}
            resp = httplib2.Response({'status': '200', 'location': session_uri, 'content-type': 'application/json'})
            return resp, b'{}'

        if op == 'put':
            session = self.sessions.get(uri)
            if session is None:
                for s_uri, s_val in self.sessions.items():
                    if urllib.parse.urlsplit(s_uri).path == split.path:
                        session = s_val
                        break
            if session is None:
                resp = httplib2.Response({'status': '404', 'content-type': 'application/json'})
                return resp, b'{}'
            content_range = headers_lower.get('content-range', '')
            if content_range.startswith('bytes */'):
                fid = session['id']
                if fid in self.files:
                    resp = httplib2.Response({'status': '200', 'content-type': 'application/json'})
                    return resp, json.dumps({'id': fid}).encode('utf-8')
                n = len(session['data'])
                resp_headers = {'status': '308', 'content-type': 'application/json'}
                if n > 0:
                    resp_headers['range'] = f'bytes=0-{n - 1}'
                return httplib2.Response(resp_headers), b'{}'
            parts = content_range[len('bytes '):].split('/')
            range_part = parts[0]
            total = int(parts[1])
            a_str, b_str = range_part.split('-')
            a = int(a_str)
            chunk = body_bytes
            data = session['data']
            if a > len(data):
                data.extend(b'\x00' * (a - len(data)))
            data[a:a + len(chunk)] = chunk
            if len(data) == total:
                fid = session['id']
                final_bytes = bytes(data)
                if self.corrupt_next_upload:
                    final_bytes = bytes([final_bytes[0] ^ 0xFF]) + final_bytes[1:]
                    self.corrupt_next_upload = False
                self.files[fid] = final_bytes
                resp = httplib2.Response({'status': '200', 'content-type': 'application/json'})
                return resp, json.dumps({'id': fid}).encode('utf-8')
            else:
                resp = httplib2.Response({
                    'status': '308',
                    'range': f'bytes=0-{len(data) - 1}',
                    'content-type': 'application/json',
                })
                return resp, b'{}'

        if op == 'meta':
            fid = path.split('/drive/v3/files/')[-1]
            if fid not in self.files:
                resp = httplib2.Response({'status': '404', 'content-type': 'application/json'})
                return resp, json.dumps({'error': {'code': 404, 'message': 'File not found', 'errors': []}}).encode('utf-8')
            data = self.files[fid]
            meta_payload = {
                'id': fid,
                'size': str(len(data)),
                'md5Checksum': hashlib.md5(data, usedforsecurity=False).hexdigest(),
                'sha256Checksum': hashlib.sha256(data).hexdigest(),
                'trashed': False,
            }
            resp = httplib2.Response({'status': '200', 'content-type': 'application/json'})
            return resp, json.dumps(meta_payload).encode('utf-8')

        resp = httplib2.Response({'status': '400', 'content-type': 'application/json'})
        return resp, b'{}'


def make_store(root: pathlib.Path, drive: LoopbackDrive, broker: TokenBroker) -> DriveObjectStore:
    config = DriveStoreConfig(
        chunk_bytes=262144,
        chunk_timeout_seconds=5.0,
        retry_max_attempts=3,
        retry_backoff_base_seconds=0.01,
        retry_backoff_cap_seconds=0.02,
        session_ttl_seconds=1000,
        quota_reserve_ratio=0.0,
        placement={NAMESPACE: 'folder-out'},
        fallback_parent_id='folder-fallback',
    )
    return DriveObjectStore(
        config,
        broker,
        StagingArtifactSource(root),
        http_factory=lambda timeout: drive,
        sleep=lambda seconds: None,
    )


class SpyCloud:
    def __init__(self, store: DriveObjectStore) -> None:
        self._store = store
        self.attempts = 0
        self.completed = 0
        self.before: Any = None
        self.die_before = False
        self.die_after = False

    def reserve_object_id(self, namespace_ref: str) -> str:
        return self._store.reserve_object_id(namespace_ref)

    def lookup(self, object_id: str) -> Any:
        return self._store.lookup(object_id)

    def upload(self, *args: Any, **kwargs: Any) -> None:
        self.attempts += 1
        if self.before is not None:
            self.before()
        if self.die_before:
            raise WorkerDied('before upload')
        self._store.upload(*args, **kwargs)
        self.completed += 1
        if self.die_after:
            raise WorkerDied('after upload')


@dataclass
class Rig:
    db: Any
    manager: Any
    root: pathlib.Path
    drive: LoopbackDrive
    broker: TokenBroker
    cloud: SpyCloud
    service: Any


@pytest.fixture
def rig(pw_database: Any, manager: Any, tmp_path: pathlib.Path) -> Rig:
    root = tmp_path / 'staging'
    write(root, 'render/out.mp4', MP4)
    drive = LoopbackDrive(TOKEN_OK)
    broker = TokenBroker()
    broker.token = TOKEN_OK
    cloud = SpyCloud(make_store(root, drive, broker))
    service = persist_video_output_handler(
        manager,
        workspace_id=pw_database.workspace_id,
        staging_root=root,
        cloud=cloud,
        namespace_ref=NAMESPACE,
    )
    return Rig(
        db=pw_database,
        manager=manager,
        root=root,
        drive=drive,
        broker=broker,
        cloud=cloud,
        service=service,
    )


def locations(rig: Rig, backend: str) -> list[tuple]:
    return rows(
        rig.db,
        'SELECT state, observed_hash, observed_size_bytes, verification_evidence_ref, provider_object_ref, provider_namespace_ref '
        'FROM controlplane.cp_artifact_locations WHERE backend_ref = %s',
        (backend,),
    )


def receipt_rows(rig: Rig) -> list[tuple]:
    return rows(
        rig.db,
        'SELECT operation_key, state, provider_object_ref, verification_evidence_ref '
        'FROM controlplane.cp_upload_receipts',
    )


def test_success_registers_the_version_two_verified_locations_and_a_verified_receipt(rig: Rig):
    result = rig.service(request(), CLAIMS)
    assert result['disposition'] == 'succeeded'

    version_row = rows(
        rig.db,
        'SELECT artifact_version_id, mime_type, artifact_kind, retention_ref, sha256_hash, size_bytes '
        'FROM controlplane.cp_artifact_versions',
    )
    assert len(version_row) == 1
    raw_version_id, mime_type, artifact_kind, retention_ref, sha256_hash, size_bytes = version_row[0]
    version_id = str(raw_version_id)
    assert mime_type == 'video/mp4'
    assert artifact_kind == 'video_output'
    assert retention_ref == 'durable'
    assert sha256_hash == sha(MP4)
    assert size_bytes == len(MP4)

    loc_local = locations(rig, 'local-staging')
    assert len(loc_local) == 1
    assert loc_local[0][0] == 'VERIFIED'
    assert loc_local[0][1] == sha(MP4)
    assert loc_local[0][2] == len(MP4)

    loc_cloud = locations(rig, 'cloud')
    assert len(loc_cloud) == 1
    c_state, c_hash, c_size, c_evidence, c_obj, c_ns = loc_cloud[0]
    assert c_state == 'VERIFIED'
    assert c_ns == NAMESPACE
    assert len(rig.drive.files) == 1
    object_id = list(rig.drive.files.keys())[0]
    assert c_obj == object_id
    assert c_hash == sha(MP4)
    assert c_size == len(MP4)
    assert c_evidence == f'drive:{object_id}:sha256Checksum'

    rc_rows = receipt_rows(rig)
    assert len(rc_rows) == 1
    r_key, r_state, r_obj, r_evidence = rc_rows[0]
    assert r_key == 'persist-output:' + version_id
    assert r_state == 'VERIFIED'
    assert r_obj == object_id
    assert r_evidence == f'drive:{object_id}:sha256Checksum'

    assert rig.drive.files[object_id] == MP4
    assert rig.cloud.completed == 1

    cloud_loc_id = str(rows(rig.db, 'SELECT location_id FROM controlplane.cp_artifact_locations WHERE backend_ref = %s', ('cloud',))[0][0])
    assert result['output_refs'] == [
        {'ref_type': 'output_artifact_version', 'ref_id': version_id},
        {'ref_type': 'cloud_location', 'ref_id': cloud_loc_id},
    ]
    assert result['metrics']['upload_receipt_ref'] == 'persist-output:' + version_id

    ws = rig.db.workspace_id
    with rig.db.connect() as conn:
        repo = PostgresStorageMetaRepository(conn, ws)
        local_loc = repo.find_location(ws, 'local-staging', 'staging', version_id)
        assert local_loc is not None
        release_for_render([{'artifact_version_id': version_id, 'sha256': sha(MP4), 'size_bytes': len(MP4)}], {version_id: local_loc})

    res2 = rig.service(request(key='op-2'), CLAIMS)
    assert res2['disposition'] == 'succeeded'
    assert rig.cloud.attempts == 1
    assert len(rig.drive.files) == 1
    assert count(rig.db, 'cp_artifact_versions') == 1
    assert count(rig.db, 'cp_artifact_locations') == 2


def test_the_receipt_is_committed_before_the_upload_starts(rig: Rig):
    seen = []
    rig.cloud.before = lambda: seen.append(receipt_rows(rig))
    result = rig.service(request(), CLAIMS)
    assert result['disposition'] == 'succeeded'
    assert len(seen) == 1
    rows_seen = seen[0]
    assert len(rows_seen) == 1
    r_key, r_state, r_obj, r_evidence = rows_seen[0]
    assert r_state == 'PREPARED'
    assert r_obj
    object_id = list(rig.drive.files.keys())[0]
    assert r_obj == object_id
    assert r_evidence is None


def test_worker_dying_before_the_upload_resumes_with_a_single_upload(rig: Rig):
    rig.cloud.die_before = True
    with pytest.raises(WorkerDied):
        rig.service(request(), CLAIMS)

    rc = receipt_rows(rig)
    assert len(rc) == 1
    assert rc[0][1] == 'PREPARED'
    chosen = rc[0][2]
    assert chosen
    assert rig.drive.files == {}
    assert locations(rig, 'cloud') == []
    loc_local = locations(rig, 'local-staging')
    assert len(loc_local) == 1 and loc_local[0][0] == 'VERIFIED'

    rig.cloud.die_before = False
    result = rig.service(request(key='op-2'), CLAIMS)
    assert result['disposition'] == 'succeeded'
    assert list(rig.drive.files.keys()) == [chosen]
    assert rig.cloud.completed == 1
    rc2 = receipt_rows(rig)
    assert len(rc2) == 1 and rc2[0][1] == 'VERIFIED' and rc2[0][2] == chosen
    loc_cloud = locations(rig, 'cloud')
    assert len(loc_cloud) == 1 and loc_cloud[0][0] == 'VERIFIED'


def test_worker_dying_after_the_object_reached_drive_does_not_upload_twice(rig: Rig):
    rig.cloud.die_after = True
    with pytest.raises(WorkerDied):
        rig.service(request(), CLAIMS)

    assert len(rig.drive.files) == 1
    assert rig.cloud.attempts == 1 and rig.cloud.completed == 1
    rc = receipt_rows(rig)
    assert len(rc) == 1 and rc[0][1] == 'PREPARED'
    assert locations(rig, 'cloud') == []

    rig.cloud.die_after = False
    result = rig.service(request(key='op-2'), CLAIMS)
    assert result['disposition'] == 'succeeded'
    assert rig.cloud.attempts == 1
    assert rig.drive.initiates == 1
    assert len(rig.drive.files) == 1
    rc2 = receipt_rows(rig)
    assert len(rc2) == 1 and rc2[0][1] == 'VERIFIED'
    loc_cloud = locations(rig, 'cloud')
    assert len(loc_cloud) == 1
    assert loc_cloud[0][0] == 'VERIFIED'
    assert loc_cloud[0][1] == sha(MP4)
    assert loc_cloud[0][2] == len(MP4)


def test_digest_mismatch_never_verifies_the_cloud_location(rig: Rig):
    rig.drive.corrupt_next_upload = True
    result = rig.service(request(), CLAIMS)
    assert result['disposition'] == 'failed'
    assert result['problem']['code'] == 'CLOUD_OBJECT_CORRUPT'
    assert result['problem']['retryable'] is False
    assert result['output_refs'] == []

    loc_cloud = locations(rig, 'cloud')
    assert len(loc_cloud) == 1
    assert loc_cloud[0][0] == 'CORRUPT'
    assert loc_cloud[0][1] is None
    assert loc_cloud[0][2] is None
    assert loc_cloud[0][3] is None

    verified_cloud_count = rows(
        rig.db,
        "SELECT count(*) FROM controlplane.cp_artifact_locations WHERE backend_ref = 'cloud' AND state = 'VERIFIED'",
    )[0][0]
    assert verified_cloud_count == 0

    rc = receipt_rows(rig)
    assert len(rc) == 1
    assert rc[0][1] == 'FAILED'
    assert rc[0][3] is None

    loc_local = locations(rig, 'local-staging')
    assert len(loc_local) == 1 and loc_local[0][0] == 'VERIFIED'


def seed_job(pw_database: Any, status: str = 'ACTIVE', job_id: str = 'job-1', batch_id: str = 'batch-1') -> None:
    with pw_database.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO controlplane.cp_production_batches (batch_id, workspace_id, status, target_count) VALUES (%s, %s, %s, %s)',
                (batch_id, pw_database.workspace_id, 'RUNNING', 1),
            )
            cur.execute(
                'INSERT INTO controlplane.cp_video_jobs (job_id, batch_id, workspace_id, status, snapshot_ref, revision) VALUES (%s, %s, %s, %s, %s, %s)',
                (job_id, batch_id, pw_database.workspace_id, status, 'snap-1', 1),
            )


def job_row(pw_database: Any) -> tuple | None:
    res = rows(
        pw_database,
        'SELECT status, wait_reason FROM controlplane.cp_video_jobs WHERE workspace_id = %s AND job_id = %s',
        (pw_database.workspace_id, 'job-1'),
    )
    return res[0] if res else None


def report(pw_database: Any, result: dict[str, Any]) -> None:
    JobLifecycleListener(pw_database.connect, workspace_id=pw_database.workspace_id).on_result(
        {'stage_run_id': 'job-1:process:r1', 'activity_name': 'PersistVideoOutput'},
        result,
    )


def test_401_waits_with_credential_unavailable_then_completes_exactly_one_object(rig: Rig):
    seed_job(rig.db)
    rig.broker.token = TOKEN_BAD
    result = rig.service(request(), CLAIMS)
    assert result['disposition'] == 'waiting'
    assert result['problem']['code'] == 'credential_unavailable'
    assert result['problem']['retryable'] is True
    assert result['output_refs'] == []

    report(rig.db, result)
    assert job_row(rig.db) == ('WAITING', 'credential_unavailable')
    assert rig.drive.files == {}
    assert locations(rig, 'cloud') == []

    rig.broker.token = TOKEN_OK
    res2 = rig.service(request(key='op-2'), CLAIMS)
    assert res2['disposition'] == 'succeeded'
    report(rig.db, res2)
    assert job_row(rig.db)[0] == 'READY_FOR_COMPLETION'
    assert len(rig.drive.files) == 1
    assert rig.cloud.completed == 1
    assert len(locations(rig, 'cloud')) == 1
    assert locations(rig, 'cloud')[0][0] == 'VERIFIED'
    assert len(receipt_rows(rig)) == 1
    assert receipt_rows(rig)[0][1] == 'VERIFIED'


def test_401_during_the_upload_keeps_the_receipt_and_resumes_without_a_second_object(rig: Rig):
    seed_job(rig.db)
    rig.cloud.before = lambda: setattr(rig.broker, 'token', TOKEN_BAD)
    result = rig.service(request(), CLAIMS)
    assert result['disposition'] == 'waiting'
    assert result['problem']['code'] == 'credential_unavailable'

    rc = receipt_rows(rig)
    assert len(rc) == 1
    assert rc[0][1] == 'PREPARED'
    chosen = rc[0][2]
    assert chosen
    assert rig.drive.files == {}

    rig.cloud.before = None
    rig.broker.token = TOKEN_OK
    res2 = rig.service(request(key='op-2'), CLAIMS)
    assert res2['disposition'] == 'succeeded'
    assert list(rig.drive.files.keys()) == [chosen]
    assert rig.cloud.completed == 1
    assert len(receipt_rows(rig)) == 1
    assert receipt_rows(rig)[0][1] == 'VERIFIED'
    assert receipt_rows(rig)[0][2] == chosen


def test_the_store_reports_401_with_its_own_code_on_every_drive_call(tmp_path: pathlib.Path):
    root = tmp_path / 'staging'
    write(root, 'a1', b'abc')
    drive = LoopbackDrive(TOKEN_OK)
    broker = TokenBroker()
    broker.token = TOKEN_BAD
    store = make_store(root, drive, broker)

    for op in (
        lambda: store.reserve_object_id(NAMESPACE),
        lambda: store.upload('obj-1', 'a1', sha(b'abc'), 3),
        lambda: store.lookup('obj-1'),
    ):
        with pytest.raises(DriveCredentialError) as caught:
            op()
        assert isinstance(caught.value, DriveObjectStoreError)
        assert caught.value.code == DRIVE_CREDENTIAL_INVALID == 'DRIVE_CREDENTIAL_INVALID'
        assert 'HTTP 401' in str(caught.value)
        assert len(drive.calls) == 1
        drive.calls.clear()

    broker.token = TOKEN_OK
    drive.forced_status = 403
    drive.calls.clear()
    with pytest.raises(DriveObjectStoreError) as caught_fatal:
        store.reserve_object_id(NAMESPACE)
    assert type(caught_fatal.value) is DriveObjectStoreError
    assert caught_fatal.value.code is None


class RaisingCloud:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def reserve_object_id(self, namespace_ref: str) -> str:
        raise self.error

    def upload(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError('unreachable')

    def lookup(self, object_id: str) -> Any:
        raise AssertionError('unreachable')


def test_the_handler_maps_the_error_code_and_not_the_message(pw_database: Any, manager: Any, tmp_path: pathlib.Path):
    root = tmp_path / 'staging'
    write(root, 'render/out.mp4', MP4)

    cloud1 = RaisingCloud(DriveCredentialError('boom'))
    service1 = persist_video_output_handler(
        manager,
        workspace_id=pw_database.workspace_id,
        staging_root=root,
        cloud=cloud1,
        namespace_ref=NAMESPACE,
    )
    result1 = service1(request(), CLAIMS)
    assert result1['disposition'] == 'waiting'
    assert result1['problem']['code'] == 'credential_unavailable'

    cloud2 = RaisingCloud(DriveObjectStoreError('Drive request failed: HTTP 401'))
    service2 = persist_video_output_handler(
        manager,
        workspace_id=pw_database.workspace_id,
        staging_root=root,
        cloud=cloud2,
        namespace_ref=NAMESPACE,
    )
    with pytest.raises(DriveObjectStoreError):
        service2(request(), CLAIMS)


def test_input_grant_and_source_validation(pw_database: Any, manager: Any, tmp_path: pathlib.Path):
    root = tmp_path / 'staging'
    cloud = RaisingCloud(AssertionError('unreachable'))
    service = persist_video_output_handler(
        manager,
        workspace_id=pw_database.workspace_id,
        staging_root=root,
        cloud=cloud,
        namespace_ref=NAMESPACE,
    )

    with pytest.raises(ActivityRejected):
        service(request(), None)

    res_empty = service(request(refs=()), CLAIMS)
    assert res_empty['disposition'] == 'failed'
    assert res_empty['problem']['code'] == 'PERSIST_INPUT_INVALID'

    res_two = service(request(refs=(('render_output', 'render/a.mp4'), ('render_output', 'render/b.mp4'))), CLAIMS)
    assert res_two['disposition'] == 'failed'
    assert res_two['problem']['code'] == 'PERSIST_INPUT_INVALID'

    res_not_ready = service(request(), CLAIMS)
    assert res_not_ready['disposition'] == 'waiting'
    assert res_not_ready['problem']['code'] == 'artifact_not_ready'
    assert count(pw_database, 'cp_artifact_versions') == 0

    write(root, 'render/out.wav', b'x')
    with pytest.raises(ActivityRejected):
        service(request(refs=(('render_output', 'render/out.wav'),)), CLAIMS)

    with pytest.raises(ActivityRejected):
        service(request(refs=(('render_output', '../out.mp4'),)), CLAIMS)


def test_handler_source_is_free_of_test_doubles_and_message_matching():
    target = pathlib.Path(__file__).resolve().parents[3] / 'src' / 'controlplane' / 'application' / 'storage_meta' / 'persist_handler.py'
    text = target.read_text(encoding='utf-8')
    assert 'credential_unavailable' in text
    assert 'fake' not in text.lower()
    assert 'from src.' not in text
    assert '401' not in text
    assert '.commit(' not in text
    assert '.rollback(' not in text
