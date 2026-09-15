DROP TRIGGER IF EXISTS cp_schema_migrations_prune_future ON controlplane.cp_schema_migrations;
DROP FUNCTION IF EXISTS controlplane.cp_prune_future_schema_migrations();
DROP TABLE IF EXISTS controlplane.cp_secret_handles;
DROP TABLE IF EXISTS controlplane.cp_config_revisions;
