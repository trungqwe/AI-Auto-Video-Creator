"""ADAPT-F: FFmpeg adapter of RendererPort and OutputObservationPort (CT-RND-004, CT-STATE-011).

run() executes one render RenderCommandSpec with subprocess.run and an argument list on the ffmpeg binary whose sha256 equals pins.ffmpeg.sha256 of tools/runtime/runtime.lock.json; a missing pin, a BLOCKED pin or a different hash is refused before anything runs.
Production profile (plan.md 7.4): 1080x1920 (scale increase then crop), 30 fps, h264_nvenc with one retry on libx264 when NVENC cannot start, AAC 192k 48 kHz stereo, MP4 +faststart, ASS burned in by the subtitles filter.
Each attempt writes a temporary file next to the output; only exit code 0 renames it atomically to output_ref (the output path of the spec), and an existing output is never overwritten.
LOCK-DESKTOP-GPU is taken through GpuLeasePort for the whole run and always returned. The encoder used is written to the metrics (gpu_metrics encoder_h264_nvenc or cpu_metrics encoder_libx264) and to last_encoder.
command_prefix exists for tests only (an interpreter that runs a fake ffmpeg script); the pin check always applies to ffmpeg_path.

coveredIds: CT-RND-004, CT-STATE-011
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
import time
import uuid
from collections.abc import Sequence
from pathlib import Path
from types import MappingProxyType

from render.domain.render_command import KIND_RENDER, RenderCommandSpec
from render.ports.lease import GpuLeasePort
from render.ports.renderer import OutputObservation, RendererMetrics, RendererOutcome, RendererStatus, RendererTimeout

ENCODER_NVENC = 'h264_nvenc'
ENCODER_LIBX264 = 'libx264'
DEFAULT_FFMPEG_PATH = 'C:/ffmpeg/bin/ffmpeg.exe'
DEFAULT_LOCK_PATH = Path(__file__).resolve().parents[3] / 'tools' / 'runtime' / 'runtime.lock.json'
DEFAULT_TIMEOUT_SECONDS = 900
ENCODER_ARGS = MappingProxyType({
    ENCODER_NVENC: (
        '-preset', 'p5', '-tune', 'hq', '-rc', 'vbr', '-cq', '23', '-b:v', '0', '-maxrate', '12M', '-bufsize', '24M',
        '-profile:v', 'high', '-pix_fmt', 'yuv420p', '-g', '60', '-bf', '2',
    ),
    ENCODER_LIBX264: ('-preset', 'medium', '-crf', '21', '-pix_fmt', 'yuv420p'),
})
AUDIO_ARGS = ('-b:a', '192k', '-ar', '48000', '-ac', '2')
MP4_ARGS = ('-movflags', '+faststart')
NVENC_FAILURE_MARKERS = ('nvenc', 'nvcuda', 'cuda', 'could not open encoder', 'error initializing output stream')
ERROR_TAIL_CHARS = 2000
CHUNK_BYTES = 1 << 20


REASON_UNSUPPORTED_KIND = 'unsupported_spec_kind'
REASON_UNSUPPORTED_ENCODER = 'unsupported_encoder'
REASON_SPEC_SHAPE = 'spec_shape_invalid'
REASON_EXECUTABLE = 'executable_not_pinned'
REASON_OUTPUT_EXISTS = 'output_already_exists'
REASON_NO_OUTPUT = 'output_missing_after_exit_0'


class FfmpegPinRejected(RuntimeError):
    """ffmpeg is not the pinned binary: pin missing or not PINNED, sha256 different or a file unreadable; nothing is run."""


class _SpecRejected(Exception):
    """The spec has a shape this adapter cannot run; the message is a static reason code."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(CHUNK_BYTES), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify_ffmpeg_pin(ffmpeg_path: Path, lock_path: Path) -> None:
    """Raise FfmpegPinRejected unless pins.ffmpeg of the lock is PINNED and its sha256 equals the sha256 of ffmpeg_path."""
    try:
        pin = json.loads(lock_path.read_text(encoding='utf-8'))['pins']['ffmpeg']
        status, expected = pin['status'], pin['sha256']
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise FfmpegPinRejected(f'ffmpeg_pin_unreadable: {type(error).__name__}') from None
    if status != 'PINNED' or not isinstance(expected, str) or len(expected) != 64:
        raise FfmpegPinRejected('ffmpeg_pin_not_pinned')
    try:
        actual = sha256_file(ffmpeg_path)
    except OSError as error:
        raise FfmpegPinRejected(f'ffmpeg_unreadable: {type(error).__name__}') from None
    if not hmac.compare_digest(actual, expected.lower()):
        raise FfmpegPinRejected('ffmpeg_sha256_mismatch')


def _rewrite_graph(graph: str) -> str:
    """The spec chain has scale and ass; production needs scale with increase plus crop, and the subtitles filter (libass)."""
    parts = []
    for part in graph.split(','):
        if part.startswith('scale='):
            parts += [f'{part}:force_original_aspect_ratio=increase', 'crop=' + part[len('scale='):]]
        elif part.startswith('ass='):
            parts.append('subtitles=' + part[len('ass='):])
        else:
            parts.append(part)
    return ','.join(parts)


def build_final_argv(spec_argv: Sequence[str], ffmpeg: str, encoder: str, temp_output: str) -> list[str]:
    """Argv of one attempt: ffmpeg and the temporary output replace the spec ones; encoder preset, audio, +faststart and the filter chain are set here."""
    args = list(spec_argv)
    if '-b:v' in args:
        index = args.index('-b:v')
        del args[index:index + 2]
    try:
        graph = args.index('-filter_complex') + 1
        video = args.index('-c:v') + 1
        audio = args.index('-c:a') + 1
        container = args.index('-f')
        args[graph] = _rewrite_graph(args[graph])
    except (ValueError, IndexError):
        raise _SpecRejected(REASON_SPEC_SHAPE) from None
    args[0], args[-1] = ffmpeg, temp_output
    # Applied from the highest position down; the sort is stable, so at an equal position the audio block lands before +faststart.
    edits = [(video, 1, [encoder, *ENCODER_ARGS[encoder]]), (container, 0, list(MP4_ARGS)), (audio + 1, 0, list(AUDIO_ARGS))]
    for position, count, items in sorted(edits, key=lambda edit: edit[0], reverse=True):
        args[position:position + count] = items
    return args


def _nvenc_unavailable(stderr: str) -> bool:
    text = stderr.lower()
    return any(marker in text for marker in NVENC_FAILURE_MARKERS)


def _metrics(encoder: str, started: float, size: int) -> RendererMetrics:
    used = MappingProxyType({f'encoder_{encoder}': 1})
    none = MappingProxyType({})
    return RendererMetrics(
        wall_time_ms=int((time.monotonic() - started) * 1000),
        cpu_metrics=used if encoder == ENCODER_LIBX264 else none,
        gpu_metrics=used if encoder == ENCODER_NVENC else none,
        peak_disk_bytes=size,
    )


class RealFfmpegRenderer:
    """RendererPort and OutputObservationPort over the pinned ffmpeg; raises FfmpegPinRejected when the binary is not the pinned one."""

    def __init__(
        self, *, lease: GpuLeasePort, ffmpeg_path: str = DEFAULT_FFMPEG_PATH, lock_path: Path | str = DEFAULT_LOCK_PATH,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS, command_prefix: Sequence[str] = (),
    ) -> None:
        self._lease = lease
        self._ffmpeg = Path(ffmpeg_path)
        self._lock_path = Path(lock_path)
        self._timeout = timeout_seconds
        self._prefix = tuple(command_prefix)
        self.last_encoder: str | None = None

    def observe(self, output_ref: str) -> OutputObservation:
        path = Path(output_ref)
        if not path.is_file():
            return OutputObservation(exists=False)
        return OutputObservation(exists=True, sha256=sha256_file(path))

    def _plan(self, spec: RenderCommandSpec) -> tuple[str, tuple[str, ...]]:
        """Output ref and encoder order of a spec this adapter can run; raises _SpecRejected otherwise."""
        argv = spec.argv
        if spec.kind != KIND_RENDER:
            raise _SpecRejected(REASON_UNSUPPORTED_KIND)
        if len(argv) < 3 or '-c:v' not in argv[:-1]:
            raise _SpecRejected(REASON_SPEC_SHAPE)
        if os.path.normcase(os.path.normpath(argv[0])) != os.path.normcase(os.path.normpath(str(self._ffmpeg))):
            raise _SpecRejected(REASON_EXECUTABLE)
        requested = argv[argv.index('-c:v') + 1]
        if requested not in ENCODER_ARGS:
            raise _SpecRejected(REASON_UNSUPPORTED_ENCODER)
        if Path(argv[-1]).exists():
            raise _SpecRejected(REASON_OUTPUT_EXISTS)
        encoders = (ENCODER_NVENC, ENCODER_LIBX264) if requested == ENCODER_NVENC else (ENCODER_LIBX264,)
        return argv[-1], encoders

    def run(self, spec: RenderCommandSpec) -> RendererOutcome:
        if not isinstance(spec, RenderCommandSpec):
            raise TypeError('spec must be a RenderCommandSpec')
        verify_ffmpeg_pin(self._ffmpeg, self._lock_path)
        self.last_encoder = None
        try:
            output_ref, encoders = self._plan(spec)
        except _SpecRejected as rejected:
            return RendererOutcome(status=RendererStatus.FAILED, error=str(rejected))
        lease = self._lease.acquire(spec.spec_fingerprint)
        try:
            return self._run_attempts(spec, output_ref, encoders)
        except _SpecRejected as rejected:
            return RendererOutcome(status=RendererStatus.FAILED, error=str(rejected))
        finally:
            self._lease.release(lease)

    def _run_attempts(self, spec: RenderCommandSpec, output_ref: str, encoders: tuple[str, ...]) -> RendererOutcome:
        """NVENC first; one retry on libx264 only when ffmpeg reports that NVENC could not start. A temporary file never outlives its attempt."""
        output = Path(output_ref)
        output.parent.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        failure = REASON_NO_OUTPUT
        for encoder in encoders:
            remaining = self._timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise RendererTimeout('render deadline reached before the next attempt')
            temp = output.with_name(f'{output.name}.{uuid.uuid4().hex[:12]}.part')
            try:
                code, stderr = self._execute(spec.argv, encoder, temp, remaining)
                if code == 0:
                    return self._publish(temp, output_ref, encoder, started)
            finally:
                temp.unlink(missing_ok=True)
            failure = f'ffmpeg_exit_{code}: {stderr[-ERROR_TAIL_CHARS:]}'
            if encoder != ENCODER_NVENC or not _nvenc_unavailable(stderr):
                break
        return RendererOutcome(status=RendererStatus.FAILED, error=failure)

    def _execute(self, argv: Sequence[str], encoder: str, temp: Path, timeout: float) -> tuple[int, str]:
        command = [*self._prefix, *build_final_argv(argv, str(self._ffmpeg), encoder, str(temp))]
        try:
            done = subprocess.run(
                command, capture_output=True, stdin=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace',
                timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired:
            raise RendererTimeout('ffmpeg exceeded the render timeout') from None
        return done.returncode, done.stderr or ''

    def _publish(self, temp: Path, output_ref: str, encoder: str, started: float) -> RendererOutcome:
        size = temp.stat().st_size if temp.is_file() else 0
        if size == 0:
            return RendererOutcome(status=RendererStatus.FAILED, error=REASON_NO_OUTPUT)
        output = Path(output_ref)
        os.replace(temp, output)
        self.last_encoder = encoder
        return RendererOutcome(
            status=RendererStatus.SUCCEEDED, output_ref=output_ref, sha256=sha256_file(output), metrics=_metrics(encoder, started, size),
        )


__all__ = ['FfmpegPinRejected', 'RealFfmpegRenderer', 'build_final_argv', 'sha256_file', 'verify_ffmpeg_pin']
