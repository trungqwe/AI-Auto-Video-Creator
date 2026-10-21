CREATE INDEX cp_production_batches_keyset_idx ON controlplane.cp_production_batches (workspace_id, created_at DESC, batch_id DESC);
CREATE INDEX cp_video_jobs_keyset_idx ON controlplane.cp_video_jobs (workspace_id, created_at DESC, job_id DESC);
CREATE INDEX cp_command_receipts_keyset_idx ON controlplane.cp_command_receipts (workspace_id, accepted_at DESC, receipt_id DESC);
