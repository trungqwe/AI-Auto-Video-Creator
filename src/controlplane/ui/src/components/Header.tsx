import React from 'react';

interface HeaderProps {
  sseStatus: 'connecting' | 'connected' | 'disconnected' | 'resync';
  lastCursor: string | null;
  workspaceId: string;
  onRefresh: () => void;
  onOpenTestError: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  sseStatus,
  lastCursor,
  workspaceId,
  onRefresh,
  onOpenTestError,
}) => {
  const statusLabels: Record<string, string> = {
    connected: 'Đã kết nối luồng SSE',
    connecting: 'Đang kết nối...',
    disconnected: 'Mất kết nối — Đang thử lại...',
    resync: 'Cần đồng bộ lại dữ liệu',
  };

  return (
    <header className="app-header">
      <div className="brand-section">
        <h1 className="brand-title">Bảng Điều Khiển Quản Trị - AI Video</h1>
        <div className={`status-badge ${sseStatus}`} data-testid="sse-status-badge">
          <span className="indicator-dot"></span>
          <span>{statusLabels[sseStatus] || sseStatus}</span>
        </div>
      </div>

      <div className="header-status-group">
        <div className="header-meta">
          <span>Không gian: <strong>{workspaceId || 'Mặc định'}</strong></span>
          {lastCursor && <span>Cursor: <strong>{lastCursor}</strong></span>}
        </div>
        <button
          className="btn btn-secondary"
          onClick={onRefresh}
          title="Tải lại danh sách từ API"
          data-testid="refresh-btn"
        >
          Làm mới
        </button>
        <button
          className="btn btn-secondary"
          onClick={onOpenTestError}
          title="Kiểm thử modal chẩn đoán lỗi an toàn"
          data-testid="test-error-modal-btn"
        >
          Kiểm tra Modal Lỗi
        </button>
      </div>
    </header>
  );
};