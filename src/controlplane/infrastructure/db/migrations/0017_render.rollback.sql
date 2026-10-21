-- 0017_render.rollback.sql
DROP TABLE IF EXISTS controlplane.cp_render_operation_receipts;
DROP TABLE IF EXISTS controlplane.cp_video_outputs;
DROP TABLE IF EXISTS controlplane.cp_quality_gate_results;
DROP TABLE IF EXISTS controlplane.cp_quality_reports;
DROP TABLE IF EXISTS controlplane.cp_render_attempts;
DROP TABLE IF EXISTS controlplane.cp_package_validation_reports;
DROP TABLE IF EXISTS controlplane.cp_render_packages;
DROP TABLE IF EXISTS controlplane.cp_render_preset_revisions;
DROP FUNCTION IF EXISTS controlplane.cp_reject_render_history_mutation();
