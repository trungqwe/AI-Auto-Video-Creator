"""IMGGEN-LABEL: nhãn AI-generated illustration góc trên trái của cảnh vẽ bằng ảnh AI: hàng ASS, cửa sổ thời gian, render FFmpeg ghim thật và QC; không DB, không mạng.

coveredIds: OI-CP7-11-Q2
"""
from __future__ import annotations

import pathlib
from types import SimpleNamespace

import pytest

import render.adapters.ass_manifest as ass_manifest
from controlplane.api.wiring import render as render_wiring
from render.adapters.postgres_plan_assets import ScriptSegmentInfo
from render.adapters.real_ffmpeg_renderer import DEFAULT_LOCK_PATH, verify_ffmpeg_pin
from render.adapters.real_output_inspector import Band, InspectionInputs, InspectorSettings, RealOutputInspector, karaoke_observations, parse_ass_dialogues, style_band_from_ass
from render.domain.content_gates import check_thumbnail_present, check_visual_hook_present
from render.domain.karaoke_plan import STYLE_NAME as KARAOKE_STYLE
from render.domain.karaoke_plan import TimedWord
from render.domain.package_contract import validate_render_package_payload
from render.domain.quality_report import GateStatus, QualityPolicy
from tests.integration.render.test_f10_fix6_frame_placement import FFMPEG, MIN_SIMILARITY, H, W, grab_frame, luma, make_stage, mean_diff, render_package, write_png_raw, write_wav

AI = 'ai_generated'
GREY = (128, 128, 128)
TYPOGRAPHY = {'font_name': 'Arial', 'font_size': 72, 'primary_colour': '&H0000D4FF', 'secondary_colour': '&H00FFFFFF', 'outline_colour': '&H00000000', 'back_colour': '&H80000000', 'bold': -1, 'italic': 0, 'underline': 0, 'strike_out': 0, 'scale_x': 100, 'scale_y': 100, 'spacing': 0, 'angle': 0, 'border_style': 1, 'outline': 4, 'shadow': 0, 'alignment': 2, 'encoding': 1}
SAFE_AREA = {'margin_left': 60, 'margin_right': 60, 'margin_vertical': 360}
LIMITS = {'max_words_per_line': 4, 'max_chars_per_line': 28, 'play_res_x': 1080, 'play_res_y': 1920}
DISCLOSURE_STYLE = {'font_size': 40, 'alignment': 8, 'margin_v': 240}
WORDS = [TimedWord(w, i * 500, i * 500 + 500) for i, w in enumerate('Port strike ends today ships should move again'.split())]
SEGMENTS = (
    ScriptSegmentInfo(segment_id='seg-0', order=0, claim_mode='source_backed', disclosure=None, word_count=4),
    ScriptSegmentInfo(segment_id='seg-1', order=1, claim_mode='inference', disclosure='Inference drawn from the sources.', word_count=4),
)
WINDOWS = ((1000, 1500), (3000, 4000))


def ass(windows=()):
    return ass_manifest.build_ass_text(WORDS, TYPOGRAPHY, SAFE_AREA, LIMITS, DISCLOSURE_STYLE, SEGMENTS, illustration_windows=windows)


def scene(index, start, end, ref, origin=None, media=None, refs=None):
    visual = {'media_asset_id': media or f'm-{index}', 'artifact_version_ref': ref, 'start_ms': start, 'end_ms': end}
    if origin is not None:
        visual['origin'] = origin
    return {'scene_id': f's{index}', 'start_ms': start, 'end_ms': end, 'visuals': [visual], 'visual_asset_refs': [ref] if refs is None else refs}


def raw_scene(*args, **kwargs):
    return {k: v for k, v in scene(*args, **kwargs).items() if k != 'visual_asset_refs'}


def hook(hook_end, thumb=(200, 600)):
    return {'hook_time_range': {'start_ms': 0, 'end_ms': hook_end}, 'thumbnail_time_range': {'start_ms': thumb[0], 'end_ms': thumb[1]}}


def rule(media, reason, onto):
    return {'rule_id': f'image-safety:{media}', 'kind': 'replace_asset', 'replaced_media_asset_id': media, 'replaced_artifact_version_ref': 'orig-' + media, 'artifact_version_id': onto, 'reason': reason}


def test_the_label_style_follows_the_disclosure_style_and_one_row_shows_per_window():
    m = ass_manifest
    assert (m.ILLUSTRATION_STYLE, m.ILLUSTRATION_TEXT, m.ILLUSTRATION_FONT_SIZE, m.ILLUSTRATION_ALIGNMENT) == ('Illustration', 'AI-generated illustration', 34, 7)
    lines = ass(WINDOWS).splitlines()
    styles = [line for line in lines if line.startswith('Style: ')]
    assert [line[7:].split(',')[0] for line in styles][-2:] == ['Disclosure', 'Illustration']
    disclosure, label = (line[7:].split(',') for line in styles[-2:])
    assert label[1] == disclosure[1] and label[7:15] == disclosure[7:15] and label[22] == disclosure[22]
    assert label[2:7] == ['34', '&H00FFFFFF', '&H00FFFFFF', '&H80000000', '&H80000000']
    assert label[15:22] == ['3', '8', '0', '7', '60', '60', '110']
    rows = [line for line in lines if line.startswith('Dialogue:') and ',Illustration,' in line]
    expected = [f'Dialogue: 0,{a},{b},Illustration,,60,60,110,,AI-generated illustration' for a, b in (('0:00:01.00', '0:00:01.50'), ('0:00:03.00', '0:00:04.00'))]
    assert rows == expected and lines[-2:] == rows


def test_without_windows_the_text_and_its_digest_do_not_change(tmp_path):
    plain = ass()
    assert ass(()) == plain and 'Illustration' not in plain
    kept = [line for line in ass(WINDOWS).split(chr(10)) if not line.startswith('Style: Illustration,') and ',Illustration,' not in line]
    assert chr(10).join(kept) == plain
    args = dict(staging_root=str(tmp_path), words=WORDS, typography=TYPOGRAPHY, safe_area=SAFE_AREA, profile=LIMITS, disclosure_style=DISCLOSURE_STYLE, segments=SEGMENTS)
    base = ass_manifest.build_ass_material(**args)
    empty = ass_manifest.build_ass_material(**args, illustration_windows=())
    labelled = ass_manifest.build_ass_material(**args, illustration_windows=WINDOWS)
    assert (base.sha256, base.ass_ref, base.text) == (empty.sha256, empty.ass_ref, plain)
    assert labelled.sha256 != base.sha256 and (tmp_path / f'{labelled.sha256}.ass').read_bytes() == labelled.text.encode('utf-8')


def test_overlapping_windows_merge_and_malformed_windows_are_refused():
    def label_rows(windows):
        return [line.split(',')[1:3] for line in ass(windows).splitlines() if line.startswith('Dialogue:') and ',Illustration,' in line]
    assert label_rows([(2000, 3000), (500, 1500), (1400, 2100), (3000, 3500)]) == [['0:00:00.50', '0:00:03.50']]
    assert label_rows([[3000, 4000], [0, 1000], [1000, 2000]]) == [['0:00:00.00', '0:00:02.00'], ['0:00:03.00', '0:00:04.00']]
    assert label_rows([]) == []
    for bad in ('0-1', b'ab', 7, None, [7], [(1,)], [(1, 2, 3)], [(-1, 5)], [(5, 5)], [(6, 5)], [(True, 5)], [(0, True)]):
        with pytest.raises(ass_manifest.AssManifestRejected) as info:
            ass(bad)
        assert info.value.code == 'ILLUSTRATION_WINDOW_INVALID', bad


def test_qc_readers_see_the_same_karaoke_and_disclosure_and_the_label_band_ends_above_the_disclosure_band():
    plain, labelled = ass(), ass(WINDOWS)
    before, after = parse_ass_dialogues(plain), parse_ass_dialogues(labelled)
    assert tuple(d for d in after if d.style != 'Illustration') == before and len(after) == len(before) + 2
    assert karaoke_observations(after) == karaoke_observations(before)
    for style in (KARAOKE_STYLE, 'Disclosure'):
        assert style_band_from_ass(labelled, style) is not None and style_band_from_ass(labelled, style) == style_band_from_ass(plain, style)
    label_band = style_band_from_ass(labelled, 'Illustration')
    assert label_band.bottom <= style_band_from_ass(labelled, 'Disclosure').top and label_band.bottom <= style_band_from_ass(labelled, KARAOKE_STYLE).top
    assert [(d.start_ms, d.end_ms, d.text) for d in after if d.style == 'Illustration'] == [(1000, 1500, 'AI-generated illustration'), (3000, 4000, 'AI-generated illustration')]


def test_only_scenes_drawn_with_an_ai_image_are_labelled_and_the_hook_and_thumbnail_ranges_are_cut_out():
    windows = render_wiring.illustration_windows
    timeline = {'segments': [scene(1, 0, 3000, 'AAA', AI), scene(2, 3000, 6000, 'bbb'), scene(3, 6000, 9000, 'ccc', AI), scene(4, 9000, 12000, 'ddd', AI)]}
    result = windows(timeline, hook(2000, (500, 1500)), ())
    assert result == ((2000, 3000), (6000, 12000)) and isinstance(result, tuple) and all(type(v) is int for pair in result for v in pair)
    assert windows(timeline, hook(3500, (500, 1500)), ()) == ((6000, 12000),)
    assert windows(timeline, {**hook(2000), 'thumbnail_time_range': {'start_ms': 7000, 'end_ms': 8000}}, ()) == ((2000, 3000), (6000, 7000), (8000, 12000))
    assert windows(timeline, hook(2000), (), 13500) == ((2000, 3000), (6000, 13500))
    assert windows(timeline, hook(2000), (), 11000) == ((2000, 3000), (6000, 12000))
    assert windows(timeline, hook(2000), (), None) == windows(timeline, hook(2000), ())
    assert windows({'segments': [scene(1, 0, 3000, 'AAA', AI), scene(2, 3000, 6000, 'bbb')]}, hook(2000), (), 9000) == ((2000, 3000),)
    assert windows({'segments': [scene(1, 0, 3000, 'AAA', AI, refs=['aaa'])]}, hook(1000), ()) == ((1000, 3000),)
    first = {'segments': [scene(1, 0, 3000, 'AAA', AI, refs=['bbb', 'AAA']), scene(2, 3000, 6000, 'ccc', AI, refs=['AAA', 'bbb'])]}
    assert windows(first, hook(2000), ()) == ((3000, 6000),)


def test_an_ai_image_replaced_by_another_media_is_not_labelled_and_a_fallback_onto_an_ai_image_is():
    windows = render_wiring.illustration_windows
    swapped = {'segments': [scene(1, 0, 3000, 'ref-new', AI, media='m-ai')]}
    for reason in ('image_fallback', 'seed_fallback'):
        assert windows(swapped, hook(1000), (rule('m-ai', reason, 'ref-new'),)) == ()
    assert windows(swapped, hook(1000), (rule('m-ai', 'blurred', 'ref-new'),)) == ((1000, 3000),)
    plan_rule = {'rule_id': 'fb-1', 'kind': 'replace_asset', 'scene_id': 's1', 'replacement_media_asset_id': 'm-x'}
    assert windows(swapped, hook(1000), (plan_rule,)) == ((1000, 3000),)
    onto = {'segments': [scene(1, 0, 3000, 'ref-ai', AI, media='m-ai'), scene(2, 3000, 6000, 'REF-AI', media='m-art')]}
    assert windows(onto, hook(1000), (rule('m-art', 'image_fallback', 'REF-AI'),)) == ((1000, 6000),)


def test_timelines_without_an_ai_image_have_no_window():
    windows = render_wiring.illustration_windows
    for origin in (None, 'seed', 'article', 'AI_GENERATED', ''):
        assert windows({'segments': [scene(1, 0, 3000, 'aaa', origin)]}, hook(1000), (), 9000) == ()
    for timeline in ({}, {'segments': 'x'}, {'segments': []}, {'segments': [7]}, {'segments': [{'visuals': 'x'}]}, [], None, 'x'):
        assert windows(timeline, hook(1000), ()) == ()
    assert windows({'segments': [scene(1, 0, 3000, 'aaa', AI, refs=[])]}, hook(1000), ()) == ()
    assert windows({'segments': [raw_scene(1, 0, 3000, 'aaa', AI)]}, hook(1000), ()) == ()
    for start, end in ((True, 3000), (0, 'x'), (None, 3000), (3000, 3000), (-5, 3000)):
        bad = scene(1, 0, 3000, 'aaa', AI)
        bad.update(start_ms=start, end_ms=end)
        assert windows({'segments': [bad]}, hook(1000), ()) == ()
    one = {'segments': [scene(1, 0, 3000, 'aaa', AI)]}
    for placement in ({}, None, 'x', {'hook_time_range': 'x'}, {'hook_time_range': {'start_ms': True, 'end_ms': 5}}):
        assert windows(one, placement, ()) == ((0, 3000),)
    assert windows(one, hook(1000), (), True) == ((1000, 3000),) and windows(one, hook(1000), (), '9') == ((1000, 3000),)


VOICE_MS = 4000
RENDER_SCENES = [scene(1, 0, 1500, 'ref-ai1', AI), scene(2, 1500, 3000, 'ref-art'), scene(3, 3000, 3500, 'ref-ai2', AI)]
RENDER_HOOK = {'visual_hook_ref': 'ref-hook', 'audio_hook_ref': 'ref-hook-a', 'thumbnail_ref': 'ref-hook', **hook(1000)}
RENDER_WINDOWS = ((1000, 1500), (3000, 4000))


def package_payload(timeline, placement, fallbacks):
    refs = sorted({ref for item in timeline['segments'] for ref in item['visual_asset_refs']} | {'ref-hook'})
    manifest = {ref: {'local_ref': f'media/{ref}.png'} for ref in refs}
    manifest.update({'ref-hook-a': {'local_ref': 'media/hook.wav'}, 'ref-voice': {'local_ref': 'media/voice.wav'}, 'ref-ass': {'local_ref': 'subs/karaoke.ass'}})
    return {
        'render_package_id': 'pkg-label', 'package_fingerprint': 'a' * 64, 'production_snapshot_ref': 'snap', 'script_version_ref': 'script',
        'production_plan_ref': 'plan', 'preset_revision_ref': 'preset', 'voice_artifact_ref': 'ref-voice', 'word_timing_ref': 'ref-timing',
        'output_metadata_revision': 'meta', 'output_profile_revision': 'profile', 'language_validation_refs': ['lang'],
        'input_artifacts': [{'artifact_version_id': ref, 'sha256': 'c' * 64, 'size_bytes': 1, 'media_type': 'image/png'} for ref in refs],
        'timeline': {'duration_ms': VOICE_MS, 'segments': timeline['segments']}, 'hook_placement': placement, 'subtitle_config': {'karaoke': True},
        'mix_plan': {}, 'allowed_fallbacks': list(fallbacks), 'materialization_manifest': manifest, 'output_path_ref': 'ref-output',
    }


def test_resolve_time_and_package_time_inputs_give_the_same_windows():
    raw = {'segments': [raw_scene(1, 0, 1500, 'AAA', AI), raw_scene(2, 1500, 3000, 'bbb'), raw_scene(3, 3000, 3500, 'CCC', AI)]}
    rules = (rule('m-9', 'blurred', 'zzz'),)
    render_timeline = render_wiring._timeline_for_render(raw)
    at_resolve = render_wiring.illustration_windows(render_timeline, hook(1000), rules, VOICE_MS)
    record = validate_render_package_payload(package_payload(render_timeline, hook(1000), rules))
    at_package = render_wiring.illustration_windows(record.timeline, record.hook_placement, record.allowed_fallbacks, VOICE_MS)
    assert at_resolve == at_package == RENDER_WINDOWS
    assert ass(at_resolve) == ass(at_package)


def test_the_windows_of_the_rendered_package_are_the_ai_scenes_without_the_hook():
    assert render_wiring.illustration_windows({'segments': RENDER_SCENES}, RENDER_HOOK, (), VOICE_MS) == RENDER_WINDOWS
    labels = [d for d in parse_ass_dialogues(ass(RENDER_WINDOWS)) if d.style == 'Illustration']
    assert [(d.start_ms, d.end_ms) for d in labels] == [(1000, 1500), (3000, 4000)]
    assert all(d.start_ms >= RENDER_HOOK['hook_time_range']['end_ms'] for d in labels) and labels[-1].end_ms == VOICE_MS


GREEN = (0, 200, 0)


def solid_png(path, colour):
    write_png_raw(path, W, H, (bytes([0]) + bytes(colour) * W) * H)


def build_world(base, windows):
    root = make_stage(base)
    media = root / 'media'
    write_wav(media / 'voice.wav', VOICE_MS / 1000)
    for name, colour in (('ref-ai1', GREY), ('ref-art', (90, 90, 160)), ('ref-ai2', GREY), ('ref-hook', GREEN)):
        solid_png(media / f'{name}.png', colour)
    (root / 'subs' / 'karaoke.ass').write_text(ass(windows), encoding='utf-8')
    locals_ = {ref: f'media/{ref}.png' for ref in ('ref-ai1', 'ref-art', 'ref-ai2', 'ref-hook')}
    locals_.update({'ref-hook-a': 'media/hook.wav', 'ref-voice': 'media/voice.wav', 'ref-ass': 'subs/karaoke.ass'})
    segments = [{'start_ms': s['start_ms'], 'end_ms': s['end_ms'], 'visual_asset_refs': s['visual_asset_refs']} for s in RENDER_SCENES]
    record, _spec, output = render_package(root, locals_=locals_, still_refs=['ref-ai1', 'ref-art', 'ref-ai2', 'ref-hook'], segments=segments, hook=RENDER_HOOK, voice_ms=VOICE_MS)
    return SimpleNamespace(root=root, record=record, output=output)


@pytest.fixture(scope='module')
def worlds(tmp_path_factory):
    verify_ffmpeg_pin(pathlib.Path(FFMPEG), DEFAULT_LOCK_PATH)
    return SimpleNamespace(plain=build_world(tmp_path_factory.mktemp('plain'), ()), label=build_world(tmp_path_factory.mktemp('label'), RENDER_WINDOWS))


def differing(a, b):
    rows, cols = set(), set()
    for y in range(H):
        ra, rb = a[y * W * 3:(y + 1) * W * 3], b[y * W * 3:(y + 1) * W * 3]
        if ra != rb:
            rows.add(y)
            cols.update(x for x in range(W) if ra[3 * x:3 * x + 3] != rb[3 * x:3 * x + 3])
    return rows, cols


def bright(frame, top, bottom):
    return sum(1 for y in range(top, bottom + 1) for x in range(W) if luma(tuple(frame[(y * W + x) * 3:(y * W + x) * 3 + 3])) >= 200)


def test_the_rendered_label_shows_only_in_its_windows_and_stays_above_the_disclosure_band(worlds):
    for index in (37, 105):
        plain = grab_frame(worlds.plain.output, index)
        label = grab_frame(worlds.label.output, index)
        rows, cols = differing(plain[:200 * W * 3], label[:200 * W * 3])
        assert rows, index
        assert 95 <= min(rows) and max(rows) <= 160, (index, min(rows), max(rows))
        assert max(rows) < round(0.125 * H)
        assert 40 <= min(cols) and max(cols) <= 700, (index, min(cols), max(cols))
        assert bright(label, min(rows), max(rows)) > 100 and bright(plain, min(rows), max(rows)) == 0
    for index in (5, 25, 55, 75):
        assert mean_diff(grab_frame(worlds.plain.output, index), grab_frame(worlds.label.output, index)) <= 0.05, index


def qc_evidence(world):
    settings = InspectorSettings(compare_width=90, compare_height=160, thumbnail_min_ssim=MIN_SIMILARITY, subtitle_band=Band(top=0.70, bottom=0.80), disclosure_band=Band(top=0.10, bottom=0.25), overlay_max_missing_share=0.25, max_subtitle_samples=4, timeout_seconds=120)
    inspector = RealOutputInspector(inputs=InspectionInputs(staging_root=world.root, ass_ref='ref-ass', segments=[]), settings=settings)
    return inspector.inspect(str(world.output), world.record)


def test_qc_measures_the_same_output_with_and_without_the_label(worlds):
    plain, label = qc_evidence(worlds.plain), qc_evidence(worlds.label)
    policy = QualityPolicy(revision='imggen-label', thresholds={'VISUAL_HOOK_PRESENT': {'min_similarity': MIN_SIMILARITY}})
    for check in (check_visual_hook_present, check_thumbnail_present):
        a = check(plain, worlds.plain.record, policy)
        b = check(label, worlds.label.record, policy)
        assert a.status is GateStatus.PASSED and b.status is GateStatus.PASSED, (a.reason, b.reason)
        assert a.measured_value == b.measured_value
    assert label == plain
