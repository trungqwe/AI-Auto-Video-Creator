"""PRS-LAYOUT-DOMAIN: the five presentation layouts of a 9:16 video (FR-PRS-001, FR-PRS-002, FR-PRS-006).

layout_geometry(key) is the single source of the geometry (image cells, bands, gradients, text slots) designed on a 1080x1920 canvas
(docs: Control LAYOUTS.md of 03/11/2026, approved by the Control self decision 02:12Z 03/11/2026).
compose_layout(...) is the single builder of the ffmpeg filter chain of one scene: the render calls it with frames (Ken Burns on the
main cell, every other layer still) and the QC calls it without frames (one still frame, the final state of the scene).
compose_chrome(...) paints the bands, cards and gradients once (two transparent layers) for every scene of a video.
slot_sources(...) decides which image fills which cell for a scene; safe_zone_violations(...) checks a geometry against the
platform safe zones without ffmpeg. Text is drawn by the subtitle (ASS) layer, never here.
Pure domain: no I/O, no clock, no process execution.
coveredIds: FR-PRS-001, FR-PRS-002, FR-PRS-006
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from render.domain.render_command import BACKDROP_BLUR_SIGMA, BACKDROP_SHRINK, ZOOM_FRAME_STEP

HERO_STRIP = 'HERO_STRIP'
MOSAIC_GRID = 'MOSAIC_GRID'
FULL_BLEED_INSET = 'FULL_BLEED_INSET'
SPLIT_STACK = 'SPLIT_STACK'
DATA_CARD = 'DATA_CARD'
LAYOUT_KEYS = (HERO_STRIP, MOSAIC_GRID, FULL_BLEED_INSET, SPLIT_STACK, DATA_CARD)
DEFAULT_LAYOUT = HERO_STRIP
# Fewest distinct images a layout is drawn with (LAYOUTS.md section 4.2); with fewer the render keeps the single-image scene.
MIN_IMAGES = {HERO_STRIP: 2, MOSAIC_GRID: 3, FULL_BLEED_INSET: 1, SPLIT_STACK: 2, DATA_CARD: 1}
DESIGN_WIDTH = 1080
DESIGN_HEIGHT = 1920
LAYOUT_ZOOM = 0.06
UNKNOWN_LAYOUT = 'unknown_layout'
INVALID_LAYOUT_INPUT = 'invalid_layout_input'

# Safe zones of the 1080x1920 design canvas (LAYOUTS.md section 2).
PLATFORM_TOP_ROWS = (0, 220)
SUBTITLE_ROWS = (1380, 1580)
PLATFORM_BOTTOM_ROWS = (1600, 1920)
TEXT_LEFT = 60
TEXT_RIGHT = 1020
RIGHT_RAIL_ROWS = (1000, 1600)
RIGHT_RAIL_LEFT = 960

_COLOURS = {'white': 'FFFFFF', 'black': '101010', 'red': 'FF3B30'}
_ACCENT_RE = re.compile(r'#[0-9A-Fa-f]{6}')
_LABEL_RE = re.compile(r'[A-Za-z0-9_:]+')


class LayoutRejected(ValueError):
    """A layout input is unknown or invalid: `code` is the stable error code and `reason` names the offending field."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(f'{code}: {reason}')
        self.code = code
        self.reason = reason


@dataclass(frozen=True)
class Box:
    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h

    def meets_rows(self, rows: tuple[int, int]) -> bool:
        return self.y < rows[1] and rows[0] < self.bottom


@dataclass(frozen=True)
class Cell:
    """An image slot; the picture is cut to cover the box minus the border."""

    name: str
    box: Box
    border: int = 0
    border_colour: str = 'white'


@dataclass(frozen=True)
class Shape:
    """A flat band or card; role 'emphasis' holds an emphasis layer, 'backing' sits behind the subtitles, 'outline' is drawn as a frame."""

    name: str
    box: Box
    colour: str
    opacity: float = 1.0
    radius: int = 0
    role: str = 'band'


@dataclass(frozen=True)
class Gradient:
    """A black band whose opacity goes linearly from top to bottom (0..1)."""

    name: str
    box: Box
    top: float
    bottom: float


@dataclass(frozen=True)
class TextSlot:
    """Where the subtitle layer may write text of this layout (title, category, emphasis, labels)."""

    name: str
    box: Box
    size: int
    max_lines: int
    max_chars: int


@dataclass(frozen=True)
class LayoutGeometry:
    key: str
    backdrop_level: float | None
    layers: tuple[Cell | Shape | Gradient, ...]
    texts: tuple[TextSlot, ...]
    main: str
    rotating: tuple[str, ...] = ()

    @property
    def cells(self) -> tuple[Cell, ...]:
        return tuple(layer for layer in self.layers if isinstance(layer, Cell))


def _hero() -> LayoutGeometry:
    strip = tuple(Cell(f'strip{k}', Box(40 + 340 * k, 1160, 320, 190), 6 if k == 0 else 3, 'accent' if k == 0 else 'white') for k in range(3))
    return LayoutGeometry(
        key=HERO_STRIP,
        backdrop_level=0.45,
        layers=(
            Shape('title_band', Box(0, 310, 1080, 170), 'accent'),
            Cell('main', Box(34, 504, 1012, 632), 6, 'white'),
            Shape('number_card', Box(70, 966, 330, 132), 'black', 0.82, 16, 'emphasis'),
            *strip,
            Gradient('subtitle_shade', Box(0, 1340, 1080, 580), 0.0, 0.8),
        ),
        texts=(
            TextSlot('title', Box(60, 322, 960, 140), 56, 2, 30),
            TextSlot('number', Box(92, 972, 290, 90), 84, 1, 8),
            TextSlot('number_caption', Box(92, 1064, 290, 30), 26, 1, 22),
            TextSlot('position_dots', Box(60, 1352, 900, 24), 20, 1, 12),
        ),
        main='main',
    )


def _mosaic() -> LayoutGeometry:
    cells = tuple(Cell(f'grid{k}', Box(544 * (k % 2), 476 + 444 * (k // 2), 536, 436)) for k in range(4))
    return LayoutGeometry(
        key=MOSAIC_GRID,
        backdrop_level=0.18,
        layers=(
            Shape('title_band', Box(0, 300, 1080, 160), 'black', 0.92),
            Shape('category_bar', Box(0, 300, 16, 160), 'red'),
            *cells,
            Shape('badge_ring', Box(422, 780, 236, 236), 'black', 1.0, 118, 'emphasis'),
            Shape('badge', Box(430, 788, 220, 220), 'accent', 1.0, 110, 'emphasis'),
            Shape('subtitle_backing', Box(0, 1360, 1080, 560), 'black', 0.92, 0, 'backing'),
        ),
        texts=(
            TextSlot('category', Box(60, 316, 960, 40), 32, 1, 40),
            TextSlot('title', Box(60, 360, 960, 56), 44, 1, 42),
            TextSlot('badge_number', Box(450, 820, 180, 110), 110, 1, 4),
            TextSlot('badge_caption', Box(450, 940, 180, 36), 30, 1, 12),
        ),
        main='grid0',
        rotating=tuple(cell.name for cell in cells),
    )


def _full_bleed() -> LayoutGeometry:
    return LayoutGeometry(
        key=FULL_BLEED_INSET,
        backdrop_level=None,
        layers=(
            Cell('background', Box(0, 0, 1080, 1920)),
            Gradient('top_shade', Box(0, 0, 1080, 560), 0.75, 0.0),
            Gradient('bottom_shade', Box(0, 1240, 1080, 680), 0.0, 0.85),
            Cell('inset', Box(70, 570, 908, 588), 14, 'white'),
            Shape('quote_card', Box(90, 1210, 900, 150), 'black', 0.8, 14, 'emphasis'),
            Shape('quote_bar', Box(90, 1210, 10, 150), 'accent', 1.0, 0, 'emphasis'),
        ),
        texts=(
            TextSlot('category', Box(60, 318, 960, 40), 32, 1, 40),
            TextSlot('title', Box(60, 362, 960, 140), 58, 2, 28),
            TextSlot('ai_label', Box(780, 510, 230, 40), 26, 1, 16),
            TextSlot('quote', Box(130, 1226, 820, 110), 40, 2, 32),
        ),
        main='background',
    )


def _split() -> LayoutGeometry:
    return LayoutGeometry(
        key=SPLIT_STACK,
        backdrop_level=0.3,
        layers=(
            Cell('top', Box(0, 290, 1080, 600)),
            Cell('bottom', Box(0, 1040, 1080, 880)),
            Shape('middle_band', Box(0, 890, 1080, 150), 'black'),
            Shape('middle_rule_top', Box(0, 890, 1080, 6), 'accent'),
            Shape('middle_rule_bottom', Box(0, 1034, 1080, 6), 'accent'),
            Gradient('subtitle_shade', Box(0, 1300, 1080, 620), 0.0, 0.85),
            Shape('top_label', Box(40, 320, 470, 64), 'accent', 1.0, 10, 'emphasis'),
            Shape('bottom_label', Box(40, 1072, 450, 64), 'white', 1.0, 10, 'emphasis'),
        ),
        texts=(
            TextSlot('title', Box(60, 900, 900, 130), 46, 2, 34),
            TextSlot('arrow', Box(976, 945, 40, 40), 40, 1, 1),
            TextSlot('top_label', Box(60, 328, 440, 48), 34, 1, 26),
            TextSlot('bottom_label', Box(60, 1080, 420, 48), 34, 1, 24),
        ),
        main='top',
    )


def _data() -> LayoutGeometry:
    return LayoutGeometry(
        key=DATA_CARD,
        backdrop_level=0.22,
        layers=(
            Shape('category_pill', Box(60, 330, 300, 54), 'red', 1.0, 27),
            Cell('main', Box(60, 580, 960, 540)),
            Cell('aux0', Box(90, 1050, 208, 138), 4, 'white'),
            Cell('aux1', Box(310, 1050, 208, 138), 4, 'white'),
            Shape('counter_pill', Box(890, 600, 110, 48), 'black', 0.7, 24),
            Shape('number_rule', Box(60, 1210, 960, 4), 'accent', 1.0, 0, 'emphasis'),
        ),
        texts=(
            TextSlot('category', Box(84, 334, 260, 44), 32, 1, 14),
            TextSlot('title', Box(60, 404, 960, 132), 54, 2, 30),
            TextSlot('counter', Box(900, 606, 90, 36), 28, 1, 7),
            TextSlot('number', Box(60, 1216, 400, 156), 136, 1, 6),
            TextSlot('explain', Box(480, 1236, 480, 44), 34, 1, 26),
            TextSlot('sub_line', Box(480, 1286, 480, 44), 34, 1, 26),
        ),
        main='main',
    )


_BUILDERS = {HERO_STRIP: _hero, MOSAIC_GRID: _mosaic, FULL_BLEED_INSET: _full_bleed, SPLIT_STACK: _split, DATA_CARD: _data}


def layout_geometry(key: object) -> LayoutGeometry:
    """Geometry of one of the five LAYOUT_KEYS on the 1080x1920 design canvas; any other key raises LayoutRejected(unknown_layout)."""
    if not isinstance(key, str) or key not in _BUILDERS:
        raise LayoutRejected(UNKNOWN_LAYOUT, 'layout_key')
    return _BUILDERS[key]()


def safe_zone_violations(geometry: LayoutGeometry) -> tuple[str, ...]:
    """Names of the layers and text slots of geometry that break the safe zones; empty when the layout is safe.

    Text slots and emphasis shapes stay out of the platform rows (top 0-220, bottom 1600-1920) and the subtitle rows 1380-1580;
    text stays inside x 60-1020 and, in the rows 1000-1600 of the right button rail, left of x 960; flat bands do not cover the
    subtitle rows (gradients and the subtitle backing may); every box stays inside the canvas. Pictures may bleed anywhere."""
    found: list[str] = []
    boxes = [(layer.name, layer.box) for layer in geometry.layers] + [(text.name, text.box) for text in geometry.texts]
    for name, box in boxes:
        if box.x < 0 or box.y < 0 or box.right > DESIGN_WIDTH or box.bottom > DESIGN_HEIGHT or box.w <= 0 or box.h <= 0:
            found.append(f'{name}:outside_canvas')
    for text in geometry.texts:
        box = text.box
        if any(box.meets_rows(rows) for rows in (PLATFORM_TOP_ROWS, SUBTITLE_ROWS, PLATFORM_BOTTOM_ROWS)):
            found.append(f'{text.name}:text_in_reserved_rows')
        if box.x < TEXT_LEFT or box.right > TEXT_RIGHT:
            found.append(f'{text.name}:text_outside_margins')
        if box.meets_rows(RIGHT_RAIL_ROWS) and box.right > RIGHT_RAIL_LEFT:
            found.append(f'{text.name}:text_in_right_rail')
    for layer in geometry.layers:
        if isinstance(layer, Shape) and layer.role in ('band', 'emphasis', 'outline') and layer.box.meets_rows(SUBTITLE_ROWS):
            found.append(f'{layer.name}:shape_in_subtitle_rows')
        if isinstance(layer, Shape) and layer.role == 'emphasis' and any(layer.box.meets_rows(r) for r in (PLATFORM_TOP_ROWS, PLATFORM_BOTTOM_ROWS)):
            found.append(f'{layer.name}:emphasis_in_platform_rows')
    return tuple(found)


def slot_sources(key: object, images: Sequence[str], scene_index: int) -> tuple[tuple[str, ...], int]:
    """(source per cell in layer order, active cell) for scene scene_index of a video whose distinct images are `images` in plan order.

    HERO_STRIP and DATA_CARD: the scene image is the main cell and the next images fill the strip or the side cells; MOSAIC_GRID:
    pages of four images, the scene image is the active (outlined, moving) cell of its page; FULL_BLEED_INSET: the first image is
    the background and the scene image (from the second on) the inset; SPLIT_STACK: images at even positions rotate in the top half,
    odd positions in the bottom half. Fewer images than cells repeat images cyclically."""
    geometry = layout_geometry(key)
    if isinstance(images, str) or not isinstance(images, Sequence) or not images or not all(isinstance(i, str) and i for i in images):
        raise LayoutRejected(INVALID_LAYOUT_INPUT, 'images')
    if isinstance(scene_index, bool) or not isinstance(scene_index, int) or scene_index < 0:
        raise LayoutRejected(INVALID_LAYOUT_INPUT, 'scene_index')
    n, i, count = len(images), scene_index, len(geometry.cells)
    if geometry.key == MOSAIC_GRID:
        page = (i // count) * count
        return tuple(images[(page + k) % n] for k in range(count)), i % count
    if geometry.key == FULL_BLEED_INSET:
        inset = images[1 + i % (n - 1)] if n > 1 else images[0]
        return (images[0], inset), 0
    if geometry.key == SPLIT_STACK:
        tops, bottoms = images[0::2], images[1::2] or images[0::2]
        return (tops[i % len(tops)], bottoms[i % len(bottoms)]), 0
    return tuple(images[(i + k) % n] for k in range(count)), 0


def _scaled(box: Box, width: int, height: int) -> Box:
    def even(value: float) -> int:
        return max(2, 2 * round(value / 2))

    sx, sy = width / DESIGN_WIDTH, height / DESIGN_HEIGHT
    return Box(round(box.x * sx), round(box.y * sy), even(box.w * sx), even(box.h * sy))


def _inner(cell: Cell) -> Box:
    return Box(cell.box.x + cell.border, cell.box.y + cell.border, cell.box.w - 2 * cell.border, cell.box.h - 2 * cell.border)


def _colour(name: str, accent: str) -> str:
    return '0x' + (accent[1:].upper() if name == 'accent' else _COLOURS[name])


def _mask(box: Box, radius: int, scale: float, opacity: float, label: str) -> str:
    """Grey alpha mask of a box with rounded corners (radius in design pixels, scaled), multiplied by opacity."""
    r = max(0, round(radius * scale))
    w, h = box.w, box.h
    inside = '1' if r == 0 else f'lte(pow(max(max({r}-X,X-({w - 1}-{r})),0),2)+pow(max(max({r}-Y,Y-({h - 1}-{r})),0),2),{r * r})'
    return f"color=c=white:s={w}x{h}:r=1:d=1,format=gray,geq=lum='{round(255 * opacity)}*{inside}'[{label}]"


class _Graph:
    def __init__(self, prefix: str, width: int, height: int, accent: str) -> None:
        self.prefix, self.width, self.height, self.accent = prefix, width, height, accent
        self.chains: list[str] = []
        self.count = 0

    def label(self, kind: str) -> str:
        self.count += 1
        return f'{self.prefix}{kind}{self.count}'

    def box(self, box: Box) -> Box:
        return _scaled(box, self.width, self.height)

    def over(self, base: str, top: str, box: Box, repeat: bool = False) -> str:
        out = self.label('o')
        tail = ':eof_action=repeat' if repeat else ''
        self.chains.append(f'[{base}][{top}]overlay=x={box.x}:y={box.y}:format=auto{tail}[{out}]')
        return out

    def flat(self, box: Box, colour: str, opacity: float, radius: int) -> str:
        out = self.label('f')
        if radius == 0 and opacity >= 1:
            self.chains.append(f'color=c={colour}:s={box.w}x{box.h}:r=1:d=1,format=rgba[{out}]')
            return out
        mask, fill = self.label('m'), self.label('c')
        self.chains.append(_mask(box, radius, self.width / DESIGN_WIDTH, opacity, mask))
        self.chains.append(f'color=c={colour}:s={box.w}x{box.h}:r=1:d=1,format=rgba[{fill}]')
        self.chains.append(f'[{fill}][{mask}]alphamerge[{out}]')
        return out

    def gradient(self, box: Box, top: float, bottom: float) -> str:
        mask, fill, out = self.label('m'), self.label('c'), self.label('g')
        expr = f'255*({top:g}+({bottom:g}-{top:g})*Y/{max(1, box.h - 1)})'
        self.chains.append(f"color=c=white:s={box.w}x{box.h}:r=1:d=1,format=gray,geq=lum='{expr}'[{mask}]")
        self.chains.append(f'color=c=black:s={box.w}x{box.h}:r=1:d=1,format=rgba[{fill}]')
        self.chains.append(f'[{fill}][{mask}]alphamerge[{out}]')
        return out

    def ring(self, canvas: str, outer: Box, inner: Box, colour: str) -> str:
        """The border of a cell: the four bands of outer around inner, painted opaque on a transparent canvas."""
        out = self.label('r')
        sides = (
            (outer.x, outer.y, outer.w, inner.y - outer.y), (outer.x, inner.bottom, outer.w, outer.bottom - inner.bottom),
            (outer.x, inner.y, inner.x - outer.x, inner.h), (inner.right, inner.y, outer.right - inner.right, inner.h),
        )
        boxes = ','.join(f'drawbox=x={x}:y={y}:w={w}:h={h}:color={colour}@1:t=fill:replace=1' for x, y, w, h in sides if w > 0 and h > 0)
        self.chains.append(f'[{canvas}]{boxes}[{out}]')
        return out

    def picture(self, source: str, box: Box, motion: str = '') -> str:
        out = self.label('p')
        self.chains.append(
            f'[{source}]scale={box.w}:{box.h}:force_original_aspect_ratio=increase,crop={box.w}:{box.h},setsar=1{motion}[{out}]'
        )
        return out


def _cell_zoom(frames: int, fps: int | float) -> str:
    """Ken Burns 1.00 to 1.06 inside a cell over frames frames (same perspective scheme as the single-image scene zoom)."""
    progress = f'(in-1)*{ZOOM_FRAME_STEP}/{frames}'
    inset = f'{LAYOUT_ZOOM / 2:g}*{progress}/(1+{LAYOUT_ZOOM:g}*{progress})'
    return (
        f",loop=loop={frames - 1}:size=1,setpts=N/{fps}/TB,select='not(mod(n,{ZOOM_FRAME_STEP}))',"
        f"perspective=x0='W*{inset}':y0='H*{inset}':x1='W-W*{inset}':y1='H*{inset}':x2='W*{inset}':y2='H-H*{inset}':x3='W-W*{inset}':y3='H-H*{inset}':eval=frame"
    )


def _checked(key: object, width: object, height: object, accent: object, prefix: object) -> LayoutGeometry:
    geometry = layout_geometry(key)
    if not all(isinstance(v, int) and not isinstance(v, bool) and v >= 2 for v in (width, height)):
        raise LayoutRejected(INVALID_LAYOUT_INPUT, 'size')
    if not isinstance(accent, str) or _ACCENT_RE.fullmatch(accent) is None:
        raise LayoutRejected(INVALID_LAYOUT_INPUT, 'accent')
    if not isinstance(prefix, str) or _LABEL_RE.fullmatch(prefix) is None:
        raise LayoutRejected(INVALID_LAYOUT_INPUT, 'prefix')
    return geometry


def compose_chrome(key: object, *, width: int, height: int, accent: str, prefix: str) -> tuple[str, str, str]:
    """(chains, under, above): two still, transparent, full-frame layers holding every band, card, gradient and cell border of the layout.

    under holds the layers listed before the first cell, above all the others. The render builds them once per video and splits
    them over its scenes (a graph per scene stays short); compose_layout without chrome builds them itself, so the QC frame and the
    render frame are painted from the same layers."""
    geometry = _checked(key, width, height, accent, prefix)
    graph = _Graph(prefix, width, height, accent)
    first = next(index for index, layer in enumerate(geometry.layers) if isinstance(layer, Cell))
    labels = []
    for part in (geometry.layers[:first], geometry.layers[first:]):
        canvas = graph.label('k')
        graph.chains.append(f'color=c=black@0:s={width}x{height}:r=1:d=1,format=rgba[{canvas}]')
        for layer in part:
            if isinstance(layer, Cell):
                if layer.border:
                    canvas = graph.ring(canvas, graph.box(layer.box), graph.box(_inner(layer)), _colour(layer.border_colour, accent))
                continue
            box = graph.box(layer.box)
            if isinstance(layer, Gradient):
                top = graph.gradient(box, layer.top, layer.bottom)
            else:
                top = graph.flat(box, _colour(layer.colour, accent), layer.opacity, layer.radius)
            canvas = graph.over(canvas, top, box)
        labels.append(canvas)
    return ';'.join(graph.chains), labels[0], labels[1]


def compose_layout(
    key: object,
    *,
    width: int,
    height: int,
    sources: Sequence[str],
    accent: str,
    prefix: str,
    active: int = 0,
    frames: int | None = None,
    fps: int | float | None = None,
    chrome: tuple[str, str] | None = None,
) -> str:
    """The single builder of a layout frame: a filter chain whose last element has no output label (the caller appends to it).

    sources holds one single-frame stream label per cell of layout_geometry(key).cells (slot_sources gives them); each label is
    consumed once (the chain splits a label used by the backdrop and a cell). Drawing order: the blurred, darkened backdrop of the
    first source (FULL_BLEED_INSET: black), the under chrome, the cells in geometry order, the above chrome; chrome is the pair of
    labels made by compose_chrome, built here when None. 'accent' paints with the preset accent (#RRGGBB). The main cell (with
    rotating cells the active one, also outlined with the accent) zooms 1.00 to 1.06 over `frames` frames when frames is given:
    what lies under it is one still frame looped, what lies above it is still frames repeated by overlay; without frames (QC) the
    result is the still frame at zoom 1.00 with no time expression."""
    geometry = _checked(key, width, height, accent, prefix)
    cells = geometry.cells
    if isinstance(sources, str) or len(sources) != len(cells) or not all(isinstance(s, str) and _LABEL_RE.fullmatch(s) for s in sources):
        raise LayoutRejected(INVALID_LAYOUT_INPUT, 'sources')
    if frames is not None and (isinstance(frames, bool) or not isinstance(frames, int) or frames < 1 or fps is None):
        raise LayoutRejected(INVALID_LAYOUT_INPUT, 'frames')
    graph = _Graph(prefix, width, height, accent)
    if chrome is None:
        chains, under, above = compose_chrome(key, width=width, height=height, accent=accent, prefix=prefix + 'c')
        graph.chains.append(chains)
    elif isinstance(chrome, tuple) and len(chrome) == 2 and all(isinstance(c, str) and _LABEL_RE.fullmatch(c) for c in chrome):
        under, above = chrome
    else:
        raise LayoutRejected(INVALID_LAYOUT_INPUT, 'chrome')
    main = geometry.rotating[active % len(geometry.rotating)] if geometry.rotating else geometry.main
    uses: dict[str, list[str]] = {}
    wanted = list(sources) + ([sources[0]] if geometry.backdrop_level is not None else [])
    for source in dict.fromkeys(wanted):
        count = wanted.count(source)
        if count == 1:
            uses[source] = [source]
            continue
        outs = [graph.label('s') for _ in range(count)]
        graph.chains.append(f'[{source}]split={count}' + ''.join(f'[{o}]' for o in outs))
        uses[source] = outs
    feed = {cell.name: uses[source].pop(0) for cell, source in zip(cells, sources)}
    base = graph.label('b')
    if geometry.backdrop_level is None:
        graph.chains.append(f'color=c=black:s={width}x{height}:r=1:d=1,format=rgba[{base}]')
    else:
        level = geometry.backdrop_level
        small = f'{max(2, width // BACKDROP_SHRINK)}:{max(2, height // BACKDROP_SHRINK)}'
        graph.chains.append(
            f'[{uses[sources[0]].pop(0)}]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},'
            f'scale={small},gblur=sigma={BACKDROP_BLUR_SIGMA},colorchannelmixer=rr={level:g}:gg={level:g}:bb={level:g},'
            f'scale={width}:{height}:flags=bilinear,setsar=1[{base}]'
        )
    whole = Box(0, 0, width, height)
    base = graph.over(base, under, whole)
    moving = False
    for cell in cells:
        box = graph.box(cell.box)
        inner = graph.box(_inner(cell))
        if cell.name != main:
            base = graph.over(base, graph.picture(feed[cell.name], inner), inner, moving)
            continue
        if frames is not None:
            looped = graph.label('l')
            graph.chains.append(f'[{base}]loop=loop={frames - 1}:size=1,setpts=N/{fps}/TB[{looped}]')
            base, moving = looped, True
        base = graph.over(base, graph.picture(feed[cell.name], inner, _cell_zoom(frames, fps) if moving else ''), inner, moving)
        if geometry.rotating:
            outlined = graph.label('a')
            thick = max(2, round(8 * width / DESIGN_WIDTH))
            graph.chains.append(f'[{base}]drawbox=x={box.x}:y={box.y}:w={box.w}:h={box.h}:color={_colour("accent", accent)}:t={thick}[{outlined}]')
            base = outlined
    base = graph.over(base, above, whole, moving)
    last = graph.chains.pop()
    return ';'.join([*graph.chains, last[: last.rindex('[')]])
