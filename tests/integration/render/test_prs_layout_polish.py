"""PRS-LAYOUT-POLISH: bản dựng bố cục gần ảnh mẫu đã duyệt (quyết định Control 03:10Z 03/11/2026): ô bo góc, viền thuộc ô, bóng đổ,
ảnh lồng xoay -2 độ, ô phụ trượt vào đầu cảnh; mặt nạ dựng một lần mỗi video; đồ thị dài hơn LAYOUT_GRAPH_MAX_CHARS tới FFmpeg qua tệp.

FFmpeg ghim thật trên ảnh nhỏ tự tạo; không mạng, không CSDL, không GPU.

coveredIds: FR-PRS-002, FR-PRS-006
"""
import math
import pathlib
import subprocess

from render.adapters import real_ffmpeg_renderer as renderer
from render.domain import layout, render_command
from render.domain.render_command import build_render_command
from tests.integration.render.test_prs_layout_graph import ACCENT, COLOURS, H, W, frames_of, near, pixel, solid_images, write_png
from tests.integration.render.test_prs_layout_render import preset, record_for, stage  # noqa: F401 (module fixture)
from tests.integration.render.test_f10_fix6_frame_placement import FFMPEG, grab_frame, materialized, profile, tool

WHITE = (255, 255, 255)


def scaled(x, y):
    return round(x * W / 1080), round(y * H / 1920)


def qc_frame(key, paths):
    count = len(layout.layout_geometry(key).cells)
    graph = layout.compose_layout(key, width=W, height=H, sources=[f'{k}:v' for k in range(count)], accent=ACCENT, prefix='q')
    return frames_of(paths[:count], graph, 1)[0]


def test_tiles_have_rounded_corners_and_their_border(tmp_path):
    images = solid_images(tmp_path, 4)
    frame = qc_frame('HERO_STRIP', images)
    main = layout.layout_geometry('HERO_STRIP').cells[0]
    # The white border runs along the top edge, but the very corner of the box is cut round and shows the backdrop.
    assert near(pixel(frame, *scaled(main.box.x + main.box.w // 2, main.box.y + 2)), WHITE)
    corner = pixel(frame, *scaled(main.box.x + 1, main.box.y + 1))
    assert not near(corner, WHITE, 60), corner
    data = qc_frame('DATA_CARD', images)
    card = layout.layout_geometry('DATA_CARD').cells[0]
    assert near(pixel(data, *scaled(card.box.x + card.box.w // 2, card.box.y + card.box.h // 2)), COLOURS[0])
    assert not near(pixel(data, *scaled(card.box.x + 2, card.box.y + 2)), COLOURS[0], 40)


def test_main_card_casts_a_shadow_below_it(tmp_path):
    bright = tmp_path / 'bright.png'
    write_png(bright, 64, 36, lambda x, y: (250, 250, 250))
    images = [bright, *solid_images(tmp_path, 3)[1:]]
    frame = qc_frame('DATA_CARD', images)
    card = layout.layout_geometry('DATA_CARD').cells[0]
    below = pixel(frame, *scaled(800, card.box.bottom + 8))
    far = pixel(frame, *scaled(800, card.box.bottom + 70))
    assert sum(below) + 30 < sum(far), (below, far)


def test_inset_photo_is_turned_two_degrees(tmp_path):
    images = solid_images(tmp_path, 2)
    frame = qc_frame('FULL_BLEED_INSET', images)
    inset = layout.layout_geometry('FULL_BLEED_INSET').cells[1]

    def first_white_row(x_design):
        x = scaled(x_design, 0)[0]
        for y in range(scaled(0, inset.box.y - 60)[1], scaled(0, inset.box.y + 80)[1]):
            if near(pixel(frame, x, y), WHITE, 40):
                return y
        return None

    left, right = first_white_row(inset.box.x + 90), first_white_row(inset.box.right - 90)
    assert left is not None and right is not None
    rise = (inset.box.w - 180) * math.sin(math.radians(2)) * H / 1920
    assert abs(abs(left - right) - rise) <= 3, (left, right, rise)


def test_side_tiles_slide_in_and_settle_on_the_qc_frame(tmp_path):
    images = solid_images(tmp_path, 4)
    labels = [f'{k}:v' for k in range(4)]
    still = qc_frame('DATA_CARD', images)
    moving = frames_of(images[:3], layout.compose_layout('DATA_CARD', width=W, height=H, sources=labels[:3], accent=ACCENT, prefix='s0', frames=30, fps=30), 30)
    aux = layout.layout_geometry('DATA_CARD').cells[1]
    x, y = scaled(aux.box.x + aux.box.w // 2, aux.box.y + aux.box.h // 2)
    assert not near(pixel(moving[0], x, y), COLOURS[1]) and near(pixel(moving[-1], x, y), COLOURS[1])
    assert pixel(moving[-1], x, y) == pixel(still, x, y)
    assert not any(token in layout.compose_layout('DATA_CARD', width=W, height=H, sources=labels[:3], accent=ACCENT, prefix='q') for token in ("-t)/", 'pow(max(0'))


def test_shared_masks_give_the_qc_frame(tmp_path):
    images = solid_images(tmp_path, 5)
    for key in layout.LAYOUT_KEYS:
        count = len(layout.layout_geometry(key).cells)
        labels = [f'{k}:v' for k in range(count)]
        chrome, under, above = layout.compose_chrome(key, width=W, height=H, accent=ACCENT, prefix='c')
        still, masks = layout.compose_masks(key, width=W, height=H, prefix='n')
        body = layout.compose_layout(key, width=W, height=H, sources=labels, accent=ACCENT, prefix='s0', chrome=(under, above), masks=masks)
        shared = ';'.join(part for part in (chrome, still, body) if part)
        assert frames_of(images[:count], shared, 1)[0] == qc_frame(key, images), key


def test_long_graph_goes_through_a_file(tmp_path):
    short = ['ffmpeg', '-filter_complex', 'null', '-map', '[v]', 'out.mp4']
    assert renderer.graph_through_file(short, tmp_path / 'g.txt') == short and not (tmp_path / 'g.txt').exists()
    graph = 'null,' * (render_command.LAYOUT_GRAPH_MAX_CHARS // 5 + 1) + 'null'
    moved = renderer.graph_through_file(['ffmpeg', '-filter_complex', graph, '-map', '[v]', 'out.mp4'], tmp_path / 'g.txt')
    assert moved == ['ffmpeg', renderer.GRAPH_FILE_OPTION, str(tmp_path / 'g.txt'), '-map', '[v]', 'out.mp4']
    assert (tmp_path / 'g.txt').read_text(encoding='utf-8') == graph


def test_twelve_scene_hero_video_renders_with_the_graph_in_a_file(stage, tmp_path):  # noqa: F811
    refs = ['ref-a', 'ref-b', 'ref-c', 'ref-d']
    record = record_for(refs, scene_ms=400, scenes=(refs * 3)[:12])
    spec = build_render_command(record, preset({'layout_key': 'HERO_STRIP', 'accent_colour': '#FFD400'}), profile(), 'ref-ass', tool(), materialized(stage), voice_duration_ms=4800)
    graph = spec.argv[spec.argv.index('-filter_complex') + 1]
    assert len(graph) > render_command.LAYOUT_GRAPH_MAX_CHARS and '{image:3}' in spec.redacted_argv
    output = stage / 'out' / 'hero12.mp4'
    argv = renderer.graph_through_file(renderer.build_final_argv(spec.argv, FFMPEG, 'libx264', str(output)), tmp_path / 'graph.txt')
    assert renderer.GRAPH_FILE_OPTION in argv and len(subprocess.list2cmdline(argv)) < 32767
    done = subprocess.run(argv, capture_output=True, text=True, encoding='utf-8', errors='replace', stdin=subprocess.DEVNULL, timeout=900, check=False)
    assert done.returncode == 0, done.stderr[-2000:]
    main = layout.Box(40, 510, 1000, 620)
    # The voice of the stage lasts 3 s (-shortest): scene 6 starts at 2.4 s, its frame 9 is after the strip has settled.
    frame = grab_frame(output, 12 * 6 + 9)
    cells, _ = layout.slot_sources('HERO_STRIP', refs, 6)
    found = pixel_full(frame, main.x + main.w // 4, main.y + main.h // 3)
    assert all(abs(a - b) <= 40 for a, b in zip(found, {'ref-a': (220, 30, 30), 'ref-b': (30, 200, 60), 'ref-c': (40, 60, 230), 'ref-d': (230, 200, 20)}[cells[0]])), found


def pixel_full(frame, x, y):
    at = (y * 1080 + x) * 3
    return tuple(frame[at:at + 3])

