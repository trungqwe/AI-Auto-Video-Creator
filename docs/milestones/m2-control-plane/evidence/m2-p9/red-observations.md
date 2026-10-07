# Quan sát Thất bại RED Oracle Milestone M2-P9

**Milestone:** M2  
**Package:** M2-P9 (Kiểm chứng Hồi quy, Quét Bảo mật, Tổng hợp Manifest & Nghiệm thu Exit Gate M2)  
**Thời điểm ghi nhận:** 2026-10-08  
**Trạng thái kiểm thử:** RED (Đúng Oracle đặc tả trong Implementation Plan)

---

## 1. Mục tiêu và Nguyên tắc Test-First của M2-P9

Theo đúng kế hoạch triển khai đã đóng băng tại `docs/milestones/m2-control-plane/implementation-plan.md` mục M2-P9:
- P9 là chặng nghiệm thu cuối cùng của Milestone M2 Control Plane.
- Để đảm bảo nguyên tắc test-first nghiêm ngặt, tệp kiểm thử `tests/m2/test_p9_m2_exit_gate.py` được tạo trước khi tổng hợp manifest và lập báo cáo kiểm toán.
- Hai bài kiểm thử Oracle RED bắt buộc phải thất bại trước khi bước sang pha tổng hợp bằng chứng:
  1. `test_tst_m2_p9_001_m2_manifest_and_gate_evaluation`: Thất bại vì chưa có tệp `manifest.json` tổng hợp trên đĩa.
  2. `test_tst_m2_p9_006_m2_exit_gate_and_audit_report`: Thất bại vì chưa có Báo cáo Kiểm toán `audit-m2.md` và `status.json` của P9.

---

## 2. Kết quả Chạy Kiểm thử RED Thực tế

Lệnh thực thi:
```sh
.venv/Scripts/python.exe -m pytest tests/m2/test_p9_m2_exit_gate.py -v --tb=short
```

Kết quả quan sát:
- Tổng số bài test thu thập: 6 items.
- Số bài test thất bại (FAILED): 2 items (đúng 2 bài RED oracle).
- Số bài test vượt qua (PASSED): 4 items (các kiểm chứng nền tảng độc lập).

### Chi tiết các lỗi RED ghi nhận:

1. **`test_tst_m2_p9_001_m2_manifest_and_gate_evaluation` (FAILED)**:
   - *Nguyên nhân thất bại*: `FileNotFoundError: Manifest file missing: docs\milestones\m2-control-plane\evidence\manifest.json`.
   - *Đánh giá*: Đây là RED hợp lệ tuyệt đối vì manifest tổng hợp toàn bộ các gói bằng chứng P0..P8 chưa được xuất bản.
2. **`test_tst_m2_p9_006_m2_exit_gate_and_audit_report` (FAILED)**:
   - *Nguyên nhân thất bại*: `AssertionError: M2 Exit Audit report missing at docs\milestones\m2-control-plane\audit-m2.md`.
   - *Đánh giá*: Báo cáo kiểm toán M2 và trạng thái `M2_READY_FOR_USER_CHECKPOINT` chưa được lập, phản ánh trung thực hiện trạng trước khi hoàn tất P9.

### Chi tiết 4 bài kiểm thử độc lập đã PASSED ngay trong pha RED:

1. **`test_tst_m2_p9_002_artifact_tamper_detection` (PASSED)**:
   - Thử nghiệm trên bản sao cô lập trong `tmp_path`: Khi sửa đổi 1 byte của artifact, engine xác thực SHA-256 lập tức phát hiện sai lệch băm và kích hoạt lỗi `ValueError: Tampered artifacts detected` fail-closed.
2. **`test_tst_m2_p9_003_m1_regression_suite_93_tests` (PASSED)**:
   - Báo cáo JUnit XML `tests/m2/evidence/m1-regression.xml` xác nhận đúng 93/93 bài test M1 đạt GREEN 100%, 0 failures, 0 errors, 0 skipped.
3. **`test_tst_m2_p9_004_secret_scanner_clean_and_fail_closed_canary` (PASSED)**:
   - Quét bảo mật độc lập trên toàn bộ mã nguồn `src/controlplane`, `tests/m2`, `docs/milestones/m2-control-plane` và `migrations`: Xác nhận 0 findings, kết luận `CLEAN`.
   - Thử nghiệm chèn canary secret vào thư mục tạm: Scanner phát hiện ngay lập tức và chuyển verdict sang `VIOLATIONS_DETECTED`.
4. **`test_tst_m2_p9_005_migration_full_down_up_cycle_disposable_db` (PASSED)**:
   - Khởi tạo cơ sở dữ liệu tạm thời `m2_p1_test_<uuid>`, áp dụng toàn bộ 8 migration forward (1..8).
   - Tiến hành rollback toàn bộ 8 migration về trạng thái ban đầu, xác minh bảng `cp_schema_migrations` và schema `controlplane` được dọn dẹp sạch sẽ.
   - Tái áp dụng toàn bộ 8 migration forward thành công mà không cần sửa bất kỳ tệp migration nào.

---

## 3. Lộ trình Chuyển Trạng thái sang GREEN

Để chuyển 2 bài test RED sang GREEN:
1. Xây dựng bộ tổng hợp băm SHA-256 toàn bộ các artifact bằng chứng từ P0..P8 và P9 (loại trừ tự tham chiếu) và ghi vào `docs/milestones/m2-control-plane/evidence/manifest.json`.
2. Tạo Báo cáo Kiểm toán Exit Gate M2 tại `docs/milestones/m2-control-plane/audit-m2.md` chứng minh độc lập 6 tiêu chí đạt chuẩn và chuyển trạng thái sang `M2_READY_FOR_USER_CHECKPOINT`.
3. Sinh các tệp bằng chứng P9: `commands.jsonl`, `status.json`, `status.md`, `hashes.sha256`.
4. Chạy lại toàn bộ test suite để đạt 6/6 PASSED cho P9, đồng thời giữ vững 174/174 test M2 và 93/93 test M1.