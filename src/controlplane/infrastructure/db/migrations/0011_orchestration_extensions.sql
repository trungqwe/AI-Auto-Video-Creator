-- 0011_orchestration_extensions.sql
ALTER TABLE controlplane.cp_stage_runs DROP CONSTRAINT cp_stage_runs_recovery_epoch_check;
ALTER TABLE controlplane.cp_stage_runs ALTER COLUMN recovery_epoch TYPE TEXT USING recovery_epoch::text;
ALTER TABLE controlplane.cp_stage_runs ADD CONSTRAINT cp_stage_runs_recovery_epoch_text_check CHECK (btrim(recovery_epoch) <> '');
ALTER TABLE controlplane.cp_stage_runs ADD COLUMN stage_type TEXT NULL, ADD COLUMN input_refs JSONB NOT NULL DEFAULT '[]'::jsonb, ADD COLUMN dependency_refs JSONB NOT NULL DEFAULT '[]'::jsonb, ADD COLUMN wait_reason TEXT NULL, ADD COLUMN problem JSONB NULL, ADD COLUMN started_at TIMESTAMPTZ NULL, ADD COLUMN finished_at TIMESTAMPTZ NULL, ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, ADD COLUMN superseded_by TEXT NULL;

ALTER TABLE controlplane.cp_video_jobs ADD COLUMN wait_reason TEXT NULL, ADD COLUMN parent_variant_ref TEXT NULL, ADD COLUMN prior_variant_ref TEXT NULL;

ALTER TABLE controlplane.cp_completion_ledger ADD COLUMN completion_id TEXT NULL, ADD COLUMN session_ref TEXT NULL, ADD COLUMN cloud_location_ref TEXT NULL, ADD COLUMN cloud_location_verification_ref TEXT NULL, ADD COLUMN snapshot_ref TEXT NULL, ADD COLUMN script_version_ref TEXT NULL, ADD COLUMN production_plan_ref TEXT NULL, ADD COLUMN preset_revision_ref TEXT NULL, ADD COLUMN quality_report_ref TEXT NULL, ADD COLUMN variant_validation_ref TEXT NULL, ADD COLUMN media_usage_manifest JSONB NULL, ADD COLUMN output_naming_metadata JSONB NULL, ADD COLUMN cost_usage_summary JSONB NULL, ADD COLUMN cleanup_policy_ref TEXT NULL;
CREATE UNIQUE INDEX cp_completion_ledger_completion_id_unique ON controlplane.cp_completion_ledger (workspace_id, completion_id) WHERE completion_id IS NOT NULL;

ALTER TABLE controlplane.cp_production_batches ADD COLUMN stop_reason TEXT NULL, ADD COLUMN stopped_at TIMESTAMPTZ NULL;

CREATE TABLE controlplane.cp_execution_grants (
    grant_id TEXT NOT NULL,
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    stage_run_id TEXT NOT NULL,
    execution_generation BIGINT NOT NULL CHECK (execution_generation >= 1),
    recovery_epoch TEXT NOT NULL CHECK (btrim(recovery_epoch) <> ''),
    worker_lease_id TEXT NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    allowed_operation TEXT NOT NULL,
    input_fingerprint TEXT NOT NULL,
    revoked_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (expires_at > issued_at),
    PRIMARY KEY (workspace_id, grant_id),
    UNIQUE (workspace_id, stage_run_id, execution_generation),
    FOREIGN KEY (workspace_id, stage_run_id) REFERENCES controlplane.cp_stage_runs (workspace_id, stage_run_id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX cp_execution_grants_one_active_idx ON controlplane.cp_execution_grants (workspace_id, stage_run_id) WHERE revoked_at IS NULL;

CREATE TABLE controlplane.cp_orchestration_receipts (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    aggregate_ref TEXT NOT NULL,
    aggregate_revision BIGINT NOT NULL CHECK (aggregate_revision >= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, idempotency_key)
);

CREATE TABLE controlplane.cp_cleanup_eligibility (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    cleanup_eligibility_id TEXT NOT NULL,
    video_job_id TEXT NOT NULL,
    artifact_version_id UUID NOT NULL,
    cleanup_policy_ref TEXT NOT NULL,
    eligible_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'ELIGIBLE' CHECK (status IN ('ELIGIBLE','CONSUMED','REVOKED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, cleanup_eligibility_id),
    UNIQUE (workspace_id, video_job_id, artifact_version_id),
    FOREIGN KEY (workspace_id, video_job_id) REFERENCES controlplane.cp_video_jobs (workspace_id, job_id) ON DELETE RESTRICT,
    FOREIGN KEY (workspace_id, artifact_version_id) REFERENCES controlplane.cp_artifact_versions (workspace_id, artifact_version_id) ON DELETE RESTRICT
);

CREATE TABLE controlplane.cp_app_sessions (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    session_ref TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ACTIVE','ENDED','ABANDONED')),
    recovery_epoch TEXT NOT NULL CHECK (btrim(recovery_epoch) <> ''),
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, session_ref)
);
