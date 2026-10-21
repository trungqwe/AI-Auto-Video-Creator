-- 0013_ingestion.sql
CREATE FUNCTION controlplane.cp_reject_ingestion_history_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'ingestion history is append-only';
END;
$$;

CREATE TABLE controlplane.cp_articles (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    article_id TEXT NOT NULL,
    identity_key TEXT NOT NULL,
    exact_fingerprint TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, article_id),
    UNIQUE (workspace_id, identity_key)
);
CREATE INDEX cp_articles_fingerprint_idx ON controlplane.cp_articles (workspace_id, exact_fingerprint);

CREATE TABLE controlplane.cp_article_revisions (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    article_id TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, article_id, revision)
);
CREATE TRIGGER cp_article_revisions_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_article_revisions FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_ingestion_history_mutation();

CREATE TABLE controlplane.cp_collected_document_resolutions (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    collected_document_id TEXT NOT NULL,
    dedup_policy_revision BIGINT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, collected_document_id, dedup_policy_revision)
);

CREATE TABLE controlplane.cp_dedup_evidence (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    evidence_id TEXT NOT NULL,
    collected_document_id TEXT NOT NULL,
    dedup_policy_revision BIGINT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, evidence_id)
);
CREATE INDEX cp_dedup_evidence_document_idx ON controlplane.cp_dedup_evidence (workspace_id, collected_document_id);
CREATE TRIGGER cp_dedup_evidence_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_dedup_evidence FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_ingestion_history_mutation();

CREATE TABLE controlplane.cp_events (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    event_id TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, event_id)
);

CREATE TABLE controlplane.cp_event_link_candidates (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    record_id TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_id)
);

CREATE TABLE controlplane.cp_event_updates (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    record_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_id)
);
CREATE INDEX cp_event_updates_event_idx ON controlplane.cp_event_updates (workspace_id, event_id);
CREATE TRIGGER cp_event_updates_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_event_updates FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_ingestion_history_mutation();

CREATE TABLE controlplane.cp_event_update_candidates (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    record_id TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_id)
);
