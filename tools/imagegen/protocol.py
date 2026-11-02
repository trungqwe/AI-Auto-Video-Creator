"""Giao thức HTTP của sidecar sinh ảnh minh hoạ (IMGGEN-SVC): hằng số, kiểm yêu cầu, băm idempotency, seed, dạng trả lời.

Chỉ dùng thư viện chuẩn: module này được nạp trong runtime sản phẩm (test của lane) lẫn trong môi trường riêng của sidecar.
API (DESIGN wave 42 mục 2), chỉ nghe 127.0.0.1, bearer token trên mọi lệnh trừ health:
- GET /v1/health: state, revision, queue, fp8_path, VRAM trống; không bao giờ nạp mô hình.
- POST /v1/jobs {job_id, items[<=6]{item_id, caption, width, height, steps, seed}}: 202; idempotent theo (job_id, sha256 thân
  chuẩn hoá); khác thân thì 409; 503 khi chưa cấp trọng số.
- GET /v1/jobs/{id}: trạng thái, sha256 và lỗi từng ảnh. GET /v1/jobs/{id}/items/{item}: PNG kèm X-Content-SHA256. Giữ 24 giờ.
- POST /v1/shutdown: dừng êm.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass

PROTOCOL_VERSION = 1
SERVICE_NAME = 'aiavc-imagegen'
HOST = '127.0.0.1'
DEFAULT_PORT = 57030
TOKEN_ENV = 'AIAVC_IMAGEGEN_TOKEN'
TOKEN_MIN_CHARS = 32

MODEL_REPO = 'black-forest-labs/flux-3-image-klein'
MODEL_REVISION = '337337621b8526e120f2275d250242f4a6bedd75'
PUP_REPO = 'black-forest-labs/flux-3-image-klein-pup'
PUP_REVISION = '3f3edb52b2c55de0d49feab28598b68f7f8e4830'

MAX_ITEMS_PER_JOB = 6
MAX_ITEMS_PER_CYCLE = 16
MAX_QUEUED_ITEMS = 96
MAX_ITEM_ATTEMPTS = 3
RESULT_TTL_SECONDS = 24 * 3600
IDLE_UNLOAD_SECONDS = 120
MAX_BODY_BYTES = 64 * 1024

DEFAULT_WIDTH = 864
DEFAULT_HEIGHT = 1536
DEFAULT_STEPS = 16
SIZE_MULTIPLE = 16
MIN_SIDE = 256
MAX_SIDE = 2048
MAX_PIXELS = 1024 * 1536
MIN_STEPS = 1
MAX_STEPS = 32
MAX_CAPTION_CHARS = 4000
SEED_LIMIT = 2 ** 63

JOB_ID_PATTERN = re.compile(r'[0-9a-f]{32}')
ITEM_ID_PATTERN = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}')
_CONTROL = re.compile(r'[\x00-\x08\x0b-\x1f\x7f]')

SERVICE_STATES = ('not_provisioned', 'verifying', 'idle', 'loading', 'busy', 'error')
ITEM_STATES = ('queued', 'running', 'done', 'failed')
JOB_KEYS = frozenset({'job_id', 'items'})
ITEM_KEYS = frozenset({'item_id', 'caption', 'width', 'height', 'steps', 'seed'})

# Item errors. Retryable ones are queued again when the client repeats the same POST (at most MAX_ITEM_ATTEMPTS attempts).
GPU_OUT_OF_MEMORY = 'GPU_OUT_OF_MEMORY'
GPU_MEMORY_UNAVAILABLE = 'GPU_MEMORY_UNAVAILABLE'
HOST_MEMORY_LOW = 'HOST_MEMORY_LOW'
HOST_COMMIT_LOW = 'HOST_COMMIT_LOW'
MODEL_LOAD_FAILED = 'MODEL_LOAD_FAILED'
GENERATION_FAILED = 'GENERATION_FAILED'
OUTPUT_WRITE_FAILED = 'OUTPUT_WRITE_FAILED'
RESULT_MISSING = 'RESULT_MISSING'
NOT_PROVISIONED = 'NOT_PROVISIONED'
ENGINE_UNAVAILABLE = 'ENGINE_UNAVAILABLE'
RETRYABLE_ITEM_ERRORS = frozenset({GPU_OUT_OF_MEMORY, GPU_MEMORY_UNAVAILABLE, HOST_MEMORY_LOW, HOST_COMMIT_LOW, MODEL_LOAD_FAILED,
                                   GENERATION_FAILED, OUTPUT_WRITE_FAILED, RESULT_MISSING})

# HTTP errors: (status, code).
BAD_REQUEST = (400, 'BAD_REQUEST')
UNAUTHORIZED = (401, 'UNAUTHORIZED')
NOT_FOUND = (404, 'NOT_FOUND')
METHOD_NOT_ALLOWED = (405, 'METHOD_NOT_ALLOWED')
JOB_CONFLICT = (409, 'JOB_CONFLICT')
ITEM_NOT_READY = (409, 'ITEM_NOT_READY')
LENGTH_REQUIRED = (411, 'LENGTH_REQUIRED')
BODY_TOO_LARGE = (413, 'BODY_TOO_LARGE')
QUEUE_FULL = (429, 'QUEUE_FULL')
RESULT_CORRUPT = (500, 'RESULT_CORRUPT')
SERVICE_NOT_PROVISIONED = (503, NOT_PROVISIONED)
SERVICE_UNAVAILABLE = (503, ENGINE_UNAVAILABLE)
SHUTTING_DOWN = (503, 'SHUTTING_DOWN')


class ProtocolError(Exception):
    """A request the service refuses: HTTP status, stable code, English message and the offending field."""

    def __init__(self, error: tuple[int, str], message: str, field: str | None = None, **extra):
        super().__init__(message)
        self.status, self.code = error
        self.message = message
        self.field = field
        self.extra = extra

    def body(self) -> dict:
        detail = {'code': self.code, 'message': self.message}
        if self.field:
            detail['field'] = self.field
        detail.update(self.extra)
        return {'error': detail}


@dataclass(frozen=True)
class ItemRequest:
    item_id: str
    caption: str
    width: int
    height: int
    steps: int
    seed: int

    def as_dict(self) -> dict:
        return {'item_id': self.item_id, 'caption': self.caption, 'width': self.width, 'height': self.height,
                'steps': self.steps, 'seed': self.seed}


@dataclass(frozen=True)
class JobRequest:
    job_id: str
    items: tuple[ItemRequest, ...]

    def as_dict(self) -> dict:
        return {'job_id': self.job_id, 'items': [item.as_dict() for item in self.items]}

    @property
    def body_sha256(self) -> str:
        return body_sha256(self.as_dict())


def canonical_json(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def body_sha256(value) -> str:
    """SHA-256 of the canonical JSON of a parsed job body: key order and whitespace do not change it."""
    return hashlib.sha256(canonical_json(value)).hexdigest()


def derive_seed(job_id: str, item_id: str) -> int:
    """The seed both sides use for an item: the first 63 bits of sha256('<job_id>:<item_id>')."""
    digest = hashlib.sha256(f'{job_id}:{item_id}'.encode('utf-8')).digest()
    return int.from_bytes(digest[:8], 'big') >> 1


def _bad(message: str, field: str) -> ProtocolError:
    return ProtocolError(BAD_REQUEST, message, field)


def _int(value, field: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise _bad(f'{field} must be an integer in [{low}, {high}]', field)
    return value


def _caption(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _bad(f'{field} must be a non-empty string', field)
    if len(value) > MAX_CAPTION_CHARS:
        raise _bad(f'{field} is longer than {MAX_CAPTION_CHARS} characters', field)
    if _CONTROL.search(value):
        raise _bad(f'{field} contains control characters', field)
    return value


def parse_item(value, index: int) -> ItemRequest:
    field = f'items[{index}]'
    if not isinstance(value, dict):
        raise _bad(f'{field} must be an object', field)
    keys = set(value)
    if keys != ITEM_KEYS:
        raise _bad(f'{field} must have exactly the keys {sorted(ITEM_KEYS)}; missing {sorted(ITEM_KEYS - keys)}, '
                   f'unknown {sorted(keys - ITEM_KEYS)}', field)
    item_id = value['item_id']
    if not isinstance(item_id, str) or not ITEM_ID_PATTERN.fullmatch(item_id):
        raise _bad(f'{field}.item_id must match {ITEM_ID_PATTERN.pattern}', f'{field}.item_id')
    width = _int(value['width'], f'{field}.width', MIN_SIDE, MAX_SIDE)
    height = _int(value['height'], f'{field}.height', MIN_SIDE, MAX_SIDE)
    if width % SIZE_MULTIPLE or height % SIZE_MULTIPLE:
        raise _bad(f'{field}.width and height must be multiples of {SIZE_MULTIPLE}', f'{field}.width')
    if width * height > MAX_PIXELS:
        raise _bad(f'{field} asks for {width * height} pixels; at most {MAX_PIXELS}', f'{field}.width')
    steps = _int(value['steps'], f'{field}.steps', MIN_STEPS, MAX_STEPS)
    seed = _int(value['seed'], f'{field}.seed', 0, SEED_LIMIT - 1)
    return ItemRequest(item_id, _caption(value['caption'], f'{field}.caption'), width, height, steps, seed)


def parse_job(raw: bytes) -> JobRequest:
    """Validates a POST /v1/jobs body (UTF-8 JSON) strictly; raises ProtocolError(400) naming the field."""
    try:
        value = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError) as error:
        raise _bad(f'body is not UTF-8 JSON ({type(error).__name__})', 'body') from None
    if not isinstance(value, dict):
        raise _bad('body must be a JSON object', 'body')
    keys = set(value)
    if keys != JOB_KEYS:
        raise _bad(f'body must have exactly the keys {sorted(JOB_KEYS)}; missing {sorted(JOB_KEYS - keys)}, '
                   f'unknown {sorted(keys - JOB_KEYS)}', 'body')
    job_id = value['job_id']
    if not isinstance(job_id, str) or not JOB_ID_PATTERN.fullmatch(job_id):
        raise _bad('job_id must be 32 lowercase hex characters', 'job_id')
    items = value['items']
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_ITEMS_PER_JOB:
        raise _bad(f'items must be a list of 1 to {MAX_ITEMS_PER_JOB} objects', 'items')
    parsed = tuple(parse_item(item, index) for index, item in enumerate(items))
    ids = [item.item_id for item in parsed]
    if len(set(ids)) != len(ids):
        raise _bad('item_id values must be unique within a job', 'items')
    return JobRequest(job_id, parsed)


def iso(ts: float | None) -> str | None:
    if ts is None:
        return None
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(ts))


def job_state(item_states) -> str:
    """queued, running, done (every item done) or failed (every item finished and one failed)."""
    states = list(item_states)
    if any(s == 'running' for s in states):
        return 'running'
    if all(s == 'done' for s in states):
        return 'done'
    if all(s in ('done', 'failed') for s in states):
        return 'failed'
    return 'queued' if all(s == 'queued' for s in states) else 'running'


def error_view(code: str | None, message: str | None) -> dict | None:
    if code is None:
        return None
    return {'code': code, 'retryable': code in RETRYABLE_ITEM_ERRORS, 'message': message or ''}


def json_bytes(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=None, separators=(',', ':')).encode('utf-8')


def utf8_stdio() -> None:
    """Entry scripts run with -I, which ignores PYTHONIOENCODING: a redirected stdout would be cp1252 and a Vietnamese help text or a
    localised OS error in a log line would raise UnicodeEncodeError. Write UTF-8 whatever the console code page."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, 'reconfigure', None)
        if reconfigure is not None:
            reconfigure(encoding='utf-8', errors='backslashreplace')
