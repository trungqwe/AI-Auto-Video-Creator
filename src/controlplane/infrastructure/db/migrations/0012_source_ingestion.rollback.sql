-- 0012_source_ingestion.rollback.sql
DROP TABLE IF EXISTS controlplane.cp_source_command_receipts;
DROP TABLE IF EXISTS controlplane.cp_collected_document_packages;
DROP TABLE IF EXISTS controlplane.cp_fetch_observations;
DROP TABLE IF EXISTS controlplane.cp_collection_checkpoints;
DROP TABLE IF EXISTS controlplane.cp_collection_attempts;
DROP TABLE IF EXISTS controlplane.cp_collection_runs;
DROP TABLE IF EXISTS controlplane.cp_source_candidates;
DROP TABLE IF EXISTS controlplane.cp_source_identities;
DROP TABLE IF EXISTS controlplane.cp_sources;
DROP FUNCTION IF EXISTS controlplane.cp_reject_source_ingestion_history_mutation();
