"""Exact four M2-P6 Behavioral RED oracles."""

from __future__ import annotations

import os
import re
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from controlplane.application.orchestration import (
    BatchCapacityService,
    CompletionLedgerService,
    ExecutionGrantService,
    VariantReservationService,
)
from controlplane.domain.orchestration import (
    CapacityAllocation,
    CompletionLedger,
    ExecutionGrant,
    OrchestrationContractError,
    ReservationState,
    VariantReservation,
)
from controlplane.infrastructure.db.migration_runner import MigrationRunner
from controlplane.infrastructure.db.uow import TransactionManager

ROOT = Path(__file__).parents[2]
MIGRATIONS = ROOT / "src/controlplane/infrastructure/db/migrations"
DATABASE_NAME = re.compile(r"^m2_p6_test_[0-9a-f]+$")
WORKSPACE_ID = "00000000-0000-0000-0000-000000000601"
HASH_A = "a" * 64


@dataclass
class DisposableDatabase:
    name: str
    dsn: str = field(repr=False)


@contextmanager
def _database() -> Iterator[DisposableDatabase]:
    admin_dsn = os.environ.get("M2_TEST_PG_DSN")
    if not admin_dsn:
        pytest.fail("BLOCKED_EXTERNAL: M2_TEST_PG_DSN is required")
    name = f"m2_p6_test_{uuid.uuid4().hex}"
    assert DATABASE_NAME.fullmatch(name)
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        assert admin.execute("SHOW server_version").fetchone()[0].split()[0] == "18.6"
        assert admin.execute(
            "SELECT rolcreatedb FROM pg_roles WHERE rolname=current_user"
        ).fetchone()[0]
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    dsn = make_conninfo(admin_dsn, dbname=name)
    try:
        MigrationRunner(dsn, MIGRATIONS, is_test_env=True).migrate_up()
        with psycopg.connect(dsn) as connection:
            connection.execute(
                "INSERT INTO controlplane.cp_workspaces (workspace_id,name,status) VALUES (%s,'P6','ACTIVE')",
                (WORKSPACE_ID,),
            )
            connection.commit()
        yield DisposableDatabase(name, dsn)
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            assert DATABASE_NAME.fullmatch(name)
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s",
                (name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


@pytest.fixture
def p6_database() -> Iterator[DisposableDatabase]:
    with _database() as database:
        yield database


@contextmanager
def _manager(dsn: str) -> Iterator[TransactionManager]:
    manager = TransactionManager(dsn, pool_max_size=4)
    try:
        yield manager
    finally:
        manager.close()


def test_tst_m2_p6_001_execution_grant_stale_epoch_fencing(
    p6_database: DisposableDatabase,
) -> None:
    service = ExecutionGrantService()
    grant = ExecutionGrant(WORKSPACE_ID, "operation-1", "job-1", "stage-1", 4, 9)
    with _manager(p6_database.dsn) as manager:
        with manager.unit_of_work() as uow:
            accepted = service.accept_result(
                grant=grant,
                submitted_generation=4,
                submitted_recovery_epoch=9,
                result_ref="result-1",
                connection=uow.connection,
            )
        assert accepted.grant == grant and accepted.accepted is True
        with manager.unit_of_work() as uow:
            with pytest.raises(OrchestrationContractError) as stale_epoch:
                service.accept_result(
                    grant=grant,
                    submitted_generation=4,
                    submitted_recovery_epoch=8,
                    result_ref="stale",
                    connection=uow.connection,
                )
        assert stale_epoch.value.code == "STALE_RECOVERY_EPOCH"
        with manager.unit_of_work() as uow:
            with pytest.raises(OrchestrationContractError) as stale_generation:
                service.accept_result(
                    grant=grant,
                    submitted_generation=3,
                    submitted_recovery_epoch=9,
                    result_ref="stale",
                    connection=uow.connection,
                )
        assert stale_generation.value.code == "STALE_EXECUTION_GENERATION"


def test_tst_m2_p6_002_variant_reservation_cas_and_conflict(
    p6_database: DisposableDatabase,
) -> None:
    service = VariantReservationService()
    request = dict(
        workspace_id=WORKSPACE_ID,
        fingerprint="fingerprint-1",
        snapshot_scope="snapshot-1",
        validation_ref="validation-1",
        variation_policy_revision="policy-1",
        expected_registry_revision=1,
    )
    with _manager(p6_database.dsn) as manager:

        def reserve(job_id: str) -> object:
            try:
                with manager.unit_of_work() as uow:
                    return service.reserve(
                        **request, job_id=job_id, connection=uow.connection
                    )
            except OrchestrationContractError as error:
                return error

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(reserve, ("job-a", "job-b")))
        winners = [x for x in outcomes if isinstance(x, VariantReservation)]
        losers = [x for x in outcomes if isinstance(x, OrchestrationContractError)]
        assert len(winners) == 1 and winners[0].state is ReservationState.ACTIVE
        assert winners[0].committed_registry_revision == 2
        assert len(losers) == 1 and losers[0].code == "VARIANT_CONFLICT"
        with manager.unit_of_work() as uow:
            with pytest.raises(OrchestrationContractError) as stale:
                service.reserve(
                    **{
                        **request,
                        "fingerprint": "different",
                        "expected_registry_revision": 1,
                    },
                    job_id="job-c",
                    connection=uow.connection,
                )
        assert stale.value.code == "VARIANT_VALIDATION_STALE"


def test_tst_m2_p6_003_batch_capacity_reservation_lifecycle(
    p6_database: DisposableDatabase,
) -> None:
    service = BatchCapacityService()
    with _manager(p6_database.dsn) as manager:

        class InjectedAllocationFailure(Exception):
            pass

        def fail_after_job(boundary: str) -> None:
            if boundary == "after_job_insert":
                raise InjectedAllocationFailure

        with pytest.raises(InjectedAllocationFailure):
            with manager.unit_of_work() as uow:
                service.allocate(
                    workspace_id=WORKSPACE_ID,
                    batch_id="batch-1",
                    job_id="job-rollback",
                    target_completed_videos=2,
                    fault_hook=fail_after_job,
                    connection=uow.connection,
                )
        with manager.unit_of_work() as uow:
            orphan_job = uow.connection.execute(
                "SELECT count(*) FROM controlplane.cp_video_jobs WHERE workspace_id=%s AND job_id=%s",
                (WORKSPACE_ID, "job-rollback"),
            ).fetchone()[0]
            orphan_capacity = uow.connection.execute(
                "SELECT count(*) FROM controlplane.cp_batch_capacity_reservations WHERE workspace_id=%s AND job_id=%s",
                (WORKSPACE_ID, "job-rollback"),
            ).fetchone()[0]
        assert orphan_job == 0 and orphan_capacity == 0
        with manager.unit_of_work() as uow:
            first = service.allocate(
                workspace_id=WORKSPACE_ID,
                batch_id="batch-1",
                job_id="job-1",
                target_completed_videos=2,
                connection=uow.connection,
            )
        assert (
            isinstance(first, CapacityAllocation)
            and first.state is ReservationState.ACTIVE
        )
        with manager.unit_of_work() as uow:
            retry = service.allocate(
                workspace_id=WORKSPACE_ID,
                batch_id="batch-1",
                job_id="job-1",
                target_completed_videos=2,
                connection=uow.connection,
            )
        assert retry.reservation_id == first.reservation_id
        with manager.unit_of_work() as uow:
            waiting = service.mark_waiting(
                workspace_id=WORKSPACE_ID, job_id="job-1", connection=uow.connection
            )
        assert waiting.state is ReservationState.ACTIVE

        def last_slot(job_id: str) -> object:
            try:
                with manager.unit_of_work() as uow:
                    return service.allocate(
                        workspace_id=WORKSPACE_ID,
                        batch_id="batch-1",
                        job_id=job_id,
                        target_completed_videos=2,
                        connection=uow.connection,
                    )
            except OrchestrationContractError as error:
                return error

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(last_slot, ("job-2", "job-3")))
        assert sum(isinstance(x, CapacityAllocation) for x in outcomes) == 1
        with manager.unit_of_work() as uow:
            released = service.release_terminal(
                workspace_id=WORKSPACE_ID,
                job_id="job-1",
                terminal_status="FAILED_FINAL",
                connection=uow.connection,
            )
        assert released.state is ReservationState.RELEASED
        with manager.unit_of_work() as uow:
            completed = service.convert_completion(
                workspace_id=WORKSPACE_ID, job_id="job-2", connection=uow.connection
            )
        assert completed.state is ReservationState.CONVERTED
        assert completed.state is not ReservationState.RELEASED


def test_tst_m2_p6_004_completion_ledger_unique_job_invariant(
    p6_database: DisposableDatabase,
) -> None:
    service = CompletionLedgerService()
    values = dict(
        workspace_id=WORKSPACE_ID,
        job_id="job-1",
        batch_id="batch-1",
        capacity_reservation_id="capacity-1",
        variant_reservation_id="variant-1",
        output_artifact_version_id="00000000-0000-0000-0000-000000005b01",
        output_artifact_hash=HASH_A,
        actor_ref="actor-1",
        completed_at=datetime.now(timezone.utc),
        audit_ref="audit-1",
    )
    with _manager(p6_database.dsn) as manager:

        class InjectedCompletionFailure(Exception):
            pass

        def fail_before_ledger(boundary: str) -> None:
            if boundary == "before_ledger_insert":
                raise InjectedCompletionFailure

        with pytest.raises(InjectedCompletionFailure):
            with manager.unit_of_work() as uow:
                service.commit(
                    **{**values, "job_id": "job-rollback"},
                    fault_hook=fail_before_ledger,
                    connection=uow.connection,
                )

        def commit() -> object:
            try:
                with manager.unit_of_work() as uow:
                    return service.commit(**values, connection=uow.connection)
            except OrchestrationContractError as error:
                return error

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _: commit(), range(2)))
        ledgers = [x for x in outcomes if isinstance(x, CompletionLedger)]
        assert len(ledgers) == 1
        assert (
            ledgers[0].job_id == "job-1" and ledgers[0].output_artifact_hash == HASH_A
        )
        with manager.unit_of_work() as uow:
            count = uow.connection.execute(
                "SELECT count(*) FROM controlplane.cp_completion_ledger WHERE workspace_id=%s AND job_id=%s",
                (WORKSPACE_ID, "job-1"),
            ).fetchone()[0]
        assert count == 1
