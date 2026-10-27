"""PW-F1: frame measurements over the pinned ffmpeg (signalstats band difference and media duration); read-only, never writes a file.

coveredIds: PW-F1-01, CT-QC-001
"""
import re
import subprocess
from collections.abc import Sequence
from pathlib import Path

DEFAULT_TIMEOUT_SECONDS = 60
_YAVG_RE = re.compile(r'lavfi\.signalstats\.YAVG=([0-9]+(?:\.[0-9]+)?)')
_DURATION_RE = re.compile(r'Duration:\s*(\d+):(\d{2}):(\d{2})\.(\d{2})')


def seek_arg(ms: int) -> str:
    return f'{ms / 1000:.3f}'


def band_pixels(height: int, top: float, bottom: float) -> tuple[int, int] | None:
    y = int(height * top) // 2 * 2
    end = int(height * bottom) // 2 * 2
    return (y, end - y) if end - y >= 2 else None


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

    def band_difference(
        self,
        media: Path,
        *,
        sample_ms: int,
        baseline_ms: int,
        width: int,
        height: int,
        top: float,
        bottom: float,
    ) -> float | None:
        band = band_pixels(height, top, bottom)
        if band is None:
            return None
        prep = f'scale={width}:{height},crop={width}:{band[1]}:0:{band[0]},setpts=PTS-STARTPTS'
        graph = f'[0:v]{prep}[a];[1:v]{prep}[b];[a][b]blend=all_mode=difference,signalstats,metadata=mode=print:key=lavfi.signalstats.YAVG'
        args = [
            '-ss',
            seek_arg(sample_ms),
            '-i',
            str(media),
            '-ss',
            seek_arg(baseline_ms),
            '-i',
            str(media),
            '-filter_complex',
            graph,
            '-frames:v',
            '1',
            '-f',
            'null',
            '-',
        ]
        res = self._run(args)
        if res is None or res[0] != 0:
            return None
        m = _YAVG_RE.search(res[1])
        if not m:
            return None
        return float(m.group(1))


__all__ = ['FrameProbe', 'band_pixels', 'seek_arg']
