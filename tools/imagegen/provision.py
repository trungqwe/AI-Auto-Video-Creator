"""Cài trọng số ghim của sidecar sinh ảnh (IMGGEN-SVC) vào <data>/models/hf-hub. Control chạy một lần trên máy user; không
bao giờ chạy trong lane.

  python -I tools/imagegen/provision.py --hub <data>/models/hf-hub [--from-hub D:/AIAVC_IMGPROTO/hub] [--no-download]

Mỗi tệp của weights.lock.json: đã có và đúng SHA-256 thì giữ; có trong --from-hub thì chép (băm khi chép, sai thì bỏ bản tạm);
còn lại gọi huggingface_hub.hf_hub_download(revision=<sha>) dưới đăng nhập `hf auth login` của user: mã này không bao giờ đọc,
nhận hay ghi token. Tệp sai nội dung ở đích được dời sang tên .mismatch-<thời điểm>, không xoá. Sau cùng ghi refs/main của từng
kho, băm lại toàn bộ và ghi tem (đường dẫn, kích thước, mtime, sha256) cho lần khởi động nhanh của sidecar.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from imagegen import protocol, weights  # noqa: E402

COPY_CHUNK_BYTES = 8 << 20


def _copy_verified(source: Path, target: Path, entry: weights.Entry) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f'{target.name}.partial-{os.getpid()}-{time.time_ns()}')
    digest = hashlib.sha256()
    size = 0
    try:
        with source.open('rb') as reader, tmp.open('wb') as writer:
            while True:
                chunk = reader.read(COPY_CHUNK_BYTES)
                if not chunk:
                    break
                size += len(chunk)
                digest.update(chunk)
                writer.write(chunk)
            writer.flush()
            os.fsync(writer.fileno())
        if size != entry.size or digest.hexdigest() != entry.sha256:
            raise ValueError(f'{entry.label}: source has size {size} sha256 {digest.hexdigest()[:12]}, expected {entry.size} {entry.sha256[:12]}')
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()


def _hf_download(**kwargs) -> str:
    from huggingface_hub import hf_hub_download
    return hf_hub_download(**kwargs)


def install(hub: Path, manifest: weights.Manifest, *, from_hub: Path | None = None, download=_hf_download,
            hasher=weights.sha256_file, log=print) -> dict:
    """Installs every manifest file under `hub` (HF cache layout), sets refs/main and writes the stamp after a full verification."""
    hub = Path(hub)
    report = {'kept': 0, 'copied': 0, 'downloaded': 0, 'moved_aside': [], 'failures': []}
    for entry in manifest.entries:
        target = weights.file_path(hub, entry)
        if target.is_file():
            if target.stat().st_size == entry.size and hasher(target) == (entry.size, entry.sha256):
                report['kept'] += 1
                continue
            aside = target.with_name(f'{target.name}.mismatch-{time.strftime("%Y%m%dT%H%M%S")}')
            os.replace(target, aside)
            report['moved_aside'].append(str(aside))
        source = weights.file_path(Path(from_hub), entry) if from_hub else None
        if source is not None and source.is_file():
            try:
                _copy_verified(source, target, entry)
            except (OSError, ValueError) as error:
                report['failures'].append(str(error))
                continue
            report['copied'] += 1
            log(f'đã chép {entry.label}')
            continue
        if download is None:
            report['failures'].append(f'{entry.label}: không có trong --from-hub và việc tải đang tắt')
            continue
        try:
            path = Path(download(repo_id=entry.repo, filename=entry.path, revision=entry.revision, cache_dir=str(hub)))
            got = hasher(path)
        except Exception as error:  # network, licence gate, disk
            report['failures'].append(f'{entry.label}: tải không được ({type(error).__name__}: {error})')
            continue
        if got != (entry.size, entry.sha256):
            report['failures'].append(f'{entry.label}: bản tải có size {got[0]} sha256 {got[1][:12]}, cần {entry.size} {entry.sha256[:12]}')
            continue
        report['downloaded'] += 1
        log(f'đã tải {entry.label}')
    for repo, revision in sorted(manifest.revisions.items()):
        weights.atomic_write_text(weights.repo_dir(hub, repo) / 'refs' / 'main', revision)
    result = weights.verify(hub, manifest, full=True, hasher=hasher)
    report.update(ok=result.ok and not report['failures'], problems=result.problems(), stamp_written=result.stamp_written)
    return report


def main(argv=None) -> int:
    protocol.utf8_stdio()
    parser = argparse.ArgumentParser(prog='provision', description='Cài trọng số ghim của sidecar sinh ảnh vào cache HF ngoài Git.')
    parser.add_argument('--hub', required=True, help='<data>/models/hf-hub')
    parser.add_argument('--from-hub', help='cache HF có sẵn để chép (ví dụ D:/AIAVC_IMGPROTO/hub)')
    parser.add_argument('--no-download', action='store_true', help='không tải; chỉ chép từ --from-hub')
    parser.add_argument('--manifest', default=str(Path(__file__).resolve().with_name(weights.MANIFEST_NAME)))
    args = parser.parse_args(argv)
    manifest = weights.load_manifest(Path(args.manifest))
    report = install(Path(args.hub), manifest, from_hub=Path(args.from_hub) if args.from_hub else None,
                     download=None if args.no_download else _hf_download)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
