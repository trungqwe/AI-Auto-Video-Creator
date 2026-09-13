import importlib
import sys
from pathlib import Path

import psycopg
import pytest


ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "src"))
SCHEMA = ROOT / "sql" / "m1" / "p1_schema.sql"
DSN = "postgresql://postgres@127.0.0.1:55432/aiavc_m1"


def setup():
    with psycopg.connect(DSN, autocommit=True) as connection:
        connection.execute(SCHEMA.read_text(encoding="utf-8"))
        connection.execute("SELECT m1_p1_reset()")
    module = importlib.import_module("m1proof.contracts")
    service = module.ContractProofService(DSN)
    service.set_workspace_epoch(
        workspace_id="workspace-1", recovery_epoch="epoch-1", epoch_sequence=1
    )
    service.set_execution_fence(
        workspace_id="workspace-1",
        grant_id="grant-1",
        operation_key="operation-1",
        input_fingerprint="input-1",
        execution_generation=1,
        recovery_epoch="epoch-1",
    )
    return module, service


def result(module, result_id="result-1", operation_key="operation-1", value="ok"):
    return module.ActivityCommit(
        result_id=result_id,
        workspace_id="workspace-1",
        grant_id="grant-1",
        operation_key=operation_key,
        input_fingerprint="input-1",
        execution_generation=1,
        recovery_epoch="epoch-1",
        payload={"result": value},
    )


def test_activity_result_is_idempotent_by_operation_and_bound_to_input() -> None:
    module, service = setup()
    first = service.commit_activity_result(result(module))
    duplicate = service.commit_activity_result(result(module, result_id="result-2"))
    assert first.disposition == "accepted"
    assert duplicate.disposition == "duplicate"
    assert duplicate.receipt_id == first.receipt_id

    with pytest.raises(module.IdempotencyConflict):
        service.commit_activity_result(result(module, value="changed"))
    with pytest.raises(module.StaleExecution, match="ACTIVITY_BINDING_MISMATCH"):
        service.commit_activity_result(result(module, operation_key="other"))


def test_grant_cannot_rebind_at_same_generation_and_operation_input_is_stable() -> None:
    module, service = setup()
    service.commit_activity_result(result(module))

    with pytest.raises(module.StaleExecution, match="ACTIVITY_GRANT_CONFLICT"):
        service.set_execution_fence(
            workspace_id="workspace-1",
            grant_id="grant-1",
            operation_key="operation-2",
            input_fingerprint="input-2",
            execution_generation=1,
            recovery_epoch="epoch-1",
        )

    service.set_execution_fence(
        workspace_id="workspace-1",
        grant_id="grant-1",
        operation_key="operation-1",
        input_fingerprint="input-2",
        execution_generation=2,
        recovery_epoch="epoch-1",
    )
    changed_input = result(module).model_copy(
        update={"result_id": "result-2", "input_fingerprint": "input-2", "execution_generation": 2}
    )
    with pytest.raises(module.IdempotencyConflict, match="ACTIVITY_INPUT_CONFLICT"):
        service.commit_activity_result(changed_input)
