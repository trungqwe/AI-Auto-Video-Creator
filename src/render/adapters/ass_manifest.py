"""Builds the ASS file of one render from karaoke_plan (build_karaoke_plan, render_ass), adds the Disclosure style and Dialogue rows of inference segments (CT-AI-004, CT-QC-001), writes it under the staging root and returns the materialization_manifest entry (PW-F3)."""
from __future__ import annotations

import hashlib
import pathlib
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from render.adapters.postgres_plan_assets import ScriptSegmentInfo
from render.adapters.real_output_inspector import DISCLOSURE_STYLE
from render.domain.content_gates import INFERENCE_CLAIM_MODES
from render.domain.karaoke_plan import ConsumerWordTiming, TimedWord, build_karaoke_plan, render_ass
from render.ports.inputs import LocalMaterialRef

DISCLOSURE_MISSING = 'DISCLOSURE_MISSING'
WORD_COUNT_MISMATCH = 'WORD_COUNT_MISMATCH'
SEGMENT_INVALID = 'SEGMENT_INVALID'
DISCLOSURE_STYLE_INVALID = 'DISCLOSURE_STYLE_INVALID'
STAGING_ROOT_INVALID = 'STAGING_ROOT_INVALID'
MANIFEST_CONFLICT = 'MANIFEST_CONFLICT'


class AssManifestRejected(ValueError):
    """Raised when an ASS materialization or manifest invariant is violated."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(f'{code}: {reason}')
        self.code = code
        self.reason = reason


@dataclass(frozen=True, kw_only=True)
class AssMaterial:
    ass_ref: str
    entry: LocalMaterialRef
    local_path: str
    sha256: str
    text: str


def disclosure_windows(
    segments: Sequence[ScriptSegmentInfo], words: Sequence[TimedWord]
) -> tuple[tuple[str, int, int, str], ...]:
    if not isinstance(segments, Sequence) or len(segments) == 0:
        raise AssManifestRejected(SEGMENT_INVALID, 'segments')
    for s in segments:
        if not isinstance(s, ScriptSegmentInfo):
            raise AssManifestRejected(SEGMENT_INVALID, 'segment')
        for ch in s.segment_id:
            if ch == ',' or ord(ch) < 32 or ord(ch) == 127:
                raise AssManifestRejected(SEGMENT_INVALID, s.segment_id)
        if s.claim_mode in INFERENCE_CLAIM_MODES:
            if not isinstance(s.disclosure, str) or not s.disclosure.strip():
                raise AssManifestRejected(DISCLOSURE_MISSING, s.segment_id)
            if s.word_count < 1:
                raise AssManifestRejected(SEGMENT_INVALID, s.segment_id)
    orders = [s.order for s in segments]
    if len(orders) != len(set(orders)):
        raise AssManifestRejected(SEGMENT_INVALID, 'duplicate_orders')

    sorted_segments = sorted(segments, key=lambda s: s.order)
    total_words = sum(s.word_count for s in sorted_segments)
    if total_words != len(words):
        raise AssManifestRejected(
            WORD_COUNT_MISMATCH, f'{total_words}!={len(words)}'
        )

    windows: list[tuple[str, int, int, str]] = []
    cursor = 0
    for s in sorted_segments:
        if s.claim_mode in INFERENCE_CLAIM_MODES:
            start_ms = words[cursor].start_ms
            end_ms = words[cursor + s.word_count - 1].end_ms
            windows.append((s.segment_id, start_ms, end_ms, s.disclosure.strip()))
        cursor += s.word_count
    return tuple(windows)


def _clock(ms: int) -> str:
    centis = (ms * 2 + 10) // 20
    seconds, centis = divmod(centis, 100)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f'{hours}:{minutes:02d}:{seconds:02d}.{centis:02d}'


def _field_text(text: str) -> str:
    cleaned: list[str] = []
    for ch in text:
        if ch == '{':
            cleaned.append('\uff5b')
        elif ch == '}':
            cleaned.append('\uff5d')
        elif ch == '\\':
            cleaned.append('\uff3c')
        elif unicodedata.category(ch) in ('Cc', 'Zl', 'Zp'):
            cleaned.append(' ')
        else:
            cleaned.append(ch)
    return ''.join(cleaned)


def _disclosure_style_row(plan: Any, style: object) -> tuple[str, int]:
    if not isinstance(style, Mapping):
        raise AssManifestRejected(DISCLOSURE_STYLE_INVALID, 'style')
    font_size = style.get('font_size')
    if not isinstance(font_size, int) or isinstance(font_size, bool) or font_size <= 0:
        raise AssManifestRejected(DISCLOSURE_STYLE_INVALID, 'font_size')
    alignment = style.get('alignment')
    if not isinstance(alignment, int) or isinstance(alignment, bool) or not (1 <= alignment <= 9):
        raise AssManifestRejected(DISCLOSURE_STYLE_INVALID, 'alignment')
    margin_v = style.get('margin_v')
    if not isinstance(margin_v, int) or isinstance(margin_v, bool) or not (0 <= margin_v < plan.play_res_y):
        raise AssManifestRejected(DISCLOSURE_STYLE_INVALID, 'margin_v')
    if (alignment, margin_v) == (plan.style.alignment, plan.margin_vertical):
        raise AssManifestRejected(DISCLOSURE_STYLE_INVALID, 'overlaps_karaoke')
    s = plan.style
    row = 'Style: ' + ','.join(
        str(v)
        for v in (
            DISCLOSURE_STYLE,
            s.font_name,
            font_size,
            s.primary_colour,
            s.secondary_colour,
            s.outline_colour,
            s.back_colour,
            s.bold,
            s.italic,
            s.underline,
            s.strike_out,
            s.scale_x,
            s.scale_y,
            s.spacing,
            s.angle,
            s.border_style,
            s.outline,
            s.shadow,
            alignment,
            plan.margin_left,
            plan.margin_right,
            margin_v,
            s.encoding,
        )
    )
    return row, margin_v


def build_ass_text(
    words: ConsumerWordTiming | Sequence[TimedWord],
    typography: Mapping,
    safe_area: Mapping,
    profile: Mapping,
    disclosure_style: Mapping,
    segments: Sequence[ScriptSegmentInfo],
) -> str:
    words_seq = words.words if isinstance(words, ConsumerWordTiming) else words
    words_tuple = tuple(words_seq)
    plan = build_karaoke_plan(words_tuple, typography, safe_area, profile)
    base = render_ass(plan)
    windows = disclosure_windows(segments, words_tuple)
    style_row, margin_v = _disclosure_style_row(plan, disclosure_style)

    rows = base.rstrip('\n').split('\n')
    if windows:
        last_style_idx = max(i for i, r in enumerate(rows) if r.startswith('Style: '))
        rows.insert(last_style_idx + 1, style_row)
        for segment_id, start_ms, end_ms, disclosure in windows:
            start_str = _clock(start_ms)
            end_str = _clock(end_ms)
            dialogue_row = (
                f'Dialogue: 0,{start_str},{end_str},{DISCLOSURE_STYLE},{segment_id},'
                f'{plan.margin_left},{plan.margin_right},{margin_v},,{_field_text(disclosure)}'
            )
            rows.append(dialogue_row)
    return '\n'.join(rows) + '\n'


def build_ass_material(
    *,
    staging_root: str,
    words: ConsumerWordTiming | Sequence[TimedWord],
    typography: Mapping,
    safe_area: Mapping,
    profile: Mapping,
    disclosure_style: Mapping,
    segments: Sequence[ScriptSegmentInfo],
) -> AssMaterial:
    if not isinstance(staging_root, str) or not staging_root:
        raise AssManifestRejected(STAGING_ROOT_INVALID, 'staging_root')
    root_path = pathlib.Path(staging_root)
    if not root_path.is_absolute():
        raise AssManifestRejected(STAGING_ROOT_INVALID, 'staging_root')

    text = build_ass_text(
        words=words,
        typography=typography,
        safe_area=safe_area,
        profile=profile,
        disclosure_style=disclosure_style,
        segments=segments,
    )
    data = text.encode('utf-8')
    digest = hashlib.sha256(data).hexdigest()
    local_ref = f'{digest}.ass'
    ass_ref = f'ass-{digest}'
    root_path.mkdir(parents=True, exist_ok=True)
    target = root_path / local_ref
    if not (target.is_file() and target.read_bytes() == data):
        target.write_bytes(data)

    return AssMaterial(
        ass_ref=ass_ref,
        entry=LocalMaterialRef(artifact_version_id=ass_ref, local_ref=local_ref),
        local_path=str(target),
        sha256=digest,
        text=text,
    )


def with_ass_entry(
    manifest: Sequence[LocalMaterialRef], material: AssMaterial
) -> tuple[LocalMaterialRef, ...]:
    items = tuple(manifest)
    for existing in items:
        if existing.artifact_version_id == material.ass_ref:
            if existing.local_ref == material.entry.local_ref:
                return items
            raise AssManifestRejected(MANIFEST_CONFLICT, material.ass_ref)
    return (*items, material.entry)


__all__ = (
    'AssManifestRejected',
    'AssMaterial',
    'DISCLOSURE_MISSING',
    'DISCLOSURE_STYLE_INVALID',
    'MANIFEST_CONFLICT',
    'SEGMENT_INVALID',
    'STAGING_ROOT_INVALID',
    'WORD_COUNT_MISMATCH',
    'build_ass_material',
    'build_ass_text',
    'disclosure_windows',
    'with_ass_entry',
)
