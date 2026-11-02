"""Provisioning tool for FLUX 3 Image Klein weights cache."""

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import sys
import time

import protocol
import weights


def provision(hub, manifest, from_hub=None, download=True, hf_download=None, clock=time.time):
    hub_path = pathlib.Path(hub)
    report = {
        'copied': [],
        'downloaded': [],
        'skipped': [],
        'mismatched': [],
        'missing': [],
    }

    for item in manifest.get('files', []):
        repo = item['repo']
        revision = item['revision']
        rel_path = item['path']
        expected_size = item['size']
        expected_sha256 = item['sha256']
        target = weights.file_path(hub_path, repo, revision, rel_path)

        if target.exists():
            if target.stat().st_size == expected_size and weights.sha256_file(target) == expected_sha256:
                report['skipped'].append(rel_path)
                continue
            else:
                mismatch_name = f"{target.name}.mismatch-{int(clock())}"
                target.rename(target.with_name(mismatch_name))

        copied = False
        if from_hub is not None:
            source = weights.file_path(pathlib.Path(from_hub), repo, revision, rel_path)
            if source.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                part_target = target.with_name(target.name + '.part')
                h = hashlib.sha256()
                with open(source, 'rb') as sf, open(part_target, 'wb') as df:
                    while chunk := sf.read(1048576):
                        df.write(chunk)
                        h.update(chunk)
                if h.hexdigest() == expected_sha256:
                    os.replace(part_target, target)
                    report['copied'].append(rel_path)
                    copied = True
                else:
                    if part_target.exists():
                        part_target.unlink()
                    report['mismatched'].append(rel_path)
                    continue

        if copied:
            continue

        if download:
            if hf_download is not None:
                hf_download(repo_id=repo, filename=rel_path, revision=revision, cache_dir=str(hub_path))
                report['downloaded'].append(rel_path)
            else:
                try:
                    from huggingface_hub import hf_hub_download
                    hf_hub_download(repo_id=repo, filename=rel_path, revision=revision, cache_dir=str(hub_path))
                    report['downloaded'].append(rel_path)
                except Exception:
                    report['missing'].append(rel_path)
        else:
            report['missing'].append(rel_path)

    for repo, rinfo in manifest.get('repos', {}).items():
        revision = rinfo['revision']
        r_dir = weights.repo_dir(hub_path, repo)
        refs_dir = r_dir / 'refs'
        refs_dir.mkdir(parents=True, exist_ok=True)
        (refs_dir / 'main').write_text(revision, encoding='utf-8')

    if not report['mismatched'] and not report['missing']:
        weights.write_stamp(hub_path, manifest)

    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Provision FLUX 3 Image Klein weights")
    parser.add_argument("--hub", default=str(weights.default_hub()))
    parser.add_argument("--from-hub", default=None)
    parser.add_argument("--no-download", action="store_true")
    parser.add_argument("--manifest", default=None)

    args = parser.parse_args(argv)
    protocol.utf8_stdio()
    manifest = weights.load_manifest(args.manifest)
    res = provision(
        hub=args.hub,
        manifest=manifest,
        from_hub=args.from_hub,
        download=not args.no_download,
    )
    print(json.dumps(res, indent=2))
    if res['missing'] or res['mismatched']:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
