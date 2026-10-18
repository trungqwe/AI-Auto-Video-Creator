"""CollectionRun and CollectionAttempt state machine (CT-STATE-002, A-RULE-004, A-RULE-005)."""
from __future__ import annotations

from collections.abc import Iterable
import dataclasses
import datetime
import enum
import logging

logger = logging.getLogger(__name__)


class CollectionPurpose(str, enum.Enum):
    PERIODIC = 'PERIODIC'
    SOURCE_TEST = 'SOURCE_TEST'
    SUPPLEMENTAL = 'SUPPLEMENTAL'


class RunStatus(str, enum.Enum):
    SCHEDULED = 'SCHEDULED'
    RUNNING = 'RUNNING'
    WAITING_RETRY = 'WAITING_RETRY'
    WAITING_RECONCILIATION = 'WAITING_RECONCILIATION'
    COMPLETED = 'COMPLETED'
    COMPLETED_PARTIAL = 'COMPLETED_PARTIAL'
    FAILED_FINAL = 'FAILED_FINAL'


class AttemptOutcome(str, enum.Enum):
    SUCCEEDED = 'SUCCEEDED'
    FAILED_RETRYABLE = 'FAILED_RETRYABLE'
    FAILED_FINAL = 'FAILED_FINAL'
    OUTCOME_UNKNOWN = 'OUTCOME_UNKNOWN'


class TerminalReason(str, enum.Enum):
    ALL_WORK_DONE = 'ALL_WORK_DONE'
    RETRY_EXHAUSTED = 'RETRY_EXHAUSTED'
    SOURCE_INACTIVE = 'SOURCE_INACTIVE'
    FINAL_ERROR = 'FINAL_ERROR'


class ReconciliationResult(str, enum.Enum):
    RETRYABLE = 'RETRYABLE'
    ALL_WORK_DONE = 'ALL_WORK_DONE'
    FINAL_STOP = 'FINAL_STOP'
    DONE_CONTINUE = 'DONE_CONTINUE'


TERMINAL_STATUSES = frozenset({RunStatus.COMPLETED, RunStatus.COMPLETED_PARTIAL, RunStatus.FAILED_FINAL})


class InvalidTransitionError(ValueError):
    pass


class TerminalRunError(InvalidTransitionError):
    pass


class DuplicatePeriodicRunError(ValueError):
    pass


@dataclasses.dataclass(frozen=True)
class RetryPolicy:
    revision: str
    max_attempts: int

    def __post_init__(self) -> None:
        if not isinstance(self.revision, str) or not self.revision:
            raise ValueError('revision must be a non-empty string')
        if isinstance(self.max_attempts, bool) or not isinstance(self.max_attempts, int) or self.max_attempts < 1:
            raise ValueError('max_attempts must be an integer >= 1')


@dataclasses.dataclass(frozen=True)
class CollectionAttempt:
    attempt_no: int
    outcome: AttemptOutcome


@dataclasses.dataclass(frozen=True)
class ReconciliationRecord:
    attempt_no: int
    result: ReconciliationResult
    evidence_ref: str


@dataclasses.dataclass(frozen=True)
class TerminalDecision:
    status: RunStatus
    reason: TerminalReason
    policy_revision: str
    checkpoint_ref: str


@dataclasses.dataclass(frozen=True)
class CollectionRun:
    run_id: str
    workspace_id: str
    source_id: str
    business_date: datetime.date
    purpose: CollectionPurpose
    retry_policy: RetryPolicy
    status: RunStatus
    attempts: tuple[CollectionAttempt, ...] = ()
    reconciliations: tuple[ReconciliationRecord, ...] = ()
    committed_package_count: int = 0
    checkpoint_ref: str | None = None
    terminal_decision: TerminalDecision | None = None
    warnings: tuple[str, ...] = ()

    @property
    def unique_key(self) -> tuple[str, str, datetime.date, CollectionPurpose] | None:
        if self.purpose is not CollectionPurpose.PERIODIC:
            return None
        return (self.workspace_id, self.source_id, self.business_date, CollectionPurpose.PERIODIC)


def _checkpoint(ref: str) -> str:
    if not isinstance(ref, str) or not ref:
        raise ValueError('checkpoint_ref must be a non-empty string')
    return ref


def _require(run: CollectionRun, *allowed: RunStatus) -> None:
    if run.status in TERMINAL_STATUSES:
        raise TerminalRunError(f'run {run.run_id} is terminal ({run.status.value}) and cannot be reopened')
    if run.status not in allowed:
        raise InvalidTransitionError(f'{run.status.value} does not allow this transition')


def _has_budget(run: CollectionRun) -> bool:
    return len(run.attempts) < run.retry_policy.max_attempts


def _terminate(
    run: CollectionRun,
    status: RunStatus,
    reason: TerminalReason,
    checkpoint_ref: str,
) -> CollectionRun:
    return dataclasses.replace(
        run,
        status=status,
        checkpoint_ref=checkpoint_ref,
        terminal_decision=TerminalDecision(status, reason, run.retry_policy.revision, checkpoint_ref),
    )


def _stop(run: CollectionRun, reason: TerminalReason, checkpoint_ref: str) -> CollectionRun:
    status = RunStatus.COMPLETED_PARTIAL if run.committed_package_count > 0 else RunStatus.FAILED_FINAL
    return _terminate(run, status, reason, checkpoint_ref)


def _retry_or_stop(
    run: CollectionRun,
    *,
    source_active: bool,
    deadline_passed: bool,
    checkpoint_ref: str,
) -> CollectionRun:
    if not source_active:
        return _stop(run, TerminalReason.SOURCE_INACTIVE, checkpoint_ref)
    if deadline_passed or not _has_budget(run):
        return _stop(run, TerminalReason.RETRY_EXHAUSTED, checkpoint_ref)
    return dataclasses.replace(run, status=RunStatus.WAITING_RETRY, checkpoint_ref=checkpoint_ref)


def schedule_run(
    *,
    run_id: str,
    workspace_id: str,
    source_id: str,
    business_date: datetime.date,
    purpose: CollectionPurpose,
    retry_policy: RetryPolicy,
) -> CollectionRun:
    if not isinstance(purpose, CollectionPurpose):
        raise TypeError('purpose must be a CollectionPurpose')
    if not isinstance(retry_policy, RetryPolicy):
        raise TypeError('retry_policy must be a RetryPolicy')
    if not isinstance(business_date, datetime.date):
        raise TypeError('business_date must be a datetime.date')
    if not isinstance(run_id, str) or not run_id:
        raise ValueError('run_id must be a non-empty string')
    if not isinstance(workspace_id, str) or not workspace_id:
        raise ValueError('workspace_id must be a non-empty string')
    if not isinstance(source_id, str) or not source_id:
        raise ValueError('source_id must be a non-empty string')
    return CollectionRun(
        run_id=run_id,
        workspace_id=workspace_id,
        source_id=source_id,
        business_date=business_date,
        purpose=purpose,
        retry_policy=retry_policy,
        status=RunStatus.SCHEDULED,
    )


def ensure_periodic_unique(existing: Iterable[CollectionRun], candidate: CollectionRun) -> None:
    key = candidate.unique_key
    if key is None:
        return
    for r in existing:
        if r.unique_key == key:
            raise DuplicatePeriodicRunError(f'periodic run already exists for {key!r}')


def start_run(run: CollectionRun, *, source_active: bool, checkpoint_ref: str) -> CollectionRun:
    _require(run, RunStatus.SCHEDULED)
    cp = _checkpoint(checkpoint_ref)
    if not source_active:
        return _terminate(run, RunStatus.FAILED_FINAL, TerminalReason.SOURCE_INACTIVE, cp)
    return dataclasses.replace(run, status=RunStatus.RUNNING, checkpoint_ref=cp)


def record_committed_packages(run: CollectionRun, count: int) -> CollectionRun:
    _require(run, RunStatus.RUNNING)
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError('count must be an integer >= 1')
    return dataclasses.replace(run, committed_package_count=run.committed_package_count + count)


def record_attempt_outcome(
    run: CollectionRun,
    outcome: AttemptOutcome,
    *,
    source_active: bool,
    deadline_passed: bool,
    checkpoint_ref: str,
) -> CollectionRun:
    _require(run, RunStatus.RUNNING)
    cp = _checkpoint(checkpoint_ref)
    if not isinstance(outcome, AttemptOutcome):
        raise TypeError('outcome must be an AttemptOutcome')
    run = dataclasses.replace(
        run,
        attempts=run.attempts + (CollectionAttempt(len(run.attempts) + 1, outcome),),
    )
    if outcome == AttemptOutcome.SUCCEEDED:
        return _terminate(run, RunStatus.COMPLETED, TerminalReason.ALL_WORK_DONE, cp)
    if outcome == AttemptOutcome.FAILED_RETRYABLE:
        return _retry_or_stop(
            run,
            source_active=source_active,
            deadline_passed=deadline_passed,
            checkpoint_ref=cp,
        )
    if outcome == AttemptOutcome.FAILED_FINAL:
        return _stop(run, TerminalReason.FINAL_ERROR, cp)
    if outcome == AttemptOutcome.OUTCOME_UNKNOWN:
        return dataclasses.replace(run, status=RunStatus.WAITING_RECONCILIATION, checkpoint_ref=cp)
    raise ValueError(f'unhandled outcome {outcome!r}')


def resume_retry(
    run: CollectionRun,
    *,
    source_active: bool,
    deadline_passed: bool,
    checkpoint_ref: str,
) -> CollectionRun:
    _require(run, RunStatus.WAITING_RETRY)
    cp = _checkpoint(checkpoint_ref)
    if not source_active:
        return _stop(run, TerminalReason.SOURCE_INACTIVE, cp)
    if deadline_passed or not _has_budget(run):
        return _stop(run, TerminalReason.RETRY_EXHAUSTED, cp)
    return dataclasses.replace(run, status=RunStatus.RUNNING, checkpoint_ref=cp)


def deactivate_source(run: CollectionRun, *, checkpoint_ref: str) -> CollectionRun:
    _require(run, RunStatus.SCHEDULED, RunStatus.RUNNING, RunStatus.WAITING_RETRY)
    cp = _checkpoint(checkpoint_ref)
    if run.status == RunStatus.SCHEDULED:
        return _terminate(run, RunStatus.FAILED_FINAL, TerminalReason.SOURCE_INACTIVE, cp)
    return _stop(run, TerminalReason.SOURCE_INACTIVE, cp)


def reconcile(
    run: CollectionRun,
    result: ReconciliationResult,
    *,
    evidence_ref: str,
    source_active: bool,
    deadline_passed: bool,
    checkpoint_ref: str,
) -> CollectionRun:
    _require(run, RunStatus.WAITING_RECONCILIATION)
    cp = _checkpoint(checkpoint_ref)
    if not isinstance(result, ReconciliationResult):
        raise TypeError('result must be a ReconciliationResult')
    if not isinstance(evidence_ref, str) or not evidence_ref:
        raise ValueError('evidence_ref must be a non-empty string')
    run = dataclasses.replace(
        run,
        reconciliations=run.reconciliations + (
            ReconciliationRecord(run.attempts[-1].attempt_no, result, evidence_ref),
        ),
    )
    if result == ReconciliationResult.RETRYABLE:
        return _retry_or_stop(
            run,
            source_active=source_active,
            deadline_passed=deadline_passed,
            checkpoint_ref=cp,
        )
    if result == ReconciliationResult.ALL_WORK_DONE:
        return _terminate(run, RunStatus.COMPLETED, TerminalReason.ALL_WORK_DONE, cp)
    if result == ReconciliationResult.FINAL_STOP:
        return _stop(run, TerminalReason.FINAL_ERROR, cp)
    if result == ReconciliationResult.DONE_CONTINUE:
        if not source_active:
            return _stop(run, TerminalReason.SOURCE_INACTIVE, cp)
        return dataclasses.replace(run, status=RunStatus.RUNNING, checkpoint_ref=cp)
    raise ValueError(f'unhandled reconciliation result {result!r}')


def flag_reconciliation_overdue(run: CollectionRun, *, warning: str) -> CollectionRun:
    _require(run, RunStatus.WAITING_RECONCILIATION)
    if not isinstance(warning, str) or not warning:
        raise ValueError('warning must be a non-empty string')
    logger.warning('collection run %s reconciliation overdue: %s', run.run_id, warning)
    return dataclasses.replace(run, warnings=run.warnings + (warning,))
