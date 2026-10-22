from __future__ import annotations

'''ADAPT-SEED: sinh media seed tự tạo vào thư mục dữ liệu ngoài cây Git (plan.md mục 7.8): PNG bằng zlib, WAV bằng wave, MP4 bằng ffmpeg đã ghim sha256 với nguồn lavfi.'''

import argparse
import colorsys
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import wave
import zlib

PROD_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
HOOKS_JSON = PROD_DIR / 'hooks.json'
RUNTIME_LOCK = REPO_ROOT / 'tools' / 'runtime' / 'runtime.lock.json'
DEFAULT_FFMPEG = Path('C:/ffmpeg/bin/ffmpeg.exe')
MANIFEST_NAME = 'seed-manifest.json'
FFMPEG_TIMEOUT_SECONDS = 180
DETERMINISM_ARGS = ['-threads', '1', '-fflags', '+bitexact', '-flags:v', '+bitexact', '-map_metadata', '-1']


class SeedError(ValueError):
    pass


def _inside_git_tree(path):
    resolved = Path(path).resolve()
    if resolved == REPO_ROOT or REPO_ROOT in resolved.parents:
        return True
    return any((parent / '.git').exists() for parent in (resolved, *resolved.parents))


def ensure_outside_git(path):
    resolved = Path(path).resolve()
    if _inside_git_tree(resolved):
        raise SeedError('seed dir must be outside the Git tree')
    return resolved


def resolve_seed_dir(base_dir=None):
    '''Thư mục seed = <gốc dữ liệu>/<storage.subdir của hooks.json>; gốc mặc định LOCALAPPDATA/AIAutoVideoCreator.'''
    hooks = json.loads(HOOKS_JSON.read_text(encoding='utf-8'))
    if base_dir is None:
        local = os.environ.get('LOCALAPPDATA')
        if not local:
            raise SeedError('LOCALAPPDATA is not set')
        base_dir = Path(local) / 'AIAutoVideoCreator'
    return ensure_outside_git(Path(base_dir) / hooks['storage']['subdir'])


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


PNG_SIGNATURE = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
ENVELOPES = {
    'linear_fade_out': lambda t, d: 1 - t / d,
    'linear_fade_in': lambda t, d: t / d,
    'triangle': lambda t, d: 1 - abs(2 * t / d - 1),
    'exponential_decay': lambda t, d: math.exp(-3 * t / d),
    'hann': lambda t, d: 0.5 - 0.5 * math.cos(2 * math.pi * t / d),
}


def _rgb(hue_degrees, hsv):
    red, green, blue = colorsys.hsv_to_rgb((hue_degrees % 360) / 360, hsv['s'], hsv['v'])
    return (red * 255, green * 255, blue * 255)


def _chunk(tag, data):
    body = tag + data
    return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body) & 0xFFFFFFFF)


def make_png(width, height, hue_degrees, template):
    if template['method'] != 'vertical_gradient' or template['bit_depth'] != 8 or template['color_type'] != 'rgb':
        raise SeedError('unsupported background template')
    top = _rgb(hue_degrees, template['top_hsv'])
    bottom = _rgb(hue_degrees, template['bottom_hsv'])
    rows = bytearray()
    for y in range(height):
        ratio = y / (height - 1)
        pixel = bytes(round(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3))
        rows += bytes(1) + pixel * width
    header = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    return PNG_SIGNATURE + _chunk(b'IHDR', header) + _chunk(b'IDAT', zlib.compress(bytes(rows), 9)) + _chunk(b'IEND', b'')


def make_wav(path, envelope, template):
    if envelope not in ENVELOPES or envelope not in template['envelopes']:
        raise SeedError('unknown envelope')
    rate = template['sample_rate_hz']
    duration = template['duration_s']
    shape = ENVELOPES[envelope]
    samples = bytearray()
    for n in range(round(rate * duration)):
        t = n / rate
        sweep = math.sin(2 * math.pi * (220 * t + (880 - 220) * t * t / (2 * duration)))
        samples += struct.pack('<h', round(32767 * 0.5 * shape(t, duration) * sweep))
    with wave.open(str(path), 'wb') as handle:
        handle.setnchannels(template['channels'])
        handle.setsampwidth(template['sample_width_bits'] // 8)
        handle.setframerate(rate)
        handle.writeframes(bytes(samples))


def verify_ffmpeg_pin(ffmpeg_path, runtime_lock_path):
    pin = json.loads(Path(runtime_lock_path).read_text(encoding='utf-8'))['pins']['ffmpeg']
    if pin.get('status') != 'PINNED' or not isinstance(pin.get('sha256'), str):
        raise SeedError('ffmpeg pin is not PINNED in runtime.lock.json')
    if not Path(ffmpeg_path).is_file():
        raise SeedError('ffmpeg binary not found')
    if file_sha256(ffmpeg_path) != pin['sha256']:
        raise SeedError('ffmpeg sha256 does not match runtime.lock.json')


def make_video(ffmpeg_path, path, recipe, template):
    if template['input'] != 'lavfi':
        raise SeedError('visual hooks must use the lavfi source')
    graph = template['filtergraph'].format(c0=recipe['c0'], c1=recipe['c1'], hz=recipe['hz'], amp=recipe['amp'])
    if 'gradients=' in graph and ':seed=' not in graph and 'seed=' not in graph:
        graph = graph.replace('gradients=', 'gradients=seed=1:')
    command = [str(ffmpeg_path), '-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', graph]
    command += template['output_args'].split() + DETERMINISM_ARGS + [str(path)]
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=FFMPEG_TIMEOUT_SECONDS, check=False, shell=False, stdin=subprocess.DEVNULL)
    if result.returncode != 0:
        raise SeedError('ffmpeg exit ' + str(result.returncode) + ': ' + result.stderr.strip()[:300])


def _plain_name(name):
    if Path(name).name != name or name in ('', '.', '..'):
        raise SeedError('file_name must not contain a path')
    return name


def generate_seed_media(out_dir, ffmpeg_path=DEFAULT_FFMPEG, *, hooks_path=HOOKS_JSON, runtime_lock_path=RUNTIME_LOCK, emit=print):
    '''Sinh 22 tệp seed vào out_dir (ngoài cây Git); trả về {file_name: sha256} và gọi emit("<sha256>  <file_name>") cho từng tệp.'''
    target = ensure_outside_git(Path(out_dir))
    hooks = json.loads(Path(hooks_path).read_text(encoding='utf-8'))
    templates = hooks['recipe_templates']
    verify_ffmpeg_pin(ffmpeg_path, runtime_lock_path)
    target.mkdir(parents=True, exist_ok=True)
    shas = {}
    manifest = {}
    for group in ('visual_hooks', 'audio_hooks', 'background_images'):
        for item in hooks[group]:
            name = _plain_name(item['file_name'])
            recipe = item['recipe']
            template = templates[recipe['template']]
            path = target / name
            if group == 'visual_hooks':
                make_video(ffmpeg_path, path, recipe, template)
            elif group == 'audio_hooks':
                make_wav(path, recipe['envelope'], template)
            else:
                path.write_bytes(make_png(item['width'], item['height'], recipe['hue_degrees'], template))
            sha = file_sha256(path)
            declared = item.get('sha256')
            if declared is not None and declared != sha:
                raise SeedError('sha256 of ' + name + ' differs from hooks.json')
            shas[name] = sha
            manifest[item['id']] = {'file_name': name, 'kind': item['kind'], 'sha256': sha, 'size_bytes': path.stat().st_size}
            emit(sha + '  ' + name)
    (target / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return shas


def main(argv=None):
    parser = argparse.ArgumentParser(description='Sinh media seed tự tạo cho ADAPT-SEED (ngoài cây Git).')
    parser.add_argument('--base-dir', default=None, help='Gốc dữ liệu; mặc định LOCALAPPDATA/AIAutoVideoCreator')
    parser.add_argument('--ffmpeg', default=str(DEFAULT_FFMPEG), help='Đường dẫn tuyệt đối ffmpeg.exe đã ghim')
    args = parser.parse_args(argv)
    try:
        generate_seed_media(resolve_seed_dir(args.base_dir), Path(args.ffmpeg))
    except SeedError as exc:
        print('SEED_ERROR: ' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
