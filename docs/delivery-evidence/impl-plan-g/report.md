# Báo cáo bằng chứng IMPL-PLAN-G

- Task: `IMPL-PLAN-G` (planning_package), trigger INITIAL. Base: `ccbfbb5771f4b8bca783f3d2c94cbcc7f328d5b4`.
- Tệp tạo mới: `docs/implementation/g/plan.md`, `docs/implementation/g/slices.md` (14 slice G-01..G-14), `docs/delivery-evidence/impl-plan-g/report.md`.

## Nguồn đã đọc

- `docs/modules/capability-g-orchestration.md`
- `docs/09-contracts/09-orchestration-contracts.md`
- `docs/09-contracts/03-workflow-and-execution.md`
- `docs/09-contracts/12-state-machines.md`
- `docs/09-contracts/02-domain-events.md`
- `docs/09-contracts/00-common-contract.md`
- `docs/09-contracts/01-control-api-and-stream.md`
- `docs/09-contracts/11-configuration-security-contracts.md`
- `docs/11-roadmap.md` (§8–§14, ROADMAP-OPEN)
- `docs/10-test-strategy.md`
- `docs/adr/0003-durable-workflow-engine.md`
- `docs/adr/0004-commit-idempotency-and-fencing.md`
- `docs/parallel-delivery/ownership-and-locks.yaml`
- `docs/parallel-delivery/contract-registry.yaml`
- `docs/parallel-delivery/schedule-policy.yaml`
- `docs/parallel-delivery/bindings/README.md`
- `docs/parallel-delivery/bindings/g-activity-execution.json`
- `docs/parallel-delivery/bindings/g-c-i-completion.json`
- `docs/parallel-delivery/bindings/domain-event-envelope.json`
- `docs/parallel-delivery/bindings/b-d-production-snapshot.json`
- `tests/fixtures/contracts/g-activity-execution/payloads.json`
- `tests/fixtures/contracts/g-c-i-completion/payloads.json`
- `docs/parallel-delivery/errata/m7-integration.md`
- `src/controlplane/domain/orchestration/__init__.py`
- `src/controlplane/application/orchestration/__init__.py`
- `src/controlplane/application/orchestration/start_batch.py`
- `src/controlplane/infrastructure/db/orchestration/__init__.py`
- `src/controlplane/infrastructure/db/migrations/0006_orchestration_shell.sql`
- `src/controlplane/domain/statemachine/__init__.py`
- `src/controlplane/domain/events/contracts.py`
- `src/controlplane/domain/interfaces/uow.py`
- `tests/m2/test_p6_orchestration_shell.py`
- `docs/implementation/a/plan.md`, `c/plan.md`, `d/plan.md`, `i/plan.md`, `i/slices.md`, `j/plan.md`
- `pyproject.toml`

## Quyết định D8 (chi tiết ở plan.md mục 6)

- D8-G-01 Mỗi attempt là StageRun mới; hàng không có cạnh thoát được đánh dấu superseded, không thêm cạnh state machine.
- D8-G-02 Disposition `waiting` khi RUNNING: job WAITING, stage RUNNING → STALE khi grant mất hiệu lực.
- D8-G-03 `recovery_epoch` là chuỗi opaque, so bằng `str()`.
- D8-G-04 `GrantClaims` riêng, không sửa `ExecutionGrant` P6.
- D8-G-05 `stage_type` là tập mở dạng chuỗi.
- D8-G-06 Wait reason đúng 8 giá trị; bão hòa tài nguyên là deferral, thiếu đĩa là `insufficient_disk`.
- D8-G-07 Ngưỡng, timeout, retry là tham số bắt buộc từ cấu hình J.
- D8-G-08 Kiểm thử đồng thời bằng fake có khóa luồng.
- D8-G-09 Module mới cạnh P6/P7A, không sửa `__init__.py`.
- D8-G-10 Event envelope: `schema_version` `1`, sensitivity `internal`.
- D8-G-11 Không lập slice pause/resume/cancel.
- D8-G-12 Khóa registry theo workspace.
- D8-G-13 Không import `temporalio` trong slice.
- D8-G-14 Trường ledger ngoài request lấy từ ngữ cảnh qua port.

## Quyết định D10

Không thêm thư viện. Slice chỉ dùng stdlib và `pytest==9.1.1` đã khoá. Gói đã khai cho wiring và CP7 của hội tụ: `temporalio==1.32.0`, `psycopg[binary]==3.3.5`, `psycopg-pool==3.3.1`; kế hoạch không đề xuất gói mới.

## Danh sách chờ user (chưa duyệt)

PUC-G-01 (múi giờ), PUC-G-02 (khoảng trống CT-STATE-008), PUC-G-03 (pause/resume/cancel), PUC-G-04 (TEST-OPEN-003), PUC-G-05 (scale và ngưỡng R6), PUC-G-06 (backup/restore), PUC-G-07 (D5, USER-CKPT-D9-D10), PUC-G-08 (duyệt mốc A-B, C-I, D, E-F, R5/R6).

## Yêu cầu gửi IMPL-PLAN-CONVERGENCE

YC-HT-G-01..YC-HT-G-10 (plan.md mục 9): migration, composition root, binding, state machine, workflow, control API, outbox, UI shell, tài liệu và catalog, tích hợp A-18.

## Đính chính tài liệu cũ

ERR-G-01..08 (plan.md mục 1.1): đường dẫn allowed path, CT-API-001/CT-BAT-001, CT-ORC-002 so với CT-ORC-008, nhãn INV-010/016/017, lệnh unittest và trạng thái job không tồn tại, tên aggregate, nguồn ngưỡng admission, phạm vi transaction completion.

## Lệnh kiểm

Ghi lại sau khi chạy (lệnh, exit code, kết quả):

| Lệnh | Exit code | Kết quả |
|---|---|---|
| git diff --check | 0 | không có output |
| Lệnh kiểm bắt buộc python -c (plan/slices) | 0 | không có output |
| Probe phong bì ownedPaths (bước 27) | 0 | không có output |
| Probe tệp binding/fixture tồn tại (bước 28) | 0 | không có output |

Interpreter: C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe
