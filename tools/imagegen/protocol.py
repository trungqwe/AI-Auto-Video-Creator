"""Protocol definitions and validation for FLUX 3 Image Klein sidecar."""

import hashlib
import json
import re
import sys

HOST = '127.0.0.1'
DEFAULT_PORT = 57030
TOKEN_ENV = 'AIAVC_IMAGEGEN_TOKEN'
TOKEN_MIN_LENGTH = 32
MAX_ITEMS_PER_JOB = 6
MAX_ITEMS_PER_CYCLE = 16
MAX_QUEUED_ITEMS = 96
MAX_ITEM_ATTEMPTS = 3
RESULT_TTL_SECONDS = 24 * 3600
IDLE_UNLOAD_SECONDS = 120
DEFAULT_WIDTH = 864
DEFAULT_HEIGHT = 1536
DEFAULT_STEPS = 16
MAX_PIXELS = 1024 * 1536
MAX_STEPS = 32
MAX_SEED = 2**63 - 1

GPU_MEMORY_UNAVAILABLE = 'GPU_MEMORY_UNAVAILABLE'
HOST_COMMIT_LOW = 'HOST_COMMIT_LOW'
HOST_MEMORY_LOW = 'HOST_MEMORY_LOW'
GPU_OUT_OF_MEMORY = 'GPU_OUT_OF_MEMORY'
IMAGE_FAILED = 'IMAGE_FAILED'


class ProtocolError(Exception):
    def __init__(self, status, field, message=''):
        super().__init__(f"{status} {field}: {message}" if message else f"{status} {field}")
        self.status = status
        self.field = field
        self.message = message


ITEM_KEYS = frozenset({'item_id', 'caption', 'width', 'height', 'steps', 'seed'})


def parse_job(body):
    if not isinstance(body, dict):
        raise ProtocolError(400, 'body', 'Body must be a JSON object')
    if set(body.keys()) != {'job_id', 'items'}:
        if 'job_id' not in body:
            raise ProtocolError(400, 'job_id', 'Missing job_id')
        if 'items' not in body:
            raise ProtocolError(400, 'items', 'Missing items')
        extra = sorted(set(body.keys()) - {'job_id', 'items'})
        raise ProtocolError(400, extra[0], f"Unexpected key: {extra[0]}")

    job_id = body['job_id']
    if not isinstance(job_id, str) or not re.fullmatch(r'[0-9a-f]{32}', job_id):
        raise ProtocolError(400, 'job_id', 'Invalid job_id: must be 32 lowercase hex characters')

    items_raw = body['items']
    if not isinstance(items_raw, list) or len(items_raw) < 1 or len(items_raw) > MAX_ITEMS_PER_JOB:
        raise ProtocolError(400, 'items', f"Items must be a list of 1 to {MAX_ITEMS_PER_JOB} items")

    seen_ids = set()
    normalized_items = []
    for idx, item in enumerate(items_raw):
        prefix = f"items[{idx}]."
        if not isinstance(item, dict):
            raise ProtocolError(400, f"items[{idx}]", "Item must be a JSON object")
        if set(item.keys()) != ITEM_KEYS:
            missing = sorted(ITEM_KEYS - set(item.keys()))
            if missing:
                raise ProtocolError(400, f"{prefix}{missing[0]}", f"Missing key: {missing[0]}")
            extra = sorted(set(item.keys()) - ITEM_KEYS)
            raise ProtocolError(400, f"{prefix}{extra[0]}", f"Unexpected key: {extra[0]}")

        iid = item['item_id']
        if not isinstance(iid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', iid):
            raise ProtocolError(400, f"{prefix}item_id", "Invalid item_id")
        if iid in seen_ids:
            raise ProtocolError(400, f"{prefix}item_id", f"Duplicate item_id: {iid}")
        seen_ids.add(iid)

        caption = item['caption']
        if not isinstance(caption, str) or not caption.strip() or len(caption) > 4000:
            raise ProtocolError(400, f"{prefix}caption", "Caption must be non-empty and at most 4000 characters")

        w = item['width']
        h = item['height']
        if isinstance(w, bool) or not isinstance(w, int) or w <= 0 or w % 16 != 0:
            raise ProtocolError(400, f"{prefix}width", "Width must be a positive int divisible by 16")
        if isinstance(h, bool) or not isinstance(h, int) or h <= 0 or h % 16 != 0:
            raise ProtocolError(400, f"{prefix}height", "Height must be a positive int divisible by 16")
        if w * h > MAX_PIXELS:
            raise ProtocolError(400, f"{prefix}width", f"Total pixels {w * h} exceeds {MAX_PIXELS}")

        steps = item['steps']
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1 or steps > MAX_STEPS:
            raise ProtocolError(400, f"{prefix}steps", f"Steps must be an int between 1 and {MAX_STEPS}")

        seed = item['seed']
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0 or seed > MAX_SEED:
            raise ProtocolError(400, f"{prefix}seed", f"Seed must be an int between 0 and {MAX_SEED}")

        normalized_items.append({
            'item_id': iid,
            'caption': caption,
            'width': w,
            'height': h,
            'steps': steps,
            'seed': seed,
        })

    return {'job_id': job_id, 'items': normalized_items}


def body_sha256(job):
    return hashlib.sha256(
        json.dumps(job, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    ).hexdigest()


def derive_seed(job_id, item_id):
    return int.from_bytes(hashlib.sha256(f'{job_id}:{item_id}'.encode('utf-8')).digest()[:8], 'big') >> 1


def utf8_stdio():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')


def check_token_strength(token):
    return isinstance(token, str) and len(token) >= TOKEN_MIN_LENGTH
