"""ADAPT-I: Google Drive adapter implementing CloudObjectPort (CT-STO-003, ADR-0006); real Drive is verified at CP7-I-01."""
from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager, closing
from dataclasses import dataclass
from typing import BinaryIO, Protocol

import httplib2
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from controlplane.application.config_security.route_resolver import CREDENTIAL_METHOD
from controlplane.application.storage_meta.cloud_persist import CloudObjectPort, ObjectAlreadyExistsError
from controlplane.domain.storage_meta.verification import IntegrityObservation
from controlplane.infrastructure.security.oauth_google_loopback import ACCOUNT_REF

_LOGGER = logging.getLogger(__name__)
_CHUNK_ALIGNMENT = 262144
_OCTET_STREAM = 'application/octet-stream'
_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})
_RATE_LIMIT_REASONS = frozenset({'rateLimitExceeded', 'userRateLimitExceeded'})
_HEX = frozenset('0123456789abcdef')
_RESUME_INCOMPLETE = 308


def drive_http(timeout: float) -> httplib2.Http:
    """httplib2 client for Google Drive. Drive answers every non-final resumable chunk with 308 Resume Incomplete and no Location;
    httplib2 treats 308 as a redirect by default and raises RedirectMissingLocation, so 308 is removed from the redirect codes
    exactly as googleapiclient.http.build_http does."""
    http = httplib2.Http(timeout=timeout)
    http.redirect_codes = http.redirect_codes - {_RESUME_INCOMPLETE}
    return http


class DriveObjectStoreError(Exception):
    pass


class DriveQuotaError(DriveObjectStoreError):
    pass


class ArtifactSourcePort(Protocol):
    def open(self, artifact_version_id: str) -> BinaryIO: ...


class DriveTokenBrokerPort(Protocol):
    def acquire(self, credential_method: str, account_ref: str) -> AbstractContextManager[str]: ...


@dataclass(frozen=True)
class DriveStoreConfig:
    chunk_bytes: int
    chunk_timeout_seconds: float
    retry_max_attempts: int
    retry_backoff_base_seconds: float
    retry_backoff_cap_seconds: float
    session_ttl_seconds: int
    quota_reserve_ratio: float
    placement: Mapping[str, str]
    fallback_parent_id: str

    def __post_init__(self) -> None:
        if isinstance(self.chunk_bytes, bool) or not isinstance(self.chunk_bytes, int) or self.chunk_bytes <= 0 or self.chunk_bytes % _CHUNK_ALIGNMENT != 0:
            raise ValueError('chunk_bytes must be a positive integer aligned to 256 KiB')
        if isinstance(self.chunk_timeout_seconds, bool) or not isinstance(self.chunk_timeout_seconds, (int, float)) or self.chunk_timeout_seconds <= 0:
            raise ValueError('chunk_timeout_seconds must be a positive number')
        if isinstance(self.retry_max_attempts, bool) or not isinstance(self.retry_max_attempts, int) or self.retry_max_attempts < 1:
            raise ValueError('retry_max_attempts must be an integer >= 1')
        if isinstance(self.retry_backoff_base_seconds, bool) or not isinstance(self.retry_backoff_base_seconds, (int, float)) or self.retry_backoff_base_seconds <= 0:
            raise ValueError('retry_backoff_base_seconds must be a positive number')
        if isinstance(self.retry_backoff_cap_seconds, bool) or not isinstance(self.retry_backoff_cap_seconds, (int, float)) or self.retry_backoff_cap_seconds < self.retry_backoff_base_seconds:
            raise ValueError('retry_backoff_cap_seconds must be >= retry_backoff_base_seconds')
        if isinstance(self.session_ttl_seconds, bool) or not isinstance(self.session_ttl_seconds, int) or self.session_ttl_seconds <= 0:
            raise ValueError('session_ttl_seconds must be a positive integer')
        if isinstance(self.quota_reserve_ratio, bool) or not isinstance(self.quota_reserve_ratio, (int, float)) or not (0 <= self.quota_reserve_ratio < 1):
            raise ValueError('quota_reserve_ratio must be in [0, 1)')
        if not isinstance(self.placement, Mapping) or not self.placement:
            raise ValueError('placement must be a non-empty mapping')
        for k, v in self.placement.items():
            if not isinstance(k, str) or not k or not isinstance(v, str) or not v:
                raise ValueError('placement keys and values must be non-empty strings')
        if not isinstance(self.fallback_parent_id, str) or not self.fallback_parent_id:
            raise ValueError('fallback_parent_id must be a non-empty string')


def _describe(exc: BaseException) -> str:
    if isinstance(exc, HttpError):
        return 'HTTP ' + str(exc.resp.status)
    return type(exc).__name__


def _has_rate_limit_reason(exc: HttpError) -> bool:
    try:
        errors = json.loads(exc.content.decode('utf-8'))['error']['errors']
        return any(isinstance(e, dict) and e.get('reason') in _RATE_LIMIT_REASONS for e in errors)
    except (ValueError, KeyError, TypeError, AttributeError):
        return False


def _failure_kind(exc: BaseException) -> str:
    if isinstance(exc, HttpError):
        status = exc.resp.status
        if status == 409:
            return 'exists'
        if status in (404, 410):
            return 'expired'
        if status in _RETRYABLE_STATUS:
            return 'retry'
        if status == 403 and _has_rate_limit_reason(exc):
            return 'retry'
        return 'fatal'
    if isinstance(exc, TimeoutError):
        return 'timeout'
    return 'retry'


class _BrokerHttp:
    def __init__(self, inner: httplib2.Http, broker: DriveTokenBrokerPort) -> None:
        self._inner = inner
        self._broker = broker

    def request(
        self,
        uri: str,
        method: str = 'GET',
        body: object = None,
        headers: Mapping[str, str] | None = None,
        **kwargs: object,
    ) -> tuple[httplib2.Response, bytes]:
        merged = dict(headers or {})
        with self._broker.acquire(CREDENTIAL_METHOD, ACCOUNT_REF) as token:
            merged['Authorization'] = 'Bearer ' + token
            return self._inner.request(uri, method=method, body=body, headers=merged, **kwargs)

    def close(self) -> None:
        self._inner.close()


class _HashingSink:
    def __init__(self) -> None:
        self._digest = hashlib.sha256()
        self.size = 0

    def write(self, data: bytes) -> int:
        self._digest.update(data)
        self.size += len(data)
        return len(data)

    def hexdigest(self) -> str:
        return self._digest.hexdigest()


class DriveObjectStore(CloudObjectPort):
    def __init__(
        self,
        config: DriveStoreConfig,
        broker: DriveTokenBrokerPort,
        source: ArtifactSourcePort,
        *,
        http_factory: Callable[[float], httplib2.Http] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config
        self._broker = broker
        self._source = source
        self._http_factory = http_factory or drive_http
        self._sleep = sleep
        self._clock = clock
        self._parents: dict[str, str] = {}

    def _open_service(self) -> object:
        return build(
            'drive',
            'v3',
            http=_BrokerHttp(self._http_factory(self._config.chunk_timeout_seconds), self._broker),
            static_discovery=True,
            cache_discovery=False,
        )

    def _backoff(self, failures: int) -> float:
        return min(
            self._config.retry_backoff_cap_seconds,
            self._config.retry_backoff_base_seconds * 2 ** (failures - 1),
        )

    def _run(self, operation: Callable[[], object]) -> object:
        failures = 0
        while True:
            try:
                return operation()
            except (HttpError, OSError, httplib2.HttpLib2Error) as exc:
                kind = _failure_kind(exc)
                if kind == 'exists':
                    raise ObjectAlreadyExistsError('Drive file id already exists') from None
                if kind in ('expired', 'fatal'):
                    raise DriveObjectStoreError('Drive request failed: ' + _describe(exc)) from None
                failures += 1
                _LOGGER.warning(
                    'drive request failed (%s), attempt %d of %d',
                    _describe(exc),
                    failures,
                    self._config.retry_max_attempts,
                )
                if failures >= self._config.retry_max_attempts:
                    if kind == 'timeout':
                        raise TimeoutError('Drive request timed out after retries') from None
                    raise DriveObjectStoreError('Drive request failed after retries: ' + _describe(exc)) from None
                self._sleep(self._backoff(failures))

    def reserve_object_id(self, namespace_ref: str) -> str:
        if not isinstance(namespace_ref, str) or not namespace_ref.strip():
            raise ValueError('namespace_ref must be a non-empty string')
        parent_id = self._config.placement.get(namespace_ref)
        if parent_id is None:
            raise DriveObjectStoreError('placement is not configured for namespace_ref')

        def fetch() -> object:
            with closing(self._open_service()) as service:
                return service.files().generateIds(count=1, space='drive').execute()  # type: ignore[attr-defined]

        result = self._run(fetch)
        ids = result.get('ids') if isinstance(result, dict) else None
        if not isinstance(ids, list) or len(ids) != 1 or not isinstance(ids[0], str) or not ids[0]:
            raise DriveObjectStoreError('Drive generateIds returned no usable id')
        self._parents[ids[0]] = parent_id
        return ids[0]

    def _check_quota(self, size_bytes: int) -> None:
        def fetch() -> object:
            with closing(self._open_service()) as service:
                return service.about().get(fields='storageQuota').execute()  # type: ignore[attr-defined]

        about = self._run(fetch)
        quota = about.get('storageQuota') or {} if isinstance(about, dict) else {}
        limit = quota.get('limit')
        if limit is None:
            return
        try:
            limit_bytes = int(limit)
            usage_bytes = int(quota.get('usage', 0))
        except (TypeError, ValueError):
            raise DriveObjectStoreError('Drive storageQuota is malformed') from None
        if limit_bytes - usage_bytes - size_bytes < self._config.quota_reserve_ratio * limit_bytes:
            raise DriveQuotaError('projected free space is below quota_reserve_ratio')

    def _new_upload_request(
        self,
        service: object,
        stream: BinaryIO,
        object_id: str,
        artifact_version_id: str,
        content_sha256: str,
        parent_id: str,
    ) -> object:
        media = MediaIoBaseUpload(stream, mimetype=_OCTET_STREAM, chunksize=self._config.chunk_bytes, resumable=True)
        body = {
            'id': object_id,
            'name': artifact_version_id,
            'parents': [parent_id],
            'appProperties': {
                'artifact_version_id': artifact_version_id,
                'content_sha256': content_sha256,
            },
        }
        return service.files().create(body=body, media_body=media, fields='id')  # type: ignore[attr-defined]

    def upload(self, object_id: str, artifact_version_id: str, content_sha256: str, size_bytes: int) -> None:
        if not isinstance(object_id, str) or not object_id:
            raise ValueError('object_id must be a non-empty string')
        if not isinstance(artifact_version_id, str) or not artifact_version_id:
            raise ValueError('artifact_version_id must be a non-empty string')
        if not isinstance(content_sha256, str) or len(content_sha256) != 64 or not (set(content_sha256) <= _HEX):
            raise ValueError('content_sha256 must be a 64-character lowercase hex string')
        if type(size_bytes) is not int or size_bytes < 0:
            raise ValueError('size_bytes must be a non-negative integer')

        parent_id = self._parents.get(object_id, self._config.fallback_parent_id)

        with self._source.open(artifact_version_id) as stream:
            stream.seek(0, 2)
            if stream.tell() != size_bytes:
                raise ValueError('source size does not match size_bytes')
            stream.seek(0)
            self._check_quota(size_bytes)
            with closing(self._open_service()) as service:
                cfg = self._config
                failures = 0
                sessions = 0
                request = None
                started = 0.0
                while True:
                    if request is not None and self._clock() - started >= cfg.session_ttl_seconds:
                        request = None
                    if request is None:
                        sessions += 1
                        if sessions > cfg.retry_max_attempts:
                            raise DriveObjectStoreError('Drive upload session expired repeatedly')
                        request = self._new_upload_request(
                            service, stream, object_id, artifact_version_id, content_sha256, parent_id
                        )
                        started = self._clock()
                        _LOGGER.info('drive upload session %d opened for file id %s', sessions, object_id)
                    try:
                        _, response = request.next_chunk()  # type: ignore[attr-defined]
                    except (HttpError, OSError, httplib2.HttpLib2Error) as exc:
                        kind = _failure_kind(exc)
                        if kind == 'exists':
                            raise ObjectAlreadyExistsError('Drive file id already exists') from None
                        if kind == 'fatal':
                            raise DriveObjectStoreError('Drive upload failed: ' + _describe(exc)) from None
                        if kind == 'expired':
                            request = None
                            continue
                        failures += 1
                        _LOGGER.warning(
                            'drive upload request failed (%s), attempt %d of %d',
                            _describe(exc),
                            failures,
                            cfg.retry_max_attempts,
                        )
                        if failures >= cfg.retry_max_attempts:
                            if kind == 'timeout':
                                raise TimeoutError('Drive upload timed out after retries') from None
                            raise DriveObjectStoreError('Drive upload failed after retries: ' + _describe(exc)) from None
                        self._sleep(self._backoff(failures))
                        continue
                    failures = 0
                    if response is not None:
                        return

    def _sha256_by_download(self, object_id: str) -> tuple[str, int]:
        sink = _HashingSink()
        with closing(self._open_service()) as service:
            request = service.files().get_media(fileId=object_id)  # type: ignore[attr-defined]
            downloader = MediaIoBaseDownload(sink, request, chunksize=self._config.chunk_bytes)
            done = False
            while not done:
                _, done = self._run(downloader.next_chunk)  # type: ignore[arg-type]
        return sink.hexdigest(), sink.size

    def lookup(self, object_id: str) -> IntegrityObservation:
        if not isinstance(object_id, str) or not object_id:
            raise ValueError('object_id must be a non-empty string')

        def fetch() -> object:
            try:
                with closing(self._open_service()) as service:
                    return service.files().get(fileId=object_id, fields='id,size,sha256Checksum,trashed').execute()  # type: ignore[attr-defined]
            except HttpError as exc:
                if exc.resp.status == 404:
                    return None
                raise

        meta = self._run(fetch)
        if meta is None or (isinstance(meta, dict) and meta.get('trashed') is True):
            return IntegrityObservation(False, None, None, None)

        declared = meta.get('sha256Checksum') if isinstance(meta, dict) else None
        if isinstance(declared, str) and len(declared) == 64 and set(declared.lower()) <= _HEX:
            try:
                size: int | None = int(meta['size'])  # type: ignore[index]
            except (KeyError, TypeError, ValueError):
                size = None
            return IntegrityObservation(True, declared.lower(), size, 'drive:' + object_id + ':sha256Checksum')

        digest, size = self._sha256_by_download(object_id)
        return IntegrityObservation(True, digest, size, 'drive:' + object_id + ':download-sha256')


__all__ = [
    'ArtifactSourcePort',
    'DriveObjectStore',
    'DriveObjectStoreError',
    'DriveQuotaError',
    'DriveStoreConfig',
    'DriveTokenBrokerPort',
    'drive_http',
]
