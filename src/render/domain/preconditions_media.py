"""F-06: CT-RND-003 hard preconditions 1-4 and 6 (hook, thumbnail, voice, timing, timeline).

Pure domain: no I/O, no clock. All functions return complete findings in a
fixed order without raising on malformed data. Shapes of hook_placement and
timeline.segments are F-local assumptions (CONV-F-07).

coveredIds: CT-RND-003 (1-4, 6), TST-MEDIA-INV-007 (phía F)
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

CONDITION_VISUAL_HOOK = 1
CONDITION_AUDIO_HOOK = 2
CONDITION_THUMBNAIL = 3
CONDITION_VOICE_TIMING = 4
CONDITION_TIMELINE = 6

VISUAL_HOOK_MISSING = 'visual_hook_missing'
AUDIO_HOOK_MISSING = 'audio_hook_missing'
THUMBNAIL_MISSING = 'thumbnail_missing'
THUMBNAIL_OUTSIDE_HOOK_RANGE = 'thumbnail_outside_hook_range'
TIME_RANGE_INVALID = 'time_range_invalid'
VOICE_MISSING = 'voice_missing'
WORD_TIMING_MISSING = 'word_timing_missing'
VOICE_TIMING_BINDING_MISMATCH = 'voice_timing_binding_mismatch'
TIMELINE_SEGMENT_WITHOUT_VISUAL = 'timeline_segment_without_visual'
TIMELINE_SEGMENTS_INVALID = 'timeline_segments_invalid'


@dataclass(frozen=True)
class Finding:
    condition: int
    code: str
    field: str


@dataclass(frozen=True)
class VoiceTrackInfo:
    """DTO representing the subset of VoiceTrackResult fields from binding d-e-f-voice-timing."""

    voice_artifact_ref: str
    script_version_id: str
    script_fingerprint: str
    voice_hash: str


@dataclass(frozen=True)
class WordTimingInfo:
    """DTO representing the subset of WordTiming fields from binding d-e-f-voice-timing."""

    timing_artifact_ref: str
    script_version_id: str
    script_fingerprint: str
    voice_hash: str


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _bounds_valid(start: object, end: object) -> bool:
    return _is_int(start) and _is_int(end) and start >= 0 and start < end


def _range_bounds(value: object) -> tuple[int, int] | None:
    if not isinstance(value, Mapping):
        return None
    start, end = value.get('start_ms'), value.get('end_ms')
    return (start, end) if _bounds_valid(start, end) else None


def check_hook_preconditions(record: object) -> tuple[Finding, ...]:
    """Check hard preconditions for hook placement and thumbnail range."""
    placement = getattr(record, 'hook_placement', None)
    if not isinstance(placement, Mapping):
        placement = {}
    findings: list[Finding] = []
    if _text(placement.get('visual_hook_ref')) is None:
        findings.append(Finding(CONDITION_VISUAL_HOOK, VISUAL_HOOK_MISSING, 'hook_placement.visual_hook_ref'))
    if _text(placement.get('audio_hook_ref')) is None:
        findings.append(Finding(CONDITION_AUDIO_HOOK, AUDIO_HOOK_MISSING, 'hook_placement.audio_hook_ref'))
    has_thumbnail = _text(placement.get('thumbnail_ref')) is not None
    if not has_thumbnail:
        findings.append(Finding(CONDITION_THUMBNAIL, THUMBNAIL_MISSING, 'hook_placement.thumbnail_ref'))
    hook = _range_bounds(placement.get('hook_time_range'))
    thumb = _range_bounds(placement.get('thumbnail_time_range')) if has_thumbnail else None
    if hook is not None and thumb is not None and not (hook[0] <= thumb[0] and thumb[1] <= hook[1]):
        findings.append(Finding(CONDITION_THUMBNAIL, THUMBNAIL_OUTSIDE_HOOK_RANGE, 'hook_placement.thumbnail_time_range'))
    if hook is None:
        findings.append(Finding(CONDITION_THUMBNAIL, TIME_RANGE_INVALID, 'hook_placement.hook_time_range'))
    if has_thumbnail and thumb is None:
        findings.append(Finding(CONDITION_THUMBNAIL, TIME_RANGE_INVALID, 'hook_placement.thumbnail_time_range'))
    return tuple(findings)


def check_voice_timing_binding(record: object, voice_info: object, timing_info: object) -> tuple[Finding, ...]:
    """Check voice and word timing binding invariants against render package.

    RenderPackageRecord does not carry script_fingerprint or voice_hash, so
    the package is cross-checked via voice_artifact_ref, word_timing_ref, and
    script_version_ref. The fingerprint and hash are verified directly between
    voice and timing artifacts. Non-DTO inputs or missing package references
    are treated as missing artifacts.
    """
    package_voice = _text(getattr(record, 'voice_artifact_ref', None))
    package_timing = _text(getattr(record, 'word_timing_ref', None))
    voice = voice_info if package_voice is not None and isinstance(voice_info, VoiceTrackInfo) else None
    timing = timing_info if package_timing is not None and isinstance(timing_info, WordTimingInfo) else None
    findings: list[Finding] = []

    if voice is None:
        findings.append(Finding(CONDITION_VOICE_TIMING, VOICE_MISSING, 'voice_artifact_ref'))
    if timing is None:
        findings.append(Finding(CONDITION_VOICE_TIMING, WORD_TIMING_MISSING, 'word_timing_ref'))

    if voice is not None and _text(voice.voice_artifact_ref) != package_voice:
        findings.append(Finding(CONDITION_VOICE_TIMING, VOICE_TIMING_BINDING_MISMATCH, 'voice_artifact_ref'))
    if timing is not None and _text(timing.timing_artifact_ref) != package_timing:
        findings.append(Finding(CONDITION_VOICE_TIMING, VOICE_TIMING_BINDING_MISMATCH, 'word_timing_ref'))

    if voice is not None or timing is not None:
        versions = {_text(getattr(record, 'script_version_ref', None))}
        if voice is not None:
            versions.add(_text(voice.script_version_id))
        if timing is not None:
            versions.add(_text(timing.script_version_id))
        if len(versions) > 1 or None in versions:
            findings.append(Finding(CONDITION_VOICE_TIMING, VOICE_TIMING_BINDING_MISMATCH, 'script_version_id'))

    if voice is not None and timing is not None:
        for name in ('script_fingerprint', 'voice_hash'):
            left = _text(getattr(voice, name))
            right = _text(getattr(timing, name))
            if left is None or left != right:
                findings.append(Finding(CONDITION_VOICE_TIMING, VOICE_TIMING_BINDING_MISMATCH, name))

    return tuple(findings)


def check_timeline_coverage(timeline: object) -> tuple[Finding, ...]:
    """Check timeline segment coverage and time ranges.

    The shape of segments is an F-local assumption (CONV-F-07).
    """
    segments = timeline.get('segments') if isinstance(timeline, Mapping) else None
    if isinstance(segments, (str, bytes)) or not isinstance(segments, Sequence):
        return (Finding(CONDITION_TIMELINE, TIMELINE_SEGMENTS_INVALID, 'timeline.segments'),)

    findings: list[Finding] = []
    for index, segment in enumerate(segments):
        item = segment if isinstance(segment, Mapping) else {}
        base = f'timeline.segments[{index}]'
        refs = item.get('visual_asset_refs')
        has_visual = isinstance(refs, Sequence) and not isinstance(refs, (str, bytes)) and any(_text(ref) is not None for ref in refs)
        if not has_visual:
            findings.append(Finding(CONDITION_TIMELINE, TIMELINE_SEGMENT_WITHOUT_VISUAL, f'{base}.visual_asset_refs'))
        if not _bounds_valid(item.get('start_ms'), item.get('end_ms')):
            findings.append(Finding(CONDITION_TIMELINE, TIME_RANGE_INVALID, base))

    return tuple(findings)
