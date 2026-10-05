import {
  BatchItem,
  CommandReceipt,
  JobItem,
  OperationItem,
  ProblemDetail,
  SSEEventPayload,
  TechnicalDetail,
} from '../types/api.ts';

export class ApiError extends Error {
  problem?: ProblemDetail;
  status: number;

  constructor(message: string, status: number, problem?: ProblemDetail) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.problem = problem;
  }
}

export function getCsrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : '';
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers || {});
  const method = (init.method || 'GET').toUpperCase();

  if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') {
    const csrf = getCsrfToken();
    if (csrf && !headers.has('X-CSRF-Token')) {
      headers.set('X-CSRF-Token', csrf);
    }
  }

  const response = await fetch(path, {
    ...init,
    headers,
    credentials: 'include',
  });

  const contentType = response.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json') || contentType.includes('application/problem+json');

  if (!response.ok) {
    if (isJson) {
      const problem = (await response.json()) as ProblemDetail;
      throw new ApiError(
        problem.detail || problem.title || `Yêu cầu thất bại với mã ${response.status}`,
        response.status,
        problem
      );
    }
    const text = await response.text();
    throw new ApiError(text || `Lỗi máy chủ (${response.status})`, response.status);
  }

  if (isJson) {
    return (await response.json()) as T;
  }
  return (await response.text()) as unknown as T;
}

export async function bootstrapSession(capabilityToken?: string): Promise<{ session_id: string; status: string }> {
  let token = capabilityToken;
  if (!token) {
    // Check if test-driver can issue a capability in test environment
    try {
      const res = await fetch('/test-driver/issue-capability', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      if (res.ok) {
        const data = await res.json();
        token = data.capability;
      }
    } catch {
      // Continue if test-driver is not present
    }
  }

  if (!token) {
    throw new Error('Cần có Launch Capability để khởi tạo phiên đăng nhập');
  }

  return request<{ session_id: string; status: string }>('/v1/session/bootstrap', {
    method: 'POST',
    headers: {
      'x-launch-capability': token,
    },
  });
}

export async function fetchOperations(): Promise<OperationItem[]> {
  const data = await request<{ items: OperationItem[]; next_cursor: string | null }>('/v1/operations');
  return data.items || [];
}

export async function fetchBatches(): Promise<BatchItem[]> {
  const data = await request<{ items: BatchItem[]; next_cursor: string | null }>('/v1/batches');
  return data.items || [];
}

export async function fetchJobs(): Promise<JobItem[]> {
  const data = await request<{ items: JobItem[]; next_cursor: string | null }>('/v1/jobs');
  return data.items || [];
}

export async function startProductionBatch(
  targetCount: number,
  idempotencyKey: string
): Promise<CommandReceipt> {
  return request<CommandReceipt>('/v1/batches', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': idempotencyKey,
    },
    body: JSON.stringify({
      target_completed_videos: targetCount,
    }),
  });
}

export async function fetchTechnicalDetail(detailRef: string): Promise<TechnicalDetail> {
  return request<TechnicalDetail>(`/v1/errors/${encodeURIComponent(detailRef)}`);
}

export function subscribeToOperationsStream(
  cursor: string | null,
  handlers: {
    onEvent: (event: SSEEventPayload) => void;
    onStatusChange: (status: 'connecting' | 'connected' | 'disconnected' | 'resync') => void;
    onResync: (serverCursor: string | null) => void;
  }
): () => void {
  const url = cursor ? `/v1/operations/stream?cursor=${encodeURIComponent(cursor)}` : '/v1/operations/stream';
  let eventSource: EventSource | null = null;
  let isClosed = false;

  function connect() {
    if (isClosed) return;
    handlers.onStatusChange('connecting');
    eventSource = new EventSource(url, { withCredentials: true });

    eventSource.onopen = () => {
      handlers.onStatusChange('connected');
    };

    eventSource.onerror = () => {
      if (isClosed) return;
      handlers.onStatusChange('disconnected');
    };

    const handlePayload = (eventData: string) => {
      try {
        const parsed = JSON.parse(eventData) as SSEEventPayload;
        handlers.onEvent(parsed);
      } catch (err) {
        console.warn('Không thể giải mã dữ liệu SSE:', err);
      }
    };

    // Standard operation events
    const eventKinds = [
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
    ];

    eventKinds.forEach((kind) => {
      eventSource?.addEventListener(kind, (e: MessageEvent) => {
        handlePayload(e.data);
      });
    });

    eventSource.addEventListener('resync_required', (e: MessageEvent) => {
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
      handlers.onStatusChange('resync');
      let serverCursor: string | null = null;
      try {
        if (e.data) {
          const parsed = JSON.parse(e.data);
          if (parsed && parsed.cursor != null) {
            serverCursor = String(parsed.cursor);
          }
        }
      } catch {
        // ignore parse error
      }
      handlers.onResync(serverCursor);
    });

    eventSource.onmessage = (e: MessageEvent) => {
      handlePayload(e.data);
    };
  }

  connect();

  return () => {
    isClosed = true;
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  };
}