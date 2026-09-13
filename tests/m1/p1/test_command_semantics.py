import importlib
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
import pytest


REPOSITORY_ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

SCHEMA_PATH = REPOSITORY_ROOT / "sql" / "m1" / "p1_schema.sql"
DSN = "postgresql://postgres@127.0.0.1:55432/aiavc_m1"


def prepare_database() -> None:
    assert SCHEMA_PATH.is_file(), "P1 PostgreSQL schema is not implemented"
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with psycopg.connect(DSN, autocommit=True) as connection:
        connection.execute(schema)
        connection.execute("SELECT m1_p1_reset()")
        connection.execute(
            """
            INSERT INTO workspace_epochs
                (workspace_id, recovery_epoch, epoch_sequence, updated_at)
            VALUES ('workspace-1', 'epoch-1', 1, now())
            """
        )


def load_contract_module():
    module = importlib.import_module("m1proof.contracts")
    assert hasattr(module, "ContractProofService"), "P1 service is not implemented"
    return module


def make_command(module, *, key: str, value: str = "first"):
    return module.MutationCommand(
        command_id=f"command-{key}-{value}",
        idempotency_key=key,
        workspace_id="workspace-1",
        aggregate_id="aggregate-1",
        expected_revision=0,
        recovery_epoch="epoch-1",
        execution_generation=1,
        payload={"value": value},
    )


def table_count(table_name: str) -> int:
    allowed = {"proof_aggregates", "command_receipts", "outbox_events"}
    assert table_name in allowed
    with psycopg.connect(DSN) as connection:
        return connection.execute(f"SELECT count(*) FROM {table_name}").fetchone()[0]


def test_duplicate_command_returns_same_receipt_and_one_mutation() -> None:
    prepare_database()
    module = load_contract_module()
    service = module.ContractProofService(DSN)
    command = make_command(module, key="same-command")

    first = service.execute_mutation(command)
    duplicate = service.execute_mutation(command)

    assert first.disposition == "accepted"
    assert duplicate.disposition == "duplicate"
    assert duplicate.receipt_id == first.receipt_id
    assert duplicate.resource_revision == first.resource_revision == 1
    assert table_count("proof_aggregates") == 1
    assert table_count("command_receipts") == 1
    assert table_count("outbox_events") == 1


def test_concurrent_duplicate_commands_commit_only_once() -> None:
    prepare_database()
    module = load_contract_module()
    command = make_command(module, key="concurrent-command")

    def execute_once():
        return module.ContractProofService(DSN).execute_mutation(command)

    with ThreadPoolExecutor(max_workers=2) as executor:
        receipts = list(executor.map(lambda _: execute_once(), range(2)))

    assert {receipt.disposition for receipt in receipts} == {"accepted", "duplicate"}
    assert len({receipt.receipt_id for receipt in receipts}) == 1
    assert table_count("proof_aggregates") == 1
    assert table_count("command_receipts") == 1
    assert table_count("outbox_events") == 1


def test_concurrent_distinct_commands_cannot_both_create_same_revision(
    monkeypatch,
) -> None:
    prepare_database()
    module = load_contract_module()
    real_connect = module.psycopg.connect
    revision_read_barrier = threading.Barrier(2)

    class BarrierConnection:
        def __init__(self, connection):
            self._connection = connection
            self._aggregate_lock_seen = False

        def __enter__(self):
            self._connection.__enter__()
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return self._connection.__exit__(exc_type, exc_value, traceback)

        def execute(self, query, params=None):
            cursor = self._connection.execute(query, params)
            query_text = str(query)
            if (
                "pg_advisory_xact_lock" in query_text
                and params
                and str(params[0]).startswith("aggregate:")
            ):
                self._aggregate_lock_seen = True
            if (
                not self._aggregate_lock_seen
                and "SELECT revision" in query_text
                and "proof_aggregates" in query_text
            ):
                revision_read_barrier.wait(timeout=5)
            return cursor

    def synchronized_connect(*args, **kwargs):
        return BarrierConnection(real_connect(*args, **kwargs))

    monkeypatch.setattr(module.psycopg, "connect", synchronized_connect)
    commands = [
        make_command(module, key="create-a", value="a"),
        make_command(module, key="create-b", value="b"),
    ]

    def execute(command):
        try:
            return module.ContractProofService(DSN).execute_mutation(command)
        except module.ContractProofError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(execute, commands))

    accepted = [item for item in outcomes if isinstance(item, module.CommandReceipt)]
    conflicts = [item for item in outcomes if isinstance(item, module.ContractProofError)]
    assert len(accepted) == 1
    assert len(conflicts) == 1
    assert "REVISION_CONFLICT" in str(conflicts[0])
    assert table_count("proof_aggregates") == 1
    assert table_count("command_receipts") == 1
    assert table_count("outbox_events") == 1


def test_reused_idempotency_key_with_different_payload_is_rejected() -> None:
    prepare_database()
    module = load_contract_module()
    service = module.ContractProofService(DSN)
    service.execute_mutation(make_command(module, key="reused-key", value="first"))

    with pytest.raises(
        module.IdempotencyConflict,
        match="IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
    ):
        service.execute_mutation(make_command(module, key="reused-key", value="second"))

    with psycopg.connect(DSN) as connection:
        payload = connection.execute(
            "SELECT payload FROM proof_aggregates WHERE aggregate_id = %s",
            ("aggregate-1",),
        ).fetchone()[0]
    assert payload == json.dumps({"value": "first"}) or payload == {"value": "first"}
    assert table_count("command_receipts") == 1


def test_mutation_and_outbox_roll_back_together_at_crash_boundary() -> None:
    prepare_database()
    module = load_contract_module()
    service = module.ContractProofService(DSN)

    with pytest.raises(module.InjectedFailure, match="after_mutation"):
        service.execute_mutation(
            make_command(module, key="crash-boundary"),
            inject_failure="after_mutation",
        )

    assert table_count("proof_aggregates") == 0
    assert table_count("command_receipts") == 0
    assert table_count("outbox_events") == 0
