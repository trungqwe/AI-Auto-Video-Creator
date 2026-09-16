CREATE TABLE controlplane.cp_production_batches (
    batch_id TEXT NOT NULL,
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    status TEXT NOT NULL CHECK (status IN ('CREATED','RUNNING','WAITING_CAPABILITY','COMPLETED_TARGET','COMPLETED_EXHAUSTED','FAILED_SYSTEM')),
    target_count INTEGER NOT NULL CHECK (target_count > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, batch_id)
);

CREATE TABLE controlplane.cp_video_jobs (
    job_id TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    workspace_id UUID NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('CREATED','SNAPSHOTTED','ACTIVE','WAITING','READY_FOR_COMPLETION','COMPLETED','FAILED_FINAL')),
    snapshot_ref TEXT NOT NULL CHECK (btrim(snapshot_ref) <> ''),
    revision BIGINT NOT NULL CHECK (revision >= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, job_id),
    UNIQUE (workspace_id, job_id, batch_id),
    FOREIGN KEY (workspace_id, batch_id) REFERENCES controlplane.cp_production_batches(workspace_id, batch_id) ON DELETE RESTRICT
);

CREATE TABLE controlplane.cp_stage_runs (
    stage_run_id TEXT NOT NULL,
    workspace_id UUID NOT NULL,
    job_id TEXT NOT NULL,
    stage_name TEXT NOT NULL CHECK (btrim(stage_name) <> ''),
    attempt INTEGER NOT NULL CHECK (attempt > 0),
    status TEXT NOT NULL CHECK (status IN ('PENDING','WAITING_DEPENDENCY','WAITING_CAPABILITY','RUNNING','SUCCEEDED','FAILED_RETRYABLE','FAILED_FINAL','OUTCOME_UNKNOWN','STALE')),
    recovery_epoch BIGINT NOT NULL CHECK (recovery_epoch >= 0),
    execution_generation BIGINT NOT NULL CHECK (execution_generation >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, stage_run_id),
    FOREIGN KEY (workspace_id, job_id) REFERENCES controlplane.cp_video_jobs(workspace_id, job_id) ON DELETE RESTRICT
);

CREATE TABLE controlplane.cp_variant_registry (
    workspace_id UUID PRIMARY KEY REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    current_registry_revision BIGINT NOT NULL CHECK (current_registry_revision >= 0)
);

CREATE TABLE controlplane.cp_batch_capacity_reservations (
    reservation_id TEXT NOT NULL,
    workspace_id UUID NOT NULL,
    batch_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('ACTIVE','CONVERTED','RELEASED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, reservation_id),
    UNIQUE (workspace_id, job_id),
    UNIQUE (workspace_id, reservation_id, batch_id, job_id),
    FOREIGN KEY (workspace_id, job_id, batch_id) REFERENCES controlplane.cp_video_jobs(workspace_id, job_id, batch_id) ON DELETE RESTRICT
);

CREATE TABLE controlplane.cp_variant_reservations (
    reservation_id TEXT NOT NULL,
    workspace_id UUID NOT NULL,
    job_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL CHECK (btrim(fingerprint) <> ''),
    snapshot_scope TEXT NOT NULL CHECK (btrim(snapshot_scope) <> ''),
    validation_ref TEXT NOT NULL CHECK (btrim(validation_ref) <> ''),
    variation_policy_revision TEXT NOT NULL CHECK (btrim(variation_policy_revision) <> ''),
    expected_registry_revision BIGINT NOT NULL CHECK (expected_registry_revision >= 0),
    committed_registry_revision BIGINT NOT NULL CHECK (committed_registry_revision >= 0),
    state TEXT NOT NULL CHECK (state IN ('ACTIVE','CONVERTED','RELEASED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, reservation_id),
    UNIQUE (workspace_id, job_id),
    UNIQUE (workspace_id, reservation_id, job_id),
    FOREIGN KEY (workspace_id, job_id) REFERENCES controlplane.cp_video_jobs(workspace_id, job_id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX cp_variant_reservations_live_fingerprint
ON controlplane.cp_variant_reservations (workspace_id, fingerprint)
WHERE state IN ('ACTIVE', 'CONVERTED');

CREATE TABLE controlplane.cp_completion_ledger (
    ledger_id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL,
    job_id TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    capacity_reservation_id TEXT NOT NULL,
    variant_reservation_id TEXT NOT NULL,
    output_artifact_version_id UUID NOT NULL,
    output_artifact_hash TEXT NOT NULL CHECK (output_artifact_hash ~ '^[0-9a-f]{64}$'),
    actor_ref TEXT NOT NULL CHECK (btrim(actor_ref) <> ''),
    completed_at TIMESTAMPTZ NOT NULL,
    audit_ref TEXT NOT NULL CHECK (btrim(audit_ref) <> ''),
    UNIQUE (workspace_id, job_id),
    FOREIGN KEY (workspace_id, job_id, batch_id) REFERENCES controlplane.cp_video_jobs(workspace_id, job_id, batch_id) ON DELETE RESTRICT,
    FOREIGN KEY (workspace_id, capacity_reservation_id, batch_id, job_id) REFERENCES controlplane.cp_batch_capacity_reservations(workspace_id, reservation_id, batch_id, job_id) ON DELETE RESTRICT,
    FOREIGN KEY (workspace_id, variant_reservation_id, job_id) REFERENCES controlplane.cp_variant_reservations(workspace_id, reservation_id, job_id) ON DELETE RESTRICT,
    FOREIGN KEY (workspace_id, output_artifact_version_id, output_artifact_hash) REFERENCES controlplane.cp_artifact_versions(workspace_id, artifact_version_id, sha256_hash) ON DELETE RESTRICT
);
