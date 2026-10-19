import type { OperationStatus } from '../../types/operationView.ts';

export interface StatusPresentation {
  label: string;
  cssClass: string;
  terminal: boolean;
  attention: boolean;
}

export const STATUS_PRESENTATION: Record<OperationStatus, StatusPresentation> = {
  accepted: { label: 'Đã tiếp nhận', cssClass: 'pill-accepted', terminal: false, attention: false },
  running: { label: 'Đang chạy', cssClass: 'pill-running', terminal: false, attention: false },
  waiting: { label: 'Đang chờ', cssClass: 'pill-waiting', terminal: false, attention: true },
  outcome_unknown: { label: 'Chưa xác định kết quả', cssClass: 'pill-outcome-unknown', terminal: false, attention: true },
  succeeded: { label: 'Thành công', cssClass: 'pill-succeeded', terminal: true, attention: false },
  failed: { label: 'Thất bại', cssClass: 'pill-failed', terminal: true, attention: true },
};

export const UNRECOGNIZED_STATUS_PRESENTATION: StatusPresentation = {
  label: 'Không nhận diện được',
  cssClass: 'pill-unknown',
  terminal: false,
  attention: true,
};

function normalize(value: string | null | undefined): string {
  return typeof value === 'string' ? value.trim().toLowerCase() : '';
}

export function presentStatus(value: string | null | undefined): StatusPresentation {
  const key = normalize(value);
  if (Object.prototype.hasOwnProperty.call(STATUS_PRESENTATION, key)) {
    return STATUS_PRESENTATION[key as OperationStatus];
  }
  return UNRECOGNIZED_STATUS_PRESENTATION;
}

export const ARTIFACT_AVAILABILITY_STATES = [
  'original',
  'processed',
  'uncertain',
  'failed',
  'unavailable',
] as const;

export type ArtifactAvailability = (typeof ARTIFACT_AVAILABILITY_STATES)[number];

export interface ArtifactAvailabilityPresentation {
  label: string;
}

export const ARTIFACT_AVAILABILITY_PRESENTATION: Record<ArtifactAvailability, ArtifactAvailabilityPresentation> = {
  original: { label: 'Bản gốc' },
  processed: { label: 'Đã xử lý' },
  uncertain: { label: 'Chưa chắc chắn' },
  failed: { label: 'Lỗi' },
  unavailable: { label: 'Không khả dụng' },
};

export function presentArtifactAvailability(value: string | null | undefined): ArtifactAvailabilityPresentation {
  const key = normalize(value);
  if (Object.prototype.hasOwnProperty.call(ARTIFACT_AVAILABILITY_PRESENTATION, key)) {
    return ARTIFACT_AVAILABILITY_PRESENTATION[key as ArtifactAvailability];
  }
  return { label: UNRECOGNIZED_STATUS_PRESENTATION.label };
}
