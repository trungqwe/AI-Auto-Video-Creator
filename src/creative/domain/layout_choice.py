"""PRS-LAYOUT-PLAN: which of the five presentation layouts a video uses, chosen by the AI inside the production plan (FR-PRS-002..005).

The eligible set is computed before the model call from the selection and the script (layout_features, eligible_layouts) and narrowed
by the batch share cap (capped_layouts, at most BATCH_SHARE_MAX of the batch per layout). The model names one key of the offered
set with a short reason (and a contrast_pair for SPLIT_STACK, an optional short title); choose_layout validates it and falls back
deterministically, recording why, instead of failing the plan. The keys mirror render.domain.layout.LAYOUT_KEYS (D does not import
F; a cross-check test keeps them equal). Pure domain: no I/O, no clock.
coveredIds: FR-PRS-002, FR-PRS-003, FR-PRS-004, FR-PRS-005
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

HERO_STRIP = 'HERO_STRIP'
MOSAIC_GRID = 'MOSAIC_GRID'
FULL_BLEED_INSET = 'FULL_BLEED_INSET'
SPLIT_STACK = 'SPLIT_STACK'
DATA_CARD = 'DATA_CARD'
LAYOUT_KEYS = (HERO_STRIP, MOSAIC_GRID, FULL_BLEED_INSET, SPLIT_STACK, DATA_CARD)
DEFAULT_LAYOUT = HERO_STRIP
SINGLE_IMAGE_LAYOUT = FULL_BLEED_INSET
BATCH_SHARE_MAX = 0.4
TITLE_MAX_CHARS = 48
REASON_MAX_CHARS = 200
ORIGIN_SEED = 'seed'
ORIGIN_AI = 'ai_generated'
LAYOUT_DESCRIPTIONS = {
    HERO_STRIP: 'one large picture with a strip of three smaller pictures under it; the default for ordinary news with two to six pictures',
    MOSAIC_GRID: 'a 2x2 grid of four story pictures of equal weight; for scenes, consequences or several places',
    FULL_BLEED_INSET: 'one tall picture fills the screen with one story picture framed on top; for one or two pictures, emotion or a quote',
    SPLIT_STACK: 'two pictures stacked top and bottom with a band between them; for a contrast such as cause and effect or before and after',
    DATA_CARD: 'a picture card with one large number under it; for a story led by a figure such as a temperature, an amount or a percentage',
}
FALLBACK_MISSING = 'layout_missing'
FALLBACK_INVALID = 'layout_invalid'
FALLBACK_UNKNOWN = 'layout_unknown'
FALLBACK_NOT_ELIGIBLE = 'layout_not_eligible'
FALLBACK_CONTRAST = 'contrast_pair_invalid'

_NUMBER_RE = re.compile(r'\d|\b(?:hundred|thousand|million|billion|trillion|percent|per cent)\b', re.IGNORECASE)


@dataclass(frozen=True)
class LayoutFeatures:
    story_images: int
    ai_images: int
    has_number: bool

    @property
    def images(self) -> int:
        return self.story_images + self.ai_images


@dataclass(frozen=True)
class LayoutChoice:
    layout_key: str
    preset_key: str
    reason: str
    fallback_reason: str | None = None
    contrast_pair: tuple[str, str] | None = None
    title: str | None = None

    def to_payload(self) -> dict[str, object]:
        return {
            'layout_key': self.layout_key, 'preset_key': self.preset_key, 'reason': self.reason, 'fallback_reason': self.fallback_reason,
            'contrast_pair': None if self.contrast_pair is None else list(self.contrast_pair), 'title': self.title,
        }


def layout_features(selection: object, script: object) -> LayoutFeatures:
    """Distinct story pictures (origin other than seed and ai_generated), distinct AI pictures and whether the narration holds a number."""
    story: set[str] = set()
    ai: set[str] = set()
    for item in getattr(selection, 'assignments', ()):
        origin = getattr(item, 'origin', None)
        if origin == ORIGIN_SEED:
            continue
        (ai if origin == ORIGIN_AI else story).add(item.media_asset_id)
    text = ' '.join(getattr(segment, 'text', '') for segment in getattr(script, 'segments', ()))
    return LayoutFeatures(story_images=len(story), ai_images=len(ai), has_number=_NUMBER_RE.search(text) is not None)


def eligible_layouts(features: LayoutFeatures) -> tuple[str, ...]:
    """LAYOUTS.md 4.2: HERO_STRIP with two pictures of which one story picture; MOSAIC_GRID with three story pictures; FULL_BLEED_INSET
    with an AI picture (tall) or a single picture; SPLIT_STACK with two pictures (the model must also name a contrast pair); DATA_CARD
    when the narration holds a number. Always non-empty: HERO_STRIP when nothing else applies."""
    rules = {
        HERO_STRIP: features.images >= 2 and features.story_images >= 1,
        MOSAIC_GRID: features.story_images >= 3,
        FULL_BLEED_INSET: features.ai_images >= 1 or features.images <= 1,
        SPLIT_STACK: features.images >= 2,
        DATA_CARD: features.has_number and features.images >= 1,
    }
    found = tuple(key for key in LAYOUT_KEYS if rules[key])
    return found or (DEFAULT_LAYOUT,)


def capped_layouts(options: Sequence[str], used: Mapping[str, int], batch_size: int) -> tuple[str, ...]:
    """options without the layouts that already hold their share of the batch (floor(BATCH_SHARE_MAX * batch_size), at least 1);
    when every option is full the least used one stays (first in LAYOUT_KEYS order on a tie), so a plan is never left without a layout."""
    options = tuple(key for key in LAYOUT_KEYS if key in options)
    if not options:
        return (DEFAULT_LAYOUT,)
    limit = max(1, math.floor(BATCH_SHARE_MAX * batch_size)) if batch_size > 0 else None
    if limit is None:
        return options
    kept = tuple(key for key in options if used.get(key, 0) < limit)
    return kept or (min(options, key=lambda key: (used.get(key, 0), LAYOUT_KEYS.index(key))),)


def _fallback(options: Sequence[str]) -> str:
    for key in (DEFAULT_LAYOUT, SINGLE_IMAGE_LAYOUT, *LAYOUT_KEYS):
        if key in options:
            return key
    return DEFAULT_LAYOUT


def _short_text(value: object, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = ' '.join(value.split())
    return text if text and len(text) <= limit else None


def choose_layout(raw: object, *, options: Sequence[str], presets: Mapping[str, str], segment_ids: Sequence[str]) -> LayoutChoice:
    """The layout of the plan: the model's key when it is one of the five keys, inside options and (SPLIT_STACK) names two distinct
    segment_ids of the script as contrast_pair; otherwise the fallback (HERO_STRIP, else FULL_BLEED_INSET, else the first option) with
    fallback_reason. preset_key is presets[layout_key]; title is kept only when it is 1..TITLE_MAX_CHARS characters."""
    reason, title, pair, fallback = '', None, None, None
    key = None
    if raw is None:
        fallback = FALLBACK_MISSING
    elif not isinstance(raw, Mapping) or not isinstance(raw.get('key'), str):
        fallback = FALLBACK_INVALID
    else:
        key = raw['key']
        reason = _short_text(raw.get('reason'), REASON_MAX_CHARS) or ''
        title = _short_text(raw.get('title'), TITLE_MAX_CHARS)
        if key not in LAYOUT_KEYS:
            fallback = FALLBACK_UNKNOWN
        elif key not in options:
            fallback = FALLBACK_NOT_ELIGIBLE
        elif key == SPLIT_STACK:
            given = raw.get('contrast_pair')
            ok = isinstance(given, (list, tuple)) and len(given) == 2 and given[0] != given[1] and all(isinstance(s, str) and s in segment_ids for s in given)
            if ok:
                pair = (given[0], given[1])
            else:
                fallback = FALLBACK_CONTRAST
    if fallback is not None:
        key = _fallback(options)
        pair = None
    return LayoutChoice(layout_key=key, preset_key=presets[key], reason=reason, fallback_reason=fallback, contrast_pair=pair, title=title)


def valid_presets(presets: object) -> bool:
    """True when presets maps each of the five LAYOUT_KEYS, and nothing else, to a non-empty preset key."""
    return isinstance(presets, Mapping) and set(presets) == set(LAYOUT_KEYS) and all(isinstance(v, str) and v.strip() for v in presets.values())


def layout_prompt_data(options: Sequence[str]) -> list[dict[str, str]]:
    """The offered layouts as the plan prompt data lists them: key and description, in LAYOUT_KEYS order."""
    return [{'key': key, 'description': LAYOUT_DESCRIPTIONS[key]} for key in LAYOUT_KEYS if key in options]
