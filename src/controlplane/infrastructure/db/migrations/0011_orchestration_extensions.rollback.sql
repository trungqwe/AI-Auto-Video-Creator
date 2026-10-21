-- 0011_orchestration_extensions.rollback.sql
DROP TABLE IF EXISTS controlplane.cp_app_sessions;
DROP TABLE IF EXISTS controlplane.cp_cleanup_eligibility;
DROP TABLE IF EXISTS controlplane.cp_orchestration_receipts;
DROP TABLE IF EXISTS controlplane.cp_execution_grants;
DROP INDEX IF EXISTS controlplane.cp_completion_ledger_completion_id_unique;
ALTER TABLE controlplane.cp_production_batches DROP COLUMN IF EXISTS stop_reason, DROP COLUMN IF EXISTS stopped_at;
ALTER TABLE controlplane.cp_completion_ledger DROP COLUMN IF EXISTS completion_id, DROP COLUMN IF EXISTS session_ref, DROP COLUMN IF EXISTS cloud_location_ref, DROP COLUMN IF EXISTS cloud_location_verification_ref, DROP COLUMN IF EXISTS snapshot_ref, DROP COLUMN IF EXISTS script_version_ref, DROP COLUMN IF EXISTS production_plan_ref, DROP COLUMN IF EXISTS preset_revision_ref, DROP COLUMN IF EXISTS quality_report_ref, DROP COLUMN IF EXISTS variant_validation_ref, DROP COLUMN IF EXISTS media_usage_manifest, DROP COLUMN IF EXISTS output_naming_metadata, DROP COLUMN IF EXISTS cost_usage_summary, DROP COLUMN IF EXISTS cleanup_policy_ref;
ALTER TABLE controlplane.cp_video_jobs DROP COLUMN IF EXISTS wait_reason, DROP COLUMN IF EXISTS parent_variant_ref, DROP COLUMN IF EXISTS prior_variant_ref;
ALTER TABLE controlplane.cp_stage_runs DROP COLUMN IF EXISTS stage_type, DROP COLUMN IF EXISTS input_refs, DROP COLUMN IF EXISTS dependency_refs, DROP COLUMN IF EXISTS wait_reason, DROP COLUMN IF EXISTS problem, DROP COLUMN IF EXISTS started_at, DROP COLUMN IF EXISTS finished_at, DROP COLUMN IF EXISTS updated_at, DROP COLUMN IF EXISTS superseded_by;
ALTER TABLE controlplane.cp_stage_runs DROP CONSTRAINT IF EXISTS cp_stage_runs_recovery_epoch_text_check;
ALTER TABLE controlplane.cp_stage_runs ALTER COLUMN recovery_epoch TYPE BIGINT USING recovery_epoch::bigint;
ALTER TABLE controlplane.cp_stage_runs ADD CONSTRAINT cp_stage_runs_recovery_epoch_check CHECK (recovery_epoch >= 0);
