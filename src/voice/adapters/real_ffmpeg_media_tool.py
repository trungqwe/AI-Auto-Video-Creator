"""Real adapter for MediaToolPort, TransformPort, and ProbePort.

Executes ffmpeg and ffprobe binaries located in the same directory.
Pin is verified from tools/runtime/runtime.lock.json (pins.ffmpeg).
Region masking is performed using the boxblur filter.
The blur radius of a region follows its shorter side (blur_radius).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path

from voice.adapters.audio_bed_source import PreparedMusic
from voice.adapters.wav_duration import read_wav_info
from voice.domain.audio_bed import LoudnessReport
from voice.domain.image_safety import ImageSafetyAssessment, SafetyOutcome
from voice.domain.image_transform import TransformOutput, TransformRequest
from voice.domain.normalize import RenditionPlan
from voice.domain.processing import ArtifactRef, Disposition
from voice.ports.media_tool import ToolOutcome

RUNTIME_LOCK_RELATIVE_PATH = 'tools/runtime/runtime.lock.json'
MASK_REF_PREFIX = 'region:'
BLUR_ACTION = 'blur'
LUMA_POWER = 1
BLUR_MIN_RADIUS = 4
BLUR_REGION_DIVISOR = 6
_SHA256_RE = re.compile(r'[0-9a-f]{64}')
_EXTENSION_RE = re.compile(r'[a-z0-9]{1,8}')
_COLOR_RE = re.compile(r'#[0-9a-fA-F]{6}')
_PIXEL_FORMAT_RE = re.compile(r'[a-z0-9_]+')
_LOUDNESS_RANGES = ((-70.0, -5.0), (-9.0, 0.0), (1.0, 50.0))
_LOUDNORM_JSON_RE = re.compile(r'\{[^{}]*\}')


class FfmpegToolError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class FfmpegPinError(FfmpegToolError):
    pass


def format_mask_ref(x: float, y: float, width: float, height: float) -> str:
    for v in (x, y, width, height):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise ValueError('invalid_mask_ref')
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        raise ValueError('invalid_mask_ref')
    if width <= 0.0 or height <= 0.0:
        raise ValueError('invalid_mask_ref')
    if x + width > 1.000001 or y + height > 1.000001:
        raise ValueError('invalid_mask_ref')
    return f'{MASK_REF_PREFIX}{x:.6f},{y:.6f},{width:.6f},{height:.6f}'


def parse_mask_ref(mask_ref: str) -> tuple[float, float, float, float]:
    if not isinstance(mask_ref, str) or not mask_ref.startswith(MASK_REF_PREFIX):
        raise ValueError('invalid_mask_ref')
    parts = mask_ref[len(MASK_REF_PREFIX):].split(',')
    if len(parts) != 4:
        raise ValueError('invalid_mask_ref')
    try:
        x, y, w, h = (float(p) for p in parts)
        format_mask_ref(x, y, w, h)
    except (ValueError, TypeError):
        raise ValueError('invalid_mask_ref') from None
    return (x, y, w, h)


def blur_radius(width: int, height: int) -> int:
    short = min(width, height)
    return min(max(BLUR_MIN_RADIUS, short // BLUR_REGION_DIVISOR), short // 4)


def _file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open('rb') as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def _loudness_target(integrated_lufs: object, true_peak_dbtp: object, lra: object) -> tuple[float, float, float]:
    for (low, high), value in zip(_LOUDNESS_RANGES, (integrated_lufs, true_peak_dbtp, lra)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
            raise FfmpegToolError('loudness_target_invalid')
    return (float(integrated_lufs), float(true_peak_dbtp), float(lra))


class _FfprobeRunner:
    def __init__(self, tool: RealFfmpegMediaTool, path: Path) -> None:
        self._tool = tool
        self._path = path

    def __str__(self) -> str:
        return str(self._path)

    def __call__(self, extra: list[str], path: Path) -> dict:
        return self._tool._run_ffprobe(extra, path)


class RealFfmpegMediaTool:
    """Implements MediaToolPort, TransformPort, and ProbePort."""

    def __init__(
        self,
        ffmpeg_path: Path | str,
        lock_path: Path | str,
        resolve_input: Callable[[str], Path],
        resolve_output: Callable[[str, str], Path],
        *,
        timeout_seconds: float = 600.0,
        reassess: Callable[[ArtifactRef], ImageSafetyAssessment] | None = None,
    ) -> None:
        ffmpeg = Path(ffmpeg_path)
        if not ffmpeg.is_absolute() or ffmpeg.stem.lower() != 'ffmpeg':
            raise ValueError('ffmpeg_path must be an absolute path named ffmpeg')
        if not callable(resolve_input) or not callable(resolve_output):
            raise ValueError('resolve_input and resolve_output must be callable')
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or timeout_seconds <= 0:
            raise ValueError('timeout_seconds must be positive number')

        self._ffmpeg = ffmpeg
        self._ffprobe = _FfprobeRunner(self, ffmpeg.with_name('ffprobe' + ffmpeg.suffix))
        self._lock_path = Path(lock_path)
        self._resolve_input = resolve_input
        self._resolve_output = resolve_output
        self._timeout = float(timeout_seconds)
        self._reassess = reassess

    def _run(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=self._timeout,
            check=False,
            shell=False,
            stdin=subprocess.DEVNULL,
        )

    def _verify_pin(self) -> str:
        try:
            data = json.loads(self._lock_path.read_text(encoding='utf-8'))
            entry = data['pins']['ffmpeg']
            if not isinstance(entry, dict):
                raise TypeError
            status = entry.get('status')
            sha = entry.get('sha256')
            archive_name = entry.get('archive_name')
        except (OSError, ValueError, KeyError, TypeError):
            raise FfmpegPinError('pin_unreadable') from None

        if status != 'PINNED':
            raise FfmpegPinError('pin_not_pinned')
        if not isinstance(sha, str) or not _SHA256_RE.fullmatch(sha):
            raise FfmpegPinError('pin_not_pinned')
        if not isinstance(archive_name, str) or not archive_name:
            raise FfmpegPinError('pin_not_pinned')

        try:
            actual_sha = _file_sha256(self._ffmpeg)
        except OSError:
            raise FfmpegPinError('ffmpeg_unreadable') from None

        if actual_sha != sha:
            raise FfmpegPinError('ffmpeg_sha256_mismatch')

        try:
            completed = self._run([str(self._ffprobe), '-version'])
        except (subprocess.TimeoutExpired, OSError):
            raise FfmpegPinError('ffprobe_unavailable') from None

        first_line = completed.stdout.splitlines()[0] if completed.stdout.splitlines() else ''
        if completed.returncode != 0 or archive_name not in first_line:
            raise FfmpegPinError('ffprobe_build_mismatch')

        return archive_name

    def _source_path(self, ref: ArtifactRef, *, verify_sha: bool = True) -> Path:
        path = Path(self._resolve_input(ref.ref))
        if not path.is_file():
            raise FfmpegToolError('input_missing')
        if verify_sha and _file_sha256(path) != ref.content_sha256:
            raise FfmpegToolError('input_sha256_mismatch')
        return path

    def _new_output(self, ref: str, extension: str, source: Path) -> Path:
        if not _EXTENSION_RE.fullmatch(extension):
            raise FfmpegToolError('extension_invalid')
        path = Path(self._resolve_output(ref, extension))
        if path.resolve() == source.resolve():
            raise FfmpegToolError('output_is_input')
        if not path.parent.is_dir():
            raise FfmpegToolError('output_dir_missing')
        return path

    @staticmethod
    def _discard(output: Path) -> None:
        try:
            output.unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def _temp_for(output: Path) -> Path:
        return output.with_name(f'{output.stem}.{uuid.uuid4().hex[:12]}.part{output.suffix}')

    def _execute(self, head: list[str], output: Path, output_ref: str) -> ToolOutcome:
        temp = self._temp_for(output)
        command = [str(self._ffmpeg), '-nostdin', '-hide_banner', '-loglevel', 'error', '-n', *head, str(temp)]
        try:
            try:
                completed = self._run(command)
            except subprocess.TimeoutExpired:
                return ToolOutcome(Disposition.OUTCOME_UNKNOWN, error='ffmpeg_timeout')
            except OSError:
                return ToolOutcome(Disposition.FAILED, error='ffmpeg_not_started')
            if completed.returncode != 0:
                return ToolOutcome(Disposition.FAILED, error=f'ffmpeg_exit_{completed.returncode}')
            if not temp.is_file() or temp.stat().st_size == 0:
                return ToolOutcome(Disposition.FAILED, error='output_missing')
            return self._publish(temp, output, output_ref)
        finally:
            self._discard(temp)

    def _publish(self, temp: Path, output: Path, output_ref: str) -> ToolOutcome:
        try:
            os.link(temp, output)
        except FileExistsError:
            return self._accept_existing(temp, output, output_ref)
        except OSError:
            if os.name != 'nt':
                return ToolOutcome(Disposition.FAILED, error='output_publish_failed')
            try:
                os.rename(temp, output)
            except FileExistsError:
                return self._accept_existing(temp, output, output_ref)
            except OSError:
                return ToolOutcome(Disposition.FAILED, error='output_publish_failed')
        try:
            return ToolOutcome(Disposition.SUCCEEDED, output_ref=output_ref, output_sha256=_file_sha256(output))
        except OSError:
            return ToolOutcome(Disposition.FAILED, error='output_publish_failed')

    def _accept_existing(self, temp: Path, output: Path, output_ref: str) -> ToolOutcome:
        try:
            existing = _file_sha256(output)
            same = _file_sha256(temp) == existing
        except OSError:
            return ToolOutcome(Disposition.FAILED, error='output_publish_failed')
        if not same:
            return ToolOutcome(Disposition.FAILED, error='output_conflict')
        return ToolOutcome(Disposition.SUCCEEDED, output_ref=output_ref, output_sha256=existing)

    def _run_ffprobe(self, extra: list[str], path: Path) -> dict:
        completed = self._run([str(self._ffprobe), '-v', 'error', '-print_format', 'json', *extra, str(path)])
        if completed.returncode != 0:
            raise FfmpegToolError('probe_failed')
        try:
            data = json.loads(completed.stdout)
            if not isinstance(data, dict):
                raise ValueError
        except (ValueError, TypeError):
            raise FfmpegToolError('probe_failed') from None
        return data

    def _ffprobe(self, extra: list[str], path: Path) -> dict:
        return self._run_ffprobe(extra, path)

    def _extension(self, plan: RenditionPlan, source: Path) -> str:
        for step in plan.spec.operations:
            if str(step.operation) == 'transcode':
                container = step.params.get('container')
                if isinstance(container, str) and _EXTENSION_RE.fullmatch(container):
                    return container
        ext = source.suffix.lstrip('.').lower()
        if not ext or not _EXTENSION_RE.fullmatch(ext):
            raise FfmpegToolError('extension_invalid')
        return ext

    def _plan_tail(self, plan: RenditionPlan, source: Path, output: Path) -> list[str]:
        pre: list[str] = []
        vf: list[str] = []
        af: list[str] = []
        out: list[str] = []

        def _int_param(params: Mapping, name: str, min_val: int = 0) -> int:
            val = params.get(name)
            if isinstance(val, bool) or not isinstance(val, int) or val < min_val:
                raise FfmpegToolError('invalid_param')
            return val

        for step in plan.spec.operations:
            op_name = str(step.operation)
            if op_name == 'crop':
                x = _int_param(step.params, 'x', 0)
                y = _int_param(step.params, 'y', 0)
                w = _int_param(step.params, 'width', 1)
                h = _int_param(step.params, 'height', 1)
                vf.append(f'crop={w}:{h}:{x}:{y}')
            elif op_name == 'resize':
                w = _int_param(step.params, 'width', 1)
                h = _int_param(step.params, 'height', 1)
                vf.append(f"scale='min({w},iw)':'min({h},ih)':force_original_aspect_ratio=decrease:force_divisible_by=2")
            elif op_name == 'pad':
                w = step.params.get('width')
                h = step.params.get('height')
                if w is None or h is None or isinstance(w, bool) or isinstance(h, bool):
                    raise FfmpegToolError('pad_size_required')
                if not isinstance(w, int) or not isinstance(h, int) or w < 1 or h < 1:
                    raise FfmpegToolError('pad_size_required')
                color = step.params.get('color')
                if not isinstance(color, str) or not _COLOR_RE.fullmatch(color):
                    raise FfmpegToolError('invalid_param')
                color_hex = color[1:].lower()
                vf.append(f'pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:0x{color_hex}')
            elif op_name == 'color_conversion':
                pfmt = step.params.get('pixel_format')
                if not isinstance(pfmt, str) or not _PIXEL_FORMAT_RE.fullmatch(pfmt):
                    raise FfmpegToolError('invalid_param')
                vf.append(f'format={pfmt}')
            elif op_name == 'transcode':
                codec = step.params.get('codec')
                if codec == 'h264':
                    out.extend(['-c:v', 'libx264'])
                else:
                    raise FfmpegToolError('unsupported_codec')
            elif op_name == 'audio_normalize':
                af.append('loudnorm=I=-16:TP=-1.5:LRA=11')
            elif op_name == 'extract_frame':
                at_ms = _int_param(step.params, 'at_ms', 0)
                pre.extend(['-ss', f'{at_ms / 1000:.3f}'])
                out.extend(['-frames:v', '1'])
            elif op_name == 'duration_trim':
                start_ms = _int_param(step.params, 'start_ms', 0)
                end_ms = _int_param(step.params, 'end_ms', start_ms + 1)
                pre.extend(['-ss', f'{start_ms / 1000:.3f}'])
                out.extend(['-t', f'{(end_ms - start_ms) / 1000:.3f}'])
            else:
                raise FfmpegToolError('unsupported_operation')

        if plan.media_kind == 'image' and '-frames:v' not in out:
            out.extend(['-frames:v', '1'])

        result = [*pre, '-i', str(source)]
        if vf:
            result.extend(['-vf', ','.join(vf)])
        if af:
            result.extend(['-af', ','.join(af)])
        result.extend(out)
        result.append(str(output))
        return result

    def run(self, plan: RenditionPlan) -> ToolOutcome:
        try:
            self._verify_pin()
            source = self._source_path(plan.input_ref)
            extension = self._extension(plan, source)
            output = self._new_output(plan.output_ref, extension, source)
            tail = self._plan_tail(plan, source, output)
        except FfmpegToolError as exc:
            return ToolOutcome(Disposition.FAILED, error=exc.code)
        return self._execute(tail[:-1], output, plan.output_ref)

    def _post_assessment(self, request: TransformRequest, processed: ArtifactRef) -> ImageSafetyAssessment:
        if self._reassess is not None:
            try:
                res = self._reassess(processed)
                if isinstance(res, ImageSafetyAssessment):
                    return res
            except Exception:
                pass
        return ImageSafetyAssessment(
            outcome=SafetyOutcome.DETECTION_FAILED,
            original_usable=True,
            reason='post_transform_not_reassessed',
            warnings=('post_transform_not_reassessed',),
            policy_revision=str(request.transform_policy_revision),
        )

    def transform(self, request: TransformRequest) -> TransformOutput:
        archive = self._verify_pin()
        source = self._source_path(request.source_ref)

        actions = dict(request.actions)
        for region in request.regions:
            if actions.get(region.category) != BLUR_ACTION:
                raise FfmpegToolError('unsupported_action')

        streams = self._ffprobe(['-select_streams', 'v:0', '-show_entries', 'stream=width,height'], source).get('streams')
        if not isinstance(streams, list) or not streams:
            raise FfmpegToolError('source_size_unknown')
        first_stream = streams[0]
        if not isinstance(first_stream, dict):
            raise FfmpegToolError('source_size_unknown')
        width = first_stream.get('width')
        height = first_stream.get('height')
        if not isinstance(width, int) or isinstance(width, bool) or width <= 0:
            raise FfmpegToolError('source_size_unknown')
        if not isinstance(height, int) or isinstance(height, bool) or height <= 0:
            raise FfmpegToolError('source_size_unknown')

        n = len(request.regions)
        clauses: list[str] = [f"[0:v]split={n + 1}[b0]" + "".join(f"[t{i}]" for i in range(n))]
        for i, region in enumerate(request.regions):
            x, y, w, h = parse_mask_ref(str(region.mask_ref))
            px = int(x * width)
            py = int(y * height)
            pw = min(max(1, round(w * width)), width - px)
            ph = min(max(1, round(h * height)), height - py)
            if min(pw, ph) < 4:
                raise FfmpegToolError('region_too_small')
            radius = blur_radius(pw, ph)
            clauses.append(f"[t{i}]crop={pw}:{ph}:{px}:{py},boxblur=luma_radius={radius}:luma_power={LUMA_POWER}[k{i}]")
            clauses.append(f"[b{i}][k{i}]overlay={px}:{py}:format=auto[b{i + 1}]")

        graph = ';'.join(clauses)
        payload = {
            'source': request.source_ref.content_sha256,
            'regions': [[r.category, r.mask_ref] for r in request.regions],
            'actions': list(request.actions),
            'policy': request.transform_policy_revision,
            'profile': dict(request.output_profile),
            'processor': f'ffmpeg-{archive}',
            'graph': graph,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
        ).hexdigest()
        processed_ref = f'processed:{digest}'

        fmt = request.output_profile.get('format')
        extension = fmt if isinstance(fmt, str) and fmt else source.suffix.lstrip('.').lower()

        output = self._new_output(processed_ref, extension, source)
        outcome = self._execute(
            ['-i', str(source), '-filter_complex', graph, '-map', f'[b{n}]', '-frames:v', '1'],
            output,
            processed_ref,
        )
        if outcome.status is not Disposition.SUCCEEDED:
            raise FfmpegToolError(outcome.error or outcome.status.value)

        processed = ArtifactRef(processed_ref, outcome.output_sha256)
        return TransformOutput(
            processed_ref=processed,
            evidence_ref=f'evidence:{outcome.output_sha256}',
            processor_version=f'ffmpeg-{archive}',
            post_assessment=self._post_assessment(request, processed),
        )

    def _run_audio(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            completed = self._run([str(self._ffmpeg), '-nostdin', '-hide_banner', '-nostats', *args])
        except subprocess.TimeoutExpired:
            raise FfmpegToolError('ffmpeg_timeout') from None
        except OSError:
            raise FfmpegToolError('ffmpeg_not_started') from None
        if completed.returncode != 0:
            raise FfmpegToolError(f'ffmpeg_exit_{completed.returncode}')
        return completed

    def _music_sample_rate(self, path: Path) -> int:
        streams = self._ffprobe(['-select_streams', 'a:0', '-show_entries', 'stream=sample_rate'], path).get('streams')
        raw = streams[0].get('sample_rate') if isinstance(streams, list) and streams and isinstance(streams[0], dict) else None
        try:
            rate = int(raw)
        except (TypeError, ValueError):
            raise FfmpegToolError('music_no_audio') from None
        if rate <= 0:
            raise FfmpegToolError('music_no_audio')
        return rate

    def _measure_music(self, path: Path, target: tuple[float, float, float]) -> dict[str, float]:
        i, tp, lra = target
        completed = self._run_audio(['-i', str(path), '-vn', '-map', '0:a:0', '-af', f'loudnorm=I={i:.2f}:TP={tp:.2f}:LRA={lra:.2f}:print_format=json', '-f', 'null', '-'])
        try:
            raw = json.loads(_LOUDNORM_JSON_RE.findall(completed.stderr)[-1])
            measured = {name: float(raw[name]) for name in ('input_i', 'input_tp', 'input_lra', 'input_thresh', 'target_offset')}
        except (IndexError, KeyError, ValueError, TypeError):
            raise FfmpegToolError('music_unmeasurable') from None
        if not all(math.isfinite(value) for value in measured.values()):
            raise FfmpegToolError('music_unmeasurable')
        return measured

    def prepare_music(self, body: bytes, *, integrated_lufs: float, true_peak_dbtp: float, lra: float, work_dir: Path | str) -> PreparedMusic:
        target = _loudness_target(integrated_lufs, true_peak_dbtp, lra)
        i, tp, lra_target = target
        if not isinstance(body, bytes) or not body:
            raise FfmpegToolError('music_empty')
        self._verify_pin()
        work = Path(work_dir)
        work.mkdir(parents=True, exist_ok=True)
        stem = f'prep-{uuid.uuid4().hex}'
        source = work / f'{stem}.src'
        normalized = work / f'{stem}.norm.wav'
        lowered = work / f'{stem}.low.wav'
        try:
            source.write_bytes(body)
            rate = self._music_sample_rate(source)
            m = self._measure_music(source, target)
            m_i, m_tp, m_lra, m_thresh, m_offset = m['input_i'], m['input_tp'], m['input_lra'], m['input_thresh'], m['target_offset']
            graph = ':'.join([
                f'loudnorm=I={i:.2f}', f'TP={tp:.2f}', f'LRA={lra_target:.2f}', f'measured_I={m_i:.2f}', f'measured_TP={m_tp:.2f}',
                f'measured_LRA={m_lra:.2f}', f'measured_thresh={m_thresh:.2f}', f'offset={m_offset:.2f}', 'linear=true',
            ])
            self._run_audio(['-i', str(source), '-vn', '-map', '0:a:0', '-af', graph, '-ar', str(rate), '-c:a', 'pcm_s16le', str(normalized)])
            after = self._measure_music(normalized, target)
            final = normalized
            excess = after['input_tp'] - tp
            if excess > 0:
                self._run_audio(['-i', str(normalized), '-af', f'volume=-{excess:.4f}dB', '-c:a', 'pcm_s16le', str(lowered)])
                after = self._measure_music(lowered, target)
                final = lowered
            data = final.read_bytes()
            info = read_wav_info(data)
            return PreparedMusic(data=data, duration_ms=info.duration_ms, report=LoudnessReport(integrated_lufs=after['input_i'], true_peak_dbtp=after['input_tp']))
        finally:
            for path in (source, normalized, lowered):
                self._discard(path)

    def probe(self, artifact_ref: ArtifactRef) -> dict[str, object]:
        try:
            self._verify_pin()
            path = self._source_path(artifact_ref, verify_sha=False)
            return self._ffprobe(['-show_format', '-show_streams'], path)
        except (FfmpegToolError, OSError, subprocess.TimeoutExpired):
            return {}


__all__ = (
    'FfmpegToolError',
    'FfmpegPinError',
    'RealFfmpegMediaTool',
    'RUNTIME_LOCK_RELATIVE_PATH',
    'blur_radius',
    'format_mask_ref',
    'parse_mask_ref',
)