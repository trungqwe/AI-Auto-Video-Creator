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
    module = importlib.import_module("m1proof.contracts")
    assert hasattr(module, "OutboxDispatcher"), (
        "P1 outbox dispatcher with a crash checkpoint is not implemented"
    )
    return module


def test_dispatch_crash_before_checkpoint_is_recovered_by_consumer_dedupe() -> None:
    prepare_database()
    module = load_contract_module()
    service = module.ContractProofService(DSN)
    service.set_workspace_epoch(
        workspace_id="workspace-1",
        recovery_epoch="epoch-dispatch",
        epoch_sequence=1,
    )
    command = module.MutationCommand(
        command_id="command-dispatch",
        idempotency_key="dispatch-key",
        workspace_id="workspace-1",
        aggregate_id="aggregate-dispatch",
        expected_revision=0,
        recovery_epoch="epoch-dispatch",
        execution_generation=1,
        payload={"value": "dispatch-once"},
    )
    service.execute_mutation(command)

    delivered = []

    def consume(event):
        delivered.append(event.event_id)
        return service.consume_event("consumer-dispatch", event)

    dispatcher = module.OutboxDispatcher(DSN, consume)
    with pytest.raises(module.InjectedFailure, match="after_dispatch_before_checkpoint"):
        dispatcher.dispatch_next(inject_failure="after_dispatch_before_checkpoint")

    with psycopg.connect(DSN) as connection:
        published_at, apply_count = connection.execute(
            """
            SELECT
                (SELECT published_at FROM outbox_events LIMIT 1),
                (SELECT apply_count FROM consumer_projections
                  WHERE consumer_id = 'consumer-dispatch')
            """
        ).fetchone()
    assert published_at is None
    assert apply_count == 1

    restarted_dispatcher = module.OutboxDispatcher(DSN, consume)
    assert restarted_dispatcher.dispatch_next() is True

    with psycopg.connect(DSN) as connection:
        published_at, apply_count = connection.execute(
            """
            SELECT
                (SELECT published_at FROM outbox_events LIMIT 1),
                (SELECT apply_count FROM consumer_projections
                  WHERE consumer_id = 'consumer-dispatch')
            """
        ).fetchone()
    assert published_at is not None
    assert apply_count == 1
    assert len(delivered) == 2
