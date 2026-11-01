"""F-10-FIX4: render chuẩn hoá âm lượng loudnorm hai lượt về audio.loudness của hồ sơ production (FFmpeg ghim thật, không DB).

coveredIds: CT-RND-004
"""
from __future__ import annotations

import dataclasses
import json
import math
import pathlib
import re
import struct
import subprocess
import sys
import wave
import zlib

import pytest

from controlplane.api.wiring.production_profile import load_production_profile
from render.adapters import real_ffmpeg_renderer as renderer_module
from render.adapters import real_ffprobe_probe as probe_module
from render.adapters.config_render_sources import render_config_payloads
from render.adapters.real_ffmpeg_renderer import DEFAULT_FFMPEG_PATH, DEFAULT_LOCK_PATH, RealFfmpegRenderer
from render.adapters.real_ffprobe_probe import DEFAULT_FFPROBE_PATH
from render.domain.package_contract import validate_render_package_payload
from render.domain.preset import build_preset_revision
from render.domain.render_command import MaterializedPaths, OutputProfile, ToolIdentity, build_render_command
from render.ports.lease import GpuLease
from render.ports.renderer import RendererStatus, RendererTimeout

ROOT = pathlib.Path(__file__).resolve().parents[3]
PROFILE = ROOT / 'tools' / 'launcher' / 'prod' / 'profile.json'
FFMPEG = DEFAULT_FFMPEG_PATH
RATE = 48000
HOOK_SECONDS = 1.5
SOURCE_LUFS = -38.6
STEADY = 0.0166
PEAKY_BASE = 0.01
PEAKY_PEAK = 0.5
BURST_SAMPLES = 96
LEASE = GpuLease(lease_id='lease-1', owner_ref='f10-fix4')

SUPPLEMENTS = {
    'ass_style': {
        'secondary_colour': '&H00FFFFFF',
        'back_colour': '&H80000000',
        'italic': 0,
        'underline': 0,
        'strike_out': 0,
        'scale_x': 100,
        'scale_y': 100,
        'spacing': 0,
        'angle': 0,
        'border_style': 1,
        'shadow': 0,
        'alignment': 2,
        'encoding': 1,
    },
    'layout': {
        'margin_left': 60,
        'margin_right': 60,
        'max_words_per_line': 4,
        'max_chars_per_line': 28,
        'disclosure_font_size': 40,
        'disclosure_alignment': 8,
        'disclosure_margin_v': 240,
    },
    'sections': {
        'visual_rhythm': {'note': 'f10-fix4'},
        'thumbnail_overlay_style': {'note': 'f10-fix4'},
        'hook_treatment': {'note': 'f10-fix4'},
        'color_effect_rules': {'note': 'f10-fix4'},
    },
    'quality_thresholds': {
        'SUBTITLE_BURNED_IN': {'min_frames_with_text': 2},
        'VOICE_AUDIBLE': {'min_voice_level': -40.0},
    },
    'output_profile': {
        'video_codec': 'h264',
        'pixel_format': 'yuv420p',
    },
}

ASS_TEXT = chr(10).join([
    '[Script Info]', 'ScriptType: v4.00+', 'PlayResX: 1080', 'PlayResY: 1920', '', '[V4+ Styles]',
    'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
    'Style: Default,Arial,60,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1', '', '[Events]',
    'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text',
    'Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,Sub',
]) + chr(10)


def write_png_raw(path, width, height, raw):
    def chunk(kind, data):
        body = kind + data
        return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body) & 0xFFFFFFFF)
    header = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    path.write_bytes(bytes([137, 80, 78, 71, 13, 10, 26, 10]) + chunk(b'IHDR', header) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def write_png(path, width, height, rgb):
    write_png_raw(path, width, height, (bytes([0]) + bytes(rgb) * width) * height)


PREFIX = """import json, subprocess, sys

log, mode, args = sys.argv[1], sys.argv[2], sys.argv[3:]
with open(log, 'a', encoding='utf-8') as handle:
    handle.write(json.dumps(args) + chr(10))
quiet = subprocess.DEVNULL if mode == 'quiet' else None
sys.exit(subprocess.run(args, stdin=subprocess.DEVNULL, stderr=quiet).returncode)
"""


def production_preset(drop_loudness=False):
    params = dict(load_production_profile(PROFILE).parameters)
    items = render_config_payloads(params, SUPPLEMENTS)
    output = next(p for kind, key, p in items if key == 'output-profile')
    payload = dict(next(p for kind, key, p in items if kind == 'preset' and key == 'bold-yellow'))
    if drop_loudness:
        payload['mix_rules'] = {'bed_gain_db': payload['mix_rules']['bed_gain_db']}
    return build_preset_revision({**payload, 'revision': 1}), output


def target():
    rule = production_preset()[0].mix_rules['loudness']
    return (rule['integrated_lufs'], rule['true_peak_dbtp'], rule['warn_tolerance_lu'])


def write_voice(path, seconds, kind):
    total = int(RATE * seconds)
    samples = []
    for n in range(total):
        if kind == 'silent':
            samples.append(0)
        elif kind == 'steady':
            samples.append(int(STEADY * 32767 * math.sin(2 * math.pi * 1000 * n / RATE)))
        else:
            amplitude = PEAKY_PEAK if n % RATE < BURST_SAMPLES else PEAKY_BASE
            samples.append(int(amplitude * 32767 * math.sin(2 * math.pi * 1000 * n / RATE)))
    with wave.open(str(path), 'wb') as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(struct.pack(f'<{total}h', *samples))


def write_silence(path, seconds):
    total = int(RATE * seconds)
    with wave.open(str(path), 'wb') as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(struct.pack(f'<{total}h', *([0] * total)))


def run(command):
    return subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', stdin=subprocess.DEVNULL, timeout=600, check=False)


def ffprobe(entries, path):
    done = run([DEFAULT_FFPROBE_PATH, '-v', 'error', *entries, '-of', 'json', str(path)])
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def loudness_of(path):
    stats = probe_module.measure_loudness(pathlib.Path(FFMPEG), pathlib.Path(path))
    assert stats.integrated_lufs is not None and stats.true_peak_dbtp is not None
    return stats


def durations(path):
    info = ffprobe(['-show_entries', 'format=duration:stream=codec_type,duration'], path)
    video = next(float(s['duration']) for s in info['streams'] if s['codec_type'] == 'video')
    audio = next(float(s['duration']) for s in info['streams'] if s['codec_type'] == 'audio')
    return (float(info['format']['duration']), video, audio)


def pcm(path):
    done = subprocess.run(
        [FFMPEG, '-hide_banner', '-nostdin', '-v', 'error', '-i', str(path), '-vn', '-f', 's16le', '-ac', '2', '-ar', '48000', '-'],
        capture_output=True, stdin=subprocess.DEVNULL, timeout=300, check=False,
    )
    assert done.returncode == 0 and done.stdout
    return done.stdout


def silence_starts(path):
    done = run([FFMPEG, '-hide_banner', '-nostdin', '-i', str(path), '-vn', '-af', 'silencedetect=noise=-50dB:d=0.03', '-f', 'null', '-'])
    assert done.returncode == 0, done.stderr
    return [float(x) for x in re.findall(r'silence_start: (-?[0-9.]+)', done.stderr)]


def value_after(argv, flag):
    return argv[argv.index(flag) + 1]


def artifact(ref, media_type):
    return {'artifact_version_id': ref, 'sha256': 'c' * 64, 'size_bytes': 1, 'media_type': media_type}


def hook_placement(**changes):
    value = {
        'visual_hook_ref': 'ref-bg',
        'audio_hook_ref': 'ref-hook',
        'thumbnail_ref': 'ref-bg',
        'hook_time_range': {'start_ms': 0, 'end_ms': 1500},
        'thumbnail_time_range': {'start_ms': 200, 'end_ms': 800},
    }
    value.update(changes)
    return value


class Rig:
    def __init__(self, tmp_path, voice_seconds, kind='steady', drop_loudness=False):
        tmp_path.mkdir(parents=True, exist_ok=True)
        self.root = tmp_path / 'stage'
        for name in ('media', 'subs', 'out'):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        self.voice_ms = round(voice_seconds * 1000)
        write_voice(self.root / 'media' / 'voice.wav', voice_seconds, kind)
        write_silence(self.root / 'media' / 'hook.wav', HOOK_SECONDS)
        write_png(self.root / 'media' / 'bg.png', 1080, 1920, (40, 40, 200))
        (self.root / 'subs' / 'karaoke.ass').write_text(ASS_TEXT, encoding='utf-8')
        self.preset, self.output = production_preset(drop_loudness)
        self.log = tmp_path / 'calls.jsonl'
        self.script = tmp_path / 'prefix.py'
        self.script.write_text(PREFIX, encoding='utf-8')
        payload = {
            'render_package_id': 'pkg-1',
            'package_fingerprint': 'a' * 64,
            'production_snapshot_ref': 'snap-1',
            'script_version_ref': 'script-1',
            'production_plan_ref': 'plan-1',
            'preset_revision_ref': 'preset-1',
            'voice_artifact_ref': 'ref-voice',
            'word_timing_ref': 'ref-timing',
            'output_metadata_revision': 'meta-1',
            'output_profile_revision': 'profile-1',
            'language_validation_refs': ['lang-1'],
            'input_artifacts': [artifact('ref-bg', 'image/png')],
            'timeline': {'duration_ms': self.voice_ms, 'segments': [{'start_ms': 0, 'end_ms': self.voice_ms, 'visual_asset_refs': ['ref-bg']}]},
            'hook_placement': hook_placement(),
            'subtitle_config': {'karaoke': True},
            'mix_plan': {},
            'allowed_fallbacks': [],
            'materialization_manifest': {
                'ref-bg': {'local_ref': 'media/bg.png'},
                'ref-hook': {'local_ref': 'media/hook.wav'},
                'ref-voice': {'local_ref': 'media/voice.wav'},
                'ref-ass': {'local_ref': 'subs/karaoke.ass'},
            },
            'output_path_ref': 'ref-output',
        }
        self.record = validate_render_package_payload(payload)

    def spec(self, name):
        o = self.output
        return build_render_command(
            self.record, self.preset,
            OutputProfile(width=o['width'], height=o['height'], fps=o['fps'], video_codec=o['video_codec'], audio_codec=o['audio_codec'], container=o['container'], pixel_format=o['pixel_format'], encoder='libx264', bitrate=None),
            'ref-ass', ToolIdentity(name='ffmpeg', version='2025-03-13', build='gyan-essentials', executable=FFMPEG),
            MaterializedPaths(staging_root=str(self.root), output_path=f'out/{name}.mp4', thumbnail_path='out/thumb.jpg'),
            voice_duration_ms=self.voice_ms,
        )

    def renderer(self, mode='pass', **kwargs):
        return RealFfmpegRenderer(
            ffmpeg_path=FFMPEG, lock_path=DEFAULT_LOCK_PATH,
            command_prefix=(sys.executable, str(self.script), str(self.log), mode),
            timeout_seconds=kwargs.pop('timeout_seconds', 300), **kwargs,
        )

    def run(self, spec, mode='pass', **kwargs):
        return self.renderer(mode, **kwargs).run(spec, lease=LEASE)

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding='utf-8').splitlines() if line]


def test_profile_target_is_the_approved_decision():
    assert target() == (-16, -1.5, 1.5)


def test_synthetic_voice_is_quiet_before_normalisation(tmp_path):
    rig = Rig(tmp_path, 4.0)
    assert abs(loudness_of(rig.root / 'media' / 'voice.wav').integrated_lufs - SOURCE_LUFS) <= 0.5


def test_mp4_lands_on_the_profile_loudness_in_one_render_command(tmp_path):
    rig = Rig(tmp_path, 4.0)
    spec = rig.spec('final')
    outcome = rig.run(spec)
    assert outcome.status is RendererStatus.SUCCEEDED, outcome.error
    lufs, ceiling, tolerance = target()
    stats = loudness_of(outcome.output_ref)
    assert abs(stats.integrated_lufs - lufs) <= tolerance
    assert stats.true_peak_dbtp <= ceiling
    calls = rig.calls()
    assert len(calls) == 1
    assert calls[0][-1].endswith('.part')
    assert value_after(calls[0], '-f') == 'mp4'
    assert pathlib.PurePath(calls[0][0]) == pathlib.PurePath(FFMPEG)
    m = renderer_module.measure_loudness(FFMPEG, spec.argv, timeout_seconds=120)
    graph = value_after(calls[0], '-filter_complex')
    assert f':measured_I={m.input_i:.2f}:measured_TP={m.input_tp:.2f}:measured_LRA={m.input_lra:.2f}:measured_thresh={m.input_thresh:.2f}:offset={m.target_offset:.2f}:linear=true' in graph
    assert 'print_format' not in graph


def test_prefix_that_drops_stderr_still_measures(tmp_path):
    rig = Rig(tmp_path, 4.0)
    outcome = rig.run(rig.spec('final'), mode='quiet')
    assert outcome.status is RendererStatus.SUCCEEDED, outcome.error
    lufs, ceiling, tolerance = target()
    stats = loudness_of(outcome.output_ref)
    assert abs(stats.integrated_lufs - lufs) <= tolerance
    assert stats.true_peak_dbtp <= ceiling
    assert len(rig.calls()) == 1


def test_voice_not_a_multiple_of_100_ms_keeps_full_aac_packets_and_the_tail(tmp_path):
    rig = Rig(tmp_path, 8.008)
    outcome = rig.run(rig.spec('final'))
    assert outcome.status is RendererStatus.SUCCEEDED, outcome.error
    packets = ffprobe(['-select_streams', 'a:0', '-show_entries', 'packet=pts,duration'], outcome.output_ref)['packets']
    sizes = [int(p['duration']) for p in packets]
    assert len(sizes) > 100 and all(s == 1024 for s in sizes[:-1])
    end = (int(packets[-1]['pts']) + sizes[-1]) / RATE
    assert abs(end - 8.008) <= 0.05
    assert [t for t in silence_starts(outcome.output_ref) if 0.15 < t < 8.008 - 0.15] == []


def test_peaky_voice_stays_under_the_ceiling_and_is_raised_at_least_10_lu(tmp_path):
    rig = Rig(tmp_path, 6.0, kind='peaky')
    spec = rig.spec('final')
    lufs, ceiling, tolerance = target()
    m = renderer_module.measure_loudness(FFMPEG, spec.argv, timeout_seconds=120)
    assert m.input_tp + (lufs - m.input_i) > ceiling + 3 and lufs - m.input_i >= 10
    outcome = rig.run(spec)
    assert outcome.status is RendererStatus.SUCCEEDED, outcome.error
    stats = loudness_of(outcome.output_ref)
    assert stats.true_peak_dbtp <= ceiling
    assert stats.integrated_lufs - m.input_i >= 10


def test_two_attempts_of_one_spec_give_the_same_measurement_and_pcm(tmp_path):
    rig = Rig(tmp_path, 8.008)
    first, second = rig.spec('a'), rig.spec('b')
    assert first.spec_fingerprint == second.spec_fingerprint
    assert renderer_module.measure_loudness(FFMPEG, first.argv, timeout_seconds=120) == renderer_module.measure_loudness(FFMPEG, second.argv, timeout_seconds=120)
    one, two = rig.run(first), rig.run(second)
    assert one.status is RendererStatus.SUCCEEDED, one.error
    assert two.status is RendererStatus.SUCCEEDED, two.error
    assert pcm(one.output_ref) == pcm(two.output_ref)
    plain = Rig(tmp_path / 'plain', 8.008, drop_loudness=True)
    base = plain.run(plain.spec('final'))
    assert base.status is RendererStatus.SUCCEEDED, base.error
    for path in (one.output_ref, two.output_ref, base.output_ref):
        assert all(abs(d - 8.008) <= 0.05 for d in durations(path))


def test_preset_without_a_loudness_rule_runs_one_command_and_keeps_the_level(tmp_path):
    rig = Rig(tmp_path, 4.0, drop_loudness=True)
    outcome = rig.run(rig.spec('final'))
    assert outcome.status is RendererStatus.SUCCEEDED, outcome.error
    assert len(rig.calls()) == 1
    assert 'loudnorm' not in value_after(rig.calls()[0], '-filter_complex')
    assert abs(loudness_of(outcome.output_ref).integrated_lufs - SOURCE_LUFS) <= 2.0


def test_silent_mix_is_loudness_measure_failed_and_writes_nothing(tmp_path):
    rig = Rig(tmp_path, 3.0, kind='silent')
    outcome = rig.run(rig.spec('final'))
    assert outcome.status is RendererStatus.FAILED
    assert outcome.error.startswith('loudness_measure_failed')
    assert rig.calls() == []
    assert list((rig.root / 'out').iterdir()) == []


@pytest.mark.parametrize('case', ['two', 'video_chain', 'unmapped'])
def test_spec_shapes_the_two_pass_cannot_serve_run_nothing(tmp_path, case):
    rig = Rig(tmp_path, 3.0)
    spec = rig.spec('final')
    argv = list(spec.argv)
    graph_index = argv.index('-filter_complex') + 1
    graph = argv[graph_index]
    loud = re.search(r'loudnorm=[^,\[]*', graph).group(0)
    if case == 'two':
        graph = graph.replace('asetpts=N/SR/TB[aout]', loud + ',asetpts=N/SR/TB[aout]')
    elif case == 'video_chain':
        graph = graph.replace(',' + loud, '').replace(',setsar=1,', ',setsar=1,' + loud + ',', 1)
    else:
        argv[argv.index('[aout]')] = '[unused]'
    argv[graph_index] = graph
    bad = dataclasses.replace(spec, argv=tuple(argv))
    outcome = rig.run(bad)
    assert outcome.status is RendererStatus.FAILED
    assert outcome.error == 'spec_shape_invalid'
    assert rig.calls() == []
    assert list((rig.root / 'out').iterdir()) == []


def test_measure_pass_argv_goes_straight_to_the_pinned_ffmpeg(tmp_path):
    rig = Rig(tmp_path, 3.0)
    spec = rig.spec('final')
    argv = renderer_module.build_measure_argv(spec.argv, FFMPEG)
    assert argv[0] == FFMPEG and argv[-3:] == ['-f', 'null', '-']
    inputs = [argv[i + 1] for i, item in enumerate(argv) if item == '-i']
    assert inputs == [spec.argv[i + 1] for i, item in enumerate(spec.argv) if item == '-i']
    graph = value_after(argv, '-filter_complex')
    chains = graph.split(chr(59))
    assert all(re.match(r'\[\d+:a:\d+\]', chain) for chain in chains)
    assert ':print_format=json' in graph and 'subtitles' not in graph and 'overlay' not in graph
    assert argv.count('-map') == 1 and value_after(argv, '-map') == '[aout]'
    at = argv.index('-map')
    assert argv[at + 2:at + 4] == ['-t', '3.000']
    assert argv.count('-shortest') == 0
    plain = Rig(tmp_path / 'plain', 3.0, drop_loudness=True)
    assert renderer_module.build_measure_argv(plain.spec('final').argv, FFMPEG) is None
    outcome = rig.run(spec)
    assert outcome.status is RendererStatus.SUCCEEDED, outcome.error
    assert [c for c in rig.calls() if 'null' in c] == []


def test_parse_loudness_json_accepts_the_loudnorm_block_and_rejects_the_rest():
    def block(**changes):
        data = {'input_i': '-22.20', 'input_tp': '-3.00', 'input_lra': '5.20', 'input_thresh': '-32.70', 'output_i': '-16.0', 'target_offset': '0.50', **changes}
        return '[Parsed_loudnorm_1 @ 0000]' + chr(10) + json.dumps(data)

    m = renderer_module.parse_loudness_json(block())
    assert (m.input_i, m.input_tp, m.input_lra, m.input_thresh, m.target_offset) == (-22.2, -3.0, 5.2, -32.7, 0.5)
    missing = {'input_tp': '-3.00', 'input_lra': '5.20', 'input_thresh': '-32.70', 'target_offset': '0.50'}
    bad = ['', 'no json here', '{broken', '{input_i: 1}', block(input_i='-inf'), block(input_tp='nan'), block(input_lra='120'),
           block(target_offset='abc'), block(input_thresh=None), json.dumps(missing)]
    for text in bad:
        with pytest.raises(renderer_module.LoudnessMeasureFailed):
            renderer_module.parse_loudness_json(text)


def test_measure_pass_shares_the_render_timeout(tmp_path):
    rig = Rig(tmp_path, 3.0)
    with pytest.raises(RendererTimeout):
        rig.run(rig.spec('final'), timeout_seconds=0.01)
    assert rig.calls() == []
