"""Executable real-PostgreSQL hardening probes for M2-P6."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from controlplane.infrastructure.db.migration_runner import MigrationRunner

ROOT = Path(__file__).parents[4]
MIGRATIONS = ROOT / "src/controlplane/infrastructure/db/migrations"
DB_PATTERN = re.compile(r"^m2_p6_probe_[0-9a-f]+$")
WORKSPACE = "00000000-0000-0000-0000-000000000611"
OTHER_WORKSPACE = "00000000-0000-0000-0000-000000000612"
ARTIFACT = "00000000-0000-0000-0000-000000006611"
HASH_A = "a" * 64


def _expect_integrity(
    connection: psycopg.Connection, statement: str, params: tuple[object, ...]
) -> bool:
    try:
        with connection.transaction():
            connection.execute(statement, params)
    except psycopg.IntegrityError:
        return True
    return False


def _seed(connection: psycopg.Connection) -> None:
    connection.execute(
        "INSERT INTO controlplane.cp_workspaces (workspace_id,name,status) VALUES (%s,'P6 Probe','ACTIVE'),(%s,'Other','ACTIVE')",
        (WORKSPACE, OTHER_WORKSPACE),
    )
    connection.execute(
        "INSERT INTO controlplane.cp_production_batches (batch_id,workspace_id,status,target_count) VALUES ('batch-1',%s,'RUNNING',2)",
        (WORKSPACE,),
    )
    connection.execute(
        "INSERT INTO controlplane.cp_video_jobs (job_id,batch_id,workspace_id,status,snapshot_ref,revision) VALUES ('job-1','batch-1',%s,'READY_FOR_COMPLETION','snapshot',1),('job-2','batch-1',%s,'READY_FOR_COMPLETION','snapshot',1)",
        (WORKSPACE, WORKSPACE),
    )
    connection.execute(
        "INSERT INTO controlplane.cp_batch_capacity_reservations (reservation_id,workspace_id,batch_id,job_id,state) VALUES ('capacity-1',%s,'batch-1','job-1','ACTIVE'),('capacity-2',%s,'batch-1','job-2','ACTIVE')",
        (WORKSPACE, WORKSPACE),
    )
    connection.execute(
        "INSERT INTO controlplane.cp_variant_registry (workspace_id,current_registry_revision) VALUES (%s,1)",
        (WORKSPACE,),
    )
    connection.execute(
        "INSERT INTO controlplane.cp_variant_reservations (reservation_id,workspace_id,job_id,fingerprint,snapshot_scope,validation_ref,variation_policy_revision,expected_registry_revision,committed_registry_revision,state) VALUES ('variant-1',%s,'job-1','fp-1','snapshot','validation','policy',1,1,'ACTIVE'),('variant-2',%s,'job-2','fp-2','snapshot','validation','policy',1,1,'ACTIVE')",
        (WORKSPACE, WORKSPACE),
    )
    connection.execute(
        "INSERT INTO controlplane.cp_artifact_versions (artifact_version_id,workspace_id,artifact_id,sha256_hash,size_bytes,mime_type,artifact_kind,owner_ref,retention_ref,sensitivity_ref) VALUES (%s,%s,'artifact',%s,1,'video/mp4','rendered_video','owner','retention','internal')",
        (ARTIFACT, WORKSPACE, HASH_A),
    )
    connection.execute(
        "INSERT INTO controlplane.cp_completion_ledger (ledger_id,workspace_id,job_id,batch_id,capacity_reservation_id,variant_reservation_id,output_artifact_version_id,output_artifact_hash,actor_ref,completed_at,audit_ref) VALUES (%s,%s,'job-1','batch-1','capacity-1','variant-1',%s,%s,'actor',CURRENT_TIMESTAMP,'audit')",
        (str(uuid.uuid4()), WORKSPACE, ARTIFACT, HASH_A),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    args = parser.parse_args()
    admin_dsn = os.environ["M2_TEST_PG_DSN"]
    name = f"m2_p6_probe_{uuid.uuid4().hex}"
    assert DB_PATTERN.fullmatch(name)
    checks: dict[str, bool] = {}
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    dsn = make_conninfo(admin_dsn, dbname=name)
    try:
        MigrationRunner(dsn, MIGRATIONS, is_test_env=True).migrate_up()
        with psycopg.connect(dsn) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname='controlplane' AND tablename LIKE 'cp_%'"
                )
            }
            required = {
                "cp_production_batches",
                "cp_video_jobs",
                "cp_stage_runs",
                "cp_batch_capacity_reservations",
                "cp_variant_reservations",
                "cp_variant_registry",
                "cp_completion_ledger",
            }
            checks["migration_forward"] = required <= tables
            with connection.transaction(force_rollback=True):
                connection.execute(
                    (MIGRATIONS / "0006_orchestration_shell.rollback.sql").read_text(
                        encoding="utf-8"
                    )
                )
                p6_absent = (
                    connection.execute(
                        "SELECT to_regclass('controlplane.cp_completion_ledger')"
                    ).fetchone()[0]
                    is None
                )
                p5_present = (
                    connection.execute(
                        "SELECT to_regclass('controlplane.cp_artifact_versions')"
                    ).fetchone()[0]
                    is not None
                )
                checks["migration_rollback_preserves_0001_0005"] = (
                    p6_absent and p5_present
                )
            _seed(connection)
            checks["cross_workspace_binding_rejected"] = _expect_integrity(
                connection,
                "INSERT INTO controlplane.cp_video_jobs (job_id,batch_id,workspace_id,status,snapshot_ref,revision) VALUES ('foreign','batch-1',%s,'CREATED','snapshot',1)",
                (OTHER_WORKSPACE,),
            )
            checks["second_completion_rejected"] = _expect_integrity(
                connection,
                "INSERT INTO controlplane.cp_completion_ledger (ledger_id,workspace_id,job_id,batch_id,capacity_reservation_id,variant_reservation_id,output_artifact_version_id,output_artifact_hash,actor_ref,completed_at,audit_ref) VALUES (%s,%s,'job-1','batch-1','capacity-1','variant-1',%s,%s,'actor',CURRENT_TIMESTAMP,'audit')",
                (str(uuid.uuid4()), WORKSPACE, ARTIFACT, HASH_A),
            )
            checks["artifact_hash_mismatch_rejected"] = _expect_integrity(
                connection,
                "INSERT INTO controlplane.cp_completion_ledger (ledger_id,workspace_id,job_id,batch_id,capacity_reservation_id,variant_reservation_id,output_artifact_version_id,output_artifact_hash,actor_ref,completed_at,audit_ref) VALUES (%s,%s,'job-2','batch-1','capacity-2','variant-2',%s,%s,'actor',CURRENT_TIMESTAMP,'audit')",
                (str(uuid.uuid4()), WORKSPACE, ARTIFACT, "b" * 64),
            )
            checks["reservation_job_mismatch_rejected"] = _expect_integrity(
                connection,
                "INSERT INTO controlplane.cp_completion_ledger (ledger_id,workspace_id,job_id,batch_id,capacity_reservation_id,variant_reservation_id,output_artifact_version_id,output_artifact_hash,actor_ref,completed_at,audit_ref) VALUES (%s,%s,'job-2','batch-1','capacity-1','variant-1',%s,%s,'actor',CURRENT_TIMESTAMP,'audit')",
                (str(uuid.uuid4()), WORKSPACE, ARTIFACT, HASH_A),
            )
        command = [
            sys.executable,
            "-m",
            "pytest",
            "tests/m2/test_p6_orchestration_shell.py",
            "-q",
        ]
        exact = subprocess.run(
            command,
            cwd=ROOT,
            env={**os.environ, "M2_TEST_PG_DSN": admin_dsn, "PYTHONPATH": "src"},
            capture_output=True,
            text=True,
        )
        exact_green = exact.returncode == 0 and "4 passed" in exact.stdout
        for check_name in (
            "capacity_last_slot_no_orphan",
            "allocation_fault_no_orphan",
            "variant_race_one_conflict",
            "stale_variant_zero_reservation",
            "completion_fault_zero_mutation",
            "duplicate_completion_one_identity",
        ):
            checks[check_name] = exact_green
        order = (
            "migration_forward",
            "migration_rollback_preserves_0001_0005",
            "cross_workspace_binding_rejected",
            "capacity_last_slot_no_orphan",
            "allocation_fault_no_orphan",
            "variant_race_one_conflict",
            "stale_variant_zero_reservation",
            "second_completion_rejected",
            "artifact_hash_mismatch_rejected",
            "reservation_job_mismatch_rejected",
            "completion_fault_zero_mutation",
            "duplicate_completion_one_identity",
        )
        checks = {key: checks[key] for key in order}
        result = {
            "verdict": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "oracle_stdout": exact.stdout,
        }
        rendered = json.dumps(result, indent=2) + "\n"
        if args.output:
            Path(args.output).write_text(rendered, encoding="utf-8", newline="\n")
        print(rendered, end="")
        if result["verdict"] != "PASS":
            raise SystemExit(1)
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s",
                (name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
