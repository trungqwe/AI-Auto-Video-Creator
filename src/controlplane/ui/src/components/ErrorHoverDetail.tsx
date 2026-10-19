import React, { useId, useState } from 'react';

export const MAX_DETAIL_CHARS = 300;
const TRIGGER_LABEL = 'Chi tiết lỗi';
const TECHNICAL_DETAIL_LABEL = 'Xem chi tiết kỹ thuật';

export interface ErrorHoverProblem {
  title?: string;
  code?: string;
  correlation_id?: string;
  technical_detail_ref?: string;
  detail?: string;
}

interface ErrorHoverDetailProps {
  problem: ErrorHoverProblem | null | undefined;
  onOpenTechnicalDetail?: (ref: string) => void;
}

const TOOLTIP_STYLE: React.CSSProperties = {
  position: 'absolute',
  top: '100%',
  left: 0,
  zIndex: 20,
  display: 'block',
  minWidth: '220px',
  maxWidth: '340px',
  padding: '0.5rem 0.75rem',
  borderRadius: '6px',
  border: '1px solid var(--border-color, #888)',
  backgroundColor: 'var(--bg-surface)',
  color: 'var(--text-primary)',
  fontSize: '0.8125rem',
};

const LINE_STYLE: React.CSSProperties = { display: 'block', marginTop: '0.25rem' };

export const ErrorHoverDetail: React.FC<ErrorHoverDetailProps> = ({ problem, onOpenTechnicalDetail }) => {
  const [open, setOpen] = useState<boolean>(false);
  const tooltipId = useId();

  if (!problem) return null;

  const detailText = problem.detail ? Array.from(problem.detail).slice(0, MAX_DETAIL_CHARS).join('') : '';
  const technicalRef = problem.technical_detail_ref;
  const openTechnical = onOpenTechnicalDetail;

  const handleBlur = (event: React.FocusEvent<HTMLSpanElement>) => {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false);
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLSpanElement>) => {
    if (event.key === 'Escape') setOpen(false);
  };

  return (
    <span
      data-testid="error-hover-detail"
      style={{ position: 'relative', display: 'inline-block' }}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={handleBlur}
      onKeyDown={handleKeyDown}
    >
      <span
        tabIndex={0}
        aria-describedby={tooltipId}
        data-testid="error-hover-trigger"
        style={{ cursor: 'help', textDecoration: 'underline dotted' }}
      >
        {TRIGGER_LABEL}
      </span>
      {open && (
        <span role="tooltip" id={tooltipId} data-testid="error-hover-tooltip" style={TOOLTIP_STYLE}>
          {problem.title && (
            <span style={{ display: 'block', fontWeight: 600 }}>{problem.title}</span>
          )}
          {problem.code && (
            <span style={LINE_STYLE}>
              Mã lỗi: <strong>{problem.code}</strong>
            </span>
          )}
          {problem.correlation_id && (
            <span style={LINE_STYLE}>
              Mã tương quan: {problem.correlation_id}
            </span>
          )}
          {detailText && (
            <span style={{ ...LINE_STYLE, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{detailText}</span>
          )}
          {technicalRef && openTechnical && (
            <button
              type="button"
              className="btn btn-secondary"
              data-testid="error-hover-open-technical"
              style={{ ...LINE_STYLE, marginTop: '0.5rem' }}
              onClick={() => openTechnical(technicalRef)}
            >
              {TECHNICAL_DETAIL_LABEL}
            </button>
          )}
        </span>
      )}
    </span>
  );
};
