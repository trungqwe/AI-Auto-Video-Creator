# Báo cáo bằng chứng IMPL-PLAN-H

## Môi trường

- Interpreter khoá: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `ccbfbb5771f4b8bca783f3d2c94cbcc7f328d5b4`

## Nguồn đã đọc

- `docs/09-contracts/01-control-api-and-stream.md`, `docs/09-contracts/12-state-machines.md` (CT-STATE-003, 004, 008, 009, 010), `docs/09-contracts/02-domain-events.md` (tiêu đề CT-EVT)
- `docs/11-roadmap.md` (§8–§14, ROADMAP-OPEN), `docs/10-test-strategy.md` (§12.8, §17.4, §26), `docs/03-quality-requirements.md` (QR-UX, QUALITY-OPEN)
- `docs/adr/0007-runtime-and-admin-ui.md`, `docs/milestones/m2-control-plane/spec.md`, `HANDOFF.md`
- `docs/parallel-delivery/ownership-and-locks.yaml`, `docs/parallel-delivery/bindings/README.md`, `docs/parallel-delivery/bindings/domain-event-envelope.json`, `docs/parallel-delivery/bindings/b-d-production-snapshot.json`, `docs/parallel-delivery/bindings/g-activity-execution.json`, `docs/parallel-delivery/bindings/g-c-i-completion.json`, `docs/parallel-delivery/bindings/i-artifact-version.json`, `docs/parallel-delivery/errata/m7-integration.md`
- `docs/delivery-evidence/cp1-contract-binding/report.md`, `docs/delivery-evidence/cp2a-layout/report.md`
- `docs/implementation/j/plan.md`, `docs/implementation/j/slices.md`, `docs/implementation/i/plan.md`, `docs/implementation/i/slices.md` (mẫu cấu trúc và đồng bộ YC)
- Mã H: `src/controlplane/ui/package.json`, `src/controlplane/ui/src/App.tsx`, `src/controlplane/ui/src/api/client.ts`, `src/controlplane/ui/src/types/api.ts`, `src/controlplane/ui/src/components/OperationsGrid.tsx`, `src/controlplane/ui/src/components/SafeErrorModal.tsx`, `src/controlplane/ui/src/components/CommandForm.tsx`, `src/controlplane/api/routes/control.py`, `src/controlplane/api/sse/stream.py`, `src/controlplane/application/sse/stream.py`, `src/controlplane/application/projections/operation_view_mapper.py`, `src/controlplane/application/control_api/query_ports.py`, `src/controlplane/infrastructure/db/control_api_queries.py`, `src/controlplane/infrastructure/db/projections/postgres.py`, `src/controlplane/requirements.lock`, `pyproject.toml`

## RED

- Ở HEAD `ccbfbb5` thư mục `docs/implementation/h` chưa tồn tại (xác nhận khi lập lệnh), nên instrument nghiệm thu không thể đạt vì thiếu `plan.md` và `slices.md`.

## Thay đổi

- `docs/implementation/h/plan.md`: kế hoạch Phân hệ H (nguồn chuẩn, errata ERR-H, khoảng trống GAP-H, năng lực, vị trí mã D1, contract, exit gate, D8, D10, CP7, YC hội tụ, DAG).
- `docs/implementation/h/slices.md`: 16 slice H-01..H-16.
- `docs/delivery-evidence/impl-plan-h/report.md`: báo cáo này.

## Lệnh kiểm

| # | Lệnh | Exit code | Kết quả |
|---|---|---|---|
| 1 | `git diff --check` | 0 | kh?ng output |
| 2 | `python -c` instrument nghi?m thu (id slice duy nh?t, ?? m?c, ti?ng Vi?t c? d?u, kh?ng U+FFFD) | 0 | kh?ng output |

## Quyết định mặc định (D8)

- D8-H-01: test tĩnh bằng pytest cho TypeScript, không thêm test runner JS.
- D8-H-02: trạng thái lạ hiển thị `Không nhận diện được`, không rơi về accepted.
- D8-H-03: phân trang keyset, cursor đục, `default_limit` và `max_limit` là tham số bắt buộc (50 và 100 là GIẢ ĐỊNH).
- D8-H-04: quy tắc view (finished_at, wait_reason, problem), severity log và enum trạng thái account là GIẢ ĐỊNH.
- D8-H-05: tập trường cấm sửa; articles, events, snapshots, story-angles, scripts chỉ đọc.
- D8-H-06: bốn mã lỗi của route module (VALIDATION_FAILED, FORBIDDEN_FIELD, REVISION_CONFLICT, NOT_FOUND).
- D8-H-07: không có `__init__.py` ở `api/routes/modules/`; module mới cạnh mã cũ.
- D8-H-08: màn hình chưa có backend là `pending_module`.
- D8-H-09: giữ AG Grid Community 32.3.9.
- D8-H-10: múi giờ hiển thị theo trình duyệt (GIẢ ĐỊNH).

## Quyết định thư viện (D10)

- Các slice H không cần thư viện mới. Thư viện hiện có giữ nguyên (react 18.3.1, react-dom 18.3.1, ag-grid-community 32.3.9, ag-grid-react 32.3.9, vite 6.2.0, typescript 5.7.3, @playwright/test 1.50.1).
- Test runner TypeScript và thư viện render component chỉ là đề xuất chờ USER-CKPT-D9-D10; kế hoạch không ghi số phiên bản vì chưa xác minh được.

## Danh sách chờ user (pendingUserCheckpoint)

- PUC-H-01..PUC-H-07 (múi giờ; quy mô bảng và dataset; chi tiết cột và trường sửa được; checkpoint M2 và duyệt UI theo milestone; test runner TypeScript; cơ chế cấp phiên sản xuất; D5 cho CP7). Không mục nào được coi là đã duyệt.

## Yêu cầu gửi IMPL-PLAN-CONVERGENCE

- YC-HT-H-01..YC-HT-H-10 (ownership, composition root, UI shell, control API, migration, state machine, binding, workflow, packaging, catalog test và tài liệu) — chi tiết ở `docs/implementation/h/plan.md` mục 9.

## Giới hạn

- Chỉ sửa trong `docs/implementation/h/**` và `docs/delivery-evidence/impl-plan-h/**`.
- Test tĩnh TypeScript của các slice không thay `tsc`, Playwright hay duyệt thị giác; không dùng mock để đóng gate ngoài (CP7).
- Không gọi mạng hay dịch vụ thật, không đọc bí mật, không thêm thư viện.
