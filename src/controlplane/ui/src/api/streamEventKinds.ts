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
  'source.registered',
  'source.metadata_updated',
  'source.removed',
  'source.restored',
  'source.candidate_discovered',
  'source.candidate_resolved',
  'source.collection_run_started',
  'source.collected_document_available',
  'source.collection_run_completed',
  'source.collection_run_failed',
  'ingestion.article_revision_accepted',
  'ingestion.duplicate_document_resolved',
  'ingestion.event_link_resolved',
  'ingestion.event_update_accepted',
  'creative.production_snapshot_committed',
  'creative.story_angles_generated',
  'creative.script_version_created',
  'creative.production_plan_created',
  'creative.variant_validated',
  'creative.output_metadata_created',
  'voice.image_safety_assessed',
  'voice.media_processing_completed',
  'voice.voice_ready',
  'voice.word_timing_ready',
  'render.render_completed',
  'render.output_quality_checked',
  'orchestration.batch_started',
  'orchestration.job_allocated',
  'orchestration.stage_state_changed',
  'orchestration.job_waiting',
  'orchestration.job_failed',
  'orchestration.video_completed',
  'orchestration.batch_target_reached',
  'orchestration.batch_exhausted',
  'storage.artifact_location_verified',
  'storage.cleanup_completed',
  'config.revision_published',
  'config.credential_changed',
] as const;

export type StreamEventKind = (typeof STREAM_EVENT_KINDS)[number];

export const ALL_SNAPSHOT_RESOURCES: readonly string[] = [
  'operations',
  'batches',
  'jobs',
  'sources',
  'articles',
  'events',
  'media',
  'hooks',
  'stage-runs',
  'sessions',
  'logs',
];

export const RESYNC_SNAPSHOT_RESOURCES: Record<string, readonly string[]> = {
  operation: ['operations'],
  production_batch: ['batches'],
  job: ['jobs'],
  source: ['sources'],
  ingestion: ['articles', 'events'],
  orchestration: ['batches', 'jobs', 'stage-runs'],
};

export function snapshotResourcesFor(resourceType: string): readonly string[] {
  if (Object.prototype.hasOwnProperty.call(RESYNC_SNAPSHOT_RESOURCES, resourceType)) {
    return RESYNC_SNAPSHOT_RESOURCES[resourceType];
  }
  return ALL_SNAPSHOT_RESOURCES;
}
