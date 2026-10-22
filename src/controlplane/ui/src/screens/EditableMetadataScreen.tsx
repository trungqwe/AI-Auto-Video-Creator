import React, { useState } from 'react';
import { ApiError, patchModuleItem } from '../api/client.ts';
import type { ScreenSpec } from '../features/screens/screenRegistry.ts';
import type { ModuleRow } from '../types/api.ts';
import { ModuleListScreen } from './ModuleListScreen.tsx';
import { buildChanges, buildDrafts, newIdempotencyKey, revisionOf, rowKey, type FieldDraft } from './screenHelpers.ts';

export const EditableMetadataScreen: React.FC<{ screen: ScreenSpec }> = ({ screen }) => {
  const [reloadKey, setReloadKey] = useState<number>(0);
  const [selectedRow, setSelectedRow] = useState<ModuleRow | null>(null);
  const [drafts, setDrafts] = useState<FieldDraft[]>([]);
  const [saving, setSaving] = useState<boolean>(false);
  const [message, setMessage] = useState<string | null>(null);
  const [errorText, setErrorText] = useState<string | null>(null);

  const closeForm = () => {
    setSelectedRow(null);
    setDrafts([]);
  };

  const handleSelect = (row: ModuleRow) => {
    setSelectedRow(row);
    setDrafts(buildDrafts(screen, row));
    setMessage(null);
    setErrorText(null);
  };

  const updateDraft = (name: string, patch: Partial<FieldDraft>) => {
    setDrafts((previous) => previous.map((draft) => (draft.name === name ? { ...draft, ...patch } : draft)));
  };

  const handleSave = async (event: React.FormEvent) => {
    event.preventDefault();
    if (selectedRow === null || saving) return;
    const itemId = rowKey(screen, selectedRow);
    const revision = revisionOf(selectedRow);
    if (itemId === null || revision === null) {
      setErrorText('Dòng thiếu mã định danh hoặc revision nên không thể lưu.');
      return;
    }
    const changes = buildChanges(screen, selectedRow, drafts);
    if (Object.keys(changes).length === 0) {
      setErrorText('Không có thay đổi để lưu.');
      return;
    }
    setSaving(true);
    setMessage(null);
    setErrorText(null);
    try {
      await patchModuleItem(screen.resourcePath, itemId, revision, changes, newIdempotencyKey());
      setMessage('Đã lưu thay đổi.');
      closeForm();
      setReloadKey((previous) => previous + 1);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 409 || err.problem?.code === 'REVISION_CONFLICT')) {
        setErrorText('Dòng đã bị cập nhật ở nơi khác (xung đột revision); danh sách đã được tải lại, hãy chọn lại dòng.');
        closeForm();
        setReloadKey((previous) => previous + 1);
      } else {
        setErrorText(err instanceof Error ? err.message : 'Lưu thất bại');
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div data-testid={`editable-screen-${screen.id}`}>
      <ModuleListScreen screen={screen} reloadKey={reloadKey} selectedRow={selectedRow} onSelectRow={handleSelect} />
      {message !== null && <p className="screen-status" role="status" data-testid="metadata-saved">{message}</p>}
      {errorText !== null && <p className="screen-error" role="alert" data-testid="metadata-error">{errorText}</p>}
      {selectedRow !== null && (
        <form className="panel metadata-form" data-testid="metadata-form" onSubmit={handleSave}>
          <h3>Sửa metadata: {rowKey(screen, selectedRow)}</h3>
          {drafts.map((draft) => (
            <label key={draft.name} className="form-group">
              <span className="form-label">{draft.name}{draft.kind === 'list' ? ' (phân tách bằng dấu phẩy)' : ''}</span>
              {draft.kind === 'boolean' ? (
                <input type="checkbox" checked={draft.checked} data-testid={`metadata-field-${draft.name}`} onChange={(event) => updateDraft(draft.name, { checked: event.target.checked })} />
              ) : (
                <input className="form-input" type={draft.kind === 'number' ? 'number' : 'text'} value={draft.text} data-testid={`metadata-field-${draft.name}`} onChange={(event) => updateDraft(draft.name, { text: event.target.value })} />
              )}
            </label>
          ))}
          <div className="metadata-form-actions">
            <button type="submit" className="btn btn-primary" disabled={saving} data-testid="metadata-save">Lưu</button>
            <button type="button" className="btn btn-secondary" disabled={saving} onClick={closeForm}>Hủy</button>
          </div>
        </form>
      )}
    </div>
  );
};
