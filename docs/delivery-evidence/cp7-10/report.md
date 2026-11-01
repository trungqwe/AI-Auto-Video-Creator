# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

- Ngày kiểm: bắt đầu 2026-11-01T20:12:06Z, kết thúc 2026-11-01T20:18:21Z (giờ Việt Nam: 02/11/2026 03:12:06 đến 03:18:21).
- `HEAD`: `2933496487013333ee2d94b252eb054c998d50fd` (đã có D-10-FIX1 từ 9eaedbf, không rebase lượt này).
- Interpreter khoá: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\8715e538\venv\Scripts\python.exe`.

## Kết luận trung thực

Lượt này PASS toàn bộ 10 mục RG-09 trên ngăn xếp thật (lô 1 video, một lần chạy duy nhất, không thử lại). 11 stage đều SUCCEEDED ở attempt 1, QC hard gate 11/11, cloud verified (md5 và sha256 khớp), resume sau `launcher stop`/`start` sẵn sàng sau 10 giây và không stage nào chạy lại. Sau lượt, lô ở trạng thái `COMPLETED_TARGET` và Temporal không còn workflow RUNNING, nên không có lô cần terminate.

## Lệnh đã chạy

1. `git diff --check` trước khi chạy: exit 0, không output.
2. `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider` (đúng một lần): bắt đầu 2026-11-01T20:12:06Z, kết thúc 2026-11-01T20:18:21Z, exit code 0, dòng tổng kết `56 passed in 373.74s (0:06:13)`.
4. `git diff --check` sau khi ghi report: exit 0, không output (xem mục xác nhận khi chạy).
5. Probe 10 mục RG-09 (`python -c ...`): exit 0 (xem mục xác nhận khi chạy).

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

Các dòng `- ` do test in (nguyên văn):

- stages_succeeded: analyze(snapshot)=SUCCEEDED/attempt1 script(script_ai)=SUCCEEDED/attempt1 plan(plan)=SUCCEEDED/attempt1 media_select(media_select)=SUCCEEDED/attempt1 tts(tts)=SUCCEEDED/attempt1 align(align)=SUCCEEDED/attempt1 process(process)=SUCCEEDED/attempt1 render(render)=SUCCEEDED/attempt1 qc(qc)=SUCCEEDED/attempt1 sync(upload_drive_and_verify)=SUCCEEDED/attempt1 complete(completion)=SUCCEEDED/attempt1
- stages_succeeded: elapsed_s=372 final_batch_status=COMPLETED_TARGET (so do, OI-PW-E2E-01: production chua co writer CREATED->RUNNING nen khong bat buoc COMPLETED_TARGET)
- no_fake_adapters: objects_scanned=283 violations=0 source=launcher.load_app production_py_sha256=1853e3ab8dc1f3290f283bde0f73a7ddd4eed5a95df67730295f3c24740b0f02 read_only=True
- qc_hard_gates: hard_total=11 hard_passed=11 not_applicable=0 blocking_gates=[none] duration=[mp4_ms=65452 voice_est_ms=64412 delta_ms=1040]
- cloud_verified_before_count: md5_match=True sha256_match=True ledger_count=1 ordering=ledger_refs_timestamps ledger_refs_match=True drive_ref=1QNKeh***
- cleanup_after_verify: cleaned_locations=0 cleanup_before_verified=False
- cleanup_after_verify: reason=production_chua_co_duong_don_local; rang_buoc_chi_cam_don_truoc_VERIFIED
- plan_unchanged: digest_equal=True script_sha256=e55fd0cb media_count=5 render_matches_plan=True
- resume_300s: ready_seconds=10.0 limit=300 stop_attempts=1 stopped_in_render=True
- no_rerun_completed: completed_before_stop=7 reruns=0 attempts_unchanged=True
- trace_complete: snapshot_id_present=True model_refs=3 prompt_refs=7 config_revision=5 profile_sha256=aa9b6f8f
- secret_scan: match_count=0 khong_doc_Credentials=True capability_khong_ghi=True
- budget: attempts=1 ai_calls=6 cap=25 spent_usd=0 ceiling_usd=3 drive_bytes=4919316 cap_bytes=209715200 elapsed_s=372 limit_s=7200 remaining_s=6826
- seed: launcher_line=Đã nạp bộ media seed (idempotent). seed_counts={"hooks": 10, "media_assets": 455, "sources": 7} render_config=render_config=[preset/bold-yellow=PUBLISHED preset/output-profile=PUBLISHED policy/quality=PUBLISHED]
- start: pre_stop_attempts=1
- pre_check: other_workflows_running=0 (Temporal 127.0.0.1:7233 namespace default, chi doc)
- ai_calls_source: dem cp_ai_invocation_records record_key bat dau <ws>:<batch>:video: ai_calls=6 ledger_usd=0 (route_cost_per_request=0 nen ledger luon 0)
- batch_after_run=[db_status=COMPLETED_TARGET temporal_running=0 ids=[]] (OI-PW-E2E-01: trang thai dong lo la muc mo, RG-09 khong cham theo no)
- qc_evidence: blocking_gates=[none] duration=[mp4_ms=65452 voice_est_ms=64412 delta_ms=1040]
- media_audio_evidence=[media_count=5 media_ids=[ma-a5f,seed-b,seed-b,seed-b,seed-b] image_safety=[not_measured] bed_kind=not_measured music_cues=not_measured mp4_has_music=not_measured]

Tổng hợp theo yêu cầu của lệnh làm việc:

- batch_id, job_id: không có (output test không in; `ids=[]` vì lô không còn RUNNING).
- Bảng 11 stage (status/attempt): cả 11 stage SUCCEEDED/attempt 1 như dòng `stages_succeeded` ở trên.
- qc_evidence: hard_total=11, hard_passed=11, `blocking_gates=[none]`, `failed_detail`: không có (qc không hỏng); mp4_ms=65452, voice_est_ms=64412, delta_ms=1040.
- media_audio_evidence: 5 ảnh bài (media_count=5), seed: `seed-b` cho 4 ảnh và `ma-a5f` cho 1 ảnh; phán quyết an toàn ảnh `not_measured`; bed_kind `not_measured`; mp4 có nhạc `not_measured` (output thật không đo các mục này, không suy đoán).
- Số từ align đã chia: không có (output test không in số này).
- Location cloud VERIFIED: backend_ref cloud, evidence drive `1QNKeh***` (che còn 6 ký tự); số dòng ledger = 1, ledger_refs_match=True.
- cleanup_after_verify: PASS với `cleaned_locations=0`, lý do `production_chua_co_duong_don_local` (ràng buộc chỉ cấm dọn trước VERIFIED, `cleanup_before_verified=False`).
- drive_md5_check: md5_match=True, sha256_match=True.
- Ngân sách: ai_calls=6 (trần 25); ledger_usd=0 (trần 3); drive_bytes=4919316 (trần 209715200); elapsed_s=372 (trần 7200).
- Resume: ready_seconds=10.0 (trần 300); completed_before_stop=7; reruns=0; attempts_unchanged=True; stopped_in_render=True.

## Open item

- Sau lượt lô không còn RUNNING: `db_status=COMPLETED_TARGET`, `temporal_running=0`, `run_ids=[]`. Control không cần terminate lô nào.
- OI-PW-E2E-01: trạng thái đóng lô là mục mở; RG-09 không chạm theo nó (giữ nguyên).
- OI-CP7-10-F11: output pytest thật không có dòng nào nêu riêng mục này nên chưa thể khẳng định đã kiểm chứng trên ngăn xếp thật; giữ mở.
- OI-CP7-10-F12: output pytest thật không có dòng nào nêu riêng mục này nên chưa thể khẳng định đã kiểm chứng trên ngăn xếp thật; giữ mở. Liên quan: `image_safety`, `bed_kind`, `mp4_has_music` đều `not_measured` trong output lượt này.
