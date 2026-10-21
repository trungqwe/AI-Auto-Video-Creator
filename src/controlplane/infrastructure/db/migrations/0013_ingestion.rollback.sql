-- 0013_ingestion.rollback.sql
DROP TABLE IF EXISTS controlplane.cp_event_update_candidates;
DROP TABLE IF EXISTS controlplane.cp_event_updates;
DROP TABLE IF EXISTS controlplane.cp_event_link_candidates;
DROP TABLE IF EXISTS controlplane.cp_events;
DROP TABLE IF EXISTS controlplane.cp_dedup_evidence;
DROP TABLE IF EXISTS controlplane.cp_collected_document_resolutions;
DROP TABLE IF EXISTS controlplane.cp_article_revisions;
DROP TABLE IF EXISTS controlplane.cp_articles;
DROP FUNCTION IF EXISTS controlplane.cp_reject_ingestion_history_mutation();
