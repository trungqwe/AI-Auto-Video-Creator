"""LanguageEvidence: language evidence bound to the exact script, voice and timing revision (CT-RND-002).

E records the locale the provider reported, the subtitle text hash and the revisions; it never declares the output valid for a language, F decides that from this evidence.
Pure domain: no I/O, no clock, no default language.
"""
from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from controlplane.application.idempotency.canonicalization import request_hash
from voice.domain.voice_track import (
    INPUT_NOT_READY,
    VoiceTrack,
    VoiceTrackValidationError,
    validate_voice_track_request,
)
from voice.domain.word_timing import WordTimingRecord, validate_word_timing

REVISION_MISMATCH = 'revision_mismatch'
LANGUAGE_MISMATCH = 'language_mismatch'
MISSING_LOCALE_REPORT = 'missing_locale_report'
INVALID_LOCALE_REPORT = 'invalid_locale_report'
MISSING_EXPECTED_LANGUAGE = 'missing_expected_language'
MISSING_WORD_TEXT = 'missing_word_text'
LOCALE_REPORT_FIELD = 'voice_locale_reported'


class RevisionMismatchError(Exception):
    """script_version_id, script_fingerprint or voice_hash differ between request, voice track and timing; `fields` lists the names."""

    def __init__(self, fields: Iterable[str]) -> None:
        self.fields = tuple(fields)
        self.code = REVISION_MISMATCH
        super().__init__(f'{REVISION_MISMATCH}: ' + ', '.join(self.fields))


class LanguageEvidenceRejected(Exception):
    """An input needed for the evidence is missing: `code` is INPUT_NOT_READY, `reason` is the stable machine reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(f'{INPUT_NOT_READY}: {reason}')
        self.code = INPUT_NOT_READY
        self.reason = reason


@dataclass(frozen=True)
class LanguageFinding:
    """A finding recorded next to the evidence (code language_mismatch); E records it and never drops it."""

    code: str
    expected_language: str
    voice_locale_reported: str


@dataclass(frozen=True, kw_only=True)
class LanguageEvidence:
    """Frozen evidence for F (CT-RND-002 language_validation_refs); evidence_ref is request_hash of the seven bound fields."""

    script_version_id: str
    script_fingerprint: str
    voice_hash: str
    voice_locale_reported: str
    subtitle_text_hash: str
    timing_artifact_ref: str
    expected_language: str
    evidence_ref: str
    findings: tuple[LanguageFinding, ...] = ()


def _normalize_tag(tag: str) -> str:
    return tag.strip().replace('_', '-').casefold()


def _locale_matches(expected: str, reported: str) -> bool:
    """Equal tags, or a bare expected language (no region) equal to the primary subtag of the reported locale."""
    wanted, actual = _normalize_tag(expected), _normalize_tag(reported)
    return actual == wanted or ('-' not in wanted and actual.split('-')[0] == wanted)


def _reported_locale(locale_report: object) -> str:
    if locale_report is None:
        raise LanguageEvidenceRejected(MISSING_LOCALE_REPORT)
    if not isinstance(locale_report, Mapping):
        raise LanguageEvidenceRejected(INVALID_LOCALE_REPORT)
    locale = locale_report.get(LOCALE_REPORT_FIELD)
    if locale is None:
        raise LanguageEvidenceRejected(MISSING_LOCALE_REPORT)
    if not isinstance(locale, str):
        raise LanguageEvidenceRejected(INVALID_LOCALE_REPORT)
    if not locale.strip():
        raise LanguageEvidenceRejected(MISSING_LOCALE_REPORT)
    return locale


def _as_voice_track(value: object) -> VoiceTrack:
    return value if isinstance(value, VoiceTrack) else VoiceTrack.from_payload(value)


def _as_timing(value: object) -> WordTimingRecord:
    return value if isinstance(value, WordTimingRecord) else validate_word_timing(value)


def _revision_mismatches(request: Mapping[str, object], voice_track: VoiceTrack, timing: WordTimingRecord) -> tuple[str, ...]:
    mismatched = [
        name
        for name in ('script_version_id', 'script_fingerprint')
        if not request[name] == getattr(voice_track, name) == getattr(timing, name)
    ]
    if voice_track.voice_hash != timing.voice_hash:
        mismatched.append('voice_hash')
    return tuple(mismatched)


def _subtitle_text_hash(timing: WordTimingRecord) -> str:
    texts = [word.text for word in timing.words]
    if not texts or any(text is None or not text.strip() for text in texts):
        raise LanguageEvidenceRejected(MISSING_WORD_TEXT)
    return hashlib.sha256(' '.join(texts).encode('utf-8')).hexdigest()


def build_language_evidence(request, voice_track, locale_report, timing) -> LanguageEvidence:
    """Build the evidence for the exact revision shared by request, voice track and timing (CT-RND-002).

    request is a VoiceTrackRequest mapping, voice_track a VoiceTrack (or VoiceTrackResult mapping), timing a WordTimingRecord (or WordTiming mapping),
    locale_report a mapping with voice_locale_reported, set by the adapter from the provider output.
    Raises VoiceTrackValidationError or WordTimingError when an input breaks its binding, RevisionMismatchError when script_version_id,
    script_fingerprint or voice_hash differ, LanguageEvidenceRejected (INPUT_NOT_READY) when locale_report, expected_language or word text is missing.
    A locale different from expected_language still builds the evidence, with a language_mismatch finding.
    """
    issues = validate_voice_track_request(request)
    if issues:
        raise VoiceTrackValidationError(issues)
    track = _as_voice_track(voice_track)
    word_timing = _as_timing(timing)
    mismatched = _revision_mismatches(request, track, word_timing)
    if mismatched:
        raise RevisionMismatchError(mismatched)
    expected = request['expected_language']
    if not expected.strip():
        raise LanguageEvidenceRejected(MISSING_EXPECTED_LANGUAGE)
    reported = _reported_locale(locale_report)
    bound = {
        'script_version_id': track.script_version_id,
        'script_fingerprint': track.script_fingerprint,
        'voice_hash': track.voice_hash,
        'voice_locale_reported': reported,
        'subtitle_text_hash': _subtitle_text_hash(word_timing),
        'timing_artifact_ref': word_timing.timing_artifact_ref,
        'expected_language': expected,
    }
    findings = () if _locale_matches(expected, reported) else (LanguageFinding(LANGUAGE_MISMATCH, expected, reported),)
    return LanguageEvidence(**bound, evidence_ref=request_hash(bound), findings=findings)
