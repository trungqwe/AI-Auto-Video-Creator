# ADAPT-E-MEDIA-FIX3: Đầu ra ffmpeg của E chịu được nhiều job, nhiều luồng và chạy lại

Mã gói: `ADAPT-E-MEDIA-FIX3` (milestone CP7). Ngày thực hiện: 01/11/2026.

## 1. Phạm vi

Chín owned paths đã sửa hoặc tạo; không sửa tệp nào ngoài danh sách này:

1. `src/voice/adapters/real_ffmpeg_media_tool.py`
2. `src/voice/adapters/activity_inputs.py`
3. `src/voice/adapters/audio_bed_source.py`
4. `src/voice/application/media_pipeline.py`
5. `tests/integration/adapt/e_media/test_adapt_e_media_tools.py`
6. `tests/integration/prod_wiring/test_pw_e3_media_inputs.py`
7. `tests/integration/prod_wiring/test_pw_e4_audio_bed.py`
8. `tests/integration/voice/test_e17_media_processing_pipeline.py`
9. `docs/delivery-evidence/adapt-e-media-fix3/report.md`

## 2. Nguyên nhân gốc của lỗi RG-09 (CP7-10, 01/11/2026)

Job FAILED_FINAL ở stage process, `NormalizeMedia` trả `output_exists`. Gốc: tên đầu ra theo nội dung dùng chung giữa job, item và lần thử, trong khi cách ghi không chịu được tệp đã có. Năm điểm:

- (a) `_normalize` không truyền `output_ref`, nên `plan_rendition` đặt `rendition:<plan_fp>`; job và item cùng ảnh, cùng spec dùng chung một tệp rendition.
- (b) `_new_output` từ chối tệp đã có; `_execute` ghi thẳng vào tên cuối, worker chết giữa chừng để lại tệp dở và lần thử lại hỏng mãi.
- (c) Bản làm mờ `processed:<digest>` đi cùng đường nên job thứ hai làm mờ cùng ảnh bị lỗi.
- (d) `_atomic_write` của audio bed dùng tạm tên cố định `<tên>.part`; hai luồng tranh nhau, và trên Windows `replace` lên tệp đang đọc ném `PermissionError` (`bed_none_store_failed`).
- (e) `_append_receipt` đọc latest rồi append `receipt_by_request` theo fingerprint dùng chung giữa các job; hai job commit cùng lúc gây `RevisionConflictError`, `_commit` ghi `OUTCOME_UNKNOWN` giả và `_replay` chặn ảnh ở mọi job sau.

## 3. Thiết kế

- Adapter ffmpeg idempotent theo nội dung: ffmpeg (giữ `-n`) ghi vào tệp tạm `<stem>.<uuid hex 12>.part.<ext>` cùng thư mục (giữ đuôi thật, không khớp `<stem>.<ext>` mà `locate_media_file` tìm). Exit 0 và tệp không rỗng thì công bố bằng `os.link(tạm, đích)` rồi xoá tạm.
- Khi `FileExistsError`: so sha256 tệp tạm với đích; bằng nhau thì SUCCEEDED với sha của đích; khác thì FAILED `output_conflict`, đích giữ nguyên. `OSError` khác: trên `nt` dùng `os.rename` (không ghi đè; `FileExistsError` xử lý như trên), nơi khác trả FAILED `output_publish_failed`. Hết giờ, không khởi được, exit khác 0 hoặc tệp rỗng thì chỉ xoá tệp tạm. Mã lỗi `output_exists` đã bỏ hẳn.
- `run()` và `transform()` dùng chung `_execute`. Payload digest của `processed` thêm `'processor': 'ffmpeg-<archive>'`.
- `_normalize` trả thêm `output_ref = 'rendition:' + sha256(operation_key + '|' + plan_fp)`, với `plan_fp = compute_plan_fingerprint(nguồn, compute_spec_fingerprint(spec))`: cô lập job và item, ổn định theo cùng key.
- `_atomic_write` (audio bed): đích đã có và trùng sha256 thì không ghi; ngược lại ghi `<tên>.<uuid12>.part` (không kết thúc bằng `.json`), `os.replace`, `finally` xoá tạm; `replace` lỗi `OSError` mà đích trùng byte thì coi là thành công.
- `_append_receipt`: append `receipt_by_request` gặp `RevisionConflictError` thì đọc lại latest và thử lại, tối đa 5 lần (`RECEIPT_APPEND_ATTEMPTS`) rồi ném như cũ. Receipt theo `operation_key` không thử lại.
- Không đổi: mặc định `plan_rendition`, fingerprint của `MediaPipeline`, hợp đồng CT-PROC, bất biến không ghi đè (không bao giờ ghi, dời hay xoá tệp đích). Cleanup chưa nối (`cleanup_executor.py:33`).

## 4. Nhãn R33

Nhãn R33 là nhãn rủi ro của task theo lệnh kiểm của gói này.

`GIẢ ĐỊNH`: tài liệu hiện hành không định nghĩa R33, nên báo cáo chỉ dùng R33 làm nhãn cho nhóm lỗi đầu ra dùng chung (a)–(e) ở mục 2, không suy diễn thêm.

## 5. Lệnh đã chạy

Interpreter khoá của lane (`.local-tools/runtime/8715e538/venv/Scripts/python.exe`), `PYTEST_DEBUG_TEMPROOT` riêng của lượt. Dòng tổng kết là nguyên văn của pytest.

| Bước | Lệnh | Exit code | Kết quả thực tế |
| --- | --- | --- | --- |
| 13 (RED, mã chưa sửa) | pytest `test_adapt_e_media_tools.py`, `test_adapt_e_media_safety_scores.py`, `test_e01_package_layout.py` | 1 | `6 failed, 116 passed, 89 subtests passed in 1.45s` |
| 14 (RED, mã chưa sửa) | pytest E-17, E-18, E-07, E-15 | 1 | `1 failed, 242 passed in 0.76s` |
| 15 (RED, mã chưa sửa) | pytest PW-E3, PW-E4, PW-E1 | 1 | `5 failed, 37 passed in 15.02s` |
| 27 | pytest `test_adapt_e_media_tools.py`, `test_adapt_e_media_safety_scores.py`, `test_e01_package_layout.py` | 0 | `122 passed, 89 subtests passed in 1.21s` |
| 28 | pytest E-17, E-18, E-07, E-15 | 0 | `243 passed in 0.42s` |
| 29 | pytest PW-E3, PW-E4, PW-E1 (Postgres, FFmpeg ghim thật `C:/ffmpeg/bin`) | 0 | `42 passed in 15.21s` |
| 30 | pytest PW-W2, PW-E2E | 0 | `23 passed, 1 warning in 133.94s (0:02:13)` |
| 31 | probe `real_ffmpeg_media_tool.py` | 0 | không assert nào đỏ |
| 32 | probe `activity_inputs.py` | 0 | không assert nào đỏ |
| 33 | probe `audio_bed_source.py` và `media_pipeline.py` | 0 | không assert nào đỏ |
| 35 | probe `report.md` (có `ADAPT-E-MEDIA-FIX3` và `R33`) | 0 | không assert nào đỏ |
| 36 | `git diff --check` | 0 | không có lỗi khoảng trắng |

## 6. RED / GREEN

Test đỏ với mã cũ (đều vì lý do hành vi):

- `test_adapt_e_media_tools.py` (6): `test_existing_output_never_overwritten` (mã cũ ra `output_exists`, không phải `output_conflict`), `test_existing_output_with_same_bytes_succeeds`, `test_same_plan_twice_succeeds_with_one_file`, `test_ffmpeg_writes_to_unique_temp_with_real_extension`, `test_transform_twice_with_the_same_request_gives_the_same_sha`, `test_transform_processed_ref_depends_on_the_archive`.
- `test_e17_media_processing_pipeline.py` (1): `test_normalize_receipt_by_request_conflict_retries_and_succeeds` (mã cũ ra `OUTCOME_UNKNOWN` với `receipt_commit_failed`).
- `test_pw_e3_media_inputs.py` (4): `test_pw_e3_normalize_output_ref_is_per_operation`, `test_pw_e3_second_job_on_the_same_images_normalizes_and_blurs_again`, `test_pw_e3_two_items_with_the_same_image_both_normalize`, `test_pw_e3_normalize_with_the_destination_already_written_by_the_tool_succeeds`.
- `test_pw_e4_audio_bed.py` (1): `test_pw_e4_bed_none_already_present_and_open_is_reused` (mã cũ ra `bed_none_store_failed`).

Nói thật về các test xanh với mã cũ:

- `test_nonzero_exit_after_temp_write_leaves_no_destination_and_retry_succeeds` và `test_timeout_after_temp_write_leaves_no_destination_and_retry_succeeds` là test bảo vệ hồi quy, xanh với mã cũ.
- `test_two_threads_with_the_same_plan_both_succeed_with_one_file` cũng xanh với mã cũ ở lần chạy RED (không đỏ như brief dự kiến; chưa điều tra thêm nguyên nhân). Test này vẫn xanh với mã mới và bảo vệ hành vi hai luồng công bố cùng đích, nhưng không phải bằng chứng RED.

## 7. Việc còn lại (backlog) và mục mở

- Chưa đo lại RG-09 trên job thật; không dùng mock để tuyên bố cổng ngoài PASS.
- Mục mở: renderer còn từ chối tệp đầu ra đã có khi chết sau `os.replace` mà trước receipt (`real_ffmpeg_renderer.py:176-177`); cần gói riêng.
- Mục mở: khi nối cleanup (`cleanup_executor.py:33`) phải đếm tham chiếu các tệp dùng chung `processed`, `music`, `bed-none`.
- Dọn tệp `.part` mồ côi sau crash cứng và tệp `rendition_<fp>` cũ trong `staging/media` chưa được nối.
- Test nhánh `os.rename` trên `nt` không có (cần monkeypatch mã production, bị cấm).
- Ngoài phạm vi: lỗi các lần thử của render dùng chung một khoá; `OUTCOME_UNKNOWN` thật (`ffmpeg_timeout`) của bản làm mờ vẫn chặn ảnh đó ở mọi job sau; `real_kokoro_tts.py` và `real_media_fetch.py` còn dùng `.part` tên cố định; sidecar `music-<sha>.json` ghi đồng thời với `collected_at` khác nhau có thể ra `music_store_failed`.
- Rủi ro khi gộp: job đang ở giữa stage process mà `NormalizeMedia` đã commit nhưng chưa báo Temporal sẽ gặp `IdempotencyConflictError` ở lần thử lại vì ref mới; `os.link` cần NTFS và cùng ổ.
