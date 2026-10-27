"""PW-A1: PlanCollectionCycle (CT-SRC-004, CONV-A-06, FR-COL-001): mỗi nguồn tối đa một lượt định kỳ mỗi business_date.

business_date tính theo múi giờ Asia/Ho_Chi_Minh từ đồng hồ tiêm được; created_at của mark lưu UTC. Tier được áp bằng tier_order (Tier ngoài danh sách bị chặn và không tiêu mark); thứ tự đầu ra là (thứ hạng Tier, source_id) của rank_eligible_sources. Mark ghi vào cp_source_cycle_marks trên chính kết nối của UoW và chỉ commit cùng một lần với kế hoạch. collection_run_ref của mark là cycle_ref theo operation_key: gọi lại cùng operation_key nhận lại đúng các ref cũ, operation_key khác trong cùng ngày không nhận lại nguồn đã có mark.
"""
from __future__ import annotations

import dataclasses
import datetime
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from controlplane.application.orchestration.workflows.activities import (
    INVALID_ACTIVITY_REQUEST,
    MISSING_EXECUTION_GRANT,
    ActivityRejected,
)
from source_ingestion.application.source_eligibility import (
    EligibilityReason,
    SourceEligibility,
    rank_eligible_sources,
)
from source_ingestion.persistence._sql import ConnectionProvider, uuid_text

ACTIVITY_NAME = 'PlanCollectionCycle'
REF_TYPE_SOURCE = 'collection_source'
DEFAULT_TIMEZONE = 'Asia/Ho_Chi_Minh'
DEFAULT_TOPIC = 'news'
SUCCEEDED = 'succeeded'


@dataclasses.dataclass(frozen=True)
class CyclePlan:
    cycle_ref: str
    business_date: datetime.date
    due: tuple[SourceEligibility, ...]
    skipped: tuple[SourceEligibility, ...]


class CycleMarkStore(Protocol):
    def claim(
        self,
        workspace_id: str,
        source_id: str,
        cycle_day: datetime.date,
        cycle_ref: str,
        at: datetime.datetime,
    ) -> bool:
        """True khi mark vừa được ghi hoặc đã thuộc đúng cycle_ref này; False khi nguồn đã có mark của cycle khác trong ngày."""
        ...


class PostgresCycleMarkStore:
    """cp_source_cycle_marks trên đúng kết nối của UoW đang mở, nên mark nằm trong giao dịch của kế hoạch."""

    def __init__(self, connection: ConnectionProvider) -> None:
        self._connection = connection

    @classmethod
    def for_uow(cls, uow: Any) -> PostgresCycleMarkStore:
        # PostgresSourceIngestionUnitOfWork chưa có kho marks và persistence nằm ngoài owned paths của PW-A1:
        # dùng đúng provider kết nối mà các repository của UoW đang dùng.
        return cls(uow._active_connection)

    def claim(
        self,
        workspace_id: str,
        source_id: str,
        cycle_day: datetime.date,
        cycle_ref: str,
        at: datetime.datetime,
    ) -> bool:
        conn = self._connection()
        ws = uuid_text(workspace_id)
        inserted = conn.execute(
            'INSERT INTO controlplane.cp_source_cycle_marks (workspace_id, source_id, cycle_day, collection_run_ref, created_at) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (workspace_id, source_id, cycle_day) DO NOTHING RETURNING source_id',
            (ws, source_id, cycle_day, cycle_ref, at.astimezone(datetime.timezone.utc)),
        ).fetchone()
        if inserted is not None:
            return True
        stored = conn.execute(
            'SELECT collection_run_ref FROM controlplane.cp_source_cycle_marks WHERE workspace_id = %s AND source_id = %s AND cycle_day = %s',
            (ws, source_id, cycle_day),
        ).fetchone()
        return stored is not None and stored[0] == cycle_ref


class PlanCollectionCycle:
    def __init__(
        self,
        *,
        uow_factory: Callable[[], Any],
        workspace_id: str,
        tier_order: Sequence[str],
        topic: str = DEFAULT_TOPIC,
        timezone_name: str = DEFAULT_TIMEZONE,
        clock: Callable[[], datetime.datetime] | None = None,
        marks_for: Callable[[Any], CycleMarkStore] = PostgresCycleMarkStore.for_uow,
    ) -> None:
        self._uow_factory = uow_factory
        self._workspace_id = uuid_text(workspace_id)
        self._tier_order = tuple(tier_order)
        self._topic = topic
        self._zone = ZoneInfo(timezone_name)
        self._clock = clock if clock is not None else lambda: datetime.datetime.now(datetime.timezone.utc)
        self._marks_for = marks_for

    def business_date(self, at: datetime.datetime) -> datetime.date:
        if not isinstance(at, datetime.datetime) or at.tzinfo is None:
            raise ValueError('clock must return a timezone-aware datetime')
        return at.astimezone(self._zone).date()

    def plan(self, *, cycle_key: str) -> CyclePlan:
        if not isinstance(cycle_key, str) or not cycle_key.strip():
            raise ValueError('cycle_key must be a non-empty string')
        at = self._clock()
        business_date = self.business_date(at)
        cycle_ref = 'cycle:' + cycle_key
        with self._uow_factory() as uow:
            ranked = rank_eligible_sources(
                sources=uow.sources.list_sources(self._workspace_id),
                existing_runs=(),
                workspace_id=self._workspace_id,
                topic=self._topic,
                business_date=business_date,
                tier_order=self._tier_order,
            )
            marks = self._marks_for(uow)
            due: list[SourceEligibility] = []
            skipped = list(ranked.skipped)
            for entry in ranked.selected:
                if marks.claim(self._workspace_id, entry.source_id, business_date, cycle_ref, at):
                    due.append(entry)
                else:
                    skipped.append(
                        dataclasses.replace(entry, selected=False, reason=EligibilityReason.PERIODIC_RUN_EXISTS)
                    )
            uow.commit()
        return CyclePlan(cycle_ref, business_date, tuple(due), tuple(skipped))

    def __call__(self, request: Mapping[str, Any], claims: Any) -> dict[str, Any]:
        operation_key = request.get('operation_key')
        if not isinstance(operation_key, str) or not operation_key.strip():
            raise ActivityRejected(INVALID_ACTIVITY_REQUEST)
        plan = self.plan(cycle_key=operation_key)
        return {
            'disposition': SUCCEEDED,
            'output_refs': [{'ref_type': REF_TYPE_SOURCE, 'ref_id': entry.source_id} for entry in plan.due],
            'metrics': {
                'business_date': plan.business_date.isoformat(),
                'cycle_ref': plan.cycle_ref,
                'selected': len(plan.due),
                'skipped': len(plan.skipped),
            },
        }


def plan_collection_cycle_handler(
    service: PlanCollectionCycle, clock: Callable[[], datetime.datetime]
) -> Callable[[Mapping[str, Any], Any], dict[str, Any]]:
    def handler(request: Mapping[str, Any], claims: Any) -> dict[str, Any]:
        if claims is None:
            raise ActivityRejected(MISSING_EXECUTION_GRANT)
        outcome = service(request, claims)
        completed_at = clock().astimezone(datetime.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
        return {
            'stage_run_id': claims.stage_run_id,
            'grant_id': claims.grant_id,
            'execution_generation': claims.execution_generation,
            'recovery_epoch': claims.recovery_epoch,
            'disposition': outcome['disposition'],
            'output_refs': list(outcome['output_refs']),
            'completed_at': completed_at,
            'metrics': outcome['metrics'],
        }

    return handler


__all__ = [
    'ACTIVITY_NAME',
    'REF_TYPE_SOURCE',
    'CycleMarkStore',
    'CyclePlan',
    'PlanCollectionCycle',
    'PostgresCycleMarkStore',
    'plan_collection_cycle_handler',
]
