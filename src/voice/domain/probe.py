"""ProbeMedia technical report contract (CT-PROC-003): parses simulated ffprobe output, no I/O and no subprocess."""
from __future__ import annotations

from collections.abc import Mapping
import dataclasses
import enum
import math
import re
from types import MappingProxyType

from voice.domain.processing import (
    CONSTRAINT_VIOLATION,
    ENUM_VIOLATION,
    MISSING_REQUIRED,
    WRONG_TYPE,
    ProcessingContractError,
)

DECLARED_TYPE_MISMATCH = 'declared_type_mismatch'
NO_STREAMS = 'no_streams'
INVALID_DURATION = 'invalid_duration'
INVALID_STREAM_FIELD = 'invalid_stream_field'
ROTATIONS = (0, 90, 180, 270)

_SHA256_RE = re.compile(r'[0-9a-f]{64}')
_UINT_RE = re.compile(r'[0-9]{1,18}')


class MediaType(enum.StrEnum):
    VIDEO = 'video'
    AUDIO = 'audio'
    IMAGE = 'image'
    UNKNOWN = 'unknown'


class StreamKind(enum.StrEnum):
    VIDEO = 'video'
    AUDIO = 'audio'
    IMAGE = 'image'


class Readability(enum.StrEnum):
    READABLE = 'readable'
    CORRUPT = 'corrupt'
    UNREADABLE = 'unreadable'


@dataclasses.dataclass(frozen=True)
class ProbeStream:
    kind: StreamKind
    codec: str | None = None
    duration_ms: int | None = None
    width: int | None = None
    height: int | None = None
    frame_rate: float | None = None
    sample_rate: int | None = None
    channels: int | None = None
    pixel_format: str | None = None


@dataclasses.dataclass(frozen=True)
class ColorMetadata:
    color_space: str | None = None
    color_range: str | None = None
    color_transfer: str | None = None
    color_primaries: str | None = None


@dataclasses.dataclass(frozen=True)
class ProbeReport:
    media_type: MediaType
    container: str | None
    streams: tuple[ProbeStream, ...]
    duration_ms: int | None
    readability: Readability
    corruption_flags: tuple[str, ...]
    orientation_degrees: int
    color: ColorMetadata
    observed_sha256: str
    observed_size: int
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, 'media_type', _coerce_enum(MediaType, self.media_type, 'media_type'))
        object.__setattr__(self, 'readability', _coerce_enum(Readability, self.readability, 'readability'))
        streams = _as_tuple(self.streams, 'streams')
        if not all(isinstance(stream, ProbeStream) for stream in streams):
            raise ProcessingContractError(WRONG_TYPE, 'streams')
        object.__setattr__(self, 'streams', streams)
        flags = _str_tuple(self.corruption_flags, 'corruption_flags')
        object.__setattr__(self, 'corruption_flags', flags)
        object.__setattr__(self, 'warnings', _str_tuple(self.warnings, 'warnings'))
        if self.container is not None and not isinstance(self.container, str):
            raise ProcessingContractError(WRONG_TYPE, 'container')
        if self.duration_ms is not None:
            if isinstance(self.duration_ms, bool) or not isinstance(self.duration_ms, int):
                raise ProcessingContractError(WRONG_TYPE, 'duration_ms')
            if self.duration_ms < 0:
                raise ProcessingContractError(CONSTRAINT_VIOLATION, 'duration_ms')
        if not isinstance(self.color, ColorMetadata):
            raise ProcessingContractError(WRONG_TYPE, 'color')
        if isinstance(self.orientation_degrees, bool) or not isinstance(self.orientation_degrees, int):
            raise ProcessingContractError(WRONG_TYPE, 'orientation_degrees')
        if self.orientation_degrees not in ROTATIONS:
            raise ProcessingContractError(CONSTRAINT_VIOLATION, 'orientation_degrees')
        _check_sha256(self.observed_sha256, 'observed_sha256')
        _check_size(self.observed_size)
        if self.readability is Readability.READABLE and (flags or not streams):
            raise ProcessingContractError(CONSTRAINT_VIOLATION, 'readability')
        if self.readability is Readability.CORRUPT and not flags:
            raise ProcessingContractError(CONSTRAINT_VIOLATION, 'corruption_flags')
        if self.readability is Readability.UNREADABLE and streams:
            raise ProcessingContractError(CONSTRAINT_VIOLATION, 'readability')


class _InvalidValue(Exception):
    pass


def _to_float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise _InvalidValue
    try:
        number = float(value)
    except (ValueError, OverflowError):
        raise _InvalidValue from None
    if not math.isfinite(number):
        raise _InvalidValue
    return number


def _duration_ms(value: object, flags: set[str]) -> int | None:
    if value is None:
        return None
    try:
        millis = _to_float(value) * 1000.0
        if millis < 0 or not math.isfinite(millis):
            raise _InvalidValue
    except _InvalidValue:
        flags.add(INVALID_DURATION)
        return None
    return round(millis)


def _positive_int(value: object, flags: set[str]) -> int | None:
    if value is None:
        return None
    if isinstance(value, str) and _UINT_RE.fullmatch(value):
        value = int(value)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        flags.add(INVALID_STREAM_FIELD)
        return None
    return value


def _frame_rate(value: object, flags: set[str]) -> float | None:
    if value is None:
        return None
    try:
        if isinstance(value, str) and '/' in value:
            numerator_text, _, denominator_text = value.partition('/')
            numerator = _to_float(numerator_text)
            denominator = _to_float(denominator_text)
            if numerator == 0.0 and denominator == 0.0:
                return None
            if denominator == 0.0:
                raise _InvalidValue
            rate = numerator / denominator
        else:
            rate = _to_float(value)
        if rate <= 0.0 or not math.isfinite(rate):
            raise _InvalidValue
    except _InvalidValue:
        flags.add(INVALID_STREAM_FIELD)
        return None
    return rate


def _rotation(value: object, flags: set[str]) -> int | None:
    if value is None:
        return None
    try:
        degrees = _to_float(value)
    except _InvalidValue:
        flags.add(INVALID_STREAM_FIELD)
        return None
    if degrees != int(degrees) or int(degrees) % 360 not in ROTATIONS:
        flags.add(INVALID_STREAM_FIELD)
        return None
    return int(degrees) % 360


def _opt_text(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProcessingContractError(WRONG_TYPE, field)
    return value.strip() or None


_STREAM_KINDS = MappingProxyType({kind.value: kind for kind in StreamKind})
_KIND_PRIORITY = (StreamKind.VIDEO, StreamKind.AUDIO, StreamKind.IMAGE)
_VISUAL_KINDS = frozenset({StreamKind.VIDEO, StreamKind.IMAGE})
_EXTENSION_MEDIA_TYPE = MappingProxyType({
    'mp4': MediaType.VIDEO, 'mov': MediaType.VIDEO, 'mkv': MediaType.VIDEO, 'm4v': MediaType.VIDEO,
    'avi': MediaType.VIDEO,
    'mp3': MediaType.AUDIO, 'wav': MediaType.AUDIO, 'flac': MediaType.AUDIO, 'aac': MediaType.AUDIO,
    'm4a': MediaType.AUDIO, 'opus': MediaType.AUDIO,
    'png': MediaType.IMAGE, 'jpg': MediaType.IMAGE, 'jpeg': MediaType.IMAGE, 'webp': MediaType.IMAGE,
    'bmp': MediaType.IMAGE,
})
_MIME_MEDIA_TYPE = MappingProxyType({
    'video': MediaType.VIDEO, 'audio': MediaType.AUDIO, 'image': MediaType.IMAGE,
})


def _parse_stream(raw_stream: object, flags: set[str]) -> ProbeStream | None:
    if not isinstance(raw_stream, Mapping):
        raise ProcessingContractError(WRONG_TYPE, 'raw.streams')
    codec_type = raw_stream.get('codec_type')
    kind = _STREAM_KINDS.get(codec_type) if isinstance(codec_type, str) else None
    if kind is None:
        return None
    return ProbeStream(
        kind=kind,
        codec=_opt_text(raw_stream.get('codec_name'), 'raw.streams.codec_name'),
        duration_ms=_duration_ms(raw_stream.get('duration'), flags),
        width=_positive_int(raw_stream.get('width'), flags),
        height=_positive_int(raw_stream.get('height'), flags),
        frame_rate=_frame_rate(raw_stream.get('r_frame_rate'), flags),
        sample_rate=_positive_int(raw_stream.get('sample_rate'), flags),
        channels=_positive_int(raw_stream.get('channels'), flags),
        pixel_format=_opt_text(raw_stream.get('pix_fmt'), 'raw.streams.pix_fmt'),
    )


def _observed_media_type(streams: list[ProbeStream]) -> MediaType:
    kinds = {stream.kind for stream in streams}
    for kind in _KIND_PRIORITY:
        if kind in kinds:
            return MediaType(kind.value)
    return MediaType.UNKNOWN


def _normalize_extension(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProcessingContractError(WRONG_TYPE, 'declared_extension')
    return value.strip().lower().rsplit('.', 1)[-1] or None


def _normalize_mime(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProcessingContractError(WRONG_TYPE, 'declared_mime')
    return value.split(';', 1)[0].strip().lower() or None


def _mime_media_type(mime_type: str | None) -> MediaType | None:
    if mime_type is None:
        return None
    return _MIME_MEDIA_TYPE.get(mime_type.partition('/')[0])


def _check_sha256(value: object, field: str) -> str:
    if value is None:
        raise ProcessingContractError(MISSING_REQUIRED, field)
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ProcessingContractError(WRONG_TYPE, field)
    return value


def _check_size(value: object) -> int:
    if value is None:
        raise ProcessingContractError(MISSING_REQUIRED, 'observed_size')
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProcessingContractError(WRONG_TYPE, 'observed_size')
    if value < 0:
        raise ProcessingContractError(CONSTRAINT_VIOLATION, 'observed_size')
    return value


def _coerce_enum(enum_cls: type[enum.StrEnum], value: object, field: str):
    if isinstance(value, enum_cls):
        return value
    if not isinstance(value, str):
        raise ProcessingContractError(WRONG_TYPE, field)
    try:
        return enum_cls(value)
    except ValueError:
        raise ProcessingContractError(ENUM_VIOLATION, field) from None


def _as_tuple(value: object, field: str) -> tuple:
    if value is None:
        raise ProcessingContractError(MISSING_REQUIRED, field)
    if isinstance(value, (str, bytes, Mapping)):
        raise ProcessingContractError(WRONG_TYPE, field)
    try:
        return tuple(value)
    except TypeError:
        raise ProcessingContractError(WRONG_TYPE, field) from None


def _str_tuple(value: object, field: str) -> tuple[str, ...]:
    items = _as_tuple(value, field)
    if not all(isinstance(item, str) and item for item in items):
        raise ProcessingContractError(WRONG_TYPE, field)
    return items


def parse_probe_output(
    raw: object,
    declared_extension: object,
    declared_mime: object,
    observed_sha256: object,
    observed_size: object,
) -> ProbeReport:
    """Build a ProbeReport from simulated ffprobe output; declared values never override observed streams."""
    if raw is None:
        raise ProcessingContractError(MISSING_REQUIRED, 'raw')
    if not isinstance(raw, Mapping):
        raise ProcessingContractError(WRONG_TYPE, 'raw')
    sha256 = _check_sha256(observed_sha256, 'observed_sha256')
    size = _check_size(observed_size)
    extension = _normalize_extension(declared_extension)
    mime_type = _normalize_mime(declared_mime)
    if not raw:
        return ProbeReport(
            media_type=MediaType.UNKNOWN, container=None, streams=(), duration_ms=None,
            readability=Readability.UNREADABLE, corruption_flags=(), orientation_degrees=0,
            color=ColorMetadata(), observed_sha256=sha256, observed_size=size, warnings=(),
        )
    raw_format = raw.get('format')
    if raw_format is None:
        raw_format = {}
    elif not isinstance(raw_format, Mapping):
        raise ProcessingContractError(WRONG_TYPE, 'raw.format')
    raw_streams = raw.get('streams')
    if raw_streams is None:
        raw_streams = ()
    elif not isinstance(raw_streams, (list, tuple)):
        raise ProcessingContractError(WRONG_TYPE, 'raw.streams')
    flags: set[str] = set()
    container = _opt_text(raw_format.get('format_name'), 'raw.format.format_name')
    format_duration = _duration_ms(raw_format.get('duration'), flags)
    streams: list[ProbeStream] = []
    orientation: int | None = None
    colors: dict[str, str | None] = {}
    for raw_stream in raw_streams:
        stream = _parse_stream(raw_stream, flags)
        if stream is None:
            continue
        streams.append(stream)
        if stream.kind not in _VISUAL_KINDS:
            continue
        rotation = _rotation(raw_stream.get('rotation'), flags)
        if orientation is None:
            orientation = rotation
        for color_field in dataclasses.fields(ColorMetadata):
            text = _opt_text(raw_stream.get(color_field.name), f'raw.streams.{color_field.name}')
            if colors.get(color_field.name) is None:
                colors[color_field.name] = text
    if not streams:
        flags.add(NO_STREAMS)
    media_type = _observed_media_type(streams)
    stream_durations = [s.duration_ms for s in streams if s.duration_ms is not None]
    duration_ms = format_duration if format_duration is not None else max(stream_durations, default=None)
    warnings: list[str] = []
    if media_type is not MediaType.UNKNOWN:
        declared = {_EXTENSION_MEDIA_TYPE.get(extension), _mime_media_type(mime_type)} - {None}
        if any(item is not media_type for item in declared):
            warnings.append(DECLARED_TYPE_MISMATCH)
    return ProbeReport(
        media_type=media_type,
        container=container,
        streams=tuple(streams),
        duration_ms=duration_ms,
        readability=Readability.CORRUPT if flags else Readability.READABLE,
        corruption_flags=tuple(sorted(flags)),
        orientation_degrees=orientation or 0,
        color=ColorMetadata(**colors),
        observed_sha256=sha256,
        observed_size=size,
        warnings=tuple(warnings),
    )


__all__ = (
    'DECLARED_TYPE_MISMATCH',
    'NO_STREAMS',
    'INVALID_DURATION',
    'INVALID_STREAM_FIELD',
    'ROTATIONS',
    'MediaType',
    'StreamKind',
    'Readability',
    'ProbeStream',
    'ColorMetadata',
    'ProbeReport',
    'parse_probe_output',
)
