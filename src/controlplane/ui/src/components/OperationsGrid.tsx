import React, { useMemo } from 'react';
import { AgGridReact } from 'ag-grid-react';
import { ColDef, ICellRendererParams } from 'ag-grid-community';
import { OperationItem } from '../types/api.ts';

interface OperationsGridProps {
  operations: OperationItem[];
  onSelectOperation?: (op: OperationItem) => void;
}

export const OperationsGrid: React.FC<OperationsGridProps> = ({ operations }) => {
  const columnDefs = useMemo<ColDef<OperationItem>[]>(() => {
    return [
      {
        field: 'operation_id',
        headerName: 'Mã Thao tác (Operation ID)',
        minWidth: 260,
        flex: 2,
        cellRenderer: (params: ICellRendererParams<OperationItem>) => {
          return <span style={{ fontFamily: 'monospace' }}>{params.value}</span>;
        },
      },
      {
        field: 'status',
        headerName: 'Trạng thái',
        width: 140,
        cellRenderer: (params: ICellRendererParams<OperationItem>) => {
          const val = (params.value || 'ACCEPTED').toUpperCase();
          let cls = 'pill-accepted';
          if (val === 'RUNNING') cls = 'pill-running';
          if (val === 'SUCCEEDED' || val === 'COMPLETED') cls = 'pill-succeeded';
          if (val === 'FAILED') cls = 'pill-failed';
          return <span className={`pill ${cls}`} data-testid={`operation-status-${val.toLowerCase()}`}>{val}</span>;
        },
      },
      {
        field: 'latest_event_kind',
        headerName: 'Loại sự kiện mới nhất',
        width: 180,
        valueFormatter: (params) => params.value || 'chưa có',
      },
      {
        field: 'latest_safe_summary',
        headerName: 'Tóm tắt an toàn',
        flex: 2,
        minWidth: 200,
        valueFormatter: (params) => params.value || 'N/A',
      },
      {
        field: 'command_ref',
        headerName: 'Mã Lệnh (Command ID)',
        flex: 1.5,
        minWidth: 180,
      },
      {
        field: 'accepted_at',
        headerName: 'Thời điểm tiếp nhận',
        width: 200,
        valueFormatter: (params) => {
          if (!params.value) return 'N/A';
          try {
            return new Date(params.value).toLocaleString('vi-VN');
          } catch {
            return params.value;
          }
        },
      },
    ];
  }, []);

  const defaultColDef = useMemo<ColDef>(() => {
    return {
      sortable: true,
      filter: true,
      resizable: true,
    };
  }, []);

  return (
    <div className="panel" data-testid="operations-panel">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">Danh Sách Thao Tác (Operations)</h2>
          <p className="panel-subtitle">
            Cập nhật thời gian thực qua luồng SSE (/v1/operations/stream) từ Control API
          </p>
        </div>
        <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
          Tổng số: <strong>{operations.length}</strong>
        </span>
      </div>

      <div className="ag-theme-quartz-dark" style={{ height: 420, width: '100%' }}>
        <AgGridReact<OperationItem>
          rowData={operations}
          columnDefs={columnDefs}
          defaultColDef={defaultColDef}
          animateRows={true}
          pagination={true}
          paginationPageSize={10}
          paginationPageSizeSelector={[10, 20, 50]}
          getRowId={(params) => params.data.operation_id}
          overlayNoRowsTemplate="<span>Chưa có thao tác nào trong không gian làm việc</span>"
        />
      </div>
    </div>
  );
};