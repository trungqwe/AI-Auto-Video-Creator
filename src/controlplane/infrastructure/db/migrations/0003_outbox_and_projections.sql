CREATE TABLE controlplane.cp_outbox_events (
    event_id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id),
    contract_name TEXT NOT NULL,
    contract_version INTEGER NOT NULL,
    message_id TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    causation_id TEXT NULL,
    trace_context TEXT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    actor TEXT NOT NULL,
    recovery_epoch BIGINT NULL,
    payload JSONB NOT NULL,
    event_name TEXT NOT NULL,
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    aggregate_revision BIGINT NOT NULL,
    producer TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    sensitivity TEXT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    published BOOLEAN NOT NULL DEFAULT false,
    published_at TIMESTAMPTZ NULL,
    CHECK ((published = false AND published_at IS NULL) OR (published = true AND published_at IS NOT NULL))
);
CREATE INDEX cp_outbox_events_aggregate_order_idx ON controlplane.cp_outbox_events (workspace_id, aggregate_type, aggregate_id, aggregate_revision, recorded_at, event_id);
CREATE INDEX cp_outbox_events_dispatch_idx ON controlplane.cp_outbox_events (recorded_at, event_id) WHERE published = false;

CREATE TABLE controlplane.cp_event_checkpoints (
    consumer_id TEXT NOT NULL,
    event_id UUID NOT NULL,
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id),
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    aggregate_revision BIGINT NOT NULL,
    current_applied_revision BIGINT NULL,
    status TEXT NOT NULL,
    checkpointed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (consumer_id, event_id)
);
CREATE TABLE controlplane.cp_event_quarantine (
    consumer_id TEXT NOT NULL,
    event_id UUID NOT NULL,
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id),
    reason_code TEXT NOT NULL,
    event_envelope JSONB NOT NULL,
    quarantine_status TEXT NOT NULL DEFAULT 'OPEN',
    quarantined_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (consumer_id, event_id)
);
CREATE TABLE controlplane.cp_operation_stream (
    stream_event_id BIGSERIAL PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES controlplane.cp_workspaces(workspace_id),
    operation_id UUID NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    resource_revision BIGINT NOT NULL,
    event_kind TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    summary TEXT NOT NULL,
    correlation_id TEXT NOT NULL
);
CREATE TABLE controlplane.cp_operation_stream_retention_watermarks (
    workspace_id UUID PRIMARY KEY REFERENCES controlplane.cp_workspaces(workspace_id),
    minimum_available_cursor BIGINT NOT NULL,
    minimum_available_at TIMESTAMPTZ NOT NULL
);
