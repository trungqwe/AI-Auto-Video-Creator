"""IMGGEN-PIPE: stdlib HTTP client of the on-machine illustration sidecar (IMGGEN-SVC protocol, DESIGN wave 42 section 2).

The launcher (IMGGEN-LAUNCH) starts the sidecar and writes <data>/imagegen/endpoint.json = {url, token, pid}. The client reads that
file on every call, so a restarted sidecar with a new token is found and a stopped one is reported, never guessed. Only
http://127.0.0.1:<port> is accepted; http.client follows no redirect and uses no proxy. A missing endpoint file, a refused
connection, a wrong token or a sidecar that is not provisioned raises ImagegenUnavailable; a full queue raises ImagegenBusy; any
other refusal raises ImagegenRejected. Error codes are fixed strings: the token never reaches an exception, a repr or a log.
This module never imports tools.*; the protocol values it needs are restated here and a test pins them to tools/imagegen/protocol.py.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SERVICE_NAME = 'aiavc-imagegen'
LOOPBACK_HOST = '127.0.0.1'
TOKEN_MIN_CHARS = 32
MAX_ITEMS_PER_JOB = 6
HTTP_TIMEOUT_SECONDS = 10.0
MAX_JSON_BYTES = 1024 * 1024
MAX_PNG_BYTES = 64 * 1024 * 1024
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
UNAVAILABLE_STATES = frozenset({'not_provisioned', 'error'})

ENDPOINT_MISSING = 'endpoint_missing'
ENDPOINT_INVALID = 'endpoint_invalid'
CONNECTION_FAILED = 'connection_failed'
UNAUTHORIZED = 'unauthorized'
NOT_PROVISIONED = 'not_provisioned'
ENGINE_UNAVAILABLE = 'engine_unavailable'
SHUTTING_DOWN = 'shutting_down'
QUEUE_FULL = 'queue_full'
JOB_CONFLICT = 'job_conflict'
ITEM_NOT_READY = 'item_not_ready'
RESULT_CORRUPT = 'result_corrupt'
BAD_RESPONSE = 'bad_response'
REJECTED = 'rejected'

_URL = re.compile(r'http://127\.0\.0\.1:([0-9]{1,5})')
_TOKEN = re.compile(r'[!-~]+')
_JOB_ID = re.compile(r'[0-9a-f]{32}')
_ITEM_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}')
_SHA256 = re.compile(r'[0-9a-f]{64}')
_UNAVAILABLE_BY_CODE = {'NOT_PROVISIONED': NOT_PROVISIONED, 'ENGINE_UNAVAILABLE': ENGINE_UNAVAILABLE, 'SHUTTING_DOWN': SHUTTING_DOWN}
_REJECTED_BY_CODE = {'JOB_CONFLICT': JOB_CONFLICT, 'ITEM_NOT_READY': ITEM_NOT_READY, 'RESULT_CORRUPT': RESULT_CORRUPT}


class ImagegenError(Exception):
    def __init__(self, code: str, status: int | None = None) -> None:
        self.code = code
        self.status = status
        super().__init__(code if status is None else f'{code} (HTTP {status})')


class ImagegenUnavailable(ImagegenError):
    """The sidecar cannot take or serve work now: no endpoint, no answer, wrong token, not provisioned, engine error, stopping."""


class ImagegenBusy(ImagegenError):
    """The sidecar queue is full (HTTP 429); the same body may be posted again later."""


class ImagegenRejected(ImagegenError):
    """The sidecar refused this request (conflicting body, item not ready, corrupt result, bad request)."""


@dataclass(frozen=True)
class ImagegenEndpoint:
    port: int
    token: str = field(repr=False)


def read_endpoint(path: Path | None) -> ImagegenEndpoint:
    """The sidecar of this launcher run from its endpoint file; ImagegenUnavailable when the file is missing or malformed."""
    if path is None:
        raise ImagegenUnavailable(ENDPOINT_MISSING)
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError):
        raise ImagegenUnavailable(ENDPOINT_MISSING) from None
    except ValueError:
        raise ImagegenUnavailable(ENDPOINT_INVALID) from None
    url = data.get('url') if isinstance(data, dict) else None
    token = data.get('token') if isinstance(data, dict) else None
    found = _URL.fullmatch(url) if isinstance(url, str) else None
    if found is None or not 1 <= int(found.group(1)) <= 65535:
        raise ImagegenUnavailable(ENDPOINT_INVALID)
    if not isinstance(token, str) or len(token) < TOKEN_MIN_CHARS or _TOKEN.fullmatch(token) is None:
        raise ImagegenUnavailable(ENDPOINT_INVALID)
    return ImagegenEndpoint(int(found.group(1)), token)


def _error_code(raw: bytes) -> str | None:
    try:
        error = json.loads(raw.decode('utf-8')).get('error')
    except (UnicodeDecodeError, ValueError, AttributeError):
        return None
    code = error.get('code') if isinstance(error, dict) else None
    return code if isinstance(code, str) else None


def _json_object(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        raise ImagegenRejected(BAD_RESPONSE) from None
    if not isinstance(value, dict):
        raise ImagegenRejected(BAD_RESPONSE)
    return value


class ImagegenClient:
    """Client of the sidecar named by `endpoint_file`; `connect(host, port, timeout=...)` builds the HTTP connection (http.client)."""

    def __init__(
        self,
        endpoint_file: Path | None,
        *,
        timeout: float = HTTP_TIMEOUT_SECONDS,
        connect: Callable[..., Any] = http.client.HTTPConnection,
    ) -> None:
        self._endpoint_file = None if endpoint_file is None else Path(endpoint_file)
        self._timeout = float(timeout)
        self._connect = connect

    def __repr__(self) -> str:
        return f'ImagegenClient(endpoint_file={str(self._endpoint_file)!r})'

    def _request(self, method: str, path: str, body: bytes | None = None, *, auth: bool = True,
                 limit: int = MAX_JSON_BYTES) -> tuple[int, dict[str, str], bytes]:
        endpoint = read_endpoint(self._endpoint_file)
        headers = {'Accept': 'application/json'}
        if auth:
            headers['Authorization'] = 'Bearer ' + endpoint.token
        if body is not None:
            headers['Content-Type'] = 'application/json'
        connection = self._connect(LOOPBACK_HOST, endpoint.port, timeout=self._timeout)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            data = response.read(limit + 1)
            status = response.status
            found = {name.lower(): value for name, value in response.getheaders()}
        except (OSError, http.client.HTTPException):
            raise ImagegenUnavailable(CONNECTION_FAILED) from None
        finally:
            connection.close()
        if len(data) > limit:
            raise ImagegenRejected(BAD_RESPONSE, status)
        if status == 401:
            raise ImagegenUnavailable(UNAUTHORIZED, status)
        if status == 429:
            raise ImagegenBusy(QUEUE_FULL, status)
        if status == 503:
            raise ImagegenUnavailable(_UNAVAILABLE_BY_CODE.get(_error_code(data) or '', ENGINE_UNAVAILABLE), status)
        return status, found, data

    def _refused(self, status: int, data: bytes) -> ImagegenRejected:
        return ImagegenRejected(_REJECTED_BY_CODE.get(_error_code(data) or '', REJECTED), status)

    def health(self) -> dict[str, Any]:
        """GET /v1/health of the sidecar (it never loads a model); ImagegenUnavailable when it does not answer as this sidecar or its
        state is not_provisioned or error."""
        status, _, data = self._request('GET', '/v1/health', auth=False)
        if status != 200:
            raise ImagegenUnavailable(CONNECTION_FAILED, status)
        health = _json_object(data)
        if health.get('service') != SERVICE_NAME:
            raise ImagegenUnavailable(CONNECTION_FAILED, status)
        state = health.get('state')
        if state in UNAVAILABLE_STATES:
            raise ImagegenUnavailable(NOT_PROVISIONED if state == 'not_provisioned' else ENGINE_UNAVAILABLE, status)
        return health

    def submit(self, body: Mapping[str, Any]) -> dict[str, Any]:
        """POST /v1/jobs: 202 with the job view. The same body again returns the same job and queues again its retryable failures."""
        job_id = body.get('job_id') if isinstance(body, Mapping) else None
        if not isinstance(job_id, str) or _JOB_ID.fullmatch(job_id) is None:
            raise ValueError('job_id must be 32 lowercase hex characters')
        raw = json.dumps(dict(body), ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        status, _, data = self._request('POST', '/v1/jobs', raw)
        if status != 202:
            raise self._refused(status, data)
        view = _json_object(data)
        if view.get('job_id') != job_id or not isinstance(view.get('items'), list):
            raise ImagegenRejected(BAD_RESPONSE, status)
        return view

    def job(self, job_id: str) -> dict[str, Any] | None:
        """GET /v1/jobs/{id}: the job view, None when the sidecar does not hold the job."""
        if not isinstance(job_id, str) or _JOB_ID.fullmatch(job_id) is None:
            raise ValueError('job_id must be 32 lowercase hex characters')
        status, _, data = self._request('GET', f'/v1/jobs/{job_id}')
        if status == 404:
            return None
        if status != 200:
            raise self._refused(status, data)
        view = _json_object(data)
        if view.get('job_id') != job_id or not isinstance(view.get('items'), list):
            raise ImagegenRejected(BAD_RESPONSE, status)
        return view

    def png(self, job_id: str, item_id: str) -> tuple[bytes, str]:
        """GET /v1/jobs/{id}/items/{item}: the PNG bytes and their sha256, checked against X-Content-SHA256 and the PNG signature."""
        if not isinstance(job_id, str) or _JOB_ID.fullmatch(job_id) is None or not isinstance(item_id, str) or _ITEM_ID.fullmatch(item_id) is None:
            raise ValueError('job_id or item_id is malformed')
        status, headers, data = self._request('GET', f'/v1/jobs/{job_id}/items/{item_id}', limit=MAX_PNG_BYTES)
        if status != 200:
            raise self._refused(status, data)
        digest = hashlib.sha256(data).hexdigest()
        stated = headers.get('x-content-sha256', '')
        if _SHA256.fullmatch(stated) is None or stated != digest or not data.startswith(PNG_SIGNATURE):
            raise ImagegenRejected(RESULT_CORRUPT, status)
        return data, digest


__all__ = [
    'BAD_RESPONSE', 'CONNECTION_FAILED', 'ENDPOINT_INVALID', 'ENDPOINT_MISSING', 'ENGINE_UNAVAILABLE', 'ITEM_NOT_READY', 'JOB_CONFLICT',
    'MAX_ITEMS_PER_JOB', 'NOT_PROVISIONED', 'QUEUE_FULL', 'REJECTED', 'RESULT_CORRUPT', 'SERVICE_NAME', 'SHUTTING_DOWN', 'UNAUTHORIZED',
    'ImagegenBusy', 'ImagegenClient', 'ImagegenEndpoint', 'ImagegenError', 'ImagegenRejected', 'ImagegenUnavailable', 'read_endpoint',
]
