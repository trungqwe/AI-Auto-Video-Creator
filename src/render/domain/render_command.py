"""F-10: structured render command specification (CT-RND-004).

A command is an argv tuple built from validated structured parts: there is no command string and no free text.
Profile values, tool identity and paths are inputs. Paths come only from the local refs of the materialization manifest under the staging root.
redacted_argv replaces every path with a token and is the only argv view that to_dict and to_json serialize.
Pure domain: no I/O, no clock, no process execution.
coveredIds: CT-RND-004, TST-SEC-INV-012, TST-SEC-INV-020 (F side)
"""
from __future__ import annotations

import json
import math
import re
import string
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import PureWindowsPath

from controlplane.application.idempotency.canonicalization import request_hash
from render.domain.package_contract import RenderPackageRecord
from render.domain.preconditions_artifacts import _inside_staging_root
from render.domain.preset import RenderPresetRevision

INPUT_NOT_READY = 'INPUT_NOT_READY'
INVALID_INPUT = 'INVALID_INPUT'
UNSAFE_ARGUMENT = 'unsafe_argument'
ASSET_NOT_MATERIALIZED = 'asset_not_materialized'
PATH_OUTSIDE_STAGING_ROOT = 'path_outside_staging_root'
KIND_RENDER = 'render'
KIND_THUMBNAIL = 'thumbnail'
IMAGE_MEDIA_PREFIX = 'image/'
COVER_ASPECT_TOLERANCE = 0.06
SCENE_ZOOM = 0.06
ZOOM_FRAME_STEP = 2
BACKDROP_SHRINK = 8
BACKDROP_BLUR_SIGMA = 6
BACKDROP_LEVEL = 0.5


class RenderCommandRejected(ValueError):
    """A command input is missing, invalid or unsafe: `code` is the stable error code and `reason` names the offending field."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(f'{code}: {reason}')
        self.code = code
        self.reason = reason


@dataclass(frozen=True, kw_only=True)
class OutputProfile:
    """Output profile of a render; every value is an input and None means missing (bitrate is optional)."""

    width: int | None = None
    height: int | None = None
    fps: int | float | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    container: str | None = None
    pixel_format: str | None = None
    encoder: str | None = None
    bitrate: int | None = None


@dataclass(frozen=True, kw_only=True)
class ToolIdentity:
    """Identity of the render tool; executable is the argv[0] path and is kept out of repr, dict and JSON views."""

    name: str | None = None
    version: str | None = None
    build: str | None = None
    executable: str | None = field(default=None, repr=False)


@dataclass(frozen=True, kw_only=True)
class MaterializedPaths:
    """Paths issued by the storage owner: the staging root, the output path and the thumbnail path (both under the staging root)."""

    staging_root: str | None = None
    output_path: str | None = None
    thumbnail_path: str | None = None


@dataclass(frozen=True, kw_only=True)
class RenderCommandSpec:
    """Frozen command specification: argv is the executable view, redacted_argv the only view that to_dict and to_json serialize."""

    kind: str
    argv: tuple[str, ...] = field(repr=False)
    redacted_argv: tuple[str, ...]
    spec_fingerprint: str
    tool_identity: ToolIdentity

    def to_dict(self) -> dict[str, object]:
        identity = self.tool_identity
        return {
            'kind': self.kind,
            'redacted_argv': list(self.redacted_argv),
            'spec_fingerprint': self.spec_fingerprint,
            'tool_identity': {'name': identity.name, 'version': identity.version, 'build': identity.build},
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)


_UNSAFE_CHARS = frozenset(';|&<>`$')
_BACKSLASH = chr(92)
_IDENTIFIER_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]*')
_FILTER_PATH_CHARS = frozenset(string.ascii_letters + string.digits + '_-./:' + _BACKSLASH)
_MAX_NUMBER = 2 ** 31 - 1
_LOUDNESS_LIMITS = (('integrated_lufs', 'I', -70, -5), ('true_peak_dbtp', 'TP', -9, 0), ('lra', 'LRA', 1, 50))
_PROFILE_TEXT_FIELDS = ('video_codec', 'audio_codec', 'container', 'pixel_format', 'encoder')
_TOOL_FIELDS = ('name', 'version', 'build', 'executable')


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_unsafe(text: str) -> bool:
    if '://' in text or '..' in text:
        return True
    return any(ch in _UNSAFE_CHARS or ord(ch) < 32 or ord(ch) == 127 for ch in text)


def _require(value: object, kind: type, name: str) -> None:
    if value is None:
        raise RenderCommandRejected(INPUT_NOT_READY, f'missing_{name}')
    if not isinstance(value, kind):
        raise RenderCommandRejected(INVALID_INPUT, f'invalid_{name}')


def _safe_text(value: object, name: str) -> str:
    """Return value when it is a non-empty string that is safe as an argv element; raise unsafe_argument otherwise."""
    if value is None:
        raise RenderCommandRejected(INPUT_NOT_READY, f'missing_{name}')
    if not isinstance(value, str):
        raise RenderCommandRejected(INVALID_INPUT, f'invalid_{name}')
    if _is_unsafe(value):
        raise RenderCommandRejected(UNSAFE_ARGUMENT, name)
    if not value.strip():
        raise RenderCommandRejected(INVALID_INPUT, f'invalid_{name}')
    return value


def _positive_number(value: object, name: str, integer: bool) -> int | float:
    if value is None:
        raise RenderCommandRejected(INPUT_NOT_READY, f'missing_{name}')
    numeric = _is_int(value) or (not integer and isinstance(value, float) and math.isfinite(value))
    if not numeric or not 0 < value <= _MAX_NUMBER:
        raise RenderCommandRejected(INVALID_INPUT, f'invalid_{name}')
    return value


def _checked_profile(profile: object) -> dict[str, object]:
    _require(profile, OutputProfile, 'profile')
    values: dict[str, object] = {
        'width': _positive_number(profile.width, 'profile.width', True),
        'height': _positive_number(profile.height, 'profile.height', True),
        'fps': _positive_number(profile.fps, 'profile.fps', False),
    }
    for name in _PROFILE_TEXT_FIELDS:
        text = _safe_text(getattr(profile, name), f'profile.{name}')
        if _IDENTIFIER_RE.fullmatch(text) is None:
            raise RenderCommandRejected(INVALID_INPUT, f'invalid_profile.{name}')
        values[name] = text
    bitrate = profile.bitrate
    values['bitrate'] = None if bitrate is None else _positive_number(bitrate, 'profile.bitrate', True)
    return values


def _checked_tool(tool_identity: object) -> dict[str, str]:
    _require(tool_identity, ToolIdentity, 'tool_identity')
    return {name: _safe_text(getattr(tool_identity, name), f'tool_identity.{name}') for name in _TOOL_FIELDS}


def _checked_root(materialized: object) -> str:
    _require(materialized, MaterializedPaths, 'materialized')
    return _safe_text(materialized.staging_root, 'materialized.staging_root')


def _staged_path(root: str, value: object, name: str) -> str:
    local = _safe_text(value, name)
    if not _inside_staging_root(root, local):
        raise RenderCommandRejected(PATH_OUTSIDE_STAGING_ROOT, name)
    return str(PureWindowsPath(root) / PureWindowsPath(local))


def _local_path(record: RenderPackageRecord, root: str, ref: object, name: str) -> str:
    if ref is None:
        raise RenderCommandRejected(INPUT_NOT_READY, f'missing_{name}')
    if not isinstance(ref, str) or not ref.strip():
        raise RenderCommandRejected(INVALID_INPUT, f'invalid_{name}')
    manifest = record.materialization_manifest
    entry = manifest.get(ref) if isinstance(manifest, Mapping) else None
    if entry is None:
        raise RenderCommandRejected(ASSET_NOT_MATERIALIZED, name)
    if not isinstance(entry, Mapping):
        raise RenderCommandRejected(INVALID_INPUT, f'invalid_{name}')
    return _staged_path(root, entry.get('local_ref'), f'{name}.local_ref')


def _duration_ms(segment: Mapping, index: int) -> int:
    name = f'timeline.segments[{index}]'
    bounds = []
    for key in ('start_ms', 'end_ms'):
        value = segment.get(key)
        if value is None:
            raise RenderCommandRejected(INPUT_NOT_READY, f'missing_{name}.{key}')
        if not _is_int(value):
            raise RenderCommandRejected(INPUT_NOT_READY, f'invalid_{name}.{key}')
        bounds.append(value)
    if bounds[1] <= bounds[0]:
        raise RenderCommandRejected(INVALID_INPUT, f'invalid_{name}.duration')
    return bounds[1] - bounds[0]


def _visual_refs(record: RenderPackageRecord) -> list[tuple[tuple[object, ...], str, int]]:
    timeline = record.timeline
    segments = timeline.get('segments') if isinstance(timeline, Mapping) else None
    if not isinstance(segments, (list, tuple)) or not segments:
        raise RenderCommandRejected(INPUT_NOT_READY, 'missing_timeline.segments')
    found = []
    for index, segment in enumerate(segments):
        name = f'timeline.segments[{index}].visual_asset_refs'
        refs = segment.get('visual_asset_refs') if isinstance(segment, Mapping) else None
        if not isinstance(refs, (list, tuple)) or not refs:
            raise RenderCommandRejected(INPUT_NOT_READY, f'missing_{name}')
        found.append((tuple(refs), name, _duration_ms(segment, index)))
    return found


def _seconds(duration_ms: int) -> str:
    return f'{duration_ms // 1000}.{duration_ms % 1000:03d}'


def _is_still_image(record: RenderPackageRecord, ref: object) -> bool:
    for artifact in record.input_artifacts:
        if artifact.artifact_version_id == ref:
            return artifact.media_type.lower().startswith(IMAGE_MEDIA_PREFIX)
    return False


def _ass_path(record: RenderPackageRecord, root: str, ass_ref: object) -> str:
    path = _local_path(record, root, ass_ref, 'ass_ref')
    if PureWindowsPath(path).suffix.lower() != '.ass':
        raise RenderCommandRejected(INVALID_INPUT, 'invalid_ass_ref')
    return path


def _filter_path(path: str) -> str:
    if not all(ch in _FILTER_PATH_CHARS for ch in path):
        raise RenderCommandRejected(UNSAFE_ARGUMENT, 'ass_ref.local_ref')
    return path.replace(_BACKSLASH, '/').replace(':', _BACKSLASH + ':')


def frame_placement(width: int, height: int, prefix: str) -> str:
    """The single builder that places one input on a width x height frame (scene, hook, thumbnail and the QC SSIM all call it); it has no time expression."""
    zoomed = 1 + SCENE_ZOOM
    fit_w, fit_h = int(width / zoomed), int(height / zoomed)
    back_w, back_h = max(2, width // BACKDROP_SHRINK), max(2, height // BACKDROP_SHRINK)
    cover = f'lt(abs(a*{height}/{width}-1),{COVER_ASPECT_TOLERANCE})'
    back = (
        f"[{prefix}in0]crop=w='min(iw,ih*{width}/{height})':h='min(ih,iw*{height}/{width})',scale={back_w}:{back_h},"
        f'gblur=sigma={BACKDROP_BLUR_SIGMA},colorchannelmixer=rr={BACKDROP_LEVEL}:gg={BACKDROP_LEVEL}:bb={BACKDROP_LEVEL},'
        f'scale={width}:{height}:flags=bilinear[{prefix}back]'
    )
    pic = (
        f"[{prefix}in1]scale=w='if({cover},max({width},{height}*a),min({fit_w},{fit_h}*a))':"
        f"h='if({cover},max({height},{width}/a),min({fit_h},{fit_w}/a))',"
        f"crop=w='min(iw,{width})':h='min(ih,{height})'[{prefix}pic]"
    )
    return f"split=2[{prefix}in0][{prefix}in1];{back};{pic};[{prefix}back][{prefix}pic]overlay=x='(W-w)/2':y='(H-h)/2'"


def _segment_frames(duration_ms: int, fps: int | float) -> int:
    return max(1, math.floor(Fraction(duration_ms, 1000) * Fraction(str(fps)) + Fraction(1, 2)))


def _scene_zoom(frames: int, fps: int | float) -> str:
    """Slow 1.00 to 1.06 zoom of a still scene: perspective every ZOOM_FRAME_STEP frames, the odd frames repeated by the fps filter."""
    progress = f'(in-1)*{ZOOM_FRAME_STEP}/{frames}'
    inset = f'{SCENE_ZOOM / 2:g}*{progress}/(1+{SCENE_ZOOM:g}*{progress})'
    return (
        f",loop=loop={frames - 1}:size=1,setpts=N/{fps}/TB,select='not(mod(n,{ZOOM_FRAME_STEP}))',"
        f"perspective=x0='W*{inset}':y0='H*{inset}':x1='W-W*{inset}':y1='H*{inset}':x2='W*{inset}':y2='H-H*{inset}':x3='W-W*{inset}':y3='H-H*{inset}':eval=frame"
    )


def _chain(source: str, values: dict[str, object], prefix: str, head: str = '', motion: str = '') -> str:
    width, height, fps, pixel_format = values['width'], values['height'], values['fps'], values['pixel_format']
    return f'[{source}]{head}{frame_placement(width, height, prefix)}{motion},setsar=1,fps={fps},format={pixel_format}'


def _normalise(index: int, values: dict[str, object], still: bool, duration_ms: int) -> str:
    prefix = f's{index}'
    if not still:
        return _chain(f'{index}:v:0', values, prefix) + f'[v{index}]'
    motion = _scene_zoom(_segment_frames(duration_ms, values['fps']), values['fps'])
    return _chain(f'{index}:v:0', values, prefix, 'trim=end_frame=1,', motion) + f'[v{index}]'


def _overlay(base: str, top: str, window: tuple[int, int]) -> str:
    return f"[{base}][{top}]overlay=eof_action=repeat:enable='between(t,{_seconds(window[0])},{_seconds(window[1])})'"


def _shifted(source: str, values: dict[str, object], start_ms: int, label: str, first_frame_only: bool) -> str:
    trim = ',trim=end_frame=1' if first_frame_only else ''
    return f'{_chain(source, values, label)}{trim},setpts=PTS-STARTPTS+{_seconds(start_ms)}/TB[{label}]'


def _loudness_rule(preset: RenderPresetRevision) -> dict[str, int | float] | None:
    """preset.mix_rules['loudness'] checked against the loudnorm domain; None when the preset has no such rule."""
    rules = preset.mix_rules
    if 'loudness' not in rules:
        return None
    rule = rules['loudness']
    if not isinstance(rule, Mapping):
        raise RenderCommandRejected(INVALID_INPUT, 'invalid_preset.mix_rules.loudness')
    checked: dict[str, int | float] = {}
    for key, _, low, high in _LOUDNESS_LIMITS:
        name = f'preset.mix_rules.loudness.{key}'
        value = rule.get(key)
        if value is None:
            raise RenderCommandRejected(INPUT_NOT_READY, f'missing_{name}')
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
            raise RenderCommandRejected(INVALID_INPUT, f'invalid_{name}')
        checked[key] = value
    return checked


def _loudnorm_chain(rule: dict[str, int | float] | None) -> str:
    """',loudnorm=...,asetpts=N/SR/TB' appended to the mix chain, or '' without a rule; asetpts renumbers pts because loudnorm flushes its last buffer with jumping pts."""
    if rule is None:
        return ''
    args = ':'.join(flag + '=' + format(rule[key], 'g') for key, flag, _, _ in _LOUDNESS_LIMITS)
    return ',loudnorm=' + args + ',asetpts=N/SR/TB'


def _filter_graph(scenes: Sequence[tuple[bool, int]], values: dict[str, object], ass_path: str, hook: _HookPlan, loudnorm: str = '', beds: Sequence[_Bed] = ()) -> str:
    count = len(scenes)
    voice, visual, audio, thumbnail = count, count + 1, count + 2, count + 3
    first_bed = thumbnail + (1 if hook.thumbnail_path is not None else 0)
    chains = [_normalise(index, values, still, duration_ms) for index, (still, duration_ms) in enumerate(scenes)]
    labels = ''.join(f'[v{index}]' for index in range(count))
    chains.append(f'[{audio}:a:0]adelay={hook.hook_range[0]}:all=1[ahook]')
    chains += [
        f'[{first_bed + index}:a:0]volume={bed.gain_db:.2f}dB,adelay={bed.start_ms}:all=1[abed{index}]'
        for index, bed in enumerate(beds)
    ]
    mixed = '[ahook]' + ''.join(f'[abed{index}]' for index in range(len(beds)))
    chains += [
        f'[{voice}:a:0]{mixed}amix=inputs={2 + len(beds)}:duration=first:normalize=0{loudnorm}[aout]',
        labels + f'concat=n={count}:v=1:a=0,tpad=stop_mode=clone:stop=-1[base]',
        _shifted(f'{visual}:v:0', values, hook.hook_range[0], 'vhook', False),
    ]
    ending = f'ass=filename={ass_path}[vout]'
    if hook.thumbnail_path is None:
        chains.append(_overlay('base', 'vhook', hook.hook_range) + ',' + ending)
    else:
        chains += [
            _overlay('base', 'vhook', hook.hook_range) + '[vtop]',
            _shifted(f'{thumbnail}:v:0', values, hook.thumbnail_range[0], 'vthumb', True),
            _overlay('vtop', 'vthumb', hook.thumbnail_range) + ',' + ending,
        ]
    return ';'.join(chains)


def _plain(*items: str) -> list[tuple[str, str]]:
    return [(item, item) for item in items]


def _time_range(placement: Mapping, name: str) -> tuple[int, int]:
    value = placement.get(name)
    if value is None:
        raise RenderCommandRejected(INPUT_NOT_READY, f'missing_hook_placement.{name}')
    start = value.get('start_ms') if isinstance(value, Mapping) else None
    end = value.get('end_ms') if isinstance(value, Mapping) else None
    if not (_is_int(start) and _is_int(end) and 0 <= start < end):
        raise RenderCommandRejected(INVALID_INPUT, f'invalid_hook_placement.{name}')
    return start, end


def _thumbnail_moment_ms(record: RenderPackageRecord) -> int:
    placement = record.hook_placement
    if not isinstance(placement, Mapping):
        raise RenderCommandRejected(INPUT_NOT_READY, 'missing_hook_placement')
    hook = _time_range(placement, 'hook_time_range')
    thumb = _time_range(placement, 'thumbnail_time_range')
    if not (hook[0] <= thumb[0] and thumb[1] <= hook[1]):
        raise RenderCommandRejected(INVALID_INPUT, 'thumbnail_outside_hook_range')
    return (thumb[0] + thumb[1]) // 2


@dataclass(frozen=True)
class _HookPlan:
    visual_ref: str
    audio_ref: str
    thumbnail_ref: str
    visual_path: str
    audio_path: str
    thumbnail_path: str | None
    hook_range: tuple[int, int]
    thumbnail_range: tuple[int, int]


def _hook_plan(record: RenderPackageRecord, root: str) -> _HookPlan:
    """thumbnail_path is None when the thumbnail shares its path with the visual hook."""
    placement = record.hook_placement
    if not isinstance(placement, Mapping):
        raise RenderCommandRejected(INPUT_NOT_READY, 'missing_hook_placement')
    hook = _time_range(placement, 'hook_time_range')
    thumb = _time_range(placement, 'thumbnail_time_range')
    if not (hook[0] <= thumb[0] and thumb[1] <= hook[1]):
        raise RenderCommandRejected(INVALID_INPUT, 'thumbnail_outside_hook_range')
    visual_ref, audio_ref, thumbnail_ref = placement.get('visual_hook_ref'), placement.get('audio_hook_ref'), placement.get('thumbnail_ref')
    visual = _local_path(record, root, visual_ref, 'visual_hook_ref')
    audio = _local_path(record, root, audio_ref, 'audio_hook_ref')
    thumbnail = _local_path(record, root, thumbnail_ref, 'thumbnail_ref')
    separate = PureWindowsPath(thumbnail) != PureWindowsPath(visual)
    return _HookPlan(visual_ref, audio_ref, thumbnail_ref, visual, audio, thumbnail if separate else None, hook, thumb)


@dataclass(frozen=True)
class _Bed:
    rendition_ref: str
    path: str
    start_ms: int
    end_ms: int
    gain_db: float


def _bed_plan(record: RenderPackageRecord, root: str) -> list[_Bed]:
    """mix_plan.beds of the package as checked beds sorted by (start_ms, end_ms, rendition_ref); empty without beds."""
    plan = record.mix_plan
    beds = plan.get('beds') if isinstance(plan, Mapping) else None
    if beds is None:
        return []
    if isinstance(beds, (str, bytes)) or not isinstance(beds, (list, tuple)):
        raise RenderCommandRejected(INVALID_INPUT, 'invalid_mix_plan.beds')
    found: list[_Bed] = []
    for index, item in enumerate(beds):
        name = f'mix_plan.beds[{index}]'
        if not isinstance(item, Mapping):
            raise RenderCommandRejected(INVALID_INPUT, f'invalid_{name}')
        start, end, gain = item.get('start_ms'), item.get('end_ms'), item.get('gain_db')
        if not (_is_int(start) and _is_int(end) and 0 <= start < end):
            raise RenderCommandRejected(INVALID_INPUT, f'invalid_{name}.range')
        if isinstance(gain, bool) or not isinstance(gain, (int, float)) or not math.isfinite(gain):
            raise RenderCommandRejected(INVALID_INPUT, f'invalid_{name}.gain_db')
        ref = item.get('rendition_ref')
        found.append(_Bed(ref, _local_path(record, root, ref, f'{name}.rendition_ref'), start, end, float(gain)))
    return sorted(found, key=lambda bed: (bed.start_ms, bed.end_ms, bed.rendition_ref))


def _make_spec(kind: str, pairs: list[tuple[str, str]], tool_identity: ToolIdentity, tool: dict[str, str], details: dict[str, object]) -> RenderCommandSpec:
    argv = tuple(real for real, _ in pairs)
    for index, item in enumerate(argv):
        # The filter graph is built only from validated numbers, identifiers and a character-restricted path; its chain separators are the only allowed semicolons.
        is_graph = index > 0 and argv[index - 1] == '-filter_complex'
        if _is_unsafe(item.replace(';', '') if is_graph else item):
            raise RenderCommandRejected(UNSAFE_ARGUMENT, f'argv[{index}]')
    redacted = tuple(shown for _, shown in pairs)
    basis = {'kind': kind, 'redacted_argv': list(redacted), 'tool': {name: tool[name] for name in ('name', 'version', 'build')}, **details}
    return RenderCommandSpec(kind=kind, argv=argv, redacted_argv=redacted, spec_fingerprint=request_hash(basis), tool_identity=tool_identity)


def _timeline_end_ms(record: RenderPackageRecord) -> int:
    timeline = record.timeline
    if isinstance(timeline, Mapping):
        val = timeline.get('duration_ms') or timeline.get('voice_duration_ms')
        if _is_int(val) and val > 0:
            return val
        segments = timeline.get('segments')
        if isinstance(segments, Sequence) and segments:
            last = segments[-1]
            if isinstance(last, Mapping) and _is_int(last.get('end_ms')):
                return last['end_ms']
    return 0


def _timed_input(record: RenderPackageRecord, ref: object, path: str, token: str, values: dict[str, object], duration_ms: int) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    if _is_still_image(record, ref):
        pairs += _plain('-loop', '1', '-framerate', str(values['fps']))
    return pairs + [*_plain('-t', _seconds(duration_ms), '-i'), (path, token)]


def build_render_command(record: object, preset: object, profile: object, ass_ref: object, tool_identity: object, materialized: object, *, voice_duration_ms: int | None = None) -> RenderCommandSpec:
    """Build the spec of the main render: each segment's first visual looped (still image) or trimmed (other media) to its timeline duration and normalised to the profile size, concat, the visual hook overlaid over hook_time_range, a distinct thumbnail asset's first frame overlaid over thumbnail_time_range, ASS subtitles, and the voice mixed with the audio hook delayed to hook start (amix, first input sets the length, normalize off). The output is exactly voice_duration_ms long (-t after -shortest), the last frame held by tpad when the timeline is shorter than the voice; without voice_duration_ms the output length is the timeline end. When preset.mix_rules has a loudness rule the mix chain continues with loudnorm and asetpts from that rule; without it the graph and the fingerprint are unchanged. When record.mix_plan has beds, each bed (sorted by start, end, ref) is one more input after the hook and thumbnail inputs (-t window length), set to its gain_db and delayed to its start, and joins the same amix before loudnorm; the package carries the gain, nothing is decided here; fingerprint includes the beds; without beds the argv, the graph and the fingerprint are unchanged."""
    _require(record, RenderPackageRecord, 'record')
    _require(preset, RenderPresetRevision, 'preset')
    if voice_duration_ms is not None and not (_is_int(voice_duration_ms) and 0 < voice_duration_ms <= _MAX_NUMBER):
        raise RenderCommandRejected(INVALID_INPUT, 'invalid_voice_duration_ms')
    rule = _loudness_rule(preset)
    loudnorm = _loudnorm_chain(rule)
    values = _checked_profile(profile)
    tool = _checked_tool(tool_identity)
    root = _checked_root(materialized)
    visual_refs = []
    assets = []
    for refs, name, duration_ms in _visual_refs(record):
        paths = [_local_path(record, root, ref, name) for ref in refs]
        visual_refs.append(refs[0])
        assets.append((paths[0], refs[0], duration_ms))
    voice = _local_path(record, root, record.voice_artifact_ref, 'voice_artifact_ref')
    hook = _hook_plan(record, root)
    beds = _bed_plan(record, root)
    ass = _ass_path(record, root, ass_ref)
    output = _staged_path(root, materialized.output_path, 'materialized.output_path')
    scenes = [(_is_still_image(record, ref), duration_ms) for _, ref, duration_ms in assets]
    pairs = [(tool['executable'], '{tool}'), *_plain('-hide_banner', '-nostdin', '-n')]
    for index, (path, ref, duration_ms) in enumerate(assets):
        pairs += _timed_input(record, ref, path, f'{{asset:{index}}}', values, duration_ms)
    pairs += [*_plain('-i'), (voice, '{voice}')]
    hook_ms = hook.hook_range[1] - hook.hook_range[0]
    pairs += _timed_input(record, hook.visual_ref, hook.visual_path, '{hook_visual}', values, hook_ms)
    pairs += [*_plain('-t', _seconds(hook_ms), '-i'), (hook.audio_path, '{hook_audio}')]
    if hook.thumbnail_path is not None:
        thumb_ms = hook.thumbnail_range[1] - hook.thumbnail_range[0]
        pairs += _timed_input(record, hook.thumbnail_ref, hook.thumbnail_path, '{thumbnail_asset}', values, thumb_ms)
    for index, bed in enumerate(beds):
        pairs += [*_plain('-t', _seconds(bed.end_ms - bed.start_ms), '-i'), (bed.path, f'{{bed:{index}}}')]
    pairs += _plain('-filter_complex')
    pairs.append((_filter_graph(scenes, values, _filter_path(ass), hook, loudnorm, beds), _filter_graph(scenes, values, '{ass}', hook, loudnorm, beds)))
    pairs += _plain('-map', '[vout]', '-map', '[aout]', '-shortest')
    output_ms = voice_duration_ms if voice_duration_ms is not None else _timeline_end_ms(record)
    if output_ms > 0:
        pairs += _plain('-t', _seconds(output_ms))
    pairs += _plain('-c:v', values['encoder'], '-c:a', values['audio_codec'])
    if values['bitrate'] is not None:
        pairs += _plain('-b:v', str(values['bitrate']))
    pairs += [*_plain('-f', values['container']), (output, '{output}')]
    details = {
        'package_fingerprint': record.package_fingerprint,
        'preset_fingerprint': preset.preset_fingerprint,
        'profile': values,
        'visual_refs': visual_refs,
        'voice_ref': record.voice_artifact_ref,
        'ass_ref': ass_ref,
        'hook': {
            'visual_ref': hook.visual_ref,
            'audio_ref': hook.audio_ref,
            'thumbnail_ref': hook.thumbnail_ref,
            'hook_time_range': list(hook.hook_range),
            'thumbnail_time_range': list(hook.thumbnail_range),
        },
    }
    if rule is not None:
        details['loudness'] = dict(rule)
    if beds:
        details['beds'] = [{'rendition_ref': bed.rendition_ref, 'start_ms': bed.start_ms, 'end_ms': bed.end_ms, 'gain_db': bed.gain_db} for bed in beds]
    return _make_spec(KIND_RENDER, pairs, tool_identity, tool, details)


def build_thumbnail_command(record: object, profile: object, tool_identity: object, materialized: object) -> RenderCommandSpec:
    """Build the spec that extracts one frame, at the middle of thumbnail_time_range, from the rendered video."""
    _require(record, RenderPackageRecord, 'record')
    values = _checked_profile(profile)
    tool = _checked_tool(tool_identity)
    root = _checked_root(materialized)
    moment = _thumbnail_moment_ms(record)
    video = _staged_path(root, materialized.output_path, 'materialized.output_path')
    image = _staged_path(root, materialized.thumbnail_path, 'materialized.thumbnail_path')
    seconds = f'{moment // 1000}.{moment % 1000:03d}'
    width, height = values['width'], values['height']
    pairs = [
        (tool['executable'], '{tool}'),
        *_plain('-hide_banner', '-nostdin', '-n', '-ss', seconds, '-i'),
        (video, '{video}'),
        *_plain('-frames:v', '1', '-vf', f'scale={width}:{height}'),
        (image, '{thumbnail}'),
    ]
    details = {'package_fingerprint': record.package_fingerprint, 'profile': values, 'moment_ms': moment}
    return _make_spec(KIND_THUMBNAIL, pairs, tool_identity, tool, details)
