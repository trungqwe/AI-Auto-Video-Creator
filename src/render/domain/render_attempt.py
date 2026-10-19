"""F-11: RenderAttempt, operation receipt and OUTCOME_UNKNOWN reconcile (CT-RND-004, CT-STATE-011).

RenderAttempt is a frozen record of one render try. receipt_state is the shared controlplane OperationState and every state
change goes through transition_operation, so this module owns no state machine. A transition returns a new attempt with
revision + 1 and never mutates the old one; each attempt has its own output_artifact_ref and a new attempt never overwrites an
older output. Times, metrics, errors and probe results are inputs. Error and warning text is redacted (declared secret values,
secret assignments, bearer tokens, absolute paths) before it is stored. A technically successful render is not a finished
video: the attempt has no field or function that marks a video as done; that verdict belongs to the quality gates and storage.
OUTCOME_UNKNOWN is never retried directly: reconcile_attempt decides from a ProbeEvidence first.
Pure domain: no I/O, no clock.

coveredIds: CT-RND-004, CT-STATE-011, TST-SEC-INV-012
"""
from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from types import MappingProxyType

from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.statemachine import (
    ForbiddenTransitionError,
    OperationState,
    ReconciliationEvidence,
    TransitionResult,
    transition_operation,
)
from render.domain.render_command import KIND_RENDER, RenderCommandSpec

INVALID_INPUT = 'INVALID_INPUT'
OUTPUT_ARTIFACT_REUSED = 'output_artifact_ref_reused'
REASON_OUTPUT_MISSING = 'reconcile_output_missing'
REASON_OUTPUT_CORRUPT = 'reconcile_output_corrupt'
REDACTED = '[REDACTED]'
PATH_TOKEN = '[PATH]'
MAX_TEXT = 500
MAX_SAFE_INTEGER = 2**53 - 1


class RenderAttemptRejected(ValueError):
    """An input broke CT-RND-004: `code` is the stable error code and `reason` names the offending field."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(f'{code}: {reason}')
        self.code = code
        self.reason = reason


_ASSIGNMENT = re.compile(r'(?i)(?<![A-Za-z0-9_])(password|passwd|secret|access[_-]?token|refresh[_-]?token|token|api[_-]?key|credential|authorization)(\s*[:=]\s*)([^\s,;]+)')
_BEARER = re.compile(r'(?i)(?<![A-Za-z0-9_])Bearer\s+[^\s,;]+')
_PRIVATE_KEY = re.compile(r'-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----', re.DOTALL)
_ABS_PATH = re.compile(r'(?<![\w.])[A-Za-z]:[\\/][^\s,;]*|\\\\[^\s,;]+|(?<![\w.])/(?:[^\s/,;]+/)*[^\s/,;]+')
_IDENTIFIER_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}')
_REF_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}')
_DRIVE_RE = re.compile(r'[A-Za-z]:')
_SHA256_RE = re.compile(r'[0-9A-Fa-f]{64}')
_METRIC_KEY_RE = re.compile(r'[a-z][a-z0-9_]{0,63}')


def _reject(reason: str) -> RenderAttemptRejected:
    return RenderAttemptRejected(INVALID_INPUT, reason)


def _identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER_RE.fullmatch(value) is None:
        raise _reject(f'invalid_{name}')
    return value


def _output_ref(value: object) -> str:
    if not isinstance(value, str) or _REF_RE.fullmatch(value) is None or '..' in value or '//' in value or _DRIVE_RE.match(value):
        raise _reject('invalid_output_artifact_ref')
    return value


def _moment(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise _reject(f'invalid_{name}')
    return value


def _count(value: object, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_SAFE_INTEGER:
        raise _reject(f'invalid_{name}')
    return value


def _metrics(value: object, name: str) -> Mapping[str, int | float]:
    if value is None:
        return MappingProxyType({})
    if not isinstance(value, Mapping):
        raise _reject(f'invalid_{name}')
    items = {}
    for key, number in value.items():
        numeric = isinstance(number, (int, float)) and not isinstance(number, bool) and math.isfinite(number) and number >= 0
        if not (isinstance(key, str) and _METRIC_KEY_RE.fullmatch(key)) or not numeric:
            raise _reject(f'invalid_{name}')
        items[key] = number
    return MappingProxyType(dict(sorted(items.items())))


def _texts(values: object, name: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise _reject(f'invalid_{name}')
    items = tuple(values)
    if not all(isinstance(item, str) for item in items):
        raise _reject(f'invalid_{name}')
    return items


def _secrets(values: object) -> tuple[str, ...]:
    return tuple(sorted({item for item in _texts(values, 'secret_values') if item}, key=len, reverse=True))


def _redact(text: str, secrets: tuple[str, ...] = (), limit: int | None = MAX_TEXT) -> str:
    for secret in secrets:
        text = text.replace(secret, REDACTED)
    text = _PRIVATE_KEY.sub('[REDACTED PRIVATE KEY]', text)
    text = _BEARER.sub('Bearer ' + REDACTED, text)
    text = _ASSIGNMENT.sub(lambda match: match.group(1) + match.group(2) + REDACTED, text)
    text = _ABS_PATH.sub(PATH_TOKEN, text)
    return text if limit is None else text[:limit]


def _error(value: object, secrets: tuple[str, ...]) -> str:
    if not isinstance(value, str):
        raise _reject('invalid_error')
    text = _redact(value, secrets).strip()
    if not text:
        raise _reject('invalid_error')
    return text


def _warnings(values: object, secrets: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(_redact(item, secrets) for item in _texts(values, 'warnings'))


@dataclass(frozen=True, kw_only=True)
class ProbeEvidence:
    """What a probe saw of the attempt output; None means not observed. expected_sha256 comes from the verified source, sha256 from the probed file."""

    output_artifact_ref: str | None = None
    exists: bool | None = None
    sha256: str | None = None
    expected_sha256: str | None = None
    playable: bool | None = None
    evidence_ref: str | None = None
    observed_at: datetime | None = None


def _no_metrics() -> Mapping[str, int | float]:
    return MappingProxyType({})


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


@dataclass(frozen=True, kw_only=True)
class RenderAttempt:
    """Frozen CT-RND-004 record: command_spec is redacted JSON, receipt_state is the OperationState, error is redacted text."""

    render_attempt_id: str
    package_fingerprint: str
    output_artifact_ref: str
    tool_name: str
    tool_version: str
    build_version: str
    command_spec: str
    receipt_state: OperationState
    receipt_ref: str
    revision: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    wall_time_ms: int | None = None
    cpu_metrics: Mapping[str, int | float] = field(default_factory=_no_metrics)
    gpu_metrics: Mapping[str, int | float] = field(default_factory=_no_metrics)
    peak_disk_bytes: int | None = None
    warnings: tuple[str, ...] = ()
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            'render_attempt_id': self.render_attempt_id,
            'package_fingerprint': self.package_fingerprint,
            'output_artifact_ref': self.output_artifact_ref,
            'tool_name': self.tool_name,
            'tool_version': self.tool_version,
            'build_version': self.build_version,
            'command_spec': json.loads(self.command_spec),
            'receipt_state': self.receipt_state.value,
            'receipt_ref': self.receipt_ref,
            'revision': self.revision,
            'started_at': _iso(self.started_at),
            'finished_at': _iso(self.finished_at),
            'wall_time_ms': self.wall_time_ms,
            'cpu_metrics': dict(self.cpu_metrics),
            'gpu_metrics': dict(self.gpu_metrics),
            'peak_disk_bytes': self.peak_disk_bytes,
            'warnings': list(self.warnings),
            'error': self.error,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)


def _scrub_json(value: object) -> object:
    if isinstance(value, str):
        return _redact(value, limit=None)
    if isinstance(value, Mapping):
        return {key: _scrub_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_scrub_json(item) for item in value]
    return value


def _command_spec_json(command_spec: object) -> str:
    if not isinstance(command_spec, RenderCommandSpec) or command_spec.kind != KIND_RENDER:
        raise _reject('invalid_command_spec')
    return json.dumps(_scrub_json(command_spec.to_dict()), sort_keys=True, ensure_ascii=False)


def _tool_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _reject(f'invalid_{name}')
    return _redact(value, limit=None)


def prepare_attempt(
    *,
    render_attempt_id: str,
    package_fingerprint: str,
    output_artifact_ref: str,
    command_spec: RenderCommandSpec,
    receipt_ref: str,
    previous_output_artifact_refs: Iterable[str] = (),
) -> RenderAttempt:
    """Create the PREPARED attempt (revision 0); output_artifact_ref must differ from every earlier attempt output."""
    attempt_id = _identifier(render_attempt_id, 'render_attempt_id')
    fingerprint = _identifier(package_fingerprint, 'package_fingerprint')
    output_ref = _output_ref(output_artifact_ref)
    spec_json = _command_spec_json(command_spec)
    receipt = _identifier(receipt_ref, 'receipt_ref')
    if output_ref in _texts(previous_output_artifact_refs, 'previous_output_artifact_refs'):
        raise RenderAttemptRejected(OUTPUT_ARTIFACT_REUSED, 'output_artifact_ref')
    identity = command_spec.tool_identity
    return RenderAttempt(
        render_attempt_id=attempt_id,
        package_fingerprint=fingerprint,
        output_artifact_ref=output_ref,
        tool_name=_tool_text(identity.name, 'tool_name'),
        tool_version=_tool_text(identity.version, 'tool_version'),
        build_version=_tool_text(identity.build, 'build_version'),
        command_spec=spec_json,
        receipt_state=OperationState.PREPARED,
        receipt_ref=receipt,
        revision=0,
    )


def _require_attempt(attempt: object) -> None:
    if not isinstance(attempt, RenderAttempt):
        raise _reject('invalid_attempt')


def _advance(attempt: RenderAttempt, expected_revision: int, requested: OperationState, evidence: ReconciliationEvidence | None = None) -> TransitionResult:
    _require_attempt(attempt)
    return transition_operation(
        current_state=attempt.receipt_state,
        current_revision=attempt.revision,
        expected_revision=expected_revision,
        requested_state=requested,
        reconciliation_evidence=evidence,
    )


def start_attempt(attempt: RenderAttempt, *, expected_revision: int, started_at: datetime) -> RenderAttempt:
    """PREPARED -> STARTED; started_at is an input."""
    result = _advance(attempt, expected_revision, OperationState.STARTED)
    return replace(attempt, receipt_state=result.state, revision=result.revision, started_at=_moment(started_at, 'started_at'))


def _finish(
    attempt: RenderAttempt,
    result: TransitionResult,
    *,
    finished_at: datetime | None,
    wall_time_ms: object,
    cpu_metrics: object,
    gpu_metrics: object,
    peak_disk_bytes: object,
    warnings: object,
    error: str | None,
    secrets: tuple[str, ...],
) -> RenderAttempt:
    if finished_at is not None and attempt.started_at is not None and finished_at < attempt.started_at:
        raise _reject('invalid_finished_at')
    return replace(
        attempt,
        receipt_state=result.state,
        revision=result.revision,
        finished_at=finished_at,
        wall_time_ms=_count(wall_time_ms, 'wall_time_ms'),
        cpu_metrics=_metrics(cpu_metrics, 'cpu_metrics'),
        gpu_metrics=_metrics(gpu_metrics, 'gpu_metrics'),
        peak_disk_bytes=_count(peak_disk_bytes, 'peak_disk_bytes'),
        warnings=_warnings(warnings, secrets),
        error=error,
    )


def succeed_attempt(
    attempt: RenderAttempt,
    *,
    expected_revision: int,
    finished_at: datetime,
    wall_time_ms: int | None = None,
    cpu_metrics: Mapping[str, int | float] | None = None,
    gpu_metrics: Mapping[str, int | float] | None = None,
    peak_disk_bytes: int | None = None,
    warnings: Iterable[str] = (),
    secret_values: Iterable[str] = (),
) -> RenderAttempt:
    """STARTED -> SUCCEEDED: the render produced an output; this is a technical fact, not a finished video."""
    result = _advance(attempt, expected_revision, OperationState.SUCCEEDED)
    return _finish(
        attempt, result, finished_at=_moment(finished_at, 'finished_at'), wall_time_ms=wall_time_ms, cpu_metrics=cpu_metrics,
        gpu_metrics=gpu_metrics, peak_disk_bytes=peak_disk_bytes, warnings=warnings, error=None, secrets=_secrets(secret_values),
    )


def fail_attempt(
    attempt: RenderAttempt,
    *,
    expected_revision: int,
    finished_at: datetime,
    error: str,
    wall_time_ms: int | None = None,
    cpu_metrics: Mapping[str, int | float] | None = None,
    gpu_metrics: Mapping[str, int | float] | None = None,
    peak_disk_bytes: int | None = None,
    warnings: Iterable[str] = (),
    secret_values: Iterable[str] = (),
) -> RenderAttempt:
    """STARTED -> FAILED; error is redacted before it is stored."""
    result = _advance(attempt, expected_revision, OperationState.FAILED)
    secrets = _secrets(secret_values)
    return _finish(
        attempt, result, finished_at=_moment(finished_at, 'finished_at'), wall_time_ms=wall_time_ms, cpu_metrics=cpu_metrics,
        gpu_metrics=gpu_metrics, peak_disk_bytes=peak_disk_bytes, warnings=warnings, error=_error(error, secrets), secrets=secrets,
    )


def mark_outcome_unknown(
    attempt: RenderAttempt,
    *,
    expected_revision: int,
    reason: str,
    finished_at: datetime | None = None,
    wall_time_ms: int | None = None,
    cpu_metrics: Mapping[str, int | float] | None = None,
    gpu_metrics: Mapping[str, int | float] | None = None,
    peak_disk_bytes: int | None = None,
    warnings: Iterable[str] = (),
    secret_values: Iterable[str] = (),
) -> RenderAttempt:
    """STARTED -> OUTCOME_UNKNOWN (timeout or crash after a possible side effect); the output must be probed before any retry."""
    result = _advance(attempt, expected_revision, OperationState.OUTCOME_UNKNOWN)
    secrets = _secrets(secret_values)
    moment = None if finished_at is None else _moment(finished_at, 'finished_at')
    return _finish(
        attempt, result, finished_at=moment, wall_time_ms=wall_time_ms, cpu_metrics=cpu_metrics, gpu_metrics=gpu_metrics,
        peak_disk_bytes=peak_disk_bytes, warnings=warnings, error=_error(reason, secrets), secrets=secrets,
    )


def _sha(value: object) -> str | None:
    return value.lower() if isinstance(value, str) and _SHA256_RE.fullmatch(value) else None


def _verdict(attempt: RenderAttempt, probe: object) -> tuple[OperationState, str | None] | None:
    """Return (next state, error reason) when the probe is conclusive and None when it is not."""
    if not isinstance(probe, ProbeEvidence) or probe.output_artifact_ref != attempt.output_artifact_ref:
        return None
    if not isinstance(probe.evidence_ref, str) or _IDENTIFIER_RE.fullmatch(probe.evidence_ref) is None:
        return None
    if probe.exists is False:
        return OperationState.FAILED, REASON_OUTPUT_MISSING
    if probe.exists is not True:
        return None
    if probe.playable is False:
        return OperationState.FAILED, REASON_OUTPUT_CORRUPT
    actual, expected = _sha(probe.sha256), _sha(probe.expected_sha256)
    if actual is not None and expected is not None and actual != expected:
        return OperationState.FAILED, REASON_OUTPUT_CORRUPT
    if probe.playable is True and actual is not None and expected is not None:
        return OperationState.SUCCEEDED, None
    return None


def _finished_for(attempt: RenderAttempt, probe: ProbeEvidence) -> datetime | None:
    if attempt.finished_at is not None:
        return attempt.finished_at
    seen = probe.observed_at
    if isinstance(seen, datetime) and seen.utcoffset() is not None and (attempt.started_at is None or seen >= attempt.started_at):
        return seen
    return None


def reconcile_attempt(attempt: RenderAttempt, probe: object, *, expected_revision: int | None = None) -> RenderAttempt:
    """Resolve an OUTCOME_UNKNOWN attempt from a ProbeEvidence: present, playable and matching -> SUCCEEDED; missing or corrupt -> FAILED; otherwise the same attempt (still OUTCOME_UNKNOWN)."""
    _require_attempt(attempt)
    if attempt.receipt_state is not OperationState.OUTCOME_UNKNOWN:
        raise ForbiddenTransitionError(
            aggregate_type='operation',
            current_state=attempt.receipt_state,
            requested_next_state=OperationState.SUCCEEDED,
            current_revision=attempt.revision,
        )
    expected = attempt.revision if expected_revision is None else expected_revision
    if expected != attempt.revision:
        raise RevisionConflictError(attempt.revision)
    verdict = _verdict(attempt, probe)
    if verdict is None:
        return attempt
    state, reason = verdict
    result = _advance(attempt, expected, state, ReconciliationEvidence(reference=probe.evidence_ref))
    return replace(attempt, receipt_state=result.state, revision=result.revision, finished_at=_finished_for(attempt, probe), error=reason)


def can_retry_directly(attempt: RenderAttempt) -> bool:
    """Only a FAILED attempt may be retried, and only as a new attempt with a new output; OUTCOME_UNKNOWN never, until reconciled."""
    _require_attempt(attempt)
    return attempt.receipt_state is OperationState.FAILED


__all__ = [
    'INVALID_INPUT',
    'OUTPUT_ARTIFACT_REUSED',
    'ProbeEvidence',
    'RenderAttempt',
    'RenderAttemptRejected',
    'can_retry_directly',
    'fail_attempt',
    'mark_outcome_unknown',
    'prepare_attempt',
    'reconcile_attempt',
    'start_attempt',
    'succeed_attempt',
]
