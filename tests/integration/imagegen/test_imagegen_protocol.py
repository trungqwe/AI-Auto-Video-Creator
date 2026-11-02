"""IMGGEN-SVC: giao thức HTTP của sidecar sinh ảnh và luật không import torch khi nạp.

Môi trường uv riêng (pyproject.toml, uv.lock) thuộc slice phụ thuộc IMGGEN-DEPS, kiểm ở test_imagegen_env.py.

Chạy bằng runtime sản phẩm: không torch, không GPU, không mạng.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
IMAGEGEN = ROOT / 'tools' / 'imagegen'
if str(ROOT / 'tools') not in sys.path:
    sys.path.insert(0, str(ROOT / 'tools'))

from imagegen import protocol  # noqa: E402

HEAVY = {'torch', 'torchvision', 'diffusers', 'transformers', 'accelerate', 'safetensors', 'PIL', 'numpy', 'psutil',
         'huggingface_hub', 'tokenizers'}
MODULES = ('__init__', 'protocol', 'weights', 'engine', 'server', 'provision')


def _item(**overrides):
    item = {'item_id': 'shot-1', 'caption': 'A wide documentary photograph of an empty city street at dawn.', 'width': 864,
            'height': 1536, 'steps': 16, 'seed': 7}
    item.update(overrides)
    return item


def _body(items=None, **overrides):
    body = {'job_id': 'a' * 32, 'items': items if items is not None else [_item(), _item(item_id='shot-2', seed=8)]}
    body.update(overrides)
    return json.dumps(body).encode('utf-8')


def test_constants_follow_the_design():
    assert (protocol.HOST, protocol.DEFAULT_PORT) == ('127.0.0.1', 57030)
    assert protocol.MAX_ITEMS_PER_JOB == 6 and protocol.MAX_ITEMS_PER_CYCLE == 16
    assert protocol.RESULT_TTL_SECONDS == 24 * 3600 and protocol.IDLE_UNLOAD_SECONDS == 120
    assert (protocol.DEFAULT_WIDTH, protocol.DEFAULT_HEIGHT, protocol.DEFAULT_STEPS) == (864, 1536, 16)
    assert protocol.SERVICE_STATES == ('not_provisioned', 'verifying', 'idle', 'loading', 'busy', 'error')
    assert protocol.MODEL_REVISION == '337337621b8526e120f2275d250242f4a6bedd75'
    assert protocol.PUP_REVISION == '3f3edb52b2c55de0d49feab28598b68f7f8e4830'
    assert protocol.TOKEN_ENV == 'AIAVC_IMAGEGEN_TOKEN' and protocol.TOKEN_MIN_CHARS >= 32


def test_a_full_body_parses_and_hashes_canonically():
    request = protocol.parse_job(_body())
    assert request.job_id == 'a' * 32 and [i.item_id for i in request.items] == ['shot-1', 'shot-2']
    reordered = json.dumps({'items': [dict(reversed(list(_item().items()))), _item(item_id='shot-2', seed=8)], 'job_id': 'a' * 32},
                           indent=3).encode('utf-8')
    assert protocol.parse_job(reordered).body_sha256 == request.body_sha256
    changed = protocol.parse_job(_body([_item(caption='Another caption entirely.'), _item(item_id='shot-2', seed=8)]))
    assert changed.body_sha256 != request.body_sha256
    assert re.fullmatch(r'[0-9a-f]{64}', request.body_sha256)


@pytest.mark.parametrize('raw, field', [
    (b'\xff\xfe', 'body'),
    (b'[1, 2]', 'body'),
    (_body(extra=1), 'body'),
    (json.dumps({'job_id': 'a' * 32}).encode(), 'body'),
    (_body(job_id='../' + 'a' * 29), 'job_id'),
    (_body(job_id='A' * 32), 'job_id'),
    (_body(items=[]), 'items'),
    (_body(items=[_item(item_id=f's{i}') for i in range(7)]), 'items'),
    (_body(items=[_item(), _item()]), 'items'),
    (_body(items=[dict(_item(), lens='35mm')]), 'items[0]'),
    (_body(items=[_item(item_id='../x')]), 'items[0].item_id'),
    (_body(items=[_item(caption='   ')]), 'items[0].caption'),
    (_body(items=[_item(caption='x' * 4001)]), 'items[0].caption'),
    (_body(items=[_item(caption='bell\x07')]), 'items[0].caption'),
    (_body(items=[_item(width=870)]), 'items[0].width'),
    (_body(items=[_item(width=2048, height=2048)]), 'items[0].width'),
    (_body(items=[_item(width=True)]), 'items[0].width'),
    (_body(items=[_item(steps=0)]), 'items[0].steps'),
    (_body(items=[_item(steps=33)]), 'items[0].steps'),
    (_body(items=[_item(seed=-1)]), 'items[0].seed'),
    (_body(items=[_item(seed=2 ** 63)]), 'items[0].seed'),
])
def test_bad_bodies_are_refused_with_the_field(raw, field):
    with pytest.raises(protocol.ProtocolError) as caught:
        protocol.parse_job(raw)
    assert caught.value.status == 400 and caught.value.code == 'BAD_REQUEST'
    assert caught.value.field == field
    assert caught.value.body()['error']['field'] == field


def test_seeds_are_stable_63_bit_and_differ_per_item():
    seed = protocol.derive_seed('a' * 32, 'shot-1')
    assert seed == protocol.derive_seed('a' * 32, 'shot-1')
    assert 0 <= seed < 2 ** 63 and seed != protocol.derive_seed('a' * 32, 'shot-2')


def test_job_state_rules():
    assert protocol.job_state(['queued', 'queued']) == 'queued'
    assert protocol.job_state(['running', 'queued']) == 'running'
    assert protocol.job_state(['done', 'queued']) == 'running'
    assert protocol.job_state(['done', 'done']) == 'done'
    assert protocol.job_state(['done', 'failed']) == 'failed'


def _load_time_imports(tree: ast.Module) -> list[str]:
    """Imports that run when the module loads: module level and class bodies, including if/try/with blocks; not function bodies."""
    found = []

    def visit(statements):
        for node in statements:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if isinstance(node, ast.Import):
                found.extend(alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                found.append(node.module.split('.')[0])
            for name in ('body', 'orelse', 'finalbody'):
                visit(getattr(node, name, []) or [])
            for handler in getattr(node, 'handlers', []) or []:
                visit(handler.body)

    visit(tree.body)
    return found


def test_no_imagegen_module_imports_torch_or_other_heavy_libraries_at_load_time():
    for name in MODULES:
        source = (IMAGEGEN / f'{name}.py').read_text(encoding='utf-8')
        heavy = set(_load_time_imports(ast.parse(source))) & HEAVY
        assert not heavy, f'{name}.py imports {sorted(heavy)} at load time'


def test_every_module_loads_in_the_product_runtime_without_torch():
    from imagegen import engine, provision, server, weights  # noqa: F401
    assert 'torch' not in sys.modules and 'diffusers' not in sys.modules
