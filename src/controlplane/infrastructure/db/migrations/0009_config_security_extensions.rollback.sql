-- 0009_config_security_extensions.rollback.sql
DROP TABLE IF EXISTS controlplane.cp_audit_records;
DROP TABLE IF EXISTS controlplane.cp_cost_records;
DROP TABLE IF EXISTS controlplane.cp_capacity_reservations;
DROP TABLE IF EXISTS controlplane.cp_provider_capacity_snapshots;
DROP TABLE IF EXISTS controlplane.cp_external_accounts;
DROP FUNCTION IF EXISTS controlplane.cp_reject_audit_record_mutation();
ALTER TABLE controlplane.cp_config_revisions DROP CONSTRAINT IF EXISTS cp_config_revisions_scope_kind_check;
ALTER TABLE controlplane.cp_secret_handles DROP COLUMN IF EXISTS credential_version, DROP COLUMN IF EXISTS revocation_version;
