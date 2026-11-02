"""Weight verification and cache management for FLUX 3 Image Klein."""

import dataclasses
import hashlib
import json
import os
import pathlib
import time

STAMP_NAME = 'imagegen-weights.stamp.json'


def default_hub():
    if 'LOCALAPPDATA' in os.environ and os.environ['LOCALAPPDATA']:
        return pathlib.Path(os.environ['LOCALAPPDATA']) / 'AIAutoVideoCreator' / 'models' / 'hf-hub'
    return pathlib.Path.home() / '.aiavc' / 'models' / 'hf-hub'


def load_manifest(path=None):
    p = pathlib.Path(path) if path else pathlib.Path(__file__).resolve().parent / 'weights.lock.json'
    manifest = json.loads(p.read_text(encoding='utf-8'))
    if manifest.get('schema_version') != 1:
        raise ValueError(f"Invalid schema_version: {manifest.get('schema_version')}")
    if len(manifest.get('files', [])) != 25:
        raise ValueError(f"Expected 25 files, got {len(manifest.get('files', []))}")
    return manifest


def repo_dir(hub, repo):
    return pathlib.Path(hub) / ('models--' + repo.replace('/', '--'))


def file_path(hub, repo, revision, rel):
    return repo_dir(hub, repo) / 'snapshots' / revision / pathlib.Path(rel)


def manifest_digest(manifest):
    return hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode('utf-8')
    ).hexdigest()


def sha256_file(path, chunk=1048576):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk_bytes := f.read(chunk):
            h.update(chunk_bytes)
    return h.hexdigest()


@dataclasses.dataclass
class VerifyResult:
    ok: bool
    problems: list[str]
    hashed: int
    trusted_stamp: bool


def write_stamp(hub, manifest):
    hub = pathlib.Path(hub)
    m_digest = manifest_digest(manifest)
    files_map = {}
    for f in manifest.get('files', []):
        p = file_path(hub, f['repo'], f['revision'], f['path'])
        if p.exists():
            st = p.stat()
            key = f"{f['repo']}|{f['path']}"
            files_map[key] = [st.st_size, st.st_mtime_ns]
    stamp_data = {'manifest_sha256': m_digest, 'files': files_map}
    (hub / STAMP_NAME).write_text(json.dumps(stamp_data, indent=2), encoding='utf-8')


def verify(hub, manifest, full=False, hasher=sha256_file):
    hub = pathlib.Path(hub)
    problems = []
    hashed = 0

    for repo, rinfo in manifest.get('repos', {}).items():
        ref_file = repo_dir(hub, repo) / 'refs' / 'main'
        if not ref_file.exists():
            problems.append(f'refs/main {repo}')
        else:
            val = ref_file.read_text(encoding='utf-8').strip()
            if val != rinfo['revision']:
                problems.append(f'refs/main {repo}')

    for f in manifest.get('files', []):
        p = file_path(hub, f['repo'], f['revision'], f['path'])
        if not p.exists():
            problems.append(f"missing {f['path']}")
        elif p.stat().st_size != f['size']:
            problems.append(f"size {f['path']}")

    if not problems and not full:
        stamp_path = hub / STAMP_NAME
        if stamp_path.exists():
            try:
                sdata = json.loads(stamp_path.read_text(encoding='utf-8'))
                if sdata.get('manifest_sha256') == manifest_digest(manifest):
                    sfiles = sdata.get('files', {})
                    stamp_ok = True
                    for f in manifest.get('files', []):
                        key = f"{f['repo']}|{f['path']}"
                        if key not in sfiles:
                            stamp_ok = False
                            break
                        rec_size, rec_mtime_ns = sfiles[key]
                        p = file_path(hub, f['repo'], f['revision'], f['path'])
                        st = p.stat()
                        if st.st_size != rec_size or st.st_mtime_ns != rec_mtime_ns:
                            stamp_ok = False
                            break
                    if stamp_ok:
                        return VerifyResult(ok=True, problems=[], hashed=0, trusted_stamp=True)
            except Exception:
                pass

    if not any(p.startswith(('missing ', 'size ')) for p in problems):
        for f in manifest.get('files', []):
            p = file_path(hub, f['repo'], f['revision'], f['path'])
            h = hasher(p)
            hashed += 1
            if h != f['sha256']:
                problems.append(f"sha256 {f['path']}")

    if not problems:
        write_stamp(hub, manifest)
        return VerifyResult(ok=True, problems=[], hashed=hashed, trusted_stamp=False)

    return VerifyResult(ok=False, problems=problems, hashed=hashed, trusted_stamp=False)
