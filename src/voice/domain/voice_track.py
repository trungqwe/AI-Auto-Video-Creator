"""VoiceTrack value, binding validators and script/duration guards (CT-TTS-001).

Constants mirror BINDING-D-E-F-VOICE-TIMING entities VoiceTrackRequest and VoiceTrackResult; unknown additive fields are ignored.
Pure domain: no I/O, no clock. The script fingerprint is computed by D and compared as given; E never recomputes it.
The voice duration range is a policy input; the module has no default range and no hidden default for it.
"""
from __future__ import annotations

import copy
import hashlib
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from voice.ports.script_text import ScriptText

MISSING_REQUIRED = 'missing_required'
WRONG_TYPE = 'wrong_type'
INPUT_NOT_READY = 'INPUT_NOT_READY'
SCRIPT_FINGERPRINT_MISMATCH = 'script_fingerprint_mismatch'
SCRIPT_VERSION_MISMATCH = 'script_version_mismatch'
VOICE_DURATION_OUT_OF_RANGE = 'voice_duration_out_of_range'
RETENTION_PER_VIDEO = 'per_video'
BINDING_VERSION = '1.0.0'

VOICE_TRACK_REQUEST_REQUIRED = MappingProxyType({
    'script_version_id': 'string',
    'script_fingerprint': 'sha256',
    'voice_profile_ref': 'string',
    'provider_route_ref': 'string',
    'expected_language': 'string',
    'operation_key': 'string',
    'execution_grant_ref': 'string',
})
VOICE_TRACK_REQUEST_OPTIONAL = MappingProxyType({
    'pronunciation_hints': 'array',
    'style_parameters': 'object',
})
VOICE_TRACK_RESULT_REQUIRED = MappingProxyType({
    'voice_artifact_ref': 'string',
    'script_version_id': 'string',
    'script_fingerprint': 'sha256',
    'voice_hash': 'sha256',
    'actual_duration_ms': 'integer',
    'provider_model_voice_revision': 'string',
    'usage_metrics': 'object',
    'warnings': 'array',
    'receipt_ref': 'string',
})
VOICE_TRACK_RESULT_OPTIONAL = MappingProxyType({})

_SHA256_RE = re.compile(r'[0-9a-f]{64}')


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    field: str


class VoiceTrackValidationError(ValueError):
    """A VoiceTrackRequest or VoiceTrackResult broke the binding; `issues` lists every (code, field)."""

    def __init__(self, issues: Iterable[ValidationIssue]) -> None:
        self.issues = tuple(issues)
        super().__init__(', '.join(f'{issue.code}:{issue.field}' for issue in self.issues))


class ScriptBindingError(Exception):
    """The request is not bound to the exact script text D returned; `code` is script_fingerprint_mismatch or script_version_mismatch."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class VoiceTrackRejected(Exception):
    """A policy input is missing: `code` is INPUT_NOT_READY, `reason` is the stable machine reason."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(f'{code}: {reason}')
        self.code = code
        self.reason = reason


def matches_type(value: object, type_name: str) -> bool:
    if type_name == 'string':
        return isinstance(value, str)
    if type_name == 'integer':
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == 'object':
        return isinstance(value, Mapping)
    if type_name == 'array':
        return isinstance(value, (list, tuple))
    if type_name == 'sha256':
        return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None
    return False


def _validate(payload: object, required: Mapping[str, str], optional: Mapping[str, str]) -> list[ValidationIssue]:
    if not isinstance(payload, Mapping):
        return [ValidationIssue(WRONG_TYPE, '$')]
    issues: list[ValidationIssue] = []
    for name, type_name in (*required.items(), *optional.items()):
        if name not in payload:
            if name in required:
                issues.append(ValidationIssue(MISSING_REQUIRED, name))
            continue
        value = payload[name]
        if value is None:
            if name in required:
                issues.append(ValidationIssue(WRONG_TYPE, name))
            continue
        if not matches_type(value, type_name):
            issues.append(ValidationIssue(WRONG_TYPE, name))
    return issues


def validate_voice_track_request(payload: object) -> list[ValidationIssue]:
    """Return boundary issues of a VoiceTrackRequest payload (CT-TTS-001); empty list means valid."""
    return _validate(payload, VOICE_TRACK_REQUEST_REQUIRED, VOICE_TRACK_REQUEST_OPTIONAL)


def validate_voice_track_result(payload: object) -> list[ValidationIssue]:
    """Return boundary issues of a VoiceTrackResult payload (CT-TTS-001); empty list means valid."""
    return _validate(payload, VOICE_TRACK_RESULT_REQUIRED, VOICE_TRACK_RESULT_OPTIONAL)


@dataclass(frozen=True, kw_only=True)
class VoiceTrack:
    """CT-TTS-001 VoiceTrackResult as an immutable value; voice is per-video data, so retention_class is always per_video (cleanup stays with I)."""

    voice_artifact_ref: str
    script_version_id: str
    script_fingerprint: str
    voice_hash: str
    actual_duration_ms: int
    provider_model_voice_revision: str
    usage_metrics: Mapping[str, object]
    warnings: tuple[object, ...]
    receipt_ref: str
    retention_class: str = RETENTION_PER_VIDEO

    def __post_init__(self) -> None:
        if self.retention_class != RETENTION_PER_VIDEO:
            raise ValueError(f'retention_class must be {RETENTION_PER_VIDEO!r}')
        issues = validate_voice_track_result({name: getattr(self, name) for name in VOICE_TRACK_RESULT_REQUIRED})
        if issues:
            raise VoiceTrackValidationError(issues)
        object.__setattr__(self, 'usage_metrics', MappingProxyType(copy.deepcopy(dict(self.usage_metrics))))
        object.__setattr__(self, 'warnings', tuple(copy.deepcopy(list(self.warnings))))

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> VoiceTrack:
        """Build from a binding payload; raises VoiceTrackValidationError, unknown fields are ignored."""
        issues = validate_voice_track_result(payload)
        if issues:
            raise VoiceTrackValidationError(issues)
        return cls(**{name: payload[name] for name in VOICE_TRACK_RESULT_REQUIRED})

    def to_payload(self) -> dict[str, object]:
        """Return the binding VoiceTrackResult payload (plain dict/list copies, no retention_class)."""
        payload: dict[str, object] = {name: getattr(self, name) for name in VOICE_TRACK_RESULT_REQUIRED}
        payload['usage_metrics'] = copy.deepcopy(dict(self.usage_metrics))
        payload['warnings'] = copy.deepcopy(list(self.warnings))
        return payload


@dataclass(frozen=True)
class DurationFinding:
    code: str
    actual_duration_ms: int
    min_duration_ms: int
    max_duration_ms: int


def verify_script_binding(request: Mapping[str, object], script_text: ScriptText) -> None:
    """Raise ScriptBindingError unless the request is bound to this exact script text.

    The request fingerprint is compared as given with the fingerprint D returned; E never recomputes it.
    Raises VoiceTrackValidationError when the request itself breaks the binding.
    """
    issues = validate_voice_track_request(request)
    if issues:
        raise VoiceTrackValidationError(issues)
    if script_text.script_version_id != request['script_version_id']:
        raise ScriptBindingError(SCRIPT_VERSION_MISMATCH)
    if script_text.script_fingerprint != request['script_fingerprint']:
        raise ScriptBindingError(SCRIPT_FINGERPRINT_MISMATCH)


def compute_voice_hash(audio_bytes: bytes | bytearray | memoryview) -> str:
    """Return the lowercase hex SHA-256 of the voice audio bytes."""
    if not isinstance(audio_bytes, (bytes, bytearray, memoryview)):
        raise TypeError('audio_bytes must be bytes-like')
    return hashlib.sha256(audio_bytes).hexdigest()


def check_duration(actual_duration_ms: int, policy_range: tuple[int, int] | list[int] | None) -> DurationFinding | None:
    """Compare the voice duration with the policy range (inclusive bounds); the range is policy input only.

    Raises VoiceTrackRejected(INPUT_NOT_READY, 'missing_duration_policy') when the policy or a bound is None,
    ValueError for a non-integer duration or malformed range. Returns None inside the range, otherwise a
    DurationFinding with code voice_duration_out_of_range.
    """
    if policy_range is None or (isinstance(policy_range, (tuple, list)) and len(policy_range) == 2 and None in policy_range):
        raise VoiceTrackRejected(INPUT_NOT_READY, 'missing_duration_policy')
    if not matches_type(actual_duration_ms, 'integer'):
        raise ValueError('actual_duration_ms must be an integer, not bool or text')
    if (
        not isinstance(policy_range, (tuple, list))
        or len(policy_range) != 2
        or not all(matches_type(bound, 'integer') for bound in policy_range)
        or policy_range[0] > policy_range[1]
    ):
        raise ValueError('policy_range must be (min_ms, max_ms) of integers with min_ms <= max_ms')
    low, high = policy_range
    if low <= actual_duration_ms <= high:
        return None
    return DurationFinding(VOICE_DURATION_OUT_OF_RANGE, actual_duration_ms, low, high)
