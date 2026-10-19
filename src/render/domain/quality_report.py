"""F-12: QualityReport, gate groups and the pass verdict (CT-QC-001, CT-QC-002).

Gate names, kinds and statuses mirror the CT-QC-001 table. Thresholds are caller input carried by QualityPolicy;
this module holds none. A report always lists all thirteen gates in GateName order and `passed` is derived from the
gate results alone: every hard gate passed and every applicable hard_conditional gate passed; warnings never count.
report_id is request_hash of the report content.
Pure domain: no I/O, no clock.

coveredIds: CT-QC-001, CT-QC-002
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from controlplane.application.idempotency.canonicalization import request_hash

MISSING_REQUIRED = 'missing_required'
WRONG_TYPE = 'wrong_type'
INVALID_VALUE = 'invalid_value'
UNKNOWN_GATE = 'unknown_gate'
DUPLICATE_GATE = 'duplicate_gate'
INPUT_NOT_READY = 'INPUT_NOT_READY'
REASON_MISSING_RESULT = 'missing_result'
REASON_NOT_APPLICABLE = 'not_applicable'
REASON_APPLICABILITY_MISMATCH = 'applicability_mismatch'
MAX_SAFE_INTEGER = 2**53 - 1


class GateName(StrEnum):
    FILE_PLAYABLE = 'FILE_PLAYABLE'
    DURATION_RANGE = 'DURATION_RANGE'
    VISUAL_HOOK_PRESENT = 'VISUAL_HOOK_PRESENT'
    AUDIO_HOOK_PRESENT = 'AUDIO_HOOK_PRESENT'
    THUMBNAIL_PRESENT = 'THUMBNAIL_PRESENT'
    SUBTITLE_BURNED_IN = 'SUBTITLE_BURNED_IN'
    KARAOKE_TIMING_VALID = 'KARAOKE_TIMING_VALID'
    VOICE_AUDIBLE = 'VOICE_AUDIBLE'
    ENGLISH_OUTPUT_VALID = 'ENGLISH_OUTPUT_VALID'
    OUTPUT_PROFILE_VALID = 'OUTPUT_PROFILE_VALID'
    INFERENCE_DISCLOSURE_PRESENT = 'INFERENCE_DISCLOSURE_PRESENT'
    VISUAL_CONTINUITY = 'VISUAL_CONTINUITY'
    AUDIO_MIX_QUALITY = 'AUDIO_MIX_QUALITY'


class GateKind(StrEnum):
    HARD = 'hard'
    HARD_CONDITIONAL = 'hard_conditional'
    WARNING = 'warning'


class GateStatus(StrEnum):
    PASSED = 'passed'
    FAILED = 'failed'
    NOT_APPLICABLE = 'not_applicable'
    NOT_EVALUATED = 'not_evaluated'


class QualityReportError(ValueError):
    """A value broke CT-QC-001; `code` is the stable reason and `field` the offending field or gate name."""

    def __init__(self, code: str, field: str) -> None:
        super().__init__(f'{code}:{field}')
        self.code = code
        self.field = field


GATE_ORDER: tuple[GateName, ...] = tuple(GateName)
GATE_KINDS: Mapping[GateName, GateKind] = MappingProxyType({
    GateName.FILE_PLAYABLE: GateKind.HARD,
    GateName.DURATION_RANGE: GateKind.HARD,
    GateName.VISUAL_HOOK_PRESENT: GateKind.HARD,
    GateName.AUDIO_HOOK_PRESENT: GateKind.HARD,
    GateName.THUMBNAIL_PRESENT: GateKind.HARD,
    GateName.SUBTITLE_BURNED_IN: GateKind.HARD,
    GateName.KARAOKE_TIMING_VALID: GateKind.HARD,
    GateName.VOICE_AUDIBLE: GateKind.HARD,
    GateName.ENGLISH_OUTPUT_VALID: GateKind.HARD,
    GateName.OUTPUT_PROFILE_VALID: GateKind.HARD,
    GateName.INFERENCE_DISCLOSURE_PRESENT: GateKind.HARD_CONDITIONAL,
    GateName.VISUAL_CONTINUITY: GateKind.WARNING,
    GateName.AUDIO_MIX_QUALITY: GateKind.WARNING,
})


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _safe_int(value: int, field: str) -> int:
    if abs(value) > MAX_SAFE_INTEGER:
        raise QualityReportError(INVALID_VALUE, field)
    return value


def _gate_name(value: object, field: str) -> GateName:
    if isinstance(value, GateName):
        return value
    if not isinstance(value, str):
        raise QualityReportError(WRONG_TYPE, field)
    try:
        return GateName(value)
    except ValueError:
        raise QualityReportError(UNKNOWN_GATE, field) from None


def _status(value: object) -> GateStatus:
    if isinstance(value, GateStatus):
        return value
    if not isinstance(value, str):
        raise QualityReportError(WRONG_TYPE, 'status')
    try:
        return GateStatus(value)
    except ValueError:
        raise QualityReportError(INVALID_VALUE, 'status') from None


def _optional_text(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise QualityReportError(WRONG_TYPE, field)
    if not value.strip():
        raise QualityReportError(INVALID_VALUE, field)
    return value


def _time_range(value: object) -> tuple[int, int] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 2 or not all(_is_int(item) for item in value):
        raise QualityReportError(WRONG_TYPE, 'time_range')
    start, end = value
    if start < 0 or end < start:
        raise QualityReportError(INVALID_VALUE, 'time_range')
    return (_safe_int(start, 'time_range'), _safe_int(end, 'time_range'))


def _measured_value(value: object) -> object:
    if value is None or isinstance(value, (str, bool)):
        return value
    if _is_int(value):
        return _safe_int(value, 'measured_value')
    if isinstance(value, float):
        if not math.isfinite(value):
            raise QualityReportError(INVALID_VALUE, 'measured_value')
        return value
    raise QualityReportError(WRONG_TYPE, 'measured_value')


@dataclass(frozen=True, kw_only=True)
class GateResult:
    """Frozen outcome of one gate: status, evidence_ref and/or time_range (ms), measured_value, threshold_revision, reason.

    Text inputs for gate and status are coerced to the enums. not_applicable is only legal for hard_conditional gates and
    every status other than passed needs a reason. measured_value is a finite scalar.
    """

    gate: GateName
    status: GateStatus
    evidence_ref: str | None = None
    time_range: tuple[int, int] | None = None
    measured_value: bool | int | float | str | None = None
    threshold_revision: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, 'gate', _gate_name(self.gate, 'gate'))
        object.__setattr__(self, 'status', _status(self.status))
        object.__setattr__(self, 'evidence_ref', _optional_text(self.evidence_ref, 'evidence_ref'))
        object.__setattr__(self, 'time_range', _time_range(self.time_range))
        object.__setattr__(self, 'measured_value', _measured_value(self.measured_value))
        object.__setattr__(self, 'threshold_revision', _optional_text(self.threshold_revision, 'threshold_revision'))
        object.__setattr__(self, 'reason', _optional_text(self.reason, 'reason'))
        if self.status is GateStatus.NOT_APPLICABLE and self.kind is not GateKind.HARD_CONDITIONAL:
            raise QualityReportError(INVALID_VALUE, 'status')
        if self.status is not GateStatus.PASSED and self.reason is None:
            raise QualityReportError(MISSING_REQUIRED, 'reason')

    @property
    def kind(self) -> GateKind:
        return GATE_KINDS[self.gate]


def _freeze(value: object, field: str) -> object:
    if value is None or isinstance(value, (str, bool)):
        return value
    if _is_int(value):
        return _safe_int(value, field)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise QualityReportError(INVALID_VALUE, field)
        return value
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise QualityReportError(WRONG_TYPE, field)
        return MappingProxyType({key: _freeze(item, field) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item, field) for item in value)
    raise QualityReportError(WRONG_TYPE, field)


@dataclass(frozen=True)
class QualityPolicy:
    """Frozen quality policy revision; thresholds maps a gate name to its caller-supplied threshold data (deep-frozen)."""

    revision: str
    thresholds: Mapping[str, object]

    def __post_init__(self) -> None:
        if _optional_text(self.revision, 'revision') is None:
            raise QualityReportError(MISSING_REQUIRED, 'revision')
        if not isinstance(self.thresholds, Mapping):
            raise QualityReportError(WRONG_TYPE, 'thresholds')
        frozen = {_gate_name(key, 'thresholds').value: _freeze(value, 'thresholds') for key, value in self.thresholds.items()}
        object.__setattr__(self, 'thresholds', MappingProxyType(frozen))

    def __hash__(self) -> int:
        return hash(self.revision)

    def has_threshold(self, gate: GateName | str) -> bool:
        """True when the policy holds a non-empty threshold for gate; an unknown gate name raises."""
        value = self.thresholds.get(_gate_name(gate, 'gate').value)
        if value is None:
            return False
        return not (isinstance(value, (str, tuple, Mapping)) and len(value) == 0)


def _is_counted(item: GateResult) -> bool:
    if item.kind is GateKind.HARD:
        return True
    return item.kind is GateKind.HARD_CONDITIONAL and item.status is not GateStatus.NOT_APPLICABLE


def _compute_passed(gates: tuple[GateResult, ...]) -> bool:
    return all(item.status is GateStatus.PASSED for item in gates if _is_counted(item))


def compute_report_id(policy_revision: str | None, gates: tuple[GateResult, ...]) -> str:
    """request_hash over the policy revision and every gate result (passed is derived and not part of the basis)."""
    basis = {
        'policy_revision': policy_revision,
        'gates': [
            {
                'gate': item.gate.value,
                'status': item.status.value,
                'evidence_ref': item.evidence_ref,
                'time_range': None if item.time_range is None else list(item.time_range),
                'measured_value': item.measured_value,
                'threshold_revision': item.threshold_revision,
                'reason': item.reason,
            }
            for item in gates
        ],
    }
    try:
        return request_hash(basis)
    except ValueError as exc:
        raise QualityReportError(INVALID_VALUE, 'report_id') from exc


@dataclass(frozen=True, kw_only=True)
class QualityReport:
    """Frozen CT-QC-001 report: all thirteen gates in GateName order; passed and report_id are verified on construction."""

    report_id: str
    policy_revision: str | None
    gates: tuple[GateResult, ...]
    passed: bool

    def __post_init__(self) -> None:
        gates = tuple(self.gates)
        if not all(isinstance(item, GateResult) for item in gates):
            raise QualityReportError(WRONG_TYPE, 'gates')
        if tuple(item.gate for item in gates) != GATE_ORDER:
            raise QualityReportError(INVALID_VALUE, 'gates')
        object.__setattr__(self, 'gates', gates)
        object.__setattr__(self, 'policy_revision', _optional_text(self.policy_revision, 'policy_revision'))
        if self.passed is not _compute_passed(gates):
            raise QualityReportError(INVALID_VALUE, 'passed')
        if self.report_id != compute_report_id(self.policy_revision, gates):
            raise QualityReportError(INVALID_VALUE, 'report_id')

    @property
    def blocking_gates(self) -> tuple[GateName, ...]:
        """Counted gates (hard, and hard_conditional when applicable) whose status is not passed."""
        return tuple(item.gate for item in self.gates if _is_counted(item) and item.status is not GateStatus.PASSED)


def _index_results(results: Iterable[GateResult]) -> dict[GateName, GateResult]:
    try:
        items = tuple(results)
    except TypeError:
        raise QualityReportError(WRONG_TYPE, 'results') from None
    indexed: dict[GateName, GateResult] = {}
    for item in items:
        if not isinstance(item, GateResult):
            raise QualityReportError(WRONG_TYPE, 'results')
        if item.gate in indexed:
            raise QualityReportError(DUPLICATE_GATE, item.gate.value)
        indexed[item.gate] = item
    return indexed


def _applicability_flags(applicability: Mapping[object, bool] | None) -> dict[GateName, bool]:
    if applicability is None:
        return {}
    if not isinstance(applicability, Mapping):
        raise QualityReportError(WRONG_TYPE, 'applicability')
    flags: dict[GateName, bool] = {}
    for key, value in applicability.items():
        name = _gate_name(key, 'applicability')
        if GATE_KINDS[name] is not GateKind.HARD_CONDITIONAL:
            raise QualityReportError(INVALID_VALUE, 'applicability')
        if not isinstance(value, bool):
            raise QualityReportError(WRONG_TYPE, 'applicability')
        flags[name] = value
    return flags


def _warning_result(name: GateName, item: GateResult | None, policy: QualityPolicy | None) -> GateResult:
    ready = item is not None and item.threshold_revision is not None and (policy is None or policy.has_threshold(name))
    if ready:
        return item
    return GateResult(gate=name, status=GateStatus.NOT_EVALUATED, reason=INPUT_NOT_READY)


def _final_result(name: GateName, item: GateResult | None, flags: dict[GateName, bool], policy: QualityPolicy | None) -> GateResult:
    kind = GATE_KINDS[name]
    if kind is GateKind.WARNING:
        return _warning_result(name, item, policy)
    if kind is GateKind.HARD_CONDITIONAL and flags.get(name) is False:
        return GateResult(gate=name, status=GateStatus.NOT_APPLICABLE, reason=REASON_NOT_APPLICABLE)
    if item is None:
        return GateResult(gate=name, status=GateStatus.NOT_EVALUATED, reason=REASON_MISSING_RESULT)
    if item.status is GateStatus.NOT_APPLICABLE:
        return GateResult(gate=name, status=GateStatus.NOT_EVALUATED, reason=REASON_APPLICABILITY_MISMATCH)
    return item


def build_quality_report(
    results: Iterable[GateResult],
    applicability: Mapping[object, bool] | None = None,
    *,
    policy: QualityPolicy | None = None,
) -> QualityReport:
    """Build the report with all thirteen gates in GateName order.

    A missing hard gate becomes not_evaluated (missing_result) and fails the report; a hard_conditional gate is skipped
    (not_applicable) only when applicability maps it to False; a warning without a threshold (no threshold_revision, or
    absent from `policy` when given) becomes not_evaluated with INPUT_NOT_READY and never affects `passed`.
    Duplicate gates raise duplicate_gate; unknown names raise unknown_gate.
    """
    if policy is not None and not isinstance(policy, QualityPolicy):
        raise QualityReportError(WRONG_TYPE, 'policy')
    indexed = _index_results(results)
    flags = _applicability_flags(applicability)
    gates = tuple(_final_result(name, indexed.get(name), flags, policy) for name in GATE_ORDER)
    revision = None if policy is None else policy.revision
    return QualityReport(report_id=compute_report_id(revision, gates), policy_revision=revision, gates=gates, passed=_compute_passed(gates))
