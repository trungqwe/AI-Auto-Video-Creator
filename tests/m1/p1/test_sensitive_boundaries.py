import importlib
import sys
from pathlib import Path

import psycopg
import pytest


REPOSITORY_ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))
SCHEMA_PATH = REPOSITORY_ROOT / "sql" / "m1" / "p1_schema.sql"
DSN = "postgresql://postgres@127.0.0.1:55432/aiavc_m1"


def prepare_service():
    with psycopg.connect(DSN, autocommit=True) as connection:
        connection.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
        connection.execute("SELECT m1_p1_reset()")
    module = importlib.import_module("m1proof.contracts")
    service = module.ContractProofService(DSN)
    service.set_workspace_epoch(
        workspace_id="workspace-1", recovery_epoch="epoch-1", epoch_sequence=1
    )
    return module, service


def test_event_payload_rejects_secret_and_unknown_fields() -> None:
    module, service = prepare_service()
    base = dict(
        event_id="event-1",
        workspace_id="workspace-1",
        aggregate_id="aggregate-1",
        aggregate_revision=1,
        recovery_epoch="epoch-1",
    )
    for payload in ({"access_token": "canary"}, {"unapproved": "value"}):
        event = module.DomainEvent(**base, payload=payload)
        with pytest.raises(module.SensitiveDataRejected):
            service.consume_event("consumer-1", event)

    with psycopg.connect(DSN) as connection:
        assert connection.execute(
            "SELECT count(*) FROM consumer_event_receipts"
        ).fetchone()[0] == 0


def test_activity_and_external_payload_boundaries_reject_secrets() -> None:
    module, service = prepare_service()
    service.set_execution_fence(
        workspace_id="workspace-1",
        grant_id="grant-1",
        operation_key="operation-1",
        input_fingerprint="input-1",
        execution_generation=1,
        recovery_epoch="epoch-1",
    )
    result = module.ActivityCommit(
        result_id="result-1",
        workspace_id="workspace-1",
        grant_id="grant-1",
        operation_key="operation-1",
        input_fingerprint="input-1",
        execution_generation=1,
        recovery_epoch="epoch-1",
        payload={"password": "canary"},
    )
    request = module.ExternalOperationRequest(
        operation_key="operation-1",
        workspace_id="workspace-1",
        operation_type="proof_side_effect",
        recovery_epoch="epoch-1",
        input_payload={"client_secret": "canary"},
    )

    with pytest.raises(module.SensitiveDataRejected):
        service.commit_activity_result(result)
    with pytest.raises(module.SensitiveDataRejected):
        service.prepare_external_operation(request)

    with psycopg.connect(DSN) as connection:
        counts = connection.execute(
            """
            SELECT
              (SELECT count(*) FROM accepted_activity_results_v2),
              (SELECT count(*) FROM operation_receipts_v2)
            """
        ).fetchone()
    assert counts == (0, 0)


def test_reconciliation_output_rejects_secret_without_persistence() -> None:
    module, service = prepare_service()
    request = module.ExternalOperationRequest(
        operation_key="operation-1",
        workspace_id="workspace-1",
        operation_type="proof_side_effect",
        recovery_epoch="epoch-1",
        input_payload={"artifact_id": "artifact-1"},
    )
    service.prepare_external_operation(request)
    service.mark_operation_started("workspace-1", "operation-1", "epoch-1")
    service.mark_operation_outcome_unknown("workspace-1", "operation-1", "epoch-1")

    canary = "M1_RECONCILE_CANARY"
    with pytest.raises(module.SensitiveDataRejected) as failure:
        service.reconcile_external_operation(
            "workspace-1",
            "operation-1",
            "epoch-1",
            output_refs={"refresh_token": canary},
        )
    assert canary not in str(failure.value)
    with psycopg.connect(DSN) as connection:
        state, output_refs = connection.execute(
            """
            SELECT state, output_refs FROM operation_receipts_v2
             WHERE workspace_id = 'workspace-1' AND operation_key = 'operation-1'
            """
        ).fetchone()
    assert state == "outcome_unknown"
    assert canary not in str(output_refs)
