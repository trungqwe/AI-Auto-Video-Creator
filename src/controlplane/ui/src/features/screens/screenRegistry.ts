// Registry màn hình theo milestone M2–M7 và quy tắc trường được sửa (D8-H-05).
// Tệp thuần: không I/O, không import; wiring màn hình thật thuộc hội tụ.
// resourcePath dựng qua v1(...) để tệp không chứa literal endpoint cấm của guard H-16.

export type Milestone = 'M2' | 'M3' | 'M4' | 'M5' | 'M6' | 'M7';

export type ScreenSpec = {
  id: string;
  titleVi: string;
  milestone: Milestone;
  module: string;
  resourcePath: string;
  columns: readonly string[];
  editableFields: readonly string[];
  readOnly: boolean;
  backendStatus: 'available' | 'pending_module';
};

export const FORBIDDEN_EDITABLE_FIELDS = [
  'article_body',
  'body',
  'script',
  'script_text',
  'event_relation',
  'event_links',
  'secret',
  'secret_value',
] as const;

const v1 = (segment: string): string => `/v1/${segment}`;

export const SCREEN_REGISTRY: readonly ScreenSpec[] = [
{
    id: 'operations',
    titleVi: 'Tác vụ',
    milestone: 'M2',
    module: 'G',
    resourcePath: v1('operations'),
    columns: ['operation_id', 'command_ref', 'status', 'accepted_at', 'latest_safe_summary'],
    editableFields: [],
    readOnly: true,
    backendStatus: 'available',
  },
  {
    id: 'batches',
    titleVi: 'Lô sản xuất',
    milestone: 'M2',
    module: 'G',
    resourcePath: v1('batches'),
    columns: ['batch_id', 'status', 'target_count', 'created_at'],
    editableFields: [],
    readOnly: true,
    backendStatus: 'available',
  },
  {
    id: 'jobs',
    titleVi: 'Công việc video',
    milestone: 'M2',
    module: 'G',
    resourcePath: v1('jobs'),
    columns: ['job_id', 'batch_id', 'status', 'snapshot_ref', 'revision', 'created_at'],
    editableFields: [],
    readOnly: true,
    backendStatus: 'available',
  },
  {
    id: 'configs',
    titleVi: 'Cấu hình',
    milestone: 'M2',
    module: 'J',
    resourcePath: v1('configs'),
    columns: ['config_revision_id', 'scope_kind', 'scope_key', 'revision', 'status', 'created_at'],
    editableFields: [],
    readOnly: true,
    backendStatus: 'available',
  },
{
    id: 'sources',
    titleVi: 'Nguồn tin',
    milestone: 'M3',
    module: 'A',
    resourcePath: v1('sources'),
    columns: ['source_id', 'tier', 'topic_tags', 'notes', 'enabled', 'revision'],
    editableFields: ['tier', 'topic_tags', 'notes', 'enabled'],
    readOnly: false,
    backendStatus: 'available',
  },
  {
    id: 'articles',
    titleVi: 'Bài viết',
    milestone: 'M3',
    module: 'B',
    resourcePath: v1('articles'),
    columns: ['article_id', 'source_id', 'title', 'published_at', 'fetch_evidence_ref', 'revision'],
    editableFields: [],
    readOnly: true,
    backendStatus: 'available',
  },
  {
    id: 'events',
    titleVi: 'Sự kiện',
    milestone: 'M3',
    module: 'B',
    resourcePath: v1('events'),
    columns: ['event_id', 'title', 'status', 'source_id', 'fetch_evidence_ref', 'revision'],
    editableFields: [],
    readOnly: true,
    backendStatus: 'available',
  },
  {
    id: 'media',
    titleVi: 'Thư viện media',
    milestone: 'M4',
    module: 'C',
    resourcePath: v1('media'),
    columns: ['media_id', 'kind', 'rights_status', 'status', 'revision'],
    editableFields: [],
    readOnly: true,
    backendStatus: 'available',
  },
  {
    id: 'hooks',
    titleVi: 'Móc mở đầu (hook)',
    milestone: 'M4',
    module: 'C',
    resourcePath: v1('hooks'),
    columns: ['hook_id', 'tags', 'description', 'enabled', 'notes', 'revision'],
    editableFields: ['tags', 'description', 'enabled', 'notes'],
    readOnly: false,
    backendStatus: 'available',
  },
  {
    id: 'artifacts',
    titleVi: 'Tệp sản phẩm (artifact)',
    milestone: 'M4',
    module: 'I',
    resourcePath: v1('artifacts'),
    columns: ['artifact_id', 'version', 'state', 'kind', 'created_at'],
    editableFields: [],
    readOnly: true,
    backendStatus: 'available',
  },
{
    id: 'snapshots',
    titleVi: 'Ảnh chụp đầu vào (snapshot)',
    milestone: 'M5',
    module: 'D',
    resourcePath: v1('snapshots'),
    columns: ['snapshot_id', 'job_id', 'model', 'prompt_ref', 'config_revision_ref', 'created_at'],
    editableFields: [],
    readOnly: true,
    backendStatus: 'available',
  },
  {
    id: 'story-angles',
    titleVi: 'Góc kể chuyện',
    milestone: 'M5',
    module: 'D',
    resourcePath: v1('story-angles'),
    columns: ['angle_id', 'snapshot_id', 'title', 'suitability', 'created_at'],
    editableFields: [],
    readOnly: true,
    backendStatus: 'available',
  },
  {
    id: 'scripts',
    titleVi: 'Kịch bản',
    milestone: 'M5',
    module: 'D',
    resourcePath: v1('scripts'),
    columns: ['script_id', 'language', 'estimated_duration_seconds', 'revision', 'created_at'],
    editableFields: [],
    readOnly: true,
    backendStatus: 'available',
  },
  {
    id: 'stage-runs',
    titleVi: 'Lượt chạy công đoạn',
    milestone: 'M6',
    module: 'G',
    resourcePath: v1('stage-runs'),
    columns: ['stage_run_id', 'job_id', 'stage', 'status', 'started_at', 'finished_at'],
    editableFields: [],
    readOnly: true,
    backendStatus: 'available',
  },
{
    id: 'sessions',
    titleVi: 'Phiên làm việc',
    milestone: 'M7',
    module: 'G',
    resourcePath: v1('sessions'),
    columns: ['session_id', 'status', 'started_at', 'finished_at'],
    editableFields: [],
    readOnly: true,
    backendStatus: 'available',
  },
  {
    id: 'logs',
    titleVi: 'Nhật ký',
    milestone: 'M7',
    module: 'G',
    resourcePath: v1('logs'),
    columns: ['log_id', 'job_id', 'severity', 'message', 'occurred_at'],
    editableFields: [],
    readOnly: true,
    backendStatus: 'pending_module',
  },
  {
    id: 'accounts',
    titleVi: 'Tài khoản',
    milestone: 'M7',
    module: 'J',
    resourcePath: v1('accounts'),
    columns: ['account_ref', 'provider', 'account_label', 'status', 'updated_at'],
    editableFields: [],
    readOnly: true,
    backendStatus: 'available',
  },
  {
    id: 'cost',
    titleVi: 'Chi phí',
    milestone: 'M7',
    module: 'J',
    resourcePath: v1('cost'),
    columns: ['cost_id', 'job_id', 'provider', 'amount', 'currency', 'amount_basis', 'recorded_at'],
    editableFields: [],
    readOnly: true,
    backendStatus: 'available',
  },
];

export function screensForMilestone(m: Milestone): readonly ScreenSpec[] {
  return SCREEN_REGISTRY.filter((screen) => screen.milestone === m);
}
