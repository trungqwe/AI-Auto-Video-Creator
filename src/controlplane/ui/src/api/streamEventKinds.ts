// Danh mục event kind và bảng resync phía client (CT-API-008, GAP-H-02).
// Phải khớp từng phần tử với controlplane.application.sse.event_catalog (H-03);
// test_h_stream_client_registry.py đối chiếu hai phía. Tệp thuần, không có I/O.

export const STREAM_EVENT_KINDS = [
  'operation.accepted',
  'operation.running',
  'operation.succeeded',
  'operation.failed',
  'operation.changed',
  'production_batch.start_accepted',
  'job.created',
  'job.running',
  'job.completed',
  'job.failed',
] as const;

export type StreamEventKind = (typeof STREAM_EVENT_KINDS)[number];

export const ALL_SNAPSHOT_RESOURCES: readonly string[] = ['operations', 'batches', 'jobs'];

export const RESYNC_SNAPSHOT_RESOURCES: Record<string, readonly string[]> = {
  operation: ['operations'],
  production_batch: ['batches'],
  job: ['jobs'],
};

export function snapshotResourcesFor(resourceType: string): readonly string[] {
  if (Object.prototype.hasOwnProperty.call(RESYNC_SNAPSHOT_RESOURCES, resourceType)) {
    return RESYNC_SNAPSHOT_RESOURCES[resourceType];
  }
  return ALL_SNAPSHOT_RESOURCES;
}
