"""TST-M1-P2-007: Temporal payload boundary, secret detection and blob prohibition proof."""
import pytest
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from m1proof.temporal_contracts import WorkflowStartPayload
from m1proof.temporal_workflows import (
    M1ProofWorkflow,
    start_safe_proof_workflow,
)
from m1proof.temporal_activities import (
    execute_stage_one_activity,
    execute_desktop_render_activity,
    reconcile_external_outcome_activity,
    activity_store,
)

CANARY_SECRET = "ghp_123456789012345678901234567890123456"
FORBIDDEN_LARGE_BLOB = "B" * 50000  # Giả lập payload blob video/ảnh thô cấm đưa vào workflow

@pytest.mark.asyncio
async def test_tst_m1_p2_007_payload_boundary_blocks_secrets_and_large_blobs(temporal_env):
    """TST-M1-P2-007:
    Payload chứa secret token hoặc binary blob lớn bị từ chối ngay tại ranh giới;
    Không để secret lọt vào Temporal event history.
    """
    activity_store.reset()
    client: Client = temporal_env.client
    task_queue = "tst-p2-007-queue"

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
        # Case 1: Thử submit canary secret qua client boundary gate
        with pytest.raises(ValueError) as exc_secret:
            await start_safe_proof_workflow(
                client,
                WorkflowStartPayload(
                    workspace_id="ws-p2-007",
                    topic_id="topic-secret",
                    run_epoch=1,
                    worker_generation=1,
                    input_data={"api_token": CANARY_SECRET},
                ),
                workflow_id="wf-tst-m1-p2-007-secret",
                task_queue=task_queue,
            )

        # Oracle 1: Bị chặn ngay tại ranh giới với thông báo rõ ràng
        assert "SECRET_BOUNDARY_VIOLATION" in str(exc_secret.value)

        # Case 2: Thử submit raw large blob qua client boundary gate
        with pytest.raises(ValueError) as exc_blob:
            await start_safe_proof_workflow(
                client,
                WorkflowStartPayload(
                    workspace_id="ws-p2-007",
                    topic_id="topic-blob",
                    run_epoch=1,
                    worker_generation=1,
                    input_data={"raw_media_bytes": FORBIDDEN_LARGE_BLOB},
                ),
                workflow_id="wf-tst-m1-p2-007-blob",
                task_queue=task_queue,
            )

        # Oracle 2: Bị chặn ngay tại ranh giới không cho đẩy blob vào Temporal
        assert "BLOB_PAYLOAD_PROHIBITED" in str(exc_blob.value)

        # Case 3: Chạy một workflow hợp lệ và xác nhận history lưu trữ hoàn toàn sạch
        valid_handle = await start_safe_proof_workflow(
            client,
            WorkflowStartPayload(
                workspace_id="ws-p2-007",
                topic_id="topic-clean",
                run_epoch=1,
                worker_generation=1,
                input_data={"safe_ref": "ref://artifact/clean-123"},
            ),
            workflow_id="wf-tst-m1-p2-007-clean",
            task_queue=task_queue,
        )
        res = await valid_handle.result()
        assert res["status"] == "COMPLETED"

        history = await valid_handle.fetch_history()
        history_str = str(history)
        assert CANARY_SECRET not in history_str, "Secret leaked into history!"
        assert FORBIDDEN_LARGE_BLOB not in history_str, "Large blob leaked into history!"
