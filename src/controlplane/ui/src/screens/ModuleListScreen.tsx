import React, { useCallback, useEffect, useState } from 'react';
import { fetchModulePage } from '../api/client.ts';
import type { ScreenSpec } from '../features/screens/screenRegistry.ts';
import type { ModuleRow } from '../types/api.ts';
import { formatCell } from './screenHelpers.ts';

interface ModuleListScreenProps {
  screen: ScreenSpec;
  reloadKey?: number;
  selectedRow?: ModuleRow | null;
  onSelectRow?: (row: ModuleRow) => void;
}

export const ModuleListScreen: React.FC<ModuleListScreenProps> = ({ screen, reloadKey = 0, selectedRow = null, onSelectRow }) => {
  const [rows, setRows] = useState<ModuleRow[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorText, setErrorText] = useState<string | null>(null);
  const available = screen.backendStatus === 'available';

  const loadPage = useCallback(async (cursor: string | null) => {
    setLoading(true);
    setErrorText(null);
    try {
      const page = await fetchModulePage(screen.resourcePath, cursor);
      setRows((previous) => (cursor === null ? page.items : [...previous, ...page.items]));
      setNextCursor(page.next_cursor);
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'Không tải được danh sách');
    } finally {
      setLoading(false);
    }
  }, [screen.resourcePath]);

  useEffect(() => {
    if (!available) return;
    setRows([]);
    setNextCursor(null);
    void loadPage(null);
  }, [available, loadPage, reloadKey]);

  if (!available) {
    return (
      <div className="panel" data-testid={`module-list-locked-${screen.id}`}>
        <p className="panel-subtitle">Màn hình {screen.titleVi} đang chờ phân hệ nên bị khóa và không gọi API.</p>
      </div>
    );
  }

  return (
    <div className="panel" data-testid={`module-list-${screen.id}`}>
      <div className="panel-header">
        <div>
          <h2 className="panel-title">{screen.titleVi}</h2>
          <p className="panel-subtitle">Nguồn dữ liệu {screen.resourcePath}, phân hệ {screen.module}.</p>
        </div>
      </div>
      {errorText !== null && <p className="screen-error" role="alert">{errorText}</p>}
      <table>
        <thead>
          <tr>
            {screen.columns.map((column) => <th key={column}>{column}</th>)}
            {onSelectRow && <th>Thao tác</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index} data-testid={`module-row-${screen.id}-${index}`} className={row === selectedRow ? 'row-selected' : undefined}>
              {screen.columns.map((column) => <td key={column}>{formatCell(row[column])}</td>)}
              {onSelectRow && (
                <td><button type="button" className="btn btn-secondary" onClick={() => onSelectRow(row)}>Sửa</button></td>
              )}
            </tr>
          ))}
          {!loading && errorText === null && rows.length === 0 && (
            <tr><td colSpan={screen.columns.length + (onSelectRow ? 1 : 0)}>Chưa có dữ liệu</td></tr>
          )}
        </tbody>
      </table>
      {loading && <p className="panel-subtitle">Đang tải...</p>}
      {nextCursor !== null && (
        <button type="button" className="btn btn-secondary" disabled={loading} data-testid={`module-load-more-${screen.id}`} onClick={() => void loadPage(nextCursor)}>
          Tải thêm
        </button>
      )}
    </div>
  );
};
