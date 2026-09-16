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
from controlplane.infrastructure.db.orchestration import (
    PostgresOrchestrationRepository,
)
from controlplane.infrastructure.db.uow import TransactionManager

ROOT = Path(__file__).parents[2]
MIGRATIONS = ROOT / "src/controlplane/infrastructure/db/migrations"
P6_MIGRATION = MIGRATIONS / "0006_orchestration_shell.sql"
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


def _repository_factory(connection: object) -> PostgresOrchestrationRepository:
    return PostgresOrchestrationRepository(connection)


def _execution_grant_service() -> ExecutionGrantService:
    return ExecutionGrantService(_repository_factory)


def _variant_reservation_service() -> VariantReservationService:
    return VariantReservationService(_repository_factory)


def _batch_capacity_service() -> BatchCapacityService:
    return BatchCapacityService(_repository_factory)


def _completion_ledger_service() -> CompletionLedgerService:
    return CompletionLedgerService(_repository_factory)


def _seed_batch(connection: psycopg.Connection[object]) -> bool:
    if not P6_MIGRATION.exists():
        return False
    connection.execute(
        "INSERT INTO controlplane.cp_production_batches "
        "(batch_id, workspace_id, status, target_count) "
        "VALUES ('batch-1', %s, 'RUNNING', 2) ON CONFLICT DO NOTHING",
        (WORKSPACE_ID,),
    )
    return True


def _seed_variant_prerequisites(connection: psycopg.Connection[object]) -> None:
    if not _seed_batch(connection):
        return
    for job_id in ("job-a", "job-b", "job-c"):
        connection.execute(
            "INSERT INTO controlplane.cp_video_jobs "
            "(job_id, batch_id, workspace_id, status, snapshot_ref, revision) "
            "VALUES (%s, 'batch-1', %s, 'ACTIVE', 'snapshot-1', 1) "
            "ON CONFLICT DO NOTHING",
            (job_id, WORKSPACE_ID),
        )
    connection.execute(
        "INSERT INTO controlplane.cp_variant_registry "
        "(workspace_id, current_registry_revision) VALUES (%s, 1) "
        "ON CONFLICT DO NOTHING",
        (WORKSPACE_ID,),
    )


def _seed_completion_prerequisites(connection: psycopg.Connection[object]) -> None:
    if not _seed_batch(connection):
        return
    for job_id in ("job-1", "job-rollback"):
        connection.execute(
            "INSERT INTO controlplane.cp_video_jobs "
            "(job_id, batch_id, workspace_id, status, snapshot_ref, revision) "
            "VALUES (%s, 'batch-1', %s, 'READY_FOR_COMPLETION', 'snapshot-1', 1) "
            "ON CONFLICT DO NOTHING",
            (job_id, WORKSPACE_ID),
        )
    connection.execute(
        "INSERT INTO controlplane.cp_variant_registry "
        "(workspace_id, current_registry_revision) VALUES (%s, 1) "
        "ON CONFLICT DO NOTHING",
        (WORKSPACE_ID,),
    )
    for capacity_id, variant_id, job_id, fingerprint in (
        ("capacity-1", "variant-1", "job-1", "fingerprint-1"),
        (
            "capacity-rollback",
            "variant-rollback",
            "job-rollback",
            "fingerprint-rollback",
        ),
    ):
        connection.execute(
            "INSERT INTO controlplane.cp_batch_capacity_reservations "
            "(reservation_id, workspace_id, batch_id, job_id, state) "
            "VALUES (%s, %s, 'batch-1', %s, 'ACTIVE') ON CONFLICT DO NOTHING",
            (capacity_id, WORKSPACE_ID, job_id),
        )
        connection.execute(
            "INSERT INTO controlplane.cp_variant_reservations "
            "(reservation_id, workspace_id, job_id, fingerprint, snapshot_scope, "
            "validation_ref, variation_policy_revision, expected_registry_revision, "
            "committed_registry_revision, state) "
            "VALUES (%s, %s, %s, %s, 'snapshot-1', 'validation-1', "
            "'policy-1', 1, 1, 'ACTIVE') ON CONFLICT DO NOTHING",
            (variant_id, WORKSPACE_ID, job_id, fingerprint),
        )
    connection.execute(
        "INSERT INTO controlplane.cp_artifact_versions "
        "(artifact_version_id, workspace_id, artifact_id, sha256_hash, size_bytes, "
        "mime_type, artifact_kind, owner_ref, lineage_ref, retention_ref, sensitivity_ref) "
        "VALUES ('00000000-0000-0000-0000-000000005b01', %s, 'artifact-p6', %s, "
        "128, 'video/mp4', 'rendered_video', 'owner-p6', 'lineage-p6', "
        "'retention-p6', 'internal') ON CONFLICT DO NOTHING",
        (WORKSPACE_ID, HASH_A),
    )


def test_tst_m2_p6_001_execution_grant_stale_epoch_fencing(
    p6_database: DisposableDatabase,
) -> None:
    service = _execution_grant_service()
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
    service = _variant_reservation_service()
    request = dict(
        workspace_id=WORKSPACE_ID,
        fingerprint="fingerprint-1",
        snapshot_scope="snapshot-1",
        validation_ref="validation-1",
        variation_policy_revision="policy-1",
        expected_registry_revision=1,
    )
    with _manager(p6_database.dsn) as manager:
        with manager.unit_of_work() as uow:
            _seed_variant_prerequisites(uow.connection)

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
    service = _batch_capacity_service()
    with _manager(p6_database.dsn) as manager:
        with manager.unit_of_work() as uow:
            seeded = _seed_batch(uow.connection)
            if seeded:
                target = uow.connection.execute(
                    "SELECT target_count FROM controlplane.cp_production_batches "
                    "WHERE workspace_id=%s AND batch_id='batch-1'",
                    (WORKSPACE_ID,),
                ).fetchone()[0]
                assert target == 2

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
                connection=uow.connection,
            )
        assert (
            isinstance(first, CapacityAllocation)
            and first.state is ReservationState.ACTIVE
        )
        assert first.target_completed_videos == 2
        with manager.unit_of_work() as uow:
            retry = service.allocate(
                workspace_id=WORKSPACE_ID,
                batch_id="batch-1",
                job_id="job-1",
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
                        connection=uow.connection,
                    )
            except OrchestrationContractError as error:
                return error

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(last_slot, ("job-2", "job-3")))
        winners = [x for x in outcomes if isinstance(x, CapacityAllocation)]
        assert len(winners) == 1
        winner = winners[0]
        loser_job_id = ({"job-2", "job-3"} - {winner.job_id}).pop()
        with manager.unit_of_work() as uow:
            loser_reservations = uow.connection.execute(
                "SELECT count(*) FROM controlplane.cp_batch_capacity_reservations "
                "WHERE workspace_id=%s AND job_id=%s",
                (WORKSPACE_ID, loser_job_id),
            ).fetchone()[0]
        assert loser_reservations == 0
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
                workspace_id=WORKSPACE_ID,
                job_id=winner.job_id,
                connection=uow.connection,
            )
        assert completed.state is ReservationState.CONVERTED
        assert completed.state is not ReservationState.RELEASED


def test_tst_m2_p6_004_completion_ledger_unique_job_invariant(
    p6_database: DisposableDatabase,
) -> None:
    service = _completion_ledger_service()
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
        with manager.unit_of_work() as uow:
            _seed_completion_prerequisites(uow.connection)

        class InjectedCompletionFailure(Exception):
            pass

        def fail_before_ledger(boundary: str) -> None:
            if boundary == "before_ledger_insert":
                raise InjectedCompletionFailure

        with pytest.raises(InjectedCompletionFailure):
            with manager.unit_of_work() as uow:
                service.commit(
                    **{
                        **values,
                        "job_id": "job-rollback",
                        "capacity_reservation_id": "capacity-rollback",
                        "variant_reservation_id": "variant-rollback",
                    },
                    fault_hook=fail_before_ledger,
                    connection=uow.connection,
                )
        with manager.unit_of_work() as uow:
            rollback_ledgers = uow.connection.execute(
                "SELECT count(*) FROM controlplane.cp_completion_ledger "
                "WHERE workspace_id=%s AND job_id='job-rollback'",
                (WORKSPACE_ID,),
            ).fetchone()[0]
            capacity_state = uow.connection.execute(
                "SELECT state FROM controlplane.cp_batch_capacity_reservations "
                "WHERE workspace_id=%s AND reservation_id='capacity-rollback'",
                (WORKSPACE_ID,),
            ).fetchone()[0]
            variant_state = uow.connection.execute(
                "SELECT state FROM controlplane.cp_variant_reservations "
                "WHERE workspace_id=%s AND reservation_id='variant-rollback'",
                (WORKSPACE_ID,),
            ).fetchone()[0]
            rollback_job_state = uow.connection.execute(
                "SELECT status FROM controlplane.cp_video_jobs "
                "WHERE workspace_id=%s AND job_id='job-rollback'",
                (WORKSPACE_ID,),
            ).fetchone()[0]
        assert rollback_ledgers == 0
        assert capacity_state == "ACTIVE" and variant_state == "ACTIVE"
        assert rollback_job_state == "READY_FOR_COMPLETION"

        def commit() -> object:
            try:
                with manager.unit_of_work() as uow:
                    return service.commit(**values, connection=uow.connection)
            except OrchestrationContractError as error:
                return error

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _: commit(), range(2)))
        ledgers = [x for x in outcomes if isinstance(x, CompletionLedger)]
        assert len(ledgers) == 2
        assert ledgers[0].ledger_id == ledgers[1].ledger_id
        assert {ledger.job_id for ledger in ledgers} == {"job-1"}
        assert {ledger.output_artifact_version_id for ledger in ledgers} == {
            values["output_artifact_version_id"]
        }
        assert {ledger.output_artifact_hash for ledger in ledgers} == {HASH_A}
        with manager.unit_of_work() as uow:
            count = uow.connection.execute(
                "SELECT count(*) FROM controlplane.cp_completion_ledger WHERE workspace_id=%s AND job_id=%s",
                (WORKSPACE_ID, "job-1"),
            ).fetchone()[0]
        assert count == 1
