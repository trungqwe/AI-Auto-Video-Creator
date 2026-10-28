# Báo cáo PW-E3-FIX1: TransformSensitiveImage thành công không output khi không có ảnh nhạy cảm

## 1. Nhóm lỗi

Nhóm lỗi R5: `TransformSensitiveImage` luôn nằm trong stage `process` của `VideoProductionWorkflow` và không có fan-out (`workflows/activities.py:142-147`). Tuy nhiên, hàm `_transform` gọi `_first_ref(refs, "sensitive_image")` (`voice/adapters/activity_inputs.py:172-176, 327`) và ném lỗi `INPUT_NOT_READY` (`missing_sensitive_image_ref`) khi request không có ảnh nào cần làm mờ — đây là trường hợp bình thường trong quy trình sản xuất, dẫn đến việc stage chờ mãi không hoàn tất.

Quy tắc sửa đổi:
- Khi request không có ref `sensitive_image`, activity hoàn thành thành công không tạo output (`succeeded`, `output_refs` rỗng), áp dụng cùng quy tắc với `NormalizeMedia` ("without a seed the activity succeeds with no output").
- Khi request có ref `sensitive_image`, toàn bộ hành vi cũ được giữ nguyên (thiếu `regions` hoặc assessment chưa lưu vẫn ném `INPUT_NOT_READY`, xử lý làm mờ với FFmpeg gyan.dev đã ghim vẫn chạy bình thường).
- Luồng production thật chạy từ `controlplane/api/wiring/voice.py` -> `voice.worker.activity_handler.handle_activity` -> `ProductionActivityInputs.resolve` -> `_transform` (không đi qua `handle_voice_activity`), do đó nhánh route được xử lý nhất quán tại `voice/worker/activity_handler.py`.

## 2. Tệp đã sửa

- `src/voice/adapters/activity_inputs.py`: `_transform` kiểm tra nếu không có ref `sensitive_image` thì trả tín hiệu `{NO_OUTPUT_KEY: REASON_NO_SENSITIVE_IMAGE}` thay vì ném lỗi `INPUT_NOT_READY`.
- `src/voice/worker/activity_handler.py`: định nghĩa hằng số `NO_OUTPUT_KEY = 'no_output_reason'`, thêm hàm `_run_transform_sensitive_image` trả `_Outcome(SUCCEEDED, [], {'output_count': 0, 'replayed': False})` khi nhận được `NO_OUTPUT_KEY`, cập nhật `_ROUTES[OP_TRANSFORM_SENSITIVE_IMAGE]` và export `NO_OUTPUT_KEY` trong `__all__`.
- `tests/integration/prod_wiring/test_pw_e3_media_inputs.py`: import `handle_activity`, thêm 2 test mới (`test_pw_e3_transform_without_a_sensitive_image_succeeds_with_no_output` và `test_pw_e3_transform_with_a_sensitive_image_keeps_the_old_path`) cùng 2 helper `transform_deps` và `transform_entries`.
- `docs/delivery-evidence/pw-e3-fix1/report.md`: tài liệu báo cáo nghiệm thu task PW-E3-FIX1.

## 3. Lệnh kiểm đã chạy

| Bước | Lệnh | Exit code | Dòng tổng kết nguyên văn |
| --- | --- | --- | --- |
| Bước 3 (RED) | `python -m pytest tests/integration/prod_wiring/test_pw_e3_media_inputs.py -q -p no:cacheprovider` | 1 | `1 failed, 8 passed in 3.79s` (FAILED `test_pw_e3_transform_without_a_sensitive_image_succeeds_with_no_output`) |
| Bước 6 (GREEN) | `python -m pytest tests/integration/prod_wiring/test_pw_e3_media_inputs.py -q -p no:cacheprovider` | 0 | `9 passed in 3.84s` |
| Bước 8 (Diff check) | `git diff --check` | 0 | Thoát mã 0, không có cảnh báo khoảng trắng thừa hoặc lỗi định dạng dòng |
| Bước 9 (Probe report) | `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-e3-fix1/report.md').read_text(encoding='utf-8'); assert 'PW-E3-FIX1' in t and 'R5' in t, 'report'"` | 0 | Thoát mã 0, xác nhận báo cáo chứa PW-E3-FIX1 và R5 |

## 4. Mục ngoài phạm vi

Các nhóm lỗi R1–R4, R6–R8 không đổi trong gói này; `controlplane/api/wiring/voice.py` (`transform_handler`) không đổi.
