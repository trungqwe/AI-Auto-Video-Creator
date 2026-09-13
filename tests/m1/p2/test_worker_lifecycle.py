"""TST-M1-P2-001: Workflow lifecycle, offline desktop waiting and resume proof."""
import asyncio
import pytest
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from m1proof.temporal_contracts import WorkflowStartPayload
from m1proof.temporal_workflows import M1ProofWorkflow
from m1proof.temporal_activities import (
    execute_stage_one_activity,
    execute_desktop_render_activity,
    reconcile_external_outcome_activity,
    activity_store,
)

@pytest.mark.asyncio
async def test_tst_m1_p2_001_desktop_worker_offline_and_resume(temporal_env):
    """TST-M1-P2-001:
    Workflow chờ khi desktop worker offline và resume đúng stage khi online lại,
    không restart từ đầu (Stage 1 chỉ thực hiện đúng 1 lần).
    """
    activity_store.reset()
    client: Client = temporal_env.client
    task_queue = "tst-p2-001-queue"

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
                workspace_id="ws-p2-001",
                topic_id="topic-001",
                run_epoch=1,
                worker_generation=1,
                input_data={"require_desktop_online_signal": True},
            ),
            id="wf-tst-m1-p2-001",
            task_queue=task_queue,
            execution_timeout=timedelta(seconds=10),
        )

        # Chờ workflow chuyển sang trạng thái chờ Desktop
        # Oracle mong đợi: Workflow phải tạm dừng ở WAITING_DESKTOP_ONLINE
        stage = None
        for _ in range(10):
            stage = await handle.query(M1ProofWorkflow.get_current_stage)
            if stage == "WAITING_DESKTOP_ONLINE":
                break
            await asyncio.sleep(0.1)

        assert stage == "WAITING_DESKTOP_ONLINE", f"Expected WAITING_DESKTOP_ONLINE but got {stage}"

        # Xác nhận Stage 1 đã xong
        executions_before = await handle.query(M1ProofWorkflow.get_stage_executions)
        assert executions_before == ["STAGE_1", "WAITING_DESKTOP_ONLINE"]

        # Gửi signal báo Desktop Worker đã Online
        await handle.signal(M1ProofWorkflow.set_worker_online, True)

        # Chờ hoàn thành
        result = await handle.result()
        assert result["status"] == "COMPLETED"

        # Oracle quan trọng: Stage 1 chỉ chạy 1 lần, không bị restart lại từ đầu khi resume
        executions_after = await handle.query(M1ProofWorkflow.get_stage_executions)
        assert executions_after == ["STAGE_1", "WAITING_DESKTOP_ONLINE", "STAGE_2_DESKTOP", "COMPLETED"]
        assert executions_after.count("STAGE_1") == 1
