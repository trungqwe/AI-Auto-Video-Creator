-- 0009_config_security_extensions.sql
ALTER TABLE controlplane.cp_secret_handles ADD COLUMN credential_version BIGINT NOT NULL DEFAULT 0 CHECK (credential_version >= 0), ADD COLUMN revocation_version BIGINT NOT NULL DEFAULT 0 CHECK (revocation_version >= 0);
ALTER TABLE controlplane.cp_config_revisions ADD CONSTRAINT cp_config_revisions_scope_kind_check CHECK (scope_kind IN ('workspace','module','provider','preset','policy','prompt'));

CREATE FUNCTION controlplane.cp_reject_audit_record_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit records are append-only';
END;
$$;

CREATE TABLE controlplane.cp_external_accounts (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    external_account_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    account_label TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ENABLED','DISABLED','DEGRADED','INVALID','REVOKED')),
    project_ref TEXT NULL,
    capabilities_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    credential_version BIGINT NOT NULL DEFAULT 0 CHECK (credential_version >= 0),
    credential_updated_at TIMESTAMPTZ NULL,
    credential_expires_at TIMESTAMPTZ NULL,
    quota_observation_ref TEXT NULL,
    health TEXT NULL,
    revision BIGINT NOT NULL DEFAULT 1 CHECK (revision >= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, external_account_id),
    UNIQUE (workspace_id, provider, account_label)
);

CREATE TABLE controlplane.cp_provider_capacity_snapshots (
    snapshot_id TEXT NOT NULL,
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    domain_key TEXT NOT NULL,
    remaining_requests BIGINT NOT NULL CHECK (remaining_requests >= 0),
    retry_after_at TIMESTAMPTZ NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    confidence_flag TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, snapshot_id)
);
CREATE INDEX cp_provider_capacity_snapshots_domain_idx ON controlplane.cp_provider_capacity_snapshots (workspace_id, domain_key, observed_at DESC);

CREATE TABLE controlplane.cp_capacity_reservations (
    reservation_ref TEXT NOT NULL,
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    domain_key TEXT NOT NULL,
    units BIGINT NOT NULL CHECK (units > 0),
    expires_at TIMESTAMPTZ NOT NULL,
    operation_key TEXT NOT NULL,
    confidence_flag TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, reservation_ref),
    UNIQUE (workspace_id, operation_key)
);
CREATE INDEX cp_capacity_reservations_domain_expiry_idx ON controlplane.cp_capacity_reservations (workspace_id, domain_key, expires_at);

CREATE TABLE controlplane.cp_cost_records (
    record_id TEXT NOT NULL,
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    provider TEXT NOT NULL,
    service TEXT NOT NULL,
    operation_ref TEXT NOT NULL,
    job_ref TEXT NULL,
    batch_ref TEXT NULL,
    quantity NUMERIC NOT NULL,
    unit TEXT NOT NULL,
    estimated_cost NUMERIC NOT NULL,
    actual_cost NUMERIC NULL,
    currency TEXT NOT NULL,
    source TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    cost_category TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_id)
);
CREATE INDEX cp_cost_records_window_idx ON controlplane.cp_cost_records (workspace_id, occurred_at DESC);

CREATE TABLE controlplane.cp_audit_records (
    audit_id TEXT NOT NULL,
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    actor_ref TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_ref TEXT NOT NULL,
    revision_before BIGINT NULL,
    revision_after BIGINT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    correlation_id TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('succeeded','failed','denied')),
    redacted_reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, audit_id)
);
CREATE INDEX cp_audit_records_time_idx ON controlplane.cp_audit_records (workspace_id, occurred_at DESC, audit_id DESC);
CREATE TRIGGER cp_audit_records_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_audit_records FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_audit_record_mutation();
