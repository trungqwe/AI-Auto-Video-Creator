# Báo cáo đóng M7 (revision 4) - TRẠNG THÁI: BLOCKED TẠI BƯỚC 8

## 1. Phạm vi và candidate

- Task: `M7-MILESTONE-CLOSE-R4` (đóng milestone M7, revision 4).
- Base tích hợp: `069d9743c18cab0003b35fcd4f81ee3b3ce622a5`.
- Candidate: `92849310eddf04f32fb2f64a08b4aa7a8e2b1a9e` (HEAD sau khi rebase lên integration head `069d9743c18cab0003b35fcd4f81ee3b3ce622a5`).
- Interpreter khoá của lane: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\1ca840a7\venv\Scripts\python.exe`.
- Ngày thực thi: `2026-10-29`.
- Owned paths: `docs/delivery-evidence/m7-milestone-close/**`. Cấm sửa đổi bất kỳ tệp nào ngoài phạm vi này.

## 2. Lý do rebase (CLOSURE_BASE_STALE)

Lượt chạy trước thực hiện trên HEAD cũ `b8b46c6365c2` chưa chứa các commit tích hợp sau đó (như các commit sửa render PW-F4-FIX1, PW-F4-FIX2). Do đó grant G1 bị Control thu hồi với lý do `CLOSURE_BASE_STALE`.
Kết quả của lượt trước không còn giá trị sử dụng. Nhánh đã được rebase thành công lên `069d9743c18cab0003b35fcd4f81ee3b3ce622a5` tạo candidate mới `92849310eddf04f32fb2f64a08b4aa7a8e2b1a9e`.
Sau khi rebase, lỗi kiểm thử PW-F4 trước đây (`test_inspect_output_disclosure_gate_follows_the_script_segments`) đã hoàn toàn biến mất: kiểm thử `tests/integration/prod_wiring/test_pw_f4_render_worker.py` chạy đạt exit 0 (`16 passed in 42.99s`) tại Bước 6 (Chuỗi 5).

## 3. Revision trước đã đóng mà không tích hợp

Milestone đóng mốc revision 3 (`M7-MILESTONE-CLOSE-R3`) đã được đóng mà không tích hợp.
Lý do mở lại revision 4 (theo kế hoạch mở lại `docs/plans/PROD_WIRING_REOPEN_PLAN_20261025.md`):
R3 chắc chắn phải chạy lại thành R4 vì các gói `RS-1..RS-13`, bốn gói sửa read-screens (`CP-4B-UI-SCREENS-FIX3`, `CP-4-WIRING-FIX3`, `ADAPT-PROD-FIX3`, `CP-4B-UI-SCREENS-FIX4`), gói kế hoạch PW (`IMPL-PLAN-PROD-WIRING`), các gói `PW-*` và cổng `GATE-PW-E2E` không nằm trong danh sách `coveredTasks` đã đóng băng của R3. R3 được retire để không đốt một lượt kiểm 22-25 phút và một lượt kiểm định Auditor rủi ro vô ích.

Bảng kiểm lại các điểm bổ sung của R4 so với R3:
- Bốn gói sửa read-screens: Chuỗi 3 (Bước 4) gồm `test_cp4_wiring_fix3.py` (exit 0), `test_h_screen_registry.py` (exit 0), các probe `production.py` và `screenRegistry.ts` (exit 0).
- Gói kế hoạch PW: Chuỗi 4 (Bước 5) gồm probe `slices.md` và `plan.md` của prod-wiring (exit 0).
- Các gói PW-* và sửa lỗi PW: Chuỗi 5 (Bước 6) gồm scheduler, media_inputs, materialize, render_worker (exit 0).
- `GATE-PW-E2E`: Bản ghi quyết định RELEASE có recordHash `de33d674f014ef13caf258cd7a9c8b6b0dae633def501a3e53e150c14ba9da19` tại `gate-releases.md`.
- `RS-1..RS-13`: Sẽ được kiểm lại tại Chuỗi 22 khi giải quyết xong blocker.

## 4. Gói được bao phủ

- Toàn bộ 99 gói được bao phủ theo yêu cầu nghiệm thu kèm SHA tích hợp 40 hex đã được liệt kê đầy đủ tại [packages.md](packages.md). 100% SHA tích hợp được xác nhận là tổ tiên của HEAD `92849310eddf04f32fb2f64a08b4aa7a8e2b1a9e`.
- Gói mốc `M7-INTEGRATION-PLAN`: Control đã xác minh receipt Auditor PASS và commit nội dung `0a3f707ffa08b3a5737be6fa30769933d2cf475d` là tổ tiên của nhánh tích hợp.
- Toàn bộ 16 cổng `GATE-*` đã có bản ghi quyết định RELEASE được ghi nhận tại [gate-releases.md](gate-releases.md).

## 5. Gói retire, không được bao phủ

Hai gói kế hoạch sửa `IMPL-PLAN-PROD-WIRING-FIX1` và `IMPL-PLAN-PROD-WIRING-V3-FIX1` đã được retire và không nằm trong danh sách bao phủ:
- Đánh giá tác động: Hai gói này là các gói sửa kế hoạch trung gian của PROD-WIRING, đã bị thay thế hoàn toàn bởi `IMPL-PLAN-PROD-WIRING-V3` và `IMPL-PLAN-PROD-WIRING-V4` trong danh sách bao phủ. Do đó việc loại bỏ chúng không làm ảnh hưởng đến các exit gate `M7-R5-EG1` và `M7-R6`.

## 6. Kết quả lệnh kiểm

- Chi tiết tiến trình kiểm tra được ghi nhận tại [command-results.md](command-results.md).
- Tổng số đoạn lệnh đã chạy: 153 đoạn (Chuỗi 1 đến Chuỗi 7 đoạn 11).
- Số đoạn đạt exit code 0: 152 đoạn.
- Số đoạn thất bại exit code 1: 1 đoạn (Chuỗi 7 đoạn 11).
- Số đoạn chưa chạy: 314 đoạn (Chuỗi 8 đến 23) do dừng fail-closed ngay khi gặp lỗi kiểm thử.

## 7. Đối chiếu exit gate

- Chi tiết đối chiếu exit gate Milestone M7 theo roadmap được trình bày tại [exit-gates.md](exit-gates.md).
- Danh sách `pendingUserCheckpoint` chỉ gồm đúng 2 mục: `M7-R5-EG1` và `M7-R6` (chờ tài nguyên thật, GPU, OAuth Drive và vận hành 100 video trong 12 giờ tại gói CP7).
- Các exit gate `M7-R5-EG2..EG5` được ghi nhận dưới dạng GHI CHÚ theo đúng quyết định của user ngày 2026-10-22 («Exit gate của roadmap rộng hơn kế hoạch đã duyệt chỉ được ghi chú trong báo cáo đóng mốc, không phải FAIL và không hỏi user. Việc kế hoạch đã duyệt có mà chưa nối do Control tự lập gói sửa.»).

## 8. Chi tiết lỗi kiểm thử và Blocked Manifest

Tại Bước 8 (Chuỗi 7, đoạn lệnh thứ 11):
- Lệnh: `python -m pytest tests/integration/adapt/f/test_adapt_f_render.py -q -p no:cacheprovider`
- Mã thoát: `1`
- Dòng tóm tắt: `1 failed, 53 passed in 3.66s`
- Tên test thất bại: `tests/integration/adapt/f/test_adapt_f_render.py::test_command_is_an_argument_list_with_production_parameters`
- Lỗi chi tiết:
  ```text
  AssertionError: assert 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30' in '[0:v:0]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30,format=yuv420p[v0]...'
  ```
- Nguyên nhân quan sát được:
  Gói `F-10-FIX1` / `F-10-FIX2` (commit `5b2c4ce` và `d594e12`) đã chuẩn hoá bộ lọc đầu vào trước concat bằng cách bổ sung `setsar=1,format=yuv420p` vào filtergraph theo yêu cầu của R9. Tuy nhiên, tệp test `tests/integration/adapt/f/test_adapt_f_render.py` thuộc gói `ADAPT-F` vẫn assert chuỗi bộ lọc cũ không có `setsar=1`. Tệp này nằm ngoài owned paths của lane (`docs/delivery-evidence/m7-milestone-close/**`). Tuân thủ nguyên tắc Single-Writer và phân quyền đóng của Orca, Worker không tự ý sửa test ngoài thẩm quyền và báo cáo trạng thái BLOCKED.

```blocked-manifest
{
  "step": 8,
  "kind": "DEPENDENCY_GAP",
  "ownerTaskIds": ["ADAPT-F"],
  "paths": ["tests/integration/adapt/f/test_adapt_f_render.py"],
  "ids": ["test_command_is_an_argument_list_with_production_parameters"]
}
```

## 9. Vệ sinh và kiểm tra tuân thủ

- Lệnh `git diff --check` sạch hoàn toàn, không có khoảng trắng thừa hay lỗi định dạng.
- Mọi tệp tài liệu đều sử dụng mã hóa UTF-8 chuẩn không BOM, giữ nguyên vẹn tiếng Việt có đầy đủ dấu và không chứa ký tự thay thế `U+FFFD`.
