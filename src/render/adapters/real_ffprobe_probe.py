"""ADAPT-F: ffprobe adapter of OutputProbePort (CT-QC-001).

probe runs ffprobe with -print_format json on the output file (argument list, no command string) and fills OutputMeasurements only from what ffprobe reports.
A field ffprobe does not report stays None: no guess, no default, no fallback to another field (fps comes from avg_frame_rate only).
audio_level and severe_audio_errors are not measured here and stay None.
A missing file, a missing or timed-out ffprobe and unparsable output measure nothing (all None); a file ffprobe rejects (non-zero exit) or that has no video stream is decodable=False.
container is 'mp4' for the mov/mp4 demuxer family unless major_brand is qt; any other multi-name format_name is None.

coveredIds: CT-QC-001
"""
from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path

from render.ports.output_probe import OutputMeasurements

DEFAULT_FFPROBE_PATH = 'C:/ffmpeg/bin/ffprobe.exe'
DEFAULT_TIMEOUT_SECONDS = 60


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


class RealFfprobeProbe:
    """OutputProbePort over ffprobe; read-only, never modifies the output. command_prefix is for tests only."""

    def __init__(
        self, *, ffprobe_path: str = DEFAULT_FFPROBE_PATH, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        command_prefix: Sequence[str] = (),
    ) -> None:
        self._ffprobe = ffprobe_path
        self._timeout = timeout_seconds
        self._prefix = tuple(command_prefix)

    def probe(self, output_ref: str) -> OutputMeasurements:
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
        return measurements_from_ffprobe(data)


__all__ = ['RealFfprobeProbe', 'measurements_from_ffprobe']
