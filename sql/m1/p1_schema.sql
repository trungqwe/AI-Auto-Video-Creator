CREATE TABLE IF NOT EXISTS workspace_epochs (
    workspace_id text PRIMARY KEY,
    recovery_epoch text NOT NULL,
    epoch_sequence bigint NOT NULL CHECK (epoch_sequence > 0),
    updated_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS proof_aggregates (
    workspace_id text NOT NULL,
    aggregate_id text NOT NULL,
    revision integer NOT NULL CHECK (revision > 0),
    payload jsonb NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (workspace_id, aggregate_id)
);

CREATE TABLE IF NOT EXISTS command_receipts (
    workspace_id text NOT NULL,
    idempotency_key text NOT NULL,
    command_id text NOT NULL,
    receipt_id text NOT NULL,
    payload_fingerprint text NOT NULL,
    disposition text NOT NULL,
    resource_revision integer NOT NULL,
    result jsonb NOT NULL,
    recovery_epoch text NOT NULL,
    execution_generation integer NOT NULL,
    accepted_at timestamptz NOT NULL,
    PRIMARY KEY (workspace_id, idempotency_key),
    UNIQUE (receipt_id)
);

CREATE TABLE IF NOT EXISTS outbox_events (
    event_id text PRIMARY KEY,
    workspace_id text NOT NULL,
    aggregate_type text NOT NULL,
    aggregate_id text NOT NULL,
    aggregate_revision integer NOT NULL,
    event_name text NOT NULL,
    recovery_epoch text NOT NULL,
    payload jsonb NOT NULL,
    occurred_at timestamptz NOT NULL,
    published_at timestamptz
);

CREATE TABLE IF NOT EXISTS consumer_event_receipts (
    consumer_id text NOT NULL,
    event_id text NOT NULL,
    observed_at timestamptz NOT NULL,
    PRIMARY KEY (consumer_id, event_id)
);

CREATE TABLE IF NOT EXISTS consumer_projections (
    consumer_id text NOT NULL,
    workspace_id text NOT NULL,
    aggregate_id text NOT NULL,
    aggregate_revision integer NOT NULL CHECK (aggregate_revision > 0),
    payload jsonb NOT NULL,
    apply_count integer NOT NULL CHECK (apply_count > 0),
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (consumer_id, workspace_id, aggregate_id)
);

CREATE TABLE IF NOT EXISTS execution_fences (
    workspace_id text NOT NULL,
    grant_id text NOT NULL,
    execution_generation integer NOT NULL CHECK (execution_generation > 0),
    recovery_epoch text NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (workspace_id, grant_id)
);

CREATE TABLE IF NOT EXISTS accepted_activity_results (
    result_id text PRIMARY KEY,
    workspace_id text NOT NULL,
    grant_id text NOT NULL,
    execution_generation integer NOT NULL,
    recovery_epoch text NOT NULL,
    payload jsonb NOT NULL,
    committed_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS execution_grants_v2 (
    workspace_id text NOT NULL,
    grant_id text NOT NULL,
    operation_key text NOT NULL,
    input_fingerprint text NOT NULL,
    execution_generation integer NOT NULL CHECK (execution_generation > 0),
    recovery_epoch text NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (workspace_id, grant_id)
);

CREATE TABLE IF NOT EXISTS accepted_activity_results_v2 (
    workspace_id text NOT NULL,
    operation_key text NOT NULL,
    result_id text NOT NULL,
    receipt_id text NOT NULL,
    input_fingerprint text NOT NULL,
    result_fingerprint text NOT NULL,
    grant_id text NOT NULL,
    execution_generation integer NOT NULL,
    recovery_epoch text NOT NULL,
    payload jsonb NOT NULL,
    committed_at timestamptz NOT NULL,
    PRIMARY KEY (workspace_id, operation_key),
    UNIQUE (workspace_id, result_id),
    UNIQUE (receipt_id)
);

CREATE TABLE IF NOT EXISTS operation_receipts (
    operation_key text PRIMARY KEY,
    receipt_id text NOT NULL UNIQUE,
    workspace_id text NOT NULL,
    operation_type text NOT NULL,
    input_fingerprint text NOT NULL,
    recovery_epoch text NOT NULL,
    state text NOT NULL CHECK (
        state IN ('prepared', 'started', 'outcome_unknown', 'succeeded', 'failed')
    ),
    output_refs jsonb NOT NULL DEFAULT '{}'::jsonb,
    attempt integer NOT NULL CHECK (attempt > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS operation_receipts_v2 (
    workspace_id text NOT NULL,
    operation_key text NOT NULL,
    receipt_id text NOT NULL UNIQUE,
    operation_type text NOT NULL,
    input_fingerprint text NOT NULL,
    recovery_epoch text NOT NULL,
    state text NOT NULL CHECK (
        state IN ('prepared', 'started', 'outcome_unknown', 'succeeded', 'failed')
    ),
    output_refs jsonb NOT NULL DEFAULT '{}'::jsonb,
    attempt integer NOT NULL CHECK (attempt > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (workspace_id, operation_key)
);

CREATE TABLE IF NOT EXISTS proof_batches (
    workspace_id text NOT NULL,
    batch_id text NOT NULL,
    target_count integer NOT NULL CHECK (target_count > 0),
    completed_count integer NOT NULL DEFAULT 0 CHECK (completed_count >= 0),
    PRIMARY KEY (workspace_id, batch_id),
    CHECK (completed_count <= target_count)
);

CREATE TABLE IF NOT EXISTS completion_admissions (
    workspace_id text NOT NULL,
    job_id text NOT NULL,
    output_artifact_id text NOT NULL,
    output_hash text NOT NULL,
    quality_report_ref text NOT NULL,
    cloud_location_ref text NOT NULL,
    snapshot_ref text NOT NULL,
    script_ref text NOT NULL,
    plan_ref text NOT NULL,
    variant_validation_ref text NOT NULL,
    output_metadata_ref text NOT NULL,
    expected_variant_registry_revision integer NOT NULL,
    quality_passed boolean NOT NULL,
    cloud_verified boolean NOT NULL,
    admitted_at timestamptz NOT NULL,
    PRIMARY KEY (workspace_id, job_id)
);

ALTER TABLE completion_admissions ADD COLUMN IF NOT EXISTS snapshot_ref text;
ALTER TABLE completion_admissions ADD COLUMN IF NOT EXISTS script_ref text;
ALTER TABLE completion_admissions ADD COLUMN IF NOT EXISTS plan_ref text;
ALTER TABLE completion_admissions ADD COLUMN IF NOT EXISTS variant_validation_ref text;
ALTER TABLE completion_admissions ADD COLUMN IF NOT EXISTS output_metadata_ref text;
ALTER TABLE completion_admissions ADD COLUMN IF NOT EXISTS expected_variant_registry_revision integer;

CREATE TABLE IF NOT EXISTS proof_video_jobs (
    workspace_id text NOT NULL,
    job_id text NOT NULL,
    batch_id text NOT NULL,
    state text NOT NULL CHECK (state IN ('running', 'completed', 'failed', 'cancelled')),
    output_hash text,
    completed_at timestamptz,
    PRIMARY KEY (workspace_id, job_id)
);

CREATE TABLE IF NOT EXISTS batch_capacity_reservations (
    workspace_id text NOT NULL,
    reservation_id text NOT NULL,
    batch_id text NOT NULL,
    job_id text NOT NULL,
    state text NOT NULL CHECK (state IN ('active', 'converted', 'released')),
    PRIMARY KEY (workspace_id, reservation_id),
    UNIQUE (workspace_id, job_id)
);

CREATE TABLE IF NOT EXISTS variant_registries (
    workspace_id text PRIMARY KEY,
    revision integer NOT NULL CHECK (revision > 0)
);

CREATE TABLE IF NOT EXISTS variant_reservations (
    workspace_id text NOT NULL,
    reservation_id text NOT NULL,
    job_id text NOT NULL,
    output_hash text NOT NULL,
    state text NOT NULL CHECK (state IN ('active', 'converted', 'released')),
    PRIMARY KEY (workspace_id, reservation_id),
    UNIQUE (workspace_id, job_id)
);

CREATE TABLE IF NOT EXISTS completion_ledgers (
    workspace_id text NOT NULL,
    completion_id text NOT NULL,
    receipt_id text NOT NULL,
    command_id text NOT NULL,
    idempotency_key text NOT NULL,
    input_fingerprint text NOT NULL,
    job_id text NOT NULL,
    batch_id text NOT NULL,
    output_artifact_id text NOT NULL,
    output_hash text NOT NULL,
    cloud_location_ref text NOT NULL,
    snapshot_ref text NOT NULL,
    script_ref text NOT NULL,
    plan_ref text NOT NULL,
    quality_report_ref text NOT NULL,
    variant_validation_ref text NOT NULL,
    output_metadata_ref text NOT NULL,
    cleanup_policy_ref text NOT NULL,
    media_usage_manifest jsonb NOT NULL,
    variant_registry_revision integer NOT NULL,
    completed_count integer NOT NULL,
    completed_at timestamptz NOT NULL,
    PRIMARY KEY (workspace_id, completion_id),
    UNIQUE (workspace_id, receipt_id),
    UNIQUE (workspace_id, idempotency_key),
    UNIQUE (workspace_id, job_id)
);

-- This proof table is owned through the media application port, not by G directly.
CREATE TABLE IF NOT EXISTS media_usages (
    workspace_id text NOT NULL,
    usage_id text NOT NULL,
    completion_id text NOT NULL,
    job_id text NOT NULL,
    media_id text NOT NULL,
    artifact_id text NOT NULL,
    role text NOT NULL,
    time_range text NOT NULL,
    transform_ref text NOT NULL,
    selection_rationale text NOT NULL,
    completed_at timestamptz NOT NULL,
    PRIMARY KEY (workspace_id, usage_id),
    UNIQUE (workspace_id, completion_id, media_id, artifact_id, role, time_range)
);

CREATE TABLE IF NOT EXISTS cleanup_eligibilities (
    workspace_id text NOT NULL,
    eligibility_id text NOT NULL,
    completion_id text NOT NULL,
    job_id text NOT NULL,
    output_hash text NOT NULL,
    cleanup_policy_ref text NOT NULL,
    recovery_epoch text NOT NULL,
    state text NOT NULL CHECK (state IN ('eligible', 'consumed', 'revoked')),
    created_at timestamptz NOT NULL,
    PRIMARY KEY (workspace_id, eligibility_id),
    UNIQUE (workspace_id, completion_id)
);

CREATE OR REPLACE FUNCTION m1_p1_reset()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    TRUNCATE TABLE
        cleanup_eligibilities,
        media_usages,
        completion_ledgers,
        variant_reservations,
        variant_registries,
        batch_capacity_reservations,
        proof_video_jobs,
        proof_batches,
        completion_admissions,
        operation_receipts_v2,
        operation_receipts,
        accepted_activity_results_v2,
        execution_grants_v2,
        accepted_activity_results,
        execution_fences,
        consumer_projections,
        consumer_event_receipts,
        outbox_events,
        command_receipts,
        proof_aggregates,
        workspace_epochs;
END;
$$;
