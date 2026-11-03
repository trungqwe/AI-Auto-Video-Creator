"""PRS-LAYOUT-TEXT: the words a presentation layout writes on the video, as ASS styles and Dialogue rows (FR-PRS-002, FR-PRS-006).

The text slots come from render.domain.layout.layout_geometry (design canvas 1080x1920, scaled to the PlayRes of the ASS file):
the title band (the short AI title of the plan, else the first sentence of the narration cut at a word boundary to TITLE_MAX_CHARS
characters with an ellipsis), the category (the hook intent of the script), the emphasis number (the first word of the narration
that holds a digit, verbatim, popping when it is spoken; no number, no number layer), the quote of FULL_BLEED_INSET (a quoted span
of the script, else its shortest sentence that fits), the two side labels of SPLIT_STACK (the contrast pair of the plan), the image
counter of DATA_CARD and the "AI illustration" label on every cell that shows an ai_generated picture, scene by scene. Text is cut
to the max_chars and max_lines of its slot, never wrapped by libass (q2), and is hidden while the hook or the thumbnail covers the
frame. Pure domain: no I/O, no clock, no ffmpeg.
coveredIds: FR-PRS-002, FR-PRS-006
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass

from render.domain.layout import (
    DATA_CARD,
    DESIGN_HEIGHT,
    DESIGN_WIDTH,
    FULL_BLEED_INSET,
    HERO_STRIP,
    MIN_IMAGES,
    MOSAIC_GRID,
    RIGHT_RAIL_LEFT,
    RIGHT_RAIL_ROWS,
    SPLIT_STACK,
    TEXT_LEFT,
    TEXT_RIGHT,
    LayoutRejected,
    layout_geometry,
    slot_sources,
)

AI_LABEL_TEXT = 'AI illustration'
AI_LABEL_SIZE = 26
GLYPH_WIDTH = 0.62
AI_LABEL_INSET = 12
TITLE_MAX_CHARS = 48
ELLIPSIS = '…'
ARROW = '▼'
NUMBER_POP_MS = 300
LAYER = 1
INK, WHITE, RED, GREY = '#101010', '#FFFFFF', '#FF3B30', '#B8B8B8'
LABEL_BOX = '&H59000000'
_NUMBER_WORD = re.compile(r'\d')
_EDGE = re.compile(r'^[^\w$€£]+|[^\w%°]+$')
_QUOTED = re.compile('[“"]([^”"]{8,})[”"]')
_SENTENCE = re.compile(r'[^.!?]+[.!?]?')


@dataclass(frozen=True)
class LayoutScene:
    """One scene of the render timeline: its window and its visual refs (the first one is the scene image)."""

    start_ms: int
    end_ms: int
    refs: tuple[str, ...]


@dataclass(frozen=True)
class LayoutRows:
    """ASS styles and Dialogue rows of the layout text; values names what was written (for the report and the tests)."""

    styles: tuple[str, ...]
    events: tuple[str, ...]
    values: Mapping[str, object]


@dataclass(frozen=True)
class _Look:
    size: int
    colour: str
    italic: bool = False
    shadow: int = 0
    box: bool = False
    bold: bool = True


# Slot name -> (look, ASS alignment of the anchor, anchor in the slot box: 'tl' top-left, 'ml' middle-left, 'mc' middle-centre).
_SLOTS: dict[str, dict[str, tuple[_Look, int, str]]] = {
    HERO_STRIP: {
        'title': (_Look(56, INK), 4, 'ml'), 'number': (_Look(84, 'accent'), 4, 'ml'), 'number_caption': (_Look(26, WHITE, bold=False), 7, 'tl'),
    },
    MOSAIC_GRID: {
        'category': (_Look(32, RED), 7, 'tl'), 'title': (_Look(44, WHITE), 7, 'tl'),
        'badge_number': (_Look(110, INK), 5, 'mc'), 'badge_caption': (_Look(30, INK), 5, 'mc'),
    },
    FULL_BLEED_INSET: {
        'category': (_Look(32, 'accent'), 7, 'tl'), 'title': (_Look(58, WHITE, shadow=3), 7, 'tl'),
        'quote': (_Look(40, WHITE, italic=True), 7, 'tl'),
    },
    SPLIT_STACK: {
        'title': (_Look(46, WHITE), 5, 'mc'), 'arrow': (_Look(40, 'accent'), 5, 'mc'),
        'top_label': (_Look(34, INK), 4, 'ml'), 'bottom_label': (_Look(34, INK), 4, 'ml'),
    },
    DATA_CARD: {
        'category': (_Look(32, WHITE), 4, 'ml'), 'title': (_Look(54, WHITE), 7, 'tl'), 'counter': (_Look(28, WHITE), 5, 'mc'),
        'number': (_Look(136, 'accent'), 7, 'tl'), 'explain': (_Look(34, WHITE), 7, 'tl'),
    },
}
_NUMBER_SLOTS = {HERO_STRIP: ('number', 'number_caption'), MOSAIC_GRID: ('badge_number', 'badge_caption'), DATA_CARD: ('number', 'explain')}
_UPPER = {'category', 'top_label', 'bottom_label'}


def plain_text(text: str) -> str:
    """Text safe inside an ASS Dialogue field: braces and backslashes become their full-width forms, line breaks and controls a space."""
    out = []
    for ch in text:
        if ch == '{':
            out.append('｛')
        elif ch == '}':
            out.append('｝')
        elif ch == '\\':
            out.append('＼')
        elif unicodedata.category(ch) in ('Cc', 'Zl', 'Zp'):
            out.append(' ')
        else:
            out.append(ch)
    return ' '.join(''.join(out).split())


def cut_words(text: str, limit: int) -> str:
    """text when it fits in limit characters, else its longest word prefix that fits with an ellipsis (a single long word is cut)."""
    text = ' '.join(text.split())
    if len(text) <= limit:
        return text
    words, kept = text.split(' '), ''
    for word in words:
        trial = f'{kept} {word}' if kept else word
        if len(trial) + 1 > limit:
            break
        kept = trial
    return (kept or text[: limit - 1]).rstrip(' ,;:') + ELLIPSIS


def wrap_lines(text: str, max_chars: int, max_lines: int) -> tuple[str, ...]:
    """Word wrap to at most max_lines lines of max_chars characters; what does not fit ends the last line with an ellipsis."""
    words, lines, current = ' '.join(text.split()).split(' '), [], ''
    for index, word in enumerate(words):
        trial = f'{current} {word}' if current else word
        if len(trial) <= max_chars:
            current = trial
            continue
        if len(lines) + 1 == max_lines:
            return (*lines, cut_words(' '.join([current, *words[index:]]).strip(), max_chars))
        lines.append(current if current else cut_words(word, max_chars))
        current = word if current else ''
    if current:
        lines.append(current)
    return tuple(lines[:max_lines])


def short_title(chosen: object, narration: str) -> str:
    """The plan title when it has 1..TITLE_MAX_CHARS characters, else the first sentence of the narration cut to TITLE_MAX_CHARS."""
    if isinstance(chosen, str) and 0 < len(' '.join(chosen.split())) <= TITLE_MAX_CHARS:
        return ' '.join(chosen.split())
    first = next((m.group(0).strip() for m in _SENTENCE.finditer(narration) if m.group(0).strip()), '')
    return cut_words(first.rstrip('.!?'), TITLE_MAX_CHARS)


def first_number(words: Sequence[object], max_chars: int, caption_chars: int) -> tuple[str, str, int] | None:
    """(number, caption, spoken at ms) of the first narration word that holds a digit, verbatim without edge punctuation; the caption
    is the next words that fit caption_chars. None when there is no such word or it is longer than max_chars."""
    for index, word in enumerate(words):
        text = _EDGE.sub('', getattr(word, 'text', ''))
        if not _NUMBER_WORD.search(text):
            continue
        if len(text) > max_chars:
            return None
        caption = ''
        for follow in words[index + 1:index + 4]:
            token = _EDGE.sub('', getattr(follow, 'text', '')).lower()
            if not token or len(f'{caption} {token}'.strip()) > caption_chars:
                break
            caption = f'{caption} {token}'.strip()
        return text, caption, int(getattr(word, 'start_ms', 0))
    return None


def quote_of(texts: Sequence[str], max_chars: int) -> str | None:
    """A quoted span of the script that fits max_chars, else its shortest sentence that fits, else None."""
    for text in texts:
        found = _QUOTED.search(text)
        if found and len(found.group(1).strip()) <= max_chars:
            return found.group(1).strip()
    sentences = sorted((m.group(0).strip() for text in texts for m in _SENTENCE.finditer(text)), key=len)
    return next((s for s in sentences if 12 <= len(s) <= max_chars), None)


def _ass_colour(hex_rgb: str, alpha: int = 0) -> str:
    h = hex_rgb.lstrip('#').upper()
    return f'&H{alpha:02X}{h[4:6]}{h[2:4]}{h[0:2]}'


def _clock(ms: int) -> str:
    centis = (ms * 2 + 10) // 20
    seconds, centis = divmod(centis, 100)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f'{hours}:{minutes:02d}:{seconds:02d}.{centis:02d}'


def _cut(spans: Sequence[tuple[int, int]], cuts: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    pieces = [span for span in spans if span[0] < span[1]]
    for start, end in cuts:
        kept = []
        for a, b in pieces:
            if end <= a or start >= b:
                kept.append((a, b))
                continue
            if a < start:
                kept.append((a, start))
            if end < b:
                kept.append((end, b))
        pieces = kept
    return pieces


class _Writer:
    def __init__(self, key: str, accent: str, font: str, play_res: tuple[int, int], cuts: Sequence[tuple[int, int]]) -> None:
        self.key, self.accent, self.font, self.cuts = key, accent, font, cuts
        self.sx, self.sy = play_res[0] / DESIGN_WIDTH, play_res[1] / DESIGN_HEIGHT
        self.styles: dict[str, str] = {}
        self.events: list[str] = []

    def style(self, name: str, look: _Look) -> str:
        if name not in self.styles:
            colour = _ass_colour(self.accent if look.colour == 'accent' else look.colour)
            back = LABEL_BOX if look.box else '&H00000000'
            border_style, outline = (3, 8) if look.box else (1, 0)
            values = (
                name, self.font, round(look.size * self.sy), colour, colour, back, back, -1 if look.bold else 0, -1 if look.italic else 0, 0, 0, 100, 100, 0, 0,
                border_style, outline, look.shadow, 7, 0, 0, 0, 1,
            )
            self.styles[name] = 'Style: ' + ','.join(str(v) for v in values)
        return name

    def write(self, style: str, align: int, x: int, y: int, lines: Sequence[str], spans: Sequence[tuple[int, int]], tags: Callable[[int], str] | None = None) -> None:
        body = '\\N'.join(plain_text(line) for line in lines if line)
        if not body:
            return
        for start, end in _cut(spans, self.cuts):
            extra = tags(start) if tags is not None else ''
            self.events.append(
                f'Dialogue: {LAYER},{_clock(start)},{_clock(end)},{style},,0,0,0,,'
                f'{{\\an{align}\\pos({round(x * self.sx)},{round(y * self.sy)})\\q2{extra}}}{body}'
            )

    def slot(self, slots: Mapping[str, object], name: str, text: str | None, spans: Sequence[tuple[int, int]], tags: Callable[[int], str] | None = None) -> str | None:
        if not text or name not in slots:
            return None
        look, align, anchor = _SLOTS[self.key][name]
        box = slots[name].box
        text = text.rstrip('.;,') if name in _UPPER else text
        lines = wrap_lines(text.upper() if name in _UPPER else text, slots[name].max_chars, slots[name].max_lines)
        x = box.x + box.w // 2 if anchor == 'mc' else box.x
        y = box.y if anchor == 'tl' else box.y + box.h // 2
        # Big glyphs in a narrow slot (the badge of MOSAIC_GRID): shrink the line so its estimated width stays inside the slot box.
        fit = min(1.0, box.w / (GLYPH_WIDTH * look.size * max(len(line) for line in lines)))
        shrink = f'\\fs{round(look.size * fit * self.sy)}' if fit < 1 else ''

        def tagged(start: int) -> str:
            return shrink + (tags(start) if tags is not None else '')

        self.write(self.style(f'Layout{name.title().replace("_", "")}', look), align, x, y, lines, spans, tagged)
        return ' / '.join(lines)


def _label_anchor(key: str, cell: object) -> tuple[int, int, int]:
    """(ASS alignment, x, y) of the AI label of a cell: its top-left inner corner, or top-right for SPLIT_STACK and the right column of
    MOSAIC_GRID (their top-left corner holds a label pill or the badge), kept inside the text margins and left of the right rail."""
    box, border = cell.box, cell.border
    y = box.y + border + AI_LABEL_INSET
    if key == SPLIT_STACK or (key == MOSAIC_GRID and box.x > 0):
        right = min(box.right - border - AI_LABEL_INSET, TEXT_RIGHT)
        if RIGHT_RAIL_ROWS[0] < y + AI_LABEL_SIZE * 2 and y < RIGHT_RAIL_ROWS[1]:
            right = min(right, RIGHT_RAIL_LEFT)
        return 9, right, y
    return 7, max(TEXT_LEFT, box.x + border + AI_LABEL_INSET), y


def layout_text_rows(
    key: object,
    *,
    accent: str,
    font: str,
    play_res: tuple[int, int],
    scenes: Sequence[LayoutScene],
    words: Sequence[object],
    end_ms: int,
    title: object = None,
    category: object = None,
    segment_texts: Mapping[str, str] | None = None,
    contrast_pair: Sequence[str] | None = None,
    ai_refs: Collection[str] = (),
    cuts: Sequence[tuple[int, int]] = (),
) -> LayoutRows | None:
    """The ASS rows of the layout text, or None when the video is not drawn with the layout (unknown key, no scene, fewer distinct
    images than MIN_IMAGES: the render keeps the single-image scene then). Cells are filled exactly as the render fills them
    (slot_sources over the distinct refs in first-use order); scene windows are the timeline ones, the last one runs to end_ms."""
    try:
        geometry = layout_geometry(key)
    except LayoutRejected:
        return None
    images = list(dict.fromkeys(ref for scene in scenes for ref in scene.refs))
    if not scenes or len(images) < MIN_IMAGES[geometry.key]:
        return None
    texts = list((segment_texts or {}).values())
    narration = ' '.join(getattr(word, 'text', '') for word in words)
    writer = _Writer(geometry.key, accent, font, play_res, cuts)
    slots = {slot.name: slot for slot in geometry.texts}
    last = max(scene.end_ms for scene in scenes)
    whole = [(0, max(end_ms, last))]
    values: dict[str, object] = {'layout_key': geometry.key}
    values['title'] = writer.slot(slots, 'title', short_title(title, narration), whole)
    values['category'] = writer.slot(slots, 'category', cut_words(category, slots['category'].max_chars) if isinstance(category, str) and 'category' in slots else None, whole)
    if geometry.key in _NUMBER_SLOTS:
        number_slot, caption_slot = _NUMBER_SLOTS[geometry.key]
        found = first_number(words, slots[number_slot].max_chars, slots[caption_slot].max_chars)
        if found is not None:
            number, caption, spoken = found
            def pop(start: int, spoken: int = spoken) -> str:
                """Scale pulse when the number is spoken (times of \\t count from the start of the Dialogue row)."""
                at = max(0, spoken - start)
                return f'\\t({at},{at + NUMBER_POP_MS // 2},\\fscx118\\fscy118)\\t({at + NUMBER_POP_MS // 2},{at + NUMBER_POP_MS},\\fscx100\\fscy100)'

            values['number'] = writer.slot(slots, number_slot, number, whole, pop)
            values['number_caption'] = writer.slot(slots, caption_slot, caption, whole)
    if geometry.key == FULL_BLEED_INSET:
        quote = quote_of(texts, slots['quote'].max_chars * slots['quote'].max_lines - 2)
        values['quote'] = writer.slot(slots, 'quote', f'“{quote}”' if quote else None, whole)
    if geometry.key == SPLIT_STACK:
        writer.slot(slots, 'arrow', ARROW, whole)
        pair = list(contrast_pair or ())
        if len(pair) == 2 and segment_texts:
            values['top_label'] = writer.slot(slots, 'top_label', segment_texts.get(pair[0]), whole)
            values['bottom_label'] = writer.slot(slots, 'bottom_label', segment_texts.get(pair[1]), whole)
    labels = 0
    ai = {ref.lower() for ref in ai_refs}
    label_style = writer.style('LayoutAiLabel', _Look(AI_LABEL_SIZE, WHITE, box=True))
    for index, scene in enumerate(scenes):
        span = [(scene.start_ms, max(end_ms, scene.end_ms) if scene.end_ms == last else scene.end_ms)]
        cells, _ = slot_sources(geometry.key, images, index)
        if geometry.key == DATA_CARD:
            writer.slot(slots, 'counter', f'{images.index(cells[0]) + 1} / {len(images)}', span)
        for cell, ref in zip(geometry.cells, cells):
            if ref.lower() not in ai:
                continue
            if geometry.key == FULL_BLEED_INSET and cell.name == 'background':
                slot = slots['ai_label'].box
                align, x, y = 9, slot.right, slot.y
            else:
                align, x, y = _label_anchor(geometry.key, cell)
            before = len(writer.events)
            writer.write(label_style, align, x, y, [AI_LABEL_TEXT], span)
            labels += len(writer.events) > before
    values['ai_labels'] = labels
    return LayoutRows(styles=tuple(writer.styles.values()), events=tuple(writer.events), values=values)


__all__ = [
    'AI_LABEL_TEXT', 'LayoutRows', 'LayoutScene', 'TITLE_MAX_CHARS', 'cut_words', 'first_number', 'layout_text_rows', 'plain_text',
    'quote_of', 'short_title', 'wrap_lines',
]
