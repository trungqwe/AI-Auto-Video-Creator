-- 0016_voice.sql
CREATE FUNCTION controlplane.cp_reject_voice_history_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'voice history is append-only';
END;
$$;

CREATE TABLE controlplane.cp_processed_media (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    record_key TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_key, revision)
);
CREATE TRIGGER cp_processed_media_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_processed_media FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_voice_history_mutation();

CREATE TABLE controlplane.cp_image_safety_assessments (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    record_key TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_key, revision)
);
CREATE TRIGGER cp_image_safety_assessments_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_image_safety_assessments FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_voice_history_mutation();

CREATE TABLE controlplane.cp_voice_tracks (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    record_key TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    voice_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_key, revision),
    UNIQUE (voice_hash)
);
CREATE TRIGGER cp_voice_tracks_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_voice_tracks FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_voice_history_mutation();

CREATE TABLE controlplane.cp_word_timings (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    record_key TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    timing_artifact_ref TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_key, revision),
    UNIQUE (timing_artifact_ref)
);
CREATE TRIGGER cp_word_timings_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_word_timings FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_voice_history_mutation();

CREATE TABLE controlplane.cp_timing_validation_reports (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    record_key TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_key, revision)
);
CREATE TRIGGER cp_timing_validation_reports_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_timing_validation_reports FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_voice_history_mutation();

CREATE TABLE controlplane.cp_tts_invocation_records (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    record_key TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_key, revision)
);
CREATE TRIGGER cp_tts_invocation_records_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_tts_invocation_records FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_voice_history_mutation();

CREATE TABLE controlplane.cp_language_evidence (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    record_key TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_key, revision)
);
CREATE TRIGGER cp_language_evidence_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_language_evidence FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_voice_history_mutation();

CREATE TABLE controlplane.cp_audio_bed_results (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    record_key TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_key, revision)
);
CREATE TRIGGER cp_audio_bed_results_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_audio_bed_results FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_voice_history_mutation();

CREATE TABLE controlplane.cp_probe_reports (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    record_key TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_key, revision)
);
CREATE TRIGGER cp_probe_reports_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_probe_reports FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_voice_history_mutation();

CREATE TABLE controlplane.cp_analysis_results (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    record_key TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 1),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, record_key, revision)
);
CREATE TRIGGER cp_analysis_results_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_analysis_results FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_voice_history_mutation();

CREATE TABLE controlplane.cp_voice_receipts (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    aggregate_ref TEXT NOT NULL,
    aggregate_revision BIGINT NOT NULL CHECK (aggregate_revision >= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, idempotency_key)
);
CREATE TRIGGER cp_voice_receipts_append_only BEFORE UPDATE OR DELETE ON controlplane.cp_voice_receipts FOR EACH ROW EXECUTE FUNCTION controlplane.cp_reject_voice_history_mutation();
