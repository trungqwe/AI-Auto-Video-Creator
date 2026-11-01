# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

- Ngày kiểm: bắt đầu 2026-11-01T23:05:37Z, kết thúc 2026-11-01T23:11:21Z (giờ Việt Nam: 02/11/2026 06:05:37 đến 06:11:21).
- `HEAD`: `6c8da98510ab5ae185c387c63331429376747bf5` (mã đã rebase lên 4943c617f1ae0772be2cc4bbb9786790d35e8167, đã gồm ADAPT-E-FIX6).
- Interpreter: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\8715e538\venv\Scripts\python.exe` (interpreter khoá của lane).

## Kết luận trung thực

Lượt này ĐẠT cả 10 mục RG-09 trên ngăn xếp thật (lô 1 video, một lần chạy duy nhất, không thử lại): cả 11 stage SUCCEEDED ở attempt 1, QC hard gate 11/11, cloud verified md5 và sha256 khớp, resume sẵn sàng sau 9,9 giây, không chạy lại stage đã xong. Pytest kết thúc `1 failed, 58 passed in 343.36s (0:05:43)`, exit code 1: 10 test `test_rg09_*` đo RG-09 đều passed, test thất bại duy nhất là `test_rg09_budget_envelope`, không thuộc 10 mục RG-09. Test này đã in dòng `- budget:` (ai_calls=6, drive_bytes=5099423, elapsed_s=340 đều trong trần) rồi lỗi `UnicodeEncodeError` (codec cp1252 của console không in được chữ `Đ` trong dòng `- seed:`) ở `tests/real/conftest.py:32`; đây là lỗi mã hoá console của lượt chạy, không phải vi phạm ngưỡng. Không sửa test, không chạy lại, không hạ ngưỡng; Control quyết định có chấp nhận pytest exit 1 do lỗi in ấn này hay cấp lượt khác với `PYTHONIOENCODING=utf-8`.

## Lệnh đã chạy

1. `git rebase 4943c617f1ae0772be2cc4bbb9786790d35e8167`: hoàn tất không xung đột (29 commit), HEAD `6c8da98510ab5ae185c387c63331429376747bf5`, worktree sạch.
2. `git diff --check` (trước khi chạm ngăn xếp thật): exit 0, không output.
3. `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider` (đúng một lần, HEAD `6c8da98`, chạy thêm `-rA` để lưu danh sách kết quả): bắt đầu 2026-11-01T23:05:37Z, kết thúc 2026-11-01T23:11:21Z, exit code 1, dòng tổng kết `1 failed, 58 passed in 343.36s (0:05:43)`.
4. `git diff --check` sau khi ghi report: exit 0, không output.
5. Probe 10 mục RG-09 (`python -c ...`): kết quả ghi trong báo cáo worker_done.

## Kết quả

RG-09.stages_succeeded: PASS
RG-09.no_fake_adapters: PASS
RG-09.qc_hard_gates: PASS
RG-09.cloud_verified_before_count: PASS
RG-09.cleanup_after_verify: PASS
RG-09.plan_unchanged: PASS
RG-09.resume_300s: PASS
RG-09.no_rerun_completed: PASS
RG-09.trace_complete: PASS
RG-09.secret_scan: PASS

## Chi tiết đo

Chép từ các dòng `- ` mà pytest in ra trong lượt này (batch_id `3563cfa7-8f29-407c-9945-9ad4a5a8d788`, job_id `3563cfa7-8f29-407c-9945-9ad4a5a8d788:job:1`).

- blocking_gates: `[none]`; không có stage hỏng nên không có failed_detail.
- Bảng stage (status/attempt) của 11 stage: analyze(snapshot), script(script_ai), plan, media_select, tts, align, process, render, qc, sync(upload_drive_and_verify), complete(completion) đều `SUCCEEDED/attempt1`.
- final_batch_status: `COMPLETED_TARGET`, elapsed_s=340.
- no_fake_adapters: `objects_scanned=283 violations=0 source=launcher.load_app production_py_sha256=1853e3ab8dc1f3290f283bde0f73a7ddd4eed5a95df67730295f3c24740b0f02 read_only=True`.
- qc_hard_gates: `hard_total=11 hard_passed=11 not_applicable=0 blocking_gates=[none] duration=[mp4_ms=69883 voice_est_ms=64853 delta_ms=5030]`.
- cloud location VERIFIED và drive_md5_check: `md5_match=True sha256_match=True ledger_count=1 ledger_refs_match=True drive_ref=1_XFDU***` (che, chỉ còn 6 ký tự đầu của provider_object_ref).
- ordering: `ledger_refs_timestamps`.
- cleanup_after_verify: `cleaned_locations=0 cleanup_before_verified=False`; lý do: production chưa có đường dọn local, ràng buộc chỉ cấm dọn trước VERIFIED.
- plan_unchanged: `digest_equal=True script_sha256=046e873c media_count=5 render_matches_plan=True`.
- resume: `ready_seconds=9.9 limit=300 stop_attempts=1 stopped_in_render=True`.
- no_rerun_completed: `completed_before_stop=7 reruns=0 attempts_unchanged=True`.
- trace_complete: `snapshot_id_present=True model_refs=3 prompt_refs=7 config_revision=5 profile_sha256=aa9b6f8f`.
- secret_scan: `match_count=0 khong_doc_Credentials=True capability_khong_ghi=True`.
- budget: `attempts=1 ai_calls=6 cap=25 spent_usd=0 ceiling_usd=3 drive_bytes=5099423 cap_bytes=209715200 elapsed_s=340 limit_s=7200 remaining_s=6857`.
- seed_counts: `{"hooks": 10, "media_assets": 455, "sources": 7}`; render_config: `preset/bold-yellow=PUBLISHED preset/output-profile=PUBLISHED policy/quality=PUBLISHED`.
- media_audio_evidence (từ repr của `RunResult` trong lỗi pytest): `image_safety=[not_measured] bed_kind=not_measured music_cues=not_measured mp4_has_music=not_measured`.
- Số từ align đã chia (so với trần 5%): stage align SUCCEEDED nhưng pytest không in dòng nào về số từ đã chia, nên không có số liệu.
- script_length, hook_placement, pre_check, batch_after_run (db_status, temporal_running): test không in trong lượt thành công nên không có số liệu; `final_batch_status=COMPLETED_TARGET` cho thấy lô đã kết thúc, nhưng `temporal_running` chưa được đo.

## Open item

- OI-CP7-10-BUDGET-PRINT: `test_rg09_budget_envelope` lỗi `UnicodeEncodeError` (cp1252) khi in dòng `- seed:` có chữ `Đ` qua `tests/real/conftest.py:32`; pytest exit 1 dù 10 mục RG-09 PASS. Cần Control quyết định: chạy lại với `PYTHONIOENCODING=utf-8` hoặc chủ gói test sửa dòng in (lane này không sửa test theo lệnh làm việc).
- Lô `3563cfa7-8f29-407c-9945-9ad4a5a8d788` (job `3563cfa7-8f29-407c-9945-9ad4a5a8d788:job:1`) kết thúc `COMPLETED_TARGET`; `temporal_running` chưa đo. Control kiểm và terminate nếu còn workflow RUNNING (workflow id dự kiến `3563cfa7-8f29-407c-9945-9ad4a5a8d788` và `3563cfa7-8f29-407c-9945-9ad4a5a8d788:video:1`).
- OI-CP7-10-F15 (align `word_coverage_incomplete`): lượt này align SUCCEEDED trên HEAD có ADAPT-E-FIX6; đề nghị Control xác nhận đóng.
- OI-CP7-10-QC-THUMB: lượt này QC 11/11 PASS (`blocking_gates=[none]`); `hook_placement` không được in nên chưa có số đo vị trí; đề nghị Control xác nhận đóng.
- OI-PW-E2E-01: trạng thái đóng lô là mục mở; RG-09 không chấm theo nó (lượt này lô đạt `COMPLETED_TARGET`).
- OI-CP7-10-F11, OI-CP7-10-F12: giữ mở; `image_safety`, `bed_kind`, `music_cues`, `mp4_has_music` vẫn `not_measured`.
- OI-CP7-10-F13: số từ align đã chia chưa có số liệu vì pytest không in.
