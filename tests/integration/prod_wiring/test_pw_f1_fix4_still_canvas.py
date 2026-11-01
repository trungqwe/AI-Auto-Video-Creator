"""PW-F1-FIX4: ảnh bài tối 1200x630 đi qua render thật và inspector thật; ảnh được đặt lên khung output trước khi thu nhỏ để SSIM không lệch ở vùng gần đen (FFmpeg ghim thật, không DB).

coveredIds: CT-QC-001
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

from render.adapters.frame_probe import FrameProbe
from render.adapters.real_output_inspector import ssim_between
from render.domain.quality_report import GateStatus

HERE = pathlib.Path(__file__).resolve().parent
D10_FIX1 = HERE / 'test_d10_fix1_hook_lead.py'


def load_module(name, path):
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


base = load_module('pw_f1_fix4_d10_fix1', D10_FIX1)
stage, render, judge, make_media = base.stage, base.render, base.judge, base.make_media
require_ffmpeg, MIN_SIMILARITY, d10, f10 = base.require_ffmpeg, base.MIN_SIMILARITY, base.d10, base.f10

STRIPES = ''.join(f',drawbox=x={x}:y=440:w=40:h=110:color=black:t=fill' for x in range(100, 701, 120))
DARK = f'color=c=0x010101:s=1200x630:r=1:d=1,drawbox=x=0:y=420:w=1200:h=150:color=0xF2D21B:t=fill{STRIPES}'


def staged_dark(tmp_path):
    plan = d10._build(d10._hook((0, 3000), (500, 1500)))
    placement = plan.to_render_package_inputs()['hook_placement']
    rig = stage(tmp_path, placement)
    make_media(rig.root / 'media' / 'thumb.png', DARK, '-frames:v', '1')
    return rig, placement


def test_dark_still_thumbnail_passes_thumbnail_gate(tmp_path):
    require_ffmpeg()
    rig, placement = staged_dark(tmp_path)
    evidence, hook_gate, thumb_gate = judge(rig, render(rig))
    assert thumb_gate.status is GateStatus.PASSED, thumb_gate.reason
    assert hook_gate.status is GateStatus.PASSED, hook_gate.reason
    assert evidence.thumbnail.asset_ref == placement['thumbnail_ref']


def test_ssim_prepares_the_still_on_the_output_canvas(tmp_path):
    require_ffmpeg()
    rig, _ = staged_dark(tmp_path)
    output = pathlib.Path(render(rig))
    probe = FrameProbe(ffmpeg_path=f10.FFMPEG)
    canvas = probe.frame_size(output)
    assert canvas == (1080, 1920)
    still = rig.root / 'media' / 'thumb.png'
    common = dict(width=90, height=160, timeout_seconds=120)
    without_canvas = ssim_between(f10.FFMPEG, output, 1000, still, None, **common)
    with_canvas = ssim_between(f10.FFMPEG, output, 1000, still, None, canvas=canvas, **common)
    print(f'without_canvas={without_canvas!r} with_canvas={with_canvas!r}')
    assert without_canvas is not None and with_canvas is not None
    assert with_canvas >= MIN_SIMILARITY
    assert with_canvas > without_canvas


def test_frame_size_reads_video_and_still(tmp_path):
    require_ffmpeg()
    still = tmp_path / 'dark.png'
    make_media(still, DARK, '-frames:v', '1')
    text = tmp_path / 'note.txt'
    text.write_text('not a media file', encoding='utf-8')
    probe = FrameProbe(ffmpeg_path=f10.FFMPEG)
    assert probe.frame_size(still) == (1200, 630)
    assert probe.frame_size(text) is None
