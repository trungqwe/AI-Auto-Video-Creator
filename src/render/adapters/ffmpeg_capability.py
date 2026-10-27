"""PW-F2: ToolCapability read from the pinned ffmpeg (filters, encoders and the libraries of the build); read-only.

The pin of tools/runtime/runtime.lock.json is verified before any run (FfmpegPinRejected otherwise). Every name comes only from what
ffmpeg prints for -filters, -encoders and -buildconf; there is no fixed list of filters or encoders. The pinned build prints two flag columns for -filters (T timeline, S slice threading); the legend lines never match because their name token is an equals sign. A listing that cannot be read
gives None, which check_preset_tool_compat reports as INPUT_NOT_READY. ToolCapability has only filters and encoders, so the
libraries of the build (--enable-libass gives 'libass') are added to filters: a preset that needs libass lists it in required_filters.

coveredIds: PW-F2-01, CT-QC-001
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from render.adapters.real_ffmpeg_renderer import DEFAULT_FFMPEG_PATH, DEFAULT_LOCK_PATH, verify_ffmpeg_pin
from render.domain.preconditions_artifacts import ToolCapability

DEFAULT_TIMEOUT_SECONDS = 30
_FILTER_RE = re.compile(r'^\s+[T.][S.]\s+([A-Za-z0-9_]+)\s+\S*->\S*\s', re.MULTILINE)
_ENCODER_RE = re.compile(r'^\s+[VAS][.FSXBD]{5}\s+([A-Za-z0-9_]+)\s', re.MULTILINE)
_ENABLE_RE = re.compile(r'--enable-([A-Za-z0-9_-]+)')


def parse_filters(text: str) -> frozenset[str]:
    return frozenset(_FILTER_RE.findall(text))


def parse_encoders(text: str) -> frozenset[str]:
    return frozenset(_ENCODER_RE.findall(text))


def parse_libraries(text: str) -> frozenset[str]:
    return frozenset(name for name in _ENABLE_RE.findall(text) if name.startswith('lib'))


def _listing(ffmpeg: Path, flag: str, timeout_seconds: float) -> str | None:
    try:
        done = subprocess.run(
            [str(ffmpeg), '-hide_banner', '-nostdin', flag], capture_output=True, stdin=subprocess.DEVNULL, text=True,
            encoding='utf-8', errors='replace', timeout=timeout_seconds, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout + chr(10) + done.stderr if done.returncode == 0 else None


def read_tool_capability(
    *, ffmpeg_path: str | Path = DEFAULT_FFMPEG_PATH, lock_path: str | Path = DEFAULT_LOCK_PATH,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> ToolCapability | None:
    ffmpeg = Path(ffmpeg_path)
    verify_ffmpeg_pin(ffmpeg, Path(lock_path))
    filters_text = _listing(ffmpeg, '-filters', timeout_seconds)
    encoders_text = _listing(ffmpeg, '-encoders', timeout_seconds)
    build_text = _listing(ffmpeg, '-buildconf', timeout_seconds)
    if filters_text is None or encoders_text is None or build_text is None:
        return None
    filters, encoders = parse_filters(filters_text), parse_encoders(encoders_text)
    if not filters or not encoders:
        return None
    return ToolCapability(filters=(filters | parse_libraries(build_text)) - encoders, encoders=encoders)


__all__ = ['parse_encoders', 'parse_filters', 'parse_libraries', 'read_tool_capability']
