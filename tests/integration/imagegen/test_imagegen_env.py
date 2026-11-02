"""IMGGEN-DEPS: môi trường uv riêng của sidecar sinh ảnh (tools/imagegen/pyproject.toml, uv.lock) ghim đúng môi trường nguyên mẫu.

Chạy bằng runtime sản phẩm: không torch, không GPU, không mạng.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
IMAGEGEN = ROOT / 'tools' / 'imagegen'

# Môi trường nguyên mẫu Control đã sinh ảnh thật ngày 02/11/2026 (D:/AIAVC_IMGPROTO/requirements.lock.txt) cộng torchvision.
PROTOTYPE_PINS = {
    'accelerate': '1.15.0', 'annotated-doc': '0.0.5', 'anyio': '4.16.0', 'certifi': '2026.10.23', 'charset-normalizer': '3.5.2',
    'click': '8.5.0', 'colorama': '0.4.6', 'diffusers': '0.42.1', 'filelock': '4.2.6', 'fsspec': '2026.9.0', 'h11': '0.16.0',
    'hf-xet': '1.8.0', 'httpcore': '1.0.9', 'httpx': '0.28.1', 'huggingface-hub': '1.33.0', 'idna': '3.20',
    'importlib-metadata': '10.1.0', 'jinja2': '3.1.6', 'markdown-it-py': '4.2.0', 'markupsafe': '3.0.4', 'mdurl': '0.1.2',
    'mpmath': '1.3.0', 'networkx': '3.7', 'numpy': '2.5.4', 'packaging': '26.3', 'pillow': '13.0.0', 'psutil': '7.2.2',
    'pygments': '2.21.0', 'pyyaml': '6.0.3', 'regex': '2026.9.29', 'requests': '2.34.2', 'rich': '15.0.0', 'safetensors': '0.8.0',
    'setuptools': '84.2.1', 'shellingham': '1.5.4', 'sympy': '1.14.0', 'tokenizers': '0.23.3', 'torch': '2.14.1+cu130',
    'torchvision': '0.29.1+cu130', 'tqdm': '4.70.1', 'transformers': '5.22.1', 'typer': '0.27.3', 'typing-extensions': '4.16.0',
    'urllib3': '2.8.0', 'zipp': '4.1.2',
}
CU130 = 'https://download.pytorch.org/whl/cu130'


def test_pyproject_pins_the_prototype_environment():
    doc = tomllib.loads((IMAGEGEN / 'pyproject.toml').read_text(encoding='utf-8'))
    assert doc['project']['requires-python'] == '==3.13.15'
    for requirement in doc['project']['dependencies']:
        name, _, version = requirement.partition('==')
        assert version and PROTOTYPE_PINS.get(name) == version, requirement
    names = {r.partition('==')[0] for r in doc['project']['dependencies']}
    assert {'torch', 'torchvision', 'diffusers', 'transformers', 'accelerate', 'psutil', 'pillow'} <= names
    uv = doc['tool']['uv']
    assert uv['package'] is False and uv['environments'] == ["sys_platform == 'win32'"]
    assert {c.partition('==')[0]: c.partition('==')[2] for c in uv['constraint-dependencies']} == PROTOTYPE_PINS
    assert uv['index'] == [{'name': 'pytorch-cu130', 'url': CU130, 'explicit': True}]
    assert uv['sources'] == {'torch': {'index': 'pytorch-cu130'}, 'torchvision': {'index': 'pytorch-cu130'}}


def test_uv_lock_resolves_the_pins_from_the_cu130_index_with_hashes():
    lock = tomllib.loads((IMAGEGEN / 'uv.lock').read_text(encoding='utf-8'))
    assert lock['requires-python'] == '==3.13.15'
    assert lock['resolution-markers'] == ["sys_platform == 'win32'"]
    packages = {p['name']: p for p in lock['package']}
    assert set(packages) == set(PROTOTYPE_PINS) | {'aiavc-imagegen'}
    for name, version in PROTOTYPE_PINS.items():
        package = packages[name]
        assert package['version'] == version, name
        files = package.get('wheels', []) + ([package['sdist']] if 'sdist' in package else [])
        assert files and all(re.fullmatch(r'sha256:[0-9a-f]{64}', f.get('hash', '')) for f in files), name
    for name in ('torch', 'torchvision'):
        assert packages[name]['source'] == {'registry': CU130}
        assert all('cp313-cp313-win_amd64' in wheel['url'] for wheel in packages[name]['wheels'])
    assert packages['aiavc-imagegen']['source'] == {'virtual': '.'}
    # The lock was made from this pyproject (what `uv lock --locked` checks): same constraints and the same direct requirements.
    project = tomllib.loads((IMAGEGEN / 'pyproject.toml').read_text(encoding='utf-8'))
    assert {c['name']: c['specifier'] for c in lock['manifest']['constraints']} == {n: f'=={v}' for n, v in PROTOTYPE_PINS.items()}
    requires = {r['name']: r['specifier'] for r in packages['aiavc-imagegen']['metadata']['requires-dist']}
    assert requires == {n: f'=={v}' for n, _, v in (d.partition('==') for d in project['project']['dependencies'])}
