# Báo cáo sửa kế hoạch IMPL-PLAN-PROD-WIRING (lần 3, PW-CAT1)

Ngày thực hiện: 26/10/2026. Task: IMPL-PLAN-PROD-WIRING-V3. Milestone: M7.

## Đã sửa

Nêu finding F1 (MAJOR, Auditor rủi ro, job impl-prod-wiring-r2-1792979693565 phần 1/3) được xử lý thế nào: acceptance PW-CAT1 tự mâu thuẫn vì `ValidateVariant` phải có ở cả stage `plan` và `qc` nhưng binding chỉ có một `stage_type`, còn test `test_bindings_follow_the_catalog` so chặt `binding.stage_type == stage_name`; cách xử lý là thêm trường `extra_stage_types: tuple[str, ...] = ()` cho `ActivityBinding`, `ValidateVariant` có `stage_type` = `plan` và `extra_stage_types` = `('qc',)`. Liệt kê các dòng đã sửa của `docs/implementation/prod-wiring/slices.md` trong mục PW-CAT1: requirement (2) (đổi câu `ValidateVariant` và `GenerateOutputMetadata` chuyển sang stage `plan` thành `GenerateOutputMetadata` chuyển sang `plan` còn `ValidateVariant` chạy hai stage), requirement (5) mới, instrument (version 2, `extra_stage_types`, `route_stage('qc')`), counterexample (thêm hai phản ví dụ và nêu `test_pw_cat1_catalog.py`). Nêu rõ giữ nguyên ownedPaths, dependsOn, resourceLocks, bindingRefs, testCommands, coveredIds của PW-CAT1 và mọi mục khác của slices.md, plan.md không đổi.

### Dòng test đã nghiệm thu được phép đổi

Ghi dòng `assert binding.stage_type == stage_name` (dòng 158 của `tests/integration/convergence/test_cp6_workflow_catalog.py`, hàm `test_bindings_follow_the_catalog`) sẽ đổi thành `assert stage_name in (binding.stage_type, *binding.extra_stage_types)` kèm hai assertion chặt, lý do: `ValidateVariant` là activity duy nhất chạy ở hai stage, ngoại lệ được liệt kê đóng, không nới oracle; ghi rõ việc đổi test thực hiện ở slice PW-CAT1, không phải ở task này.

## Lệnh đã chạy

1. Bước 5: Kiểm tra khoảng trắng git diff sau khi sửa slices.md
   - Lệnh: `git diff --check`
   - Mã thoát: 0
   - Kết quả: Đạt, không có lỗi khoảng trắng thừa.

2. Bước 6: Kiểm tra cấu trúc kế hoạch PW, từ khoá plan.md và tiếng Việt có dấu
   - Lệnh: kiểm tra cấu trúc 33 slice, ràng buộc dependsOn, coveredIds, từ khoá plan.md
   - Mã thoát: 0
   - Kết quả: Đạt toàn bộ các ràng buộc.

3. Bước 7: Probe kiểm tra nội dung mục PW-CAT1
   - Lệnh: probe extra_stage_types, assertion thay thế và hai assertion chặt
   - Mã thoát: 0
   - Kết quả: Đạt, không còn câu mâu thuấn.

4. Bước 9: Kiểm tra PW-CAT1 và tệp report.md
   - Lệnh: probe PW-CAT1 và report.md nêu PW-CAT1 và F1
   - Mã thoát: 0
   - Kết quả: Đạt, report.md chứa PW-CAT1 và F1.

5. Bước 10: Probe kiểm tra dấu tiếng Việt và từ khoá
   - Lệnh: probe extra_stage_types, test_bindings_follow_the_catalog, git diff --check và dấu tiếng Việt
   - Mã thoát: 0
   - Kết quả: Đạt, tiếng Việt nguyên vẹn, không có ký tự thay thế.

6. Bước 11: Kiểm tra lại khoảng trắng git diff sau khi tạo report.md
   - Lệnh: `git diff --check`
   - Mã thoát: 0
   - Kết quả: Đạt, toàn bộ thay đổi sạch khoảng trắng.

## Chưa kiểm

Không chạy pytest vì task chỉ sửa tài liệu kế hoạch trong owned paths; test thật của PW-CAT1 sẽ chạy ở slice PW-CAT1.
