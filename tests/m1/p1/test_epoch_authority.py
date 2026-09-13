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
    with psycopg.connect(DSN, autocommit=True) as connection:
        connection.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
        connection.execute("SELECT m1_p1_reset()")


def test_stale_command_and_event_cannot_persist() -> None:
    prepare_database()
    module = importlib.import_module("m1proof.contracts")
    service = module.ContractProofService(DSN)
    service.set_workspace_epoch(
        workspace_id="workspace-1", recovery_epoch="epoch-2", epoch_sequence=2
    )

    command = module.MutationCommand(
        command_id="command-stale",
        idempotency_key="stale",
        workspace_id="workspace-1",
        aggregate_id="aggregate-1",
        expected_revision=0,
        recovery_epoch="epoch-1",
        execution_generation=1,
        payload={"value": "stale"},
    )
    event = module.DomainEvent(
        event_id="event-stale",
        workspace_id="workspace-1",
        aggregate_id="aggregate-1",
        aggregate_revision=1,
        recovery_epoch="epoch-1",
        payload={"value": "stale"},
    )

    with pytest.raises(module.StaleExecution, match="STALE_RECOVERY_EPOCH"):
        service.execute_mutation(command)
    with pytest.raises(module.StaleExecution, match="STALE_RECOVERY_EPOCH"):
        service.consume_event("consumer-1", event)

    with psycopg.connect(DSN) as connection:
        counts = connection.execute(
            """
            SELECT
                (SELECT count(*) FROM proof_aggregates),
                (SELECT count(*) FROM command_receipts),
                (SELECT count(*) FROM consumer_projections),
                (SELECT count(*) FROM consumer_event_receipts)
            """
        ).fetchone()
    assert counts == (0, 0, 0, 0)


def test_epoch_and_fence_cannot_move_backwards() -> None:
    prepare_database()
    module = importlib.import_module("m1proof.contracts")
    service = module.ContractProofService(DSN)
    service.set_workspace_epoch(
        workspace_id="workspace-1", recovery_epoch="epoch-2", epoch_sequence=2
    )
    service.set_execution_fence(
        workspace_id="workspace-1",
        grant_id="grant-1",
        operation_key="operation-1",
        input_fingerprint="input-1",
        execution_generation=4,
        recovery_epoch="epoch-2",
    )

    with pytest.raises(module.StaleExecution, match="STALE_EXECUTION_GENERATION"):
        service.set_execution_fence(
            workspace_id="workspace-1",
            grant_id="grant-1",
            operation_key="operation-1",
            input_fingerprint="input-1",
            execution_generation=3,
            recovery_epoch="epoch-2",
        )
    with pytest.raises(module.StaleExecution, match="STALE_RECOVERY_EPOCH"):
        service.set_execution_fence(
            workspace_id="workspace-1",
            grant_id="grant-1",
            operation_key="operation-1",
            input_fingerprint="input-1",
            execution_generation=5,
            recovery_epoch="epoch-1",
        )
    with pytest.raises(module.StaleExecution, match="STALE_EPOCH_SEQUENCE"):
        service.set_workspace_epoch(
            workspace_id="workspace-1", recovery_epoch="epoch-1", epoch_sequence=1
        )

    with psycopg.connect(DSN) as connection:
        fence = connection.execute(
            """
            SELECT execution_generation, recovery_epoch FROM execution_fences
             WHERE workspace_id = 'workspace-1' AND grant_id = 'grant-1'
            """
        ).fetchone()
    assert fence == (4, "epoch-2")
