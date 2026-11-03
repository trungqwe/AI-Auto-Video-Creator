"""PRS-LAYOUT-TEXT: chữ của bố cục qua ASS (quyết định Control 02:12Z 03/11/2026, điểm 2 và 6): tiêu đề trên băng (tiêu đề ngắn của
kế hoạch, thiếu thì câu đầu của lời đọc cắt ở ranh giới từ tới 48 ký tự), chuyên mục, số nguyên văn của lời đọc, trích dẫn, nhãn hai vế,
bộ đếm ảnh và nhãn "AI illustration" ở góc mọi ô đang hiện ảnh AI; nhãn toàn khung của IMGGEN-LABEL không dán lần hai.

Không mạng, không CSDL; một ca dựng phụ đề qua FFmpeg ghim thật (libass) trên nền xám.

coveredIds: FR-PRS-002, FR-PRS-006
"""
from __future__ import annotations

import re
import subprocess
from types import SimpleNamespace

import render.adapters.ass_manifest as ass_manifest
from controlplane.api.wiring import render as render_wiring
from render.domain import layout
from render.domain.karaoke_plan import TimedWord
from tests.integration.render.test_imggen_label import DISCLOSURE_STYLE, LIMITS, SAFE_AREA, SEGMENTS, TYPOGRAPHY, WORDS
from tests.integration.render.test_f10_fix6_frame_placement import FFMPEG

try:
    from render.domain import layout_text
except ImportError:  # the module this package adds
    layout_text = None

NARRATION = 'Hackers heated supermarket freezers to 50°C across 7 countries. Staff binned tons of food overnight.'
SPOKEN = [TimedWord(w, i * 400, i * 400 + 380) for i, w in enumerate(NARRATION.split())]
SCRIPT = {
    'hook_intent': 'cyberattack',
    'segments': [
        {'segment_id': 's1', 'text': 'Inside, freezers climbed to 50°C.'},
        {'segment_id': 's2', 'text': 'Outside, food went into skips.'},
    ],
}
REFS = ['av-1', 'av-2', 'av-ai', 'av-4']


def presentation_preset(key, accent='#FFD400'):
    return SimpleNamespace(layout_rules={'presentation': {'layout_key': key, 'accent_colour': accent}})


def timeline(refs=REFS, scene_ms=3000, ai='av-ai'):
    segments = []
    for i, ref in enumerate(refs):
        visual = {'media_asset_id': f'm-{i}', 'artifact_version_ref': ref, 'start_ms': i * scene_ms, 'end_ms': (i + 1) * scene_ms}
        if ref == ai:
            visual['origin'] = 'ai_generated'
        segments.append({'start_ms': i * scene_ms, 'end_ms': (i + 1) * scene_ms, 'visuals': [visual], 'visual_asset_refs': [ref]})
    return {'segments': segments}


def rows_for(key, plan=None, hook=None, refs=REFS):
    return render_wiring.layout_rows_for(
        presentation_preset(key), plan if plan is not None else {'layout_choice': {'title': 'Hackers heat supermarket freezers to 50°C'}},
        SCRIPT, timeline=timeline(refs), hook_placement=hook or {}, allowed_fallbacks=(), words=SPOKEN, end_ms=12500,
        typography=TYPOGRAPHY, profile=LIMITS)


def dialogues(rows, style):
    return [event for event in rows.events if f',{style},' in event]


def test_titles_numbers_and_quotes_are_cut_to_their_slot_and_taken_verbatim():
    assert layout_text.short_title('Hackers heat freezers', NARRATION) == 'Hackers heat freezers'
    long = layout_text.short_title('x' * 60, NARRATION)
    assert long == 'Hackers heated supermarket freezers to 50°C…' and len(long) <= layout_text.TITLE_MAX_CHARS
    assert layout_text.wrap_lines('Hackers heat supermarket freezers to fifty degrees across Europe tonight', 30, 2) == (
        'Hackers heat supermarket', 'freezers to fifty degrees…')
    assert layout_text.first_number(SPOKEN, 8, 22) == ('50°C', 'across 7 countries', 2000)
    assert layout_text.first_number(SPOKEN, 3, 22) is None
    assert layout_text.first_number([TimedWord('no', 0, 10)], 8, 22) is None
    assert layout_text.quote_of(['He said “legitimate grievances risk being lost” today.'], 62) == 'legitimate grievances risk being lost'
    assert layout_text.plain_text('a{b}\\c') == 'a｛b｝＼c'


def test_each_layout_writes_its_slots_inside_the_safe_text_area():
    for key in layout.LAYOUT_KEYS:
        rows = rows_for(key)
        assert rows is not None and rows.events, key
        slots = {slot.name: slot for slot in layout.layout_geometry(key).texts}
        for event in rows.events:
            text = event.split(',,', 2)[-1].split('}', 1)[1]
            style = event.split(',')[3]
            if style == 'LayoutAiLabel':
                assert text == 'AI illustration', key
                continue
            name = {'LayoutBadgeNumber': 'badge_number', 'LayoutBadgeCaption': 'badge_caption', 'LayoutNumberCaption': 'number_caption',
                    'LayoutTopLabel': 'top_label', 'LayoutBottomLabel': 'bottom_label'}.get(style, style[6:].lower())
            lines = text.split('\\N')
            assert len(lines) <= slots[name].max_lines and all(len(line) <= slots[name].max_chars for line in lines), (key, name, lines)
            x, y = (int(v) for v in re.search(r'pos\((\d+),(\d+)\)', event).groups())
            assert layout.TEXT_LEFT <= x <= layout.TEXT_RIGHT and not (layout.SUBTITLE_ROWS[0] <= y <= layout.SUBTITLE_ROWS[1]), (key, name)
    assert rows_for('MOSAIC_GRID').values['number'] == '50°C' and rows_for('HERO_STRIP').values['number_caption'] == 'across 7 countries'
    assert 'number' not in rows_for('SPLIT_STACK').values
    split = rows_for('SPLIT_STACK', plan={'layout_choice': {'title': None, 'contrast_pair': ['s1', 's2']}})
    assert split.values['top_label'] == 'INSIDE, FREEZERS CLIMBED' + '…' and split.values['bottom_label'].startswith('OUTSIDE, FOOD')
    assert split.values['title'].startswith('Hackers heated supermarket')


def test_every_ai_cell_is_labelled_once_and_the_whole_frame_label_is_dropped():
    rows = rows_for('HERO_STRIP')
    labels = dialogues(rows, 'LayoutAiLabel')
    # Four images fill the four cells of every scene: av-ai is on screen in each scene, in the main cell of scene 2, once per scene.
    assert len(labels) == 4 == rows.values['ai_labels']
    assert 'pos(60,522)' in labels[2] and all('pos(60,522)' not in label for label in labels[:2])
    assert len(dialogues(rows_for('HERO_STRIP', refs=['av-1', 'av-2', 'av-4']), 'LayoutAiLabel')) == 0
    with_layout = ass_manifest.build_ass_text(WORDS, TYPOGRAPHY, SAFE_AREA, LIMITS, DISCLOSURE_STYLE, SEGMENTS, illustration_windows=((0, 1000),), layout_rows=rows)
    assert 'AI-generated illustration' not in with_layout and with_layout.count('AI illustration') == 4
    assert all(f'Style: {name},' in with_layout for name in ('LayoutTitle', 'LayoutAiLabel'))
    plain = ass_manifest.build_ass_text(WORDS, TYPOGRAPHY, SAFE_AREA, LIMITS, DISCLOSURE_STYLE, SEGMENTS, illustration_windows=((0, 1000),))
    assert 'AI-generated illustration' in plain and 'Layout' not in plain


def test_text_hides_under_the_hook_and_without_a_layout_nothing_changes():
    rows = rows_for('DATA_CARD', hook={'hook_time_range': {'start_ms': 0, 'end_ms': 2000}, 'thumbnail_time_range': {'start_ms': 500, 'end_ms': 900}})
    assert all(not event.startswith('Dialogue: 1,0:00:00.') and not event.startswith('Dialogue: 1,0:00:01.') for event in rows.events)
    counters = [event.rsplit('}', 1)[1] for event in dialogues(rows, 'LayoutCounter')]
    assert counters == ['1 / 4', '2 / 4', '3 / 4', '4 / 4']
    assert render_wiring.layout_rows_for(
        SimpleNamespace(layout_rules={'note': 'x'}), {}, SCRIPT, timeline=timeline(), hook_placement={}, allowed_fallbacks=(), words=SPOKEN,
        end_ms=12500, typography=TYPOGRAPHY, profile=LIMITS) is None
    assert rows_for('MOSAIC_GRID', refs=['av-1', 'av-2']) is None


def test_libass_draws_the_title_on_the_band_and_the_ai_label_in_its_cell(tmp_path):
    rows = rows_for('HERO_STRIP')
    text = ass_manifest.build_ass_text(SPOKEN, TYPOGRAPHY, SAFE_AREA, LIMITS, DISCLOSURE_STYLE, (
        SEGMENTS[0].__class__(segment_id='seg-0', order=0, claim_mode='source_backed', disclosure=None, word_count=len(SPOKEN)),), layout_rows=rows)
    path = tmp_path / 'layout.ass'
    path.write_text(text, encoding='utf-8')
    escaped = str(path).replace('\\', '/').replace(':', '\\:')
    argv = [FFMPEG, '-hide_banner', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=0x808080:s=1080x1920:r=10:d=8',
            '-vf', f"subtitles='{escaped}'", '-ss', '6.5', '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    done = subprocess.run(argv, capture_output=True, stdin=subprocess.DEVNULL, timeout=120, check=False)
    assert done.returncode == 0, done.stderr.decode('utf-8', 'replace')[-1500:]
    frame = done.stdout

    def count(box, test):
        hits = 0
        for y in range(box[1], box[1] + box[3], 3):
            for x in range(box[0], box[0] + box[2], 3):
                at = (y * 1080 + x) * 3
                hits += test(frame[at:at + 3])
        return hits

    # Dark ink of the title in the band rows; white letters of the label in the top-left corner of the main cell (scene 2 shows av-ai).
    assert count((60, 330, 900, 130), lambda p: max(p) < 60) > 200
    main = layout.layout_geometry('HERO_STRIP').cells[0].box
    assert count((60, main.y + 14, 200, 40), lambda p: min(p) > 220) > 20
