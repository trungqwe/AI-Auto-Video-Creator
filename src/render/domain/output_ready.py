"""F-15: VideoOutput, output ready and the four independent milestones (CT-RND-005, TST-E2E-INV-009).

evaluate_output_ready returns OutputReady only when the receipt is SUCCEEDED, the observed output hash equals the expected hash, report.passed (every hard gate), report and artifact refs are committed and the execution grant is valid; otherwise NotReady lists every failed reason. create_video_output builds the frozen VideoOutput only from an OutputReady verdict. MilestoneState keeps render_succeeded, qc_passed, upload_verified (fact from I) and completion_committed (fact from G) as four independent flags. A technically successful render is not a finished video; this module only reads facts.
Pure domain: no I/O, no clock.

coveredIds: CT-RND-005, TST-E2E-INV-009
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from controlplane.domain.statemachine import OperationState
from render.domain.quality_report import QualityReport
from render.domain.render_attempt import RenderAttempt

INVALID_INPUT = 'INVALID_INPUT'
QUALITY_NOT_PASSED = 'quality_not_passed'
OUTPUT_NOT_READY = 'output_not_ready'
REASON_RECEIPT_NOT_SUCCEEDED = 'receipt_not_succeeded'
REASON_OUTPUT_MISSING = 'output_missing'
REASON_EXPECTED_HASH_INVALID = 'expected_sha256_invalid'
REASON_HASH_MISMATCH = 'output_hash_mismatch'
REASON_REFS_NOT_COMMITTED = 'refs_not_committed'
REASON_GRANT_INVALID = 'grant_invalid'
_SHA256_RE = re.compile(r'[0-9A-Fa-f]{64}')
_TEXT_FIELDS = ('video_output_id', 'output_artifact_ref', 'quality_report_ref', 'render_attempt_ref', 'package_fingerprint', 'output_metadata_revision')
_FACT_FIELDS = ('render_succeeded', 'qc_passed', 'upload_verified', 'completion_committed')


class OutputReadyError(ValueError):
    """Stable error: `code` is the machine code and `reasons` lists every failed condition."""

    def __init__(self, code: str, reasons: tuple[str, ...] = ()) -> None:
        reasons = tuple(reasons)
        detail = ', '.join(reasons)
        super().__init__(f'{code}: {detail}' if detail else code)
        self.code = code
        self.reasons = reasons


def _invalid(name: str) -> OutputReadyError:
    return OutputReadyError(INVALID_INPUT, (f'invalid_{name}',))


def _sha(value: object) -> str | None:
    return value.lower() if isinstance(value, str) and _SHA256_RE.fullmatch(value) else None


@dataclass(frozen=True, kw_only=True)
class VideoOutput:
    """Frozen CT-RND-005 output; output_sha256 is stored lower-case and every text field must be a non-blank string."""

    video_output_id: str
    output_artifact_ref: str
    output_sha256: str
    quality_report_ref: str
    render_attempt_ref: str
    package_fingerprint: str
    output_metadata_revision: str

    def __post_init__(self) -> None:
        for name in _TEXT_FIELDS:
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise _invalid(name)
        digest = _sha(self.output_sha256)
        if digest is None:
            raise _invalid('output_sha256')
        object.__setattr__(self, 'output_sha256', digest)


@dataclass(frozen=True, kw_only=True)
class OutputReady:
    """Verdict: every CT-RND-005 condition holds; carries the refs G needs."""

    render_attempt_ref: str
    output_artifact_ref: str
    output_sha256: str
    quality_report_ref: str
    package_fingerprint: str

    @property
    def ready(self) -> bool:
        return True


@dataclass(frozen=True, kw_only=True)
class NotReady:
    """Verdict: at least one condition failed; reasons lists every failed condition in a fixed order."""

    reasons: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return False


@dataclass(frozen=True, kw_only=True)
class MilestoneState:
    """Four independent facts; completion_eligible is the only derived view and never implies completion_committed."""

    render_succeeded: bool
    qc_passed: bool
    upload_verified: bool
    completion_committed: bool

    def __post_init__(self) -> None:
        for name in _FACT_FIELDS:
            if type(getattr(self, name)) is not bool:
                raise _invalid(name)

    @property
    def completion_eligible(self) -> bool:
        return self.render_succeeded and self.qc_passed and self.upload_verified


def evaluate_output_ready(
    attempt: RenderAttempt,
    observed_sha256: str | None,
    report: QualityReport,
    refs_committed: bool,
    grant_valid: bool,
    *,
    expected_sha256: str | None,
) -> OutputReady | NotReady:
    """CT-RND-005: ready only when every condition holds; expected_sha256 is the hash the verified source records (RenderAttempt carries none)."""
    if not isinstance(attempt, RenderAttempt):
        raise _invalid('attempt')
    if not isinstance(report, QualityReport):
        raise _invalid('report')
    observed, expected = _sha(observed_sha256), _sha(expected_sha256)
    reasons = []
    if attempt.receipt_state is not OperationState.SUCCEEDED:
        reasons.append(REASON_RECEIPT_NOT_SUCCEEDED)
    if observed_sha256 is None:
        reasons.append(REASON_OUTPUT_MISSING)
    elif expected is None:
        reasons.append(REASON_EXPECTED_HASH_INVALID)
    elif observed != expected:
        reasons.append(REASON_HASH_MISMATCH)
    if not report.passed:
        reasons.append(QUALITY_NOT_PASSED)
    if refs_committed is not True:
        reasons.append(REASON_REFS_NOT_COMMITTED)
    if grant_valid is not True:
        reasons.append(REASON_GRANT_INVALID)
    if reasons:
        return NotReady(reasons=tuple(reasons))
    return OutputReady(
        render_attempt_ref=attempt.render_attempt_id,
        output_artifact_ref=attempt.output_artifact_ref,
        output_sha256=observed,
        quality_report_ref=report.report_id,
        package_fingerprint=attempt.package_fingerprint,
    )


def create_video_output(
    *,
    video_output_id: str,
    attempt: RenderAttempt,
    observed_sha256: str | None,
    expected_sha256: str | None,
    report: QualityReport,
    refs_committed: bool,
    grant_valid: bool,
    output_metadata_revision: str,
) -> VideoOutput:
    """Build VideoOutput from an OutputReady verdict; raise OutputReadyError(quality_not_passed) when QC failed, output_not_ready for any other failed condition."""
    verdict = evaluate_output_ready(attempt, observed_sha256, report, refs_committed, grant_valid, expected_sha256=expected_sha256)
    if isinstance(verdict, NotReady):
        code = QUALITY_NOT_PASSED if QUALITY_NOT_PASSED in verdict.reasons else OUTPUT_NOT_READY
        raise OutputReadyError(code, verdict.reasons)
    return VideoOutput(
        video_output_id=video_output_id,
        output_artifact_ref=verdict.output_artifact_ref,
        output_sha256=verdict.output_sha256,
        quality_report_ref=verdict.quality_report_ref,
        render_attempt_ref=verdict.render_attempt_ref,
        package_fingerprint=verdict.package_fingerprint,
        output_metadata_revision=output_metadata_revision,
    )


def derive_milestones(attempt: RenderAttempt, report: QualityReport, *, upload_verified: bool, completion_committed: bool) -> MilestoneState:
    """Read render_succeeded from the receipt and qc_passed from the report; upload_verified (I) and completion_committed (G) are inputs."""
    if not isinstance(attempt, RenderAttempt):
        raise _invalid('attempt')
    if not isinstance(report, QualityReport):
        raise _invalid('report')
    return MilestoneState(
        render_succeeded=attempt.receipt_state is OperationState.SUCCEEDED,
        qc_passed=report.passed,
        upload_verified=upload_verified,
        completion_committed=completion_committed,
    )


__all__ = [
    'INVALID_INPUT',
    'MilestoneState',
    'NotReady',
    'OUTPUT_NOT_READY',
    'OutputReady',
    'OutputReadyError',
    'QUALITY_NOT_PASSED',
    'VideoOutput',
    'create_video_output',
    'derive_milestones',
    'evaluate_output_ready',
]
