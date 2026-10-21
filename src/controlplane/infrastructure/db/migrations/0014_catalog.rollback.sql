-- 0014_catalog.rollback.sql
DROP TABLE IF EXISTS controlplane.cp_media_usage;
DROP TABLE IF EXISTS controlplane.cp_hook_revisions;
DROP TABLE IF EXISTS controlplane.cp_hooks;
DROP TABLE IF EXISTS controlplane.cp_media_renditions;
DROP TABLE IF EXISTS controlplane.cp_media_provenance;
DROP TABLE IF EXISTS controlplane.cp_media_assets;
DROP FUNCTION IF EXISTS controlplane.cp_reject_catalog_history_mutation();
