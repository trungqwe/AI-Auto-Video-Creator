"""TST-M1-P2-004: Child workflow failure isolation proof."""
import pytest
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.client import Client
from temporalio.worker import Worker
from m1proof.temporal_workflows import M1ChildProofWorkflow

@workflow.defn
class M1ParentWithChildIsolationWorkflow:
    """Parent workflow điều phối 2 child workflows song song với policy cô lập lỗi."""
    @workflow.run
    async def run(self) -> dict[str, str]:
        # Khởi chạy Child A (thành công) và Child B (cố tình fail)
        child_a_fut = workflow.execute_child_workflow(
            M1ChildProofWorkflow.run,
            False,
            id="child-a-workflow",
            execution_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
        child_b_fut = workflow.execute_child_workflow(
            M1ChildProofWorkflow.run,
            True,  # Cố tình fail
            id="child-b-workflow",
            execution_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )

        results = {}
        # Chờ Child A
        try:
            results["child_a"] = await child_a_fut
        except Exception as e:
            results["child_a"] = f"FAILED: {e}"

        # Chờ Child B với isolation policy (bắt exception, không để crash parent)
        try:
            results["child_b"] = await child_b_fut
        except Exception:
            results["child_b"] = "FAILED_ISOLATED"

        return results

@pytest.mark.asyncio
async def test_tst_m1_p2_004_child_failure_isolation(temporal_env):
    """TST-M1-P2-004:
    Child B failure bị cô lập, sibling Child A vẫn thành công và Parent hoàn thành đúng policy.
    """
    client: Client = temporal_env.client
    task_queue = "tst-p2-004-queue"

    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[M1ParentWithChildIsolationWorkflow, M1ChildProofWorkflow],
    ):
        handle = await client.start_workflow(
            M1ParentWithChildIsolationWorkflow.run,
            id="wf-tst-m1-p2-004",
            task_queue=task_queue,
            execution_timeout=timedelta(seconds=10),
        )

        result = await handle.result()
        # Oracle: Child A thành công, Child B bị cô lập mà không làm crash parent workflow
        assert result["child_a"] == "CHILD_SUCCESS"
        assert result["child_b"] == "FAILED_ISOLATED"
