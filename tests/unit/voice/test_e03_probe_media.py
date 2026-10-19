"""E-03: ProbeMedia technical report from simulated ffprobe output (CT-PROC-003).

coveredIds: CT-PROC-003
"""
import ast
import dataclasses
import enum
import inspect
import pathlib
import typing

import pytest

from voice.domain import probe
from voice.domain import processing as proc
from voice.ports.probe import ProbePort

ROOT = pathlib.Path(__file__).resolve().parents[3]
SHA = 'a' * 64
MP4_FORMAT = 'mov,mp4,m4a,3gp,3g2,mj2'


def video_stream(**over) -> dict:
    base = {
        'codec_type': 'video',
        'codec_name': 'h264',
        'duration': '12.5',
        'width': 1920,
        'height': 1080,
        'r_frame_rate': '30000/1001',
        'pix_fmt': 'yuv420p',
    }
    base.update(over)
    return base


def audio_stream(**over) -> dict:
    base = {'codec_type': 'audio', 'codec_name': 'aac', 'duration': '12.5', 'sample_rate': '48000', 'channels': 2}
    base.update(over)
    return base


def image_stream(**over) -> dict:
    base = {'codec_type': 'image', 'codec_name': 'png', 'width': 640, 'height': 480, 'pix_fmt': 'rgba'}
    base.update(over)
    return base


def raw_of(*streams: dict, fmt: dict | None = None) -> dict:
    if fmt is None:
        fmt = {'format_name': MP4_FORMAT, 'duration': '12.5'}
    return {'format': fmt, 'streams': list(streams)}


def parse(raw: object, ext: object = 'mp4', mime: object = 'video/mp4', sha: object = SHA, size: object = 1024) -> probe.ProbeReport:
    return probe.parse_probe_output(raw, ext, mime, sha, size)


def error_of(call) -> proc.ProcessingContractError:
    with pytest.raises(proc.ProcessingContractError) as exc:
        call()
    return exc.value


def test_enums_are_strenum() -> None:
    for cls, values in (
        (probe.MediaType, {'video', 'audio', 'image', 'unknown'}),
        (probe.StreamKind, {'video', 'audio', 'image'}),
        (probe.Readability, {'readable', 'corrupt', 'unreadable'}),
    ):
        assert issubclass(cls, enum.StrEnum)
        assert {e.value for e in cls} == values


def test_dataclass_field_names() -> None:
    assert tuple(f.name for f in dataclasses.fields(probe.ProbeReport)) == (
        'media_type', 'container', 'streams', 'duration_ms', 'readability', 'corruption_flags',
        'orientation_degrees', 'color', 'observed_sha256', 'observed_size', 'warnings',
    )
    assert tuple(f.name for f in dataclasses.fields(probe.ProbeStream)) == (
        'kind', 'codec', 'duration_ms', 'width', 'height', 'frame_rate', 'sample_rate', 'channels', 'pixel_format',
    )
    assert tuple(f.name for f in dataclasses.fields(probe.ColorMetadata)) == (
        'color_space', 'color_range', 'color_transfer', 'color_primaries',
    )


def test_video_report_keeps_observed_technical_fields() -> None:
    report = parse(raw_of(video_stream(), audio_stream()))
    assert report.media_type is probe.MediaType.VIDEO
    assert report.container == MP4_FORMAT
    assert report.readability is probe.Readability.READABLE
    assert report.corruption_flags == ()
    assert report.warnings == ()
    assert report.duration_ms == 12500
    assert report.orientation_degrees == 0
    assert report.observed_sha256 == SHA
    assert report.observed_size == 1024
    video, audio = report.streams
    assert video == probe.ProbeStream(
        kind=probe.StreamKind.VIDEO, codec='h264', duration_ms=12500, width=1920, height=1080,
        frame_rate=30000 / 1001, pixel_format='yuv420p',
    )
    assert audio == probe.ProbeStream(
        kind=probe.StreamKind.AUDIO, codec='aac', duration_ms=12500, sample_rate=48000, channels=2,
    )


def test_audio_only_report() -> None:
    report = parse(
        raw_of(audio_stream(), fmt={'format_name': 'mp3', 'duration': '3.2'}), ext='mp3', mime='audio/mpeg',
    )
    assert report.media_type is probe.MediaType.AUDIO
    assert report.duration_ms == 3200
    assert report.warnings == ()
    assert report.color == probe.ColorMetadata()


def test_image_report_without_duration() -> None:
    report = parse(raw_of(image_stream(), fmt={'format_name': 'png_pipe'}), ext='png', mime='image/png')
    assert report.media_type is probe.MediaType.IMAGE
    assert report.container == 'png_pipe'
    assert report.duration_ms is None
    assert report.readability is probe.Readability.READABLE
    assert report.warnings == ()
    (stream,) = report.streams
    assert (stream.kind, stream.width, stream.height, stream.pixel_format) == (
        probe.StreamKind.IMAGE, 640, 480, 'rgba',
    )


def test_media_type_priority_video_then_audio_then_image() -> None:
    both = parse(raw_of(image_stream(), audio_stream(), video_stream()), ext=None, mime=None)
    assert both.media_type is probe.MediaType.VIDEO
    audio = parse(raw_of(image_stream(), audio_stream()), ext=None, mime=None)
    assert audio.media_type is probe.MediaType.AUDIO


def test_report_stream_and_color_are_frozen() -> None:
    report = parse(raw_of(video_stream()))
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.media_type = probe.MediaType.AUDIO  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.streams[0].width = 1  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.color.color_space = 'x'  # type: ignore[misc]
    assert isinstance(report.streams, tuple)
    assert isinstance(report.corruption_flags, tuple)
    assert isinstance(report.warnings, tuple)


@pytest.mark.parametrize(
    ('streams', 'ext', 'mime', 'expected_type', 'expect_warning'),
    [
        ((video_stream(), audio_stream()), 'png', None, probe.MediaType.VIDEO, True),
        ((video_stream(), audio_stream()), None, 'image/png', probe.MediaType.VIDEO, True),
        ((video_stream(),), 'png', 'video/mp4', probe.MediaType.VIDEO, True),
        ((video_stream(),), 'mp4', 'audio/mpeg', probe.MediaType.VIDEO, True),
        ((video_stream(),), 'mp3', 'audio/mpeg', probe.MediaType.VIDEO, True),
        ((audio_stream(),), 'mp4', 'video/mp4', probe.MediaType.AUDIO, True),
        ((image_stream(),), 'mp4', 'video/mp4', probe.MediaType.IMAGE, True),
        ((video_stream(),), 'mp4', 'video/mp4', probe.MediaType.VIDEO, False),
        ((video_stream(),), '.MKV', 'Video/X-Matroska; codecs=avc1', probe.MediaType.VIDEO, False),
        ((video_stream(),), None, None, probe.MediaType.VIDEO, False),
        ((video_stream(),), 'bin', 'application/octet-stream', probe.MediaType.VIDEO, False),
        ((image_stream(),), 'jpg', 'image/jpeg', probe.MediaType.IMAGE, False),
    ],
)
def test_declared_type_never_overrides_observed_streams(streams, ext, mime, expected_type, expect_warning) -> None:
    report = parse(raw_of(*streams), ext=ext, mime=mime)
    assert report.media_type is expected_type
    assert report.readability is probe.Readability.READABLE
    assert report.warnings == (('declared_type_mismatch',) if expect_warning else ())


def test_warning_and_flag_codes() -> None:
    assert probe.DECLARED_TYPE_MISMATCH == 'declared_type_mismatch'
    assert probe.NO_STREAMS == 'no_streams'
    assert probe.INVALID_DURATION == 'invalid_duration'
    assert probe.INVALID_STREAM_FIELD == 'invalid_stream_field'


BAD_DURATIONS = [
    -1, -0.5, '-0.001', float('nan'), 'nan', float('inf'), float('-inf'), 'inf', '-inf', 'abc', '', True, [1], 10 ** 400,
]


@pytest.mark.parametrize('raw', [
    {'format': {'format_name': MP4_FORMAT, 'duration': '1'}, 'streams': []},
    {'format': {'format_name': MP4_FORMAT, 'duration': '1'}},
    {'streams': [{'codec_type': 'subtitle'}, {'codec_type': 'data'}, {}]},
    {'error': {'code': -1}},
])
def test_missing_supported_streams_is_corrupt(raw) -> None:
    report = parse(raw)
    assert report.readability is probe.Readability.CORRUPT
    assert report.readability is not probe.Readability.READABLE
    assert report.corruption_flags == ('no_streams',)
    assert report.media_type is probe.MediaType.UNKNOWN
    assert report.streams == ()
    assert report.warnings == ()


@pytest.mark.parametrize('bad', BAD_DURATIONS)
def test_invalid_stream_duration_is_corrupt(bad) -> None:
    report = parse(raw_of(video_stream(duration=bad)))
    assert report.readability is probe.Readability.CORRUPT
    assert report.corruption_flags == ('invalid_duration',)
    assert report.media_type is probe.MediaType.VIDEO
    assert report.streams[0].duration_ms is None
    assert report.duration_ms == 12500


@pytest.mark.parametrize('bad', BAD_DURATIONS)
def test_invalid_format_duration_is_corrupt(bad) -> None:
    report = parse(raw_of(video_stream(), fmt={'format_name': MP4_FORMAT, 'duration': bad}))
    assert report.readability is probe.Readability.CORRUPT
    assert report.corruption_flags == ('invalid_duration',)
    assert report.duration_ms == 12500


def test_zero_duration_is_valid_and_missing_duration_is_none() -> None:
    zero = parse(raw_of(video_stream(duration=0), fmt={'format_name': MP4_FORMAT, 'duration': 0}))
    assert zero.readability is probe.Readability.READABLE
    assert zero.duration_ms == 0
    assert zero.streams[0].duration_ms == 0
    missing = parse(raw_of(video_stream(duration=None), fmt={'format_name': MP4_FORMAT}))
    assert missing.readability is probe.Readability.READABLE
    assert missing.duration_ms is None


@pytest.mark.parametrize(('builder', 'key', 'bad'), [
    (video_stream, 'width', 0),
    (video_stream, 'width', -1),
    (video_stream, 'width', True),
    (video_stream, 'width', 'abc'),
    (video_stream, 'width', 19.5),
    (video_stream, 'width', '9' * 30),
    (video_stream, 'height', '1080x'),
    (video_stream, 'r_frame_rate', '0/1'),
    (video_stream, 'r_frame_rate', '30/0'),
    (video_stream, 'r_frame_rate', '-30/1'),
    (video_stream, 'r_frame_rate', 'abc'),
    (video_stream, 'r_frame_rate', float('nan')),
    (audio_stream, 'sample_rate', 0),
    (audio_stream, 'sample_rate', '44.1k'),
    (audio_stream, 'channels', -2),
    (audio_stream, 'channels', False),
])
def test_invalid_stream_field_is_corrupt(builder, key, bad) -> None:
    report = parse(raw_of(builder(**{key: bad})))
    assert report.readability is probe.Readability.CORRUPT
    assert report.corruption_flags == ('invalid_stream_field',)


def test_numeric_strings_and_zero_over_zero_frame_rate_are_accepted() -> None:
    report = parse(raw_of(
        video_stream(width='1920', height='1080', r_frame_rate='0/0'),
        audio_stream(sample_rate='44100', channels='1'),
    ))
    assert report.readability is probe.Readability.READABLE
    video, audio = report.streams
    assert (video.width, video.height, video.frame_rate) == (1920, 1080, None)
    assert (audio.sample_rate, audio.channels) == (44100, 1)
    assert parse(raw_of(video_stream(r_frame_rate=25))).streams[0].frame_rate == 25.0
    assert parse(raw_of(video_stream(r_frame_rate='25'))).streams[0].frame_rate == 25.0


def test_empty_dict_is_unreadable() -> None:
    report = parse({}, ext='png', mime='image/png')
    assert report.readability is probe.Readability.UNREADABLE
    assert report.media_type is probe.MediaType.UNKNOWN
    assert report.container is None
    assert report.streams == ()
    assert report.duration_ms is None
    assert report.corruption_flags == ()
    assert report.warnings == ()
    assert report.observed_sha256 == SHA
    assert report.observed_size == 1024


@pytest.mark.parametrize(('bad', 'code'), [
    ('A' * 64, 'wrong_type'),
    ('a' * 63, 'wrong_type'),
    ('a' * 65, 'wrong_type'),
    ('g' * 64, 'wrong_type'),
    (' ' + 'a' * 63, 'wrong_type'),
    ('a' * 64 + '\n', 'wrong_type'),
    ('', 'wrong_type'),
    (123, 'wrong_type'),
    (None, 'missing_required'),
])
@pytest.mark.parametrize('raw', [{}, raw_of(video_stream())], ids=['unreadable', 'readable'])
def test_bad_observed_sha256_is_error(raw, bad, code) -> None:
    err = error_of(lambda: parse(raw, sha=bad))
    assert (err.code, err.field) == (code, 'observed_sha256')


@pytest.mark.parametrize(('bad', 'code'), [
    (-1, 'constraint_violation'),
    (True, 'wrong_type'),
    (1.5, 'wrong_type'),
    ('10', 'wrong_type'),
    (None, 'missing_required'),
])
def test_bad_observed_size_is_error(bad, code) -> None:
    err = error_of(lambda: parse({}, size=bad))
    assert (err.code, err.field) == (code, 'observed_size')
    assert parse({}, size=0).observed_size == 0


@pytest.mark.parametrize(('raw', 'ext', 'mime', 'code', 'field'), [
    (None, 'mp4', 'video/mp4', 'missing_required', 'raw'),
    ('x', 'mp4', 'video/mp4', 'wrong_type', 'raw'),
    ([], 'mp4', 'video/mp4', 'wrong_type', 'raw'),
    (5, 'mp4', 'video/mp4', 'wrong_type', 'raw'),
    ({'format': 'x', 'streams': []}, 'mp4', 'video/mp4', 'wrong_type', 'raw.format'),
    ({'streams': 'x'}, 'mp4', 'video/mp4', 'wrong_type', 'raw.streams'),
    ({'streams': {}}, 'mp4', 'video/mp4', 'wrong_type', 'raw.streams'),
    ({'streams': ['x']}, 'mp4', 'video/mp4', 'wrong_type', 'raw.streams'),
    (raw_of(video_stream()), 5, 'video/mp4', 'wrong_type', 'declared_extension'),
    (raw_of(video_stream()), 'mp4', 5, 'wrong_type', 'declared_mime'),
    ({'format': {'format_name': 5}, 'streams': [video_stream()]}, 'mp4', 'video/mp4', 'wrong_type', 'raw.format.format_name'),
    (raw_of(video_stream(codec_name=5)), 'mp4', 'video/mp4', 'wrong_type', 'raw.streams.codec_name'),
    (raw_of(video_stream(pix_fmt=5)), 'mp4', 'video/mp4', 'wrong_type', 'raw.streams.pix_fmt'),
])
def test_malformed_raw_or_declared_values_are_errors(raw, ext, mime, code, field) -> None:
    err = error_of(lambda: parse(raw, ext=ext, mime=mime))
    assert (err.code, err.field) == (code, field)


@pytest.mark.parametrize(('rotation', 'expected'), [
    (None, 0), (0, 0), (90, 90), (180, 180), (270, 270), (-90, 270), ('180', 180), (-180, 180), (360, 0), (90.0, 90),
])
def test_orientation_from_first_visual_stream(rotation, expected) -> None:
    report = parse(raw_of(video_stream(rotation=rotation)))
    assert report.orientation_degrees == expected
    assert report.readability is probe.Readability.READABLE


@pytest.mark.parametrize('bad', [45, 90.5, 'abc', True, float('nan')])
def test_invalid_rotation_is_corrupt(bad) -> None:
    report = parse(raw_of(video_stream(rotation=bad)))
    assert report.readability is probe.Readability.CORRUPT
    assert report.corruption_flags == ('invalid_stream_field',)
    assert report.orientation_degrees == 0


def test_audio_stream_rotation_is_ignored() -> None:
    assert parse(raw_of(audio_stream(rotation=90))).orientation_degrees == 0


def test_color_metadata_from_visual_streams() -> None:
    full = parse(raw_of(video_stream(
        color_space='bt709', color_range='tv', color_transfer='bt709', color_primaries='bt709',
    )))
    assert full.color == probe.ColorMetadata('bt709', 'tv', 'bt709', 'bt709')
    assert parse(raw_of(video_stream())).color == probe.ColorMetadata()
    partial = parse(raw_of(video_stream(color_space='bt2020nc'), image_stream(color_range='pc')))
    assert partial.color == probe.ColorMetadata(color_space='bt2020nc', color_range='pc')


def report_kwargs(**over) -> dict:
    base = {
        'media_type': 'video',
        'container': 'mp4',
        'streams': [probe.ProbeStream(kind=probe.StreamKind.VIDEO)],
        'duration_ms': 1,
        'readability': 'readable',
        'corruption_flags': [],
        'orientation_degrees': 0,
        'color': probe.ColorMetadata(),
        'observed_sha256': SHA,
        'observed_size': 1,
        'warnings': [],
    }
    base.update(over)
    return base


def test_report_constructor_coerces_enums_and_tuples() -> None:
    report = probe.ProbeReport(**report_kwargs())
    assert report.media_type is probe.MediaType.VIDEO
    assert report.readability is probe.Readability.READABLE
    assert isinstance(report.streams, tuple)
    assert report.corruption_flags == ()
    assert report.warnings == ()


@pytest.mark.parametrize(('over', 'code', 'field'), [
    ({'corruption_flags': ['no_streams']}, 'constraint_violation', 'readability'),
    ({'streams': []}, 'constraint_violation', 'readability'),
    ({'readability': 'corrupt'}, 'constraint_violation', 'corruption_flags'),
    ({'readability': 'unreadable'}, 'constraint_violation', 'readability'),
    ({'readability': 'bogus'}, 'enum_violation', 'readability'),
    ({'media_type': 'film'}, 'enum_violation', 'media_type'),
    ({'observed_sha256': 'A' * 64}, 'wrong_type', 'observed_sha256'),
    ({'observed_size': -1}, 'constraint_violation', 'observed_size'),
    ({'orientation_degrees': 45}, 'constraint_violation', 'orientation_degrees'),
    ({'orientation_degrees': True}, 'wrong_type', 'orientation_degrees'),
    ({'color': {}}, 'wrong_type', 'color'),
    ({'streams': ['x']}, 'wrong_type', 'streams'),
    ({'warnings': [1]}, 'wrong_type', 'warnings'),
    ({'container': 5}, 'wrong_type', 'container'),
    ({'duration_ms': -1}, 'constraint_violation', 'duration_ms'),
])
def test_report_constructor_rejects_inconsistent_values(over, code, field) -> None:
    err = error_of(lambda: probe.ProbeReport(**report_kwargs(**over)))
    assert (err.code, err.field) == (code, field)


class FakeProbe:
    def __init__(self, raw: dict) -> None:
        self.raw = raw
        self.calls: list = []

    def probe(self, artifact_ref):
        self.calls.append(artifact_ref)
        return self.raw


class NotAProbe:
    def scan(self, artifact_ref):
        return {}


def test_probe_port_is_protocol_with_probe_method() -> None:
    assert typing.Protocol in ProbePort.__bases__
    assert list(inspect.signature(ProbePort.probe).parameters) == ['self', 'artifact_ref']
    assert isinstance(FakeProbe({}), ProbePort)
    assert not isinstance(NotAProbe(), ProbePort)


def test_fake_probe_output_feeds_parse_probe_output() -> None:
    ref = proc.ArtifactRef('in-1', SHA)
    port = FakeProbe(raw_of(video_stream()))
    report = parse(port.probe(ref))
    assert port.calls == [ref]
    assert report.media_type is probe.MediaType.VIDEO
    assert parse(FakeProbe({}).probe(ref)).readability is probe.Readability.UNREADABLE


PURE_ALLOWED_IMPORTS = {
    'src/voice/domain/probe.py': {
        '__future__', 'collections.abc', 'dataclasses', 'enum', 'math', 're', 'types', 'voice.domain.processing',
    },
    'src/voice/ports/probe.py': {'__future__', 'collections.abc', 'typing', 'voice.domain.processing'},
}
FORBIDDEN_NAMES = frozenset({
    'subprocess', 'Popen', 'system', 'open', 'exec', 'eval', '__import__', 'import_module',
})


@pytest.mark.parametrize('rel', sorted(PURE_ALLOWED_IMPORTS))
def test_module_has_no_subprocess_or_io(rel: str) -> None:
    path = ROOT / rel
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    imported: set[str] = set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            imported.add(node.module)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    assert 'subprocess' not in imported
    assert imported <= PURE_ALLOWED_IMPORTS[rel]
    assert names.isdisjoint(FORBIDDEN_NAMES)
