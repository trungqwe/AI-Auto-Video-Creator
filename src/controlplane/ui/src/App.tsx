import React, { useCallback, useEffect, useRef, useState } from 'react';
import { BatchItem, CommandReceipt, JobItem, OperationItem, ProblemDetail, SSEEventPayload } from './types/api.ts';
import {
  ApiError,
  bootstrapSession,
  fetchBatches,
  fetchJobs,
  fetchOperations,
  subscribeToOperationsStream,
} from './api/client.ts';
import { Header } from './components/Header.tsx';
import { CommandForm } from './components/CommandForm.tsx';
import { OperationsGrid } from './components/OperationsGrid.tsx';
import { BatchesGrid } from './components/BatchesGrid.tsx';
import { JobsGrid } from './components/JobsGrid.tsx';
import { SafeErrorModal } from './components/SafeErrorModal.tsx';
import { createBoundedEventDeduper, type BoundedEventDeduper } from './features/stream/boundedEventDeduper.ts';
import { FORBIDDEN_EDITABLE_FIELDS, SCREEN_REGISTRY, screensForMilestone, type Milestone, type ScreenSpec } from './features/screens/screenRegistry.ts';

const SCREEN_MILESTONES: readonly Milestone[] = ['M2', 'M3', 'M4', 'M5', 'M6', 'M7'];

const BACKEND_STATUS_LABELS: Record<ScreenSpec['backendStatus'], string> = {
  available: 'Sẵn sàng',
  pending_module: 'Chờ phân hệ',
};

// Chỉ hiển thị trường sửa được nằm ngoài danh sách cấm; shell không dựng ô nhập nào.
const visibleEditableFields = (screen: ScreenSpec): string[] =>
  screen.editableFields.filter((field) => !(FORBIDDEN_EDITABLE_FIELDS as readonly string[]).includes(field));

const ScreensPanel: React.FC = () => (
  <div className="panel" data-testid="screens-panel">
    <div className="panel-header">
      <div>
        <h2 className="panel-title">Danh Mục Màn Hình Theo Milestone</h2>
        <p className="panel-subtitle">Trạng thái backend lấy nguyên từ screenRegistry; tại đây không có ô nhập và không cấp thêm quyền sửa.</p>
      </div>
    </div>
    {SCREEN_MILESTONES.map((milestone) => (
      <section key={milestone} data-testid={`screens-milestone-${milestone}`}>
        <h3>{milestone}</h3>
        <table>
          <thead>
            <tr><th>Màn hình</th><th>Phân hệ</th><th>Đường dẫn</th><th>Trạng thái backend</th><th>Trường sửa được</th></tr>
          </thead>
          <tbody>
            {screensForMilestone(milestone).map((screen) => {
              const editable = visibleEditableFields(screen);
              return (
                <tr key={screen.id} data-testid={`screen-row-${screen.id}`} data-backend-status={screen.backendStatus}>
                  <td>{screen.titleVi}</td>
                  <td>{screen.module}</td>
                  <td>{screen.resourcePath}</td>
                  <td>{BACKEND_STATUS_LABELS[screen.backendStatus]}</td>
                  <td>{screen.readOnly || editable.length === 0 ? 'Chỉ đọc' : editable.join(', ')}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    ))}
  </div>
);

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'operations' | 'command' | 'batches' | 'jobs' | 'screens'>('operations');
  const [operations, setOperations] = useState<OperationItem[]>([]);
  const [batches, setBatches] = useState<BatchItem[]>([]);
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [sseStatus, setSseStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'resync'>('connecting');
  const [lastCursor, setLastCursor] = useState<string | null>(null);
  const [workspaceId, setWorkspaceId] = useState<string>('');
  const [activeError, setActiveError] = useState<ProblemDetail | null>(null);
  const [bootstrapped, setBootstrapped] = useState<boolean>(false);
  const [subscriptionEpoch, setSubscriptionEpoch] = useState<number>(0);
  const eventDeduperRef = useRef<BoundedEventDeduper>(createBoundedEventDeduper());
  const lastCursorRef = useRef<string | null>(null);

  // Load API snapshot
  const loadData = useCallback(async () => {
    try {
      const [ops, bts, jbs] = await Promise.all([
        fetchOperations(),
        fetchBatches(),
        fetchJobs(),
      ]);
      setOperations(ops);
      setBatches(bts);
      setJobs(jbs);
    } catch (err) {
      console.error('Lỗi khi nạp dữ liệu từ Control API:', err);
    }
  }, []);

  // Initialize session
  useEffect(() => {
    async function init() {
      try {
        const session = await bootstrapSession();
        setWorkspaceId(session.session_id ? 'Đang hoạt động' : '');
        setBootstrapped(true);
      } catch (err) {
        console.warn('Bootstrap tự động thất bại hoặc phiên đã tồn tại:', err);
        // Continue to load data if cookies already set
        setBootstrapped(true);
      }
    }
    init();
  }, []);

  // Load data once bootstrapped
  useEffect(() => {
    if (bootstrapped) {
      loadData();
    }
  }, [bootstrapped, loadData]);

  // Handle SSE events and stream connection
  useEffect(() => {
    if (!bootstrapped) return;

    const unsubscribe = subscribeToOperationsStream(lastCursorRef.current, {
      onEvent: (event: SSEEventPayload & { stream_event_id?: string | number }) => {
        const streamEventId = String(event.stream_event_id ?? event.cursor ?? '');
        if (streamEventId) {
          if (eventDeduperRef.current.seenBefore(streamEventId)) {
            // Deduplicate event: drop repeated stream_event_id to prevent redundant reload and overwriting lastCursor
            return;
          }
        }

        if (event.cursor) {
          const current = lastCursorRef.current;
          const isNumeric = current !== null && /^\d+$/.test(current) && /^\d+$/.test(event.cursor);
          const isNewerOrEqual = !current || (isNumeric ? BigInt(event.cursor) >= BigInt(current) : event.cursor >= current);
          if (isNewerOrEqual) {
            setLastCursor(event.cursor);
            lastCursorRef.current = event.cursor;
          }
        }

        // Authoritative execution state is reloaded from API
        if (event.resource_type === 'operation' || event.event_kind.startsWith('operation.')) {
          loadData();
        }

        if (event.event_kind.startsWith('production_batch')) {
          loadData();
        }

        if (event.resource_type === 'job' || event.event_kind.startsWith('job.')) {
          loadData();
        }
      },
      onStatusChange: (status) => {
        setSseStatus(status);
      },
      onResync: (serverCursor: string | null) => {
        // SSE cursor recovery: replace expired cursor with server-provided cursor (or null to reconnect at baseline)
        eventDeduperRef.current.clear();
        setLastCursor(serverCursor);
        lastCursorRef.current = serverCursor;
        setSubscriptionEpoch((prev) => prev + 1);
        loadData();
      },
    });

    return () => {
      unsubscribe();
    };
  }, [bootstrapped, subscriptionEpoch, loadData]);

  const handleCommandSuccess = (_receipt: CommandReceipt) => { void _receipt;
    // Refresh operations and batches immediately
    loadData();
    // Switch to operations tab or stay to show receipt
  };

  const handleCommandError = (err: unknown) => {
    if (err instanceof ApiError && err.problem) {
      setActiveError(err.problem);
    } else if (err instanceof Error) {
      setActiveError({
        type: 'about:blank',
        title: 'Lỗi Thao Tác',
        status: 400,
        detail: err.message,
        instance: 'local-err',
        code: 'CLIENT_ERROR',
        category: 'validation',
        retryable: false,
        correlation_id: 'client-err',
      });
    }
  };

  const handleTriggerTestError = () => {
    setActiveError({
      type: 'about:blank',
      title: 'Kiểm Thử Modal Lỗi & XSS',
      status: 500,
      detail: '<script>window.__xss_executed=true;</script><img src=x onerror="window.__xss_executed=true"> Lỗi kiểm thử chẩn đoán an toàn!',
      instance: 'test-instance-001',
      code: 'TEST_XSS_SANITY_CHECK',
      category: 'test',
      retryable: false,
      correlation_id: 'corr-test-xss-001',
      technical_detail_ref: '00000000-0000-0000-0000-000000000999',
    });
  };

  return (
    <div className="app-container">
      <Header
        sseStatus={sseStatus}
        lastCursor={lastCursor}
        workspaceId={workspaceId}
        onRefresh={loadData}
        onOpenTestError={handleTriggerTestError}
      />

      <main className="main-content">
        <nav className="tabs-navigation" aria-label="Điều hướng các phân hệ">
          <button
            className={`tab-button ${activeTab === 'operations' ? 'active' : ''}`}
            onClick={() => setActiveTab('operations')}
            data-testid="tab-operations"
          >
            Thao tác ({operations.length})
          </button>
          <button
            className={`tab-button ${activeTab === 'command' ? 'active' : ''}`}
            onClick={() => setActiveTab('command')}
            data-testid="tab-command"
          >
            Khởi chạy Lô Sản xuất
          </button>
          <button
            className={`tab-button ${activeTab === 'batches' ? 'active' : ''}`}
            onClick={() => setActiveTab('batches')}
            data-testid="tab-batches"
          >
            Lô sản xuất ({batches.length})
          </button>
          <button
            className={`tab-button ${activeTab === 'jobs' ? 'active' : ''}`}
            onClick={() => setActiveTab('jobs')}
            data-testid="tab-jobs"
          >
            Công việc ({jobs.length})
          </button>
          <button
            className={`tab-button ${activeTab === 'screens' ? 'active' : ''}`}
            onClick={() => setActiveTab('screens')}
            data-testid="tab-screens"
          >
            Màn hình ({SCREEN_REGISTRY.length})
          </button>
        </nav>

        <div style={{ display: activeTab === 'operations' ? 'block' : 'none' }}>
          <OperationsGrid operations={operations} />
        </div>

        <div style={{ display: activeTab === 'command' ? 'block' : 'none' }}>
          <CommandForm onSuccess={handleCommandSuccess} onError={handleCommandError} />
        </div>

        <div style={{ display: activeTab === 'batches' ? 'block' : 'none' }}>
          <BatchesGrid batches={batches} />
        </div>

        <div style={{ display: activeTab === 'jobs' ? 'block' : 'none' }}>
          <JobsGrid jobs={jobs} />
        </div>

        <div style={{ display: activeTab === 'screens' ? 'block' : 'none' }}>
          <ScreensPanel />
        </div>
      </main>

      <SafeErrorModal
        error={activeError}
        onClose={() => setActiveError(null)}
      />
    </div>
  );
};