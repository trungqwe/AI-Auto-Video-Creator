"""Data contracts for M1-P2 Temporal Proof."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class WorkflowStartPayload(BaseModel):
    workspace_id: str
    topic_id: str
    run_epoch: int
    worker_generation: int = 1
    input_data: Dict[str, Any] = Field(default_factory=dict)

class ActivityInputPayload(BaseModel):
    workspace_id: str
    operation_id: str
    idempotency_key: str
    payload_fingerprint: str
    worker_generation: int = 1
    action_type: str = "RENDER"
    payload: Dict[str, Any] = Field(default_factory=dict)

class ActivityOutputPayload(BaseModel):
    status: str  # SUCCESS, STALE_GENERATION, UNKNOWN_OUTCOME, RECONCILED
    receipt_id: str
    operation_id: str
    result_ref: str
    execution_epoch: int
    is_duplicate: bool = False
