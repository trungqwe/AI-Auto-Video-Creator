CREATE TABLE controlplane.cp_artifact_versions (
    artifact_version_id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    artifact_id TEXT NOT NULL,
    sha256_hash TEXT NOT NULL CHECK (sha256_hash ~ '^[0-9a-f]{64}$'),
    size_bytes BIGINT NOT NULL CHECK (size_bytes > 0),
    mime_type TEXT NOT NULL CHECK (btrim(mime_type) <> ''),
    artifact_kind TEXT NOT NULL,
    owner_ref TEXT NOT NULL,
    lineage_ref TEXT NULL,
    retention_ref TEXT NOT NULL,
    sensitivity_ref TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (workspace_id, artifact_id, sha256_hash),
    UNIQUE (workspace_id, artifact_version_id),
    UNIQUE (workspace_id, artifact_version_id, sha256_hash)
);

CREATE FUNCTION controlplane.cp_reject_artifact_version_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'artifact versions are immutable';
END;
$$;

CREATE TRIGGER cp_artifact_versions_immutable
BEFORE UPDATE OR DELETE ON controlplane.cp_artifact_versions
FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_artifact_version_mutation();

CREATE TABLE controlplane.cp_artifact_locations (
    location_id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    artifact_version_id UUID NOT NULL,
    backend_ref TEXT NOT NULL,
    provider_namespace_ref TEXT NOT NULL,
    provider_object_ref TEXT NOT NULL,
    logical_locator TEXT NOT NULL,
    observed_hash TEXT NULL CHECK (observed_hash IS NULL OR observed_hash ~ '^[0-9a-f]{64}$'),
    observed_size_bytes BIGINT NULL CHECK (observed_size_bytes IS NULL OR observed_size_bytes > 0),
    provider_metadata_revision TEXT NULL,
    verification_evidence_ref TEXT NULL,
    state TEXT NOT NULL CHECK (state IN ('DECLARED','MATERIALIZING','AVAILABLE_UNVERIFIED','VERIFYING','VERIFIED','CORRUPT','MISSING','OUTCOME_UNKNOWN','CLEANUP_ELIGIBLE','CLEANUP_AUTHORIZED','DELETED')),
    revision BIGINT NOT NULL DEFAULT 1 CHECK (revision >= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (workspace_id, artifact_version_id) REFERENCES controlplane.cp_artifact_versions(workspace_id, artifact_version_id) ON DELETE RESTRICT,
    UNIQUE (workspace_id, backend_ref, provider_namespace_ref, provider_object_ref),
    UNIQUE (workspace_id, location_id),
    UNIQUE (workspace_id, location_id, artifact_version_id)
);

CREATE TABLE controlplane.cp_cleanup_authorizations (
    cleanup_authorization_id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL,
    location_id UUID NOT NULL,
    artifact_version_id UUID NOT NULL,
    artifact_hash TEXT NOT NULL CHECK (artifact_hash ~ '^[0-9a-f]{64}$'),
    reason TEXT NOT NULL,
    policy_revision TEXT NOT NULL,
    completion_evidence_ref TEXT NOT NULL,
    verification_evidence_ref TEXT NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL CHECK (expires_at > issued_at),
    recovery_epoch BIGINT NOT NULL CHECK (recovery_epoch >= 0),
    authorizing_owner_ref TEXT NOT NULL,
    actor_ref TEXT NOT NULL,
    audit_ref TEXT NOT NULL,
    correlation_ref TEXT NOT NULL,
    FOREIGN KEY (workspace_id, location_id, artifact_version_id) REFERENCES controlplane.cp_artifact_locations(workspace_id, location_id, artifact_version_id) ON DELETE RESTRICT,
    FOREIGN KEY (workspace_id, artifact_version_id, artifact_hash) REFERENCES controlplane.cp_artifact_versions(workspace_id, artifact_version_id, sha256_hash) ON DELETE RESTRICT
);

CREATE FUNCTION controlplane.cp_reject_cleanup_authorization_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'cleanup authorizations are immutable';
END;
$$;

CREATE TRIGGER cp_cleanup_authorizations_immutable
BEFORE UPDATE OR DELETE ON controlplane.cp_cleanup_authorizations
FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_cleanup_authorization_mutation();
