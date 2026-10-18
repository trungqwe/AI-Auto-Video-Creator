# Bàn giao phiên làm việc — CP0-GOVERNANCE (đồng bộ nguồn quyền với Phần B)

## Đã quyết định

- Nguồn quyền (D3): M3–M7, gồm Phân hệ A, thực hiện theo ủy quyền AI_SETUP (`AI_PM_DELEGATED_AUTHORITY_RULES.md`) và chỉ thị user duyệt Phần B ngày 18/10/2026 (D0–D10). Mỗi slice chỉ sửa trong owned paths và theo tiêu chí nghiệm thu được giao.
- M1 và M2-P1..P7B: `ACCEPTED / CLOSED`. M2-P8/P9 đã triển khai và có Auditor PASS; chưa ghi user checkpoint M2, không coi là user đã duyệt.
- Kích hoạt sản xuất vẫn bị chặn (`PRODUCTION_ACTIVATION_BLOCKED`).
- Commit local; push hoặc merge là quyền riêng của user.
- Registry theo D1: path G/I nằm trong các gói của `src/controlplane`; thêm `PATH-DELIVERY-EVIDENCE`, `PATH-IMPLEMENTATION-PLANS` và các lock kế hoạch/hội tụ.
- Bằng chứng (D4): từ M3 trở đi ghi vào `docs/delivery-evidence/<task-id viết thường>/report.md`; `docs/milestones/**/evidence/**` bất biến.
- `validate.py` và `validate-docs-plan.py` đọc YAML bằng bộ đọc stdlib; `.validation-report.json` lỗi thời đã gỡ.

## Chưa quyết định

- User checkpoint M2 (P8/P9) chưa được ghi.
- USER-CKPT-D9-D10 (thư viện, cách dựng lại runtime) và CP7 tài nguyên thật (D5) chờ user.
- Dữ liệu cũ của các node TASK-CAP-J-* (authority ref dạng `tệp:dòng`, contract ref `CONTRACT-CONFIG-SECURITY` không phải mã CT-*, thiếu trường bắt buộc, nhiều task granted cùng lock) làm `check_task_dag`/`check_registries` báo lỗi; để cho slice riêng.

## Tệp cần đọc tiếp

- `docs/12-pre-code-checklist.md`, `docs/11-roadmap.md` (§4)
- `docs/parallel-delivery/ownership-and-locks.yaml`, `docs/parallel-delivery/acceptance-matrix.yaml`
- `docs/delivery-evidence/cp0-governance/report.md`, `docs/delivery-evidence/cp0-governance/ownership-recheck.md`

## Điểm tiếp tục

- CP2A-LAYOUT (dependency_slice) sau khi CP0-GOVERNANCE được nghiệm thu.
