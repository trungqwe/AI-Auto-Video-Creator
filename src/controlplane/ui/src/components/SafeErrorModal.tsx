import React, { useState } from 'react';
import { ProblemDetail, TechnicalDetail } from '../types/api.ts';
import { fetchTechnicalDetail } from '../api/client.ts';

interface SafeErrorModalProps {
  error: ProblemDetail | { title?: string; detail?: string; technical_detail_ref?: string; code?: string } | null;
  onClose: () => void;
}

export const SafeErrorModal: React.FC<SafeErrorModalProps> = ({ error, onClose }) => {
  const [technicalDetail, setTechnicalDetail] = useState<TechnicalDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  if (!error) return null;

  const handleFetchTechnicalDetail = async () => {
    if (!error.technical_detail_ref) return;
    setLoadingDetail(true);
    setDetailError(null);
    try {
      const detail = await fetchTechnicalDetail(error.technical_detail_ref);
      setTechnicalDetail(detail);
    } catch (err) {
      setDetailError(err instanceof Error ? err.message : 'Không thể lấy chi tiết kỹ thuật an toàn');
    } finally {
      setLoadingDetail(false);
    }
  };

  return (
    <div className="modal-overlay" data-testid="error-modal-overlay">
      <div className="modal-content" data-testid="safe-error-modal">
        <div className="modal-header">
          <h3 className="modal-title" data-testid="error-modal-title">
            {error.title || 'Thông Báo Lỗi Hệ Thống'}
          </h3>
          <button
            className="btn btn-secondary"
            onClick={onClose}
            data-testid="close-error-modal-btn"
            style={{ padding: '0.25rem 0.5rem', minWidth: 'auto' }}
          >
            ✕
          </button>
        </div>

        <div className="modal-body">
          {error.code && (
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
              Mã lỗi chuẩn: <strong style={{ color: 'var(--color-danger)' }}>{error.code}</strong>
            </div>
          )}

          <div className="error-detail-box" data-testid="error-modal-detail">
            {/* React escapes content safely, preventing any XSS execution */}
            {error.detail || 'Đã xảy ra lỗi trong quá trình xử lý yêu cầu.'}
          </div>

          {error.technical_detail_ref && (
            <div style={{ marginTop: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                Mã tham chiếu chẩn đoán an toàn:
                <br />
                <code
                  data-testid="technical-detail-ref"
                  style={{
                    display: 'inline-block',
                    padding: '0.25rem 0.5rem',
                    backgroundColor: 'var(--bg-surface)',
                    borderRadius: '4px',
                    marginTop: '0.25rem',
                    color: 'var(--text-primary)',
                  }}
                >
                  {error.technical_detail_ref}
                </code>
              </div>

              {!technicalDetail && (
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={handleFetchTechnicalDetail}
                  disabled={loadingDetail}
                  data-testid="fetch-technical-detail-btn"
                  style={{ alignSelf: 'flex-start' }}
                >
                  {loadingDetail ? 'Đang truy xuất...' : 'Truy xuất chi tiết lỗi an toàn'}
                </button>
              )}

              {detailError && (
                <div style={{ fontSize: '0.8125rem', color: 'var(--color-danger)' }}>
                  {detailError}
                </div>
              )}

              {technicalDetail && (
                <div
                  className="error-detail-box"
                  data-testid="technical-detail-content"
                  style={{ maxHeight: '180px', overflowY: 'auto' }}
                >
                  <div style={{ marginBottom: '0.25rem', fontWeight: 600 }}>
                    Loại ngoại lệ: {technicalDetail.error_type}
                  </div>
                  <pre
                    style={{
                      whiteSpace: 'pre-wrap',
                      fontFamily: 'monospace',
                      fontSize: '0.75rem',
                      color: 'var(--text-secondary)',
                    }}
                  >
                    {technicalDetail.internal_detail}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onClose}
            data-testid="dismiss-error-modal-btn"
          >
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
};