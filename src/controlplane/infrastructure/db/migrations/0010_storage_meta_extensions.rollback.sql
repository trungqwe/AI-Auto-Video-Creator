-- 0010_storage_meta_extensions.rollback.sql
DROP TABLE IF EXISTS controlplane.cp_working_set_policies;
DROP TABLE IF EXISTS controlplane.cp_revision_placements;
DROP TABLE IF EXISTS controlplane.cp_materialization_leases;
DROP TABLE IF EXISTS controlplane.cp_upload_receipts;
ALTER TABLE controlplane.cp_cleanup_authorizations DROP CONSTRAINT IF EXISTS cp_cleanup_authorizations_recovery_epoch_text_check;
ALTER TABLE controlplane.cp_cleanup_authorizations ALTER COLUMN recovery_epoch TYPE BIGINT USING recovery_epoch::bigint;
ALTER TABLE controlplane.cp_cleanup_authorizations ADD CONSTRAINT cp_cleanup_authorizations_recovery_epoch_check CHECK (recovery_epoch >= 0);
ALTER TABLE controlplane.cp_artifact_locations DROP COLUMN IF EXISTS device_ref, DROP COLUMN IF EXISTS logical_category, DROP COLUMN IF EXISTS last_verified_at, DROP COLUMN IF EXISTS lease_ref, DROP COLUMN IF EXISTS retention_state, DROP COLUMN IF EXISTS cleanup_state;
ALTER TABLE controlplane.cp_artifact_versions DROP COLUMN IF EXISTS intended_storage_class, DROP COLUMN IF EXISTS producer_operation_ref, DROP COLUMN IF EXISTS lineage_refs;
