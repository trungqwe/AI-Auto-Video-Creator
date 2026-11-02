"""Integration tests for imagegen weights module."""

import hashlib
import json
import os
import pathlib
import re
import struct
import sys
import time
import pytest

TOOLS = pathlib.Path(__file__).resolve().parents[3] / 'tools' / 'imagegen'
sys.path.insert(0, str(TOOLS))

import engine
import protocol
import provision
import weights


def test_verify_hashes_once_then_trusts_a_fresh_stamp(tmp_path):
    hub = tmp_path / "hub"
    repo = "org/model"
    revision = "abcdef0123456789"
    content1 = b"tensor_data_one"
    content2 = b"tensor_data_two"
    h1 = hashlib.sha256(content1).hexdigest()
    h2 = hashlib.sha256(content2).hexdigest()

    manifest = {
        "schema_version": 1,
        "repos": {
            repo: {"revision": revision}
        },
        "files": [
            {
                "repo": repo,
                "revision": revision,
                "path": "weights/file1.bin",
                "size": len(content1),
                "sha256": h1,
            },
            {
                "repo": repo,
                "revision": revision,
                "path": "weights/file2.bin",
                "size": len(content2),
                "sha256": h2,
            },
        ]
    }

    f1 = weights.file_path(hub, repo, revision, "weights/file1.bin")
    f2 = weights.file_path(hub, repo, revision, "weights/file2.bin")
    f1.parent.mkdir(parents=True, exist_ok=True)
    f1.write_bytes(content1)
    f2.write_bytes(content2)

    refs_file = weights.repo_dir(hub, repo) / "refs" / "main"
    refs_file.parent.mkdir(parents=True, exist_ok=True)
    refs_file.write_text(revision, encoding="utf-8")

    hash_counts = {"count": 0}

    def counting_hasher(path):
        hash_counts["count"] += 1
        return weights.sha256_file(path)

    # First verify: hashes each file, writes fresh stamp
    res1 = weights.verify(hub, manifest, full=False, hasher=counting_hasher)
    assert res1.ok is True
    assert res1.hashed == 2
    assert res1.trusted_stamp is False
    assert hash_counts["count"] == 2

    # Second verify: trusts stamp, hashes 0 files
    hash_counts["count"] = 0
    res2 = weights.verify(hub, manifest, full=False, hasher=counting_hasher)
    assert res2.ok is True
    assert res2.hashed == 0
    assert res2.trusted_stamp is True
    assert hash_counts["count"] == 0

    # Modify content of file1 with same size to change mtime
    time.sleep(0.01)
    new_content1 = b"tensor_data_mod"
    assert len(new_content1) == len(content1)
    f1.write_bytes(new_content1)

    # Third verify: re-hashes and detects sha256 mismatch
    hash_counts["count"] = 0
    res3 = weights.verify(hub, manifest, full=False, hasher=counting_hasher)
    assert res3.ok is False
    assert any("sha256 weights/file1.bin" in p for p in res3.problems)
    assert hash_counts["count"] > 0

    # Revert file1
    f1.write_bytes(content1)
    weights.write_stamp(hub, manifest)

    # full=True always re-hashes
    hash_counts["count"] = 0
    res_full = weights.verify(hub, manifest, full=True, hasher=counting_hasher)
    assert res_full.ok is True
    assert res_full.hashed == 2
    assert res_full.trusted_stamp is False
    assert hash_counts["count"] == 2


def test_provision_never_handles_the_hugging_face_token():
    prov_text = (TOOLS / "provision.py").read_text(encoding="utf-8")
    assert "HF_TOKEN" not in prov_text
    assert not re.search(r"token\s*=", prov_text, re.IGNORECASE)
    assert "hf_hub_download" in prov_text

    import ast
    tree = ast.parse(prov_text)
    top_level_imports = [
        node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    for node in top_level_imports:
        names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
        assert not any("huggingface_hub" in n for n in names if n), "huggingface_hub must not be imported at top level"

    func_imports = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                if isinstance(child, (ast.Import, ast.ImportFrom)):
                    names = [a.name for a in child.names] if isinstance(child, ast.Import) else [child.module or ""]
                    if any("huggingface_hub" in n for n in names if n):
                        func_imports.append(child)
    assert len(func_imports) > 0, "huggingface_hub must be imported inside a function"


def test_safetensors_headers_are_read_and_checked_without_torch(tmp_path):
    st_file = tmp_path / "model.safetensors"
    # Tensor 1: F32 shape [2, 2] -> 4 * 4 = 16 bytes. offsets [0, 16]
    # Tensor 2: BF16 shape [4] -> 4 * 2 = 8 bytes. offsets [16, 24]
    header_dict = {
        "t1": {
            "dtype": "F32",
            "shape": [2, 2],
            "data_offsets": [0, 16],
        },
        "t2": {
            "dtype": "BF16",
            "shape": [4],
            "data_offsets": [16, 24],
        },
        "__metadata__": {"format": "pt"}
    }
    header_json = json.dumps(header_dict).encode("utf-8")
    header_len = len(header_json)
    data = b"\x00" * 24

    with open(st_file, "wb") as f:
        f.write(struct.pack("<Q", header_len))
        f.write(header_json)
        f.write(data)

    parsed_header, data_start = engine.read_safetensors_header(st_file)
    assert data_start == 8 + header_len
    assert "t1" in parsed_header and "t2" in parsed_header
    assert "__metadata__" not in parsed_header

    # Error case 1: offsets exceed file size
    bad_file = tmp_path / "bad_offset.safetensors"
    bad_header = {
        "t": {"dtype": "F32", "shape": [1], "data_offsets": [0, 100]}
    }
    bad_json = json.dumps(bad_header).encode("utf-8")
    with open(bad_file, "wb") as f:
        f.write(struct.pack("<Q", len(bad_json)))
        f.write(bad_json)
        f.write(b"\x00" * 4)
    with pytest.raises(ValueError):
        engine.read_safetensors_header(bad_file)

    # Error case 2: unknown dtype
    bad_dtype_file = tmp_path / "bad_dtype.safetensors"
    bad_header2 = {
        "t": {"dtype": "UNKNOWN", "shape": [1], "data_offsets": [0, 4]}
    }
    bad_json2 = json.dumps(bad_header2).encode("utf-8")
    with open(bad_dtype_file, "wb") as f:
        f.write(struct.pack("<Q", len(bad_json2)))
        f.write(bad_json2)
        f.write(b"\x00" * 4)
    with pytest.raises(ValueError):
        engine.read_safetensors_header(bad_dtype_file)

    # Error case 3: shape * dtype does not match offset span
    bad_span_file = tmp_path / "bad_span.safetensors"
    bad_header3 = {
        "t": {"dtype": "F32", "shape": [2], "data_offsets": [0, 4]}  # 2*4=8 != 4
    }
    bad_json3 = json.dumps(bad_header3).encode("utf-8")
    with open(bad_span_file, "wb") as f:
        f.write(struct.pack("<Q", len(bad_json3)))
        f.write(bad_json3)
        f.write(b"\x00" * 8)
    with pytest.raises(ValueError):
        engine.read_safetensors_header(bad_span_file)

    # Error case 4: n too large (> 100 MiB)
    bad_large_file = tmp_path / "bad_large.safetensors"
    with open(bad_large_file, "wb") as f:
        f.write(struct.pack("<Q", 105 * 1024 * 1024))
        f.write(b"\x00" * 16)
    with pytest.raises(ValueError):
        engine.read_safetensors_header(bad_large_file)

    # Error case 5: overlapping tensor segments
    bad_overlap_file = tmp_path / "bad_overlap.safetensors"
    bad_header5 = {
        "t1": {"dtype": "F32", "shape": [2], "data_offsets": [0, 8]},
        "t2": {"dtype": "F32", "shape": [2], "data_offsets": [4, 12]},
    }
    bad_json5 = json.dumps(bad_header5).encode("utf-8")
    with open(bad_overlap_file, "wb") as f:
        f.write(struct.pack("<Q", len(bad_json5)))
        f.write(bad_json5)
        f.write(b"\x00" * 16)
    with pytest.raises(ValueError):
        engine.read_safetensors_header(bad_overlap_file)


def test_the_engine_never_maps_or_preloads_a_whole_weights_file():
    eng_text = (TOOLS / "engine.py").read_text(encoding="utf-8")
    assert "mmap" not in eng_text
    assert "load_file(" not in eng_text
    assert "safe_open(" not in eng_text
    assert "read_bytes(" not in eng_text
    assert "STREAM_CHUNK_BYTES = 64 * 1024 * 1024" in eng_text
    assert "readinto" in eng_text


def test_load_manifest_returns_25_files():
    manifest = weights.load_manifest()
    assert len(manifest.get("files", [])) == 25
    assert len(manifest.get("repos", {})) == 2
    assert manifest.get("storage", {}).get("in_git") is False


def test_file_path_layout():
    hub = pathlib.Path("/tmp/hub")
    p = weights.file_path(hub, "org/name", "rev1", "sub/file.safetensors")
    expected = hub / "models--org--name" / "snapshots" / "rev1" / "sub" / "file.safetensors"
    assert p == expected


def test_verify_fails_when_refs_main_is_wrong(tmp_path):
    hub = tmp_path / "hub"
    repo = "test/repo"
    rev = "rev123"
    manifest = {
        "schema_version": 1,
        "repos": {repo: {"revision": rev}},
        "files": []
    }
    # No refs/main
    res = weights.verify(hub, manifest)
    assert res.ok is False
    assert any("refs/main" in p for p in res.problems)

    # Wrong refs/main
    ref_f = weights.repo_dir(hub, repo) / "refs" / "main"
    ref_f.parent.mkdir(parents=True, exist_ok=True)
    ref_f.write_text("wrong_rev", encoding="utf-8")
    res2 = weights.verify(hub, manifest)
    assert res2.ok is False
    assert any("refs/main" in p for p in res2.problems)


def test_provision_from_hub_copies_and_hashes(tmp_path):
    src_hub = tmp_path / "src_hub"
    dst_hub = tmp_path / "dst_hub"
    repo = "test/repo"
    rev = "rev456"
    content = b"sample_weights_content"
    sha = hashlib.sha256(content).hexdigest()

    manifest = {
        "schema_version": 1,
        "repos": {repo: {"revision": rev}},
        "files": [
            {
                "repo": repo,
                "revision": rev,
                "path": "weights.bin",
                "size": len(content),
                "sha256": sha
            }
        ]
    }

    src_file = weights.file_path(src_hub, repo, rev, "weights.bin")
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_bytes(content)

    rep = provision.provision(dst_hub, manifest, from_hub=src_hub, download=False)
    assert "weights.bin" in rep["copied"]
    assert not rep["mismatched"]
    assert not rep["missing"]

    vres = weights.verify(dst_hub, manifest)
    assert vres.ok is True


def test_provision_mismatched_source(tmp_path):
    src_hub = tmp_path / "src_hub"
    dst_hub = tmp_path / "dst_hub"
    repo = "test/repo"
    rev = "rev456"
    content = b"corrupted_content"
    expected_sha = hashlib.sha256(b"correct_content").hexdigest()

    manifest = {
        "schema_version": 1,
        "repos": {repo: {"revision": rev}},
        "files": [
            {
                "repo": repo,
                "revision": rev,
                "path": "weights.bin",
                "size": len(content),
                "sha256": expected_sha
            }
        ]
    }

    src_file = weights.file_path(src_hub, repo, rev, "weights.bin")
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_bytes(content)

    rep = provision.provision(dst_hub, manifest, from_hub=src_hub, download=False)
    assert "weights.bin" in rep["mismatched"]
    dst_file = weights.file_path(dst_hub, repo, rev, "weights.bin")
    assert not dst_file.exists()


def test_provision_renames_corrupted_destination(tmp_path):
    hub = tmp_path / "hub"
    repo = "test/repo"
    rev = "rev456"
    good_content = b"original_good_data"
    good_sha = hashlib.sha256(good_content).hexdigest()

    manifest = {
        "schema_version": 1,
        "repos": {repo: {"revision": rev}},
        "files": [
            {
                "repo": repo,
                "revision": rev,
                "path": "data.bin",
                "size": len(good_content),
                "sha256": good_sha
            }
        ]
    }

    dst_file = weights.file_path(hub, repo, rev, "data.bin")
    dst_file.parent.mkdir(parents=True, exist_ok=True)
    dst_file.write_bytes(b"bad_data_length_differs")

    rep = provision.provision(hub, manifest, download=False, clock=lambda: 123456789)
    assert not dst_file.exists()
    renamed = dst_file.with_name("data.bin.mismatch-123456789")
    assert renamed.exists()
    assert "data.bin" in rep["missing"]


def test_provision_missing_without_download(tmp_path):
    hub = tmp_path / "hub"
    repo = "test/repo"
    rev = "rev456"
    manifest = {
        "schema_version": 1,
        "repos": {repo: {"revision": rev}},
        "files": [
            {
                "repo": repo,
                "revision": rev,
                "path": "missing.bin",
                "size": 100,
                "sha256": "00" * 32
            }
        ]
    }

    call_count = {"calls": 0}

    def dummy_download(**kwargs):
        call_count["calls"] += 1

    rep = provision.provision(hub, manifest, download=False, hf_download=dummy_download)
    assert "missing.bin" in rep["missing"]
    assert call_count["calls"] == 0


def test_provision_writes_refs_main_and_stamp(tmp_path):
    hub = tmp_path / "hub"
    src_hub = tmp_path / "src"
    repo = "test/repo"
    rev = "rev999"
    content = b"payload"
    sha = hashlib.sha256(content).hexdigest()

    manifest = {
        "schema_version": 1,
        "repos": {repo: {"revision": rev}},
        "files": [
            {
                "repo": repo,
                "revision": rev,
                "path": "file.bin",
                "size": len(content),
                "sha256": sha
            }
        ]
    }

    src_f = weights.file_path(src_hub, repo, rev, "file.bin")
    src_f.parent.mkdir(parents=True, exist_ok=True)
    src_f.write_bytes(content)

    provision.provision(hub, manifest, from_hub=src_hub, download=False)
    refs_main = weights.repo_dir(hub, repo) / "refs" / "main"
    assert refs_main.exists()
    assert refs_main.read_text(encoding="utf-8") == rev
    stamp_file = hub / weights.STAMP_NAME
    assert stamp_file.exists()