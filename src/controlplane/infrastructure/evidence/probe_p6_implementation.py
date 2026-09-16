"""Independent executable PostgreSQL probes for P6 implementation invariants."""

from __future__ import annotations

import argparse
import json
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from controlplane.application.orchestration import (
    BatchCapacityService,
    CompletionLedgerService,
    VariantReservationService,
)
from controlplane.domain.orchestration import (
    CapacityAllocation,
    CompletionLedger,
    OrchestrationContractError,
    VariantReservation,
)
from controlplane.infrastructure.db.migration_runner import MigrationRunner
from controlplane.infrastructure.db.orchestration import PostgresOrchestrationRepository

ROOT = Path(__file__).parents[4]
MIGRATIONS = ROOT / "src/controlplane/infrastructure/db/migrations"
DB_PATTERN = re.compile(r"^m2_p6_probe_[0-9a-f]+$")
HASH_A = "a" * 64
ARTIFACT = "00000000-0000-0000-0000-000000006611"
CAPACITY = BatchCapacityService(PostgresOrchestrationRepository)
VARIANT = VariantReservationService(PostgresOrchestrationRepository)
COMPLETION = CompletionLedgerService(PostgresOrchestrationRepository)


@contextmanager
def _database(admin_dsn: str) -> Iterator[str]:
    name = f"m2_p6_probe_{uuid.uuid4().hex}"
    assert DB_PATTERN.fullmatch(name)
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        yield make_conninfo(admin_dsn, dbname=name)
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s",
                (name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def _workspace(connection: psycopg.Connection, label: str) -> str:
    workspace_id = str(uuid.uuid4())
    connection.execute(
        "INSERT INTO controlplane.cp_workspaces (workspace_id,name,status) VALUES (%s,%s,'ACTIVE')",
        (workspace_id, label),
    )
    return workspace_id


def _batch(
    connection: psycopg.Connection, workspace: str, batch: str, target: int
) -> None:
    connection.execute(
        "INSERT INTO controlplane.cp_production_batches (batch_id,workspace_id,status,target_count) VALUES (%s,%s,'RUNNING',%s)",
        (batch, workspace, target),
    )


def _job(
    connection: psycopg.Connection,
    workspace: str,
    batch: str,
    job: str,
    status: str = "ACTIVE",
) -> None:
    connection.execute(
        "INSERT INTO controlplane.cp_video_jobs (job_id,batch_id,workspace_id,status,snapshot_ref,revision) VALUES (%s,%s,%s,%s,'snapshot',1)",
        (job, batch, workspace, status),
    )


def _reserve_values(
    workspace: str, job: str, fingerprint: str, expected: int = 1
) -> dict[str, object]:
    return {
        "workspace_id": workspace,
        "job_id": job,
        "fingerprint": fingerprint,
        "snapshot_scope": "snapshot",
        "validation_ref": "validation",
        "variation_policy_revision": "policy",
        "expected_registry_revision": expected,
    }


def _completion_parent(
    connection: psycopg.Connection, workspace: str, job: str
) -> tuple[str, str]:
    capacity, variant = f"capacity-{job}", f"variant-{job}"
    _job(connection, workspace, "batch-1", job, "READY_FOR_COMPLETION")
    connection.execute(
        "INSERT INTO controlplane.cp_batch_capacity_reservations (reservation_id,workspace_id,batch_id,job_id,state) VALUES (%s,%s,'batch-1',%s,'ACTIVE')",
        (capacity, workspace, job),
    )
    connection.execute(
        "INSERT INTO controlplane.cp_variant_reservations (reservation_id,workspace_id,job_id,fingerprint,snapshot_scope,validation_ref,variation_policy_revision,expected_registry_revision,committed_registry_revision,state) VALUES (%s,%s,%s,%s,'snapshot','validation','policy',1,2,'ACTIVE')",
        (variant, workspace, job, f"fp-{job}"),
    )
    return capacity, variant


def _completion_values(workspace: str, job: str) -> dict[str, object]:
    return {
        "workspace_id": workspace,
        "job_id": job,
        "batch_id": "batch-1",
        "capacity_reservation_id": f"capacity-{job}",
        "variant_reservation_id": f"variant-{job}",
        "output_artifact_version_id": ARTIFACT,
        "output_artifact_hash": HASH_A,
        "actor_ref": "actor",
        "completed_at": datetime(2026, 9, 16, tzinfo=timezone.utc),
        "audit_ref": "audit",
    }


def _ledger_row(
    connection: psycopg.Connection, workspace: str, job: str
) -> tuple[object, ...] | None:
    return connection.execute(
        "SELECT ledger_id::text,workspace_id::text,job_id,batch_id,capacity_reservation_id,variant_reservation_id,output_artifact_version_id::text,output_artifact_hash,actor_ref,completed_at,audit_ref FROM controlplane.cp_completion_ledger WHERE workspace_id=%s AND job_id=%s",
        (workspace, job),
    ).fetchone()


def _direct_ledger(connection: psycopg.Connection, values: dict[str, object]) -> None:
    connection.execute(
        "INSERT INTO controlplane.cp_completion_ledger (ledger_id,workspace_id,job_id,batch_id,capacity_reservation_id,variant_reservation_id,output_artifact_version_id,output_artifact_hash,actor_ref,completed_at,audit_ref) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            str(uuid.uuid4()),
            values["workspace_id"],
            values["job_id"],
            values["batch_id"],
            values["capacity_reservation_id"],
            values["variant_reservation_id"],
            values["output_artifact_version_id"],
            values["output_artifact_hash"],
            values["actor_ref"],
            values["completed_at"],
            values["audit_ref"],
        ),
    )


def _integrity_rejected(connection: psycopg.Connection, action: object) -> bool:
    try:
        with connection.transaction():
            action()
    except psycopg.IntegrityError:
        return True
    return False


def _service_call(dsn: str, method: object, values: dict[str, object]) -> object:
    with psycopg.connect(dsn) as connection:
        return method(**values, connection=connection)


def _outcome(dsn: str, method: object, values: dict[str, object]) -> object:
    try:
        return _service_call(dsn, method, values)
    except OrchestrationContractError as error:
        return error


def _migration_probes(dsn: str) -> tuple[dict[str, bool], list[int], list[int]]:
    checks: dict[str, bool] = {}
    MigrationRunner(dsn, MIGRATIONS, is_test_env=True).migrate_up()
    with psycopg.connect(dsn, autocommit=True) as connection:
        required = {
            "cp_production_batches",
            "cp_video_jobs",
            "cp_stage_runs",
            "cp_batch_capacity_reservations",
            "cp_variant_reservations",
            "cp_variant_registry",
            "cp_completion_ledger",
        }
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='controlplane'"
            )
        }
        before = [
            row[0]
            for row in connection.execute(
                "SELECT version FROM controlplane.cp_schema_migrations ORDER BY version"
            )
        ]
        index_present = (
            connection.execute(
                "SELECT to_regclass('controlplane.cp_variant_reservations_live_fingerprint')"
            ).fetchone()[0]
            is not None
        )
        checks["migration_forward"] = (
            required <= tables and before == [1, 2, 3, 4, 5, 6] and index_present
        )
        with connection.transaction():
            connection.execute(
                (MIGRATIONS / "0006_orchestration_shell.rollback.sql").read_text(
                    encoding="utf-8"
                )
            )
            connection.execute(
                "DELETE FROM controlplane.cp_schema_migrations WHERE version=6"
            )
        after = [
            row[0]
            for row in connection.execute(
                "SELECT version FROM controlplane.cp_schema_migrations ORDER BY version"
            )
        ]
        tables_after = {
            row[0]
            for row in connection.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='controlplane'"
            )
        }
        index_absent = (
            connection.execute(
                "SELECT to_regclass('controlplane.cp_variant_reservations_live_fingerprint')"
            ).fetchone()[0]
            is None
        )
        accepted_present = all(
            connection.execute(
                "SELECT to_regclass(%s)", (f"controlplane.{table}",)
            ).fetchone()[0]
            is not None
            for table in (
                "cp_workspaces",
                "cp_artifact_versions",
                "cp_schema_migrations",
            )
        )
        checks["migration_rollback_preserves_0001_0005"] = (
            after == [1, 2, 3, 4, 5]
            and not (required & tables_after)
            and index_absent
            and accepted_present
        )
    MigrationRunner(dsn, MIGRATIONS, is_test_env=True).migrate_up()
    return checks, before, after


def _binding_probes(dsn: str) -> dict[str, bool]:
    with psycopg.connect(dsn, autocommit=True) as connection:
        workspace = _workspace(connection, "binding")
        foreign = _workspace(connection, "foreign")
        _batch(connection, workspace, "batch-1", 3)
        job_rejected = _integrity_rejected(
            connection, lambda: _job(connection, foreign, "batch-1", "foreign-job")
        )
        _job(connection, workspace, "batch-1", "job-1")
        capacity_rejected = _integrity_rejected(
            connection,
            lambda: connection.execute(
                "INSERT INTO controlplane.cp_batch_capacity_reservations (reservation_id,workspace_id,batch_id,job_id,state) VALUES ('foreign-capacity',%s,'batch-1','job-1','ACTIVE')",
                (foreign,),
            ),
        )
        count = connection.execute(
            "SELECT count(*) FROM controlplane.cp_video_jobs WHERE workspace_id=%s",
            (foreign,),
        ).fetchone()[0]
        return {
            "cross_workspace_binding_rejected": job_rejected
            and capacity_rejected
            and count == 0
        }


def _capacity_probes(dsn: str) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    with psycopg.connect(dsn, autocommit=True) as connection:
        workspace = _workspace(connection, "capacity")
        _batch(connection, workspace, "batch-1", 1)

    def fault(boundary: str) -> None:
        if boundary == "after_job_insert":
            raise RuntimeError("injected allocation failure")

    try:
        _service_call(
            dsn,
            CAPACITY.allocate,
            {
                "workspace_id": workspace,
                "batch_id": "batch-1",
                "job_id": "job-fault",
                "fault_hook": fault,
            },
        )
    except RuntimeError as error:
        injected = str(error) == "injected allocation failure"
    else:
        injected = False
    with psycopg.connect(dsn, autocommit=True) as connection:
        jobs = connection.execute(
            "SELECT count(*) FROM controlplane.cp_video_jobs WHERE workspace_id=%s AND job_id='job-fault'",
            (workspace,),
        ).fetchone()[0]
        rows = connection.execute(
            "SELECT count(*) FROM controlplane.cp_batch_capacity_reservations WHERE workspace_id=%s AND job_id='job-fault'",
            (workspace,),
        ).fetchone()[0]
        checks["allocation_fault_no_orphan"] = injected and jobs == 0 and rows == 0

    def values(job: str) -> dict[str, object]:
        return {"workspace_id": workspace, "batch_id": "batch-1", "job_id": job}

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(
            executor.map(
                lambda job: _outcome(dsn, CAPACITY.allocate, values(job)),
                ("job-a", "job-b"),
            )
        )
    winners = [item for item in outcomes if isinstance(item, CapacityAllocation)]
    losers = [item for item in outcomes if isinstance(item, OrchestrationContractError)]
    loser = (
        ({"job-a", "job-b"} - {item.job_id for item in winners}).pop()
        if len(winners) == 1
        else "none"
    )
    with psycopg.connect(dsn, autocommit=True) as connection:
        winner_count = connection.execute(
            "SELECT count(*) FROM controlplane.cp_batch_capacity_reservations WHERE workspace_id=%s AND state='ACTIVE'",
            (workspace,),
        ).fetchone()[0]
        loser_jobs = connection.execute(
            "SELECT count(*) FROM controlplane.cp_video_jobs WHERE workspace_id=%s AND job_id=%s",
            (workspace, loser),
        ).fetchone()[0]
        loser_rows = connection.execute(
            "SELECT count(*) FROM controlplane.cp_batch_capacity_reservations WHERE workspace_id=%s AND job_id=%s",
            (workspace, loser),
        ).fetchone()[0]
        checks["capacity_last_slot_no_orphan"] = (
            len(winners) == 1
            and len(losers) == 1
            and losers[0].code == "BATCH_TARGET_REACHED"
            and winner_count == 1
            and loser_jobs == 0
            and loser_rows == 0
        )
        other = _workspace(connection, "capacity-cross-batch")
        _batch(connection, other, "batch-A", 2)
        _batch(connection, other, "batch-B", 2)
    first = _service_call(
        dsn,
        CAPACITY.allocate,
        {"workspace_id": other, "batch_id": "batch-A", "job_id": "job-cross"},
    )
    before = None
    with psycopg.connect(dsn, autocommit=True) as connection:
        before = connection.execute(
            "SELECT reservation_id,batch_id,job_id,state FROM controlplane.cp_batch_capacity_reservations WHERE workspace_id=%s AND job_id='job-cross'",
            (other,),
        ).fetchone()
    wrong = _outcome(
        dsn,
        CAPACITY.allocate,
        {"workspace_id": other, "batch_id": "batch-B", "job_id": "job-cross"},
    )
    with psycopg.connect(dsn, autocommit=True) as connection:
        after = connection.execute(
            "SELECT reservation_id,batch_id,job_id,state FROM controlplane.cp_batch_capacity_reservations WHERE workspace_id=%s AND job_id='job-cross'",
            (other,),
        ).fetchone()
        new_rows = connection.execute(
            "SELECT count(*) FROM controlplane.cp_video_jobs WHERE workspace_id=%s AND batch_id='batch-B'",
            (other,),
        ).fetchone()[0]
        checks["capacity_cross_batch_retry_rejected"] = (
            isinstance(first, CapacityAllocation)
            and isinstance(wrong, OrchestrationContractError)
            and wrong.code == "VALIDATION_ERROR"
            and before == after
            and new_rows == 0
        )
    return checks


def _variant_probes(dsn: str) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    with psycopg.connect(dsn, autocommit=True) as connection:
        workspace = _workspace(connection, "variant-first-use")
        _batch(connection, workspace, "batch-1", 5)
        for job in ("job-a", "job-b", "job-c"):
            _job(connection, workspace, "batch-1", job)
        connection.execute(
            "INSERT INTO controlplane.cp_variant_registry "
            "(workspace_id,current_registry_revision) VALUES (%s,1)",
            (workspace,),
        )
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(
            executor.map(
                lambda job: _outcome(
                    dsn,
                    VARIANT.reserve,
                    _reserve_values(workspace, job, "same-fingerprint"),
                ),
                ("job-a", "job-b"),
            )
        )
    winners = [item for item in outcomes if isinstance(item, VariantReservation)]
    losers = [item for item in outcomes if isinstance(item, OrchestrationContractError)]
    with psycopg.connect(dsn, autocommit=True) as connection:
        revision = connection.execute(
            "SELECT current_registry_revision FROM controlplane.cp_variant_registry WHERE workspace_id=%s",
            (workspace,),
        ).fetchone()[0]
        count = connection.execute(
            "SELECT count(*) FROM controlplane.cp_variant_reservations WHERE workspace_id=%s",
            (workspace,),
        ).fetchone()[0]
        race_ok = (
            len(winners) == 1
            and len(losers) == 1
            and losers[0].code == "VARIANT_CONFLICT"
            and count == 1
            and revision == 2
        )
        checks["variant_race_one_conflict"] = race_ok
    stale = _outcome(
        dsn,
        VARIANT.reserve,
        _reserve_values(workspace, "job-c", "different-fingerprint"),
    )
    with psycopg.connect(dsn, autocommit=True) as connection:
        count = connection.execute(
            "SELECT count(*) FROM controlplane.cp_variant_reservations WHERE workspace_id=%s AND job_id='job-c'",
            (workspace,),
        ).fetchone()[0]
        after_revision = connection.execute(
            "SELECT current_registry_revision FROM controlplane.cp_variant_registry WHERE workspace_id=%s",
            (workspace,),
        ).fetchone()[0]
        checks["stale_variant_zero_reservation"] = (
            isinstance(stale, OrchestrationContractError)
            and stale.code == "VARIANT_VALIDATION_STALE"
            and count == 0
            and after_revision == 2
        )
    winner = winners[0] if len(winners) == 1 else None
    if winner is not None:
        retry_values = _reserve_values(workspace, winner.job_id, "same-fingerprint", 1)
        exact = _service_call(dsn, VARIANT.reserve, retry_values)
        with psycopg.connect(dsn, autocommit=True) as connection:
            before = connection.execute(
                "SELECT reservation_id,job_id,fingerprint,snapshot_scope,validation_ref,variation_policy_revision,expected_registry_revision,committed_registry_revision,state FROM controlplane.cp_variant_reservations WHERE workspace_id=%s AND job_id=%s",
                (workspace, winner.job_id),
            ).fetchone()
        changed = _outcome(
            dsn, VARIANT.reserve, {**retry_values, "expected_registry_revision": 2}
        )
        with psycopg.connect(dsn, autocommit=True) as connection:
            after = connection.execute(
                "SELECT reservation_id,job_id,fingerprint,snapshot_scope,validation_ref,variation_policy_revision,expected_registry_revision,committed_registry_revision,state FROM controlplane.cp_variant_reservations WHERE workspace_id=%s AND job_id=%s",
                (workspace, winner.job_id),
            ).fetchone()
            final_revision = connection.execute(
                "SELECT current_registry_revision FROM controlplane.cp_variant_registry WHERE workspace_id=%s",
                (workspace,),
            ).fetchone()[0]
            checks["variant_exact_retry_and_changed_expected_rejected"] = (
                isinstance(exact, VariantReservation)
                and exact.reservation_id == winner.reservation_id
                and isinstance(changed, OrchestrationContractError)
                and changed.code == "VARIANT_CONFLICT"
                and before == after
                and final_revision == 2
            )
    else:
        checks["variant_exact_retry_and_changed_expected_rejected"] = False
    with psycopg.connect(dsn, autocommit=True) as connection:
        first_use = _workspace(connection, "variant-concurrent-first-use")
        _batch(connection, first_use, "batch-1", 2)
        _job(connection, first_use, "batch-1", "job-a")
        _job(connection, first_use, "batch-1", "job-b")
        first_use_absent = (
            connection.execute(
                "SELECT count(*) FROM controlplane.cp_variant_registry WHERE workspace_id=%s",
                (first_use,),
            ).fetchone()[0]
            == 0
        )
    with ThreadPoolExecutor(max_workers=2) as executor:
        first_use_outcomes = list(
            executor.map(
                lambda job: _outcome(
                    dsn,
                    VARIANT.reserve,
                    _reserve_values(first_use, job, "first-use-race"),
                ),
                ("job-a", "job-b"),
            )
        )
    with psycopg.connect(dsn, autocommit=True) as connection:
        first_use_revision = connection.execute(
            "SELECT current_registry_revision FROM controlplane.cp_variant_registry WHERE workspace_id=%s",
            (first_use,),
        ).fetchone()[0]
        first_use_rows = connection.execute(
            "SELECT count(*) FROM controlplane.cp_variant_reservations WHERE workspace_id=%s",
            (first_use,),
        ).fetchone()[0]
        checks["registry_concurrent_first_use"] = (
            first_use_absent
            and sum(isinstance(item, VariantReservation) for item in first_use_outcomes)
            == 1
            and sum(
                isinstance(item, OrchestrationContractError)
                and item.code == "VARIANT_CONFLICT"
                for item in first_use_outcomes
            )
            == 1
            and first_use_revision == 2
            and first_use_rows == 1
        )
    with psycopg.connect(dsn, autocommit=True) as connection:
        fresh = _workspace(connection, "variant-fresh")
        _batch(connection, fresh, "batch-1", 2)
        _job(connection, fresh, "batch-1", "job-1")
        fresh_absent = (
            connection.execute(
                "SELECT count(*) FROM controlplane.cp_variant_registry WHERE workspace_id=%s",
                (fresh,),
            ).fetchone()[0]
            == 0
        )
    result = _service_call(
        dsn, VARIANT.reserve, _reserve_values(fresh, "job-1", "fresh-fingerprint")
    )
    with psycopg.connect(dsn, autocommit=True) as connection:
        new_revision = connection.execute(
            "SELECT current_registry_revision FROM controlplane.cp_variant_registry WHERE workspace_id=%s",
            (fresh,),
        ).fetchone()[0]
        row_count = connection.execute(
            "SELECT count(*) FROM controlplane.cp_variant_reservations WHERE workspace_id=%s AND job_id='job-1'",
            (fresh,),
        ).fetchone()[0]
        checks["registry_fresh_workspace_initialized"] = (
            fresh_absent
            and isinstance(result, VariantReservation)
            and result.committed_registry_revision == 2
            and new_revision == 2
            and row_count == 1
        )
        failed_workspace = _workspace(connection, "variant-failed-first-use")
        _batch(connection, failed_workspace, "batch-1", 2)
        _job(connection, failed_workspace, "batch-1", "job-1")
    with psycopg.connect(dsn) as connection:
        try:
            VARIANT.reserve(
                **_reserve_values(failed_workspace, "job-1", "stale-first-use", 0),
                connection=connection,
            )
        except OrchestrationContractError as error:
            failed = error
        else:
            failed = None
    # The caller deliberately commits after catching the rejection. No registry
    # row may leak from the rejected first-use attempt even in this call shape.
    with psycopg.connect(dsn, autocommit=True) as connection:
        registry_count = connection.execute(
            "SELECT count(*) FROM controlplane.cp_variant_registry WHERE workspace_id=%s",
            (failed_workspace,),
        ).fetchone()[0]
        reservation_count = connection.execute(
            "SELECT count(*) FROM controlplane.cp_variant_reservations WHERE workspace_id=%s",
            (failed_workspace,),
        ).fetchone()[0]
        checks["registry_failed_first_use_atomic"] = (
            isinstance(failed, OrchestrationContractError)
            and failed.code == "VARIANT_VALIDATION_STALE"
            and registry_count == 0
            and reservation_count == 0
        )
    return checks


def _completion_probes(dsn: str) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    with psycopg.connect(dsn, autocommit=True) as connection:
        workspace = _workspace(connection, "completion")
        _batch(connection, workspace, "batch-1", 10)
        connection.execute(
            "INSERT INTO controlplane.cp_artifact_versions (artifact_version_id,workspace_id,artifact_id,sha256_hash,size_bytes,mime_type,artifact_kind,owner_ref,retention_ref,sensitivity_ref) VALUES (%s,%s,'artifact',%s,1,'video/mp4','rendered_video','owner','retention','internal')",
            (ARTIFACT, workspace, HASH_A),
        )
        for job in ("job-direct", "job-mismatch", "job-fault", "job-race"):
            _completion_parent(connection, workspace, job)
        direct_values = _completion_values(workspace, "job-direct")
        _direct_ledger(connection, direct_values)
        before = _ledger_row(connection, workspace, "job-direct")
        rejected = _integrity_rejected(
            connection, lambda: _direct_ledger(connection, direct_values)
        )
        after = _ledger_row(connection, workspace, "job-direct")
        checks["second_completion_rejected"] = (
            rejected
            and before == after
            and connection.execute(
                "SELECT count(*) FROM controlplane.cp_completion_ledger WHERE workspace_id=%s AND job_id='job-direct'",
                (workspace,),
            ).fetchone()[0]
            == 1
        )
        mismatch_values = _completion_values(workspace, "job-mismatch")
        hash_rejected = _integrity_rejected(
            connection,
            lambda: _direct_ledger(
                connection, {**mismatch_values, "output_artifact_hash": "b" * 64}
            ),
        )
        checks["artifact_hash_mismatch_rejected"] = (
            hash_rejected and _ledger_row(connection, workspace, "job-mismatch") is None
        )
        binding_rejected = _integrity_rejected(
            connection,
            lambda: _direct_ledger(
                connection,
                {
                    **mismatch_values,
                    "capacity_reservation_id": "capacity-job-direct",
                    "variant_reservation_id": "variant-job-direct",
                },
            ),
        )
        checks["reservation_job_mismatch_rejected"] = (
            binding_rejected
            and _ledger_row(connection, workspace, "job-mismatch") is None
        )

    def fault(boundary: str) -> None:
        if boundary == "before_ledger_insert":
            raise RuntimeError("injected completion failure")

    try:
        _service_call(
            dsn,
            COMPLETION.commit,
            {**_completion_values(workspace, "job-fault"), "fault_hook": fault},
        )
    except RuntimeError as error:
        injected = str(error) == "injected completion failure"
    else:
        injected = False
    with psycopg.connect(dsn, autocommit=True) as connection:
        states = connection.execute(
            "SELECT j.status,c.state,v.state FROM controlplane.cp_video_jobs j JOIN controlplane.cp_batch_capacity_reservations c USING (workspace_id,job_id) JOIN controlplane.cp_variant_reservations v USING (workspace_id,job_id) WHERE j.workspace_id=%s AND j.job_id='job-fault'",
            (workspace,),
        ).fetchone()
        checks["completion_fault_zero_mutation"] = (
            injected
            and _ledger_row(connection, workspace, "job-fault") is None
            and states == ("READY_FOR_COMPLETION", "ACTIVE", "ACTIVE")
        )
    values = _completion_values(workspace, "job-race")
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(
            executor.map(lambda _: _outcome(dsn, COMPLETION.commit, values), range(2))
        )
    with psycopg.connect(dsn, autocommit=True) as connection:
        race_before = _ledger_row(connection, workspace, "job-race")
        count = connection.execute(
            "SELECT count(*) FROM controlplane.cp_completion_ledger WHERE workspace_id=%s AND job_id='job-race'",
            (workspace,),
        ).fetchone()[0]
        checks["duplicate_completion_one_identity"] = (
            len(outcomes) == 2
            and all(isinstance(item, CompletionLedger) for item in outcomes)
            and outcomes[0].ledger_id == outcomes[1].ledger_id
            and count == 1
            and race_before is not None
            and str(race_before[0]) == outcomes[0].ledger_id
        )
    changed = _outcome(
        dsn, COMPLETION.commit, {**values, "actor_ref": "different-actor"}
    )
    with psycopg.connect(dsn, autocommit=True) as connection:
        race_after = _ledger_row(connection, workspace, "job-race")
        count_after = connection.execute(
            "SELECT count(*) FROM controlplane.cp_completion_ledger WHERE workspace_id=%s AND job_id='job-race'",
            (workspace,),
        ).fetchone()[0]
        checks["different_completion_input_forbidden_unchanged"] = (
            isinstance(changed, OrchestrationContractError)
            and changed.code == "FORBIDDEN_TRANSITION"
            and race_before == race_after
            and count_after == 1
        )
    return checks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    args = parser.parse_args()
    checks: dict[str, bool] = {}
    with _database(os.environ["M2_TEST_PG_DSN"]) as dsn:
        migration_checks, forward_tracker, rollback_tracker = _migration_probes(dsn)
        checks.update(migration_checks)
        for group in (
            _binding_probes,
            _capacity_probes,
            _variant_probes,
            _completion_probes,
        ):
            checks.update(group(dsn))
    result = {
        "verdict": "PASS" if all(checks.values()) else "FAIL",
        "count": len(checks),
        "checks": checks,
        "migration_tracker_before_rollback": forward_tracker,
        "migration_tracker_after_rollback": rollback_tracker,
    }
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    if result["verdict"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
