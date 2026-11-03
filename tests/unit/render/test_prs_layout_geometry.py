"""PRS-LAYOUT-DOMAIN: hình học năm bố cục, vùng an toàn, chọn ảnh cho từng ô và đồ thị lọc không có biểu thức thời gian ở nhánh QC.

Không chạy FFmpeg; test dựng khung thật nằm ở tests/integration/render/test_prs_layout_graph.py.

coveredIds: FR-PRS-001, FR-PRS-002, FR-PRS-006
"""
import dataclasses

import pytest

from render.domain import layout
from render.domain.render_command import _is_unsafe

KEYS = ('HERO_STRIP', 'MOSAIC_GRID', 'FULL_BLEED_INSET', 'SPLIT_STACK', 'DATA_CARD')
CELLS = {'HERO_STRIP': 4, 'MOSAIC_GRID': 4, 'FULL_BLEED_INSET': 2, 'SPLIT_STACK': 2, 'DATA_CARD': 3}


def test_exactly_five_layouts_and_hero_strip_is_the_default():
    assert layout.LAYOUT_KEYS == KEYS
    assert layout.DEFAULT_LAYOUT == 'HERO_STRIP'
    for key in KEYS:
        geometry = layout.layout_geometry(key)
        assert geometry.key == key
        assert len(geometry.cells) == CELLS[key]
        assert geometry.main in {cell.name for cell in geometry.cells}
    for bad in ('hero_strip', 'GRID', '', None, 3):
        with pytest.raises(layout.LayoutRejected) as caught:
            layout.layout_geometry(bad)
        assert caught.value.code == 'unknown_layout'


def test_every_layout_keeps_text_and_emphasis_out_of_the_reserved_zones():
    for key in KEYS:
        assert layout.safe_zone_violations(layout.layout_geometry(key)) == (), key


def test_safe_zone_check_names_each_broken_rule():
    hero = layout.layout_geometry('HERO_STRIP')
    bad_texts = (
        layout.TextSlot('in_subtitles', layout.Box(60, 1390, 400, 60), 40, 1, 20),
        layout.TextSlot('in_rail', layout.Box(500, 1100, 480, 40), 34, 1, 20),
        layout.TextSlot('off_margin', layout.Box(40, 600, 300, 40), 34, 1, 20),
        layout.TextSlot('in_top_ui', layout.Box(60, 100, 300, 40), 34, 1, 20),
    )
    bad_layers = (layout.Shape('card_on_subtitles', layout.Box(70, 1370, 330, 132), 'black', 0.8, 16, 'emphasis'),)
    broken = dataclasses.replace(hero, texts=hero.texts + bad_texts, layers=hero.layers + bad_layers)
    assert set(layout.safe_zone_violations(broken)) == {
        'in_subtitles:text_in_reserved_rows', 'in_rail:text_in_right_rail', 'off_margin:text_outside_margins',
        'in_top_ui:text_in_reserved_rows', 'card_on_subtitles:shape_in_subtitle_rows',
    }
    shaded = dataclasses.replace(hero, layers=hero.layers + (layout.Gradient('shade', layout.Box(0, 1300, 1080, 620), 0.0, 0.9),))
    assert layout.safe_zone_violations(shaded) == ()


def test_slot_sources_follow_the_layout_rules():
    six = ('a', 'b', 'c', 'd', 'e', 'f')
    assert layout.slot_sources('HERO_STRIP', six, 2) == (('c', 'd', 'e', 'f'), 0)
    assert layout.slot_sources('HERO_STRIP', ('a', 'b'), 1) == (('b', 'a', 'b', 'a'), 0)
    assert layout.slot_sources('MOSAIC_GRID', six, 1) == (('a', 'b', 'c', 'd'), 1)
    assert layout.slot_sources('MOSAIC_GRID', six, 5) == (('e', 'f', 'a', 'b'), 1)
    assert layout.slot_sources('FULL_BLEED_INSET', ('a',), 3) == (('a', 'a'), 0)
    assert [layout.slot_sources('FULL_BLEED_INSET', ('a', 'b', 'c'), i)[0] for i in range(3)] == [('a', 'b'), ('a', 'c'), ('a', 'b')]
    assert [layout.slot_sources('SPLIT_STACK', ('a', 'b', 'c'), i)[0] for i in range(2)] == [('a', 'b'), ('c', 'b')]
    assert layout.slot_sources('DATA_CARD', six, 5) == (('f', 'a', 'b'), 0)
    for images, index in (((), 0), (('a', ''), 0), ('ab', 0), (('a',), -1), (('a',), True)):
        with pytest.raises(layout.LayoutRejected):
            layout.slot_sources('HERO_STRIP', images, index)


def _sources(key):
    return [f'{k}:v' for k in range(CELLS[key])]


def test_qc_branch_has_no_time_expression_and_render_branch_moves_only_the_main_cell():
    for key in KEYS:
        still = layout.compose_layout(key, width=1080, height=1920, sources=_sources(key), accent='#FFD400', prefix='q')
        for token in ('loop=', 'setpts', 'perspective', 'eval=frame', 'select='):
            assert token not in still, (key, token)
        moving = layout.compose_layout(key, width=1080, height=1920, sources=_sources(key), accent='#FFD400', prefix='s0', frames=90, fps=30)
        assert moving.count('perspective=') == 1, key
        assert moving.count('loop=loop=89:size=1') == 2, key
        assert not _is_unsafe(moving.replace(';', '')), key
        assert not still.rstrip().endswith(']'), key
        assert '0xFFD400' in still


def test_rotating_grid_outlines_and_moves_the_active_cell():
    sources = _sources('MOSAIC_GRID')
    graph = layout.compose_layout('MOSAIC_GRID', width=1080, height=1920, sources=sources, accent='#FF3B30', prefix='g', active=3, frames=30, fps=30)
    assert 'drawbox=x=544:y=920:w=536:h=436:color=0xFF3B30:t=8' in graph
    assert graph.index('[3:v]') < graph.index('perspective=')


def test_compose_rejects_unknown_or_unsafe_input():
    good = dict(width=1080, height=1920, sources=_sources('HERO_STRIP'), accent='#FFD400', prefix='s0')
    for change in ({'accent': 'yellow'}, {'sources': ['0:v']}, {'sources': ['0:v', '1:v', '2;v', '3:v']}, {'prefix': 's 0'},
                   {'width': 0}, {'frames': 0, 'fps': 30}, {'frames': 30}):
        with pytest.raises(layout.LayoutRejected) as caught:
            layout.compose_layout('HERO_STRIP', **{**good, **change})
        assert caught.value.code == 'invalid_layout_input', change
    with pytest.raises(layout.LayoutRejected):
        layout.compose_layout('NOPE', **good)


def test_minimum_images_and_shared_chrome():
    assert layout.MIN_IMAGES == {'HERO_STRIP': 2, 'MOSAIC_GRID': 3, 'FULL_BLEED_INSET': 1, 'SPLIT_STACK': 2, 'DATA_CARD': 1}
    for key in KEYS:
        chains, under, above = layout.compose_chrome(key, width=1080, height=1920, accent='#FFD400', prefix='c')
        assert chains.endswith(f'[{above}]') and f'[{under}]' in chains
        mask_chains, masks = layout.compose_masks(key, width=1080, height=1920, prefix='n')
        assert len(masks) == layout.mask_count(key) and all(f'[{m}]' in mask_chains for m in masks)
        shared = layout.compose_layout(key, width=1080, height=1920, sources=_sources(key), accent='#FFD400', prefix='s1', chrome=(under, above), masks=masks)
        # PRS-LAYOUT-POLISH: bands, shadows and corner masks are built once per video; a scene only merges a mask into a rounded tile.
        rounded = sum(1 for cell in layout.layout_geometry(key).cells if cell.radius)
        assert 'geq=' not in shared and 'gblur=' not in shared.split('[s1b')[1] and shared.count('alphamerge') == rounded
        assert shared.count(f'[{under}]') == 1 and shared.count(f'[{above}]') == 1
        with pytest.raises(layout.LayoutRejected):
            layout.compose_layout(key, width=1080, height=1920, sources=_sources(key), accent='#FFD400', prefix='s1', chrome=('a;b', above))
