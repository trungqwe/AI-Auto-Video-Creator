"""G-13: audit nhất quán chỉ đọc (R5 no-silent-failure; INV-010, INV-017, INV-018).

Pure domain: không I/O, không đồng hồ, không ghi. Snapshot bất biến; kết quả sắp xếp ổn định theo (code, ref).
"""
from __future__ import annotations

from dataclasses import dataclass

from controlplane.domain.orchestration import ReservationState
from controlplane.domain.orchestration.job_waiting import WaitReason
from controlplane.domain.statemachine import JobState, StageRunState

LEDGER_COUNT_MISMATCH = 'LEDGER_COUNT_MISMATCH'
ORPHAN_ACTIVE_RESERVATION = 'ORPHAN_ACTIVE_RESERVATION'
LEDGER_WITHOUT_COMPLETED_JOB = 'LEDGER_WITHOUT_COMPLETED_JOB'
WAITING_JOB_WITHOUT_REASON = 'WAITING_JOB_WITHOUT_REASON'
RUNNING_STAGE_WITHOUT_ACTIVE_GRANT = 'RUNNING_STAGE_WITHOUT_ACTIVE_GRANT'
JOB_WITHOUT_STATE_OR_LOG = 'JOB_WITHOUT_STATE_OR_LOG'
FINDING_CODES = (
    LEDGER_COUNT_MISMATCH,
    ORPHAN_ACTIVE_RESERVATION,
    LEDGER_WITHOUT_COMPLETED_JOB,
    WAITING_JOB_WITHOUT_REASON,
    RUNNING_STAGE_WITHOUT_ACTIVE_GRANT,
    JOB_WITHOUT_STATE_OR_LOG,
)
TERMINAL_JOB_STATES = frozenset({JobState.COMPLETED, JobState.FAILED_FINAL})


def _require_id(name: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f'{name} must be a non-empty str')


def _require_ids(name: str, value: object) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f'{name} must be a tuple')
    for item in value:
        _require_id(name, item)


@dataclass(frozen=True)
class Finding:
    code: str
    ref: str


@dataclass(frozen=True)
class BatchRecord:
    batch_id: str
    completed_count: int
    job_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_id('batch_id', self.batch_id)
        if isinstance(self.completed_count, bool) or not isinstance(self.completed_count, int) or self.completed_count < 0:
            raise TypeError('completed_count must be a non-negative int')
        _require_ids('job_ids', self.job_ids)


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    state: object
    wait_reason: object = None
    log_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_id('job_id', self.job_id)
        _require_ids('log_refs', self.log_refs)

@dataclass(frozen=True)
class ReservationRecord:
    reservation_id: str
    job_id: str
    state: object

    def __post_init__(self) -> None:
        _require_id('reservation_id', self.reservation_id)
        _require_id('job_id', self.job_id)


@dataclass(frozen=True)
class LedgerRecord:
    ledger_id: str
    batch_id: str
    job_id: str

    def __post_init__(self) -> None:
        _require_id('ledger_id', self.ledger_id)
        _require_id('batch_id', self.batch_id)
        _require_id('job_id', self.job_id)


@dataclass(frozen=True)
class StageRunRecord:
    stage_run_id: str
    job_id: str
    state: object

    def __post_init__(self) -> None:
        _require_id('stage_run_id', self.stage_run_id)
        _require_id('job_id', self.job_id)


@dataclass(frozen=True)
class GrantRecord:
    stage_run_id: str
    active: bool

    def __post_init__(self) -> None:
        _require_id('stage_run_id', self.stage_run_id)
        if not isinstance(self.active, bool):
            raise TypeError('active must be bool')


_SNAPSHOT_FIELDS = (
    ('batches', BatchRecord),
    ('jobs', JobRecord),
    ('reservations', ReservationRecord),
    ('ledgers', LedgerRecord),
    ('stage_runs', StageRunRecord),
    ('grants', GrantRecord),
)


@dataclass(frozen=True)
class ConsistencySnapshot:
    batches: tuple[BatchRecord, ...] = ()
    jobs: tuple[JobRecord, ...] = ()
    reservations: tuple[ReservationRecord, ...] = ()
    ledgers: tuple[LedgerRecord, ...] = ()
    stage_runs: tuple[StageRunRecord, ...] = ()
    grants: tuple[GrantRecord, ...] = ()

    def __post_init__(self) -> None:
        for name, record_type in _SNAPSHOT_FIELDS:
            rows = getattr(self, name)
            if not isinstance(rows, tuple) or not all(isinstance(row, record_type) for row in rows):
                raise TypeError(f'{name} must be a tuple of {record_type.__name__}')


def _coerce(enum_type: type, value: object) -> object | None:
    if isinstance(value, enum_type):
        return value
    if isinstance(value, str):
        try:
            return enum_type(value)
        except ValueError:
            return None
    return None


def audit_consistency(snapshot: ConsistencySnapshot) -> tuple[Finding, ...]:
    if not isinstance(snapshot, ConsistencySnapshot):
        raise TypeError('snapshot must be ConsistencySnapshot')
    jobs = {record.job_id: record for record in snapshot.jobs}
    found: set[tuple[str, str]] = set()
    ledger_counts: dict[str, int] = {}
    for ledger in snapshot.ledgers:
        ledger_counts[ledger.batch_id] = ledger_counts.get(ledger.batch_id, 0) + 1
    for batch in snapshot.batches:
        if batch.completed_count != ledger_counts.get(batch.batch_id, 0):
            found.add((LEDGER_COUNT_MISMATCH, batch.batch_id))
        for job_id in batch.job_ids:
            if job_id not in jobs:
                found.add((JOB_WITHOUT_STATE_OR_LOG, job_id))
    for record in snapshot.jobs:
        state = _coerce(JobState, record.state)
        if state is None or not record.log_refs:
            found.add((JOB_WITHOUT_STATE_OR_LOG, record.job_id))
        if state == JobState.WAITING and _coerce(WaitReason, record.wait_reason) is None:
            found.add((WAITING_JOB_WITHOUT_REASON, record.job_id))
    for reservation in snapshot.reservations:
        if _coerce(ReservationState, reservation.state) != ReservationState.ACTIVE:
            continue
        owner = jobs.get(reservation.job_id)
        if owner is None or _coerce(JobState, owner.state) in TERMINAL_JOB_STATES:
            found.add((ORPHAN_ACTIVE_RESERVATION, reservation.reservation_id))
    for ledger in snapshot.ledgers:
        owner = jobs.get(ledger.job_id)
        if owner is None or _coerce(JobState, owner.state) != JobState.COMPLETED:
            found.add((LEDGER_WITHOUT_COMPLETED_JOB, ledger.ledger_id))
    active_grants = {grant.stage_run_id for grant in snapshot.grants if grant.active}
    for run in snapshot.stage_runs:
        if _coerce(StageRunState, run.state) == StageRunState.RUNNING and run.stage_run_id not in active_grants:
            found.add((RUNNING_STAGE_WITHOUT_ACTIVE_GRANT, run.stage_run_id))
    return tuple(Finding(code, ref) for code, ref in sorted(found))


__all__ = [
    'FINDING_CODES', 'JOB_WITHOUT_STATE_OR_LOG', 'LEDGER_COUNT_MISMATCH', 'LEDGER_WITHOUT_COMPLETED_JOB', 'ORPHAN_ACTIVE_RESERVATION',
    'RUNNING_STAGE_WITHOUT_ACTIVE_GRANT', 'TERMINAL_JOB_STATES', 'WAITING_JOB_WITHOUT_REASON',
    'BatchRecord', 'ConsistencySnapshot', 'Finding', 'GrantRecord', 'JobRecord', 'LedgerRecord', 'ReservationRecord', 'StageRunRecord',
    'audit_consistency',
]
