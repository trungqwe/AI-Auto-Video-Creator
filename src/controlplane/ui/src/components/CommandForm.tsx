import React, { useState } from 'react';
import { CommandReceipt } from '../types/api.ts';
import { startProductionBatch } from '../api/client.ts';

interface CommandFormProps {
  onSuccess: (receipt: CommandReceipt) => void;
  onError: (err: unknown) => void;
}

export const CommandForm: React.FC<CommandFormProps> = ({ onSuccess, onError }) => {
  const [targetCount, setTargetCount] = useState<number>(1);
  const [idempotencyKey, setIdempotencyKey] = useState<string>(() => `key-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`);
  const [loading, setLoading] = useState<boolean>(false);
  const [lastReceipt, setLastReceipt] = useState<CommandReceipt | null>(null);

  const handleGenerateNewKey = () => {
    setIdempotencyKey(`key-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (targetCount <= 0) {
      alert('Số lượng video cần hoàn thành phải lớn hơn 0');
      return;
    }
    if (!idempotencyKey.trim()) {
      alert('Vui lòng nhập Idempotency-Key');
      return;
    }

    setLoading(true);
    try {
      const receipt = await startProductionBatch(targetCount, idempotencyKey.trim());
      setLastReceipt(receipt);
      onSuccess(receipt);
    } catch (err) {
      onError(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel" data-testid="command-panel">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">Khởi chạy Lô Sản xuất (StartProductionBatch)</h2>
          <p className="panel-subtitle">Gửi lệnh tạo lô video với cơ chế khóa Idempotency chống trùng lặp</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} data-testid="start-batch-form">
        <div className="form-grid">
          <div className="form-group">
            <label className="form-label" htmlFor="target-count-input">
              Mục tiêu số video hoàn thành (target_completed_videos)
            </label>
            <input
              id="target-count-input"
              data-testid="target-count-input"
              className="form-input"
              type="number"
              min={1}
              max={100}
              value={targetCount}
              onChange={(e) => setTargetCount(parseInt(e.target.value, 10) || 1)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="idempotency-key-input">
              Khóa Idempotency (Idempotency-Key)
            </label>
            <div className="form-input-wrapper">
              <input
                id="idempotency-key-input"
                data-testid="idempotency-key-input"
                className="form-input"
                type="text"
                value={idempotencyKey}
                onChange={(e) => setIdempotencyKey(e.target.value)}
                required
              />
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleGenerateNewKey}
                data-testid="generate-key-btn"
                title="Tạo khóa ngẫu nhiên mới"
              >
                Khóa mới
              </button>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading}
            data-testid="submit-batch-btn"
          >
            {loading ? 'Đang gửi lệnh...' : 'Khởi chạy Lô Sản xuất'}
          </button>
        </div>
      </form>

      {lastReceipt && (
        <div className="receipt-card" data-testid="command-receipt-card">
          <h3 className="receipt-title">Biên nhận lệnh bền vững (CommandReceipt)</h3>
          <div className="receipt-details">
            <div className="receipt-item">
              <span className="receipt-label">Mã biên nhận (receipt_id):</span>
              <span className="receipt-value" data-testid="receipt-id-value">{lastReceipt.receipt_id}</span>
            </div>
            <div className="receipt-item">
              <span className="receipt-label">Trạng thái (disposition):</span>
              <span className="receipt-value" data-testid="receipt-disposition-value">{lastReceipt.disposition}</span>
            </div>
            <div className="receipt-item">
              <span className="receipt-label">Mã thao tác (operation_id):</span>
              <span className="receipt-value" data-testid="receipt-operation-id-value">{lastReceipt.operation_id || 'N/A'}</span>
            </div>
            <div className="receipt-item">
              <span className="receipt-label">Tài nguyên (resource_ref):</span>
              <span className="receipt-value" data-testid="receipt-resource-ref-value">
                {lastReceipt.resource_ref ? JSON.stringify(lastReceipt.resource_ref) : 'N/A'}
              </span>
            </div>
            <div className="receipt-item">
              <span className="receipt-label">Thời điểm tiếp nhận (accepted_at):</span>
              <span className="receipt-value">{lastReceipt.accepted_at}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};