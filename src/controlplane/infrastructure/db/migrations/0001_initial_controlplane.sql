CREATE SCHEMA controlplane;

CREATE TABLE controlplane.cp_schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    checksum_sha256 TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    execution_ms DOUBLE PRECISION NOT NULL
);

CREATE TABLE controlplane.cp_workspaces (
    workspace_id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE controlplane.cp_actors (
    actor_id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    actor_type TEXT NOT NULL,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (workspace_id, actor_id)
);

CREATE TABLE controlplane.cp_auth_sessions (
    session_id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL,
    actor_id UUID NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ,
    CONSTRAINT cp_auth_sessions_actor_workspace_fk
        FOREIGN KEY (workspace_id, actor_id)
        REFERENCES controlplane.cp_actors (workspace_id, actor_id)
        ON DELETE RESTRICT
);
