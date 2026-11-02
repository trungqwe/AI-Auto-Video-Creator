"""Danh mục trọng số ghim (weights.lock.json), bố cục cache Hugging Face và kiểm băm có tem cho sidecar sinh ảnh (IMGGEN-SVC).

Trọng số nằm ngoài cây Git ở <data>/models/hf-hub theo bố cục cache HF (models--<org>--<name>/snapshots/<revision>/<path>,
refs/main = revision). provision.py cài và băm đủ rồi ghi tem (đường dẫn, kích thước, mtime, sha256). Lúc khởi động, sidecar so
từng tệp với tem; tem cũ, thiếu hoặc --full-verify thì băm lại tất cả. Thiếu hay sai một tệp là not_provisioned kèm danh sách:
không tải, không dùng mô hình khác, không đường lui. Chỉ dùng thư viện chuẩn.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

SCHEMA_VERSION = 1
MANIFEST_NAME = 'weights.lock.json'
STAMP_NAME = 'imagegen-weights.stamp.json'
HASH_CHUNK_BYTES = 8 << 20
SOURCE_KINDS = frozenset({'lfs_sha256', 'git_blob_sha1', 'local_copy'})
_HEX40 = re.compile(r'[0-9a-f]{40}')
_HEX64 = re.compile(r'[0-9a-f]{64}')
_REPO = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*')
_SEGMENT = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.-]*')


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class Entry:
    repo: str
    revision: str
    path: str
    size: int
    sha256: str
    component: str

    @property
    def label(self) -> str:
        return f'{self.repo}@{self.revision[:12]}/{self.path}'


@dataclass(frozen=True)
class Manifest:
    entries: tuple[Entry, ...]
    sha256: str
    revisions: dict = field(default_factory=dict)

    def component_bytes(self, component: str) -> int:
        return sum(entry.size for entry in self.entries if entry.component == component)


@dataclass
class Verification:
    ok: bool
    missing: list[str]
    mismatched: list[str]
    refs: list[str]
    rehashed: bool
    stamp_written: bool
    seconds: float

    def problems(self) -> list[str]:
        return [f'missing: {m}' for m in self.missing] + [f'mismatched: {m}' for m in self.mismatched] + [f'refs: {r}' for r in self.refs]


def _safe_path(value) -> str:
    if not isinstance(value, str) or not value or '\\' in value:
        raise ManifestError(f'invalid path {value!r}')
    parts = PurePosixPath(value).parts
    if value.startswith('/') or not parts or any(not _SEGMENT.fullmatch(p) for p in parts):
        raise ManifestError(f'invalid path {value!r}')
    return value


def load_manifest(path: Path) -> Manifest:
    """Reads and checks weights.lock.json: schema 1, weights outside Git, one revision per repo, safe relative paths, sizes, sha256."""
    raw = Path(path).read_bytes()
    try:
        doc = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError) as error:
        raise ManifestError(f'{path}: not UTF-8 JSON ({type(error).__name__})') from None
    if not isinstance(doc, dict) or doc.get('schema_version') != SCHEMA_VERSION:
        raise ManifestError('schema_version must be 1')
    if not isinstance(doc.get('storage'), dict) or doc['storage'].get('in_git') is not False:
        raise ManifestError('storage.in_git must be false')
    files = doc.get('files')
    if not isinstance(files, list) or not files:
        raise ManifestError('files must be a non-empty list')
    entries, revisions, seen = [], {}, set()
    for index, item in enumerate(files):
        if not isinstance(item, dict):
            raise ManifestError(f'files[{index}] must be an object')
        repo, revision = item.get('repo'), item.get('revision')
        if not isinstance(repo, str) or not _REPO.fullmatch(repo):
            raise ManifestError(f'files[{index}].repo invalid')
        if not isinstance(revision, str) or not _HEX40.fullmatch(revision):
            raise ManifestError(f'files[{index}].revision must be a 40-hex commit')
        if revisions.setdefault(repo, revision) != revision:
            raise ManifestError(f'{repo} pinned at two revisions')
        rel = _safe_path(item.get('path'))
        size, sha256 = item.get('size'), item.get('sha256')
        if type(size) is not int or size <= 0:
            raise ManifestError(f'files[{index}].size must be a positive integer')
        if not isinstance(sha256, str) or not _HEX64.fullmatch(sha256):
            raise ManifestError(f'files[{index}].sha256 must be 64 lowercase hex characters')
        source = item.get('source')
        if not isinstance(source, dict) or source.get('kind') not in SOURCE_KINDS:
            raise ManifestError(f'files[{index}].source.kind must be one of {sorted(SOURCE_KINDS)}')
        component = item.get('component')
        if not isinstance(component, str) or not component:
            raise ManifestError(f'files[{index}].component missing')
        if (repo, rel.lower()) in seen:
            raise ManifestError(f'{repo}/{rel} listed twice')
        seen.add((repo, rel.lower()))
        entries.append(Entry(repo, revision, rel, size, sha256, component))
    return Manifest(tuple(entries), hashlib.sha256(raw).hexdigest(), revisions)


def repo_dir(hub: Path, repo: str) -> Path:
    return Path(hub) / ('models--' + repo.replace('/', '--'))


def snapshot_dir(hub: Path, repo: str, revision: str) -> Path:
    return repo_dir(hub, repo) / 'snapshots' / revision


def file_path(hub: Path, entry: Entry) -> Path:
    return snapshot_dir(hub, entry.repo, entry.revision).joinpath(*PurePosixPath(entry.path).parts)


def sha256_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with Path(path).open('rb') as handle:
        while True:
            chunk = handle.read(HASH_CHUNK_BYTES)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f'{path.name}.partial-{os.getpid()}-{time.time_ns()}')
    with tmp.open('w', encoding='utf-8', newline='\n') as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def stamp_path(hub: Path) -> Path:
    return Path(hub) / STAMP_NAME


def read_stamp(hub: Path) -> dict | None:
    try:
        doc = json.loads(stamp_path(hub).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) and isinstance(doc.get('files'), list) else None


def write_stamp(hub: Path, manifest: Manifest, records: list[dict]) -> None:
    doc = {'schema_version': SCHEMA_VERSION, 'manifest_sha256': manifest.sha256, 'written_at': int(time.time()), 'files': records}
    atomic_write_text(stamp_path(hub), json.dumps(doc, indent=1) + '\n')


def check_refs(hub: Path, manifest: Manifest) -> list[str]:
    """refs/main of every repo must hold its pinned revision (the cache layout the prototype loaded offline)."""
    problems = []
    for repo, revision in sorted(manifest.revisions.items()):
        ref = repo_dir(hub, repo) / 'refs' / 'main'
        try:
            value = ref.read_text(encoding='utf-8').strip()
        except OSError:
            value = None
        if value != revision:
            problems.append(f'{repo} refs/main is {value!r}, expected {revision}')
    return problems


def _stamp_matches(stamp: dict | None, manifest: Manifest) -> dict | None:
    if not stamp or stamp.get('manifest_sha256') != manifest.sha256:
        return None
    return {(r.get('repo'), r.get('path')): r for r in stamp['files'] if isinstance(r, dict)}


def verify(hub: Path, manifest: Manifest, *, full: bool = False, hasher=sha256_file, write=True) -> Verification:
    """Checks every pinned file. Fast path: the stamp lists the same manifest and every file keeps its stamped size and mtime.
    Otherwise (or full=True) every present file is hashed again; when all match, a fresh stamp is written."""
    started = time.monotonic()
    missing, present = [], []
    for entry in manifest.entries:
        target = file_path(hub, entry)
        (present if target.is_file() else missing).append((entry, target))
    refs = check_refs(hub, manifest)
    missing_labels = [entry.label for entry, _ in missing]
    stamped = None if full else _stamp_matches(read_stamp(hub), manifest)
    if stamped is not None and not missing:
        fresh = True
        for entry, target in present:
            record = stamped.get((entry.repo, entry.path))
            stat = target.stat()
            if (not record or record.get('sha256') != entry.sha256 or record.get('revision') != entry.revision
                    or record.get('size') != stat.st_size or record.get('mtime_ns') != stat.st_mtime_ns or stat.st_size != entry.size):
                fresh = False
                break
        if fresh:
            return Verification(not refs, [], [], refs, False, False, round(time.monotonic() - started, 3))
    mismatched, records = [], []
    for entry, target in present:
        stat = target.stat()
        if stat.st_size != entry.size:
            mismatched.append(f'{entry.label} (size {stat.st_size}, expected {entry.size})')
            continue
        size, digest = hasher(target)
        if size != entry.size or digest != entry.sha256:
            mismatched.append(f'{entry.label} (sha256 {digest[:12]}, expected {entry.sha256[:12]})')
            continue
        records.append({'repo': entry.repo, 'revision': entry.revision, 'path': entry.path, 'size': entry.size,
                        'mtime_ns': target.stat().st_mtime_ns, 'sha256': entry.sha256})
    ok = not missing and not mismatched and not refs
    written = False
    if ok and write:
        write_stamp(hub, manifest, records)
        written = True
    return Verification(ok, missing_labels, mismatched, refs, True, written, round(time.monotonic() - started, 3))
