"""ADAPT-F: FFmpeg adapter of RendererPort and OutputObservationPort (CT-RND-004, CT-STATE-011).

run() executes one render RenderCommandSpec with subprocess.run and an argument list on the ffmpeg binary whose sha256 equals pins.ffmpeg.sha256 of tools/runtime/runtime.lock.json; a missing pin, a BLOCKED pin or a different hash is refused before anything runs.
Production profile (plan.md 7.4): 1080x1920 (frame placement built by render_command.frame_placement), 30 fps, h264_nvenc with one retry on libx264 when NVENC cannot start, AAC 192k 48 kHz stereo, MP4 +faststart, ASS burned in by the subtitles filter.
Each attempt writes a temporary file next to the output; only exit code 0 renames it atomically to output_ref (the output path of the spec), and an existing output is never overwritten.
LOCK-DESKTOP-GPU is held by the caller: RenderPipeline.render_video acquires one slot and returns it; run() receives that held GpuLease and never acquires or releases it, so one render takes exactly one slot. The encoder used is written to the metrics (gpu_metrics encoder_h264_nvenc or cpu_metrics encoder_libx264) and to last_encoder.
command_prefix exists for tests only (an interpreter that runs a fake ffmpeg script); the pin check always applies to ffmpeg_path.
PRS-LAYOUT-POLISH: a filter graph longer than render_command.LAYOUT_GRAPH_MAX_CHARS (layout videos with many scenes) is written next to the
temporary output and passed with -/filter_complex <file> (ffmpeg 7.1+ reads the option value from the file), so the Windows command
line limit (32,767 characters) never caps a render; the file never outlives its attempt. Shorter graphs stay inline as before.
Loudness (CT-RND-004): a graph with one loudnorm in the audio chain is run in two passes; the measurement pass calls the pinned ffmpeg directly (command_prefix wraps only the render pass), a failed or silent measurement is FAILED loudness_measure_failed and writes no file, and a graph with two loudnorm, loudnorm outside the audio chain or an unmapped output label is FAILED spec_shape_invalid before anything runs. Without loudnorm one command runs as before.

coveredIds: CT-RND-004, CT-STATE-011
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
import subprocess
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from render.domain.render_command import KIND_RENDER, LAYOUT_GRAPH_MAX_CHARS, RenderCommandSpec
from render.ports.lease import GpuLease, GpuLeasePort
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
GRAPH_FILE_OPTION = '-/filter_complex'
GRAPH_FILE_SUFFIX = '.graph.txt'


REASON_UNSUPPORTED_KIND = 'unsupported_spec_kind'
REASON_UNSUPPORTED_ENCODER = 'unsupported_encoder'
REASON_SPEC_SHAPE = 'spec_shape_invalid'
REASON_EXECUTABLE = 'executable_not_pinned'
REASON_OUTPUT_EXISTS = 'output_already_exists'
REASON_NO_OUTPUT = 'output_missing_after_exit_0'
REASON_LOUDNESS = 'loudness_measure_failed'
LOUDNORM = 'loudnorm'
MEASURE_LIMITS = (('input_i', -99.0, 0.0), ('input_tp', -99.0, 99.0), ('input_lra', 0.0, 99.0), ('input_thresh', -99.0, 0.0), ('target_offset', -99.0, 99.0))
_AUDIO_INPUT = re.compile(r'\[\d+:a:\d+\]')
_EDGE_LABELS = re.compile(r'^(?:\[[^\[\]]*\])+|(?:\[[^\[\]]*\])+$')
_END_LABEL = re.compile(r'\[([^\[\]]+)\]$')
_LOUDNORM_ARGS = re.compile(r'loudnorm=[^,\[]*')
_JSON_BLOCK = re.compile(r'\{[^{}]*\}')


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


@dataclass(frozen=True)
class LoudnessMeasurement:
    """Figures of the loudnorm measurement pass (input_* are loudnorm's own field names)."""

    input_i: float
    input_tp: float
    input_lra: float
    input_thresh: float
    target_offset: float


class LoudnessMeasureFailed(RuntimeError):
    """The measurement pass failed (exit code not 0, unreadable JSON or an unusable figure); the message is the reason after 'loudness_measure_failed: '."""


def _filter_name(piece: str) -> str:
    bare = _EDGE_LABELS.sub('', piece.strip())
    return bare.split('=', 1)[0]


def _loudnorm_shape(argv: Sequence[str]) -> tuple[int, list[str], int] | None:
    """(graph index, chains, loudnorm chain index) of a graph with one loudnorm in an audio chain whose label is mapped; None without loudnorm; _SpecRejected otherwise."""
    try:
        graph_index = list(argv).index('-filter_complex') + 1
        graph = argv[graph_index]
    except (ValueError, IndexError):
        raise _SpecRejected(REASON_SPEC_SHAPE) from None
    chains = graph.split(';')
    hits = [i for i, chain in enumerate(chains) for piece in chain.split(',') if _filter_name(piece) == LOUDNORM]
    if not hits:
        return None
    if len(hits) > 1:
        raise _SpecRejected(REASON_SPEC_SHAPE)
    chain = chains[hits[0]]
    end = _END_LABEL.search(chain)
    mapped = {argv[i + 1] for i, item in enumerate(argv[:-1]) if item == '-map'}
    if _AUDIO_INPUT.match(chain) is None or end is None or f'[{end.group(1)}]' not in mapped:
        raise _SpecRejected(REASON_SPEC_SHAPE)
    return graph_index, chains, hits[0]


def build_measure_argv(spec_argv: Sequence[str], ffmpeg: str) -> list[str] | None:
    """Argv of the measurement pass: every spec input, only the audio chains with print_format=json on loudnorm, the loudnorm label, the spec output length, null output; None when the spec has no loudnorm."""
    shape = _loudnorm_shape(spec_argv)
    if shape is None:
        return None
    graph_index, chains, index = shape
    chains = list(chains)
    chains[index], count = _LOUDNORM_ARGS.subn(lambda found: found.group(0) + ':print_format=json', chains[index], count=1)
    if count != 1:
        raise _SpecRejected(REASON_SPEC_SHAPE)
    audio = [chain for chain in chains if _AUDIO_INPUT.match(chain)]
    label = '[' + _END_LABEL.search(chains[index]).group(1) + ']'
    tail = ['-map', label]
    if '-shortest' in spec_argv:
        at = list(spec_argv).index('-shortest')
        if at + 2 < len(spec_argv) and spec_argv[at + 1] == '-t':
            tail += ['-t', spec_argv[at + 2]]
    return [ffmpeg, '-nostats', *spec_argv[1:graph_index - 1], '-filter_complex', ';'.join(audio), *tail, '-f', 'null', '-']


def parse_loudness_json(stderr: str) -> LoudnessMeasurement:
    """The last JSON block of loudnorm's stderr as finite figures inside the measured_* and offset domains; LoudnessMeasureFailed otherwise."""
    blocks = _JSON_BLOCK.findall(stderr)
    if not blocks:
        raise LoudnessMeasureFailed('no_json')
    try:
        data = json.loads(blocks[-1])
    except ValueError:
        raise LoudnessMeasureFailed('json_unparsable') from None
    values = []
    for key, low, high in MEASURE_LIMITS:
        raw = data.get(key)
        try:
            number = float(raw)
        except (TypeError, ValueError):
            raise LoudnessMeasureFailed(f'{key}_unusable') from None
        if isinstance(raw, bool) or not math.isfinite(number) or not low <= number <= high:
            raise LoudnessMeasureFailed(f'{key}_out_of_range')
        values.append(number)
    return LoudnessMeasurement(*values)


def measure_loudness(ffmpeg: str | Path, spec_argv: Sequence[str], *, timeout_seconds: float) -> LoudnessMeasurement | None:
    """Run the measurement pass straight on the pinned ffmpeg (no command_prefix, nothing written); None when the spec has no loudnorm."""
    command = build_measure_argv(spec_argv, str(ffmpeg))
    if command is None:
        return None
    try:
        done = subprocess.run(
            command, capture_output=True, stdin=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace',
            timeout=timeout_seconds, check=False,
        )
    except subprocess.TimeoutExpired:
        raise RendererTimeout('ffmpeg exceeded the render timeout during the loudness measurement') from None
    stderr = done.stderr or ''
    if done.returncode != 0:
        raise LoudnessMeasureFailed(f'ffmpeg_exit_{done.returncode}: {stderr[-ERROR_TAIL_CHARS:]}')
    return parse_loudness_json(stderr)


def apply_measurement(spec_argv: Sequence[str], measurement: LoudnessMeasurement) -> list[str]:
    """Spec argv whose loudnorm carries the measured figures with linear=true."""
    argv = list(spec_argv)
    shape = _loudnorm_shape(argv)
    if shape is None:
        return argv
    graph_index, chains, index = shape
    figures = (('measured_I', measurement.input_i), ('measured_TP', measurement.input_tp), ('measured_LRA', measurement.input_lra), ('measured_thresh', measurement.input_thresh), ('offset', measurement.target_offset))
    suffix = ''.join(f':{name}={value:.2f}' for name, value in figures) + ':linear=true'
    chains = list(chains)
    chains[index] = _LOUDNORM_ARGS.sub(lambda found: found.group(0) + suffix, chains[index], count=1)
    argv[graph_index] = ';'.join(chains)
    return argv


def _rewrite_graph(graph: str) -> str:
    """F-10-FIX6: the only rewrite of the spec chain is ass turned into the subtitles filter (libass); frame placement comes from render_command.frame_placement and is never touched here."""
    parts = []
    for part in graph.split(','):
        if part.startswith('ass='):
            sub_part = 'subtitles=' + part[len('ass='):]
            if '\\:' in sub_part and '\\\\:' not in sub_part:
                sub_part = sub_part.replace('\\:', '\\\\:')
            parts.append(sub_part)
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


def graph_through_file(argv: Sequence[str], path: Path) -> list[str]:
    """PRS-LAYOUT-POLISH: argv whose -filter_complex graph, when longer than LAYOUT_GRAPH_MAX_CHARS, is written to path (UTF-8) and
    replaced by GRAPH_FILE_OPTION path; a shorter graph leaves argv unchanged and writes nothing."""
    args = list(argv)
    index = args.index('-filter_complex')
    graph = args[index + 1]
    if len(graph) <= LAYOUT_GRAPH_MAX_CHARS:
        return args
    path.write_bytes(graph.encode('utf-8'))
    return [*args[:index], GRAPH_FILE_OPTION, str(path), *args[index + 2:]]


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

    takes_held_lease = True  # RenderPipeline reads this flag and passes the lease it holds

    def __init__(
        self, *, lease: GpuLeasePort | None = None, ffmpeg_path: str = DEFAULT_FFMPEG_PATH, lock_path: Path | str = DEFAULT_LOCK_PATH,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS, command_prefix: Sequence[str] = (),
    ) -> None:
        # lease is accepted for wiring compatibility only; the renderer never acquires a slot
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

    def run(self, spec: RenderCommandSpec, *, lease: GpuLease) -> RendererOutcome:
        if not isinstance(spec, RenderCommandSpec):
            raise TypeError('spec must be a RenderCommandSpec')
        if not isinstance(lease, GpuLease):
            raise TypeError('lease must be a held GpuLease')
        verify_ffmpeg_pin(self._ffmpeg, self._lock_path)
        self.last_encoder = None
        try:
            output_ref, encoders = self._plan(spec)
        except _SpecRejected as rejected:
            return RendererOutcome(status=RendererStatus.FAILED, error=str(rejected))
        try:
            return self._run_attempts(spec, output_ref, encoders)
        except _SpecRejected as rejected:
            return RendererOutcome(status=RendererStatus.FAILED, error=str(rejected))

    def _run_attempts(self, spec: RenderCommandSpec, output_ref: str, encoders: tuple[str, ...]) -> RendererOutcome:
        """NVENC first; one retry on libx264 only when ffmpeg reports that NVENC could not start. A temporary file never outlives its attempt. When the graph has a loudnorm, the measurement pass runs first on the pinned ffmpeg (no command_prefix, same deadline) and every attempt, the libx264 retry included, carries its figures with linear=true."""
        started = time.monotonic()
        try:
            measured = measure_loudness(self._ffmpeg, spec.argv, timeout_seconds=self._timeout)
        except LoudnessMeasureFailed as failed:
            return RendererOutcome(status=RendererStatus.FAILED, error=f'{REASON_LOUDNESS}: {failed}')
        argv = spec.argv if measured is None else apply_measurement(spec.argv, measured)
        output = Path(output_ref)
        output.parent.mkdir(parents=True, exist_ok=True)
        failure = REASON_NO_OUTPUT
        for encoder in encoders:
            remaining = self._timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise RendererTimeout('render deadline reached before the next attempt')
            temp = output.with_name(f'{output.name}.{uuid.uuid4().hex[:12]}.part')
            try:
                code, stderr = self._execute(argv, encoder, temp, remaining)
                if code == 0:
                    return self._publish(temp, output_ref, encoder, started)
            finally:
                temp.unlink(missing_ok=True)
            failure = f'ffmpeg_exit_{code}: {stderr[-ERROR_TAIL_CHARS:]}'
            if encoder != ENCODER_NVENC or not _nvenc_unavailable(stderr):
                break
        return RendererOutcome(status=RendererStatus.FAILED, error=failure)

    def _execute(self, argv: Sequence[str], encoder: str, temp: Path, timeout: float) -> tuple[int, str]:
        script = temp.with_name(temp.name + GRAPH_FILE_SUFFIX)
        try:
            command = [*self._prefix, *graph_through_file(build_final_argv(argv, str(self._ffmpeg), encoder, str(temp)), script)]
            try:
                done = subprocess.run(
                    command, capture_output=True, stdin=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace',
                    timeout=timeout, check=False,
                )
            except subprocess.TimeoutExpired:
                raise RendererTimeout('ffmpeg exceeded the render timeout') from None
        finally:
            script.unlink(missing_ok=True)
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


__all__ = [
    'FfmpegPinRejected', 'LoudnessMeasureFailed', 'LoudnessMeasurement', 'RealFfmpegRenderer', 'apply_measurement', 'build_final_argv',
    'build_measure_argv', 'graph_through_file', 'measure_loudness', 'parse_loudness_json', 'sha256_file', 'verify_ffmpeg_pin',
]
