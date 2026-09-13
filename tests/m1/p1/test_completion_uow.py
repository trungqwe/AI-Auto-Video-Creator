import importlib
import importlib.util
import sys
from pathlib import Path

import psycopg
import pytest


REPOSITORY_ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

SCHEMA_PATH = REPOSITORY_ROOT / "sql" / "m1" / "p1_schema.sql"
DSN = "postgresql://postgres@127.0.0.1:55432/aiavc_m1"
OUTPUT_HASH = "sha256:" + "a" * 64


def prepare_database() -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with psycopg.connect(DSN, autocommit=True) as connection:
        connection.execute(schema)
        connection.execute("SELECT m1_p1_reset()")


def load_completion_api():
    contracts = importlib.import_module("m1proof.contracts")
    media_spec = importlib.util.find_spec("m1proof.media_usage")
    required = ["CompletionCommand", "CompletionReceipt"]
    missing = [name for name in required if not hasattr(contracts, name)]
    if media_spec is None:
        missing.append("m1proof.media_usage.PostgresMediaUsageOwnerPort")
    assert not missing, f"P1 completion API is not implemented: {', '.join(missing)}"
    media_usage = importlib.import_module("m1proof.media_usage")
    completion_admission = importlib.import_module("m1proof.completion_admission")
    assert hasattr(media_usage, "PostgresMediaUsageOwnerPort"), (
        "P1 media usage owner port is not implemented"
    )
    return contracts, media_usage, completion_admission


def seed_completion_context() -> None:
    with psycopg.connect(DSN) as connection:
        connection.execute(
            """
            INSERT INTO workspace_epochs
                (workspace_id, recovery_epoch, epoch_sequence, updated_at)
            VALUES ('workspace-1', 'epoch-current', 1, now())
            """
        )
        connection.execute(
            """
            INSERT INTO proof_batches (workspace_id, batch_id, target_count, completed_count)
            VALUES ('workspace-1', 'batch-1', 1, 0)
            """
        )
        connection.execute(
            """
            INSERT INTO proof_video_jobs (workspace_id, job_id, batch_id, state)
            VALUES ('workspace-1', 'job-1', 'batch-1', 'running')
            """
        )
        connection.execute(
            """
            INSERT INTO batch_capacity_reservations (
                workspace_id, reservation_id, batch_id, job_id, state
            ) VALUES ('workspace-1', 'capacity-1', 'batch-1', 'job-1', 'active')
            """
        )
        connection.execute(
            """
            INSERT INTO variant_registries (workspace_id, revision)
            VALUES ('workspace-1', 1)
            """
        )
        connection.execute(
            """
            INSERT INTO variant_reservations (
                workspace_id, reservation_id, job_id, output_hash, state
            ) VALUES ('workspace-1', 'variant-1', 'job-1', %s, 'active')
            """,
            (OUTPUT_HASH,),
        )
        connection.execute(
            """
            INSERT INTO completion_admissions (
                workspace_id, job_id, output_artifact_id, output_hash,
                quality_report_ref, cloud_location_ref,
                snapshot_ref, script_ref, plan_ref, variant_validation_ref,
                output_metadata_ref, expected_variant_registry_revision,
                quality_passed, cloud_verified, admitted_at
            ) VALUES (
                'workspace-1', 'job-1', 'artifact-output-1', %s,
                'quality-report-pass-1', 'drive-location-verified-1',
                'snapshot-1', 'script-1', 'plan-1', 'variant-validation-1',
                'output-metadata-1', 1,
                true, true, now()
            )
            """,
            (OUTPUT_HASH,),
        )
        connection.execute(
            """
            INSERT INTO execution_fences (
                workspace_id, grant_id, execution_generation, recovery_epoch, updated_at
            ) VALUES ('workspace-1', 'grant-completion', 7, 'epoch-current', now())
            """
        )


def make_completion(contracts, *, idempotency_key: str = "complete-job-1"):
    return contracts.CompletionCommand(
        command_id="command-complete-job-1",
        idempotency_key=idempotency_key,
        workspace_id="workspace-1",
        job_id="job-1",
        batch_id="batch-1",
        capacity_reservation_id="capacity-1",
        variant_reservation_id="variant-1",
        expected_variant_registry_revision=1,
        output_artifact_id="artifact-output-1",
        output_hash=OUTPUT_HASH,
        cloud_location_ref="drive-location-verified-1",
        snapshot_ref="snapshot-1",
        script_ref="script-1",
        plan_ref="plan-1",
        quality_report_ref="quality-report-pass-1",
        variant_validation_ref="variant-validation-1",
        output_metadata_ref="output-metadata-1",
        cleanup_policy_ref="cleanup-policy-1",
        grant_id="grant-completion",
        execution_generation=7,
        recovery_epoch="epoch-current",
        media_usages=[
            {
                "media_id": "media-1",
                "artifact_id": "artifact-media-1",
                "role": "hook",
                "time_range": "0.000-3.000",
                "transform_ref": "transform-1",
                "selection_rationale": "hook-index-match",
            },
            {
                "media_id": "media-2",
                "artifact_id": "artifact-media-2",
                "role": "story",
                "time_range": "3.000-12.000",
                "transform_ref": "transform-2",
                "selection_rationale": "entity-match",
            },
        ],
    )


def completion_state() -> tuple[object, ...]:
    with psycopg.connect(DSN) as connection:
        return connection.execute(
            """
            SELECT
                (SELECT count(*) FROM completion_ledgers),
                (SELECT state FROM proof_video_jobs WHERE job_id = 'job-1'),
                (SELECT completed_count FROM proof_batches WHERE batch_id = 'batch-1'),
                (SELECT state FROM batch_capacity_reservations
                  WHERE reservation_id = 'capacity-1'),
                (SELECT state FROM variant_reservations
                  WHERE reservation_id = 'variant-1'),
                (SELECT revision FROM variant_registries
                  WHERE workspace_id = 'workspace-1'),
                (SELECT count(*) FROM media_usages),
                (SELECT count(*) FROM outbox_events
                  WHERE event_name = 'VideoCompleted'),
                (SELECT count(*) FROM cleanup_eligibilities)
            """
        ).fetchone()


@pytest.mark.parametrize(
    "crash_boundary",
    [
        "after_ledger",
        "after_job",
        "after_capacity",
        "after_variant",
        "after_media_usage",
        "after_outbox",
        "after_cleanup_eligibility",
    ],
)
def test_completion_uow_is_atomic_at_every_crash_boundary(crash_boundary: str) -> None:
    prepare_database()
    contracts, media_usage, admission = load_completion_api()
    seed_completion_context()
    service = contracts.ContractProofService(DSN)
    owner_port = media_usage.PostgresMediaUsageOwnerPort()
    admission_port = admission.PostgresCompletionAdmissionOwnerPort()
    command = make_completion(contracts)

    with pytest.raises(contracts.InjectedFailure, match=crash_boundary):
        service.complete_video(
            command,
            media_usage_port=owner_port,
            completion_admission_port=admission_port,
            inject_failure=crash_boundary,
        )

    assert completion_state() == (
        0,
        "running",
        0,
        "active",
        "active",
        1,
        0,
        0,
        0,
    )

    receipt = service.complete_video(
        command,
        media_usage_port=owner_port,
        completion_admission_port=admission_port,
    )
    assert receipt.disposition == "accepted"
    assert receipt.completed_count == 1
    assert receipt.variant_registry_revision == 2
    assert completion_state() == (
        1,
        "completed",
        1,
        "converted",
        "converted",
        2,
        2,
        1,
        1,
    )


def test_lost_ack_and_duplicate_completion_return_one_committed_result() -> None:
    prepare_database()
    contracts, media_usage, admission = load_completion_api()
    seed_completion_context()
    service = contracts.ContractProofService(DSN)
    owner_port = media_usage.PostgresMediaUsageOwnerPort()
    admission_port = admission.PostgresCompletionAdmissionOwnerPort()
    command = make_completion(contracts)

    with pytest.raises(contracts.OutcomeUnknown) as failure:
        service.complete_video(
            command,
            media_usage_port=owner_port,
            completion_admission_port=admission_port,
            inject_failure="after_commit_before_ack",
        )

    duplicate = service.complete_video(
        command,
        media_usage_port=owner_port,
        completion_admission_port=admission_port,
    )
    assert duplicate.disposition == "duplicate"
    assert duplicate.receipt_id == failure.value.receipt_id
    assert duplicate.completed_count == 1
    assert duplicate.variant_registry_revision == 2
    assert completion_state() == (
        1,
        "completed",
        1,
        "converted",
        "converted",
        2,
        2,
        1,
        1,
    )

    changed_output = command.model_copy(
        update={"output_hash": "sha256:" + "b" * 64}
    )
    with pytest.raises(
        contracts.IdempotencyConflict,
        match="IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
    ):
        service.complete_video(
            changed_output,
            media_usage_port=owner_port,
            completion_admission_port=admission_port,
        )
