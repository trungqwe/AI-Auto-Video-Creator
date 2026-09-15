CREATE TABLE controlplane.cp_config_revisions (
    config_revision_id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    scope_kind TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    config_revision_number BIGINT NOT NULL CHECK (config_revision_number > 0),
    revision BIGINT NOT NULL DEFAULT 1 CHECK (revision >= 1),
    content_hash TEXT NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    payload JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('DRAFT', 'PUBLISHED', 'SUPERSEDED', 'INVALIDATED')),
    effective_at TIMESTAMPTZ NULL,
    actor_ref TEXT NOT NULL,
    change_reason TEXT NOT NULL,
    audit_ref TEXT NOT NULL DEFAULT 'p5a',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (workspace_id, scope_kind, scope_key, config_revision_number)
);

CREATE TABLE controlplane.cp_secret_handles (
    secret_handle_id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    provider_ref TEXT NOT NULL,
    account_ref TEXT NOT NULL,
    alias_ref TEXT NOT NULL,
    redacted_fingerprint_or_version TEXT NOT NULL,
    validation_status TEXT NOT NULL,
    revoked_at TIMESTAMPTZ NULL,
    expires_at TIMESTAMPTZ NULL,
    audit_ref TEXT NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
