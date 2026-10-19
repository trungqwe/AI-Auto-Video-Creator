import React from 'react';
import { presentStatus } from '../features/operations/statusPresentation.ts';

export const StatusPill: React.FC<{ status: string | null | undefined; testIdPrefix?: string }> = ({ status, testIdPrefix }) => {
  const presentation = presentStatus(status);
  const normalized = typeof status === 'string' ? status.trim().toLowerCase() : '';
  const suffix = normalized === '' ? 'unknown' : normalized;
  return (
    <span
      className={`pill ${presentation.cssClass}`}
      role="status"
      aria-label={presentation.label}
      data-testid={`${testIdPrefix ?? 'status'}-${suffix}`}
    >
      {presentation.label}
    </span>
  );
};
