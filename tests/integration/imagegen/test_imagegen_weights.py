"""IMGGEN-SVC: danh mục trọng số ghim (weights.lock.json), kiểm băm có tem trên tệp nhỏ và provision.py (chép từ hub, tải qua hàm
được truyền vào, không token). Không mạng, không GPU, không trọng số thật.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
IMAGEGEN = ROOT / 'tools' / 'imagegen'
if str(ROOT / 'tools') not in sys.path:
    sys.path.insert(0, str(ROOT / 'tools'))

from imagegen import engine, provision, weights  # noqa: E402

KLEIN = ('black-forest-labs/flux-3-image-klein', '337337621b8526e120f2275d250242f4a6bedd75')
PUP = ('black-forest-labs/flux-3-image-klein-pup', '3f3edb52b2c55de0d49feab28598b68f7f8e4830')
KLEIN_PATHS = {
    'LICENSE.md', 'NOTICE.md', 'modular_model_index.json', 'transformer/config.json', 'vae/config.json',
    'vae/diffusion_pytorch_model.safetensors', 'variants/fp8r/config.json', 'variants/fp8r/hf_quant_config.json',
    'variants/fp8r/manifest.json', 'variants/fp8r/model.safetensors',
} | {f'text_encoder/{name}' for name in (
    'LICENSE', 'README.md', 'chat_template.json', 'config.json', 'generation_config.json', 'merges.txt',
    'model-00001-of-00002.safetensors', 'model-00002-of-00002.safetensors', 'model.safetensors.index.json',
    'preprocessor_config.json', 'tokenizer.json', 'tokenizer_config.json', 'video_preprocessor_config.json', 'vocab.json')}
LFS = {  # lfs_sha256 of the cached hub tree at 337337621b85; fp8r also in BFL's variants/fp8r/manifest.json
    'text_encoder/model-00001-of-00002.safetensors': '30a01a0556622645a3cce87b655bbbbbc1f170c196099f1b666c93202c3339a9',
    'text_encoder/model-00002-of-00002.safetensors': '046296a2a387efb43b0c997d5833c789604d168834f6e0d3064bf7bb13d002a6',
    'vae/diffusion_pytorch_model.safetensors': 'd64f3a68e1cc4f9f4e29b6e0da38a0204fe9a49f2d4053f0ec1fa1ca02f9c4b5',
    'variants/fp8r/model.safetensors': '30054053f630725b488aead9a81b422793cee18027856a16bd17b902ad612018',
}


def test_manifest_pins_25_files_of_two_revisions():
    manifest = weights.load_manifest(IMAGEGEN / 'weights.lock.json')
    assert manifest.revisions == {KLEIN[0]: KLEIN[1], PUP[0]: PUP[1]}
    assert {e.path for e in manifest.entries if e.repo == KLEIN[0]} == KLEIN_PATHS
    assert [e.path for e in manifest.entries if e.repo == PUP[0]] == ['system_prompts.json']
    assert len(manifest.entries) == 25 and sum(e.size for e in manifest.entries) == 15_494_505_294
    by_path = {e.path: e for e in manifest.entries if e.repo == KLEIN[0]}
    assert {path: by_path[path].sha256 for path in LFS} == LFS
    assert not any('diffusion_pytorch_model-0000' in e.path or 'nvfp4' in e.path for e in manifest.entries)
    assert manifest.component_bytes('text_encoder') > 8_875_000_000 and 6_270_949_144 < manifest.component_bytes('transformer') < 6_271_000_000


def test_each_hash_records_how_it_was_checked():
    doc = json.loads((IMAGEGEN / 'weights.lock.json').read_text(encoding='utf-8'))
    assert doc['storage'] == {'base_dir_default': 'LOCALAPPDATA/AIAutoVideoCreator', 'subdir': 'models/hf-hub',
                              'layout': doc['storage']['layout'], 'in_git': False}
    kinds = {}
    for entry in doc['files']:
        kinds.setdefault(entry['source']['kind'], []).append(entry['path'])
        if entry['source']['kind'] == 'git_blob_sha1':
            assert len(entry['source']['blob_id']) == 40 and entry['source']['tree'] == KLEIN[1]
    assert sorted(kinds['lfs_sha256']) == sorted(LFS) and len(kinds['git_blob_sha1']) == 20
    assert kinds['local_copy'] == ['system_prompts.json']


def _manifest_doc(files):
    return {'schema_version': 1, 'storage': {'in_git': False}, 'files': files}


def _entry(repo, revision, path, data, component='text_encoder'):
    return {'repo': repo, 'revision': revision, 'path': path, 'component': component, 'size': len(data),
            'sha256': hashlib.sha256(data).hexdigest(), 'source': {'kind': 'local_copy'}}


TINY = [
    ('acme/klein', 'a' * 40, 'modular_model_index.json', b'{"tiny": true}\n'),
    ('acme/klein', 'a' * 40, 'text_encoder/model.safetensors', b'\x00weights\x01' * 64),
    ('acme/pup', 'b' * 40, 'system_prompts.json', b'{"t2i": "prompt"}\n'),
]


@pytest.fixture
def tiny(tmp_path):
    path = tmp_path / 'weights.lock.json'
    path.write_text(json.dumps(_manifest_doc([_entry(*row) for row in TINY])), encoding='utf-8')
    return weights.load_manifest(path)


def _fill(hub: Path, rows=TINY, refs=True):
    for repo, revision, rel, data in rows:
        target = weights.snapshot_dir(hub, repo, revision) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if refs:
            ref = weights.repo_dir(hub, repo) / 'refs' / 'main'
            ref.parent.mkdir(parents=True, exist_ok=True)
            ref.write_text(revision, encoding='utf-8')


@pytest.mark.parametrize('bad, message', [
    ({'path': '../escape.json'}, 'invalid path'),
    ({'path': 'text_encoder\\x.json'}, 'invalid path'),
    ({'path': '/abs.json'}, 'invalid path'),
    ({'sha256': 'f' * 63}, 'sha256'),
    ({'size': 0}, 'size'),
    ({'revision': 'main'}, 'revision'),
    ({'source': {'kind': 'trust_me'}}, 'source.kind'),
])
def test_unsafe_manifest_entries_are_refused(tmp_path, bad, message):
    entry = dict(_entry(*TINY[0]), **bad)
    path = tmp_path / 'm.json'
    path.write_text(json.dumps(_manifest_doc([entry])), encoding='utf-8')
    with pytest.raises(weights.ManifestError, match=message.replace('.', r'\.')):
        weights.load_manifest(path)


def test_manifest_refuses_duplicates_two_revisions_and_weights_in_git(tmp_path):
    path = tmp_path / 'm.json'
    for files, storage, message in (
        ([_entry(*TINY[0]), _entry(*TINY[0])], {'in_git': False}, 'listed twice'),
        ([_entry(*TINY[0]), _entry('acme/klein', 'c' * 40, 'x.json', b'x')], {'in_git': False}, 'two revisions'),
        ([_entry(*TINY[0])], {'in_git': True}, 'in_git'),
    ):
        path.write_text(json.dumps({'schema_version': 1, 'storage': storage, 'files': files}), encoding='utf-8')
        with pytest.raises(weights.ManifestError, match=message):
            weights.load_manifest(path)


class CountingHasher:
    def __init__(self):
        self.calls = []

    def __call__(self, path):
        self.calls.append(Path(path).name)
        return weights.sha256_file(path)


def test_verify_hashes_once_then_trusts_a_fresh_stamp(tmp_path, tiny):
    hub = tmp_path / 'hub'
    _fill(hub)
    hasher = CountingHasher()
    first = weights.verify(hub, tiny, hasher=hasher)
    assert first.ok and first.rehashed and first.stamp_written and len(hasher.calls) == 3
    assert weights.stamp_path(hub).is_file()
    hasher.calls.clear()
    second = weights.verify(hub, tiny, hasher=hasher)
    assert second.ok and not second.rehashed and hasher.calls == []
    full = weights.verify(hub, tiny, full=True, hasher=hasher)
    assert full.ok and full.rehashed and len(hasher.calls) == 3
    hasher.calls.clear()
    target = weights.snapshot_dir(hub, 'acme/klein', 'a' * 40) / 'modular_model_index.json'
    os.utime(target, ns=(target.stat().st_atime_ns, target.stat().st_mtime_ns + 5_000_000_000))
    touched = weights.verify(hub, tiny, hasher=hasher)
    assert touched.ok and touched.rehashed and len(hasher.calls) == 3


def test_verify_lists_missing_and_mismatched_files(tmp_path, tiny):
    hub = tmp_path / 'hub'
    _fill(hub)
    assert weights.verify(hub, tiny).ok
    (weights.snapshot_dir(hub, 'acme/pup', 'b' * 40) / 'system_prompts.json').unlink()
    model = weights.snapshot_dir(hub, 'acme/klein', 'a' * 40) / 'text_encoder' / 'model.safetensors'
    model.write_bytes(b'\x00WEIGHTS\x01' * 64)
    result = weights.verify(hub, tiny)
    assert not result.ok and result.rehashed and not result.stamp_written
    assert result.missing == ['acme/pup@bbbbbbbbbbbb/system_prompts.json']
    assert len(result.mismatched) == 1 and 'text_encoder/model.safetensors' in result.mismatched[0]
    assert any(p.startswith('missing: ') for p in result.problems()) and any(p.startswith('mismatched: ') for p in result.problems())


def test_verify_requires_refs_main_at_the_pinned_revision(tmp_path, tiny):
    hub = tmp_path / 'hub'
    _fill(hub, refs=False)
    result = weights.verify(hub, tiny)
    assert not result.ok and len(result.refs) == 2 and not result.stamp_written
    _fill(hub)
    assert weights.verify(hub, tiny).ok


def test_provision_copies_from_a_hub_then_writes_refs_and_the_stamp(tmp_path, tiny):
    source, hub = tmp_path / 'source', tmp_path / 'hub'
    _fill(source, refs=False)
    report = provision.install(hub, tiny, from_hub=source, download=None, log=lambda message: None)
    assert report['ok'] and report['copied'] == 3 and report['downloaded'] == 0 and report['stamp_written']
    assert (weights.repo_dir(hub, 'acme/klein') / 'refs' / 'main').read_text(encoding='utf-8') == 'a' * 40
    assert weights.verify(hub, tiny).ok and not weights.verify(hub, tiny).rehashed
    again = provision.install(hub, tiny, from_hub=source, download=None, log=lambda message: None)
    assert again['ok'] and again['kept'] == 3 and again['copied'] == 0


def test_provision_refuses_a_source_with_other_bytes_and_leaves_no_partial_file(tmp_path, tiny):
    source, hub = tmp_path / 'source', tmp_path / 'hub'
    rows = [TINY[0], (TINY[1][0], TINY[1][1], TINY[1][2], b'tampered'), TINY[2]]
    _fill(source, rows, refs=False)
    report = provision.install(hub, tiny, from_hub=source, download=None, log=lambda message: None)
    assert not report['ok'] and report['copied'] == 2 and len(report['failures']) == 1
    target_dir = weights.snapshot_dir(hub, 'acme/klein', 'a' * 40) / 'text_encoder'
    assert not target_dir.exists() or list(target_dir.iterdir()) == []


def test_provision_moves_a_wrong_file_aside_and_downloads_without_a_token(tmp_path, tiny):
    hub = tmp_path / 'hub'
    _fill(hub, [TINY[0], (TINY[1][0], TINY[1][1], TINY[1][2], b'stale'), TINY[2]])
    calls = []

    def download(**kwargs):
        calls.append(kwargs)
        repo, revision, rel, data = next(row for row in TINY if row[2] == kwargs['filename'])
        target = weights.snapshot_dir(Path(kwargs['cache_dir']), repo, revision) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return str(target)

    report = provision.install(hub, tiny, download=download, log=lambda message: None)
    assert report['ok'] and report['downloaded'] == 1 and report['kept'] == 2 and len(report['moved_aside']) == 1
    assert calls == [{'repo_id': 'acme/klein', 'filename': 'text_encoder/model.safetensors', 'revision': 'a' * 40, 'cache_dir': str(hub)}]
    assert Path(report['moved_aside'][0]).read_bytes() == b'stale'


def _safetensors(tensors) -> bytes:
    header, data = {}, b''
    for name, (dtype, shape, raw) in tensors.items():
        header[name] = {'dtype': dtype, 'shape': shape, 'data_offsets': [len(data), len(data) + len(raw)]}
        data += raw
    blob = json.dumps(dict(header, __metadata__={'format': 'pt'})).encode('utf-8')
    return len(blob).to_bytes(8, 'little') + blob + data


TINY_TENSORS = {'a.weight': ('BF16', [2, 3], bytes(range(12))), 'a.weight_scale': ('F32', [2], bytes(8)),
                'q': ('F8_E4M3', [4], b'\x01\x02\x03\x04'), 'step': ('I64', [], bytes(8))}


def test_safetensors_headers_are_read_and_checked_without_torch(tmp_path):
    path = tmp_path / 'tiny.safetensors'
    path.write_bytes(_safetensors(TINY_TENSORS))
    offset, entries = engine.read_safetensors_header(path)
    assert offset == 8 + int.from_bytes(path.read_bytes()[:8], 'little')
    assert entries == {'a.weight': ('BF16', (2, 3), 0, 12), 'a.weight_scale': ('F32', (2,), 12, 20), 'q': ('F8_E4M3', (4,), 20, 24),
                       'step': ('I64', (), 24, 32)}
    assert path.read_bytes()[offset + 20:offset + 24] == b'\x01\x02\x03\x04'
    broken = {
        'dtype': _safetensors({'x': ('F4', [2], bytes(1))}),
        'shape': _safetensors({'x': ('F32', [3], bytes(8))}),
        'past the end': _safetensors({'x': ('F32', [2], bytes(8))})[:-4],
        'header length': (10 ** 9).to_bytes(8, 'little') + b'{}',
    }
    for why, raw in broken.items():
        path.write_bytes(raw)
        with pytest.raises(ValueError):
            engine.read_safetensors_header(path)


def test_chunk_spans_cover_every_byte_once():
    assert engine.chunk_spans(10, 4) == [(0, 4), (4, 4), (8, 2)]
    assert engine.chunk_spans(8, 4) == [(0, 4), (4, 4)] and engine.chunk_spans(0, 4) == []
    spans = engine.chunk_spans(777_912_320, engine.STREAM_CHUNK_BYTES)
    assert sum(length for _, length in spans) == 777_912_320 and max(length for _, length in spans) == engine.STREAM_CHUNK_BYTES
    assert engine.STREAM_CHUNK_BYTES == 64 * 1024 * 1024


def test_the_engine_never_maps_or_preloads_a_whole_weights_file():
    # Control's GPU measurement (02/11/2026): safetensors load_file mapped the 6.27 GB fp8r file copy-on-write and the process
    # committed 16.2 GB. The engine reads tensors itself, chunk by chunk, into tensors on the GPU.
    tree = ast.parse((IMAGEGEN / 'engine.py').read_text(encoding='utf-8'))
    imported = {alias.name.split('.')[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported |= {(node.module or '').split('.')[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    called = {node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, 'id', None)
              for node in ast.walk(tree) if isinstance(node, ast.Call)}
    assert not {'mmap', 'safetensors'} & imported
    assert not {'load_file', 'safe_open', 'load_components', 'enable_model_cpu_offload'} & called
    assert {'stream_safetensors', 'load_state_dict', 'from_single_file', 'empty_cache', 'collect'} <= called


def test_provision_never_handles_the_hugging_face_token():
    tree = ast.parse((IMAGEGEN / 'provision.py').read_text(encoding='utf-8'))
    keywords = {k.arg for node in ast.walk(tree) if isinstance(node, ast.Call) for k in node.keywords}
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert 'token' not in keywords and 'use_auth_token' not in keywords
    assert not {'get_token', 'HfFolder', 'login'} & names
    assert not any('HF_TOKEN' in s or 'HUGGING_FACE_HUB_TOKEN' in s for s in strings)
