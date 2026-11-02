"""ADAPT-F: FFmpeg renderer and ffprobe probe adapters against fake test-only binaries (CT-RND-004, CT-STATE-011, CT-QC-001).

The fake ffmpeg and ffprobe are Python scripts written into tmp_path and started through sys.executable (command_prefix); no real FFmpeg, NVENC or GPU is used (the real render is CP7-F-01).

coveredIds: CT-RND-004, CT-STATE-011, CT-QC-001
"""
import hashlib
import json
import pathlib
import subprocess
import sys

import pytest

from render.adapters import real_ffmpeg_renderer as renderer_module
from render.adapters.real_ffmpeg_renderer import FfmpegPinRejected, RealFfmpegRenderer
from render.adapters.real_ffprobe_probe import RealFfprobeProbe, measurements_from_ffprobe
from render.domain import render_command
from render.domain.package_contract import validate_render_package_payload
from render.domain.preset import build_preset_revision
from render.domain.render_command import MaterializedPaths, OutputProfile, ToolIdentity, build_render_command
from render.ports.lease import GpuLease, GpuLeasePort
from render.ports.output_probe import OutputMeasurements, OutputProbePort
from render.ports.renderer import OutputObservationPort, RendererPort, RendererStatus, RendererTimeout

FAKE_FFMPEG = '''
import json, pathlib, sys, time
here = pathlib.Path(__file__).resolve().parent
args = sys.argv[1:]
with (here / 'calls.jsonl').open('a', encoding='utf-8') as log:
    log.write(json.dumps(args) + chr(10))
plan = json.loads((here / 'plan.json').read_text(encoding='utf-8'))
encoder = args[args.index('-c:v') + 1]
output = pathlib.Path(args[-1])
if plan.get('nvenc_fail') and encoder == 'h264_nvenc':
    sys.stderr.write('[h264_nvenc] OpenEncodeSessionEx failed: no NVENC capable devices found' + chr(10))
    sys.exit(1)
output.write_bytes(b'partial-' + encoder.encode())
if plan.get('sleep'):
    time.sleep(plan['sleep'])
if plan.get('exit'):
    sys.stderr.write('boom: simulated ffmpeg failure' + chr(10))
    sys.exit(plan['exit'])
output.write_bytes(b'fake-mp4-' + encoder.encode())
'''

FAKE_FFPROBE = '''
import json, pathlib, sys, time
here = pathlib.Path(__file__).resolve().parent
with (here / 'probe_calls.jsonl').open('a', encoding='utf-8') as log:
    log.write(json.dumps(sys.argv[1:]) + chr(10))
plan = json.loads((here / 'probe_plan.json').read_text(encoding='utf-8'))
if plan.get('sleep'):
    time.sleep(plan['sleep'])
sys.stdout.write(plan.get('stdout', ''))
sys.exit(plan.get('exit', 0))
'''


SECTION = {'note': 'x'}
PRESET = build_preset_revision({
    'preset_key': 'p1', 'revision': 1, 'visual_rhythm': SECTION, 'layout_rules': SECTION, 'thumbnail_overlay_style': SECTION,
    'typography_karaoke_style': SECTION, 'hook_treatment': SECTION, 'mix_rules': SECTION, 'color_effect_rules': SECTION,
    'output_profile_ref': 'profile-1', 'fallback_constraints': SECTION, 'compatibility_requirements': SECTION,
})
PAYLOAD = {
    'render_package_id': 'pkg-1', 'package_fingerprint': 'a' * 64, 'production_snapshot_ref': 'snap-1', 'script_version_ref': 'script-1',
    'production_plan_ref': 'plan-1', 'preset_revision_ref': 'preset-1', 'voice_artifact_ref': 'ref-voice', 'word_timing_ref': 'ref-timing',
    'output_metadata_revision': 'meta-1', 'output_profile_revision': 'profile-1', 'language_validation_refs': ['lang-1'], 'input_artifacts': [],
    'timeline': {'segments': [
        {'start_ms': 0, 'end_ms': 3000, 'visual_asset_refs': ['ref-visual-a']},
        {'start_ms': 3000, 'end_ms': 6000, 'visual_asset_refs': ['ref-visual-b']},
    ]},
    'hook_placement': {
        'visual_hook_ref': 'ref-visual-a', 'audio_hook_ref': 'ref-voice', 'thumbnail_ref': 'ref-visual-a',
        'hook_time_range': {'start_ms': 0, 'end_ms': 3000}, 'thumbnail_time_range': {'start_ms': 500, 'end_ms': 1500},
    },
    'subtitle_config': {'karaoke': True}, 'mix_plan': {}, 'allowed_fallbacks': [],
    'materialization_manifest': {
        'ref-visual-a': {'local_ref': 'media/a.mp4'}, 'ref-visual-b': {'local_ref': 'media/b.mp4'},
        'ref-voice': {'local_ref': 'media/voice.wav'}, 'ref-ass': {'local_ref': 'subs/karaoke.ass'},
    },
    'output_path_ref': 'ref-output',
}
MATCH = 'match'


class FakeLease:
    def __init__(self):
        self.events = []

    def acquire(self, owner_ref):
        self.events.append(('acquire', owner_ref))
        return GpuLease(lease_id='lease-1', owner_ref=owner_ref)

    def release(self, lease):
        self.events.append(('release', lease.lease_id))


class Rig:
    def __init__(self, root):
        self.root = root
        self.staging = root / 'staging'
        self.script = root / 'fakeffmpeg.py'
        self.script.write_text(FAKE_FFMPEG, encoding='utf-8')
        self.script_sha = hashlib.sha256(self.script.read_bytes()).hexdigest()
        self.lock = root / 'runtime.lock.json'
        self.lease = FakeLease()
        # lease do RenderPipeline giữ sẵn; không đi qua FakeLease nên mọi sự kiện của FakeLease là bằng chứng run đã tự chạm cổng lease
        self.held = GpuLease(lease_id='lease-held', owner_ref='render-attempt-1')
        self.write_lock('PINNED', self.script_sha)
        self.plan()
        self.output_ref = str(pathlib.PureWindowsPath(str(self.staging)) / 'out' / 'final.mp4')

    def write_lock(self, status, sha256):
        pin = {'sha256': sha256, 'status': status}
        self.lock.write_text(json.dumps({'pins': {'ffmpeg': pin}}), encoding='utf-8')

    def plan(self, **values):
        (self.root / 'plan.json').write_text(json.dumps(values), encoding='utf-8')

    def calls(self):
        log = self.root / 'calls.jsonl'
        return [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()] if log.exists() else []

    def leftovers(self):
        parent = pathlib.Path(self.output_ref).parent
        return sorted(item.name for item in parent.iterdir()) if parent.exists() else []

    def renderer(self, **kwargs):
        return RealFfmpegRenderer(
            lease=self.lease, ffmpeg_path=str(self.script), lock_path=self.lock, command_prefix=(sys.executable,), **kwargs,
        )

    def spec(self, *, encoder='h264_nvenc', executable=None):
        profile = OutputProfile(
            width=1080, height=1920, fps=30, video_codec='h264', audio_codec='aac', container='mp4', pixel_format='yuv420p',
            encoder=encoder, bitrate=None,
        )
        tool = ToolIdentity(name='ffmpeg', version='2025-03-13', build='gyan-essentials', executable=executable or str(self.script))
        paths = MaterializedPaths(staging_root=str(self.staging), output_path='out/final.mp4', thumbnail_path='out/thumb.jpg')
        return build_render_command(validate_render_package_payload(PAYLOAD), PRESET, profile, 'ref-ass', tool, paths)


@pytest.fixture
def rig(tmp_path):
    return Rig(tmp_path)


def value_after(args, flag):
    return args[args.index(flag) + 1]


def test_ports_are_implemented(rig):
    adapter = rig.renderer()
    assert isinstance(adapter, RendererPort) and isinstance(adapter, OutputObservationPort)
    assert isinstance(rig.lease, GpuLeasePort) and isinstance(RealFfprobeProbe(), OutputProbePort)


def test_command_is_an_argument_list_with_production_parameters(rig, monkeypatch):
    seen = []
    original = subprocess.run

    def spy(command, **kwargs):
        seen.append((command, kwargs))
        return original(command, **kwargs)

    monkeypatch.setattr(renderer_module.subprocess, 'run', spy)
    outcome = rig.renderer().run(rig.spec(), lease=rig.held)
    assert outcome.status is RendererStatus.SUCCEEDED
    command, kwargs = seen[0]
    assert isinstance(command, list) and all(isinstance(item, str) for item in command)
    assert not kwargs.get('shell') and kwargs['timeout'] > 0
    args = rig.calls()[0]
    joined = ' '.join(args)
    assert value_after(args, '-c:v') == 'h264_nvenc'
    for fragment in (
        '-preset p5 -tune hq -rc vbr -cq 23 -b:v 0 -maxrate 12M -bufsize 24M -profile:v high -pix_fmt yuv420p -g 60 -bf 2',
        '-c:a aac -b:a 192k -ar 48000 -ac 2 -movflags +faststart -f mp4',
    ):
        assert fragment in joined
    graph = value_after(args, '-filter_complex')
    assert render_command.frame_placement(1080, 1920, 's0') + ',setsar=1,fps=30' in graph
    assert 'subtitles=filename=' in graph and 'ass=filename=' not in graph
    assert args[-1].startswith(rig.output_ref + '.') and args[-1].endswith('.part')


def test_success_publishes_output_atomically_and_reports_encoder(rig):
    spec = rig.spec()
    adapter = rig.renderer()
    outcome = adapter.run(spec, lease=rig.held)
    output = pathlib.Path(rig.output_ref)
    assert outcome.status is RendererStatus.SUCCEEDED and outcome.output_ref == rig.output_ref
    assert output.read_bytes() == b'fake-mp4-h264_nvenc'
    assert outcome.sha256 == hashlib.sha256(output.read_bytes()).hexdigest()
    assert dict(outcome.metrics.gpu_metrics) == {'encoder_h264_nvenc': 1} and not outcome.metrics.cpu_metrics
    assert outcome.metrics.wall_time_ms >= 0 and outcome.metrics.peak_disk_bytes == output.stat().st_size
    assert adapter.last_encoder == 'h264_nvenc' and rig.leftovers() == ['final.mp4']
    assert rig.lease.events == []
    seen = adapter.observe(rig.output_ref)
    assert seen.exists and seen.sha256 == outcome.sha256
    assert adapter.observe(rig.output_ref + '.missing').exists is False


def test_nonzero_exit_never_creates_output_and_never_touches_the_lease(rig):
    rig.plan(exit=3)
    adapter = rig.renderer()
    outcome = adapter.run(rig.spec(), lease=rig.held)
    assert outcome.status is RendererStatus.FAILED and outcome.output_ref is None
    assert 'ffmpeg_exit_3' in outcome.error and 'boom' in outcome.error
    assert not pathlib.Path(rig.output_ref).exists() and rig.leftovers() == []
    assert len(rig.calls()) == 1 and adapter.last_encoder is None
    assert rig.lease.events == []


def test_nvenc_failure_retries_once_with_libx264(rig):
    rig.plan(nvenc_fail=True)
    adapter = rig.renderer()
    outcome = adapter.run(rig.spec(), lease=rig.held)
    first, second = rig.calls()
    assert value_after(first, '-c:v') == 'h264_nvenc' and value_after(second, '-c:v') == 'libx264'
    joined = ' '.join(second)
    assert '-preset medium -crf 21 -pix_fmt yuv420p' in joined and 'h264_nvenc' not in joined
    assert outcome.status is RendererStatus.SUCCEEDED
    assert pathlib.Path(rig.output_ref).read_bytes() == b'fake-mp4-libx264'
    assert dict(outcome.metrics.cpu_metrics) == {'encoder_libx264': 1} and not outcome.metrics.gpu_metrics
    assert adapter.last_encoder == 'libx264' and rig.leftovers() == ['final.mp4']
    assert rig.lease.events == []


def test_nvenc_failure_with_failing_fallback_is_failed_after_one_retry(rig):
    rig.plan(nvenc_fail=True, exit=3)
    outcome = rig.renderer().run(rig.spec(), lease=rig.held)
    assert outcome.status is RendererStatus.FAILED and outcome.output_ref is None
    assert len(rig.calls()) == 2 and rig.leftovers() == []
    assert rig.lease.events == []


def test_timeout_raises_renderer_timeout_and_cleans_up(rig):
    rig.plan(sleep=30)
    with pytest.raises(RendererTimeout):
        rig.renderer(timeout_seconds=1.5).run(rig.spec(), lease=rig.held)
    assert not pathlib.Path(rig.output_ref).exists() and rig.leftovers() == []
    assert rig.lease.events == []


@pytest.mark.parametrize('status,sha256', [('PINNED', 'f' * 64), ('BLOCKED', MATCH), ('PENDING', MATCH), ('PINNED', 'short'), ('PINNED', None)])
def test_unpinned_or_mismatched_ffmpeg_is_refused(rig, status, sha256):
    rig.write_lock(status, rig.script_sha if sha256 == MATCH else sha256)
    with pytest.raises(FfmpegPinRejected):
        rig.renderer().run(rig.spec(), lease=rig.held)
    assert rig.calls() == [] and rig.lease.events == [] and not pathlib.Path(rig.output_ref).exists()


def test_missing_lock_or_binary_is_refused(rig):
    spec = rig.spec()
    rig.lock.unlink()
    with pytest.raises(FfmpegPinRejected):
        rig.renderer().run(spec, lease=rig.held)
    rig.write_lock('PINNED', rig.script_sha)
    rig.script.unlink()
    with pytest.raises(FfmpegPinRejected):
        rig.renderer().run(spec, lease=rig.held)
    assert rig.calls() == [] and rig.lease.events == []


def test_spec_for_another_executable_is_not_run(rig):
    outcome = rig.renderer().run(rig.spec(executable=str(rig.root / 'other.exe')), lease=rig.held)
    assert outcome.status is RendererStatus.FAILED and outcome.error == 'executable_not_pinned'
    assert rig.calls() == [] and rig.lease.events == []


def test_unsupported_encoder_is_not_run(rig):
    outcome = rig.renderer().run(rig.spec(encoder='enc2'), lease=rig.held)
    assert outcome.status is RendererStatus.FAILED and outcome.error == 'unsupported_encoder'
    assert rig.calls() == [] and rig.lease.events == []


def test_libx264_spec_runs_once_without_fallback(rig):
    outcome = rig.renderer().run(rig.spec(encoder='libx264'), lease=rig.held)
    assert outcome.status is RendererStatus.SUCCEEDED and len(rig.calls()) == 1
    assert value_after(rig.calls()[0], '-c:v') == 'libx264'


def test_existing_output_is_never_overwritten(rig):
    spec = rig.spec()
    output = pathlib.Path(rig.output_ref)
    output.parent.mkdir(parents=True)
    output.write_bytes(b'old')
    outcome = rig.renderer().run(spec, lease=rig.held)
    assert outcome.status is RendererStatus.FAILED and outcome.error == 'output_already_exists'
    assert output.read_bytes() == b'old' and rig.calls() == []


def test_run_refuses_a_missing_lease_and_runs_nothing(rig):
    with pytest.raises(TypeError):
        rig.renderer().run(rig.spec(), lease=None)
    assert rig.calls() == [] and rig.lease.events == [] and not pathlib.Path(rig.output_ref).exists()


def test_a_process_that_cannot_start_leaves_the_lease_to_the_caller(rig, monkeypatch):
    def broken(command, **kwargs):
        raise OSError('cannot start')

    monkeypatch.setattr(renderer_module.subprocess, 'run', broken)
    with pytest.raises(OSError):
        rig.renderer().run(rig.spec(), lease=rig.held)
    assert rig.lease.events == [] and rig.leftovers() == []


def test_renderer_declares_that_it_takes_a_held_lease():
    assert RealFfmpegRenderer.takes_held_lease is True


def test_adapter_sources_have_no_shell_and_no_src_prefix():
    folder = pathlib.Path(renderer_module.__file__).parent
    for name in ('real_ffmpeg_renderer.py', 'real_ffprobe_probe.py'):
        text = (folder / name).read_text(encoding='utf-8')
        assert 'shell=' + 'True' not in text and 'from src' + '.' not in text and 'import src' + '.' not in text


FULL = {
    'streams': [
        {'index': 0, 'codec_type': 'video', 'codec_name': 'h264', 'width': 1080, 'height': 1920, 'avg_frame_rate': '30/1', 'r_frame_rate': '30/1'},
        {'index': 1, 'codec_type': 'audio', 'codec_name': 'aac', 'sample_rate': '48000', 'channels': 2},
    ],
    'format': {'format_name': 'mov,mp4,m4a,3gp,3g2,mj2', 'duration': '61.040000', 'tags': {'major_brand': 'isom'}},
}
MOV_FAMILY = 'mov,mp4,m4a,3gp,3g2,mj2'


def test_full_ffprobe_json_maps_every_field():
    assert measurements_from_ffprobe(FULL) == OutputMeasurements(
        decodable=True, duration_ms=61040, width=1080, height=1920, fps=30.0, video_codec='h264', audio_codec='aac',
        container='mp4', has_audio_stream=True,
    )


def test_missing_fields_stay_none_and_nothing_is_guessed():
    data = {'streams': [{'codec_type': 'video', 'codec_name': 'h264', 'width': 1080, 'height': 1920, 'r_frame_rate': '30/1'}], 'format': {'format_name': MOV_FAMILY}}
    assert measurements_from_ffprobe(data) == OutputMeasurements(
        decodable=True, width=1080, height=1920, video_codec='h264', container='mp4', has_audio_stream=False,
    )


@pytest.mark.parametrize('rate,expected', [('30/1', 30.0), ('0/0', None), ('0/1', None), ('abc', None), (None, None), (30, None)])
def test_fps_comes_only_from_avg_frame_rate(rate, expected):
    stream = {'codec_type': 'video', 'codec_name': 'h264', 'r_frame_rate': '25/1'}
    if rate is not None:
        stream['avg_frame_rate'] = rate
    assert measurements_from_ffprobe({'streams': [stream], 'format': {}}).fps == expected


@pytest.mark.parametrize('duration,expected', [('61.040000', 61040), ('0.5', 500), ('N/A', None), ('-1', None), ('NaN', None), ('Infinity', None), (61.04, None)])
def test_duration_is_exact_milliseconds_or_none(duration, expected):
    assert measurements_from_ffprobe({'streams': [], 'format': {'duration': duration}}).duration_ms == expected


@pytest.mark.parametrize('names,brand,expected', [(MOV_FAMILY, 'isom', 'mp4'), (MOV_FAMILY, 'qt  ', None), (MOV_FAMILY, None, 'mp4'), ('matroska,webm', None, None), ('mp3', None, 'mp3'), (None, None, None)])
def test_container_mapping(names, brand, expected):
    fmt = {}
    if names is not None:
        fmt['format_name'] = names
    if brand is not None:
        fmt['tags'] = {'major_brand': brand}
    assert measurements_from_ffprobe({'streams': [], 'format': fmt}).container == expected


@pytest.mark.parametrize('width', [True, 0, -1, '1080', None])
def test_invalid_size_is_none(width):
    stream = {'codec_type': 'video', 'codec_name': 'h264', 'width': width, 'height': 1920}
    assert measurements_from_ffprobe({'streams': [stream], 'format': {}}).width is None


def test_streams_decide_decodable_and_audio():
    assert measurements_from_ffprobe({}) == OutputMeasurements()
    assert measurements_from_ffprobe([]) == OutputMeasurements() and measurements_from_ffprobe(None) == OutputMeasurements()
    empty = measurements_from_ffprobe({'streams': [], 'format': {}})
    assert empty.decodable is False and empty.has_audio_stream is False
    audio_only = measurements_from_ffprobe({'streams': [{'codec_type': 'audio', 'codec_name': 'aac'}], 'format': {}})
    assert audio_only.decodable is False and audio_only.has_audio_stream is True and audio_only.video_codec is None


def run_probe(tmp_path, plan, *, with_file=True, timeout_seconds=30):
    script = tmp_path / 'fakeffprobe.py'
    script.write_text(FAKE_FFPROBE, encoding='utf-8')
    (tmp_path / 'probe_plan.json').write_text(json.dumps(plan), encoding='utf-8')
    media = tmp_path / 'clip.mp4'
    if with_file:
        media.write_bytes(b'x')
    probe = RealFfprobeProbe(ffprobe_path=str(script), timeout_seconds=timeout_seconds, command_prefix=(sys.executable,))
    return probe.probe(str(media)), tmp_path / 'probe_calls.jsonl', media


def test_probe_runs_ffprobe_json_and_maps_output(tmp_path):
    result, calls, media = run_probe(tmp_path, {'stdout': json.dumps(FULL)})
    assert result == measurements_from_ffprobe(FULL) and result.decodable is True and result.fps == 30.0
    args = json.loads(calls.read_text(encoding='utf-8').splitlines()[0])
    assert value_after(args, '-print_format') == 'json' and '-show_streams' in args and '-show_format' in args
    assert args[-1] == str(media)


def test_probe_rejected_file_is_not_decodable(tmp_path):
    result, _, _ = run_probe(tmp_path, {'exit': 1})
    assert result == OutputMeasurements(decodable=False)


def test_probe_unparsable_output_measures_nothing(tmp_path):
    result, _, _ = run_probe(tmp_path, {'stdout': 'not json'})
    assert result == OutputMeasurements()


def test_probe_missing_file_does_not_run_ffprobe(tmp_path):
    result, calls, _ = run_probe(tmp_path, {'stdout': json.dumps(FULL)}, with_file=False)
    assert result == OutputMeasurements() and not calls.exists()


def test_probe_missing_binary_measures_nothing(tmp_path):
    media = tmp_path / 'clip.mp4'
    media.write_bytes(b'x')
    assert RealFfprobeProbe(ffprobe_path=str(tmp_path / 'none.exe')).probe(str(media)) == OutputMeasurements()


def test_probe_timeout_measures_nothing(tmp_path):
    result, _, _ = run_probe(tmp_path, {'sleep': 30}, timeout_seconds=1)
    assert result == OutputMeasurements()
