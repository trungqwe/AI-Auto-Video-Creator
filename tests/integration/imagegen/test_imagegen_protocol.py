"""Integration tests for imagegen protocol module."""

import hashlib
import json
import pathlib
import subprocess
import sys
import tomllib
import pytest

TOOLS = pathlib.Path(__file__).resolve().parents[3] / 'tools' / 'imagegen'
sys.path.insert(0, str(TOOLS))

import protocol


def test_no_imagegen_module_imports_torch_or_other_heavy_libraries_at_load_time():
    code = (
        "import sys, pathlib; "
        f"sys.path.insert(0, r\'{TOOLS}\'); "
        "import protocol, weights, engine, server, provision; "
        "heavy = {\'torch\', \'torchvision\', \'diffusers\', \'transformers\', \'accelerate\', \'safetensors\', \'PIL\', \'numpy\', \'psutil\', \'huggingface_hub\', \'tokenizers'}; "
        "loaded = set(sys.modules.keys()) & heavy; "
        "assert not loaded, f\'Heavy libraries loaded: {loaded}\'"
    )
    res = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


def test_uv_lock_resolves_the_pins_from_the_cu130_index_with_hashes():
    uv_lock = TOOLS / 'uv.lock'
    if not uv_lock.exists():
        assert False, 'uv.lock do Control cáº¥p'
    data = tomllib.loads(uv_lock.read_text(encoding='utf-8'))
    packages = {p['name']: p for p in data.get('package', [])}
    assert 'torch' in packages, 'torch missing in uv.lock'
    assert 'torchvision' in packages, 'torchvision missing in uv.lock'
    torch_pkg = packages['torch']
    assert torch_pkg.get('version') == '2.14.1+cu130'
    assert torch_pkg.get('source') == {'registry': 'https://download.pytorch.org/whl/cu130'}
    assert packages['torchvision'].get('version') == '0.29.1+cu130'
    wheels = torch_pkg.get('wheels', [])
    for w in wheels:
        h = w.get('hash', '')
        assert h.startswith('sha256:'), f"Wheel hash does not start with sha256: {h}"


def test_protocol_constants():
    assert protocol.DEFAULT_PORT == 57030
    assert protocol.MAX_ITEMS_PER_JOB == 6
    assert protocol.MAX_ITEMS_PER_CYCLE == 16
    assert protocol.MAX_QUEUED_ITEMS == 96
    assert protocol.MAX_ITEM_ATTEMPTS == 3
    assert protocol.RESULT_TTL_SECONDS == 24 * 3600
    assert protocol.IDLE_UNLOAD_SECONDS == 120
    assert protocol.DEFAULT_WIDTH == 864
    assert protocol.DEFAULT_HEIGHT == 1536
    assert protocol.DEFAULT_STEPS == 16
    assert protocol.TOKEN_ENV == 'AIAVC_IMAGEGEN_TOKEN'


def test_parse_job_accepts_a_valid_job():
    job = {
        'job_id': '0123456789abcdef0123456789abcdef',
        'items': [
            {
                'item_id': f'item_{i}',
                'caption': f'Caption {i}',
                'width': 864,
                'height': 1536,
                'steps': 16,
                'seed': i * 100,
            }
            for i in range(6)
        ]
    }
    parsed = protocol.parse_job(job)
    assert parsed['job_id'] == job['job_id']
    assert len(parsed['items']) == 6


def test_parse_job_rejections():
    valid_item = {
        'item_id': 'it1',
        'caption': 'A valid caption',
        'width': 864,
        'height': 1536,
        'steps': 16,
        'seed': 42,
    }

    # Upper case job_id
    with pytest.raises(protocol.ProtocolError) as exc:
        protocol.parse_job({'job_id': '0123456789ABCDEF0123456789abcdef', 'items': [valid_item]})
    assert exc.value.status == 400 and exc.value.field == 'job_id'

    # Short job_id
    with pytest.raises(protocol.ProtocolError) as exc:
        protocol.parse_job({'job_id': '0123456789', 'items': [valid_item]})
    assert exc.value.status == 400 and exc.value.field == 'job_id'

    # 7 items
    with pytest.raises(protocol.ProtocolError) as exc:
        protocol.parse_job({
            'job_id': '0123456789abcdef0123456789abcdef',
            'items': [{**valid_item, 'item_id': f'it_{i}'} for i in range(7)]
        })
    assert exc.value.status == 400 and exc.value.field == 'items'

    # 0 items
    with pytest.raises(protocol.ProtocolError) as exc:
        protocol.parse_job({'job_id': '0123456789abcdef0123456789abcdef', 'items': []})
    assert exc.value.status == 400 and exc.value.field == 'items'

    # Missing job_id
    with pytest.raises(protocol.ProtocolError) as exc:
        protocol.parse_job({'items': [valid_item]})
    assert exc.value.status == 400 and exc.value.field == 'job_id'

    # Extra key in body
    with pytest.raises(protocol.ProtocolError) as exc:
        protocol.parse_job({'job_id': '0123456789abcdef0123456789abcdef', 'items': [valid_item], 'extra': 123})
    assert exc.value.status == 400 and exc.value.field == 'extra'

    # Width not divisible by 16
    with pytest.raises(protocol.ProtocolError) as exc:
        protocol.parse_job({'job_id': '0123456789abcdef0123456789abcdef', 'items': [{**valid_item, 'width': 865}]})
    assert exc.value.status == 400 and exc.value.field == 'items[0].width'

    # Total pixels too large
    with pytest.raises(protocol.ProtocolError) as exc:
        protocol.parse_job({'job_id': '0123456789abcdef0123456789abcdef', 'items': [{**valid_item, 'width': 2048, 'height': 2048}]})
    assert exc.value.status == 400 and exc.value.field == 'items[0].width'

    # Steps 0 and 33
    with pytest.raises(protocol.ProtocolError) as exc:
        protocol.parse_job({'job_id': '0123456789abcdef0123456789abcdef', 'items': [{**valid_item, 'steps': 0}]})
    assert exc.value.status == 400 and exc.value.field == 'items[0].steps'
    with pytest.raises(protocol.ProtocolError) as exc:
        protocol.parse_job({'job_id': '0123456789abcdef0123456789abcdef', 'items': [{**valid_item, 'steps': 33}]})
    assert exc.value.status == 400 and exc.value.field == 'items[0].steps'

    # Seed -1 and 2**63
    with pytest.raises(protocol.ProtocolError) as exc:
        protocol.parse_job({'job_id': '0123456789abcdef0123456789abcdef', 'items': [{**valid_item, 'seed': -1}]})
    assert exc.value.status == 400 and exc.value.field == 'items[0].seed'
    with pytest.raises(protocol.ProtocolError) as exc:
        protocol.parse_job({'job_id': '0123456789abcdef0123456789abcdef', 'items': [{**valid_item, 'seed': 2**63}]})
    assert exc.value.status == 400 and exc.value.field == 'items[0].seed'

    # Duplicate item_id
    with pytest.raises(protocol.ProtocolError) as exc:
        protocol.parse_job({'job_id': '0123456789abcdef0123456789abcdef', 'items': [valid_item, valid_item]})
    assert exc.value.status == 400 and exc.value.field == 'items[1].item_id'

    # Bool as width
    with pytest.raises(protocol.ProtocolError) as exc:
        protocol.parse_job({'job_id': '0123456789abcdef0123456789abcdef', 'items': [{**valid_item, 'width': True}]})
    assert exc.value.status == 400 and exc.value.field == 'items[0].width'

    # Missing item key
    bad_item = dict(valid_item)
    del bad_item['caption']
    with pytest.raises(protocol.ProtocolError) as exc:
        protocol.parse_job({'job_id': '0123456789abcdef0123456789abcdef', 'items': [bad_item]})
    assert exc.value.status == 400 and exc.value.field == 'items[0].caption'

    # Extra item key
    extra_item = dict(valid_item)
    extra_item['unknown'] = 'bad'
    with pytest.raises(protocol.ProtocolError) as exc:
        protocol.parse_job({'job_id': '0123456789abcdef0123456789abcdef', 'items': [extra_item]})
    assert exc.value.status == 400 and exc.value.field == 'items[0].unknown'


def test_body_sha256_stability():
    job1 = {'job_id': '0123456789abcdef0123456789abcdef', 'items': [{'item_id': 'i1', 'caption': 'c1', 'width': 864, 'height': 1536, 'steps': 16, 'seed': 1}]}
    job2 = {'items': [{'caption': 'c1', 'seed': 1, 'item_id': 'i1', 'height': 1536, 'steps': 16, 'width': 864}], 'job_id': '0123456789abcdef0123456789abcdef'}
    assert protocol.body_sha256(job1) == protocol.body_sha256(job2)
    job3 = {'job_id': '0123456789abcdef0123456789abcdef', 'items': [{'item_id': 'i1', 'caption': 'c2', 'width': 864, 'height': 1536, 'steps': 16, 'seed': 1}]}
    assert protocol.body_sha256(job1) != protocol.body_sha256(job3)


def test_derive_seed_formula():
    job_id = '0123456789abcdef0123456789abcdef'
    item_id = 'item_42'
    calculated = protocol.derive_seed(job_id, item_id)
    expected = int.from_bytes(hashlib.sha256(f'{job_id}:{item_id}'.encode('utf-8')).digest()[:8], 'big') >> 1
    assert calculated == expected
    assert 0 <= calculated <= 2**63 - 1


def test_utf8_stdio():
    protocol.utf8_stdio()


def test_check_token_strength():
    assert protocol.check_token_strength('a' * 32) is True
    assert protocol.check_token_strength('a' * 31) is False
