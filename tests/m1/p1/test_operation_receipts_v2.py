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
    for workspace in ("workspace-1", "workspace-2"):
        service.set_workspace_epoch(
            workspace_id=workspace, recovery_epoch="epoch-1", epoch_sequence=1
        )
    return module, service


def request(module, workspace="workspace-1", operation_type="upload"):
    return module.ExternalOperationRequest(
        operation_key="same-key",
        workspace_id=workspace,
        operation_type=operation_type,
        recovery_epoch="epoch-1",
        input_payload={"artifact_id": "artifact-1"},
    )


def test_operation_key_is_scoped_by_workspace_and_type_is_fingerprinted() -> None:
    module, service = setup()
    one = service.prepare_external_operation(request(module, "workspace-1"))
    two = service.prepare_external_operation(request(module, "workspace-2"))
    assert one.receipt_id != two.receipt_id

    with pytest.raises(module.IdempotencyConflict):
        service.prepare_external_operation(request(module, "workspace-1", "delete"))


def test_external_state_machine_rejects_forbidden_transitions() -> None:
    module, service = setup()
    req = request(module)
    service.prepare_external_operation(req)
    service.mark_operation_started("workspace-1", "same-key", "epoch-1")
    service.mark_operation_outcome_unknown("workspace-1", "same-key", "epoch-1")
    service.reconcile_external_operation(
        "workspace-1", "same-key", "epoch-1", output_refs={"external_ref": "ref-1"}
    )

    with pytest.raises(module.ContractProofError, match="INVALID_OPERATION_TRANSITION"):
        service.mark_operation_started("workspace-1", "same-key", "epoch-1")


def test_receipt_from_old_epoch_is_not_reused_as_current() -> None:
    module, service = setup()
    service.prepare_external_operation(request(module))
    service.set_workspace_epoch(
        workspace_id="workspace-1", recovery_epoch="epoch-2", epoch_sequence=2
    )
    current = request(module).model_copy(update={"recovery_epoch": "epoch-2"})

    with pytest.raises(module.StaleExecution, match="STALE_OPERATION_EPOCH"):
        service.prepare_external_operation(current)
