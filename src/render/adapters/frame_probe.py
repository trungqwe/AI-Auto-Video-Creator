"""PW-F1: frame measurements over the pinned ffmpeg (one sample frame against itself after the staged ASS is drawn again, and media duration); read-only, never writes a file.

coveredIds: PW-F1-01, CT-QC-001
"""
import re
import string
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TIMEOUT_SECONDS = 60
SEEK_LEAD_MS = 1000
_YAVG_RE = re.compile(r'lavfi\.signalstats\.YAVG=([0-9]+(?:\.[0-9]+)?)')
_DURATION_RE = re.compile(r'Duration:\s*(\d+):(\d{2}):(\d{2})\.(\d{2})')
_BACKSLASH = chr(92)
_FILTER_PATH_CHARS = frozenset(string.ascii_letters + string.digits + '_-./:' + _BACKSLASH)


def seek_arg(ms: int) -> str:
    return f'{ms / 1000:.3f}'


@dataclass(frozen=True)
class OverlayDifference:
    residual: float
    ink: float


def subtitles_filter_path(path: str | Path) -> str | None:
    text = str(path)
    if not text or not all(ch in _FILTER_PATH_CHARS for ch in text):
        return None
    return text.replace(_BACKSLASH, '/').replace(':', _BACKSLASH * 2 + ':')


class FrameProbe:
    def __init__(self, *, ffmpeg_path: str | Path, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._ffmpeg = Path(ffmpeg_path)
        self._timeout = timeout_seconds

    def _run(self, args: Sequence[str]) -> tuple[int, str] | None:
        argv = [str(self._ffmpeg), '-hide_banner', '-nostdin', '-v', 'info', *args]
        try:
            res = subprocess.run(
                argv,
                capture_output=True,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=self._timeout,
                check=False,
            )
            return (res.returncode, res.stdout + chr(10) + res.stderr)
        except (OSError, subprocess.TimeoutExpired):
            return None

    def duration_ms(self, media: Path) -> int | None:
        res = self._run(['-i', str(media)])
        if res is None:
            return None
        m = _DURATION_RE.search(res[1])
        if not m:
            return None
        h, m_, s, cs = (int(x) for x in m.groups())
        return ((h * 60 + m_) * 60 + s) * 1000 + cs * 10

    def _band_yavg(self, media: Path, *, sample_ms: int, subtitles: str, top: float, bottom: float, gray: bool) -> float | None:
        y = f'trunc(ih*{top:.6f}/2)*2'
        h = f'trunc(ih*{bottom:.6f}/2)*2-{y}'
        frame = f"select='gte(t,{sample_ms / 1000:.3f})',trim=end_frame=1,format=yuv420p"
        if gray:
            frame += ',drawbox=x=0:y=0:w=iw:h=ih:color=gray:t=fill'
        graph = (
            f'[0:v]{frame},split=2[a][b];[b]subtitles=filename={subtitles}[s];'
            f'[a][s]blend=all_mode=difference,crop=w=iw:h={h}:x=0:y={y},signalstats,'
            'metadata=mode=print:key=lavfi.signalstats.YAVG'
        )
        args = ['-copyts', '-ss', seek_arg(max(0, sample_ms - SEEK_LEAD_MS)), '-i', str(media), '-an', '-filter_complex', graph, '-frames:v', '1', '-f', 'null', '-']
        res = self._run(args)
        if res is None or res[0] != 0:
            return None
        m = _YAVG_RE.search(res[1])
        return float(m.group(1)) if m else None

    def overlay_difference(self, media: Path, *, sample_ms: int, subtitles_path: str | Path, top: float, bottom: float) -> OverlayDifference | None:
        subtitles = subtitles_filter_path(subtitles_path)
        if subtitles is None or sample_ms < 0 or not 0 <= top < bottom <= 1:
            return None
        common = {'sample_ms': sample_ms, 'subtitles': subtitles, 'top': top, 'bottom': bottom}
        residual = self._band_yavg(media, gray=False, **common)
        if residual is None:
            return None
        ink = self._band_yavg(media, gray=True, **common)
        return None if ink is None else OverlayDifference(residual=residual, ink=ink)


__all__ = ['FrameProbe', 'OverlayDifference', 'seek_arg', 'subtitles_filter_path']
