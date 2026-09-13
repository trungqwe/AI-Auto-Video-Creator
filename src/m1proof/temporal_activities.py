"""Temporal Activities implementation for M1-P2 Proof."""
from __future__ import annotations
import re
from typing import Any, Dict
from temporalio import activity
from temporalio.exceptions import ApplicationError
from m1proof.temporal_contracts import ActivityInputPayload, ActivityOutputPayload

CANARY_PATTERNS = [
    re.compile(r"ghp_[0-9A-Za-z]{36}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AIza[0-9A-Za-z_-]{35}"),
]

class TemporalActivityProofStore:
    """In-memory store for activity test harness and fault injection."""
    def __init__(self):
        self.active_generation: int = 1
        self.executed_operations: list[str] = []
        self.committed_receipts: dict[str, ActivityOutputPayload] = {}
        self.injection_mode: str = "NONE"
        self._lost_ack_attempted: set[str] = set()

    def reset(self):
        self.active_generation = 1
        self.executed_operations.clear()
        self.committed_receipts.clear()
        self.injection_mode = "NONE"
        self._lost_ack_attempted.clear()

activity_store = TemporalActivityProofStore()

def validate_payload_safety(data: Any) -> None:
    """Validate that payload does not contain canary secrets or prohibited large blobs."""
    if isinstance(data, str):
        if len(data) > 10000:
            raise ApplicationError(
                "BLOB_PAYLOAD_PROHIBITED: Raw binary blob is forbidden in Temporal payload",
                type="BlobViolationError",
                non_retryable=True,
            )
        for pat in CANARY_PATTERNS:
            if pat.search(data):
                raise ApplicationError(
                    "SECRET_BOUNDARY_VIOLATION: Canary secret detected in activity payload",
                    type="SecretViolationError",
                    non_retryable=True,
                )
    elif isinstance(data, dict):
        for k, v in data.items():
            validate_payload_safety(k)
            validate_payload_safety(v)
    elif isinstance(data, (list, tuple, set)):
        for item in data:
            validate_payload_safety(item)

@activity.defn
async def execute_stage_one_activity(inp: ActivityInputPayload) -> ActivityOutputPayload:
    """Stage one activity with validation, generation fence and fault injection."""
    validate_payload_safety(inp.payload)

    if inp.worker_generation < activity_store.active_generation:
        raise ApplicationError(
            f"STALE_GENERATION: worker generation {inp.worker_generation} < active {activity_store.active_generation}",
            type="StaleGenerationError",
            non_retryable=True,
        )

    if activity_store.injection_mode == "TRIGGER_UNKNOWN_OUTCOME":
        raise ApplicationError(
            "External provider timeout with unknown outcome",
            type="UnknownExternalOutcomeError",
            non_retryable=True,
        )

    activity_store.executed_operations.append(f"stage1:{inp.operation_id}")
    return ActivityOutputPayload(
        status="SUCCESS",
        receipt_id=f"rec-{inp.operation_id}",
        operation_id=inp.operation_id,
        result_ref="ref-stage1",
        execution_epoch=inp.worker_generation,
        is_duplicate=False,
    )

@activity.defn
async def execute_desktop_render_activity(inp: ActivityInputPayload) -> ActivityOutputPayload:
    """Stage two desktop render activity with receipt deduplication and lost-ACK simulation."""
    validate_payload_safety(inp.payload)

    if inp.worker_generation < activity_store.active_generation:
        raise ApplicationError(
            f"STALE_GENERATION: worker generation {inp.worker_generation} < active {activity_store.active_generation}",
            type="StaleGenerationError",
            non_retryable=True,
        )

    op_key = inp.idempotency_key

    # Kiểm tra receipt idempotency P1
    if op_key in activity_store.committed_receipts:
        cached = activity_store.committed_receipts[op_key]
        return ActivityOutputPayload(
            status=cached.status,
            receipt_id=cached.receipt_id,
            operation_id=cached.operation_id,
            result_ref=cached.result_ref,
            execution_epoch=cached.execution_epoch,
            is_duplicate=True,
        )

    # Thực hiện side effect (render)
    activity_store.executed_operations.append(f"desktop:{inp.operation_id}")
    receipt = ActivityOutputPayload(
        status="SUCCESS",
        receipt_id=f"rec-{inp.operation_id}",
        operation_id=inp.operation_id,
        result_ref="ref-desktop",
        execution_epoch=inp.worker_generation,
        is_duplicate=False,
    )
    activity_store.committed_receipts[op_key] = receipt

    # Giả lập Lost ACK: commit thành công vào DB nhưng kết nối mạng bị ngắt trước khi ACK về Temporal
    if (
        activity_store.injection_mode == "LOST_ACK_AFTER_COMMIT"
        and op_key not in activity_store._lost_ack_attempted
    ):
        activity_store._lost_ack_attempted.add(op_key)
        # Ném lỗi transient retryable để Temporal thử lại activity
        raise RuntimeError("Transient network drop: ACK lost after commit")

    return receipt

@activity.defn
async def reconcile_external_outcome_activity(inp: ActivityInputPayload) -> ActivityOutputPayload:
    """Reconcile unknown external outcome without repeating mutation."""
    validate_payload_safety(inp.payload)
    activity_store.executed_operations.append(f"reconcile:{inp.operation_id}")
    return ActivityOutputPayload(
        status="RECONCILED",
        receipt_id=f"rec-reconciled-{inp.operation_id}",
        operation_id=inp.operation_id,
        result_ref="ref-reconciled",
        execution_epoch=inp.worker_generation,
        is_duplicate=False,
    )
