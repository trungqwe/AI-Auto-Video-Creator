"""Owner-side validation for the M1 completion admission proof."""

import psycopg


class PostgresCompletionAdmissionOwnerPort:
    def require_admitted(
        self,
        connection: psycopg.Connection,
        *,
        workspace_id: str,
        job_id: str,
        output_artifact_id: str,
        output_hash: str,
        quality_report_ref: str,
        cloud_location_ref: str,
        snapshot_ref: str,
        script_ref: str,
        plan_ref: str,
        variant_validation_ref: str,
        output_metadata_ref: str,
        expected_variant_registry_revision: int,
    ) -> bool:
        row = connection.execute(
            """
            SELECT quality_passed, cloud_verified
              FROM completion_admissions
             WHERE workspace_id = %s AND job_id = %s
               AND output_artifact_id = %s AND output_hash = %s
               AND quality_report_ref = %s AND cloud_location_ref = %s
               AND snapshot_ref = %s AND script_ref = %s AND plan_ref = %s
               AND variant_validation_ref = %s AND output_metadata_ref = %s
               AND expected_variant_registry_revision = %s
             FOR UPDATE
            """,
            (
                workspace_id,
                job_id,
                output_artifact_id,
                output_hash,
                quality_report_ref,
                cloud_location_ref,
                snapshot_ref,
                script_ref,
                plan_ref,
                variant_validation_ref,
                output_metadata_ref,
                expected_variant_registry_revision,
            ),
        ).fetchone()
        return row == (True, True)
