export interface OperationItem {
  operation_id: string;
  command_ref: string;
  receipt_id: string;
  status: string;
  resource_refs: Array<{
    kind?: string;
    batch_id?: string;
    [key: string]: unknown;
  }>;
  accepted_at: string;
  latest_event_kind?: string | null;
  latest_safe_summary?: string | null;
  progress?: unknown;
  started_at?: string | null;
  updated_at?: string | null;
  finished_at?: string | null;
  wait_reason?: Record<string, unknown> | null;
  problem?: ProblemDetail;
}

export interface JobItem {
  job_id: string;
  batch_id: string;
  status: string;
  snapshot_ref: string;
  revision: number;
  created_at: string;
}

export interface BatchItem {
  batch_id: string;
  status: string;
  target_count: number;
  created_at: string;
}

export interface CommandReceipt {
  receipt_id: string;
  command_id: string;
  disposition: string;
  operation_id: string | null;
  resource_ref: {
    kind?: string;
    batch_id?: string;
    [key: string]: unknown;
  } | null;
  accepted_at: string;
  current_revision?: number | null;
}

export interface ProblemDetail {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance: string;
  code: string;
  category: string;
  retryable: boolean;
  correlation_id: string;
  field_errors?: Record<string, unknown>;
  technical_detail_ref?: string;
}

export interface TechnicalDetail {
  detail_ref: string;
  workspace_id: string;
  correlation_id: string;
  error_type: string;
  internal_detail: string;
  recorded_at: string;
}

export interface SSEEventPayload {
  cursor: string;
  resource_type: string;
  resource_id: string;
  resource_revision?: number | null;
  event_kind: string;
  occurred_at: string;
  recorded_at: string;
  summary: string;
  correlation_id: string;
}

export type ModuleRow = Record<string, unknown>;

export interface ModulePage {
  items: ModuleRow[];
  next_cursor: string | null;
}
