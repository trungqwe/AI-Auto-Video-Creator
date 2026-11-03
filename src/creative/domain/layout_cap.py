"""PRS-LAYOUT-QUOTA-FIX1: the batch share cap of a layout checked again when the production plan is stored (FR-PRS-005, decision D3
point 4: one layout holds at most 40 percent of the videos of a batch).

capped_layouts narrows the offered layouts with the usage read when the plan activity starts, but the plan is stored after the model
call, about a minute later; plans other jobs of the batch store meanwhile are not in that usage (batch 875e2e7d: HERO_STRIP 41 of
100). recheck_layout takes the usage read under the batch lock in the storing transaction and moves a plan whose layout filled up
meanwhile to an offered layout that still has room. Pure domain: no I/O, no clock.
coveredIds: FR-PRS-005
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from creative.domain.layout_choice import BATCH_SHARE_MAX, DEFAULT_LAYOUT, LAYOUT_KEYS, SINGLE_IMAGE_LAYOUT, LayoutChoice

FALLBACK_BATCH_CAP = 'batch_cap_race'
FALLBACK_BATCH_FULL = 'batch_cap_full'


def batch_share_limit(batch_size: int) -> int | None:
    """Plans one layout may hold in a batch of batch_size videos, as capped_layouts counts it: floor(BATCH_SHARE_MAX * batch_size),
    at least 1; None (no cap) when the batch size is not positive."""
    return max(1, math.floor(BATCH_SHARE_MAX * batch_size)) if batch_size > 0 else None


def _fallback(options: Sequence[str]) -> str:
    """The fallback order of choose_layout: HERO_STRIP, else FULL_BLEED_INSET, else the first option in LAYOUT_KEYS order."""
    for key in (DEFAULT_LAYOUT, SINGLE_IMAGE_LAYOUT, *LAYOUT_KEYS):
        if key in options:
            return key
    return DEFAULT_LAYOUT


def recheck_layout(
    choice: Mapping[str, object], *, options: Sequence[str], used: Mapping[str, int], batch_size: int, presets: Mapping[str, str],
) -> dict[str, object] | None:
    """The layout_choice payload of a plan checked again with used read under the batch lock in the storing transaction. None when
    nothing changes: no cap, an unknown key, or the chosen layout still has room. When the chosen layout is full and an offered layout
    still has room, the payload of the fallback among those layouts with its preset, the model's reason and title, no contrast_pair and
    fallback_reason batch_cap_race. When every offered layout is full the chosen layout stays (a plan never loses its layout) with
    fallback_reason batch_cap_full."""
    key = choice.get('layout_key')
    limit = batch_share_limit(batch_size)
    if limit is None or key not in LAYOUT_KEYS or used.get(key, 0) < limit:
        return None
    reason = choice.get('reason') if isinstance(choice.get('reason'), str) else ''
    title = choice.get('title') if isinstance(choice.get('title'), str) else None
    room = tuple(option for option in LAYOUT_KEYS if option in options and used.get(option, 0) < limit)
    if room:
        moved = _fallback(room)
        return LayoutChoice(
            layout_key=moved, preset_key=presets[moved], reason=reason, fallback_reason=FALLBACK_BATCH_CAP, title=title).to_payload()
    pair = choice.get('contrast_pair')
    kept = (pair[0], pair[1]) if isinstance(pair, Sequence) and not isinstance(pair, str) and len(pair) == 2 else None
    return LayoutChoice(
        layout_key=key, preset_key=presets[key], reason=reason, fallback_reason=FALLBACK_BATCH_FULL, contrast_pair=kept, title=title).to_payload()


__all__ = ['FALLBACK_BATCH_CAP', 'FALLBACK_BATCH_FULL', 'batch_share_limit', 'recheck_layout']
