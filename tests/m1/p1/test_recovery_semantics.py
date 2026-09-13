import importlib
import sys
from pathlib import Path

import psycopg
import pytest


REPOSITORY_ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

SCHEMA_PATH = REPOSITORY_ROOT / "sql" / "m1" / "p1_schema.sql"
DSN = "postgresql://postgres@127.0.0.1:55432/aiavc_m1"


def prepare_database() -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with psycopg.connect(DSN, autocommit=True) as connection:
        connection.execute(schema)
        connection.execute("SELECT m1_p1_reset()")


def load_contract_module():
    return importlib.import_module("m1proof.contracts")


def require_api(module, *names: str) -> None:
    missing = [name for name in names if not hasattr(module, name)]
    assert not missing, f"P1 recovery API is not implemented: {', '.join(missing)}"


def make_mutation(module, *, key: str, payload: dict[str, object] | None = None):
    return module.MutationCommand(
        command_id=f"command-{key}",
        idempotency_key=key,
        workspace_id="workspace-1",
        aggregate_id=f"aggregate-{key}",
        expected_revision=0,
        recovery_epoch="epoch-2",
        execution_generation=2,
        payload=payload or {"value": "safe"},
    )


def test_duplicate_and_reordered_events_do_not_repeat_projection_side_effect() -> None:
    prepare_database()
    module = load_contract_module()
    require_api(module, "DomainEvent", "EventGap")
    service = module.ContractProofService(DSN)

    event_1 = module.DomainEvent(
        event_id="event-1",
        workspace_id="workspace-1",
        aggregate_id="aggregate-events",
        aggregate_revision=1,
        payload={"value": "one"},
    )
    event_2 = event_1.model_copy(
        update={"event_id": "event-2", "aggregate_revision": 2, "payload": {"value": "two"}}
    )
    event_3 = event_1.model_copy(
        update={"event_id": "event-3", "aggregate_revision": 3, "payload": {"value": "three"}}
    )

    assert service.consume_event("consumer-1", event_1) is True
    assert service.consume_event("consumer-1", event_1) is False
    with pytest.raises(module.EventGap, match="EVENT_REVISION_GAP"):
        service.consume_event("consumer-1", event_3)
    assert service.consume_event("consumer-1", event_2) is True
    assert service.consume_event("consumer-1", event_1) is False

    with psycopg.connect(DSN) as connection:
        revision, apply_count = connection.execute(
            """
            SELECT aggregate_revision, apply_count
              FROM consumer_projections
             WHERE consumer_id = 'consumer-1'
               AND workspace_id = 'workspace-1'
               AND aggregate_id = 'aggregate-events'
            """
        ).fetchone()
    assert (revision, apply_count) == (2, 2)


def test_lost_ack_after_commit_returns_existing_receipt() -> None:
    prepare_database()
    module = load_contract_module()
    require_api(module, "OutcomeUnknown")
    service = module.ContractProofService(DSN)
    command = make_mutation(module, key="lost-ack")

    with pytest.raises(module.OutcomeUnknown) as failure:
        service.execute_mutation(command, inject_failure="after_commit_before_ack")

    restarted_service = module.ContractProofService(DSN)
    duplicate = restarted_service.execute_mutation(command)
    assert duplicate.disposition == "duplicate"
    assert duplicate.receipt_id == failure.value.receipt_id
    with psycopg.connect(DSN) as connection:
        counts = connection.execute(
            """
            SELECT
                (SELECT count(*) FROM proof_aggregates),
                (SELECT count(*) FROM command_receipts),
                (SELECT count(*) FROM outbox_events)
            """
        ).fetchone()
    assert counts == (1, 1, 1)


def test_stale_generation_or_recovery_epoch_cannot_commit_result() -> None:
    prepare_database()
    module = load_contract_module()
    require_api(module, "ActivityCommit", "StaleExecution")
    service = module.ContractProofService(DSN)
    service.set_execution_fence(
        workspace_id="workspace-1",
        grant_id="grant-1",
        execution_generation=4,
        recovery_epoch="epoch-current",
    )

    stale_generation = module.ActivityCommit(
        result_id="result-old-generation",
        workspace_id="workspace-1",
        grant_id="grant-1",
        execution_generation=3,
        recovery_epoch="epoch-current",
        payload={"result": "late"},
    )
    stale_epoch = stale_generation.model_copy(
        update={"result_id": "result-old-epoch", "execution_generation": 4, "recovery_epoch": "epoch-old"}
    )

    with pytest.raises(module.StaleExecution, match="STALE_EXECUTION_GENERATION"):
        service.commit_activity_result(stale_generation)
    with pytest.raises(module.StaleExecution, match="STALE_RECOVERY_EPOCH"):
        service.commit_activity_result(stale_epoch)

    with psycopg.connect(DSN) as connection:
        assert connection.execute("SELECT count(*) FROM accepted_activity_results").fetchone()[0] == 0


def test_unknown_external_outcome_requires_reconciliation_before_retry() -> None:
    prepare_database()
    module = load_contract_module()
    require_api(module, "ExternalOperationRequest", "ReconciliationRequired")
    service = module.ContractProofService(DSN)
    request = module.ExternalOperationRequest(
        operation_key="external-operation-1",
        workspace_id="workspace-1",
        operation_type="proof_side_effect",
        recovery_epoch="epoch-2",
        input_payload={"artifact_id": "artifact-1"},
    )

    prepared = service.prepare_external_operation(request)
    service.mark_operation_started(request.operation_key)
    service.mark_operation_outcome_unknown(request.operation_key)

    with pytest.raises(module.ReconciliationRequired, match="RECONCILIATION_REQUIRED"):
        service.retry_external_operation(request)

    reconciled = service.reconcile_external_operation(
        request.operation_key,
        output_refs={"external_ref": "redacted-ref"},
    )
    repeated = service.retry_external_operation(request)
    assert reconciled.state == repeated.state == "succeeded"
    assert repeated.receipt_id == prepared.receipt_id
    assert repeated.attempt == 1


def test_sensitive_input_is_rejected_without_persistence_or_echo() -> None:
    prepare_database()
    module = load_contract_module()
    require_api(module, "SensitiveDataRejected")
    service = module.ContractProofService(DSN)
    canary = "M1_CANARY_VALUE_8D9C"
    sensitive_key = "access" + "_token"
    command = make_mutation(module, key="sensitive", payload={sensitive_key: canary})

    with pytest.raises(module.SensitiveDataRejected) as failure:
        service.execute_mutation(command)

    assert canary not in str(failure.value)
    with psycopg.connect(DSN) as connection:
        persisted = connection.execute(
            """
            SELECT concat_ws(' ',
                (SELECT string_agg(payload::text, ' ') FROM proof_aggregates),
                (SELECT string_agg(result::text, ' ') FROM command_receipts),
                (SELECT string_agg(payload::text, ' ') FROM outbox_events)
            )
            """
        ).fetchone()[0]
    assert canary not in (persisted or "")
