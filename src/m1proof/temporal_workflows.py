"""Temporal Workflows implementation for M1-P2 Proof."""
from __future__ import annotations
import re
from datetime import timedelta
from typing import Any, Dict
from temporalio import workflow
from temporalio.client import Client, WorkflowHandle
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError
from m1proof.temporal_contracts import WorkflowStartPayload, ActivityInputPayload, ActivityOutputPayload

with workflow.unsafe.imports_passed_through():
    from m1proof.temporal_activities import (
        execute_stage_one_activity,
        execute_desktop_render_activity,
        reconcile_external_outcome_activity,
    )

CANARY_PATTERNS = [
    re.compile(r"ghp_[0-9A-Za-z]{36}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AIza[0-9A-Za-z_-]{35}"),
]

def check_workflow_payload_safety(data: Any) -> None:
    """Verify input payload in workflow does not violate security or blob boundaries."""
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
                    "SECRET_BOUNDARY_VIOLATION: Canary secret detected in workflow input",
                    type="SecretViolationError",
                    non_retryable=True,
                )
    elif isinstance(data, dict):
        for k, v in data.items():
            check_workflow_payload_safety(k)
            check_workflow_payload_safety(v)
    elif isinstance(data, (list, tuple, set)):
        for item in data:
            check_workflow_payload_safety(item)

def validate_client_boundary_payload(payload: WorkflowStartPayload) -> None:
    """Validate at client submit boundary before payload is written into Temporal Server history."""
    def _inspect(val: Any) -> None:
        if isinstance(val, str):
            if len(val) > 10000:
                raise ValueError("BLOB_PAYLOAD_PROHIBITED: Raw binary blob is forbidden in Temporal payload")
            for pat in CANARY_PATTERNS:
                if pat.search(val):
                    raise ValueError("SECRET_BOUNDARY_VIOLATION: Canary secret detected in client submission")
        elif isinstance(val, dict):
            for k, v in val.items():
                _inspect(k)
                _inspect(v)
        elif isinstance(val, (list, tuple, set)):
            for item in val:
                _inspect(item)

    _inspect(payload.input_data)

async def start_safe_proof_workflow(
    client: Client,
    payload: WorkflowStartPayload,
    workflow_id: str,
    task_queue: str,
    execution_timeout: timedelta = timedelta(seconds=10),
) -> WorkflowHandle:
    """Client-side safe boundary gate preventing secrets or raw blobs from entering Temporal wire."""
    validate_client_boundary_payload(payload)
    return await client.start_workflow(
        M1ProofWorkflow.run,
        payload,
        id=workflow_id,
        task_queue=task_queue,
        execution_timeout=execution_timeout,
    )

@workflow.defn
class M1ChildProofWorkflow:
    @workflow.run
    async def run(self, should_fail: bool) -> str:
        if should_fail:
            raise ApplicationError(
                "Child workflow intentional failure",
                type="ChildFailure",
                non_retryable=True,
            )
        return "CHILD_SUCCESS"

@workflow.defn
class M1ProofWorkflow:
    def __init__(self):
        self.stage = "INIT"
        self.worker_online = False
        self.stage_executions: list[str] = []

    @workflow.signal
    def set_worker_online(self, online: bool) -> None:
        self.worker_online = online

    @workflow.query
    def get_current_stage(self) -> str:
        return self.stage

    @workflow.query
    def get_stage_executions(self) -> list[str]:
        return self.stage_executions

    @workflow.run
    async def run(self, payload: WorkflowStartPayload) -> Dict[str, Any]:
        # 1. Kiểm tra an toàn input payload ngay tại ranh giới workflow (defence-in-depth)
        check_workflow_payload_safety(payload.input_data)

        # 2. Stage 1: Initial Processing
        self.stage = "STAGE_1"
        self.stage_executions.append("STAGE_1")
        
        act1 = await workflow.execute_activity(
            execute_stage_one_activity,
            ActivityInputPayload(
                workspace_id=payload.workspace_id,
                operation_id=f"{payload.topic_id}-op1",
                idempotency_key=f"idem-{payload.topic_id}-1",
                payload_fingerprint="fp1",
                worker_generation=payload.worker_generation,
            ),
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        # 3. Stage 2: Desktop Processing & Offline worker handling
        if payload.input_data.get("require_desktop_online_signal"):
            self.stage = "WAITING_DESKTOP_ONLINE"
            self.stage_executions.append("WAITING_DESKTOP_ONLINE")
            await workflow.wait_condition(lambda: self.worker_online)

        self.stage = "STAGE_2_DESKTOP"
        self.stage_executions.append("STAGE_2_DESKTOP")
        
        act2 = await workflow.execute_activity(
            execute_desktop_render_activity,
            ActivityInputPayload(
                workspace_id=payload.workspace_id,
                operation_id=f"{payload.topic_id}-op2",
                idempotency_key=f"idem-{payload.topic_id}-2",
                payload_fingerprint="fp2",
                worker_generation=payload.worker_generation,
                payload=payload.input_data,
            ),
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        self.stage = "COMPLETED"
        self.stage_executions.append("COMPLETED")

        return {
            "status": "COMPLETED",
            "stage_1": act1.status,
            "stage_2": act2.status,
            "stage_executions": self.stage_executions,
        }
