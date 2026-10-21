-- 0014_catalog.sql
CREATE FUNCTION controlplane.cp_reject_catalog_history_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'catalog history is append-only';
END;
$$;

CREATE TABLE controlplane.cp_media_assets (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    media_asset_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    discovery_id TEXT NULL,
    status TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    search_text TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, media_asset_id),
    UNIQUE (workspace_id, fingerprint),
    UNIQUE (workspace_id, discovery_id)
);
CREATE INDEX cp_media_assets_fts_idx ON controlplane.cp_media_assets USING GIN (string_to_array(search_text, ' '));

CREATE TABLE controlplane.cp_media_provenance (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    provenance_id TEXT NOT NULL,
    media_asset_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, provenance_id)
);
CREATE INDEX cp_media_provenance_asset_idx ON controlplane.cp_media_provenance (workspace_id, media_asset_id);
CREATE TRIGGER cp_media_provenance_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_media_provenance FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_catalog_history_mutation();

CREATE TABLE controlplane.cp_media_renditions (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    rendition_ref TEXT NOT NULL,
    media_asset_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    artifact_version_ref TEXT NOT NULL,
    source_artifact_version_ref TEXT NOT NULL,
    transformation_spec_revision BIGINT NOT NULL,
    processor_version TEXT NOT NULL,
    lineage_refs JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, rendition_ref)
);
CREATE INDEX cp_media_renditions_asset_idx ON controlplane.cp_media_renditions (workspace_id, media_asset_id);
CREATE TRIGGER cp_media_renditions_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_media_renditions FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_catalog_history_mutation();

CREATE TABLE controlplane.cp_hooks (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    hook_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    current_revision BIGINT NOT NULL CHECK (current_revision >= 1),
    is_enabled BOOLEAN NOT NULL DEFAULT true,
    search_text TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, hook_id)
);
CREATE INDEX cp_hooks_fts_idx ON controlplane.cp_hooks USING GIN (string_to_array(search_text, ' '));

CREATE TABLE controlplane.cp_hook_revisions (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    hook_id TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    artifact_version_ref TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, hook_id, revision)
);
CREATE TRIGGER cp_hook_revisions_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_hook_revisions FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_catalog_history_mutation();

CREATE TABLE controlplane.cp_media_usage (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    usage_id TEXT NOT NULL,
    completion_id TEXT NOT NULL,
    video_job_id TEXT NOT NULL,
    media_asset_id TEXT NOT NULL,
    role TEXT NOT NULL,
    usage_kind TEXT NOT NULL CHECK (usage_kind IN ('production','technical')),
    rendition_ref TEXT NULL,
    artifact_version_ref TEXT NULL,
    selection_rationale TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, usage_id),
    UNIQUE (workspace_id, completion_id, media_asset_id, role, usage_kind)
);
CREATE INDEX cp_media_usage_asset_idx ON controlplane.cp_media_usage (workspace_id, media_asset_id, usage_kind);
CREATE TRIGGER cp_media_usage_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_media_usage FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_catalog_history_mutation();
