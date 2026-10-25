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

- Finding: F1 (MAJOR), PLAN_ACTIVATION_CONFLICT — `PP-8` vẫn sở hữu `tools/launcher/launcher.py` (trùng `ADAPT-LAUNCH` của impl-adapt-r1) và khai khóa ngoài phong bì; `dependsOn` và khóa không được kiểm tra chồng đường dẫn nên xung đột còn nguyên.
- Cách giải (bỏ quyền sở hữu thay vì xin khóa): `PP-8` không còn sở hữu `tools/launcher/launcher.py`; `ownedPaths` của `PP-8` là `assembly.py`, `test_pp_8_assembly.py`, `docs/delivery-evidence/pp-8/report.md`; `resourceLocks` của `PP-8` chỉ còn `LOCK-PROD-PORTS`; `dependsOn` của `PP-8` là `PP-1` đến `PP-7`; `PP-8` đổi từ `convergence_slice` sang `work_package_slice`.
- Đấu nối launcher chuyển thành bàn giao: plan.md mục 5.1 mô tả gói đấu nối launcher do Control lập sau `PP-8` (GIẢ ĐỊNH mã `WIRE-LAUNCHER-PROD-PORTS`, giữ `LOCK-COMPOSITION-ROOT`, phụ thuộc `PP-8` và `ADAPT-LAUNCH`); thêm OI-PP-08; CP7-1 chỉ chạy lại sau gói đó.
- Tệp đã sửa: `docs/implementation/prod-ports/slices.md` (dòng mở đầu và mục `PP-8`), `docs/implementation/prod-ports/plan.md` (mục 1 điểm 3 và 4, mục 5 và mới 5.1, mục 6, mục 7 OI-PP-08, mục 8 điểm 2 và 6), báo cáo này.
- Không đổi `PP-1` đến `PP-7`, không đổi OI-PP-01 đến OI-PP-07, không đổi phạm vi adapter của `PP-8` (`build_production_ports`, `describe_runtime_ports`).
- Lệnh đã chạy: `git diff --check`, probe bắt buộc của task và probe kiểm F1 của Orchestrator; Worker ghi mã thoát từng lệnh khi báo cáo.
