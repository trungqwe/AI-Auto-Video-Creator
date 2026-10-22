"""JSON payload mapping between E records and the JSONB payload column; pure, no I/O."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from voice.domain.voice_track import VoiceTrack
from voice.domain.word_timing import WordTimingRecord, validate_word_timing


def voice_to_payload(record: VoiceTrack) -> dict[str, Any]:
    return record.to_payload()


def voice_from_payload(payload: Mapping[str, Any]) -> VoiceTrack:
    return VoiceTrack.from_payload(payload)


def timing_to_payload(record: WordTimingRecord) -> dict[str, Any]:
    return {
        'script_version_id': record.script_version_id,
        'script_fingerprint': record.script_fingerprint,
        'voice_hash': record.voice_hash,
        'timing_artifact_ref': record.timing_artifact_ref,
        'words': [
            {'start_ms': word.start_ms, 'end_ms': word.end_ms, 'text': word.text, 'normalized_text': word.normalized_text, 'confidence': word.confidence}
            for word in record.words
        ],
        'segment_boundaries': [{'start_ms': item.start_ms, 'end_ms': item.end_ms} for item in record.segment_boundaries],
        'validation_report_ref': record.validation_report_ref,
        'voice_duration_ms': record.voice_duration_ms,
        'alignment_gaps': copy.deepcopy(list(record.alignment_gaps)),
    }


def timing_from_payload(payload: Mapping[str, Any]) -> WordTimingRecord:
    return validate_word_timing(dict(payload))
