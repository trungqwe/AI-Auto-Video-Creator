# CP7-10 — R4 Video Alpha có giám sát trên ngăn xếp thật (RG-09)

- Ngày kiểm: 01/11/2026 (UTC; 02/11/2026 giờ Việt Nam).
- HEAD sau rebase: `7e126f792f7536bde5303834f604433221c26683` (rebase lên `9eaedbf4bd93469c0bcc041791263ecbaa7452df`).
- Interpreter khoá: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\8715e538\venv\Scripts\python.exe`.

## Kết luận trung thực

Lượt này **BLOCKED** ngay ở điều kiện tiên quyết của driver, trước khi tạo lô: `require_no_other_workflows` thấy Temporal còn 2 workflow RUNNING (`ProductionBatchWorkflow` và `VideoProductionWorkflow` của lô `f3f9e291-ce01-49ed-9939-a72e2192fad1`, tức lô còn sót từ lượt chạy thật trước). Driver báo `BLOCKED: OTHER_WORKFLOWS_RUNNING count=2` nên cả 11 test RG-09 lỗi ở setup fixture `batch_run`. Không có lô mới, không có stage nào chạy, không có lời gọi AI, không có upload Drive. Theo lệnh làm việc tôi không chạy lại, không tạo lô khác, không tự terminate workflow Temporal, không sửa production và không hạ ngưỡng RG-09. Vì chưa có số đo nào, cả 10 mục RG-09 ghi BLOCKED (không ghi PASS thiếu bằng chứng). Lô `f3f9e291` cần được Control xin user terminate trước lượt kế; bản sửa D-10-FIX1 và driver F11/F12 vẫn chưa được kiểm chứng trên ngăn xếp thật.

## Lệnh đã chạy

1. Bước 1: `git rebase 9eaedbf4bd93469c0bcc041791263ecbaa7452df` — thành công (24 commit), không xung đột, cây sạch, HEAD `7e126f792f7536bde5303834f604433221c26683`.
2. Bước 2: `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider -k unit` — exit 0, `45 passed, 11 deselected in 0.38s`.
3. Bước 3: `git diff --check` — exit 0, không có output.
4. Bước 4: `python -m pytest tests/real/test_cp7_video_alpha_e2e.py -q -p no:cacheprovider -s` (thêm `-s` để thấy mọi dòng in; ngoài ra giữ nguyên lệnh). Bắt đầu 2026-11-01T18:48:32Z, kết thúc 2026-11-01T18:49:27Z, exit 1, `45 passed, 11 errors in 54.69s`. Chạy đúng một lần; test không in dòng bằng chứng `RG-09.` hay `- ` nào vì driver dừng ở điều kiện tiên quyết.
5. Bước 6: `git diff --check` sau khi ghi report — exit 0, không có output.
6. Bước 7: probe 10 mục RG-09 — exit 1 (AssertionError liệt kê đủ 10 mục chưa PASS), đúng với kết quả BLOCKED thật ở bước 4; không sửa report cho probe xanh.

## Kết quả

RG-09.stages_succeeded: BLOCKED
RG-09.no_fake_adapters: BLOCKED
RG-09.qc_hard_gates: BLOCKED
RG-09.cloud_verified_before_count: BLOCKED
RG-09.cleanup_after_verify: BLOCKED
RG-09.plan_unchanged: BLOCKED
RG-09.resume_300s: BLOCKED
RG-09.no_rerun_completed: BLOCKED
RG-09.trace_complete: BLOCKED
RG-09.secret_scan: BLOCKED

## Chi tiết đo

- Lỗi nguyên văn: `BLOCKED: OTHER_WORKFLOWS_RUNNING count=2 ids=[ProductionBatchWorkflow=f3f9e291-ce01-49ed-9939-a72e2192fad1, VideoProductionWorkflow=f3f9e291-ce01-49ed-9939-a72e2192fad1:video:0]`.
- Batch id của lượt này: không có (chưa tạo lô). Job id: không có.
- Bảng 11 stage (status/attempt): không có, chưa chạy.
- qc_evidence (blocking_gates, failed_detail): không có, chưa tới stage qc.
- media_audio_evidence (số ảnh bài, seed, phán quyết an toàn ảnh, bed_kind, mp4 có nhạc): không có.
- Số từ align được chia: không có.
- Location cloud VERIFIED (backend_ref cloud, evidence drive che 6 ký tự): không có.
- cleanup_after_verify (cleaned_locations, lý do): không đo được.
- drive_md5_check (md5_match, sha256_match): không đo được.
- ai_calls=0, ledger_usd=0, drive_bytes=0 (không phát sinh); elapsed_s ≈ 54,69 (toàn phiên pytest); ready_seconds và completed_before_stop: không có (chưa tới bước stop/start giữa render).

## Open item

- Lô còn RUNNING trên Temporal: `db_status` và `temporal_running` của lượt này không đo được vì driver dừng trước khi tạo lô; workflow đang chạy do driver liệt kê là `run_ids=[batch_id=f3f9e291-ce01-49ed-9939-a72e2192fad1 job_id=chưa ghi nhận]`, `temporal_running=2` (batch + video:0). Control xin user terminate lô này trước lượt kế (user chỉ terminate, tôi không tự làm).
- OI-PW-E2E-01: giữ nguyên, chưa đổi.
- OI-CP7-10-F11 (nhận location cloud theo `CLOUD_BACKEND`, ordering_proof, media_audio_evidence): đã có trong mã và qua 45 unit test, nhưng CHƯA kiểm chứng trên ngăn xếp thật vì lượt này không tới stage sync/complete.
- OI-CP7-10-F12 (VISUAL_HOOK_PRESENT khi thumbnail trùng hook; D-10-FIX1 đã gộp): CHƯA kiểm chứng trên ngăn xếp thật, vì lượt này BLOCKED ở điều kiện tiên quyết trước stage qc.
