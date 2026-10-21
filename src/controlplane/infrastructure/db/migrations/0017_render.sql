-- 0017_render.sql
CREATE FUNCTION controlplane.cp_reject_render_history_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'render history is append-only';
END;
$$;

CREATE TABLE controlplane.cp_render_preset_revisions (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    record_key TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_key, revision)
);
CREATE TRIGGER cp_render_preset_revisions_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_render_preset_revisions FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_render_history_mutation();

CREATE TABLE controlplane.cp_render_packages (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    record_key TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    package_fingerprint TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_key, revision)
);
CREATE UNIQUE INDEX cp_render_packages_fingerprint_unique ON controlplane.cp_render_packages (package_fingerprint) WHERE revision = 1;
CREATE TRIGGER cp_render_packages_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_render_packages FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_render_history_mutation();

CREATE TABLE controlplane.cp_package_validation_reports (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    record_key TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_key, revision)
);
CREATE TRIGGER cp_package_validation_reports_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_package_validation_reports FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_render_history_mutation();

CREATE TABLE controlplane.cp_render_attempts (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    record_key TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    render_attempt_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_key, revision)
);
CREATE UNIQUE INDEX cp_render_attempts_attempt_id_unique ON controlplane.cp_render_attempts (render_attempt_id) WHERE revision = 1;
CREATE TRIGGER cp_render_attempts_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_render_attempts FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_render_history_mutation();

CREATE TABLE controlplane.cp_quality_reports (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    record_key TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_key, revision)
);
CREATE TRIGGER cp_quality_reports_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_quality_reports FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_render_history_mutation();

CREATE TABLE controlplane.cp_quality_gate_results (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    record_key TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_key, revision)
);
CREATE TRIGGER cp_quality_gate_results_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_quality_gate_results FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_render_history_mutation();

CREATE TABLE controlplane.cp_video_outputs (
    output_artifact_ref TEXT PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    render_attempt_id TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX cp_video_outputs_attempt_idx ON controlplane.cp_video_outputs (workspace_id, render_attempt_id);
CREATE TRIGGER cp_video_outputs_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_video_outputs FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_render_history_mutation();

CREATE TABLE controlplane.cp_render_operation_receipts (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    aggregate_ref TEXT NOT NULL,
    aggregate_revision BIGINT NOT NULL CHECK (aggregate_revision >= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, idempotency_key)
);
CREATE TRIGGER cp_render_operation_receipts_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_render_operation_receipts FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_render_history_mutation();
