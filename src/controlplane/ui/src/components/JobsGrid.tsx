import React, { useMemo } from 'react';
import { AgGridReact } from 'ag-grid-react';
import { ColDef, ICellRendererParams } from 'ag-grid-community';
import { JobItem } from '../types/api.ts';

interface JobsGridProps {
  jobs: JobItem[];
}

export const JobsGrid: React.FC<JobsGridProps> = ({ jobs }) => {
  const columnDefs = useMemo<ColDef<JobItem>[]>(() => {
    return [
      {
        field: 'job_id',
        headerName: 'Mã Công việc (Job ID)',
        minWidth: 260,
        flex: 2,
        cellRenderer: (params: ICellRendererParams<JobItem>) => {
          return <span style={{ fontFamily: 'monospace' }}>{params.value}</span>;
        },
      },
      {
        field: 'batch_id',
        headerName: 'Mã Lô (Batch ID)',
        minWidth: 200,
        flex: 1.5,
      },
      {
        field: 'status',
        headerName: 'Trạng thái',
        width: 140,
        cellRenderer: (params: ICellRendererParams<JobItem>) => {
          const val = (params.value || 'CREATED').toUpperCase();
          let cls = 'pill-accepted';
          if (val === 'RUNNING' || val === 'ACTIVE') cls = 'pill-running';
          if (val === 'COMPLETED' || val === 'SUCCEEDED') cls = 'pill-succeeded';
          if (val === 'FAILED' || val === 'FAILED_FINAL') cls = 'pill-failed';
          return <span className={`pill ${cls}`}>{val}</span>;
        },
      },
      {
        field: 'snapshot_ref',
        headerName: 'Snapshot tham chiếu',
        width: 180,
      },
      {
        field: 'revision',
        headerName: 'Phiên bản',
        width: 110,
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
    <div className="panel" data-testid="jobs-panel">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">Danh Sách Công Việc (Jobs)</h2>
          <p className="panel-subtitle">Dữ liệu các công việc render/sinh video thực tế từ Control API</p>
        </div>
        <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
          Tổng số: <strong>{jobs.length}</strong>
        </span>
      </div>

      <div className="ag-theme-quartz-dark" style={{ height: 420, width: '100%' }}>
        <AgGridReact<JobItem>
          rowData={jobs}
          columnDefs={columnDefs}
          defaultColDef={defaultColDef}
          animateRows={true}
          pagination={true}
          paginationPageSize={10}
          paginationPageSizeSelector={[10, 20, 50]}
          getRowId={(params) => params.data.job_id}
          overlayNoRowsTemplate="<span>Chưa có công việc nào trong danh sách</span>"
        />
      </div>
    </div>
  );
};