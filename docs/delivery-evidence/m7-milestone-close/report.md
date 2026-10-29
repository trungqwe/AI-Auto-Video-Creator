# Báo cáo đóng M7 (revision 4) - ĐẠT

## 1. Phạm vi và candidate

- Task: `M7-MILESTONE-CLOSE-R4` (đóng milestone M7, revision 4).
- Base tích hợp: `f080601bae4ed341837157aaf87b3bcd85bd7424` (đã tích hợp gói `ADAPT-F-FIX1` trên base `069d9743c18cab0003b35fcd4f81ee3b3ce622a5`).
- Candidate: `380f128bfe3c1e7e4b862ed2a8768b9344e43e91` (HEAD sau rebase lên integration head `f080601bae4ed341837157aaf87b3bcd85bd7424`).
- Interpreter khoá của lane: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\1ca840a7\venv\Scripts\python.exe`.
- Ngày thực thi: `2026-10-29`.
- Owned paths: `docs/delivery-evidence/m7-milestone-close/**`. Cấm sửa đổi bất kỳ tệp nào ngoài phạm vi này.

## 2. Lý do rebase (DEPENDENCY_FIXED)

Grant G2 trước đó bị Control thu hồi với lý do `DEPENDENCY_FIXED` sau khi gói sửa lỗi `ADAPT-F-FIX1` (commit `110ba265a338`) được hợp nhất vào nhánh tích hợp tại `f080601bae4ed341837157aaf87b3bcd85bd7424`.
Lỗi assertion cũ tại `tests/integration/adapt/f/test_adapt_f_render.py:182` (khẳng định graph cũ thiếu `setsar=1` mà lệnh render R9 F-10-FIX1 đã bổ sung) đã được khắc phục hoàn toàn.
Sau khi rebase thành công lên `f080601bae4ed341837157aaf87b3bcd85bd7424`, toàn bộ 467/467 đoạn lệnh kiểm bắt buộc đã được chạy lại trên candidate mới `380f128bfe3c1e7e4b862ed2a8768b9344e43e91` và đều đạt 100% exit code 0.

## 3. Revision trước đã đóng mà không tích hợp

Milestone đóng mốc revision 3 (`M7-MILESTONE-CLOSE-R3`) đã được đóng mà không tích hợp.
Lý do mở lại revision 4 (theo kế hoạch mở lại `docs/plans/PROD_WIRING_REOPEN_PLAN_20261025.md`):
R3 chắc chắn phải chạy lại thành R4 vì các gói `RS-1..RS-13`, bốn gói sửa read-screens (`CP-4B-UI-SCREENS-FIX3`, `CP-4-WIRING-FIX3`, `ADAPT-PROD-FIX3`, `CP-4B-UI-SCREENS-FIX4`), gói kế hoạch PW (`IMPL-PLAN-PROD-WIRING`), các gói `PW-*` và cổng `GATE-PW-E2E` không nằm trong danh sách `coveredTasks` đã đóng băng của R3. R3 được retire để không đốt một lượt kiểm 22-25 phút và một lượt kiểm định Auditor rủi ro vô ích.

Bảng kiểm lại các điểm bổ sung của R4 so với R3 trên candidate hiện hành:
| Hạng mục bổ sung của R4 | Vị trí kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Bốn gói sửa read-screens (`CP-4B-UI-SCREENS-FIX3/4`, `CP-4-WIRING-FIX3`, `ADAPT-PROD-FIX3`) | Chuỗi 3 (đoạn 68, 75, 76, 81) | Exit 0 (toàn bộ probe và test đạt) |
| Gói kế hoạch PW (`IMPL-PLAN-PROD-WIRING`) | Chuỗi 4 (đoạn 82..83), Chuỗi 20..21 | Exit 0 (toàn bộ probe và test đạt) |
| Các gói tính năng PW (`PW-*`) và các gói sửa PW | Chuỗi 5, Chuỗi 20, Chuỗi 21 | Exit 0 (toàn bộ test đạt) |
| Cổng `GATE-PW-E2E` | `gate-releases.md` & Chuỗi 21 đoạn 24 (`test_pw_e2e_batch_video.py`) | Exit 0 (10 passed, 1 warning in 120.60s) |
| Toàn bộ chuỗi `RS-1..RS-13` (read-screens) | Chuỗi 22 (đoạn 436..461) | Exit 0 (13 test + 13 probe đạt) |

## 4. Gói được bao phủ

- Toàn bộ 99 gói được bao phủ theo yêu cầu nghiệm thu kèm SHA tích hợp 40 hex đã được liệt kê đầy đủ tại [packages.md](packages.md). 100% SHA tích hợp được xác nhận là tổ tiên của HEAD `380f128bfe3c1e7e4b862ed2a8768b9344e43e91`.
- Gói mốc `M7-INTEGRATION-PLAN`: Control đã xác minh receipt Auditor PASS và commit nội dung `0a3f707ffa08b3a5737be6fa30769933d2cf475d` là tổ tiên của nhánh tích hợp.
- Toàn bộ 16 cổng `GATE-*` đã có bản ghi quyết định RELEASE với mã recordHash chính xác được ghi nhận tại [gate-releases.md](gate-releases.md).

## 5. Gói retire, không được bao phủ

Hai gói kế hoạch sửa `IMPL-PLAN-PROD-WIRING-FIX1` và `IMPL-PLAN-PROD-WIRING-V3-FIX1` đã được retire và không nằm trong danh sách bao phủ:
- Đánh giá tác động: Hai gói này là các gói sửa kế hoạch trung gian của PROD-WIRING, đã bị thay thế hoàn toàn bởi `IMPL-PLAN-PROD-WIRING-V3` và `IMPL-PLAN-PROD-WIRING-V4` trong danh sách bao phủ. Do đó việc loại bỏ chúng không làm ảnh hưởng đến các exit gate `M7-R5-EG1` và `M7-R6`.
- Toàn bộ các lệnh kiểm thử của chuỗi `PW-*` vẫn được chạy đầy đủ tại Chuỗi 20 và Chuỗi 21 và đều đạt exit code 0.

## 6. Kết quả lệnh kiểm

- Tổng số đoạn lệnh kiểm bắt buộc: 467 đoạn lệnh thuộc 23 chuỗi lệnh.
- Số đoạn đạt: 467/467 đoạn (exit code 0).
- Số đoạn thất bại: 0 đoạn.
- Toàn bộ nhật ký kiểm thử chi tiết từng lệnh, exit code và tóm tắt đầu ra được trình bày tại [command-results.md](command-results.md).

## 7. Đối chiếu exit gate

- Chi tiết đối chiếu toàn bộ các exit gate Milestone M7 theo roadmap được trình bày tại [exit-gates.md](exit-gates.md).
- Danh sách chờ phê duyệt của người dùng (`pendingUserCheckpoint`) chỉ bao gồm đúng 2 mục:
  1. `M7-R5-EG1`: Batch chạy không giám sát trên workload đại diện với nhà cung cấp thật (CP7).
  2. `M7-R6`: Mọi exit gate R6 Operational Baseline (G01–G07, 100 video trong 12 giờ, ≥95% hoàn thành, ngưỡng hiệu năng và chất lượng, chi phí dưới 50 USD/tháng, runbook/rollback, user nghiệm thu tại CP7).
- Các exit gate `M7-R5-EG2` đến `M7-R5-EG5` chỉ được ghi chú trong báo cáo đóng mốc theo quyết định của user ngày 2026-10-22 («Exit gate của roadmap rộng hơn kế hoạch đã duyệt chỉ được ghi chú trong báo cáo đóng mốc, không phải FAIL và không hỏi user. Việc kế hoạch đã duyệt có mà chưa nối do Control tự lập gói sửa.»).
- Kiểm thử `tests/m2/test_p7b_hardening.py::test_h36_m1_regression` được hoãn sang CP7 (`--deselect`) theo quyết định của user ngày 2026-10-21.

## 8. Kiểm tra encoding và vệ sinh

- Toàn bộ các tệp tài liệu trong `docs/delivery-evidence/m7-milestone-close/` được ghi bằng encoding UTF-8 không BOM, tiếng Việt đầy đủ dấu thanh, không có ký tự thay thế U+FFFD.
- Kiểm tra `git diff --check` đạt chuẩn, không có khoảng trắng thừa hay lỗi dòng.
- Worktree sạch, không sửa đổi bất kỳ tệp nào ngoài phạm vi `ownedPaths`.