import React, { useEffect, useState } from 'react';
import { BatchSettings, CommandReceipt } from '../types/api.ts';
import { fetchBatchSettings, startProductionBatch } from '../api/client.ts';

interface CommandFormProps {
  onSuccess: (receipt: CommandReceipt) => void;
  onError: (err: unknown) => void;
}

type ConcurrencyLimits = BatchSettings['max_concurrent_videos'];

export const CommandForm: React.FC<CommandFormProps> = ({ onSuccess, onError }) => {
  const [targetCount, setTargetCount] = useState<number>(1);
  const [idempotencyKey, setIdempotencyKey] = useState<string>(() => `key-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`);
  const [loading, setLoading] = useState<boolean>(false);
  const [lastReceipt, setLastReceipt] = useState<CommandReceipt | null>(null);

  const [settingsLoading, setSettingsLoading] = useState<boolean>(true);
  const [limits, setLimits] = useState<ConcurrencyLimits | null>(null);
  const [maxConcurrent, setMaxConcurrent] = useState<number>(1);

  useEffect(() => {
    let active = true;
    const loadSettings = async () => {
      try {
        const settings = await fetchBatchSettings();
        const loaded = settings.max_concurrent_videos;
        if (
          active &&
          Number.isInteger(loaded.min) &&
          Number.isInteger(loaded.max) &&
          Number.isInteger(loaded.default) &&
          loaded.min >= 1 &&
          loaded.max > 1 &&
          loaded.min <= loaded.max
        ) {
          setLimits(loaded);
          setMaxConcurrent(Math.min(Math.max(loaded.default, loaded.min), loaded.max));
        }
      } catch {
        // Settings unavailable: hide the select and never send max_concurrent_videos in this page session
      } finally {
        if (active) {
          setSettingsLoading(false);
        }
      }
    };
    void loadSettings();
    return () => {
      active = false;
    };
  }, []);

  const handleGenerateNewKey = () => {
    setIdempotencyKey(`key-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (settingsLoading) {
      return;
    }
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
      const receipt = await startProductionBatch(targetCount, idempotencyKey.trim(), limits ? maxConcurrent : undefined);
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

          {limits && (
            <div className="form-group">
              <label className="form-label" htmlFor="max-concurrent-select">
                Số luồng video song song (mặc định {limits.default}, tối đa {limits.max} theo tài nguyên máy)
              </label>
              <select
                id="max-concurrent-select"
                data-testid="max-concurrent-select"
                className="form-input"
                value={maxConcurrent}
                onChange={(e) => setMaxConcurrent(parseInt(e.target.value, 10))}
              >
                {Array.from({ length: limits.max - limits.min + 1 }, (_, i) => limits.min + i).map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading || settingsLoading}
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