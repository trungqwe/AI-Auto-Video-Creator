"""TST-M1-P2-002 & TST-M1-P2-003: Activity retry idempotency and worker generation fencing."""
import pytest
from datetime import timedelta
from temporalio.client import Client, WorkflowFailureError
from temporalio.worker import Worker
from m1proof.temporal_contracts import WorkflowStartPayload
from m1proof.temporal_workflows import M1ProofWorkflow
from m1proof.temporal_activities import (
    execute_stage_one_activity,
    execute_desktop_render_activity,
    reconcile_external_outcome_activity,
    activity_store,
)

def extract_full_error_text(exc: BaseException) -> str:
    parts = [str(exc), repr(exc)]
    curr = getattr(exc, "cause", None)
    visited = set()
    while curr and id(curr) not in visited:
        visited.add(id(curr))
        parts.extend([str(curr), repr(curr)])
        curr = getattr(curr, "cause", None)
    return " ".join(parts)

@pytest.mark.asyncio
async def test_tst_m1_p2_002_activity_retry_lost_ack_uses_p1_receipt(temporal_env):
    """TST-M1-P2-002:
    Lần gọi activity đầu commit thành công nhưng giả lập lost-ACK mạng;
    Temporal retry lại activity; activity lần 2 tìm thấy receipt P1 cũ,
    không nhân đôi side effect render và trả kết quả duplicate an toàn.
    """
    activity_store.reset()
    activity_store.injection_mode = "LOST_ACK_AFTER_COMMIT"

    client: Client = temporal_env.client
    task_queue = "tst-p2-002-queue"

    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[M1ProofWorkflow],
        activities=[
            execute_stage_one_activity,
            execute_desktop_render_activity,
            reconcile_external_outcome_activity,
        ],
    ):
        handle = await client.start_workflow(
            M1ProofWorkflow.run,
            WorkflowStartPayload(
                workspace_id="ws-p2-002",
                topic_id="topic-002",
                run_epoch=1,
                worker_generation=1,
                input_data={"test_mode": "idempotency_lost_ack"},
            ),
            id="wf-tst-m1-p2-002",
            task_queue=task_queue,
            execution_timeout=timedelta(seconds=10),
        )

        result = await handle.result()
        assert result["status"] == "COMPLETED"

        # Oracle: desktop activity được commit đúng 1 lần (dù có retry sau lost ACK)
        desktop_ops = [op for op in activity_store.executed_operations if op.startswith("desktop:")]
        assert len(desktop_ops) == 1, f"Expected exactly 1 side effect but got {desktop_ops}"


@pytest.mark.asyncio
async def test_tst_m1_p2_003_stale_worker_generation_rejected(temporal_env):
    """TST-M1-P2-003:
    Worker mang generation cũ (thấp hơn generation đang active của hệ thống)
    bị chặn với lỗi StaleGeneration và workflow fail an toàn (hoặc từ chối mutation).
    """
    activity_store.reset()
    activity_store.active_generation = 2  # Hệ thống đã nâng lên generation 2

    client: Client = temporal_env.client
    task_queue = "tst-p2-003-queue"

    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[M1ProofWorkflow],
        activities=[
            execute_stage_one_activity,
            execute_desktop_render_activity,
            reconcile_external_outcome_activity,
        ],
    ):
        handle = await client.start_workflow(
            M1ProofWorkflow.run,
            WorkflowStartPayload(
                workspace_id="ws-p2-003",
                topic_id="topic-003",
                run_epoch=1,
                worker_generation=1,  # Cố tình gửi generation 1 (stale)
                input_data={"test_mode": "stale_generation"},
            ),
            id="wf-tst-m1-p2-003",
            task_queue=task_queue,
            execution_timeout=timedelta(seconds=10),
        )

        with pytest.raises(WorkflowFailureError) as exc_info:
            await handle.result()

        # Oracle: Lỗi phải chỉ ra STALE_GENERATION trong chuỗi lỗi nguyên nhân
        full_error = extract_full_error_text(exc_info.value)
        assert "STALE_GENERATION" in full_error
