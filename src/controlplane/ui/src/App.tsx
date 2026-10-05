import React, { useCallback, useEffect, useState } from 'react';
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

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'operations' | 'command' | 'batches' | 'jobs'>('operations');
  const [operations, setOperations] = useState<OperationItem[]>([]);
  const [batches, setBatches] = useState<BatchItem[]>([]);
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [sseStatus, setSseStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'resync'>('connecting');
  const [lastCursor, setLastCursor] = useState<string | null>(null);
  const [workspaceId, setWorkspaceId] = useState<string>('');
  const [activeError, setActiveError] = useState<ProblemDetail | null>(null);
  const [bootstrapped, setBootstrapped] = useState<boolean>(false);
  const [subscriptionEpoch, setSubscriptionEpoch] = useState<number>(0);

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

    const unsubscribe = subscribeToOperationsStream(lastCursor, {
      onEvent: (event: SSEEventPayload) => {
        if (event.cursor) {
          setLastCursor(event.cursor);
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
        setLastCursor(serverCursor);
        setSubscriptionEpoch((prev) => prev + 1);
        loadData();
      },
    });

    return () => {
      unsubscribe();
    };
  }, [bootstrapped, lastCursor, subscriptionEpoch, loadData]);

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
      </main>

      <SafeErrorModal
        error={activeError}
        onClose={() => setActiveError(null)}
      />
    </div>
  );
};