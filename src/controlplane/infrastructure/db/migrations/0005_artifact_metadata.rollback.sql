DROP TABLE IF EXISTS controlplane.cp_cleanup_authorizations;
DROP TABLE IF EXISTS controlplane.cp_artifact_locations;
DROP TABLE IF EXISTS controlplane.cp_artifact_versions;
DROP FUNCTION IF EXISTS controlplane.cp_reject_cleanup_authorization_mutation();
DROP FUNCTION IF EXISTS controlplane.cp_reject_artifact_version_mutation();
