"""ADAPT-F: ffprobe adapter of OutputProbePort (CT-QC-001).

probe runs ffprobe with -print_format json on the output file (argument list, no command string) and fills OutputMeasurements only from what ffprobe reports.
A field ffprobe does not report stays None: no guess, no default, no fallback to another field (fps comes from avg_frame_rate only).
audio_level and severe_audio_errors are measured only when ffmpeg_path (the pinned ffmpeg) is given: astats (run first, on float samples, because the pinned astats prints the NaN/Inf counts only for float) gives the NaN/Inf sample counts and volumedetect the mean level in dB of the first audio stream; without ffmpeg_path, without an audio stream or when the run fails they stay None (never guessed, never a default).
A missing file, a missing or timed-out ffprobe and unparsable output measure nothing (all None); a file ffprobe rejects (non-zero exit) or that has no video stream is decodable=False.
container is 'mp4' for the mov/mp4 demuxer family unless major_brand is qt; any other multi-name format_name is None.

coveredIds: CT-QC-001
"""
from __future__ import annotations

import dataclasses
import json
import re
import subprocess
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path

from render.adapters.real_ffmpeg_renderer import DEFAULT_LOCK_PATH, verify_ffmpeg_pin
from render.ports.output_probe import OutputMeasurements

DEFAULT_FFPROBE_PATH = 'C:/ffmpeg/bin/ffprobe.exe'
DEFAULT_TIMEOUT_SECONDS = 60
SILENCE_FLOOR_DB = -120.0
ERROR_NAN_SAMPLES = 'nan_samples'
ERROR_INF_SAMPLES = 'inf_samples'
_DB = r'(-inf|-?\d+(?:\.\d+)?)'
_MEAN_VOLUME_RE = re.compile(r'mean_volume:\s*' + _DB + r'\s*dB')
_NAN_RE = re.compile(r'Number of NaNs:\s*(\d+(?:\.\d+)?)')
_INF_RE = re.compile(r'Number of Infs:\s*(\d+(?:\.\d+)?)')
_LUFS_RE = re.compile(r'\bI:\s*' + _DB + r'\s*LUFS')
_PEAK_RE = re.compile(r'\bPeak:\s*' + _DB + r'\s*dBFS')


def _streams(data: Mapping, codec_type: str) -> list[Mapping]:
    streams = data.get('streams')
    if not isinstance(streams, list):
        return []
    return [item for item in streams if isinstance(item, Mapping) and item.get('codec_type') == codec_type]


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip() or None


def _positive_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _duration_ms(fmt: Mapping) -> int | None:
    raw = fmt.get('duration')
    if not isinstance(raw, str):
        return None
    try:
        seconds = Decimal(raw)
    except InvalidOperation:
        return None
    if not seconds.is_finite() or seconds < 0:
        return None
    return int((seconds * 1000).to_integral_value())


def _fps(video: Mapping) -> float | None:
    raw = video.get('avg_frame_rate')
    if not isinstance(raw, str):
        return None
    try:
        rate = Fraction(raw)
    except (ValueError, ZeroDivisionError):
        return None
    return float(rate) if rate > 0 else None


def _container(fmt: Mapping) -> str | None:
    names = _text(fmt.get('format_name'))
    if names is None:
        return None
    tokens = [token.strip() for token in names.split(',') if token.strip()]
    tags = fmt.get('tags')
    brand = tags.get('major_brand') if isinstance(tags, Mapping) else None
    if 'mp4' in tokens and not (isinstance(brand, str) and brand.strip() == 'qt'):
        return 'mp4'
    return tokens[0] if len(tokens) == 1 else None


def measurements_from_ffprobe(data: object) -> OutputMeasurements:
    """Map the JSON of ffprobe -show_format -show_streams to OutputMeasurements; every unreported field stays None."""
    if not isinstance(data, Mapping):
        return OutputMeasurements()
    fmt = data.get('format') if isinstance(data.get('format'), Mapping) else {}
    listed = isinstance(data.get('streams'), list)
    videos, audios = _streams(data, 'video'), _streams(data, 'audio')
    video = videos[0] if videos else {}
    audio = audios[0] if audios else {}
    return OutputMeasurements(
        decodable=bool(videos) if listed else None,
        duration_ms=_duration_ms(fmt),
        width=_positive_int(video.get('width')),
        height=_positive_int(video.get('height')),
        fps=_fps(video),
        video_codec=_text(video.get('codec_name')),
        audio_codec=_text(audio.get('codec_name')),
        container=_container(fmt),
        has_audio_stream=bool(audios) if listed else None,
    )


@dataclasses.dataclass(frozen=True, kw_only=True)
class AudioStats:
    level_db: float | None = None
    severe_errors: tuple[str, ...] | None = None


@dataclasses.dataclass(frozen=True, kw_only=True)
class LoudnessStats:
    integrated_lufs: float | None = None
    true_peak_dbtp: float | None = None


def _db(token: str) -> float:
    return SILENCE_FLOOR_DB if token == '-inf' else float(token)


def _run_ffmpeg(ffmpeg: Path, args: Sequence[str], timeout_seconds: float) -> str | None:
    command = [str(ffmpeg), '-hide_banner', '-nostdin', '-nostats', '-v', 'info', *args]
    try:
        done = subprocess.run(
            command, capture_output=True, stdin=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace',
            timeout=timeout_seconds, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if done.returncode != 0:
        return None
    return done.stdout + chr(10) + done.stderr


def _select_windows(windows: Sequence[tuple[int, int]]) -> str:
    if not windows:
        return ''
    terms = '+'.join(f'between(t,{start / 1000:.3f},{end / 1000:.3f})' for start, end in windows)
    return 'aselect=' + chr(39) + terms + chr(39) + ',asetpts=N/SR/TB,'


def measure_audio(ffmpeg: Path, media: Path, *, windows: Sequence[tuple[int, int]] = (), timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> AudioStats:
    """Mean level (volumedetect) and NaN/Inf sample errors (astats) of the first audio stream, limited to windows (ms ranges) when given; the caller verifies the ffmpeg pin first. A failed run or a missing figure stays None. The graph is aformat=fltp,astats,volumedetect: astats must see float samples to print its NaN/Inf counts."""
    graph = _select_windows(windows) + 'aformat=sample_fmts=fltp,astats,volumedetect'
    text = _run_ffmpeg(ffmpeg, ['-i', str(media), '-map', '0:a:0', '-vn', '-af', graph, '-f', 'null', '-'], timeout_seconds)
    if text is None:
        return AudioStats()
    mean = _MEAN_VOLUME_RE.search(text)
    nans, infs = _NAN_RE.findall(text), _INF_RE.findall(text)
    errors = None
    if nans and infs:
        found = ((ERROR_NAN_SAMPLES, nans), (ERROR_INF_SAMPLES, infs))
        errors = tuple(code for code, counts in found if any(float(item) > 0 for item in counts))
    return AudioStats(level_db=_db(mean.group(1)) if mean else None, severe_errors=errors)


def measure_loudness(ffmpeg: Path, media: Path, *, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> LoudnessStats:
    """Integrated loudness (LUFS) and true peak (dBTP) from the ebur128 summary; only recorded, never a gate."""
    text = _run_ffmpeg(ffmpeg, ['-i', str(media), '-map', '0:a:0', '-vn', '-af', 'ebur128=peak=true:framelog=quiet', '-f', 'null', '-'], timeout_seconds)
    if text is None or 'Summary:' not in text:
        return LoudnessStats()
    summary = text.rsplit('Summary:', 1)[1]
    lufs, peak = _LUFS_RE.search(summary), _PEAK_RE.search(summary)
    return LoudnessStats(integrated_lufs=_db(lufs.group(1)) if lufs else None, true_peak_dbtp=_db(peak.group(1)) if peak else None)


class RealFfprobeProbe:
    """OutputProbePort over ffprobe; read-only, never modifies the output. ffmpeg_path (the pinned ffmpeg, verified against lock_path before anything runs) turns on the audio measurement; voice_windows (ms ranges of speech) limits audio_level to those ranges, empty means the whole stream. command_prefix is for tests only."""

    def __init__(
        self, *, ffprobe_path: str = DEFAULT_FFPROBE_PATH, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        command_prefix: Sequence[str] = (), ffmpeg_path: str | Path | None = None,
        lock_path: str | Path = DEFAULT_LOCK_PATH, voice_windows: Sequence[tuple[int, int]] = (),
    ) -> None:
        self._ffprobe = ffprobe_path
        self._timeout = timeout_seconds
        self._prefix = tuple(command_prefix)
        self._ffmpeg = None if ffmpeg_path is None else Path(ffmpeg_path)
        self._lock = Path(lock_path)
        self._windows = tuple((int(start), int(end)) for start, end in voice_windows)

    def probe(self, output_ref: str) -> OutputMeasurements:
        if self._ffmpeg is not None:
            verify_ffmpeg_pin(self._ffmpeg, self._lock)
        path = Path(output_ref)
        if not path.is_file():
            return OutputMeasurements()
        command = [
            *self._prefix, self._ffprobe, '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams', '-i', str(path),
        ]
        try:
            done = subprocess.run(
                command, capture_output=True, stdin=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace',
                timeout=self._timeout, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return OutputMeasurements()
        if done.returncode != 0:
            return OutputMeasurements(decodable=False)
        try:
            data = json.loads(done.stdout)
        except ValueError:
            return OutputMeasurements()
        measured = measurements_from_ffprobe(data)
        if self._ffmpeg is None or measured.has_audio_stream is not True:
            return measured
        stats = measure_audio(self._ffmpeg, path, windows=self._windows, timeout_seconds=self._timeout)
        return dataclasses.replace(measured, audio_level=stats.level_db, severe_audio_errors=stats.severe_errors)


__all__ = ['SILENCE_FLOOR_DB', 'AudioStats', 'LoudnessStats', 'RealFfprobeProbe', 'measure_audio', 'measure_loudness', 'measurements_from_ffprobe']
