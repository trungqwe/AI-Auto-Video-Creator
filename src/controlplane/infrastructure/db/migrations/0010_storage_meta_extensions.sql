-- 0010_storage_meta_extensions.sql
ALTER TABLE controlplane.cp_artifact_versions ADD COLUMN intended_storage_class TEXT NULL, ADD COLUMN producer_operation_ref TEXT NULL, ADD COLUMN lineage_refs JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE controlplane.cp_artifact_locations ADD COLUMN device_ref TEXT NULL, ADD COLUMN logical_category TEXT NULL, ADD COLUMN last_verified_at TIMESTAMPTZ NULL, ADD COLUMN lease_ref TEXT NULL, ADD COLUMN retention_state TEXT NULL, ADD COLUMN cleanup_state TEXT NULL;

ALTER TABLE controlplane.cp_cleanup_authorizations DROP CONSTRAINT cp_cleanup_authorizations_recovery_epoch_check;
ALTER TABLE controlplane.cp_cleanup_authorizations ALTER COLUMN recovery_epoch TYPE TEXT USING recovery_epoch::text;
ALTER TABLE controlplane.cp_cleanup_authorizations ADD CONSTRAINT cp_cleanup_authorizations_recovery_epoch_text_check CHECK (btrim(recovery_epoch) <> '');

CREATE TABLE controlplane.cp_upload_receipts (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    operation_key TEXT NOT NULL,
    artifact_version_id UUID NOT NULL,
    source_location_id UUID NULL,
    target_backend_ref TEXT NOT NULL,
    provider_object_ref TEXT NULL,
    state TEXT NOT NULL CHECK (state IN ('PREPARED','UPLOADING','UPLOADED_UNVERIFIED','VERIFIED','OUTCOME_UNKNOWN','FAILED')),
    verification_evidence_ref TEXT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, operation_key),
    FOREIGN KEY (workspace_id, artifact_version_id) REFERENCES controlplane.cp_artifact_versions (workspace_id, artifact_version_id) ON DELETE RESTRICT
);
CREATE INDEX cp_upload_receipts_state_idx ON controlplane.cp_upload_receipts (workspace_id, state);

CREATE TABLE controlplane.cp_materialization_leases (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    lease_ref TEXT NOT NULL,
    operation_key TEXT NOT NULL,
    device_ref TEXT NOT NULL,
    staging_root_ref TEXT NOT NULL,
    expected_total_bytes BIGINT NOT NULL CHECK (expected_total_bytes >= 0),
    state TEXT NOT NULL CHECK (state IN ('ACTIVE','RELEASED','EXPIRED')),
    expires_at TIMESTAMPTZ NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, lease_ref),
    UNIQUE (workspace_id, operation_key)
);

CREATE TABLE controlplane.cp_revision_placements (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    placement_id TEXT NOT NULL,
    artifact_version_id UUID NOT NULL,
    revision_ref TEXT NOT NULL,
    storage_class TEXT NOT NULL,
    location_id UUID NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, placement_id),
    UNIQUE (workspace_id, artifact_version_id, revision_ref),
    FOREIGN KEY (workspace_id, artifact_version_id) REFERENCES controlplane.cp_artifact_versions (workspace_id, artifact_version_id) ON DELETE RESTRICT,
    FOREIGN KEY (workspace_id, location_id) REFERENCES controlplane.cp_artifact_locations (workspace_id, location_id) ON DELETE RESTRICT
);

CREATE TABLE controlplane.cp_working_set_policies (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    policy_ref TEXT NOT NULL,
    policy_revision BIGINT NOT NULL CHECK (policy_revision >= 1),
    max_videos_per_render BIGINT NOT NULL DEFAULT 5 CHECK (max_videos_per_render > 0),
    max_working_set_bytes BIGINT NULL CHECK (max_working_set_bytes > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, policy_ref, policy_revision)
);
