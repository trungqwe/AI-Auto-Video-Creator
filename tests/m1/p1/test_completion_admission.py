import importlib
import importlib.util
import sys
from pathlib import Path

import psycopg
import pytest


ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "src"))
SCHEMA = ROOT / "sql" / "m1" / "p1_schema.sql"
DSN = "postgresql://postgres@127.0.0.1:55432/aiavc_m1"
OUTPUT_HASH = "sha256:" + "a" * 64


def test_completion_rejects_unverified_admission_without_state_change() -> None:
    with psycopg.connect(DSN, autocommit=True) as connection:
        connection.execute(SCHEMA.read_text(encoding="utf-8"))
        connection.execute("SELECT m1_p1_reset()")
    assert importlib.util.find_spec("m1proof.completion_admission") is not None
    contracts = importlib.import_module("m1proof.contracts")
    media = importlib.import_module("m1proof.media_usage")
    admission = importlib.import_module("m1proof.completion_admission")
    service = contracts.ContractProofService(DSN)
    service.set_workspace_epoch(
        workspace_id="workspace-1", recovery_epoch="epoch-1", epoch_sequence=1
    )
    with psycopg.connect(DSN) as connection:
        connection.execute(
            "INSERT INTO proof_batches VALUES ('workspace-1', 'batch-1', 1, 0)"
        )
        connection.execute(
            "INSERT INTO proof_video_jobs VALUES ('workspace-1', 'job-1', 'batch-1', 'running', NULL, NULL)"
        )
        connection.execute(
            "INSERT INTO batch_capacity_reservations VALUES ('workspace-1', 'capacity-1', 'batch-1', 'job-1', 'active')"
        )
        connection.execute("INSERT INTO variant_registries VALUES ('workspace-1', 1)")
        connection.execute(
            "INSERT INTO variant_reservations VALUES ('workspace-1', 'variant-1', 'job-1', %s, 'active')",
            (OUTPUT_HASH,),
        )
        connection.execute(
            "INSERT INTO execution_fences VALUES ('workspace-1', 'grant-1', 1, 'epoch-1', now())"
        )
        connection.execute(
            """
            INSERT INTO completion_admissions (
                workspace_id, job_id, output_artifact_id, output_hash,
                quality_report_ref, cloud_location_ref,
                snapshot_ref, script_ref, plan_ref, variant_validation_ref,
                output_metadata_ref, expected_variant_registry_revision,
                quality_passed, cloud_verified, admitted_at
            ) VALUES ('workspace-1', 'job-1', 'artifact-1', %s,
                      'quality-1', 'cloud-1', 'snapshot-1', 'script-1',
                      'plan-1', 'variant-1', 'metadata-1', 1,
                      false, true, now())
            """,
            (OUTPUT_HASH,),
        )
    command = contracts.CompletionCommand(
        command_id="command-1", idempotency_key="complete-1",
        workspace_id="workspace-1", job_id="job-1", batch_id="batch-1",
        capacity_reservation_id="capacity-1", variant_reservation_id="variant-1",
        expected_variant_registry_revision=1, output_artifact_id="artifact-1",
        output_hash=OUTPUT_HASH, cloud_location_ref="cloud-1", snapshot_ref="snapshot-1",
        script_ref="script-1", plan_ref="plan-1", quality_report_ref="quality-1",
        variant_validation_ref="variant-1", output_metadata_ref="metadata-1",
        cleanup_policy_ref="cleanup-1", grant_id="grant-1", execution_generation=1,
        recovery_epoch="epoch-1", media_usages=[]
    )

    with pytest.raises(contracts.ContractProofError, match="COMPLETION_NOT_ADMITTED"):
        service.complete_video(
            command,
            media_usage_port=media.PostgresMediaUsageOwnerPort(),
            completion_admission_port=admission.PostgresCompletionAdmissionOwnerPort(),
        )
    with psycopg.connect(DSN) as connection:
        assert connection.execute("SELECT count(*) FROM completion_ledgers").fetchone()[0] == 0
        assert connection.execute("SELECT state FROM proof_video_jobs").fetchone()[0] == "running"
        connection.execute(
            "UPDATE completion_admissions SET quality_passed = true"
        )

    with pytest.raises(contracts.ContractProofError, match="COMPLETION_NOT_ADMITTED"):
        service.complete_video(
            command.model_copy(update={"script_ref": "unowned-script"}),
            media_usage_port=media.PostgresMediaUsageOwnerPort(),
            completion_admission_port=admission.PostgresCompletionAdmissionOwnerPort(),
        )
