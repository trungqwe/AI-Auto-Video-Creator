DROP TABLE controlplane.cp_technical_detail_access_audit;
DROP TABLE controlplane.cp_technical_details;
DROP INDEX controlplane.cp_auth_sessions_token_hash_unique;
ALTER TABLE controlplane.cp_auth_sessions
    DROP CONSTRAINT cp_auth_sessions_workspace_session_unique,
    DROP CONSTRAINT cp_auth_sessions_token_hash_size,
    DROP COLUMN token_hash;
