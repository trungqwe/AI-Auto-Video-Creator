import type { ProblemDetail } from './api.ts';

export const OPERATION_STATUSES = [
  'accepted',
  'running',
  'waiting',
  'outcome_unknown',
  'succeeded',
  'failed',
] as const;

export type OperationStatus = (typeof OPERATION_STATUSES)[number];

export interface OperationView {
  operation_id: string;
  command_ref: string;
  status: OperationStatus;
  progress?: unknown;
  resource_refs: Array<{
    kind?: string;
    batch_id?: string;
    [key: string]: unknown;
  }>;
  started_at?: string | null;
  updated_at?: string | null;
  finished_at?: string | null;
  wait_reason?: Record<string, unknown> | null;
  problem?: ProblemDetail;
}
