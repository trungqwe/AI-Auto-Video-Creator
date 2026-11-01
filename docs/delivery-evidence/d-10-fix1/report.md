# Báo cáo bằng chứng D-10-FIX1

## 1. Môi trường

- Interpreter: `python` trong PATH của worktree `lane-d-10-fix1` (pytest chạy với `-p no:cacheprovider`); FFmpeg ghim `C:/ffmpeg/bin/ffmpeg.exe`.
- HEAD gốc: `6972626f7a280f69293662f5d1d9446211234e9d`.
- Nguồn quyền: AI PM tự mở sau Auditor PASS của D-10; căn cứ a15a18f2, FR-REN-004 và CT-RND-003 điều kiện 3.

## 2. Lỗi đo được `OI-CP7-10-F12`

- Lô 640438e3-8cb6-43b3-ac55-d645ae25fdfe, lane CP7-10, lượt RG-09 thật 01/11/2026: qc hỏng ở cổng cứng `VISUAL_HOOK_PRESENT` (`visual_hook_similarity_below_threshold`).
- Khung trích từ mp4 output ở 0,0 s, 1,5 s và 2,9 s đều là ảnh bài phủ kín; clip visual hook không hiện.
- Gốc: planner AI đặt thumbnail trùng gần cả hook; D chỉ kiểm thumbnail nằm trong hook rồi giữ nguyên khoảng của AI. QC so khung output tại hook[0] với khung đầu clip hook (SSIM 90x160, ngưỡng 0,85).

## 3. Thay đổi

- `src/creative/domain/production_plan.py`: thêm `HOOK_LEAD_IN_MS = 500` và `_thumbnail_after_lead_in`, gọi trong `_parse_hook_placement` sau hai kiểm giữ nguyên (`hook_outside_timeline`, `thumbnail_outside_hook`).
- `tests/unit/creative/test_d10_production_plan.py`: đổi ca ((0, 5000), (0, 5000)) thành ((0, 5000), (500, 1500)); thêm `test_thumbnail_starting_inside_the_lead_in_is_moved_after_it` (10 ca) và `test_lead_in_never_exceeds_the_constant_nor_half_the_hook` (18 ca).
- `tests/integration/prod_wiring/test_d10_fix1_hook_lead.py`: mới, plan thật của D -> render thật -> `RealOutputInspector` và hai cổng thật.
- Không đổi render, QC, ngưỡng, prompt, `hook_time_range`, `variant.py`; `hook_placement` giữ đúng 5 khoá.

## 4. RED (HEAD trước bản sửa)

- Bước 5: `python -m pytest tests/unit/creative/test_d10_production_plan.py -q -p no:cacheprovider` -> exit 1; dòng tóm tắt: `27 failed, 95 passed in 0.60s`. Ví dụ hỏng: `test_lead_in_never_exceeds_the_constant_nor_half_the_hook[1000-0]` (AttributeError `HOOK_LEAD_IN_MS`), `test_thumbnail_starting_inside_the_lead_in_is_moved_after_it` (thumbnail vẫn bắt đầu 0).
- Bước 6: `python -m pytest tests/integration/prod_wiring/test_d10_fix1_hook_lead.py -q -p no:cacheprovider` -> exit 1; dòng tóm tắt: `3 failed, 2 passed in 5.36s`. Ba ca AI hỏng ở assert `thumbnail_time_range` (`{'start_ms': 0} != {'start_ms': 500}`); ca (0,3000)/(500,1500) và ca đối chứng đạt.
- Tổng số ca mới hỏng trước: 30 (27 unit + 3 tích hợp).

## 5. GREEN

- Bước 10: D, D11, D14, D16 -> exit 0; `254 passed in 0.69s`.
- Bước 11: test tích hợp mới và PW-F1 -> exit 0; `76 passed in 35.52s` (5 ca test_d10_fix1_hook_lead đạt).
- Bước 12: `python -m pytest tests/unit -q -p no:cacheprovider` -> exit 0; `7638 passed, 2561 subtests passed in 26.26s` (nguyên mẫu Control ghi 7767; số thực đo ở worktree này là 7638, không có ca hỏng).

Đo thật từng ca của `test_d10_fix1_hook_lead.py` (script đọc tạm ngoài repo, gọi đúng `stage`/`render`/`judge`):

| Hook (AI) | Thumbnail AI | Thumbnail của plan | SSIM VISUAL_HOOK | VISUAL_HOOK | THUMBNAIL |
| --- | --- | --- | --- | --- | --- |
| (0, 3000) | (0, 3000) | (500, 3000) | 0,994852 | PASSED | PASSED (khung 1750 ms) |
| (0, 3000) | (0, 600) | (500, 1100) | 0,992346 | PASSED | PASSED (khung 800 ms) |
| (0, 1000) | (0, 1000) | (500, 1000) | 0,997562 | PASSED | PASSED (khung 750 ms) |
| (0, 3000) | (500, 1500) | (500, 1500) | 0,998229 | PASSED | PASSED (khung 1000 ms) |
| Đối chứng (0, 3000), gói tay không qua D | (0, 3000) | (0, 3000) | 0,523059 | FAILED `visual_hook_similarity_below_threshold` | PASSED (khung 1500 ms) |

Ghi chú: bằng chứng THUMBNAIL là `ThumbnailEvidence` (thời điểm khung và ref), inspector không xuất giá trị SSIM riêng cho thumbnail; ngưỡng `thumbnail_min_ssim` lấy từ `profile.json` = 0,85.

## 6. Bảng lệnh kiểm

| Lệnh | Exit | Kết quả |
| --- | --- | --- |
| `git diff --check` | 0 | không output |
| pytest D + D11 + D14 + D16 | 0 | 254 passed |
| pytest test_d10_fix1_hook_lead + test_pw_f1_inspector_visual | 0 | 76 passed |
| `python -m pytest tests/unit -q -p no:cacheprovider` | 0 | 7638 passed, 2561 subtests passed |
| Probe nguồn production_plan.py (bước 13) | 0 | đạt |
| Probe test tích hợp (bước 14) | 0 | đạt |
| Probe ngưỡng 0,85 và inspector (bước 15) | 0 | đạt |
| Probe bố cục CP2A-LAYOUT (bước 16) | 0 | đạt |
| Probe báo cáo (bước 18) | 0 | đạt |

## 7. coveredIds

- Test tích hợp: CT-RND-003, CT-QC-001.
- Test D: CT-AI-007, CT-RND-003.

## 8. Quyết định mặc định

- Lead-in 500 ms là quyết định kỹ thuật của Control vì tài liệu không nêu số; hook ngắn thì tối đa nửa hook. Chưa qua user; chuyển vào hồ sơ production nếu user muốn chỉnh.
- `OI-CP7-10-F12` đã đóng ở phía D (kế hoạch được chuẩn hoá, cổng QC đạt trên render thật).

## 9. Giới hạn

- Việc nêu ràng buộc lead-in trong prompt planner (`prompts.py:106`) còn mở: đổi prompt cần `PREVIOUS_DEFAULT_PROMPT_HASHES` và `test_pw_d1_roles_prompts`.
- Plan đã lưu trước bản sửa giữ khoảng cũ; chỉ job mới được chuẩn hoá.

## 10. Danh sách chờ user (pendingUserCheckpoint)

- Không có mục nào được ghi là đã duyệt; mức lead-in 500 ms chờ user xác nhận.
