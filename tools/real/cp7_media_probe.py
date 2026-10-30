"""CP7-8: đo media bằng ffprobe, loudnorm, silencedetect, signalstats của FFmpeg đã ghim (chỉ stdlib)."""
from __future__ import annotations

from fractions import Fraction
from pathlib import Path
import hashlib
import json
import math
import re
import subprocess

FFMPEG_PIN_SHA256 = 'f845a09b5467cf11651385e0be0dd4df6f70519264f8af2115e3acd6ab7f9480'
DEFAULT_FFMPEG = Path('C:/ffmpeg/bin/ffmpeg.exe')
DEFAULT_FFPROBE = Path('C:/ffmpeg/bin/ffprobe.exe')
LOCK_PATH = Path(__file__).resolve().parents[2] / 'tools' / 'runtime' / 'runtime.lock.json'


class PinMismatch(RuntimeError):
    pass


class ProbeError(RuntimeError):
    pass


class ChildKilled(TimeoutError):
    pid: int | None = None


_VERIFIED: dict[tuple[str, int, int], str] = {}


def sha256_file(path: str | Path) -> str:
    p = Path(path)
    digest = hashlib.sha256()
    with p.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify_pin(ffmpeg: str | Path = DEFAULT_FFMPEG, lock_path: str | Path = LOCK_PATH) -> str:
    p = Path(ffmpeg)
    if not p.is_file():
        raise PinMismatch('ffmpeg_sha256_mismatch')
    st = p.stat()
    key = (str(p), st.st_mtime_ns, st.st_size)
    if key in _VERIFIED:
        return _VERIFIED[key]
    lock_data = json.loads(Path(lock_path).read_text(encoding='utf-8'))
    pin_status = lock_data.get('pins', {}).get('ffmpeg', {}).get('status')
    pin_sha = lock_data.get('pins', {}).get('ffmpeg', {}).get('sha256')
    if pin_status != 'PINNED':
        raise PinMismatch('ffmpeg_sha256_mismatch')
    actual = sha256_file(p)
    if actual != FFMPEG_PIN_SHA256 or actual != pin_sha:
        raise PinMismatch('ffmpeg_sha256_mismatch')
    _VERIFIED[key] = actual
    return actual


def run_ffmpeg(args: list[str], *, timeout: float, ffmpeg: str | Path = DEFAULT_FFMPEG, lock_path: str | Path = LOCK_PATH) -> subprocess.CompletedProcess[str]:
    verify_pin(ffmpeg=ffmpeg, lock_path=lock_path)
    return subprocess.run(
        [str(ffmpeg), '-hide_banner', '-nostdin', '-nostats', *args],
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=timeout,
        check=False,
    )


def ffprobe_json(media: str | Path, *, timeout: float = 60, ffprobe: str | Path = DEFAULT_FFPROBE) -> tuple[int, dict | None]:
    proc = subprocess.run(
        [str(ffprobe), '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams', '-i', str(media)],
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        return proc.returncode, None
    try:
        data = json.loads(proc.stdout)
        return proc.returncode, data
    except Exception:
        return proc.returncode, None


def media_facts(data: dict | None) -> dict:
    keys = ['width', 'height', 'fps', 'video_codec', 'audio_codec', 'audio_rate', 'audio_channels', 'format_names', 'duration_s', 'size_bytes']
    if not data or not isinstance(data, dict):
        return {k: None for k in keys}

    video_stream = None
    audio_stream = None
    for stream in data.get('streams', []):
        codec_type = stream.get('codec_type')
        if codec_type == 'video' and video_stream is None:
            video_stream = stream
        elif codec_type == 'audio' and audio_stream is None:
            audio_stream = stream

    width = video_stream.get('width') if video_stream else None
    height = video_stream.get('height') if video_stream else None
    fps = None
    if video_stream:
        avg_rate = video_stream.get('avg_frame_rate')
        if avg_rate:
            try:
                frac = Fraction(avg_rate)
                if frac != 0:
                    fps = float(frac)
            except Exception:
                fps = None

    video_codec = video_stream.get('codec_name') if video_stream else None
    audio_codec = audio_stream.get('codec_name') if audio_stream else None
    audio_rate = None
    if audio_stream and audio_stream.get('sample_rate') is not None:
        try:
            audio_rate = int(audio_stream['sample_rate'])
        except Exception:
            audio_rate = None
    audio_channels = audio_stream.get('channels') if audio_stream else None

    fmt = data.get('format', {})
    raw_fmt_names = fmt.get('format_name')
    format_names = [name.strip() for name in raw_fmt_names.split(',')] if raw_fmt_names else None

    duration_s = None
    if fmt.get('duration') is not None:
        try:
            duration_s = float(fmt['duration'])
        except Exception:
            duration_s = None

    size_bytes = None
    if fmt.get('size') is not None:
        try:
            size_bytes = int(fmt['size'])
        except Exception:
            size_bytes = None

    return {
        'width': width,
        'height': height,
        'fps': fps,
        'video_codec': video_codec,
        'audio_codec': audio_codec,
        'audio_rate': audio_rate,
        'audio_channels': audio_channels,
        'format_names': format_names,
        'duration_s': duration_s,
        'size_bytes': size_bytes,
    }


def decode_check(media: str | Path, *, timeout: float = 600) -> dict:
    proc = run_ffmpeg(['-v', 'error', '-i', str(media), '-f', 'null', '-'], timeout=timeout)
    err_lines = len([line for line in proc.stderr.splitlines() if line.strip()])
    return {
        'returncode': proc.returncode,
        'error_lines': err_lines,
        'playable': proc.returncode == 0 and err_lines == 0,
    }


def loudnorm(media: str | Path, *, timeout: float = 600) -> dict[str, float]:
    proc = run_ffmpeg(['-i', str(media), '-vn', '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-'], timeout=timeout)
    if proc.returncode != 0:
        raise ProbeError('loudnorm_failed')
    blocks = re.findall(r'\{[^{}]*"input_i"[^{}]*\}', proc.stderr, re.DOTALL)
    if not blocks:
        raise ProbeError('loudnorm_no_json')
    last_block = json.loads(blocks[-1])

    def _val(k: str) -> float:
        v = last_block.get(k)
        if v == '-inf':
            return float('-inf')
        return float(v)

    return {
        'input_i': _val('input_i'),
        'input_tp': _val('input_tp'),
        'input_lra': _val('input_lra'),
    }


def silence_intervals(media: str | Path, *, noise_db: float = -30.0, min_s: float = 0.1, timeout: float = 600) -> list[tuple[float, float]]:
    proc = run_ffmpeg(['-i', str(media), '-af', f'silencedetect=noise={noise_db}dB:d={min_s}', '-f', 'null', '-'], timeout=timeout)
    intervals: list[tuple[float, float]] = []
    cur_start: float | None = None
    for line in proc.stderr.splitlines():
        m_start = re.search(r'silence_start:\s*([0-9.-]+)', line)
        if m_start:
            cur_start = float(m_start.group(1))
        m_end = re.search(r'silence_end:\s*([0-9.-]+)', line)
        if m_end:
            end_s = float(m_end.group(1))
            if cur_start is not None:
                intervals.append((cur_start, end_s))
                cur_start = None
    if cur_start is not None:
        m_dur = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', proc.stderr)
        end_s = cur_start
        if m_dur:
            end_s = int(m_dur.group(1)) * 3600 + int(m_dur.group(2)) * 60 + float(m_dur.group(3))
        intervals.append((cur_start, end_s))
    return intervals


def signalstats_series(media: str | Path, key: str, *, fps: int = 5, timeout: float = 900) -> list[float]:
    proc = run_ffmpeg(['-i', str(media), '-an', '-vf', f'fps={fps},signalstats,metadata=mode=print:key=lavfi.signalstats.{key}', '-f', 'null', '-'], timeout=timeout)
    pattern = re.compile(rf'lavfi\.signalstats\.{re.escape(key)}=([0-9.-]+)')
    combined = proc.stdout + '\n' + proc.stderr
    return [float(m.group(1)) for m in pattern.finditer(combined)]


def visual_continuity(media: str | Path, *, fps: int = 5, max_ydif: float = 20.0, timeout: float = 900) -> dict:
    """Định nghĩa GIẢ ĐỊNH của slice (tỷ lệ cặp khung liên tiếp không nhảy cảnh) vì repo chưa có phép đo VISUAL_CONTINUITY."""
    series = signalstats_series(media, 'YDIF', fps=fps, timeout=timeout)
    if len(series) <= 1:
        raise ProbeError('no_frames')
    subsequent = series[1:]
    frames = len(subsequent)
    jumps = sum(1 for val in subsequent if val > max_ydif)
    continuity = 1.0 - (jumps / frames)
    return {'continuity': continuity, 'frames': frames, 'jumps': jumps}


def percentile_nearest_rank(values: list[float], fraction: float) -> float:
    if not values:
        raise ProbeError('empty')
    sorted_v = sorted(values)
    idx = max(0, math.ceil(fraction * len(sorted_v)) - 1)
    return sorted_v[idx]


def run_bounded(argv: list[str], *, timeout: float) -> tuple[int, str, str]:
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return proc.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
            proc.wait()
        except Exception:
            pass
        err = ChildKilled('child killed at deadline')
        err.pid = proc.pid
        raise err
    finally:
        if proc.poll() is None:
            try:
                proc.kill()
                proc.wait()
            except Exception:
                pass
