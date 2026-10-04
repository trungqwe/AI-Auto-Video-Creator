import React, { useMemo } from 'react';
import { AgGridReact } from 'ag-grid-react';
import { ColDef, ICellRendererParams } from 'ag-grid-community';
import { BatchItem } from '../types/api.ts';

interface BatchesGridProps {
  batches: BatchItem[];
}

export const BatchesGrid: React.FC<BatchesGridProps> = ({ batches }) => {
  const columnDefs = useMemo<ColDef<BatchItem>[]>(() => {
    return [
      {
        field: 'batch_id',
        headerName: 'Mã Lô (Batch ID)',
        minWidth: 260,
        flex: 2,
        cellRenderer: (params: ICellRendererParams<BatchItem>) => {
          return <span style={{ fontFamily: 'monospace' }}>{params.value}</span>;
        },
      },
      {
        field: 'status',
        headerName: 'Trạng thái',
        width: 140,
        cellRenderer: (params: ICellRendererParams<BatchItem>) => {
          const val = (params.value || 'CREATED').toUpperCase();
          let cls = 'pill-accepted';
          if (val === 'RUNNING' || val === 'ACTIVE') cls = 'pill-running';
          if (val === 'COMPLETED' || val === 'SUCCEEDED') cls = 'pill-succeeded';
          if (val === 'FAILED') cls = 'pill-failed';
          return <span className={`pill ${cls}`}>{val}</span>;
        },
      },
      {
        field: 'target_count',
        headerName: 'Mục tiêu video',
        width: 150,
      },
      {
        field: 'created_at',
        headerName: 'Thời gian tạo',
        flex: 1.5,
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
    <div className="panel" data-testid="batches-panel">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">Danh Sách Lô Sản Xuất (Batches)</h2>
          <p className="panel-subtitle">Dữ liệu lô sản xuất lấy từ Control API thực tế</p>
        </div>
        <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
          Tổng số: <strong>{batches.length}</strong>
        </span>
      </div>

      <div className="ag-theme-quartz-dark" style={{ height: 420, width: '100%' }}>
        <AgGridReact<BatchItem>
          rowData={batches}
          columnDefs={columnDefs}
          defaultColDef={defaultColDef}
          animateRows={true}
          pagination={true}
          paginationPageSize={10}
          paginationPageSizeSelector={[10, 20, 50]}
          getRowId={(params) => params.data.batch_id}
          overlayNoRowsTemplate="<span>Chưa có lô sản xuất nào</span>"
        />
      </div>
    </div>
  );
};