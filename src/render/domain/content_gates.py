"""F-14: content gates of the rendered output (CT-QC-001, CT-QC-002, TST-QC-INV-019).

Pure domain logic evaluating seven content gates: VISUAL_HOOK_PRESENT, AUDIO_HOOK_PRESENT,
THUMBNAIL_PRESENT, SUBTITLE_BURNED_IN, KARAOKE_TIMING_VALID, ENGLISH_OUTPUT_VALID,
and INFERENCE_DISCLOSURE_PRESENT. Thresholds are provided via QualityPolicy.thresholds
(min_similarity, min_level_db, min_frames_with_text, tolerance_ms, required_language).
Missing thresholds or inputs yield not_evaluated with INPUT_NOT_READY. Pure domain,
no I/O, no clock.

coveredIds: CT-QC-001, CT-QC-002, TST-QC-INV-019
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from render.domain.quality_report import GateName, GateResult, GateStatus, QualityPolicy
from render.ports.output_inspector import (
    AudioHookEvidence,
    DisclosureEvidence,
    DisclosureObservation,
    KaraokeEvidence,
    KaraokeWordObservation,
    LanguageEvidence,
    OutputEvidence,
    OutputInspectorPort,
    SubtitleEvidence,
    ThumbnailEvidence,
    VisualHookEvidence,
)

INPUT_NOT_READY = 'INPUT_NOT_READY'
EVIDENCE_INVALID = 'evidence_invalid'
REASON_NOT_APPLICABLE = 'not_applicable'
VISUAL_HOOK_NOT_OBSERVED = 'visual_hook_not_observed'
VISUAL_HOOK_OUTSIDE_RANGE = 'visual_hook_outside_hook_range'
VISUAL_HOOK_SIMILARITY_LOW = 'visual_hook_similarity_below_threshold'
AUDIO_HOOK_NOT_OBSERVED = 'audio_hook_not_observed'
AUDIO_HOOK_OUTSIDE_RANGE = 'audio_hook_outside_hook_range'
AUDIO_HOOK_LEVEL_LOW = 'audio_hook_level_below_threshold'
THUMBNAIL_NOT_OBSERVED = 'thumbnail_not_observed'
THUMBNAIL_OUTSIDE_HOOK_RANGE = 'thumbnail_outside_hook_range'
THUMBNAIL_ASSET_MISMATCH = 'thumbnail_asset_mismatch'
SUBTITLE_NOT_OBSERVED = 'subtitle_not_observed'
SUBTITLE_FRAMES_BELOW_THRESHOLD = 'subtitle_frames_below_threshold'
KARAOKE_OBSERVATION_MISSING = 'karaoke_observation_missing'
KARAOKE_OBSERVATION_INVALID = 'karaoke_observation_invalid'
KARAOKE_WORD_NOT_OBSERVED = 'karaoke_word_not_observed'
KARAOKE_OUT_OF_TOLERANCE = 'karaoke_timing_out_of_tolerance'
LANGUAGE_EVIDENCE_MISSING = 'language_evidence_missing'
LANGUAGE_EVIDENCE_REVISION_MISMATCH = 'language_evidence_revision_mismatch'
LANGUAGE_MISMATCH = 'language_mismatch'
DISCLOSURE_NOT_OBSERVED = 'disclosure_not_observed'
DISCLOSURE_MISSING = 'disclosure_missing'
INFERENCE_CLAIM_MODES = frozenset({'inference', 'creative_hypothesis'})


@dataclass(frozen=True, kw_only=True)
class ExpectedLanguageRevisions:
    script_fingerprint: str
    voice_hash: str
    subtitle_text_hash: str


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    return (_is_int(value) or isinstance(value, float)) and math.isfinite(value)


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _revision(policy: object) -> str | None:
    return policy.revision if isinstance(policy, QualityPolicy) else None


def _not_ready(gate: GateName, field: str) -> GateResult:
    return GateResult(gate=gate, status=GateStatus.NOT_EVALUATED, reason=f'{INPUT_NOT_READY}:{field}')


def _failed(gate: GateName, reason: str, **fields: object) -> GateResult:
    return GateResult(gate=gate, status=GateStatus.FAILED, reason=reason, **fields)


def _threshold(policy: object, gate: GateName, key: str) -> object:
    entry = policy.thresholds.get(gate.value) if isinstance(policy, QualityPolicy) else None
    return entry.get(key) if isinstance(entry, Mapping) else None


def _placement(package: object) -> Mapping:
    value = getattr(package, 'hook_placement', None)
    return value if isinstance(value, Mapping) else {}


def _hook_range(package: object) -> tuple[int, int] | None:
    value = _placement(package).get('hook_time_range')
    if not isinstance(value, Mapping):
        return None
    start, end = value.get('start_ms'), value.get('end_ms')
    return (start, end) if _is_int(start) and _is_int(end) and 0 <= start < end else None


def _interval_ok(start: object, end: object) -> bool:
    return _is_int(start) and _is_int(end) and 0 <= start <= end


def check_visual_hook_present(evidence: object, package: object, policy: object) -> GateResult:
    """Verify visual hook timing is within hook range and meets similarity threshold."""
    gate = GateName.VISUAL_HOOK_PRESENT
    hook = _hook_range(package)
    if hook is None:
        return _not_ready(gate, 'hook_placement.hook_time_range')
    minimum = _threshold(policy, gate, 'min_similarity')
    if not _is_number(minimum):
        return _not_ready(gate, 'min_similarity')
    if not isinstance(evidence, OutputEvidence):
        return _not_ready(gate, 'evidence')
    item = evidence.visual_hook
    if item is None:
        return _failed(gate, VISUAL_HOOK_NOT_OBSERVED)
    if not (isinstance(item, VisualHookEvidence) and _text(item.evidence_ref) and _interval_ok(item.start_ms, item.end_ms) and _is_number(item.similarity)):
        return _failed(gate, EVIDENCE_INVALID)
    fields = {'evidence_ref': item.evidence_ref, 'time_range': (item.start_ms, item.end_ms), 'measured_value': item.similarity, 'threshold_revision': policy.revision}
    if not (hook[0] <= item.start_ms and item.end_ms <= hook[1]):
        return _failed(gate, VISUAL_HOOK_OUTSIDE_RANGE, **fields)
    if item.similarity < minimum:
        return _failed(gate, VISUAL_HOOK_SIMILARITY_LOW, **fields)
    return GateResult(gate=gate, status=GateStatus.PASSED, **fields)


def check_audio_hook_present(evidence: object, package: object, policy: object) -> GateResult:
    """Verify audio hook timing is within hook range and meets level threshold."""
    gate = GateName.AUDIO_HOOK_PRESENT
    hook = _hook_range(package)
    if hook is None:
        return _not_ready(gate, 'hook_placement.hook_time_range')
    minimum = _threshold(policy, gate, 'min_level_db')
    if not _is_number(minimum):
        return _not_ready(gate, 'min_level_db')
    if not isinstance(evidence, OutputEvidence):
        return _not_ready(gate, 'evidence')
    item = evidence.audio_hook
    if item is None:
        return _failed(gate, AUDIO_HOOK_NOT_OBSERVED)
    if not (isinstance(item, AudioHookEvidence) and _text(item.evidence_ref) and _interval_ok(item.start_ms, item.end_ms) and _is_number(item.level_db)):
        return _failed(gate, EVIDENCE_INVALID)
    fields = {'evidence_ref': item.evidence_ref, 'time_range': (item.start_ms, item.end_ms), 'measured_value': item.level_db, 'threshold_revision': policy.revision}
    if not (hook[0] <= item.start_ms and item.end_ms <= hook[1]):
        return _failed(gate, AUDIO_HOOK_OUTSIDE_RANGE, **fields)
    if item.level_db < minimum:
        return _failed(gate, AUDIO_HOOK_LEVEL_LOW, **fields)
    return GateResult(gate=gate, status=GateStatus.PASSED, **fields)


def check_thumbnail_present(evidence: object, package: object, policy: object = None) -> GateResult:
    """Verify thumbnail frame time is within hook range and asset matches."""
    gate = GateName.THUMBNAIL_PRESENT
    hook = _hook_range(package)
    if hook is None:
        return _not_ready(gate, 'hook_placement.hook_time_range')
    expected_ref = _text(_placement(package).get('thumbnail_ref'))
    if expected_ref is None:
        return _not_ready(gate, 'hook_placement.thumbnail_ref')
    if not isinstance(evidence, OutputEvidence):
        return _not_ready(gate, 'evidence')
    item = evidence.thumbnail
    if item is None:
        return _failed(gate, THUMBNAIL_NOT_OBSERVED)
    if not (isinstance(item, ThumbnailEvidence) and _text(item.evidence_ref) and _text(item.asset_ref) and _is_int(item.time_ms) and item.time_ms >= 0):
        return _failed(gate, EVIDENCE_INVALID)
    fields = {'evidence_ref': item.evidence_ref, 'time_range': (item.time_ms, item.time_ms), 'measured_value': item.time_ms, 'threshold_revision': _revision(policy)}
    if not (hook[0] <= item.time_ms <= hook[1]):
        return _failed(gate, THUMBNAIL_OUTSIDE_HOOK_RANGE, **fields)
    if item.asset_ref != expected_ref:
        return _failed(gate, THUMBNAIL_ASSET_MISMATCH, **fields)
    return GateResult(gate=gate, status=GateStatus.PASSED, **fields)


def check_subtitle_burned_in(evidence: object, policy: object) -> GateResult:
    """Verify burned-in subtitles have at least the minimum required frames with text."""
    gate = GateName.SUBTITLE_BURNED_IN
    minimum = _threshold(policy, gate, 'min_frames_with_text')
    if not (_is_int(minimum) and minimum >= 1):
        return _not_ready(gate, 'min_frames_with_text')
    if not isinstance(evidence, OutputEvidence):
        return _not_ready(gate, 'evidence')
    item = evidence.subtitle
    if item is None:
        return _failed(gate, SUBTITLE_NOT_OBSERVED)
    if not (isinstance(item, SubtitleEvidence) and _text(item.evidence_ref) and _is_int(item.frames_with_text) and item.frames_with_text >= 0):
        return _failed(gate, EVIDENCE_INVALID)
    fields = {'evidence_ref': item.evidence_ref, 'measured_value': item.frames_with_text, 'threshold_revision': policy.revision}
    if item.frames_with_text < minimum:
        return _failed(gate, SUBTITLE_FRAMES_BELOW_THRESHOLD, **fields)
    return GateResult(gate=gate, status=GateStatus.PASSED, **fields)


def check_karaoke_timing_valid(evidence: object, word_timings: object, policy: object) -> GateResult:
    """Verify observed karaoke highlight timings deviate from word timings within tolerance."""
    gate = GateName.KARAOKE_TIMING_VALID
    tolerance = _threshold(policy, gate, 'tolerance_ms')
    if not (_is_int(tolerance) and tolerance >= 0):
        return _not_ready(gate, 'tolerance_ms')
    if isinstance(word_timings, (str, bytes)) or not isinstance(word_timings, Sequence) or not word_timings:
        return _not_ready(gate, 'word_timings')
    if not all(isinstance(word, Mapping) and _is_int(word.get('start_ms')) and word['start_ms'] >= 0 for word in word_timings):
        return _not_ready(gate, 'word_timings')
    if not isinstance(evidence, OutputEvidence):
        return _not_ready(gate, 'evidence')
    item = evidence.karaoke
    if not isinstance(item, KaraokeEvidence) or not item.observations:
        return GateResult(gate=gate, status=GateStatus.NOT_EVALUATED, reason=KARAOKE_OBSERVATION_MISSING)
    if _text(item.evidence_ref) is None:
        return _failed(gate, EVIDENCE_INVALID)
    deviations: dict[int, int] = {}
    for mark in item.observations:
        if not (isinstance(mark, KaraokeWordObservation) and _is_int(mark.word_index) and _is_int(mark.highlight_ms) and 0 <= mark.word_index < len(word_timings)) or mark.word_index in deviations:
            return _failed(gate, KARAOKE_OBSERVATION_INVALID, evidence_ref=item.evidence_ref)
        deviations[mark.word_index] = abs(mark.highlight_ms - word_timings[mark.word_index]['start_ms'])
    fields = {'evidence_ref': item.evidence_ref, 'measured_value': max(deviations.values()), 'threshold_revision': policy.revision}
    if len(deviations) < len(word_timings):
        return _failed(gate, KARAOKE_WORD_NOT_OBSERVED, **fields)
    if fields['measured_value'] > tolerance:
        return _failed(gate, KARAOKE_OUT_OF_TOLERANCE, **fields)
    return GateResult(gate=gate, status=GateStatus.PASSED, **fields)


_LOCALE_FIELDS = ('script_locale', 'voice_locale', 'subtitle_locale', 'title_locale', 'hashtag_locale')
_REVISION_FIELDS = ('script_fingerprint', 'voice_hash', 'subtitle_text_hash')


def _normalize_tag(tag: str) -> str:
    return tag.strip().replace('_', '-').casefold()


def _locale_matches(required: str, reported: object) -> bool:
    """Equal tags, or a bare required language (no region) equal to the primary subtag of the reported locale."""
    if not isinstance(reported, str) or not reported.strip():
        return False
    wanted, actual = _normalize_tag(required), _normalize_tag(reported)
    return actual == wanted or ('-' not in wanted and actual.split('-')[0] == wanted)


def check_english_output_valid(evidence: object, package: object, expected: object, policy: object) -> GateResult:
    """Verify output revisions match expectations and all component locales match required language."""
    gate = GateName.ENGLISH_OUTPUT_VALID
    required = _text(_threshold(policy, gate, 'required_language'))
    if required is None:
        return _not_ready(gate, 'required_language')
    package_revision = _text(getattr(package, 'output_metadata_revision', None))
    if package_revision is None:
        return _not_ready(gate, 'output_metadata_revision')
    if not isinstance(expected, ExpectedLanguageRevisions) or any(_text(getattr(expected, name, None)) is None for name in _REVISION_FIELDS):
        return _not_ready(gate, 'expected_language')
    if not isinstance(evidence, OutputEvidence):
        return _not_ready(gate, 'evidence')
    item = evidence.language
    if not isinstance(item, LanguageEvidence) or _text(item.evidence_ref) is None:
        return _failed(gate, LANGUAGE_EVIDENCE_MISSING)
    fields = {'evidence_ref': item.evidence_ref, 'threshold_revision': policy.revision}
    for name in _REVISION_FIELDS:
        if getattr(item, name) != getattr(expected, name):
            return _failed(gate, f'{LANGUAGE_EVIDENCE_REVISION_MISMATCH}:{name}', **fields)
    if item.output_metadata_revision != package_revision:
        return _failed(gate, f'{LANGUAGE_EVIDENCE_REVISION_MISMATCH}:output_metadata_revision', **fields)
    for name in _LOCALE_FIELDS:
        if not _locale_matches(required, getattr(item, name)):
            return _failed(gate, f'{LANGUAGE_MISMATCH}:{name}', **fields)
    return GateResult(gate=gate, status=GateStatus.PASSED, **fields)


def check_inference_disclosure_present(evidence: object, segments: object) -> GateResult:
    """Verify visual disclosure is present for all inference and creative hypothesis segments."""
    gate = GateName.INFERENCE_DISCLOSURE_PRESENT
    if isinstance(segments, (str, bytes)) or not isinstance(segments, Sequence) or not all(isinstance(item, Mapping) for item in segments):
        return _not_ready(gate, 'segments')
    required: list[str] = []
    for item in segments:
        mode = item.get('claim_mode')
        if not isinstance(mode, str):
            return _not_ready(gate, 'segments')
        if mode in INFERENCE_CLAIM_MODES:
            segment_id = _text(item.get('segment_id'))
            if segment_id is None:
                return _not_ready(gate, 'segments')
            required.append(segment_id)
    if not required:
        return GateResult(gate=gate, status=GateStatus.NOT_APPLICABLE, reason=REASON_NOT_APPLICABLE)
    if not isinstance(evidence, OutputEvidence):
        return _not_ready(gate, 'evidence')
    item = evidence.disclosure
    if not isinstance(item, DisclosureEvidence) or _text(item.evidence_ref) is None:
        return _failed(gate, DISCLOSURE_NOT_OBSERVED)
    visible = {mark.segment_id for mark in item.observations if isinstance(mark, DisclosureObservation) and mark.visible is True}
    missing = [segment_id for segment_id in required if segment_id not in visible]
    if missing:
        return _failed(gate, f'{DISCLOSURE_MISSING}:{missing[0]}', evidence_ref=item.evidence_ref, measured_value=len(missing))
    return GateResult(gate=gate, status=GateStatus.PASSED, evidence_ref=item.evidence_ref, measured_value=len(required))


def evaluate_content_gates(
    inspector: OutputInspectorPort,
    output_ref: str,
    package: object,
    policy: object,
    expected_language: object,
    word_timings: object,
    segments: object,
) -> tuple[GateResult, ...]:
    """Call inspector once and return results for all seven content gates in GateName order."""
    evidence = inspector.inspect(output_ref, package)
    return (
        check_visual_hook_present(evidence, package, policy),
        check_audio_hook_present(evidence, package, policy),
        check_thumbnail_present(evidence, package, policy),
        check_subtitle_burned_in(evidence, policy),
        check_karaoke_timing_valid(evidence, word_timings, policy),
        check_english_output_valid(evidence, package, expected_language, policy),
        check_inference_disclosure_present(evidence, segments),
    )
