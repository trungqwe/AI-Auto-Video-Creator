import { FORBIDDEN_EDITABLE_FIELDS, type ScreenSpec } from '../features/screens/screenRegistry.ts';
import type { ModuleRow } from '../types/api.ts';

export type FieldKind = 'boolean' | 'list' | 'number' | 'text';

export interface FieldDraft {
  name: string;
  kind: FieldKind;
  text: string;
  checked: boolean;
}

export function formatCell(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'boolean') return value ? 'Có' : 'Không';
  if (Array.isArray(value)) return value.map((item) => formatCell(item)).join(', ');
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

// Chỉ trường nằm trong editableFields và ngoài danh sách cấm mới được dựng ô nhập hoặc gửi đi.
export function sendableFields(screen: ScreenSpec): string[] {
  return screen.editableFields.filter((field) => !(FORBIDDEN_EDITABLE_FIELDS as readonly string[]).includes(field));
}

function kindOf(value: unknown): FieldKind {
  if (typeof value === 'boolean') return 'boolean';
  if (Array.isArray(value)) return 'list';
  if (typeof value === 'number') return 'number';
  return 'text';
}

export function buildDrafts(screen: ScreenSpec, row: ModuleRow): FieldDraft[] {
  return sendableFields(screen).map((name) => {
    const value = row[name];
    const kind = kindOf(value);
    let text = '';
    if (kind === 'list') text = (value as unknown[]).map(String).join(', ');
    else if (kind !== 'boolean' && value !== null && value !== undefined) text = String(value);
    return { name, kind, text, checked: value === true };
  });
}

function parseDraft(draft: FieldDraft): unknown {
  if (draft.kind === 'boolean') return draft.checked;
  if (draft.kind === 'list') return draft.text.split(',').map((item) => item.trim()).filter((item) => item !== '');
  if (draft.kind === 'number') return draft.text.trim() === '' ? null : Number(draft.text);
  return draft.text;
}

export function buildChanges(screen: ScreenSpec, row: ModuleRow, drafts: readonly FieldDraft[]): Record<string, unknown> {
  const allowed = sendableFields(screen);
  const changes: Record<string, unknown> = {};
  for (const draft of drafts) {
    if (!allowed.includes(draft.name)) continue;
    const next = parseDraft(draft);
    const current = row[draft.name] ?? null;
    if (draft.kind === 'text' && current === null && next === '') continue;
    if (typeof next === 'number' && !Number.isFinite(next)) continue;
    if (JSON.stringify(next) !== JSON.stringify(current)) changes[draft.name] = next;
  }
  return changes;
}

export function revisionOf(row: ModuleRow): number | null {
  const value = row.revision;
  if (typeof value === 'string' && /^[0-9]+$/.test(value)) return Number(value);
  return typeof value === 'number' && Number.isInteger(value) && value >= 0 ? value : null;
}

export function rowKey(screen: ScreenSpec, row: ModuleRow): string | null {
  const value = row[screen.columns[0]];
  return typeof value === 'string' || typeof value === 'number' ? String(value) : null;
}

export function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `edit-${crypto.randomUUID()}`;
  }
  return `edit-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;
}
