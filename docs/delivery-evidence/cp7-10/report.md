# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

- Ngày kiểm: bắt đầu 2026-11-02T00:27:28Z, kết thúc 2026-11-02T00:34:09Z (giờ Việt Nam: 02/11/2026 07:27:28 đến 07:34:09).
- `HEAD`: `e9f96492fb8921e7a73d47f97553976b9ff6eca8` (mã đã rebase lên 4fcd5d584d58891281b870e25028b334637c3602, đã gồm ADAPT-E-FIX8). Lượt chạy thật dùng đúng cây làm việc sạch tại HEAD này.
- Interpreter: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\8715e538\venv\Scripts\python.exe` (interpreter khoá của lane).

## Kết luận trung thực

Lượt này ĐẠT cả 10 mục RG-09 trên ngăn xếp thật (lô 1 video, một lần chạy duy nhất, không thử lại): cả 11 stage SUCCEEDED ở attempt 1 (gồm align với ADAPT-E-FIX8), QC hard gate 11/11, cloud verified md5 và sha256 khớp, resume sẵn sàng sau 17,3 giây, không chạy lại stage đã xong. Pytest kết thúc `60 passed in 399.83s (0:06:39)`, exit code 0. Lượt này không sửa mã, test hay driver; không thử lại, không tạo lô khác, không vá production, không hạ ngưỡng.

## Lệnh đã chạy

1. `git rebase 4fcd5d584d58891281b870e25028b334637c3602`: hoàn tất không xung đột (32 commit), HEAD `e9f96492fb8921e7a73d47f97553976b9ff6eca8`, worktree sạch, cây có ADAPT-E-FIX8 (`src/voice/adapters/real_whisper_aligner.py`).
2. `git diff --check` (trước khi chạm ngăn xếp thật): exit 0, không output.
3. `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider` (đúng một lần): bắt đầu 2026-11-02T00:27:28Z, kết thúc 2026-11-02T00:34:09Z, exit code 0, dòng tổng kết `60 passed in 399.83s (0:06:39)`.
4. `git diff --check` sau khi ghi report: exit 0, không output.
5. Probe 10 mục RG-09 (`python -c ...`): kết quả ghi trong báo cáo worker_done.

Lượt này không sửa mã, test hay driver; chỉ report.md thay đổi nội dung.

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
- final_batch_status: `COMPLETED_TARGET`, elapsed_s=377.
- no_fake_adapters: `objects_scanned=283 violations=0 source=launcher.load_app production_py_sha256=1853e3ab8dc1f3290f283bde0f73a7ddd4eed5a95df67730295f3c24740b0f02 read_only=True`.
- qc_hard_gates: `hard_total=11 hard_passed=11 not_applicable=0 blocking_gates=[none] duration=[mp4_ms=66725 voice_est_ms=65294 delta_ms=1431]`.
- cloud verified: `md5_match=True sha256_match=True ledger_count=1 ordering=ledger_refs_timestamps ledger_refs_match=True drive_ref=1lOjRi***` (che, chỉ còn 6 ký tự đầu).
- cleanup_after_verify: `cleaned_locations=0 cleanup_before_verified=False`; lý do: production chưa có đường dọn local, ràng buộc chỉ cấm dọn trước VERIFIED.
- plan_unchanged: `digest_equal=True script_sha256=6ac0c33e media_count=5 render_matches_plan=True`.
- resume: `ready_seconds=17.3 limit=300 stop_attempts=1 stopped_in_render=True`.
- no_rerun_completed: `completed_before_stop=7 reruns=0 attempts_unchanged=True`.
- trace_complete: `snapshot_id_present=True model_refs=3 prompt_refs=7 config_revision=5 profile_sha256=aa9b6f8f`.
- secret_scan: `match_count=0 khong_doc_Credentials=True capability_khong_ghi=True`.
- budget: `attempts=1 ai_calls=6 tran_ai_calls=25 spent_usd=0 ceiling_usd=3 drive_bytes=5075681 cap_bytes=209715200 elapsed_s=377 limit_s=7200 remaining_s=6801`.
- seed: `launcher_line=\u0110\xe3 n\u1ea1p b\u1ed9 media seed (idempotent). seed_counts={"hooks": 10, "media_assets": 455, "sources": 7} render_config=[preset/bold-yellow=PUBLISHED preset/output-profile=PUBLISHED policy/quality=PUBLISHED]` (dạng thoát ASCII do `_ascii_line`).
- start: `pre_stop_attempts=1`.
- pre_check: `other_workflows_running=0` (Temporal 127.0.0.1:7233, namespace default, chỉ đọc).
- ai_calls_source: đếm `cp_ai_invocation_records`: `ai_calls=6 ledger_usd=0`.
- batch_after_run: `db_status=COMPLETED_TARGET temporal_running=0 ids=[]`.
- qc_evidence: `blocking_gates=[none] duration=[mp4_ms=66725 voice_est_ms=65294 delta_ms=1431]`.
- media_audio_evidence: `media_count=5 media_ids=[ma-60b,seed-b,seed-b,seed-b,seed-b] image_safety=[not_measured] bed_kind=not_measured music_cues=not_measured mp4_has_music=not_measured`.
- Số từ align đã chia (so với trần 5%): stage align SUCCEEDED nhưng pytest không in số từ đã chia nên không có số liệu.

## Open item

- Lô của lượt này kết thúc `COMPLETED_TARGET`, `temporal_running=0`, không còn workflow RUNNING cần terminate.
- OI-CP7-10-F17 (align `word_coverage_incomplete` với ADAPT-E-FIX8): lượt này align SUCCEEDED/attempt1 trên HEAD có ADAPT-E-FIX8; đề nghị Control xác nhận.
- OI-PW-E2E-01: trạng thái đóng lô là mục mở; RG-09 không chấm theo nó (lượt này lô đạt `COMPLETED_TARGET`).
- OI-CP7-10-F11, OI-CP7-10-F12: giữ mở; `image_safety`, `bed_kind`, `music_cues`, `mp4_has_music` vẫn `not_measured`.
- OI-CP7-10-F13: số từ align đã chia chưa có số liệu vì pytest không in.
