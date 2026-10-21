-- 0012_source_ingestion.sql
CREATE FUNCTION controlplane.cp_reject_source_ingestion_history_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'source ingestion history is append-only';
END;
$$;

CREATE TABLE controlplane.cp_sources (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    source_id TEXT NOT NULL,
    canonical_locator TEXT NOT NULL,
    status TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, source_id)
);
CREATE INDEX cp_sources_status_idx ON controlplane.cp_sources (workspace_id, status);

CREATE TABLE controlplane.cp_source_identities (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    canonical_locator TEXT NOT NULL,
    source_id TEXT NOT NULL,
    is_tombstone BOOLEAN NOT NULL DEFAULT false,
    tombstoned_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, canonical_locator),
    FOREIGN KEY (workspace_id, source_id) REFERENCES controlplane.cp_sources (workspace_id, source_id) ON DELETE RESTRICT
);

CREATE TABLE controlplane.cp_source_candidates (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    candidate_id TEXT NOT NULL,
    canonical_locator TEXT NOT NULL,
    status TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, candidate_id)
);
CREATE INDEX cp_source_candidates_locator_idx ON controlplane.cp_source_candidates (workspace_id, canonical_locator);

CREATE TABLE controlplane.cp_collection_runs (
    run_id TEXT NOT NULL,
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    source_id TEXT NOT NULL,
    run_kind TEXT NOT NULL,
    business_date DATE NULL,
    status TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id)
);
CREATE UNIQUE INDEX cp_collection_runs_periodic_unique ON controlplane.cp_collection_runs (workspace_id, source_id, business_date) WHERE run_kind = 'PERIODIC';
CREATE INDEX cp_collection_runs_source_idx ON controlplane.cp_collection_runs (workspace_id, source_id, created_at DESC);

CREATE TABLE controlplane.cp_collection_attempts (
    attempt_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    attempt_index BIGINT NOT NULL CHECK (attempt_index >= 1),
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ NULL,
    finished_at TIMESTAMPTZ NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (attempt_id),
    FOREIGN KEY (run_id) REFERENCES controlplane.cp_collection_runs (run_id) ON DELETE RESTRICT,
    UNIQUE (run_id, attempt_index)
);

CREATE TABLE controlplane.cp_collection_checkpoints (
    checkpoint_id TEXT NOT NULL,
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    source_id TEXT NOT NULL,
    sequence_no BIGINT NOT NULL CHECK (sequence_no >= 1),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (checkpoint_id),
    UNIQUE (source_id, sequence_no)
);
CREATE TRIGGER cp_collection_checkpoints_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_collection_checkpoints FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_source_ingestion_history_mutation();

CREATE TABLE controlplane.cp_fetch_observations (
    observation_id TEXT NOT NULL,
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    run_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    canonical_locator TEXT NOT NULL,
    observation_fingerprint TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (observation_id)
);
CREATE INDEX cp_fetch_observations_locator_idx ON controlplane.cp_fetch_observations (source_id, canonical_locator);
CREATE TRIGGER cp_fetch_observations_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_fetch_observations FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_source_ingestion_history_mutation();

CREATE TABLE controlplane.cp_collected_document_packages (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    source_id TEXT NOT NULL,
    canonical_locator TEXT NOT NULL,
    observation_fingerprint TEXT NOT NULL,
    collection_run_id TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_id, canonical_locator, observation_fingerprint)
);
CREATE INDEX cp_collected_document_packages_run_idx ON controlplane.cp_collected_document_packages (collection_run_id);
CREATE TRIGGER cp_collected_document_packages_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_collected_document_packages FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_source_ingestion_history_mutation();

CREATE TABLE controlplane.cp_source_command_receipts (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    aggregate_ref TEXT NOT NULL,
    aggregate_revision BIGINT NOT NULL CHECK (aggregate_revision >= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, idempotency_key)
);
CREATE TRIGGER cp_source_command_receipts_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_source_command_receipts FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_source_ingestion_history_mutation();
