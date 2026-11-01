# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

- Ngày kiểm: 01/11/2026.
- HEAD cơ sở: `9768d8b0fac959261e9cd379395a486d4efc7787` (HEAD sau rebase; lane đã rebase lên `b6cc8d142a2a29a0f5f1e0e61dd2ce0eb67feffb`, kết quả kiểm của lần mở trước không còn dùng được).
- Interpreter khoá: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\8715e538\venv\Scripts\python.exe`.

## Kết luận trung thực

Lượt này **BLOCKED một phần**: job J đi hết 11 stage SUCCEEDED (attempt #1) và qua cổng QC 11/11, nhưng không có dòng location Drive nào được ghi nên `RG-09.cloud_verified_before_count` không đạt. Lần chạy ngăn xếp thật duy nhất bắt đầu 2026-11-01T09:22:03Z, kết thúc 09:38:25Z (981,05 giây), exit 1, `1 failed, 48 passed in 981.05s (0:16:21)`. Test fail là `test_rg09_cloud_verified_before_count`: `assert len(drive) == 1 ...` với `len(drive) == 0` (`batch_run.locations` không có location nào có backend_ref chứa `drive`). Cổng `SUBTITLE_BURNED_IN` (OI-CP7-10-F10) đã qua: `blocking_gates=[none]`, hard 11/11. Tôi không nới ngưỡng và không sửa production. `cleanup_after_verify` ghi BLOCKED vì kết quả chỉ đúng do không có gì để dọn (`cleaned_locations=0`), không phải bằng chứng đo trực tiếp. Sau lượt chạy Temporal RUNNING 0.

## Nguyên nhân và sửa

1. Lượt này chỉ đổi nhãn: `voice_ms` thành `voice_est_ms` trong `format_qc_evidence` (`tools/real/cp7_batch_driver.py`) và `test_unit_format_qc_evidence`. `voice_est_ms` là `timeline.voice_duration_ms` ước lượng của render package, không phải số đo ffprobe của voice artifact. Logic không đổi.
2. Lane đã rebase 21 commit lên `b6cc8d142a2a29a0f5f1e0e61dd2ce0eb67feffb`, không xung đột.
3. Chưa xác định nguyên nhân gốc của việc không có location Drive: stage `sync(upload_drive_and_verify)` báo SUCCEEDED nhưng `drive_bytes=0` và không có dòng location. Cần chủ mã sync/Drive (ngoài owned paths) điều tra.

## Lệnh đã chạy

1. Bước 1: `git rebase b6cc8d142a2a29a0f5f1e0e61dd2ce0eb67feffb` — thành công, không xung đột.
2. Bước 2-3: sửa nhãn `voice_est_ms` ở driver và test.
3. Bước 4: `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider -k unit` — exit 0, `38 passed, 11 deselected in 0.16s`.
4. Bước 5: `git diff --check` — exit 0, không output.
5. Bước 6 (đúng một lần, bắt đầu 2026-11-01T09:22:03Z; chạy thêm cờ `-s` để lấy output driver): `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider` — exit 1, `1 failed, 48 passed in 981.05s (0:16:21)`.
6. Bước 7: ghi lại report.md này bằng công cụ sửa tệp (UTF-8).
7. Bước 8-9: `git diff --check` và probe 10 mục RG-09 — xem báo cáo worker_done (probe đỏ đúng kỳ vọng).

## Kết quả

RG-09.stages_succeeded: PASS
RG-09.no_fake_adapters: PASS
RG-09.qc_hard_gates: PASS
RG-09.cloud_verified_before_count: BLOCKED
RG-09.cleanup_after_verify: BLOCKED
RG-09.plan_unchanged: PASS
RG-09.resume_300s: PASS
RG-09.no_rerun_completed: PASS
RG-09.trace_complete: PASS
RG-09.secret_scan: PASS

## Chi tiết đo

- Batch id B: `8d357809-63c3-4372-9107-4be6f3aac635`. Job id J: `8d357809-63c3-4372-9107-4be6f3aac635:job:1`.
- Stage (đều SUCCEEDED/attempt1): analyze(snapshot), script(script_ai), plan, media_select, tts, align, process, render, qc, sync(upload_drive_and_verify), complete(completion). elapsed_s=979; `final_batch_status=COMPLETED_TARGET` (OI-PW-E2E-01: không bắt buộc).
- no_fake_adapters: objects_scanned=283, violations=0, nguồn `launcher.load_app`, `production_py_sha256=1853e3ab8dc1f3290f283bde0f73a7ddd4eed5a95df67730295f3c24740b0f02`, read_only=True.
- qc_hard_gates: hard_total=11, hard_passed=11, not_applicable=0, blocking_gates=[none]; `duration=[mp4_ms=62960 voice_est_ms=65735 delta_ms=-2775]`. `voice_est_ms` là `timeline.voice_duration_ms` ước lượng, không đo bằng ffprobe.
- Workflow con chạy QC của J: output của driver lượt này không in workflow_id con nên không quan sát được; không suy đoán. Nhãn `:video:0` / `:video:1` của lượt trước không được xác nhận lại ở lượt này.
- plan_unchanged: digest_equal=True, script_sha256 tiền tố `df17a35e`, media_count=5, render_matches_plan=True.
- resume_300s: ready_seconds=10,9 (giới hạn 300), stop_attempts=1, stopped_in_render=True. no_rerun_completed: completed_before_stop=7, reruns=0, attempts_unchanged=True.
- trace_complete: snapshot_id_present=True, model_refs=3, prompt_refs=7, config_revision=5, profile_sha256 tiền tố `aa9b6f8f`.
- secret_scan: match_count=0, không đọc `Credentials/`, capability không ghi.
- cloud_verified_before_count: số location Drive = 0 (cần đúng 1, VERIFIED, có verification_evidence_ref). cleanup_after_verify: `cleaned_locations=0 cleanup_before_verified=False`, không đo được vì không có bản cloud verified.
- Chi phí: ai_calls=6 (trần 25), spent_usd=0 (trần 3; route_cost_per_request=0 nên ledger luôn 0), drive_bytes=0 (trần 209715200), elapsed_s=979 (trần 7200).
- md5 local và cloud: không đo được vì không có location Drive. Số từ align được chia: không in ra ở output driver, không đo được.
- Seed: hooks=10, media_assets=432, sources=7; render_config `preset/bold-yellow`, `preset/output-profile`, `policy/quality` đều PUBLISHED. Trước chạy `other_workflows_running=0`.

## Open item

- OI-CP7-10-F10: **đóng** — cổng `SUBTITLE_BURNED_IN` đã qua ở lượt này (blocking_gates=[none]).
- OI-CP7-10-F11 (mới): stage `sync(upload_drive_and_verify)` SUCCEEDED nhưng không có location Drive (`drive_bytes=0`, `locations` không có backend Drive), nên cloud_verified_before_count và cleanup_after_verify không đạt. Cần chủ mã sync/Drive (ngoài owned paths) xác định upload có thật chạy hay bị bỏ qua, rồi Control cấp lượt mới.
- OI-PW-E2E-01: production chưa có writer CREATED->RUNNING; RG-09 không chấm theo trạng thái dòng lô (lô ở COMPLETED_TARGET lượt này).
- Temporal RUNNING 0 sau lượt chạy (`batch_after_run=[db_status=COMPLETED_TARGET temporal_running=0 ids=[]]`); không có run_id nào cần terminate.

## Giới hạn trung thực

- Không hạ ngưỡng RG-09; trần 25 lời gọi AI, 3 USD, 200 MiB, 2 giờ, 300 giây resume giữ nguyên.
- Không SQL ghi; không cancel, terminate hay signal workflow; không sửa `src/**`; không đọc `Credentials/`.
- Ngăn xếp thật chạy đúng một lần, không thử lại, không tạo lô khác.
