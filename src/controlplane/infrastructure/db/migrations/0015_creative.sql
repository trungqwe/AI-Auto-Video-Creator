-- 0015_creative.sql
CREATE FUNCTION controlplane.cp_reject_creative_history_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'creative history is append-only';
END;
$$;

CREATE TABLE controlplane.cp_production_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    source_set_fingerprint TEXT NOT NULL,
    configuration_bundle_fingerprint TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX cp_production_snapshots_workspace_idx ON controlplane.cp_production_snapshots (workspace_id, created_at DESC);
CREATE TRIGGER cp_production_snapshots_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_production_snapshots FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_creative_history_mutation();

CREATE TABLE controlplane.cp_content_analyses (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    record_key TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_key, revision)
);
CREATE TRIGGER cp_content_analyses_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_content_analyses FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_creative_history_mutation();

CREATE TABLE controlplane.cp_story_angle_sets (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    record_key TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    set_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_key, revision),
    UNIQUE (workspace_id, set_id)
);
CREATE TRIGGER cp_story_angle_sets_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_story_angle_sets FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_creative_history_mutation();

CREATE TABLE controlplane.cp_story_angles (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    angle_id TEXT NOT NULL,
    set_id TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, angle_id)
);
CREATE INDEX cp_story_angles_set_idx ON controlplane.cp_story_angles (workspace_id, set_id);
CREATE TRIGGER cp_story_angles_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_story_angles FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_creative_history_mutation();

CREATE TABLE controlplane.cp_script_versions (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    record_key TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    script_version_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_key, revision),
    UNIQUE (workspace_id, script_version_id)
);
CREATE TRIGGER cp_script_versions_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_script_versions FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_creative_history_mutation();

CREATE TABLE controlplane.cp_production_plans (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    record_key TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    production_plan_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_key, revision),
    UNIQUE (workspace_id, production_plan_id)
);
CREATE TRIGGER cp_production_plans_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_production_plans FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_creative_history_mutation();

CREATE TABLE controlplane.cp_variant_validations (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    record_key TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_key, revision)
);
CREATE TRIGGER cp_variant_validations_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_variant_validations FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_creative_history_mutation();

CREATE TABLE controlplane.cp_output_metadata (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    record_key TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_key, revision)
);
CREATE TRIGGER cp_output_metadata_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_output_metadata FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_creative_history_mutation();

CREATE TABLE controlplane.cp_ai_invocation_records (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    record_key TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_key, revision)
);
CREATE TRIGGER cp_ai_invocation_records_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_ai_invocation_records FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_creative_history_mutation();

CREATE TABLE controlplane.cp_creative_receipts (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    aggregate_ref TEXT NOT NULL,
    aggregate_revision BIGINT NOT NULL CHECK (aggregate_revision >= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, idempotency_key)
);
CREATE TRIGGER cp_creative_receipts_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_creative_receipts FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_creative_history_mutation();
