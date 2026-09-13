CREATE TABLE IF NOT EXISTS workspace_epochs (
    workspace_id text PRIMARY KEY,
    recovery_epoch text NOT NULL,
    epoch_sequence bigint NOT NULL CHECK (epoch_sequence > 0),
    updated_at timestamptz NOT NULL
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
    receipt_id text NOT NULL UNIQUE,
    input_fingerprint text NOT NULL,
    result_fingerprint text NOT NULL,
    grant_id text NOT NULL,
    execution_generation integer NOT NULL,
    recovery_epoch text NOT NULL,
    payload jsonb NOT NULL,
    committed_at timestamptz NOT NULL,
    PRIMARY KEY (workspace_id, operation_key),
    UNIQUE (workspace_id, result_id)
);

CREATE TABLE IF NOT EXISTS operation_receipts_v2 (
    operation_key text NOT NULL,
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
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (workspace_id, operation_key)
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
