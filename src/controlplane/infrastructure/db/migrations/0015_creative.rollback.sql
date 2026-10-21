-- 0015_creative.rollback.sql
DROP TABLE IF EXISTS controlplane.cp_creative_receipts;
DROP TABLE IF EXISTS controlplane.cp_ai_invocation_records;
DROP TABLE IF EXISTS controlplane.cp_output_metadata;
DROP TABLE IF EXISTS controlplane.cp_variant_validations;
DROP TABLE IF EXISTS controlplane.cp_production_plans;
DROP TABLE IF EXISTS controlplane.cp_script_versions;
DROP TABLE IF EXISTS controlplane.cp_story_angles;
DROP TABLE IF EXISTS controlplane.cp_story_angle_sets;
DROP TABLE IF EXISTS controlplane.cp_content_analyses;
DROP TABLE IF EXISTS controlplane.cp_production_snapshots;
DROP FUNCTION IF EXISTS controlplane.cp_reject_creative_history_mutation();
