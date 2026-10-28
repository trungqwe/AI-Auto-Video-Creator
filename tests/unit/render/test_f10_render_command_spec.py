"""F-10: structured render command specification (CT-RND-004).

coveredIds: CT-RND-004, TST-SEC-INV-012, TST-SEC-INV-020
"""
import dataclasses
import json
import math
import pathlib
import re
import struct
import subprocess
import wave
import zlib

import pytest

from render.adapters.real_ffmpeg_renderer import DEFAULT_FFMPEG_PATH, DEFAULT_LOCK_PATH, build_final_argv, verify_ffmpeg_pin
from render.adapters.real_ffprobe_probe import DEFAULT_FFPROBE_PATH
from render.adapters.real_output_inspector import ssim_between
from render.domain.package_contract import validate_render_package_payload
from render.domain.preset import build_preset_revision
from render.domain.render_command import (
    ASSET_NOT_MATERIALIZED,
    INPUT_NOT_READY,
    INVALID_INPUT,
    PATH_OUTSIDE_STAGING_ROOT,
    UNSAFE_ARGUMENT,
    MaterializedPaths,
    OutputProfile,
    RenderCommandRejected,
    RenderCommandSpec,
    ToolIdentity,
    build_render_command,
    build_thumbnail_command,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'src' / 'render' / 'domain' / 'render_command.py'
BACKSLASH = chr(92)
CANARY = 'CANARY-7f3a9c-SECRET'
STAGING = 'C:/staging/job1'
TOOL_PATH = 'C:/tools/ffmpeg.exe'
PROFILE_FIELDS = ('width', 'height', 'fps', 'video_codec', 'audio_codec', 'container', 'pixel_format', 'encoder')
TEXT_FIELDS = PROFILE_FIELDS[3:]
UNSAFE_TEXTS = (
    'a;b', 'a|b', 'a&b', 'a<b', 'a>b', 'a' + chr(96) + 'b', 'a$b',
    'a' + chr(10) + 'b', 'a' + chr(13) + 'b', 'http://x/y', 'a/../b', '..',
)
OUTSIDE_PATHS = ('C:/other/a.mp4', 'D:/staging/job1/a.mp4', '//server/share/a.mp4', '/abs/a.mp4', 'C:rel/a.mp4', 'C:/staging/job1')


def manifest(**extra):
    value = {
        'ref-visual-a': {'local_ref': 'media/a.mp4'},
        'ref-visual-b': {'local_ref': 'media/b.mp4'},
        'ref-voice': {'local_ref': 'media/voice.wav'},
        'ref-ass': {'local_ref': 'subs/karaoke.ass'},
    }
    value.update(extra)
    return value


def manifest_with(ref, local_ref):
    return manifest(**{ref: {'local_ref': local_ref}})


def artifact(ref, media_type):
    return {'artifact_version_id': ref, 'sha256': 'c' * 64, 'size_bytes': 1, 'media_type': media_type}


def hook_placement(**changes):
    value = {
        'visual_hook_ref': 'ref-visual-a',
        'audio_hook_ref': 'ref-voice',
        'thumbnail_ref': 'ref-visual-a',
        'hook_time_range': {'start_ms': 0, 'end_ms': 3000},
        'thumbnail_time_range': {'start_ms': 500, 'end_ms': 1500},
    }
    value.update(changes)
    return value


def payload(**changes):
    value = {
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
        'input_artifacts': [artifact('ref-visual-a', 'image/png'), artifact('ref-visual-b', 'video/mp4')],
        'timeline': {'segments': [
            {'start_ms': 0, 'end_ms': 3000, 'visual_asset_refs': ['ref-visual-a']},
            {'start_ms': 3000, 'end_ms': 6000, 'visual_asset_refs': ['ref-visual-b']},
        ]},
        'hook_placement': hook_placement(),
        'subtitle_config': {'karaoke': True},
        'mix_plan': {},
        'allowed_fallbacks': [],
        'materialization_manifest': manifest(),
        'output_path_ref': 'ref-output',
    }
    value.update(changes)
    return value


def record(**changes):
    return validate_render_package_payload(payload(**changes))


def preset(revision=1, note='x'):
    section = {'note': note}
    return build_preset_revision({
        'preset_key': 'p1', 'revision': revision, 'visual_rhythm': section, 'layout_rules': section,
        'thumbnail_overlay_style': section, 'typography_karaoke_style': section, 'hook_treatment': section,
        'mix_rules': section, 'color_effect_rules': section, 'output_profile_ref': 'profile-1',
        'fallback_constraints': section, 'compatibility_requirements': section,
    })


def profile(**changes):
    values = {
        'width': 1080, 'height': 1920, 'fps': 30, 'video_codec': 'h264', 'audio_codec': 'aac',
        'container': 'mp4', 'pixel_format': 'yuv420p', 'encoder': 'libx264', 'bitrate': None,
    }
    values.update(changes)
    return OutputProfile(**values)


def tool(**changes):
    values = {'name': 'ffmpeg', 'version': '6.1', 'build': 'test-build', 'executable': TOOL_PATH}
    values.update(changes)
    return ToolIdentity(**values)


def materialized(**changes):
    values = {'staging_root': STAGING, 'output_path': 'out/final.mp4', 'thumbnail_path': 'out/thumb.jpg'}
    values.update(changes)
    return MaterializedPaths(**values)


def staged(relative):
    return str(pathlib.PureWindowsPath(STAGING) / relative)


def render(**overrides):
    args = {'record': record(), 'preset': preset(), 'profile': profile(), 'ass_ref': 'ref-ass', 'tool_identity': tool(), 'materialized': materialized()}
    args.update(overrides)
    return build_render_command(**args)


def thumbnail(**overrides):
    args = {'record': record(), 'profile': profile(), 'tool_identity': tool(), 'materialized': materialized()}
    args.update(overrides)
    return build_thumbnail_command(**args)


def value_after(argv, flag):
    assert flag in argv
    return argv[argv.index(flag) + 1]


def assert_rejected(call, code, reason=None):
    with pytest.raises(RenderCommandRejected) as info:
        call()
    assert info.value.code == code
    if reason is not None:
        assert info.value.reason == reason


def test_render_command_structure():
    spec = render()
    assert isinstance(spec, RenderCommandSpec)
    assert spec.kind == 'render'
    assert isinstance(spec.argv, tuple)
    assert all(isinstance(item, str) for item in spec.argv)
    assert spec.argv[:1] == (TOOL_PATH,)
    inputs = [spec.argv[index + 1] for index, item in enumerate(spec.argv) if item == '-i']
    assert inputs == [staged('media/a.mp4'), staged('media/b.mp4'), staged('media/voice.wav'), staged('media/a.mp4'), staged('media/voice.wav')]
    maps = [spec.argv[index + 1] for index, item in enumerate(spec.argv) if item == '-map']
    assert maps == ['[vout]', '[aout]']
    assert value_after(spec.argv, '-c:v') == 'libx264'
    assert value_after(spec.argv, '-c:a') == 'aac'
    assert value_after(spec.argv, '-f') == 'mp4'
    assert '-n' in spec.argv and '-y' not in spec.argv
    assert spec.argv[-1] == staged('out/final.mp4')
    assert spec.tool_identity == tool()


def test_filter_graph_is_built_from_structured_parts():
    graph = value_after(render().argv, '-filter_complex')
    chain = 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30,format=yuv420p'
    ass = 'ass=filename=C' + BACKSLASH + ':/staging/job1/subs/karaoke.ass[vout]'
    expected = ';'.join([
        f'[0:v:0]{chain}[v0]',
        f'[1:v:0]{chain}[v1]',
        '[4:a:0]adelay=0:all=1[ahook]',
        '[2:a:0][ahook]amix=inputs=2:duration=first:normalize=0[aout]',
        '[v0][v1]concat=n=2:v=1:a=0,tpad=stop_mode=clone:stop=-1[base]',
        f'[3:v:0]{chain},setpts=PTS-STARTPTS+0.000/TB[vhook]',
        "[base][vhook]overlay=eof_action=repeat:enable='between(t,0.000,3.000)'," + ass,
    ])
    assert graph == expected
    assert graph.count(chr(59)) == 6


def test_profile_values_come_only_from_the_profile_input():
    other = profile(width=720, height=1280, fps=24, video_codec='vcodec2', audio_codec='acodec2', container='cont2', pixel_format='pix2', encoder='enc2')
    spec = render(profile=other)
    assert '[0:v:0]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1,fps=24,format=pix2[v0]' in value_after(spec.argv, '-filter_complex')
    assert value_after(spec.argv, '-c:v') == 'enc2'
    assert value_after(spec.argv, '-c:a') == 'acodec2'
    assert value_after(spec.argv, '-f') == 'cont2'
    assert not any('1080' in item or '1920' in item for item in spec.argv)
    assert 'fps=29.97' in value_after(render(profile=profile(fps=29.97)).argv, '-filter_complex')


def test_bitrate_is_optional():
    assert '-b:v' not in render().argv
    assert value_after(render(profile=profile(bitrate=4000000)).argv, '-b:v') == '4000000'


def test_spec_has_no_shell_key_or_whole_command_string():
    spec = render()
    names = {item.name for item in dataclasses.fields(spec)}
    assert names == {'kind', 'argv', 'redacted_argv', 'spec_fingerprint', 'tool_identity'}
    assert not any('shell' in name or 'command' in name for name in names)
    data = json.loads(spec.to_json())
    assert set(data) == {'kind', 'redacted_argv', 'spec_fingerprint', 'tool_identity'}
    assert data == spec.to_dict()
    assert 'shell' not in spec.to_json().lower()
    assert spec.redacted_argv and ' '.join(spec.redacted_argv) not in spec.to_json()


def test_redacted_argv_replaces_every_path_with_a_token():
    spec = render()
    assert len(spec.redacted_argv) == len(spec.argv)
    assert spec.redacted_argv[:1] == ('{tool}',)
    for token in ('{asset:0}', '{asset:1}', '{voice}', '{hook_visual}', '{hook_audio}', '{output}'):
        assert token in spec.redacted_argv
    changed = [index for index, pair in enumerate(zip(spec.argv, spec.redacted_argv)) if pair[0] != pair[1]]
    assert len(changed) == 8
    joined = chr(10).join(spec.redacted_argv)
    assert 'ass=filename={ass}' in joined
    assert 'staging' not in joined and 'ffmpeg.exe' not in joined and 'karaoke.ass' not in joined


def test_fingerprint_binds_inputs_but_not_attempt_paths():
    base = render()
    assert re.fullmatch('[0-9a-f]{64}', base.spec_fingerprint)
    assert render() == base
    assert render(profile=profile(width=720)).spec_fingerprint != base.spec_fingerprint
    assert render(record=record(package_fingerprint='b' * 64)).spec_fingerprint != base.spec_fingerprint
    assert render(preset=preset(revision=2)).spec_fingerprint != base.spec_fingerprint
    assert render(tool_identity=tool(version='7.0')).spec_fingerprint != base.spec_fingerprint
    moved = render(materialized=materialized(staging_root='C:/staging/job2'))
    assert moved.spec_fingerprint == base.spec_fingerprint
    assert moved.argv != base.argv


def test_text_metadata_never_reaches_argv_and_subtitles_go_only_through_ass():
    evil = '; rm -rf / | $(x) && http://evil.example'
    rec = record(
        hook_placement=hook_placement(title=evil),
        subtitle_config={'karaoke': True, 'title': evil, 'text': evil},
        mix_plan={'caption': evil},
        materialization_manifest=manifest(**{'ref-visual-a': {'local_ref': 'media/a.mp4', 'title': evil}}),
    )
    main = render(record=rec, preset=preset(note=evil))
    for spec in (main, thumbnail(record=rec)):
        text = ' '.join(spec.argv) + ' ' + ' '.join(spec.redacted_argv)
        assert spec.argv
        assert 'rm -rf' not in text and 'drawtext' not in text and 'evil.example' not in text
    assert any('ass=filename=' in item for item in main.argv)


def canary_record():
    return record(
        hook_placement=hook_placement(title=CANARY),
        subtitle_config={'karaoke': True, 'title': CANARY},
        mix_plan={'note': CANARY},
        materialization_manifest=manifest(**{'ref-visual-a': {'local_ref': 'media/a.mp4', 'title': CANARY}}),
    )


def test_canary_metadata_never_appears_in_any_view():
    specs = (render(record=canary_record(), preset=preset(note=CANARY)), thumbnail(record=canary_record()))
    for spec in specs:
        assert spec.redacted_argv
        views = [repr(spec), str(spec), ' '.join(spec.redacted_argv), ' '.join(spec.argv), spec.to_json(), str(spec.to_dict()), str(dataclasses.asdict(spec)), repr(spec.tool_identity)]
        for view in views:
            assert CANARY not in view


def test_canary_in_a_path_is_redacted_in_every_view_except_argv():
    local = 'media/' + CANARY + '/a.mp4'
    spec = render(record=record(materialization_manifest=manifest_with('ref-visual-a', local)))
    assert any(CANARY in item for item in spec.argv)
    for view in (repr(spec), str(spec), ' '.join(spec.redacted_argv), spec.to_json(), str(spec.to_dict()), repr(spec.tool_identity)):
        assert CANARY not in view


def test_output_profile_is_frozen_and_every_value_is_an_input():
    item = OutputProfile()
    assert [entry.name for entry in dataclasses.fields(item)] == [*PROFILE_FIELDS, 'bitrate']
    assert all(getattr(item, name) is None for name in (*PROFILE_FIELDS, 'bitrate'))
    with pytest.raises(dataclasses.FrozenInstanceError):
        item.width = 1


@pytest.mark.parametrize('name', PROFILE_FIELDS)
def test_missing_profile_field_is_input_not_ready(name):
    assert_rejected(lambda: render(profile=profile(**{name: None})), INPUT_NOT_READY, f'missing_profile.{name}')
    assert_rejected(lambda: thumbnail(profile=profile(**{name: None})), INPUT_NOT_READY, f'missing_profile.{name}')


def test_empty_profile_is_input_not_ready():
    assert_rejected(lambda: render(profile=OutputProfile()), INPUT_NOT_READY)
    assert_rejected(lambda: thumbnail(profile=OutputProfile()), INPUT_NOT_READY)


@pytest.mark.parametrize('changes', [
    {'width': True}, {'width': 0}, {'width': -1}, {'width': 1080.0}, {'width': '1080'}, {'height': 0}, {'height': False},
    {'fps': 0}, {'fps': -1}, {'fps': float('nan')}, {'fps': float('inf')}, {'fps': '30'}, {'fps': True},
    {'bitrate': 0}, {'bitrate': 1.5}, {'bitrate': '4M'}, {'bitrate': True},
    {'video_codec': 5}, {'encoder': 'bad encoder'}, {'container': '-f'}, {'pixel_format': ''}, {'audio_codec': '   '},
])
def test_invalid_profile_value_is_invalid_input(changes):
    assert_rejected(lambda: render(profile=profile(**changes)), INVALID_INPUT)


@pytest.mark.parametrize('name', TEXT_FIELDS)
@pytest.mark.parametrize('text', UNSAFE_TEXTS)
def test_unsafe_profile_text_is_unsafe_argument(name, text):
    assert_rejected(lambda: render(profile=profile(**{name: text})), UNSAFE_ARGUMENT, f'profile.{name}')


def test_missing_inputs_are_input_not_ready():
    assert_rejected(lambda: render(record=None), INPUT_NOT_READY, 'missing_record')
    assert_rejected(lambda: render(preset=None), INPUT_NOT_READY, 'missing_preset')
    assert_rejected(lambda: render(profile=None), INPUT_NOT_READY, 'missing_profile')
    assert_rejected(lambda: render(ass_ref=None), INPUT_NOT_READY, 'missing_ass_ref')
    assert_rejected(lambda: render(tool_identity=None), INPUT_NOT_READY, 'missing_tool_identity')
    assert_rejected(lambda: render(materialized=None), INPUT_NOT_READY, 'missing_materialized')
    assert_rejected(lambda: render(materialized=materialized(staging_root=None)), INPUT_NOT_READY, 'missing_materialized.staging_root')
    assert_rejected(lambda: render(materialized=materialized(output_path=None)), INPUT_NOT_READY, 'missing_materialized.output_path')
    assert_rejected(lambda: thumbnail(record=None), INPUT_NOT_READY, 'missing_record')
    assert_rejected(lambda: thumbnail(materialized=materialized(thumbnail_path=None)), INPUT_NOT_READY, 'missing_materialized.thumbnail_path')


def test_wrong_types_are_invalid_input():
    assert_rejected(lambda: render(record={}), INVALID_INPUT, 'invalid_record')
    assert_rejected(lambda: render(preset=object()), INVALID_INPUT, 'invalid_preset')
    assert_rejected(lambda: render(profile={}), INVALID_INPUT, 'invalid_profile')
    assert_rejected(lambda: render(tool_identity={}), INVALID_INPUT, 'invalid_tool_identity')
    assert_rejected(lambda: render(materialized={}), INVALID_INPUT, 'invalid_materialized')
    assert_rejected(lambda: render(ass_ref=5), INVALID_INPUT, 'invalid_ass_ref')


@pytest.mark.parametrize('name', ('name', 'version', 'build', 'executable'))
def test_tool_identity_fields_are_required_and_safe(name):
    assert_rejected(lambda: render(tool_identity=tool(**{name: None})), INPUT_NOT_READY, f'missing_tool_identity.{name}')
    assert_rejected(lambda: render(tool_identity=tool(**{name: 'a;b'})), UNSAFE_ARGUMENT, f'tool_identity.{name}')
    assert_rejected(lambda: render(tool_identity=tool(**{name: 'http://x'})), UNSAFE_ARGUMENT, f'tool_identity.{name}')


@pytest.mark.parametrize('text', UNSAFE_TEXTS)
def test_unsafe_argument_text_is_rejected_everywhere(text):
    for ref in ('ref-visual-a', 'ref-voice', 'ref-ass'):
        assert_rejected(lambda: render(record=record(materialization_manifest=manifest_with(ref, text))), UNSAFE_ARGUMENT)
    assert_rejected(lambda: render(materialized=materialized(output_path=text)), UNSAFE_ARGUMENT, 'materialized.output_path')
    assert_rejected(lambda: thumbnail(materialized=materialized(thumbnail_path=text)), UNSAFE_ARGUMENT, 'materialized.thumbnail_path')
    assert_rejected(lambda: render(materialized=materialized(staging_root=text)), UNSAFE_ARGUMENT, 'materialized.staging_root')


@pytest.mark.parametrize('path', OUTSIDE_PATHS)
def test_paths_outside_the_staging_root_are_rejected(path):
    for ref in ('ref-visual-a', 'ref-voice', 'ref-ass'):
        assert_rejected(lambda: render(record=record(materialization_manifest=manifest_with(ref, path))), PATH_OUTSIDE_STAGING_ROOT)
    assert_rejected(lambda: render(materialized=materialized(output_path=path)), PATH_OUTSIDE_STAGING_ROOT, 'materialized.output_path')
    assert_rejected(lambda: thumbnail(materialized=materialized(thumbnail_path=path)), PATH_OUTSIDE_STAGING_ROOT, 'materialized.thumbnail_path')


def test_relative_staging_root_rejects_every_path():
    assert_rejected(lambda: render(materialized=materialized(staging_root='staging/job1')), PATH_OUTSIDE_STAGING_ROOT)


def test_absolute_local_ref_inside_the_staging_root_is_accepted():
    spec = render(record=record(materialization_manifest=manifest_with('ref-visual-a', 'C:/staging/job1/media/a.mp4')))
    assert staged('media/a.mp4') in spec.argv


def with_segments(*spans, refs=('ref-visual-a', 'ref-visual-b')):
    return {'segments': [{'start_ms': start, 'end_ms': end, 'visual_asset_refs': [refs[index % len(refs)]]} for index, (start, end) in enumerate(spans)]}


def test_still_image_is_looped_for_the_segment_duration_and_video_is_only_trimmed():
    argv = render().argv
    image, video, voice = argv.index(staged('media/a.mp4')), argv.index(staged('media/b.mp4')), argv.index(staged('media/voice.wav'))
    assert argv[image - 7:image] == ('-loop', '1', '-framerate', '30', '-t', '3.000', '-i')
    assert argv[image + 1:video] == ('-t', '3.000', '-i')
    assert argv[video + 1:voice] == ('-i',)


def test_segment_duration_is_end_minus_start():
    argv = render(record=record(timeline=with_segments((500, 2000), (2000, 4250), (4250, 5484)))).argv
    assert [argv[i + 1] for i, item in enumerate(argv) if item == '-t'] == ['1.500', '2.250', '1.234', '3.000', '3.000', '5.484']
    assert argv.count('-loop') == 3
    assert 'concat=n=3' in value_after(argv, '-filter_complex')


def test_media_type_comes_from_the_input_artifact_with_the_same_ref():
    swapped = record(input_artifacts=[artifact('ref-visual-a', 'video/mp4'), artifact('ref-visual-b', 'image/jpeg'), artifact('ref-other', 'image/png')])
    argv = render(record=swapped).argv
    first, second = argv.index(staged('media/a.mp4')), argv.index(staged('media/b.mp4'))
    assert '-loop' not in argv[:first]
    assert argv[first + 1:second] == ('-loop', '1', '-framerate', '30', '-t', '3.000', '-i')
    assert '-loop' not in render(record=record(input_artifacts=[artifact('ref-other', 'image/png')])).argv


def test_fingerprint_and_redacted_argv_follow_durations_and_media_types():
    base = render()
    longer = render(record=record(timeline=with_segments((0, 3000), (3000, 7000))))
    video_only = render(record=record(input_artifacts=[artifact('ref-visual-a', 'video/mp4'), artifact('ref-visual-b', 'video/mp4')]))
    assert longer.spec_fingerprint != base.spec_fingerprint and video_only.spec_fingerprint != base.spec_fingerprint
    assert '4.000' in longer.redacted_argv
    assert {'-loop', '-shortest', '3.000'} <= set(base.redacted_argv)


def test_every_input_is_normalised_before_concat():
    graph = value_after(render(record=record(timeline=with_segments((0, 1000), (1000, 2000), (2000, 3000)))).argv, '-filter_complex')
    concat = graph.index('concat=')
    assert graph.count('scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30,format=yuv420p') == 4
    for index in range(3):
        assert f'[{index}:v:0]scale=' in graph[:concat] and f'[v{index}]' in graph[:concat]
    base = graph.index('[base]')
    assert 'scale=' not in graph[concat:base] and 'crop=' not in graph[concat:base]
    assert '[4:v:0]scale=' in graph[base:]
    assert '[v0][v1][v2]concat=n=3:v=1:a=0' in graph


def test_tpad_follows_concat_and_precedes_ass_and_shortest_is_added_next_to_segment_t():
    argv = render().argv
    graph = value_after(argv, '-filter_complex')
    assert graph.index('concat=') < graph.index('tpad=stop_mode=clone:stop=-1') < graph.index('ass=filename=')
    assert graph.index('tpad=stop_mode=clone:stop=-1') < graph.index('overlay=') < graph.index('ass=filename=')
    assert graph.endswith('[vout]')
    assert '-shortest' in argv and argv.index('-shortest') > argv.index('-filter_complex')
    assert argv.count('-t') == 5


@pytest.mark.parametrize('segment,reason', [
    ({'end_ms': 3000}, 'missing_timeline.segments[0].start_ms'),
    ({'start_ms': 0}, 'missing_timeline.segments[0].end_ms'),
    ({'start_ms': '0', 'end_ms': 3000}, 'invalid_timeline.segments[0].start_ms'),
    ({'start_ms': 0, 'end_ms': 3000.0}, 'invalid_timeline.segments[0].end_ms'),
    ({'start_ms': 0, 'end_ms': True}, 'invalid_timeline.segments[0].end_ms'),
])
def test_segment_bounds_missing_or_not_int_are_input_not_ready(segment, reason):
    timeline = {'segments': [{**segment, 'visual_asset_refs': ['ref-visual-a']}]}
    assert_rejected(lambda: render(record=record(timeline=timeline)), INPUT_NOT_READY, reason)


@pytest.mark.parametrize('span', [(3000, 3000), (3000, 2000)])
def test_segment_with_end_not_after_start_is_invalid_input(span):
    assert_rejected(lambda: render(record=record(timeline=with_segments((0, 1000), span))), INVALID_INPUT, 'invalid_timeline.segments[1].duration')


def test_thumbnail_command_is_unchanged():
    assert thumbnail().argv == (TOOL_PATH, '-hide_banner', '-nostdin', '-n', '-ss', '1.000', '-i', staged('out/final.mp4'), '-frames:v', '1', '-vf', 'scale=1080:1920', staged('out/thumb.jpg'))


def timeline_of(refs):
    return {'segments': [{'start_ms': 0, 'end_ms': 3000, 'visual_asset_refs': refs}]}


def test_assets_outside_the_manifest_are_rejected():
    for refs in (['ref-unknown'], ['http://evil.example/a.mp4'], ['ref-visual-a', 'ref-unknown']):
        assert_rejected(lambda: render(record=record(timeline=timeline_of(refs))), ASSET_NOT_MATERIALIZED, 'timeline.segments[0].visual_asset_refs')
    assert_rejected(lambda: render(record=record(voice_artifact_ref='ref-other')), ASSET_NOT_MATERIALIZED, 'voice_artifact_ref')
    for ass_ref in ('ref-other', 'https://evil.example/x.ass'):
        assert_rejected(lambda: render(ass_ref=ass_ref), ASSET_NOT_MATERIALIZED, 'ass_ref')


def test_malformed_manifest_entries_and_timeline():
    assert_rejected(lambda: render(record=record(materialization_manifest=manifest(**{'ref-voice': 'x'}))), INVALID_INPUT, 'invalid_voice_artifact_ref')
    assert_rejected(lambda: render(record=record(materialization_manifest=manifest(**{'ref-voice': {}}))), INPUT_NOT_READY, 'missing_voice_artifact_ref.local_ref')
    assert_rejected(lambda: render(record=record(timeline={})), INPUT_NOT_READY, 'missing_timeline.segments')
    assert_rejected(lambda: render(record=record(timeline={'segments': []})), INPUT_NOT_READY, 'missing_timeline.segments')
    assert_rejected(lambda: render(record=record(timeline={'segments': [{'start_ms': 0, 'end_ms': 1}]})), INPUT_NOT_READY, 'missing_timeline.segments[0].visual_asset_refs')
    assert_rejected(lambda: render(record=record(timeline=timeline_of([5]))), INVALID_INPUT, 'invalid_timeline.segments[0].visual_asset_refs')


@pytest.mark.parametrize('local_ref', ('subs/a b.ass', 'subs/a,b.ass', 'subs/a' + chr(39) + 'b.ass', 'subs/a=b.ass', 'subs/a[b.ass', 'subs/a]b.ass'))
def test_ass_path_must_be_safe_inside_a_filter_graph(local_ref):
    assert_rejected(lambda: render(record=record(materialization_manifest=manifest_with('ref-ass', local_ref))), UNSAFE_ARGUMENT, 'ass_ref.local_ref')


def test_subtitle_file_must_be_an_ass_file():
    assert_rejected(lambda: render(record=record(materialization_manifest=manifest_with('ref-ass', 'subs/karaoke.srt'))), INVALID_INPUT, 'invalid_ass_ref')


def test_thumbnail_command_uses_the_middle_of_the_thumbnail_range():
    spec = thumbnail()
    assert spec.kind == 'thumbnail'
    assert spec.argv[:1] == (TOOL_PATH,)
    assert value_after(spec.argv, '-ss') == '1.000'
    assert value_after(spec.argv, '-i') == staged('out/final.mp4')
    assert value_after(spec.argv, '-frames:v') == '1'
    assert value_after(spec.argv, '-vf') == 'scale=1080:1920'
    assert spec.argv[-1] == staged('out/thumb.jpg')
    assert spec.redacted_argv[:1] == ('{tool}',)
    assert spec.redacted_argv[-1] == '{thumbnail}' and '{video}' in spec.redacted_argv
    assert thumbnail().spec_fingerprint == spec.spec_fingerprint != render().spec_fingerprint


@pytest.mark.parametrize('start,end', [(0, 1), (500, 1500), (1234, 2999), (2000, 3000), (999, 1000)])
def test_thumbnail_moment_lies_inside_the_thumbnail_range(start, end):
    rec = record(hook_placement=hook_placement(thumbnail_time_range={'start_ms': start, 'end_ms': end}))
    spec = thumbnail(record=rec)
    moment = round(float(value_after(spec.argv, '-ss')) * 1000)
    assert start <= moment < end


@pytest.mark.parametrize('changes,reason', [
    ({'thumbnail_time_range': {'start_ms': 2500, 'end_ms': 3500}}, 'thumbnail_outside_hook_range'),
    ({'thumbnail_time_range': {'start_ms': 0, 'end_ms': 3001}}, 'thumbnail_outside_hook_range'),
    ({'thumbnail_time_range': {'start_ms': 1500, 'end_ms': 1500}}, 'invalid_hook_placement.thumbnail_time_range'),
    ({'thumbnail_time_range': {'start_ms': 1500, 'end_ms': 500}}, 'invalid_hook_placement.thumbnail_time_range'),
    ({'thumbnail_time_range': {'start_ms': True, 'end_ms': 500}}, 'invalid_hook_placement.thumbnail_time_range'),
    ({'thumbnail_time_range': {'start_ms': -1, 'end_ms': 500}}, 'invalid_hook_placement.thumbnail_time_range'),
    ({'thumbnail_time_range': 'x'}, 'invalid_hook_placement.thumbnail_time_range'),
    ({'hook_time_range': {'start_ms': 5, 'end_ms': 5}}, 'invalid_hook_placement.hook_time_range'),
])
def test_invalid_thumbnail_range_is_invalid_input(changes, reason):
    assert_rejected(lambda: thumbnail(record=record(hook_placement=hook_placement(**changes))), INVALID_INPUT, reason)


def test_thumbnail_ranges_are_required():
    for key in ('thumbnail_time_range', 'hook_time_range'):
        trimmed = {name: value for name, value in hook_placement().items() if name != key}
        assert_rejected(lambda: thumbnail(record=record(hook_placement=trimmed)), INPUT_NOT_READY, f'missing_hook_placement.{key}')


def test_spec_and_inputs_are_frozen_and_hide_the_executable_path():
    spec = render()
    for target, name in ((spec, 'argv'), (tool(), 'name'), (materialized(), 'output_path'), (profile(), 'width')):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(target, name, 'x')
    assert 'ffmpeg.exe' not in repr(tool())
    assert isinstance(hash(spec), int)


def test_module_holds_no_profile_values_and_builds_no_command_string():
    source = SOURCE.read_text(encoding='utf-8')
    assert re.search('(?<![0-9])(1080|1920)(?![0-9])', source) is None
    for token in ('h264', 'libx264', 'aac', 'mp4', 'yuv420p'):
        assert token not in source
    for token in ('subprocess', 'shell', 'shlex', 'os.system'):
        assert token not in source
    assert 'request_hash' in source

def thumb_record(kind, **placement):
    return record(
        hook_placement=hook_placement(thumbnail_ref='ref-thumb', thumbnail_time_range={'start_ms': 500, 'end_ms': 1500}, **placement),
        input_artifacts=[artifact('ref-visual-a', 'image/png'), artifact('ref-visual-b', 'video/mp4'), artifact('ref-thumb', kind)],
        materialization_manifest=manifest(**{'ref-thumb': {'local_ref': 'media/thumb.png'}}),
    )


def test_hook_inputs_follow_the_voice_and_are_bounded_to_the_hook_length():
    rec = record(
        hook_placement=hook_placement(
            visual_hook_ref='ref-hook-v',
            audio_hook_ref='ref-hook-a',
            thumbnail_ref='ref-hook-v',
            hook_time_range={'start_ms': 1000, 'end_ms': 3500},
            thumbnail_time_range={'start_ms': 1500, 'end_ms': 2500},
        ),
        input_artifacts=[artifact('ref-visual-a', 'image/png'), artifact('ref-visual-b', 'video/mp4'), artifact('ref-hook-v', 'video/mp4')],
        materialization_manifest=manifest(**{'ref-hook-v': {'local_ref': 'media/hook.mp4'}, 'ref-hook-a': {'local_ref': 'media/hook.wav'}}),
    )
    spec = render(record=rec)
    argv = spec.argv
    voice = argv.index(staged('media/voice.wav'))
    hook_video = argv.index(staged('media/hook.mp4'))
    hook_audio = argv.index(staged('media/hook.wav'))
    assert voice < hook_video < hook_audio
    assert argv[hook_video - 3:hook_video] == ('-t', '2.500', '-i')
    assert argv[hook_audio - 3:hook_audio] == ('-t', '2.500', '-i')
    graph = value_after(argv, '-filter_complex')
    assert '[3:v:0]scale=' in graph
    assert ',setpts=PTS-STARTPTS+1.000/TB[vhook]' in graph
    assert "overlay=eof_action=repeat:enable='between(t,1.000,3.500)'" in graph
    assert '[4:a:0]adelay=1000:all=1[ahook]' in graph
    assert '[2:a:0][ahook]amix=inputs=2:duration=first:normalize=0[aout]' in graph
    assert graph.count('overlay=') == 1
    assert '{hook_visual}' in spec.redacted_argv and '{hook_audio}' in spec.redacted_argv
    assert '{thumbnail_asset}' not in spec.redacted_argv


def test_still_image_hook_is_looped():
    argv = render().argv
    positions = [i for i, item in enumerate(argv) if item == staged('media/a.mp4')]
    assert argv[positions[1] - 7:positions[1]] == ('-loop', '1', '-framerate', '30', '-t', '3.000', '-i')


def test_distinct_thumbnail_is_overlaid_on_top_of_the_hook():
    spec = render(record=thumb_record('image/png'))
    argv = spec.argv
    thumb = argv.index(staged('media/thumb.png'))
    assert argv[thumb - 7:thumb] == ('-loop', '1', '-framerate', '30', '-t', '1.000', '-i')
    graph = value_after(argv, '-filter_complex')
    assert '[5:v:0]scale=' in graph
    assert ',trim=end_frame=1,setpts=PTS-STARTPTS+0.500/TB[vthumb]' in graph
    assert "[base][vhook]overlay=eof_action=repeat:enable='between(t,0.000,3.000)'[vtop]" in graph
    assert "[vtop][vthumb]overlay=eof_action=repeat:enable='between(t,0.500,1.500)',ass=filename=" in graph
    assert graph.count('overlay=') == 2
    assert '{thumbnail_asset}' in render(record=thumb_record('image/png')).redacted_argv


def test_thumbnail_clip_takes_only_its_first_frame():
    argv = render(record=thumb_record('video/mp4')).argv
    thumb = argv.index(staged('media/thumb.png'))
    assert argv[thumb - 3:thumb] == ('-t', '1.000', '-i')
    assert '-loop' not in argv[thumb - 7:thumb]
    assert 'trim=end_frame=1' in value_after(argv, '-filter_complex')


def test_thumbnail_with_the_same_path_as_the_hook_adds_no_second_overlay():
    base = render()
    assert value_after(base.argv, '-filter_complex').count('overlay=') == 1
    assert '{thumbnail_asset}' not in base.redacted_argv
    rec = record(
        hook_placement=hook_placement(thumbnail_ref='ref-thumb'),
        materialization_manifest=manifest(**{'ref-thumb': {'local_ref': 'media/a.mp4'}}),
    )
    same_path = render(record=rec)
    assert value_after(same_path.argv, '-filter_complex').count('overlay=') == 1
    assert '{thumbnail_asset}' not in same_path.redacted_argv


@pytest.mark.parametrize('key', ('visual_hook_ref', 'audio_hook_ref', 'thumbnail_ref'))
def test_hook_ref_outside_the_manifest_is_asset_not_materialized(key):
    assert_rejected(lambda: render(record=record(hook_placement=hook_placement(**{key: 'ref-unknown'}))), ASSET_NOT_MATERIALIZED, key)


@pytest.mark.parametrize('key', ('visual_hook_ref', 'audio_hook_ref', 'thumbnail_ref'))
def test_hook_ref_missing_from_the_placement_is_input_not_ready(key):
    trimmed = {k: v for k, v in hook_placement().items() if k != key}
    assert_rejected(lambda: render(record=record(hook_placement=trimmed)), INPUT_NOT_READY, f'missing_{key}')


@pytest.mark.parametrize('changes,code,reason', [
    ({'hook_time_range': {'start_ms': 5, 'end_ms': 5}}, INVALID_INPUT, 'invalid_hook_placement.hook_time_range'),
    ({'thumbnail_time_range': {'start_ms': 2500, 'end_ms': 3500}}, INVALID_INPUT, 'thumbnail_outside_hook_range'),
    ({'thumbnail_time_range': {'start_ms': 1500, 'end_ms': 500}}, INVALID_INPUT, 'invalid_hook_placement.thumbnail_time_range'),
])
def test_invalid_hook_ranges_are_rejected_by_the_render_command(changes, code, reason):
    assert_rejected(lambda: render(record=record(hook_placement=hook_placement(**changes))), code, reason)


def test_hook_window_is_bound_into_the_fingerprint():
    assert render(record=record(hook_placement=hook_placement(hook_time_range={'start_ms': 0, 'end_ms': 2500}))).spec_fingerprint != render().spec_fingerprint

FFMPEG = DEFAULT_FFMPEG_PATH
FPS = 30
VOICE_SECONDS = 3.0
ASS_TEXT = chr(10).join([
    '[Script Info]', 'ScriptType: v4.00+', 'PlayResX: 1080', 'PlayResY: 1920', '', '[V4+ Styles]',
    'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
    'Style: Default,Arial,60,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1', '', '[Events]',
    'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text',
    'Dialogue: 0,0:00:00.00,0:00:03.00,Default,,0,0,0,,Sub',
]) + chr(10)


def write_png_raw(path, width, height, raw):
    def chunk(kind, data):
        body = kind + data
        return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body) & 0xFFFFFFFF)
    header = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    path.write_bytes(bytes([137, 80, 78, 71, 13, 10, 26, 10]) + chunk(b'IHDR', header) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def write_png(path, width, height, rgb):
    write_png_raw(path, width, height, (bytes([0]) + bytes(rgb) * width) * height)


def write_wav(path, seconds):
    with wave.open(str(path), 'wb') as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(48000)
        handle.writeframes(bytes(2 * int(48000 * seconds)))


HOOK_HZ = 3000
VOICE_HZ = 400
VOLUME_RE = re.compile(r'max_volume:\s*(-?[0-9.]+|-inf)\s*dB')


def write_stripes_png(path, width, height, cell):
    def row(flip):
        return bytes([0]) + b''.join(bytes([255, 255, 255]) if (x // cell + flip) % 2 == 0 else bytes([0, 0, 0]) for x in range(width))
    rows = [row(0), row(1)]
    raw = b''.join(rows[(y // cell) % 2] for y in range(height))
    write_png_raw(path, width, height, raw)


def write_tone(path, seconds, hertz):
    with wave.open(str(path), 'wb') as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(48000)
        frames = bytearray()
        total_samples = int(48000 * seconds)
        for n in range(total_samples):
            s = int(8000 * math.sin(2 * math.pi * hertz * n / 48000))
            frames.extend(struct.pack('<h', s))
        handle.writeframes(bytes(frames))


def write_testsrc_clip(path, seconds):
    done = run_process([FFMPEG, '-hide_banner', '-nostdin', '-y', '-f', 'lavfi', '-i', f'testsrc=size=1080x1920:rate=30:duration={seconds}', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(path)])
    assert done.returncode == 0, done.stderr[-2000:]


def band_db(path, start_s, seconds, hertz):
    done = run_process([FFMPEG, '-hide_banner', '-nostdin', '-ss', str(start_s), '-t', str(seconds), '-i', str(path), '-vn', '-af', f'bandpass=f={hertz}:width_type=h:w=200,volumedetect', '-f', 'null', '-'])
    assert done.returncode == 0, done.stderr[-2000:]
    found = VOLUME_RE.findall(done.stderr)
    assert found, done.stderr[-2000:]
    return float(found[-1])


def similarity(left, left_ms, right, right_ms):
    value = ssim_between(pathlib.Path(FFMPEG), pathlib.Path(left), left_ms, pathlib.Path(right), right_ms, width=270, height=480, timeout_seconds=120)
    if value is None:
        value = ssim_between(pathlib.Path(FFMPEG), pathlib.Path(right), right_ms, pathlib.Path(left), left_ms, width=270, height=480, timeout_seconds=120)
    assert value is not None
    return value


def run_process(command):
    return subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', stdin=subprocess.DEVNULL, timeout=600, check=False)


def probe(path):
    done = run_process([DEFAULT_FFPROBE_PATH, '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,nb_read_frames,duration:format=duration', '-of', 'json', str(path)])
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout)


@pytest.mark.parametrize('segment_ms', [(1000, 1000), (2500, 2500)], ids=['segments_shorter_than_voice', 'segments_longer_than_voice'])
def test_pinned_ffmpeg_renders_mixed_size_stills_to_the_voice_length(tmp_path, segment_ms):
    verify_ffmpeg_pin(pathlib.Path(FFMPEG), DEFAULT_LOCK_PATH)
    root = tmp_path / 'stage'
    for folder in ('media', 'subs', 'out'):
        (root / folder).mkdir(parents=True)
    write_png(root / 'media' / 'small.png', 640, 480, (200, 40, 40))
    write_png(root / 'media' / 'tall.png', 1080, 1920, (40, 40, 200))
    write_wav(root / 'media' / 'voice.wav', VOICE_SECONDS)
    (root / 'subs' / 'karaoke.ass').write_text(ASS_TEXT, encoding='utf-8')
    locals_ = {'ref-small': 'media/small.png', 'ref-tall': 'media/tall.png', 'ref-voice': 'media/voice.wav', 'ref-ass': 'subs/karaoke.ass'}
    first, second = segment_ms
    rec = record(
        voice_artifact_ref='ref-voice',
        input_artifacts=[artifact('ref-small', 'image/png'), artifact('ref-tall', 'image/png')],
        timeline={
            'duration_ms': int(VOICE_SECONDS * 1000),
            'segments': [
                {'start_ms': 0, 'end_ms': first, 'visual_asset_refs': ['ref-small']},
                {'start_ms': first, 'end_ms': first + second, 'visual_asset_refs': ['ref-tall']},
            ],
        },
        hook_placement=hook_placement(visual_hook_ref='ref-small', audio_hook_ref='ref-voice', thumbnail_ref='ref-small'),
        materialization_manifest={ref: {'local_ref': local} for ref, local in locals_.items()},
    )
    spec = render(record=rec, tool_identity=tool(executable=FFMPEG), materialized=materialized(staging_root=str(root)))
    assert 'ass=filename=' in value_after(spec.argv, '-filter_complex') and spec.argv.count('-loop') == 3
    output = root / 'out' / 'attempt.mp4'
    done = run_process(build_final_argv(spec.argv, FFMPEG, 'libx264', str(output)))
    assert done.returncode == 0, done.stderr[-2000:]
    info = probe(output)
    stream = info['streams'][0]
    frame = 1 / FPS
    assert (stream['width'], stream['height']) == (1080, 1920)
    assert abs(float(info['format']['duration']) - VOICE_SECONDS) <= frame
    assert abs(float(stream['duration']) - VOICE_SECONDS) <= frame
    assert abs(int(stream['nb_read_frames']) - VOICE_SECONDS * FPS) <= 1


def render_hook_scene(tmp_path, thumb_ref, thumb_range):
    verify_ffmpeg_pin(pathlib.Path(FFMPEG), DEFAULT_LOCK_PATH)
    root = tmp_path / 'stage'
    for folder in ('media', 'subs', 'out'):
        (root / folder).mkdir(parents=True)
    write_png(root / 'media' / 'bg.png', 1080, 1920, (40, 40, 200))
    write_stripes_png(root / 'media' / 'thumb.png', 1080, 1920, 120)
    write_testsrc_clip(root / 'media' / 'hook.mp4', 3)
    write_tone(root / 'media' / 'voice.wav', 4, VOICE_HZ)
    write_tone(root / 'media' / 'hook.wav', 3, HOOK_HZ)
    (root / 'subs' / 'karaoke.ass').write_text(ASS_TEXT, encoding='utf-8')
    manifest_dict = {
        'ref-bg': {'local_ref': 'media/bg.png'},
        'ref-hook-v': {'local_ref': 'media/hook.mp4'},
        'ref-hook-a': {'local_ref': 'media/hook.wav'},
        'ref-thumb': {'local_ref': 'media/thumb.png'},
        'ref-voice': {'local_ref': 'media/voice.wav'},
        'ref-ass': {'local_ref': 'subs/karaoke.ass'},
    }
    rec = record(
        voice_artifact_ref='ref-voice',
        input_artifacts=[artifact('ref-bg', 'image/png'), artifact('ref-hook-v', 'video/mp4'), artifact('ref-thumb', 'image/png')],
        timeline={'segments': [{'start_ms': 0, 'end_ms': 4000, 'visual_asset_refs': ['ref-bg']}]},
        hook_placement=hook_placement(
            visual_hook_ref='ref-hook-v',
            audio_hook_ref='ref-hook-a',
            thumbnail_ref=thumb_ref,
            hook_time_range={'start_ms': 1000, 'end_ms': 2500},
            thumbnail_time_range=thumb_range,
        ),
        materialization_manifest=manifest_dict,
    )
    spec = render(record=rec, tool_identity=tool(executable=FFMPEG), materialized=materialized(staging_root=str(root)))
    output = root / 'out' / 'attempt.mp4'
    done = run_process(build_final_argv(spec.argv, FFMPEG, 'libx264', str(output)))
    assert done.returncode == 0, done.stderr[-2000:]
    return root, spec, output


def test_pinned_ffmpeg_shows_the_visual_hook_and_mixes_the_audio_hook_only_inside_the_hook_range(tmp_path):
    root, spec, output = render_hook_scene(tmp_path, 'ref-hook-v', {'start_ms': 1500, 'end_ms': 2000})
    hook = root / 'media' / 'hook.mp4'
    flat = root / 'media' / 'bg.png'
    assert similarity(flat, None, hook, 750) < 0.85
    assert similarity(output, 1750, hook, 750) >= 0.85
    assert similarity(output, 500, hook, 750) < 0.85
    assert similarity(output, 3500, hook, 750) < 0.85
    assert band_db(output, 1.2, 1.0, HOOK_HZ) - band_db(output, 3.0, 0.8, HOOK_HZ) >= 20
    assert abs(band_db(output, 1.2, 1.0, VOICE_HZ) - band_db(output, 3.0, 0.8, VOICE_HZ)) <= 2.0
    assert abs(float(probe(output)['format']['duration']) - 4.0) <= 0.1


def test_pinned_ffmpeg_overlays_a_distinct_thumbnail_image_inside_the_thumbnail_range(tmp_path):
    root, spec, output = render_hook_scene(tmp_path, 'ref-thumb', {'start_ms': 1500, 'end_ms': 2000})
    thumb = root / 'media' / 'thumb.png'
    hook = root / 'media' / 'hook.mp4'
    assert any(item.endswith('thumb.png') for item in spec.argv)
    assert similarity(thumb, None, hook, 750) < 0.85
    assert similarity(output, 1750, thumb, None) >= 0.85
    assert similarity(output, 1200, thumb, None) < 0.85
    assert similarity(output, 2250, thumb, None) < 0.85
    assert similarity(output, 1200, hook, 200) >= 0.85
    assert similarity(output, 2250, hook, 1250) >= 0.85
