DROP TABLE IF EXISTS controlplane.cp_source_cycle_marks;
DROP TABLE IF EXISTS controlplane.cp_creative_selections;
DROP TABLE IF EXISTS controlplane.cp_job_candidates;
ALTER TABLE controlplane.cp_stage_runs DROP CONSTRAINT IF EXISTS cp_stage_runs_job_or_workflow_check;
ALTER TABLE controlplane.cp_stage_runs DROP COLUMN IF EXISTS workflow_id;
ALTER TABLE controlplane.cp_stage_runs ALTER COLUMN job_id SET NOT NULL;
