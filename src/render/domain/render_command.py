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
from collections.abc import Mapping
from dataclasses import dataclass, field
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


def _visual_refs(record: RenderPackageRecord) -> list[tuple[tuple[object, ...], str]]:
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
        found.append((tuple(refs), name))
    return found


def _ass_path(record: RenderPackageRecord, root: str, ass_ref: object) -> str:
    path = _local_path(record, root, ass_ref, 'ass_ref')
    if PureWindowsPath(path).suffix.lower() != '.ass':
        raise RenderCommandRejected(INVALID_INPUT, 'invalid_ass_ref')
    return path


def _filter_path(path: str) -> str:
    if not all(ch in _FILTER_PATH_CHARS for ch in path):
        raise RenderCommandRejected(UNSAFE_ARGUMENT, 'ass_ref.local_ref')
    return path.replace(_BACKSLASH, '/').replace(':', _BACKSLASH + ':')


def _filter_graph(count: int, values: dict[str, object], ass_path: str) -> str:
    width, height, fps, pixel_format = values['width'], values['height'], values['fps'], values['pixel_format']
    inputs = ''.join(f'[{index}:v:0]' for index in range(count))
    chain = (
        f'concat=n={count}:v=1:a=0',
        f'scale={width}:{height}',
        f'fps={fps}',
        f'format={pixel_format}',
        f'ass=filename={ass_path}',
    )
    return inputs + ','.join(chain) + '[vout]'


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


def _make_spec(kind: str, pairs: list[tuple[str, str]], tool_identity: ToolIdentity, tool: dict[str, str], details: dict[str, object]) -> RenderCommandSpec:
    argv = tuple(real for real, _ in pairs)
    for index, item in enumerate(argv):
        if _is_unsafe(item):
            raise RenderCommandRejected(UNSAFE_ARGUMENT, f'argv[{index}]')
    redacted = tuple(shown for _, shown in pairs)
    basis = {'kind': kind, 'redacted_argv': list(redacted), 'tool': {name: tool[name] for name in ('name', 'version', 'build')}, **details}
    return RenderCommandSpec(kind=kind, argv=argv, redacted_argv=redacted, spec_fingerprint=request_hash(basis), tool_identity=tool_identity)


def build_render_command(record: object, preset: object, profile: object, ass_ref: object, tool_identity: object, materialized: object) -> RenderCommandSpec:
    """Build the spec of the main render: concat of the first visual rendition of each segment, burned-in ASS subtitles and the voice track."""
    _require(record, RenderPackageRecord, 'record')
    _require(preset, RenderPresetRevision, 'preset')
    values = _checked_profile(profile)
    tool = _checked_tool(tool_identity)
    root = _checked_root(materialized)
    visual_refs = []
    assets = []
    for refs, name in _visual_refs(record):
        paths = [_local_path(record, root, ref, name) for ref in refs]
        visual_refs.append(refs[0])
        assets.append(paths[0])
    voice = _local_path(record, root, record.voice_artifact_ref, 'voice_artifact_ref')
    ass = _ass_path(record, root, ass_ref)
    output = _staged_path(root, materialized.output_path, 'materialized.output_path')
    count = len(assets)
    pairs = [(tool['executable'], '{tool}'), *_plain('-hide_banner', '-nostdin', '-n')]
    for index, path in enumerate(assets):
        pairs += [*_plain('-i'), (path, f'{{asset:{index}}}')]
    pairs += [*_plain('-i'), (voice, '{voice}'), *_plain('-filter_complex')]
    pairs.append((_filter_graph(count, values, _filter_path(ass)), _filter_graph(count, values, '{ass}')))
    pairs += _plain('-map', '[vout]', '-map', f'{count}:a:0', '-c:v', values['encoder'], '-c:a', values['audio_codec'])
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
    }
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
