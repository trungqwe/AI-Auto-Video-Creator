# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

- Ngày kiểm: bắt đầu 2026-11-01T23:45:52Z, kết thúc 2026-11-01T23:52:25Z (giờ Việt Nam: 02/11/2026 06:45:52 đến 06:52:25).
- `HEAD`: `9db56bd5bedd0630637aba27f5369586b9e77e1a` (mã đã rebase lên 0e974e58947d3ab912d02713b3e79f20f2b49573, đã gồm ADAPT-E-FIX7). Lượt chạy thật dùng cây làm việc gồm HEAD này cộng sửa `_ascii_line` ở `tests/real/test_cp7_video_alpha_e2e.py` (commit ngay sau đó).
- Interpreter: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\8715e538\venv\Scripts\python.exe` (interpreter khoá của lane).

## Kết luận trung thực

Lượt này ĐẠT cả 10 mục RG-09 trên ngăn xếp thật (lô 1 video, một lần chạy duy nhất, không thử lại): cả 11 stage SUCCEEDED ở attempt 1, QC hard gate 11/11, cloud verified md5 và sha256 khớp, resume sẵn sàng sau 10,3 giây, không chạy lại stage đã xong. Pytest kết thúc `60 passed in 388.70s (0:06:28)`, exit code 0; `test_rg09_budget_envelope` không còn `UnicodeEncodeError` vì mọi dòng in đi qua `_ascii_line`. Không thử lại, không tạo lô khác, không vá production, không hạ ngưỡng.

## Lệnh đã chạy

1. `git rebase 0e974e58947d3ab912d02713b3e79f20f2b49573`: hoàn tất không xung đột (31 commit), HEAD `9db56bd5bedd0630637aba27f5369586b9e77e1a`, worktree sạch.
2. Sửa `tests/real/test_cp7_video_alpha_e2e.py`: thêm `_ascii_line`, test `test_unit_ascii_line_is_console_safe`, bọc 8 lời gọi `emit` của `test_rg09_budget_envelope` bằng `_ascii_line(...)`; giữ nguyên assert `budget_violations`.
3. `git diff --check` (trước khi chạm ngăn xếp thật): exit 0, không output.
4. `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider` (đúng một lần): bắt đầu 2026-11-01T23:45:52Z, kết thúc 2026-11-01T23:52:25Z, exit code 0, dòng tổng kết `60 passed in 388.70s (0:06:28)`.
5. `git diff --check` sau khi ghi report: exit 0, không output.
6. Probe 10 mục RG-09 (`python -c ...`): kết quả ghi trong báo cáo worker_done.

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

Chép từ các dòng `- ` mà pytest in ra trong lượt này.

- blocking_gates: `[none]`; không có stage hỏng nên không có failed_detail.
- Bảng stage (status/attempt) của 11 stage: analyze(snapshot), script(script_ai), plan, media_select, tts, align, process, render, qc, sync(upload_drive_and_verify), complete(completion) đều `SUCCEEDED/attempt1`.
- final_batch_status: `COMPLETED_TARGET`, elapsed_s=387.
- no_fake_adapters: `objects_scanned=283 violations=0 source=launcher.load_app production_py_sha256=1853e3ab8dc1f3290f283bde0f73a7ddd4eed5a95df67730295f3c24740b0f02 read_only=True`.
- qc_hard_gates: `hard_total=11 hard_passed=11 not_applicable=0 blocking_gates=[none] duration=[mp4_ms=62933 voice_est_ms=64412 delta_ms=-1479]`.
- cloud verified: `md5_match=True sha256_match=True ledger_count=1 ordering=ledger_refs_timestamps ledger_refs_match=True drive_ref=1R9NBI***` (che, chỉ còn 6 ký tự đầu).
- cleanup_after_verify: `cleaned_locations=0 cleanup_before_verified=False`; lý do: production chưa có đường dọn local, ràng buộc chỉ cấm dọn trước VERIFIED.
- plan_unchanged: `digest_equal=True script_sha256=e6f55872 media_count=5 render_matches_plan=True`.
- resume: `ready_seconds=10.3 limit=300 stop_attempts=1 stopped_in_render=True`.
- no_rerun_completed: `completed_before_stop=7 reruns=0 attempts_unchanged=True`.
- trace_complete: `snapshot_id_present=True model_refs=3 prompt_refs=7 config_revision=5 profile_sha256=aa9b6f8f`.
- secret_scan: `match_count=0 khong_doc_Credentials=True capability_khong_ghi=True`.
- budget: `attempts=1 ai_calls=6 tran_ai_calls=25 spent_usd=0 ceiling_usd=3 drive_bytes=4973755 cap_bytes=209715200 elapsed_s=387 limit_s=7200 remaining_s=6811`.
- seed: `launcher_line=\u0110\xe3 n\u1ea1p b\u1ed9 media seed (idempotent). seed_counts={"hooks": 10, "media_assets": 455, "sources": 7} render_config=[preset/bold-yellow=PUBLISHED preset/output-profile=PUBLISHED policy/quality=PUBLISHED]` (dạng thoát ASCII do `_ascii_line`).
- start: `pre_stop_attempts=1`.
- pre_check: `other_workflows_running=0` (Temporal 127.0.0.1:7233, namespace default, chỉ đọc).
- ai_calls_source: đếm `cp_ai_invocation_records`: `ai_calls=6 ledger_usd=0`.
- batch_after_run: `db_status=COMPLETED_TARGET temporal_running=0 ids=[]`.
- qc_evidence: `blocking_gates=[none] duration=[mp4_ms=62933 voice_est_ms=64412 delta_ms=-1479]`.
- media_audio_evidence: `media_count=5 media_ids=[ma-996,seed-b,seed-b,seed-b,seed-b] image_safety=[not_measured] bed_kind=not_measured music_cues=not_measured mp4_has_music=not_measured`.
- Số từ align đã chia (so với trần 5%): stage align SUCCEEDED nhưng pytest không in số từ đã chia, nên không có số liệu.

## Open item

- OI-CP7-10-BUDGET-PRINT: ĐÃ ĐÓNG. Đã sửa ở `test_rg09_budget_envelope` (mọi dòng in qua `_ascii_line`, thêm test thuần `test_unit_ascii_line_is_console_safe`); pytest exit 0 trong lượt này.
- Lô của lượt này kết thúc `COMPLETED_TARGET`, `temporal_running=0`, không còn workflow RUNNING cần terminate.
- OI-CP7-10-F16 (align với từ như Vice-Chair, CARICOM): lượt này align SUCCEEDED trên HEAD có ADAPT-E-FIX7 với kịch bản của lượt này; đề nghị Control xác nhận.
- OI-PW-E2E-01: trạng thái đóng lô là mục mở; RG-09 không chấm theo nó (lượt này lô đạt `COMPLETED_TARGET`).
- OI-CP7-10-F11, OI-CP7-10-F12: giữ mở; `image_safety`, `bed_kind`, `music_cues`, `mp4_has_music` vẫn `not_measured`.
- OI-CP7-10-F13: số từ align đã chia chưa có số liệu vì pytest không in.
