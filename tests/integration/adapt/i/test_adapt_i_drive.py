"""ADAPT-I: Google Drive adapter over a fake transport at the googleapiclient layer (test-only; no real Drive, no real token). Real Drive belongs to CP7-I-01."""
from __future__ import annotations

import hashlib
import inspect
import json
import logging
import urllib.parse
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import httplib2
import pytest

from controlplane.application.config_security.route_resolver import CREDENTIAL_METHOD
from controlplane.infrastructure.security.oauth_google_loopback import ACCOUNT_REF
from controlplane.application.storage_meta.cloud_persist import (
    ObjectAlreadyExistsError,
    PersistArtifactToCloud,
    UploadReceipt,
    UploadReceiptState,
)
from controlplane.domain.statemachine import ArtifactLocationState
from controlplane.domain.storage_meta.verification import evaluate_integrity
import controlplane.infrastructure.storage.drive_object_store as drive_module
from controlplane.infrastructure.storage.drive_object_store import (
    DriveObjectStore,
    DriveObjectStoreError,
    DriveQuotaError,
    DriveStoreConfig,
)

TOKEN = 'CANARY-ADAPT-I-ACCESS-7f3c'
CHUNK = 262144


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def payload(n: int) -> bytes:
    return bytes((i * 7 + 3) % 251 for i in range(n))


class FakeClock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeBroker:
    def __init__(self, token: str = TOKEN) -> None:
        self.token = token
        self.calls: list[tuple[str, str]] = []

    @contextmanager
    def acquire(self, credential_method: str, account_ref: str) -> Iterator[str]:
        self.calls.append((credential_method, account_ref))
        yield self.token


class FakeSource:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def put(self, avid: str, data: bytes) -> Path:
        p = self._root / avid
        p.write_bytes(data)
        return p

    def open(self, avid: str):
        return (self._root / avid).open('rb')


class MemoryReceipts:
    def __init__(self) -> None:
        self._receipts: dict[str, UploadReceipt] = {}

    def get(self, operation_key: str) -> UploadReceipt | None:
        return self._receipts.get(operation_key)

    def save(self, receipt: UploadReceipt) -> None:
        self._receipts[receipt.operation_key] = receipt


@dataclass
class Env:
    fake: FakeDriveHttp
    broker: FakeBroker
    source: FakeSource
    clock: FakeClock
    sleeps: list[float]
    store: DriveObjectStore


def make_config(**overrides: object) -> DriveStoreConfig:
    kwargs: dict[str, object] = {
        'chunk_bytes': CHUNK,
        'chunk_timeout_seconds': 5.0,
        'retry_max_attempts': 5,
        'retry_backoff_base_seconds': 2.0,
        'retry_backoff_cap_seconds': 8.0,
        'session_ttl_seconds': 1000,
        'quota_reserve_ratio': 0.2,
        'placement': {'ns-original': 'folder-original'},
        'fallback_parent_id': 'folder-fallback',
    }
    kwargs.update(overrides)
    return DriveStoreConfig(**kwargs)  # type: ignore[arg-type]


def make_env(tmp_path: Path, **overrides: object) -> Env:
    clock = FakeClock()
    broker = FakeBroker()
    source = FakeSource(tmp_path)
    sleeps: list[float] = []
    fake = FakeDriveHttp()
    store = DriveObjectStore(
        make_config(**overrides),
        broker,
        source,
        http_factory=lambda timeout: fake,
        sleep=sleeps.append,
        clock=clock,
    )
    return Env(
        fake=fake,
        broker=broker,
        source=source,
        clock=clock,
        sleeps=sleeps,
        store=store,
    )


class FakeDriveHttp:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.files: dict[str, dict] = {}
        self.sessions: dict[str, dict] = {}
        self.faults: dict[str, list[tuple]] = {}
        self.always: dict[str, tuple] = {}
        self.next_ids: list[str] = []
        self.quota: dict = {'limit': '1000000000', 'usage': '0'}
        self.error_echo: str = ''
        self.hook: Callable[[int], None] | None = None
        self.initiate_bodies: list[dict] = []
        self.put_sizes: list[int] = []
        self.media_ranges: list[tuple[int, int]] = []
        self._auto_id_seq: int = 0
        self._session_seq: int = 0
        self._put_counter: int = 0

    def count(self, op: str) -> int:
        return sum(1 for c in self.calls if c['op'] == op)

    def add_file(self, file_id: str, data: bytes, with_sha256: bool = True, trashed: bool = False) -> None:
        self.files[file_id] = {
            'data': data,
            'parents': [],
            'name': file_id,
            'appProperties': {},
            'trashed': trashed,
            'with_sha256': with_sha256,
        }

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
            body_bytes = body.read()  # type: ignore[union-attr]
        elif isinstance(body, str):
            body_bytes = body.encode('utf-8')
        elif isinstance(body, (bytes, bytearray)):
            body_bytes = bytes(body)
        else:
            body_bytes = b''

        split = urllib.parse.urlsplit(uri)
        path = split.path
        query = urllib.parse.parse_qs(split.query)

        if path.endswith('/drive/v3/files/generateIds'):
            op = 'generate'
        elif path.endswith('/drive/v3/about'):
            op = 'about'
        elif path.endswith('/upload/drive/v3/files') and method == 'POST':
            op = 'initiate'
        elif uri in self.sessions or path.startswith('/session/'):
            content_range = headers_lower.get('content-range', '')
            if content_range.startswith('bytes */'):
                op = 'query'
            else:
                op = 'put'
        elif '/drive/v3/files/' in path and method == 'GET':
            if 'alt' in query and 'media' in query['alt']:
                op = 'media'
            else:
                op = 'meta'
        else:
            op = 'unknown'

        self.calls.append({
            'op': op,
            'method': method,
            'uri': uri,
            'headers': headers_lower,
            'body': body_bytes,
        })

        if op == 'put':
            self._put_counter += 1
            if self.hook is not None:
                self.hook(self._put_counter)

        fault = None
        if op != 'query':
            if op in self.faults and self.faults[op]:
                fault = self.faults[op].pop(0)
            elif op in self.always:
                fault = self.always[op]

        if fault is not None:
            if fault[0] == 'timeout':
                raise TimeoutError('fault timeout')
            if fault[0] == 'status':
                code = fault[1]
                reason = fault[2] if len(fault) > 2 else None
                errors = [{'reason': reason}] if reason is not None else []
                err_payload = {
                    'error': {
                        'code': code,
                        'message': 'fault ' + self.error_echo,
                        'errors': errors,
                    }
                }
                resp = httplib2.Response({'status': str(code), 'content-type': 'application/json'})
                return resp, json.dumps(err_payload).encode('utf-8')

        if op == 'generate':
            self._auto_id_seq += 1
            fid = self.next_ids.pop(0) if self.next_ids else f'fid-auto-{self._auto_id_seq}'
            resp = httplib2.Response({'status': '200', 'content-type': 'application/json'})
            return resp, json.dumps({'kind': 'drive#generatedIds', 'space': 'drive', 'ids': [fid]}).encode('utf-8')

        if op == 'about':
            resp = httplib2.Response({'status': '200', 'content-type': 'application/json'})
            return resp, json.dumps({'storageQuota': self.quota}).encode('utf-8')

        if op == 'initiate':
            body_json = json.loads(body_bytes.decode('utf-8'))
            self.initiate_bodies.append(body_json)
            fid = body_json.get('id')
            if fid in self.files:
                resp = httplib2.Response({'status': '409', 'content-type': 'application/json'})
                err_payload = {'error': {'code': 409, 'message': 'File already exists: ' + str(fid)}}
                return resp, json.dumps(err_payload).encode('utf-8')
            self._session_seq += 1
            session_uri = f'https://fake.drive/session/{self._session_seq}'
            self.sessions[session_uri] = {
                'id': fid,
                'body': body_json,
                'data': bytearray(),
            }
            resp = httplib2.Response({
                'status': '200',
                'location': session_uri,
                'content-type': 'application/json',
            })
            return resp, b'{}'

        if op == 'query':
            session = self.sessions.get(uri)
            if session is None:
                for s_uri, s_val in self.sessions.items():
                    if urllib.parse.urlsplit(s_uri).path == split.path:
                        session = s_val
                        break
            if session is None:
                resp = httplib2.Response({'status': '404', 'content-type': 'application/json'})
                return resp, b'{}'
            fid = session['id']
            if fid in self.files:
                resp = httplib2.Response({'status': '200', 'content-type': 'application/json'})
                return resp, json.dumps({'id': fid}).encode('utf-8')
            n = len(session['data'])
            resp_headers = {'status': '308', 'content-type': 'application/json'}
            if n > 0:
                resp_headers['range'] = f'bytes=0-{n - 1}'
            return httplib2.Response(resp_headers), b'{}'

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
            parts = content_range[len('bytes '):].split('/')
            range_part = parts[0]
            total = int(parts[1])
            a_str, b_str = range_part.split('-')
            a = int(a_str)
            b = int(b_str)
            chunk = body_bytes
            self.put_sizes.append(len(chunk))
            data = session['data']
            if a > len(data):
                data.extend(b'\x00' * (a - len(data)))
            data[a:a + len(chunk)] = chunk
            if len(data) == total:
                fid = session['id']
                b_body = session['body']
                self.files[fid] = {
                    'data': bytes(data),
                    'parents': b_body.get('parents', []),
                    'name': b_body.get('name', ''),
                    'appProperties': b_body.get('appProperties', {}),
                    'trashed': False,
                    'with_sha256': True,
                }
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
                return resp, json.dumps({'error': {'code': 404, 'message': 'File not found'}}).encode('utf-8')
            fmeta = self.files[fid]
            data = fmeta['data']
            meta_payload = {
                'id': fid,
                'size': str(len(data)),
                'md5Checksum': hashlib.md5(data, usedforsecurity=False).hexdigest(),
                'trashed': fmeta.get('trashed', False),
            }
            if fmeta.get('with_sha256', True):
                meta_payload['sha256Checksum'] = hashlib.sha256(data).hexdigest()
            resp = httplib2.Response({'status': '200', 'content-type': 'application/json'})
            return resp, json.dumps(meta_payload).encode('utf-8')

        if op == 'media':
            fid = path.split('/drive/v3/files/')[-1]
            if fid not in self.files:
                resp = httplib2.Response({'status': '404', 'content-type': 'application/json'})
                return resp, json.dumps({'error': {'code': 404, 'message': 'File not found'}}).encode('utf-8')
            data = self.files[fid]['data']
            range_header = headers_lower.get('range', '')
            a, b = 0, len(data) - 1
            if range_header.startswith('bytes='):
                r_parts = range_header[len('bytes='):].split('-')
                a = int(r_parts[0])
                if r_parts[1]:
                    b = int(r_parts[1])
            self.media_ranges.append((a, b))
            end_slice = min(b, len(data) - 1)
            slice_data = data[a:end_slice + 1]
            resp = httplib2.Response({
                'status': '206',
                'content-range': f'bytes {a}-{end_slice}/{len(data)}',
                'content-type': 'application/octet-stream',
            })
            return resp, slice_data

        resp = httplib2.Response({'status': '400', 'content-type': 'application/json'})
        return resp, b'{}'


@pytest.mark.parametrize(
    'override',
    [
        {'chunk_bytes': 1000},
        {'chunk_bytes': True},
        {'retry_max_attempts': 0},
        {'retry_backoff_cap_seconds': 1.0},
        {'quota_reserve_ratio': 1.0},
        {'quota_reserve_ratio': -0.1},
        {'session_ttl_seconds': 0},
        {'placement': {}},
        {'fallback_parent_id': ''},
    ],
)
def test_config_requires_values_and_rejects_invalid(override: dict[str, object]) -> None:
    with pytest.raises(TypeError):
        DriveStoreConfig(chunk_bytes=CHUNK)  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        make_config(**override)


def test_reserve_object_id_uses_generate_ids(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    env.fake.next_ids = ['fid-1']
    fid = env.store.reserve_object_id('ns-original')
    assert fid == 'fid-1'
    assert env.fake.count('generate') == 1
    gen_calls = [c for c in env.fake.calls if c['op'] == 'generate']
    assert len(gen_calls) == 1
    assert 'generateIds' in gen_calls[0]['uri']
    assert 'count=1' in gen_calls[0]['uri']
    with pytest.raises(DriveObjectStoreError):
        env.store.reserve_object_id('ns-unknown')
    assert env.fake.count('generate') == 1


def test_upload_is_resumable_chunked_into_reserved_id(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    env.fake.next_ids = ['fid-1']
    fid = env.store.reserve_object_id('ns-original')
    data = payload(3 * CHUNK + 100)
    env.source.put('av-1', data)
    env.store.upload(fid, 'av-1', sha(data), len(data))
    assert env.fake.files['fid-1']['data'] == data
    assert len(env.fake.files) == 1
    assert env.fake.initiate_bodies[0]['id'] == 'fid-1'
    assert env.fake.files['fid-1']['parents'] == ['folder-original']
    assert env.fake.files['fid-1']['appProperties']['content_sha256'] == sha(data)
    assert env.fake.put_sizes == [CHUNK, CHUNK, CHUNK, 100]
    assert env.fake.count('initiate') == 1


def test_retry_after_503_reuses_session_and_creates_no_second_file(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    env.fake.next_ids = ['fid-1']
    fid = env.store.reserve_object_id('ns-original')
    data = payload(2 * CHUNK)
    env.source.put('av-1', data)
    env.fake.faults['put'] = [('status', 503, None), ('status', 503, None)]
    env.store.upload(fid, 'av-1', sha(data), len(data))
    assert env.sleeps == [2.0, 4.0]
    assert env.fake.count('initiate') == 1
    assert len(env.fake.files) == 1
    assert env.fake.files['fid-1']['data'] == data


def test_backoff_is_capped(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    env.fake.next_ids = ['fid-1']
    fid = env.store.reserve_object_id('ns-original')
    data = payload(CHUNK)
    env.source.put('av-1', data)
    env.fake.faults['put'] = [('status', 503, None)] * 4
    env.store.upload(fid, 'av-1', sha(data), len(data))
    assert env.sleeps == [2.0, 4.0, 8.0, 8.0]


def test_rate_limit_403_is_retried_but_other_403_fails_fast(tmp_path: Path) -> None:
    env1 = make_env(tmp_path / 'env1')
    env1.fake.next_ids = ['fid-1']
    fid1 = env1.store.reserve_object_id('ns-original')
    data1 = payload(CHUNK)
    env1.source.put('av-1', data1)
    env1.fake.faults['put'] = [('status', 403, 'rateLimitExceeded')]
    env1.store.upload(fid1, 'av-1', sha(data1), len(data1))
    assert env1.sleeps == [2.0]

    env2 = make_env(tmp_path / 'env2')
    env2.fake.next_ids = ['fid-2']
    fid2 = env2.store.reserve_object_id('ns-original')
    data2 = payload(CHUNK)
    env2.source.put('av-2', data2)
    env2.fake.faults['put'] = [('status', 403, 'forbidden')]
    with pytest.raises(DriveObjectStoreError) as exc_info:
        env2.store.upload(fid2, 'av-2', sha(data2), len(data2))
    assert '403' in str(exc_info.value)
    assert env2.sleeps == []
    assert env2.fake.count('put') == 1


def test_http_409_raises_object_already_exists(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    data = payload(CHUNK)
    env.fake.add_file('fid-1', data)
    env.source.put('av-1', data)
    with pytest.raises(ObjectAlreadyExistsError):
        env.store.upload('fid-1', 'av-1', sha(data), len(data))
    assert env.fake.count('put') == 0
    assert env.sleeps == []
    assert len(env.fake.files) == 1


def test_409_is_reconciled_by_persist_port(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    data = payload(CHUNK)
    env.fake.add_file('fid-1', data)
    env.fake.next_ids = ['fid-1']
    env.source.put('av-1', data)
    port = PersistArtifactToCloud(env.store, MemoryReceipts())
    result = port.execute('av-1', sha(data), len(data), True, 'ns-original', 'op-1', 'grant-1')
    assert result.state is ArtifactLocationState.VERIFIED
    assert result.object_id == 'fid-1'


@pytest.mark.parametrize('status', [404, 410])
def test_expired_session_opens_new_session_with_same_file_id(tmp_path: Path, status: int) -> None:
    env = make_env(tmp_path)
    env.fake.next_ids = ['fid-1']
    fid = env.store.reserve_object_id('ns-original')
    data = payload(2 * CHUNK)
    env.source.put('av-1', data)
    env.fake.faults['put'] = [('status', status, None)]
    env.store.upload(fid, 'av-1', sha(data), len(data))
    assert env.fake.count('initiate') == 2
    assert env.fake.initiate_bodies[0]['id'] == 'fid-1'
    assert env.fake.initiate_bodies[1]['id'] == 'fid-1'
    assert len(env.fake.files) == 1
    assert env.fake.files['fid-1']['data'] == data
    assert env.sleeps == []


def test_session_older_than_ttl_is_renewed(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    env.fake.next_ids = ['fid-1']
    fid = env.store.reserve_object_id('ns-original')
    data = payload(3 * CHUNK)
    env.source.put('av-1', data)
    env.fake.hook = lambda n: env.clock.advance(1001.0) if n == 1 else None
    env.store.upload(fid, 'av-1', sha(data), len(data))
    assert env.fake.count('initiate') == 2
    assert env.fake.initiate_bodies[0]['id'] == 'fid-1'
    assert env.fake.initiate_bodies[1]['id'] == 'fid-1'
    assert len(env.fake.files) == 1
    assert env.fake.files['fid-1']['data'] == data


def test_session_renewals_are_bounded(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    env.fake.next_ids = ['fid-1']
    fid = env.store.reserve_object_id('ns-original')
    data = payload(CHUNK)
    env.source.put('av-1', data)
    env.fake.always['put'] = ('status', 404, None)
    with pytest.raises(DriveObjectStoreError):
        env.store.upload(fid, 'av-1', sha(data), len(data))
    assert env.fake.count('initiate') == 5
    assert env.fake.files == {}


@pytest.mark.parametrize('op', ['initiate', 'put'])
def test_timeout_exhaustion_raises_timeout_error(tmp_path: Path, op: str) -> None:
    env = make_env(tmp_path)
    env.fake.next_ids = ['fid-1']
    fid = env.store.reserve_object_id('ns-original')
    data = payload(CHUNK)
    env.source.put('av-1', data)
    env.fake.always[op] = ('timeout',)
    with pytest.raises(TimeoutError):
        env.store.upload(fid, 'av-1', sha(data), len(data))
    assert env.sleeps == [2.0, 4.0, 8.0, 8.0]


def test_timeout_becomes_outcome_unknown_then_same_file_id_completes(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    data = payload(CHUNK)
    env.source.put('av-1', data)
    receipts = MemoryReceipts()
    port = PersistArtifactToCloud(env.store, receipts)
    env.fake.next_ids = ['fid-9']
    env.fake.always['put'] = ('timeout',)
    res1 = port.execute('av-1', sha(data), len(data), True, 'ns-original', 'op-1', 'grant-1')
    assert res1.state is ArtifactLocationState.OUTCOME_UNKNOWN
    receipt = receipts.get('op-1')
    assert receipt is not None
    assert receipt.state is UploadReceiptState.OUTCOME_UNKNOWN
    env.fake.always.clear()
    res2 = port.execute('av-1', sha(data), len(data), True, 'ns-original', 'op-1', 'grant-1')
    assert res2.state is ArtifactLocationState.VERIFIED
    assert res2.object_id == 'fid-9'
    assert env.fake.count('generate') == 1
    assert len(env.fake.files) == 1


def test_source_size_mismatch_is_rejected_before_any_request(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    data = payload(CHUNK)
    env.source.put('av-1', data)
    with pytest.raises(ValueError):
        env.store.upload('fid-1', 'av-1', sha(data), len(data) + 1)
    assert env.fake.calls == []


def test_lookup_uses_sha256_checksum_metadata_without_download(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    data = payload(CHUNK + 7)
    env.fake.add_file('f1', data, with_sha256=True)
    obs = env.store.lookup('f1')
    assert obs.object_present is True
    assert obs.observed_sha256 == sha(data)
    assert obs.observed_size_bytes == len(data)
    assert isinstance(obs.evidence_ref, str) and obs.evidence_ref != ''
    assert env.fake.count('media') == 0
    assert evaluate_integrity(sha(data), len(data), obs) is ArtifactLocationState.VERIFIED
    meta_calls = [c for c in env.fake.calls if c['op'] == 'meta']
    assert len(meta_calls) == 1
    assert 'md5' not in meta_calls[0]['uri'].lower()


def test_lookup_without_sha256_downloads_in_chunks_and_ignores_md5(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    data = payload(2 * CHUNK + 5)
    env.fake.add_file('f1', data, with_sha256=False)
    obs = env.store.lookup('f1')
    assert obs.observed_sha256 == sha(data)
    assert env.fake.count('media') == 3
    assert all(b - a + 1 == CHUNK for a, b in env.fake.media_ranges)
    assert obs.observed_size_bytes == len(data)
    assert evaluate_integrity(sha(data), len(data), obs) is ArtifactLocationState.VERIFIED
    assert 'BytesIO' not in Path(drive_module.__file__).read_text(encoding='utf-8')


def test_lookup_download_detects_corrupt(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    data = payload(CHUNK)
    expected = payload(CHUNK + 1)
    env.fake.add_file('f1', data, with_sha256=False)
    obs = env.store.lookup('f1')
    assert evaluate_integrity(sha(expected), len(expected), obs) is ArtifactLocationState.CORRUPT


def test_lookup_missing_and_trashed(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    obs_missing = env.store.lookup('non-existent-id')
    assert obs_missing.object_present is False
    assert evaluate_integrity('a' * 64, 10, obs_missing) is ArtifactLocationState.MISSING
    data = payload(10)
    env.fake.add_file('f2', data, trashed=True)
    obs_trashed = env.store.lookup('f2')
    assert obs_trashed.object_present is False
    assert evaluate_integrity(sha(data), 10, obs_trashed) is ArtifactLocationState.MISSING


def test_lookup_timeout_raises_timeout_error(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    env.fake.always['meta'] = ('timeout',)
    with pytest.raises(TimeoutError):
        env.store.lookup('f1')
    assert env.sleeps == [2.0, 4.0, 8.0, 8.0]


def test_upload_refused_when_projected_free_space_below_reserve(tmp_path: Path) -> None:
    env1 = make_env(tmp_path / 'env1')
    env1.fake.quota = {'limit': '1000000', 'usage': '700000'}
    env1.fake.next_ids = ['fid-1']
    fid1 = env1.store.reserve_object_id('ns-original')
    data_big = payload(150000)
    env1.source.put('av-big', data_big)
    with pytest.raises(DriveQuotaError):
        env1.store.upload(fid1, 'av-big', sha(data_big), len(data_big))
    assert env1.fake.count('initiate') == 0
    assert env1.fake.count('put') == 0
    assert env1.sleeps == []

    env2 = make_env(tmp_path / 'env2')
    env2.fake.quota = {'limit': '1000000', 'usage': '700000'}
    env2.fake.next_ids = ['fid-2']
    fid2 = env2.store.reserve_object_id('ns-original')
    data_small = payload(50000)
    env2.source.put('av-small', data_small)
    env2.store.upload(fid2, 'av-small', sha(data_small), len(data_small))
    assert len(env2.fake.files) == 1

    env3 = make_env(tmp_path / 'env3')
    env3.fake.quota = {'usage': '5'}
    env3.fake.next_ids = ['fid-3']
    fid3 = env3.store.reserve_object_id('ns-original')
    data3 = payload(150000)
    env3.source.put('av-3', data3)
    env3.store.upload(fid3, 'av-3', sha(data3), len(data3))
    assert len(env3.fake.files) == 1


def test_access_token_only_from_broker_and_never_logged(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    env = make_env(tmp_path)
    env.fake.error_echo = TOKEN
    env.fake.next_ids = ['fid-1', 'fid-2']
    fid1 = env.store.reserve_object_id('ns-original')
    data1 = payload(CHUNK)
    env.source.put('av-1', data1)
    env.fake.faults['put'] = [('status', 503, None)]
    env.store.upload(fid1, 'av-1', sha(data1), len(data1))
    env.fake.add_file('f-dl', data1, with_sha256=False)
    env.store.lookup('f-dl')
    fid2 = env.store.reserve_object_id('ns-original')
    data2 = payload(CHUNK)
    env.source.put('av-2', data2)
    env.fake.faults['put'] = [('status', 403, 'forbidden')]
    with pytest.raises(DriveObjectStoreError) as exc_info:
        env.store.upload(fid2, 'av-2', sha(data2), len(data2))
    assert len(env.fake.calls) > 0
    for call in env.fake.calls:
        assert call['headers'].get('authorization') == 'Bearer ' + TOKEN
    assert env.broker.calls == [(CREDENTIAL_METHOD, ACCOUNT_REF)] * len(env.fake.calls)
    assert TOKEN not in caplog.text
    assert TOKEN not in str(exc_info.value)


def test_adapter_holds_no_refresh_token_and_no_src_import(tmp_path: Path) -> None:
    text = Path(drive_module.__file__).read_text(encoding='utf-8')
    assert 'refresh' not in text.lower()
    assert 'from src.' not in text
    sig = inspect.signature(DriveObjectStore.__init__)
    for param in sig.parameters.values():
        assert 'refresh' not in param.name.lower()
    env = make_env(tmp_path)
    for k, v in vars(env.store).items():
        assert 'refresh' not in k.lower()
        assert 'token' not in k.lower()


def test_default_http_keeps_308_as_resume_incomplete_instead_of_a_redirect(tmp_path: Path) -> None:
    """Drive answers every non-final resumable chunk with 308 and no Location; the store's default client must return it."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class ResumeIncomplete(BaseHTTPRequestHandler):
        def do_PUT(self) -> None:
            self.rfile.read(int(self.headers.get('Content-Length', '0')))
            self.send_response(308)
            self.send_header('Range', 'bytes=0-3')
            self.send_header('Content-Length', '0')
            self.end_headers()

        def log_message(self, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), ResumeIncomplete)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f'http://127.0.0.1:{server.server_address[1]}/upload/drive/v3/files?upload_id=x'
        with pytest.raises(httplib2.RedirectMissingLocation):
            httplib2.Http(timeout=5).request(url, method='PUT', body=b'data')
        store = DriveObjectStore(make_config(), FakeBroker(), FakeSource(tmp_path))
        response, _ = store._http_factory(5).request(url, method='PUT', body=b'data')
        assert response.status == 308
    finally:
        server.shutdown()
        server.server_close()
