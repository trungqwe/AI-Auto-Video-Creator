"""PostgreSQL allocation store for caller-owned transactions."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
import uuid

from controlplane.application.orchestration.job_allocation import JobReservation
from controlplane.domain.orchestration import OrchestrationContractError
from controlplane.domain.orchestration.allocation_policy import AllocationCandidate

_SAVEPOINT = 'persist_g_lock_batch'
_ANGLE_PREFIX = 'allocation:'


class PostgresAllocationStore:
    def __init__(self, connection: Any, workspace_id: str) -> None:
        self._connection = connection
        self._workspace_id = workspace_id

    @contextmanager
    def lock_batch(self, batch_id: str) -> Iterator[int]:
        self._connection.execute(f'SAVEPOINT {_SAVEPOINT}')
        try:
            row = self._connection.execute(
                "SELECT target_count FROM controlplane.cp_production_batches "
                "WHERE workspace_id = %s AND batch_id = %s FOR UPDATE",
                (self._workspace_id, batch_id),
            ).fetchone()
            if row is None:
                raise OrchestrationContractError('NOT_FOUND')
            yield int(row[0])
        except BaseException:
            self._connection.execute(f'ROLLBACK TO SAVEPOINT {_SAVEPOINT}')
            self._connection.execute(f'RELEASE SAVEPOINT {_SAVEPOINT}')
            raise
        else:
            self._connection.execute(f'RELEASE SAVEPOINT {_SAVEPOINT}')

    def count_ledger(self, batch_id: str) -> int:
        row = self._connection.execute(
            "SELECT count(*) FROM controlplane.cp_completion_ledger "
            "WHERE workspace_id = %s AND batch_id = %s",
            (self._workspace_id, batch_id),
        ).fetchone()
        return int(row[0]) if row is not None else 0

    def count_active(self, batch_id: str) -> int:
        row = self._connection.execute(
            "SELECT count(*) FROM controlplane.cp_batch_capacity_reservations "
            "WHERE workspace_id = %s AND batch_id = %s AND state = 'ACTIVE'",
            (self._workspace_id, batch_id),
        ).fetchone()
        return int(row[0]) if row is not None else 0

    def find_reservation(self, job_id: str) -> JobReservation | None:
        row = self._connection.execute(
            "SELECT c.reservation_id, c.batch_id, c.job_id, j.snapshot_ref "
            "FROM controlplane.cp_batch_capacity_reservations c "
            "JOIN controlplane.cp_video_jobs j "
            "ON j.workspace_id = c.workspace_id AND j.job_id = c.job_id "
            "WHERE c.workspace_id = %s AND c.job_id = %s",
            (self._workspace_id, job_id),
        ).fetchone()
        if row is None:
            return None
        snap = str(row[3]) if row[3] is not None else ''
        angle_slot = snap[len(_ANGLE_PREFIX):] if snap.startswith(_ANGLE_PREFIX) else ''
        return JobReservation(str(row[1]), str(row[2]), str(row[0]), angle_slot)

    def find_candidate(self, job_id: str) -> AllocationCandidate | None:
        row = self._connection.execute(
            'SELECT k.candidate_ref, j.snapshot_ref, k.source_set_ref '
            'FROM controlplane.cp_job_candidates k '
            'JOIN controlplane.cp_video_jobs j '
            'ON j.workspace_id = k.workspace_id AND j.job_id = k.job_id '
            'WHERE k.workspace_id = %s AND k.job_id = %s',
            (self._workspace_id, job_id),
        ).fetchone()
        if row is None:
            return None
        snap = str(row[1]) if row[1] is not None else ''
        angle_slot = snap[len(_ANGLE_PREFIX):] if snap.startswith(_ANGLE_PREFIX) else ''
        return AllocationCandidate(str(row[0]), angle_slot, None if row[2] is None else str(row[2]))

    def create_job_and_reservation(
        self, batch_id: str, job_id: str, candidate: AllocationCandidate
    ) -> JobReservation:
        if not isinstance(candidate.angle_slot, str) or not candidate.angle_slot.strip():
            raise ValueError('angle_slot must be a non-empty string')
        if not isinstance(candidate.candidate_ref, str) or not candidate.candidate_ref.strip():
            raise ValueError('candidate_ref must be a non-empty string')
        source_set_ref = candidate.source_set_ref
        if source_set_ref is not None and (not isinstance(source_set_ref, str) or not source_set_ref.strip()):
            raise ValueError('source_set_ref must be None or a non-empty string')
        snapshot_ref = _ANGLE_PREFIX + candidate.angle_slot
        self._connection.execute(
            "INSERT INTO controlplane.cp_video_jobs "
            "(job_id, batch_id, workspace_id, status, snapshot_ref, revision) "
            "VALUES (%s, %s, %s, 'CREATED', %s, 1)",
            (job_id, batch_id, self._workspace_id, snapshot_ref),
        )
        reservation_id = str(uuid.uuid4())
        self._connection.execute(
            "INSERT INTO controlplane.cp_batch_capacity_reservations "
            "(reservation_id, workspace_id, batch_id, job_id, state) "
            "VALUES (%s, %s, %s, %s, 'ACTIVE')",
            (reservation_id, self._workspace_id, batch_id, job_id),
        )
        self._connection.execute(
            'INSERT INTO controlplane.cp_job_candidates '
            '(workspace_id, job_id, batch_id, candidate_ref, source_set_ref) '
            'VALUES (%s, %s, %s, %s, %s)',
            (self._workspace_id, job_id, batch_id, candidate.candidate_ref, source_set_ref),
        )
        return JobReservation(batch_id, job_id, reservation_id, candidate.angle_slot)


__all__ = ['PostgresAllocationStore']