# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

- Ngày kiểm: bắt đầu 2026-11-01T21:25:25Z, kết thúc 2026-11-01T21:30:56Z (giờ Việt Nam: 02/11/2026 04:25:25 đến 04:30:56).
- `HEAD`: `db5a400cc5d34962d50a8d9dc53125bc05d42ad8` (nền của lượt; mã chẩn đoán `hook_placement` của lượt này là thay đổi chưa commit lúc chạy, được commit sau lượt chạy).
- Interpreter: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\8715e538\venv\Scripts\python.exe` (interpreter khoá của lane).

## Kết luận trung thực

Lượt này đạt RG-09 trên ngăn xếp thật (lô 1 video, một lần chạy duy nhất, không thử lại). Cả 11 stage SUCCEEDED ở attempt 1, QC hard gate 11/11 (`blocking_gates=[none]`, trong đó `THUMBNAIL_PRESENT` đạt), cloud verified (md5 và sha256 khớp, ledger_count=1) trước khi đếm, plan không đổi, resume sau `launcher stop`/`start` sẵn sàng trong 10,5 giây không chạy lại stage đã xong, secret scan 0 khớp. Pytest kết thúc `59 passed` (gồm ba test thuần mới của `hook_placement`), exit 0. Vì job COMPLETED nên dòng chẩn đoán `hook_placement=[...]` (chỉ in trên nhánh BLOCKED) không xuất hiện trong output lượt này. Lô kết thúc `COMPLETED_TARGET`, `temporal_running=0`, không còn workflow cần terminate.

## Lệnh đã chạy

1. `git diff --check` (trước khi chạm ngăn xếp thật): exit 0, không output.
2. `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider` (đúng một lần, HEAD `db5a400`, không rebase): bắt đầu 2026-11-01T21:25:25Z, kết thúc 2026-11-01T21:30:56Z, exit code 0, dòng tổng kết `59 passed in 329.12s (0:05:29)`.
3. `git diff --check` sau khi ghi report: exit 0, không output.
4. Probe 10 mục RG-09 (`python -c ...`): kết quả ghi trong báo cáo worker_done.

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

Các dòng `- ` do test in (nguyên văn, drive ref đã che):

- stages_succeeded: analyze(snapshot)=SUCCEEDED/attempt1 script(script_ai)=SUCCEEDED/attempt1 plan(plan)=SUCCEEDED/attempt1 media_select(media_select)=SUCCEEDED/attempt1 tts(tts)=SUCCEEDED/attempt1 align(align)=SUCCEEDED/attempt1 process(process)=SUCCEEDED/attempt1 render(render)=SUCCEEDED/attempt1 qc(qc)=SUCCEEDED/attempt1 sync(upload_drive_and_verify)=SUCCEEDED/attempt1 complete(completion)=SUCCEEDED/attempt1
- stages_succeeded: elapsed_s=328 final_batch_status=COMPLETED_TARGET (so do, OI-PW-E2E-01: production chua co writer CREATED->RUNNING nen khong bat buoc COMPLETED_TARGET)
- no_fake_adapters: objects_scanned=283 violations=0 source=launcher.load_app production_py_sha256=1853e3ab8dc1f3290f283bde0f73a7ddd4eed5a95df67730295f3c24740b0f02 read_only=True
- qc_hard_gates: hard_total=11 hard_passed=11 not_applicable=0 blocking_gates=[none] duration=[mp4_ms=66753 voice_est_ms=67500 delta_ms=-747]
- cloud_verified_before_count: md5_match=True sha256_match=True ledger_count=1 ordering=ledger_refs_timestamps ledger_refs_match=True drive_ref=1FlKci***
- cleanup_after_verify: cleaned_locations=0 cleanup_before_verified=False
- cleanup_after_verify: reason=production_chua_co_duong_don_local; rang_buoc_chi_cam_don_truoc_VERIFIED
- plan_unchanged: digest_equal=True script_sha256=4059cf79 media_count=7 render_matches_plan=True
- resume_300s: ready_seconds=10.5 limit=300 stop_attempts=1 stopped_in_render=True
- no_rerun_completed: completed_before_stop=7 reruns=0 attempts_unchanged=True
- trace_complete: snapshot_id_present=True model_refs=3 prompt_refs=7 config_revision=5 profile_sha256=aa9b6f8f
- secret_scan: match_count=0 khong_doc_Credentials=True capability_khong_ghi=True
- budget: attempts=1 ai_calls=6 cap=25 spent_usd=0 ceiling_usd=3 drive_bytes=5374101 cap_bytes=209715200 elapsed_s=328 limit_s=7200 remaining_s=6871
- seed: launcher_line=Đã nạp bộ media seed (idempotent). seed_counts={"hooks": 10, "media_assets": 455, "sources": 7} render_config=render_config=[preset/bold-yellow=PUBLISHED preset/output-profile=PUBLISHED policy/quality=PUBLISHED]
- start: pre_stop_attempts=1
- pre_check: other_workflows_running=0 (Temporal 127.0.0.1:7233 namespace default, chi doc)
- ai_calls_source: dem cp_ai_invocation_records record_key bat dau <ws>:<batch>:video: ai_calls=6 ledger_usd=0 (route_cost_per_request=0 nen ledger luon 0)
- batch_after_run=[db_status=COMPLETED_TARGET temporal_running=0 ids=[]] (OI-PW-E2E-01: trang thai dong lo la muc mo, RG-09 khong cham theo no)
- qc_evidence: blocking_gates=[none] duration=[mp4_ms=66753 voice_est_ms=67500 delta_ms=-747]
- media_audio_evidence=[media_count=7 media_ids=[ma-69b,seed-b,seed-b,seed-b,seed-b,seed-b,seed-b] image_safety=[not_measured] bed_kind=not_measured music_cues=not_measured mp4_has_music=not_measured]

Tổng hợp theo yêu cầu của lệnh làm việc:

- Bảng stage (status/attempt): cả 11 stage (analyze, script, plan, media_select, tts, align, process, render, qc, sync, complete) đều SUCCEEDED/attempt 1.
- blocking_gates: `[none]`; failed_detail: không có (không gate nào hỏng); hook_placement: không in vì job COMPLETED (dòng này chỉ in trên nhánh BLOCKED).
- Số từ align đã chia: không được output test in; stage align SUCCEEDED ở attempt 1.
- Cloud location VERIFIED và evidence drive: `drive_ref=1FlKci***`, md5_match=True, sha256_match=True (drive_md5_check).
- cleanup_after_verify: `cleaned_locations=0 cleanup_before_verified=False` (production chưa có đường dọn local; ràng buộc chỉ cấm dọn trước VERIFIED).
- Ngân sách: ai_calls=6 (trần 25), ledger_usd=0 (trần 3), drive_bytes=5374101 (trần 209715200), elapsed_s=328 (trần 7200).

## Open item

- Không còn lô RUNNING cần terminate: `batch_after_run` ghi `temporal_running=0`, `db_status=COMPLETED_TARGET`.
- OI-CP7-10-QC-THUMB: lượt này `THUMBNAIL_PRESENT` đạt (11/11 hard gate) nên lỗi `thumbnail_asset_mismatch` của lượt trước không tái hiện; chưa có dữ kiện `hook_placement` để chẩn đoán nguyên nhân gốc, giữ mở theo dõi tính ổn định giữa các lần chạy (lane không vá production).
- OI-PW-E2E-01: trạng thái đóng lô là mục mở; RG-09 không chấm theo nó.
- OI-CP7-10-F11, OI-CP7-10-F12: output pytest không có dòng nêu riêng; giữ mở. `image_safety`, `bed_kind`, `mp4_has_music` vẫn `not_measured`.
- OI-CP7-10-F13: stage align SUCCEEDED ở attempt 1 với kịch bản mới; số từ align đã chia không được output test in nên chưa có số liệu; giữ mở ở phần số liệu.
