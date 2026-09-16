ALTER TABLE controlplane.cp_auth_sessions
    ADD COLUMN token_hash BYTEA NULL,
    ADD CONSTRAINT cp_auth_sessions_token_hash_size
        CHECK (token_hash IS NULL OR octet_length(token_hash) = 32),
    ADD CONSTRAINT cp_auth_sessions_workspace_session_unique
        UNIQUE (workspace_id, session_id);

CREATE UNIQUE INDEX cp_auth_sessions_token_hash_unique
    ON controlplane.cp_auth_sessions (token_hash)
    WHERE token_hash IS NOT NULL;

CREATE TABLE controlplane.cp_technical_details (
    detail_ref UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    correlation_id TEXT NOT NULL CHECK (btrim(correlation_id) <> ''),
    error_type TEXT NOT NULL CHECK (btrim(error_type) <> ''),
    stack_trace TEXT NULL,
    sanitized_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (workspace_id, detail_ref)
);

CREATE TABLE controlplane.cp_technical_detail_access_audit (
    access_id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL,
    detail_ref UUID NOT NULL,
    actor_id UUID NOT NULL,
    session_id UUID NOT NULL,
    correlation_id TEXT NOT NULL CHECK (btrim(correlation_id) <> ''),
    accessed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (workspace_id, detail_ref)
        REFERENCES controlplane.cp_technical_details (workspace_id, detail_ref) ON DELETE RESTRICT,
    FOREIGN KEY (workspace_id, actor_id)
        REFERENCES controlplane.cp_actors (workspace_id, actor_id) ON DELETE RESTRICT,
    FOREIGN KEY (workspace_id, session_id)
        REFERENCES controlplane.cp_auth_sessions (workspace_id, session_id) ON DELETE RESTRICT
);
