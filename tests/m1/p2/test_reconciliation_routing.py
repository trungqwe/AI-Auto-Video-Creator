"""TST-M1-P2-006: Non-retryable unknown external outcome reconciliation routing proof."""
import pytest
from datetime import timedelta
from temporalio import workflow
from temporalio.client import Client
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError
from temporalio.worker import Worker
from m1proof.temporal_contracts import ActivityInputPayload, ActivityOutputPayload
from m1proof.temporal_activities import (
    execute_stage_one_activity,
    reconcile_external_outcome_activity,
    activity_store,
)

@workflow.defn
class ReconciliationRoutingWorkflow:
    @workflow.run
    async def run(self, operation_id: str) -> dict[str, str]:
        try:
            act_res = await workflow.execute_activity(
                execute_stage_one_activity,
                ActivityInputPayload(
                    workspace_id="ws-p2-006",
                    operation_id=operation_id,
                    idempotency_key=f"idem-{operation_id}",
                    payload_fingerprint="fp6",
                ),
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=RetryPolicy(
                    non_retryable_error_types=["UnknownExternalOutcomeError"],
                    maximum_attempts=2,
                ),
            )
            return {"status": act_res.status, "path": "DIRECT"}
        except ActivityError as err:
            cause = err.cause
            if isinstance(cause, ApplicationError) and cause.type == "UnknownExternalOutcomeError":
                # Định tuyến an toàn vào luồng đối soát (Reconciliation Path)
                rec_res = await workflow.execute_activity(
                    reconcile_external_outcome_activity,
                    ActivityInputPayload(
                        workspace_id="ws-p2-006",
                        operation_id=operation_id,
                        idempotency_key=f"reconcile-{operation_id}",
                        payload_fingerprint="fp6-rec",
                    ),
                    start_to_close_timeout=timedelta(seconds=5),
                )
                return {"status": rec_res.status, "path": "RECONCILED"}
            raise

@pytest.mark.asyncio
async def test_tst_m1_p2_006_unknown_outcome_routes_to_reconciliation(temporal_env):
    """TST-M1-P2-006:
    Khi gặp kết quả không xác định (UnknownExternalOutcomeError),
    workflow không retry mù mà chuyển sang đường đối soát (Reconciliation Path).
    """
    activity_store.reset()
    activity_store.injection_mode = "TRIGGER_UNKNOWN_OUTCOME"

    client: Client = temporal_env.client
    task_queue = "tst-p2-006-queue"

    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[ReconciliationRoutingWorkflow],
        activities=[
            execute_stage_one_activity,
            reconcile_external_outcome_activity,
        ],
    ):
        handle = await client.start_workflow(
            ReconciliationRoutingWorkflow.run,
            "op-unknown-001",
            id="wf-tst-m1-p2-006",
            task_queue=task_queue,
            execution_timeout=timedelta(seconds=10),
        )
        res = await handle.result()

        # Oracle: Kết quả phải qua luồng RECONCILED và gọi activity đối soát đúng 1 lần
        assert res["path"] == "RECONCILED"
        assert res["status"] == "RECONCILED"
        assert any(op.startswith("reconcile:op-unknown-001") for op in activity_store.executed_operations)
