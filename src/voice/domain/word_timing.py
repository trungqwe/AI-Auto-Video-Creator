"""E-09: WordTiming boundary validator (CT-SUB-001 bất biến 1).

Constants mirror BINDING-D-E-F-VOICE-TIMING entity WordTiming; unknown additive fields are ignored.

coveredIds: CT-SUB-001 bất biến 1
"""
from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

MISSING_REQUIRED = 'missing_required'
WRONG_TYPE = 'wrong_type'
CONSTRAINT_VIOLATION = 'constraint_violation'
BINDING_VERSION = '1.0.0'

WORD_TIMING_REQUIRED = MappingProxyType({
    'script_version_id': 'string',
    'script_fingerprint': 'sha256',
    'voice_hash': 'sha256',
    'timing_artifact_ref': 'string',
    'words': 'array',
    'segment_boundaries': 'array',
    'validation_report_ref': 'string',
})
WORD_TIMING_OPTIONAL = MappingProxyType({'voice_duration_ms': 'integer', 'alignment_gaps': 'array'})
WORD_TIMING_ITEMS = MappingProxyType({'words': 'object'})
WORD_TIMING_CONSTRAINTS = ('monotonic_word_timings',)
WORD_REQUIRED = MappingProxyType({'start_ms': 'integer', 'end_ms': 'integer'})
WORD_OPTIONAL = MappingProxyType({'text': 'string', 'normalized_text': 'string', 'confidence': 'number'})
BOUNDARY_REQUIRED = MappingProxyType({'start_ms': 'integer', 'end_ms': 'integer'})


@dataclass(frozen=True)
class WordTimingIssue:
    code: str
    field: str


class WordTimingError(ValueError):
    def __init__(self, issues: tuple[WordTimingIssue, ...]) -> None:
        self.issues = tuple(issues)
        self.code = self.issues[0].code
        self.field = self.issues[0].field
        super().__init__(', '.join(f'{issue.code}:{issue.field}' for issue in self.issues))


@dataclass(frozen=True)
class WordTimingWord:
    start_ms: int
    end_ms: int
    text: str | None
    normalized_text: str | None
    confidence: int | float | None


@dataclass(frozen=True)
class SegmentBoundary:
    start_ms: int
    end_ms: int


@dataclass(frozen=True)
class WordTimingRecord:
    script_version_id: str
    script_fingerprint: str
    voice_hash: str
    timing_artifact_ref: str
    words: tuple[WordTimingWord, ...]
    segment_boundaries: tuple[SegmentBoundary, ...]
    validation_report_ref: str
    voice_duration_ms: int | None
    alignment_gaps: tuple


_SHA256_RE = re.compile(r'[0-9a-f]{64}')


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


_TYPE_CHECKS = {
    'string': lambda value: isinstance(value, str),
    'integer': _is_int,
    'number': _is_number,
    'object': lambda value: isinstance(value, Mapping),
    'array': lambda value: isinstance(value, list),
    'sha256': lambda value: isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None,
}


def _field_issues(payload: Mapping, required: Mapping, optional: Mapping, field: str | None = None) -> list[WordTimingIssue]:
    issues: list[WordTimingIssue] = []
    for name, type_name in (*required.items(), *optional.items()):
        target = field or name
        if name not in payload:
            if name in required:
                issues.append(WordTimingIssue(MISSING_REQUIRED, target))
        elif payload[name] is None:
            if name in required:
                issues.append(WordTimingIssue(WRONG_TYPE, target))
        elif not _TYPE_CHECKS[type_name](payload[name]):
            issues.append(WordTimingIssue(WRONG_TYPE, target))
    return issues


def _in_range(start: int, end: int, duration: int | None) -> bool:
    return 0 <= start < end and (duration is None or end <= duration)


def _word_issues(words: list, duration: int | None) -> list[WordTimingIssue]:
    violation = WordTimingIssue(CONSTRAINT_VIOLATION, 'words')
    if not words:
        return [violation]
    issues: list[WordTimingIssue] = []
    previous_end = None
    for word in words:
        issues.extend(_field_issues(word, WORD_REQUIRED, WORD_OPTIONAL, 'words'))
        confidence = word.get('confidence')
        if _is_number(confidence) and not 0 <= confidence <= 1:
            issues.append(violation)
        start, end = word.get('start_ms'), word.get('end_ms')
        if not (_is_int(start) and _is_int(end)):
            continue
        if not _in_range(start, end, duration) or (previous_end is not None and start < previous_end):
            issues.append(violation)
        if start < end:
            previous_end = end
    return issues


def _boundary_issues(boundaries: list, duration: int | None) -> list[WordTimingIssue]:
    issues: list[WordTimingIssue] = []
    previous_end = None
    for boundary in boundaries:
        if not isinstance(boundary, Mapping):
            issues.append(WordTimingIssue(WRONG_TYPE, 'segment_boundaries'))
            continue
        issues.extend(_field_issues(boundary, BOUNDARY_REQUIRED, {}, 'segment_boundaries'))
        start, end = boundary.get('start_ms'), boundary.get('end_ms')
        if not (_is_int(start) and _is_int(end)):
            continue
        if not _in_range(start, end, duration) or (previous_end is not None and start < previous_end):
            issues.append(WordTimingIssue(CONSTRAINT_VIOLATION, 'segment_boundaries'))
        if start < end:
            previous_end = end
    return issues


def word_timing_issues(payload: object) -> tuple[WordTimingIssue, ...]:
    """Return boundary issues of a WordTiming payload (CT-SUB-001); empty tuple means valid."""
    if not isinstance(payload, Mapping):
        return (WordTimingIssue(WRONG_TYPE, '$'),)
    issues = _field_issues(payload, WORD_TIMING_REQUIRED, WORD_TIMING_OPTIONAL)
    failed = {issue.field for issue in issues}
    for name, item_type in WORD_TIMING_ITEMS.items():
        if name not in failed and any(not _TYPE_CHECKS[item_type](item) for item in payload[name]):
            issues.append(WordTimingIssue(WRONG_TYPE, name))
            failed.add(name)
    duration = payload.get('voice_duration_ms')
    if 'voice_duration_ms' in failed or duration is None:
        duration = None
    elif duration <= 0:
        issues.append(WordTimingIssue(CONSTRAINT_VIOLATION, 'voice_duration_ms'))
        duration = None
    if 'words' not in failed:
        issues.extend(_word_issues(payload['words'], duration))
    if 'segment_boundaries' not in failed:
        issues.extend(_boundary_issues(payload['segment_boundaries'], duration))
    return tuple(dict.fromkeys(issues))


def _build_record(payload: Mapping) -> WordTimingRecord:
    return WordTimingRecord(
        script_version_id=payload['script_version_id'],
        script_fingerprint=payload['script_fingerprint'],
        voice_hash=payload['voice_hash'],
        timing_artifact_ref=payload['timing_artifact_ref'],
        words=tuple(
            WordTimingWord(
                start_ms=word['start_ms'],
                end_ms=word['end_ms'],
                text=word.get('text'),
                normalized_text=word.get('normalized_text'),
                confidence=word.get('confidence'),
            )
            for word in payload['words']
        ),
        segment_boundaries=tuple(
            SegmentBoundary(item['start_ms'], item['end_ms']) for item in payload['segment_boundaries']
        ),
        validation_report_ref=payload['validation_report_ref'],
        voice_duration_ms=payload.get('voice_duration_ms'),
        alignment_gaps=tuple(copy.deepcopy(payload.get('alignment_gaps') or [])),
    )


def validate_word_timing(payload: object) -> WordTimingRecord:
    """Return the frozen WordTimingRecord of a valid payload; raise WordTimingError with every issue otherwise."""
    issues = word_timing_issues(payload)
    if issues:
        raise WordTimingError(issues)
    return _build_record(payload)
