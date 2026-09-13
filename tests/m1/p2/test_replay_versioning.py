"""TST-M1-P2-005: Workflow replay versioning and non-deterministic change detection proof."""
import pytest
from datetime import timedelta
from temporalio import workflow
from temporalio.client import Client
from temporalio.worker import Worker, Replayer
from m1proof.temporal_activities import execute_stage_one_activity, activity_store
from m1proof.temporal_contracts import ActivityInputPayload

# Workflow V1 ban đầu
@workflow.defn(name="VersionedProofWorkflow")
class VersionedProofWorkflowV1:
    @workflow.run
    async def run(self) -> str:
        res = await workflow.execute_activity(
            execute_stage_one_activity,
            ActivityInputPayload(
                workspace_id="ws-v1",
                operation_id="op-v1",
                idempotency_key="key-v1",
                payload_fingerprint="fp-v1",
            ),
            start_to_close_timeout=timedelta(seconds=5),
        )
        return f"V1_RESULT_{res.status}"

# Workflow V2 tương thích có dùng workflow.patched
@workflow.defn(name="VersionedProofWorkflow")
class VersionedProofWorkflowV2Compatible:
    @workflow.run
    async def run(self) -> str:
        res = await workflow.execute_activity(
            execute_stage_one_activity,
            ActivityInputPayload(
                workspace_id="ws-v1",
                operation_id="op-v1",
                idempotency_key="key-v1",
                payload_fingerprint="fp-v1",
            ),
            start_to_close_timeout=timedelta(seconds=5),
        )
        if workflow.patched("v2-enhancement"):
            return f"V2_ENHANCED_{res.status}"
        return f"V1_RESULT_{res.status}"

# Workflow V2 KHÔNG tương thích (thay đổi lệnh gọi activity mà không qua patch)
@workflow.defn(name="VersionedProofWorkflow")
class VersionedProofWorkflowV2Incompatible:
    @workflow.run
    async def run(self) -> str:
        await workflow.sleep(timedelta(seconds=1))
        res = await workflow.execute_activity(
            execute_stage_one_activity,
            ActivityInputPayload(
                workspace_id="ws-v1",
                operation_id="op-v1",
                idempotency_key="key-v1",
                payload_fingerprint="fp-v1",
            ),
            start_to_close_timeout=timedelta(seconds=5),
        )
        return f"V2_INCOMPATIBLE_{res.status}"

@pytest.mark.asyncio
async def test_tst_m1_p2_005_replay_versioning_and_detection(temporal_env):
    """TST-M1-P2-005:
    1. Workflow history sinh ra bởi V1 có thể replay thành công bằng V2 tương thích (dùng workflow.patched).
    2. Workflow history sinh ra bởi V1 bị detector từ chối khi replay với V2 không tương thích.
    """
    activity_store.reset()
    client: Client = temporal_env.client
    task_queue = "tst-p2-005-queue"

    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[VersionedProofWorkflowV1],
        activities=[execute_stage_one_activity],
    ):
        handle = await client.start_workflow(
            VersionedProofWorkflowV1.run,
            id="wf-tst-m1-p2-005",
            task_queue=task_queue,
            execution_timeout=timedelta(seconds=10),
        )
        res = await handle.result()
        assert res == "V1_RESULT_SUCCESS"

    # Lấy toàn bộ event history của workflow vừa chạy
    history = await handle.fetch_history()

    # Case 1: Replay với V2 tương thích (có patch) -> Phải PASS
    replayer_compat = Replayer(workflows=[VersionedProofWorkflowV2Compatible])
    await replayer_compat.replay_workflow(history)

    # Case 2: Replay với V2 không tương thích -> Phải bị detector từ chối (NonDeterministic)
    replayer_incompat = Replayer(workflows=[VersionedProofWorkflowV2Incompatible])
    with pytest.raises(Exception) as exc_info:
        await replayer_incompat.replay_workflow(history)
    
    # Oracle: Phải bắt được lỗi replay nondeterminism
    assert "nondeterminism" in str(exc_info.value).lower() or "mismatch" in str(exc_info.value).lower()
