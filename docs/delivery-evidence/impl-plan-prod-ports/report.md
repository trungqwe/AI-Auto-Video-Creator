# Báo cáo bằng chứng — IMPL-PLAN-PROD-PORTS

- Gói: IMPL-PLAN-PROD-PORTS (planning_package), HEAD cơ sở `4b11dd042f709fb5165793cb2fd48dc275afeebe`.
- Sản phẩm: `docs/implementation/prod-ports/plan.md` (mục 1 đến 9) và `docs/implementation/prod-ports/slices.md` (`PP-1` đến `PP-8`).

## Lệnh đã chạy

1. `git diff --check` — mã thoát: 0.
2. Probe bắt buộc của task (id slice duy nhất, năm khóa mỗi slice, bảy tên cổng trong plan.md, chữ có dấu, không ký tự thay thế) — mã thoát: 0.

## Đối chiếu yêu cầu nghiệm thu

1. Khảo sát từng Protocol, nơi gọi và adapter đã có (kèm tệp:dòng): plan.md mục 3.1, 3.2, 3.3.
2. Chia slice `PP-<số>`, adapter ở `src/controlplane/infrastructure/production_ports/**`, test ở `tests/integration/prod_ports/**`, bằng chứng ở `docs/delivery-evidence/pp-*/**`, slice cuối thay thân `_load_runtime_ports`: plan.md mục 5 và slices.md (`PP-1` đến `PP-8`).
3. `drive_placement` mặc định đơn giản, lưu ID ngoài Git, dùng lại: plan.md mục 4.6 và `PP-5`.
4. Khóa 9Router lấy từ kho DPAPI qua alias riêng, cách nhập không in giá trị: plan.md mục 4.1 và `PP-2`.
5. `gpu_lease` một GPU, có thời hạn, `GpuLeaseUnavailable` khi bận: plan.md mục 4.7 và `PP-1`.
6. Mỗi slice có test thật, máy chủ giả cục bộ cho Google và 9Router, không nhánh giả, không thư viện mới: slices.md quy tắc chung và từng slice.
7. Kiểm thật cuối `launcher.py start` mở 8443 và `status` báo đủ cổng, làm ở CP7-1: plan.md mục 6.

## Mục mở

OI-PP-01 đến OI-PP-07 theo plan.md mục 7; không mục nào được ghi là đã duyệt.

## Giới hạn

Gói chỉ lập kế hoạch; không sửa `src/**`, `tools/**`, `tests/**`; không gọi dịch vụ thật, không đọc bí mật. Nội dung do Worker (Gemini 3.8 Flash) viết, Auditor rủi ro (Opus 5.5) duyệt trước khi biên dịch.

## Sửa lần 1 (IMPL-PLAN-PROD-PORTS-FIX1)

- Finding: PLAN_ACTIVATION_CONFLICT — `PP-8` (`tools/launcher/launcher.py`) chồng đường dẫn với `ADAPT-LAUNCH` của kế hoạch impl-adapt-r1.
- Cách giải: `PP-8` khai `dependsOn` thêm `ADAPT-LAUNCH` và giữ thêm `LOCK-COMPOSITION-ROOT` (cùng khóa của `ADAPT-LAUNCH`) bên cạnh `LOCK-PROD-PORTS` và `LOCK-CONVERGENCE`; `PP-8` chạy sau `ADAPT-LAUNCH` (gói sửa ADAPT-LAUNCH-FIX1 đã tích hợp tại `21d99fc`) và là writer duy nhất của `launcher.py` trong kế hoạch này.
- Tệp đã sửa: `docs/implementation/prod-ports/slices.md` (dòng mở đầu và mục `PP-8`), `docs/implementation/prod-ports/plan.md` (mục 1 điểm 4, mục 5, mục 8 điểm 2), báo cáo này.
- Không đổi phạm vi mã nguồn của `PP-8`, không đổi `PP-1` đến `PP-7`, không đổi mục mở OI-PP-01 đến OI-PP-07.
- Lệnh đã chạy: `git diff --check` và probe bắt buộc của task, cả hai mã thoát 0 (Worker xác nhận lại khi báo cáo).
