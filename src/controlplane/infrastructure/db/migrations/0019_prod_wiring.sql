ALTER TABLE controlplane.cp_stage_runs ALTER COLUMN job_id DROP NOT NULL;
ALTER TABLE controlplane.cp_stage_runs ADD COLUMN workflow_id TEXT NULL;
ALTER TABLE controlplane.cp_stage_runs ADD CONSTRAINT cp_stage_runs_job_or_workflow_check CHECK (job_id IS NOT NULL OR workflow_id IS NOT NULL);

CREATE TABLE controlplane.cp_job_candidates (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    job_id TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    candidate_ref TEXT NOT NULL,
    source_set_ref TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, job_id)
);

CREATE TABLE controlplane.cp_creative_selections (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    selection_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    selection_revision BIGINT NOT NULL,
    content_sha256 TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (workspace_id, job_id, selection_revision)
);

CREATE TABLE controlplane.cp_source_cycle_marks (
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id) ON DELETE RESTRICT,
    source_id TEXT NOT NULL,
    cycle_day DATE NOT NULL,
    collection_run_ref TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, source_id, cycle_day)
);
