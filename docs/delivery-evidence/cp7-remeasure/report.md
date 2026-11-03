# CP7-REMEASURE — Đo lại lô 100 video trên dây chuyền mới (lô lần 2)

## Kết luận trung thực

Gói CP7-REMEASURE đo lại đúng một lô thật 100 video (lô lần 2) trên HEAD tích hợp đã có QC-HOOK-FIX và STAGING-RETENTION, theo mục mở **OI-CP7-11-Q6**, bằng chính công cụ và bộ test của CP7-11; công thức và ngưỡng RG-10 giữ nguyên. Lô chạy đúng một lần (không chạy lô thứ hai).

**Trạng thái nghiệm thu: CHƯA ĐẠT, cần Control quyết.** Mục FAIL duy nhất: RG-10.failure_isolated (test thoát bằng `BLOCKED: nguồn 404 chưa có lượt thu thập nào trong lô, không chứng minh được cô lập lỗi`, tức target_runs=0 trong cửa sổ lô, không có lượt thu thập nào của nguồn 404 để chứng minh cô lập lỗi). 11 mục RG-10 còn lại PASS, warn_80_visible NOT_OBSERVED (acceptance chấp nhận), CQ.no_background_only PASS, CQ.real_hooks PASS, CQ.layout_cap_40 OVER (HERO_STRIP 41/100, trần 40; acceptance quy định kết quả là OVER chứ không FAIL, Control quyết). Điểm khác biệt chính so với lô lần 1: auto_ratio_95 và working_set_cap đã PASS.

`Batch ID: 875e2e7d-bf7c-438b-ba59-f64928dbc3eb`

`HEAD khi chạy: 479027bcd4ff15de30675c5c154916856fef78bc`

Lô đạt 100 video hợp lệ đã đồng bộ Drive (valid=100, invalid=0, drive_sample=6), tạo 101 job (1 FAILED_FINAL), dừng ở stop_reason=target_reached sau 16.469 s (khoảng 4 giờ 34 phút).

Ghi chú trung thực về quá trình chạy: lần khởi chạy đầu của lượt này thoát sau khoảng 1 giây (41 passed, 1 skipped, 16 errors) vì thư mục PYTEST_DEBUG_TEMPROOT riêng của lane chưa tồn tại (FileNotFoundError khi tạo pytest-of-unknown); lần đó chưa có Batch ID, chưa khởi động launcher hay worker, chưa có lô nào. Worker (Sonnet 5.5) đã hỏi coordinator, được trả lời YES, tạo thư mục rồi chạy lô đúng một lần; lô trong báo cáo này là lô duy nhất đã chạy.

## Cổng bộ nhớ trước lô (lô lần 2)

Đo một chuỗi 10 lần cách nhau 60 giây (RAM trống GiB / khoảng trống commit GiB):

1. 5,83 / 13,63
2. 6,34 / 14,28
3. 6,16 / 14,09
4. 5,91 / 13,81
5. 6,04 / 14,04
6. 6,04 / 14,11
7. 6,15 / 14,09
8. 6,07 / 14,08
9. 5,99 / 13,93
10. 6,05 / 13,93

Số lần RAM trống ≥ 6 GiB: 7/10 (lần 2, 3, 5, 6, 7, 8, 10). Khoảng trống commit nhỏ nhất: 13,63 GiB (≥ 12 GiB ở cả 10 lần). Kết luận: cổng bộ nhớ ĐẠT. Trước khi chạy lô (sau thời gian chờ trả lời của coordinator) đo lại một lần RAM trống: 5,99 GiB; Control đã cho phép tiếp tục (trả lời YES).

## Lịch sử

Lô lần 1 mã f132d43a-e25d-42c3-afe6-373d1155ecd6, HEAD a8a92461a94ed14db71c325bb2b65f96540746ea, chạy trước QC-HOOK-FIX và STAGING-RETENTION: 100/153 = 65,36%, 3 mục RG-10 FAIL (auto_ratio_95; failure_isolated với target_runs=0; working_set_cap 21,46 GiB), CQ.layout_cap_40 OVER (HERO_STRIP 41%). Đây chỉ là lịch sử, không phải kết quả của lô hiện tại.

## Lệnh đã chạy

- `HEAD khi chạy: 479027bcd4ff15de30675c5c154916856fef78bc`
- Interpreter khoá: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\8715e538\venv\Scripts\python.exe`
- Lệnh `git diff --check`: exit code `0`
- Lệnh `python -m pytest tests/real/test_cp7_remeasure.py -q -p no:cacheprovider` (kiểm trước lô): exit code `0`, dòng tổng kết nguyên văn `18 passed, 1 skipped in 0.06s`
- Lệnh `python -m pytest tests/real/test_cp7_overnight.py -q -p no:cacheprovider` (kiểm trước lô): exit code `0`, dòng tổng kết nguyên văn `43 passed, 15 skipped in 0.30s`
- Chạy lô thật đúng một lần bằng Start-Process tách tiến trình (CP7_RG10_LIVE=1, PYTHONUTF8=1, PYTEST_DEBUG_TEMPROOT=C:\Users\Admin\AppData\Local\Temp\ai-setup-pytest\CP7-REMEASURE-lane-r2, log ngoài repo): lệnh `python -m pytest tests/real/test_cp7_overnight.py -q -p no:cacheprovider`, dòng tổng kết nguyên văn `1 failed, 56 passed, 1 skipped in 16527.58s (4:35:27)`. Mã thoát là `1` (suy ra từ dòng tổng kết có 1 failed; Worker không đọc trực tiếp mã thoát vì tiến trình tách riêng đã kết thúc trong lúc chờ). Launcher đã dừng sau lô (không còn tiến trình launcher.py của worktree).
- Đo CQ sau lô (CP7_REMEASURE_BATCH_PREFIX=875e2e7d): lệnh `python -m pytest tests/real/test_cp7_remeasure.py -q -p no:cacheprovider -k test_cq -rP`, exit code `0`, dòng tổng kết nguyên văn `1 passed, 18 deselected in 0.34s`
- Chẩn đoán FAILED_FINAL (CP7_DIAG_BATCH_PREFIX=875e2e7d): lệnh `python -m pytest tests/real/test_cp7_overnight.py -q -p no:cacheprovider -k test_diag -rP`, exit code `0`, dòng tổng kết nguyên văn `1 passed, 57 deselected in 0.19s`
- Kiểm tra mặc định sau lô, không chạy thật: lệnh `python -m pytest tests/real/test_cp7_remeasure.py -q -p no:cacheprovider`, exit code `0`, dòng tổng kết nguyên văn `18 passed, 1 skipped in 0.05s`
- Kiểm tra mặc định sau lô, không chạy thật: lệnh `python -m pytest tests/real/test_cp7_overnight.py -q -p no:cacheprovider`, exit code `0`, dòng tổng kết nguyên văn `43 passed, 15 skipped in 0.36s`

## Kết quả

Các dòng RG-10 nguyên văn từ log lô:

```text
RG-10.drive_quota_ok: PASS
RG-10.valid_synced_100: PASS
RG-10.within_12h: PASS
RG-10.auto_ratio_95: PASS
RG-10.no_vanished_jobs: PASS
RG-10.resume_300s_midrun: PASS
RG-10.no_rerun_completed: PASS
RG-10.cost_under_cap: PASS
RG-10.working_set_cap: PASS
RG-10.stage_metrics: PASS
RG-10.secret_scan: PASS
RG-10.warn_80_visible: NOT_OBSERVED
```

Lưu ý: log lô chỉ có 12 dòng `RG-10.*`; mục thứ 13 là `RG-10.failure_isolated` kết thúc bằng pytest.fail nên không in dòng `RG-10.failure_isolated: ...`; kết quả của nó là FAIL với thông điệp `Failed: BLOCKED: nguồn 404 chưa có lượt thu thập nào trong lô, không chứng minh được cô lập lỗi` (tests\real\test_cp7_overnight.py:545). Ba dòng CQ nguyên văn từ test_cq:

```text
CQ.no_background_only: PASS
CQ.real_hooks: PASS
CQ.layout_cap_40: OVER
```

## Chi tiết đo

```text
- drive_quota_ok: free_gib=5114.10
- drive_quota_ok: required_gib=1036.00
- drive_quota_ok: unlimited=False
- valid_synced_100: valid=100
- valid_synced_100: invalid=0
- valid_synced_100: drive_sample=6
- within_12h: started_utc=2026-11-03T18:04:29Z
- within_12h: target_utc=2026-11-03T22:38:57Z
- within_12h: t_target_s=16469
- wait_provider_seconds=12286
- concurrency={"default": 6, "max": 10, "min": 1}
- auto_ratio_95: failure_cause stage=align code=word_coverage_incomplete activity=CreateWordTiming n=1
- auto_ratio_95: valid=100
- auto_ratio_95: total=101
- auto_ratio_95: failed_final=1
- auto_ratio_95: manual_actions=0
- no_vanished_jobs: jobs=101
- no_vanished_jobs: findings=0
- resume_300s_midrun: ready_seconds=15.6
- resume_300s_midrun: stop_attempts=1
- resume_300s_midrun: busy_at_stop=6
- resume_300s_midrun: completed_at_stop=40
- no_rerun_completed: jobs_checked=6
- no_rerun_completed: reruns=0
- cost_under_cap: night_usd=0
- cost_under_cap: month_usd=0
- cost_under_cap: ai_calls=665
- cost_under_cap: drive_bytes=2077197203
- cost_under_cap: usd_per_valid_video=0.0000
- cost_under_cap: route_cost_per_request=0 nen ledger co the bang 0
- working_set_cap: max_working_set_gib=10.27
- working_set_cap: min_disk_free_gib=178.7
- working_set_cap: max_vram_mib=11779
- working_set_cap: samples=56
- working_set_cap: sample_errors=0
- stage_metrics: analyze(snapshot) n=101 p50_s=42.4 p95_s=55.1 max_s=76.9 extra_attempts=0
- stage_metrics: script(script_ai) n=101 p50_s=94.8 p95_s=129.5 max_s=519.8 extra_attempts=0
- stage_metrics: plan(plan) n=101 p50_s=81.4 p95_s=486.7 max_s=2623.4 extra_attempts=0
- stage_metrics: media_select(media_select) n=101 p50_s=340.9 p95_s=1257.4 max_s=2370.9 extra_attempts=0
- stage_metrics: tts(tts) n=101 p50_s=11.4 p95_s=25.4 max_s=30.3 extra_attempts=0
- stage_metrics: align(align) n=100 p50_s=7.7 p95_s=15.0 max_s=27.3 extra_attempts=0
- stage_metrics: process(process) n=100 p50_s=73.7 p95_s=163.3 max_s=401.3 extra_attempts=0
- stage_metrics: render(render) n=100 p50_s=19.7 p95_s=32.0 max_s=131.7 extra_attempts=0
- stage_metrics: qc(qc) n=100 p50_s=3.1 p95_s=5.0 max_s=6.6 extra_attempts=0
- stage_metrics: sync(upload_drive_and_verify) n=100 p50_s=14.5 p95_s=32.0 max_s=56.4 extra_attempts=0
- stage_metrics: complete(completion) n=100 p50_s=0.0 p95_s=0.6 max_s=0.6 extra_attempts=0
- lead_time: p50_s=756.6 p95_s=1789.2 videos_per_hour=21.9
- secret_scan: match_count=0
- secret_scan: khong_doc_Credentials=True
- secret_scan: capability_khong_ghi=True
- warn_80_visible: peak_month_usd=0
- sample t=2026-11-03T18:04:29Z elapsed_s=0 batch=CREATED jobs={} valid=0 running_stages=0 night_usd=0 month_usd=0 ai_calls=0 data_free_gib=205.8 sys_free_gib=40.0 working_set_gib=8.13 vram_mib=769
- sample t=2026-11-03T18:09:29Z elapsed_s=300 batch=RUNNING jobs={"ACTIVE":6} valid=0 running_stages=6 night_usd=0 month_usd=0 ai_calls=18 data_free_gib=197.1 sys_free_gib=40.0 working_set_gib=8.06 vram_mib=10501
- sample t=2026-11-03T18:14:29Z elapsed_s=600 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":1} valid=1 running_stages=6 night_usd=0 month_usd=0 ai_calls=25 data_free_gib=185.0 sys_free_gib=40.0 working_set_gib=7.64 vram_mib=11565
- sample t=2026-11-03T18:19:30Z elapsed_s=900 batch=RUNNING jobs={"ACTIVE":2,"COMPLETED":2,"WAITING":4} valid=2 running_stages=6 night_usd=0 month_usd=0 ai_calls=30 data_free_gib=193.1 sys_free_gib=40.0 working_set_gib=7.65 vram_mib=954
- sample t=2026-11-03T18:24:30Z elapsed_s=1201 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":3,"SNAPSHOTTED":1} valid=3 running_stages=6 night_usd=0 month_usd=0 ai_calls=45 data_free_gib=193.5 sys_free_gib=40.0 working_set_gib=7.78 vram_mib=1272
- sample t=2026-11-03T18:29:30Z elapsed_s=1501 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":7,"WAITING":1} valid=7 running_stages=6 night_usd=0 month_usd=0 ai_calls=62 data_free_gib=192.5 sys_free_gib=40.0 working_set_gib=7.86 vram_mib=2141
- sample t=2026-11-03T18:34:30Z elapsed_s=1801 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":8,"SNAPSHOTTED":1} valid=8 running_stages=6 night_usd=0 month_usd=0 ai_calls=69 data_free_gib=190.3 sys_free_gib=40.0 working_set_gib=7.80 vram_mib=10433
- sample t=2026-11-03T18:39:30Z elapsed_s=2101 batch=RUNNING jobs={"ACTIVE":3,"COMPLETED":10,"WAITING":3} valid=10 running_stages=6 night_usd=0 month_usd=0 ai_calls=85 data_free_gib=195.8 sys_free_gib=40.0 working_set_gib=7.87 vram_mib=966
- sample t=2026-11-03T18:44:31Z elapsed_s=2401 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":11} valid=11 running_stages=6 night_usd=0 month_usd=0 ai_calls=97 data_free_gib=192.1 sys_free_gib=40.0 working_set_gib=7.91 vram_mib=1261
- sample t=2026-11-03T18:49:31Z elapsed_s=2702 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":15,"WAITING":1} valid=15 running_stages=6 night_usd=0 month_usd=0 ai_calls=118 data_free_gib=191.6 sys_free_gib=40.0 working_set_gib=8.09 vram_mib=10435
- sample t=2026-11-03T18:54:31Z elapsed_s=3002 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":17,"WAITING":1} valid=17 running_stages=6 night_usd=0 month_usd=0 ai_calls=130 data_free_gib=191.6 sys_free_gib=40.0 working_set_gib=8.04 vram_mib=10432
- sample t=2026-11-03T18:59:31Z elapsed_s=3302 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":19,"WAITING":1} valid=19 running_stages=6 night_usd=0 month_usd=0 ai_calls=142 data_free_gib=192.3 sys_free_gib=40.0 working_set_gib=8.10 vram_mib=10431
- sample t=2026-11-03T19:04:31Z elapsed_s=3602 batch=RUNNING jobs={"ACTIVE":3,"COMPLETED":22,"SNAPSHOTTED":1,"WAITING":2} valid=22 running_stages=6 night_usd=0 month_usd=0 ai_calls=157 data_free_gib=193.7 sys_free_gib=40.0 working_set_gib=8.26 vram_mib=966
- sample t=2026-11-03T19:09:32Z elapsed_s=3903 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":23} valid=23 running_stages=6 night_usd=0 month_usd=0 ai_calls=171 data_free_gib=188.9 sys_free_gib=40.0 working_set_gib=8.20 vram_mib=2975
- sample t=2026-11-03T19:14:32Z elapsed_s=4203 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":25} valid=25 running_stages=6 night_usd=0 month_usd=0 ai_calls=187 data_free_gib=193.0 sys_free_gib=40.0 working_set_gib=8.40 vram_mib=975
- sample t=2026-11-03T19:19:32Z elapsed_s=4503 batch=RUNNING jobs={"ACTIVE":4,"COMPLETED":29,"WAITING":2} valid=29 running_stages=6 night_usd=0 month_usd=0 ai_calls=203 data_free_gib=194.0 sys_free_gib=40.0 working_set_gib=8.37 vram_mib=968
- sample t=2026-11-03T19:24:32Z elapsed_s=4803 batch=RUNNING jobs={"ACTIVE":4,"COMPLETED":30,"WAITING":2} valid=30 running_stages=6 night_usd=0 month_usd=0 ai_calls=215 data_free_gib=194.1 sys_free_gib=40.0 working_set_gib=8.37 vram_mib=1260
- sample t=2026-11-03T19:29:33Z elapsed_s=5103 batch=RUNNING jobs={"ACTIVE":3,"COMPLETED":33,"SNAPSHOTTED":1,"WAITING":2} valid=33 running_stages=6 night_usd=0 month_usd=0 ai_calls=229 data_free_gib=188.4 sys_free_gib=39.9 working_set_gib=8.49 vram_mib=964
- sample t=2026-11-03T19:34:33Z elapsed_s=5404 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":34,"WAITING":1} valid=34 running_stages=6 night_usd=0 month_usd=0 ai_calls=246 data_free_gib=189.0 sys_free_gib=39.9 working_set_gib=8.39 vram_mib=11569
- sample t=2026-11-03T19:39:33Z elapsed_s=5704 batch=RUNNING jobs={"ACTIVE":3,"COMPLETED":37,"WAITING":3} valid=37 running_stages=6 night_usd=0 month_usd=0 ai_calls=258 data_free_gib=193.4 sys_free_gib=39.9 working_set_gib=8.57 vram_mib=950
- sample t=2026-11-03T19:44:33Z elapsed_s=6004 batch=RUNNING jobs={"ACTIVE":3,"COMPLETED":37,"WAITING":3} valid=37 running_stages=6 night_usd=0 month_usd=0 ai_calls=261 data_free_gib=188.7 sys_free_gib=39.9 working_set_gib=8.47 vram_mib=10421
- sample t=2026-11-03T19:49:33Z elapsed_s=6304 batch=RUNNING jobs={"ACTIVE":4,"COMPLETED":39,"FAILED_FINAL":1,"SNAPSHOTTED":1,"WAITING":1} valid=39 running_stages=6 night_usd=0 month_usd=0 ai_calls=284 data_free_gib=193.2 sys_free_gib=39.9 working_set_gib=8.63 vram_mib=1005
- sample t=2026-11-03T19:54:34Z elapsed_s=6605 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":42,"FAILED_FINAL":1,"WAITING":1} valid=42 running_stages=6 night_usd=0 month_usd=0 ai_calls=296 data_free_gib=196.7 sys_free_gib=39.9 working_set_gib=8.62 vram_mib=1089
- sample t=2026-11-03T19:59:34Z elapsed_s=6905 batch=RUNNING jobs={"ACTIVE":4,"COMPLETED":43,"FAILED_FINAL":1,"WAITING":1} valid=43 running_stages=5 night_usd=0 month_usd=0 ai_calls=310 data_free_gib=193.7 sys_free_gib=39.9 working_set_gib=8.67 vram_mib=1155
- sample t=2026-11-03T20:04:34Z elapsed_s=7205 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":47,"FAILED_FINAL":1,"WAITING":1} valid=47 running_stages=6 night_usd=0 month_usd=0 ai_calls=327 data_free_gib=188.9 sys_free_gib=39.9 working_set_gib=8.79 vram_mib=10650
- sample t=2026-11-03T20:09:34Z elapsed_s=7505 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":48,"FAILED_FINAL":1} valid=48 running_stages=6 night_usd=0 month_usd=0 ai_calls=338 data_free_gib=187.8 sys_free_gib=39.9 working_set_gib=8.77 vram_mib=10468
- sample t=2026-11-03T20:14:35Z elapsed_s=7805 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":51,"FAILED_FINAL":1,"SNAPSHOTTED":1} valid=51 running_stages=6 night_usd=0 month_usd=0 ai_calls=354 data_free_gib=187.0 sys_free_gib=39.9 working_set_gib=8.96 vram_mib=10473
- sample t=2026-11-03T20:19:35Z elapsed_s=8106 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":53,"FAILED_FINAL":1} valid=53 running_stages=6 night_usd=0 month_usd=0 ai_calls=366 data_free_gib=186.9 sys_free_gib=39.9 working_set_gib=8.91 vram_mib=10496
- sample t=2026-11-03T20:24:35Z elapsed_s=8406 batch=RUNNING jobs={"ACTIVE":4,"COMPLETED":55,"FAILED_FINAL":1,"WAITING":2} valid=55 running_stages=6 night_usd=0 month_usd=0 ai_calls=381 data_free_gib=190.3 sys_free_gib=39.9 working_set_gib=8.93 vram_mib=1025
- sample t=2026-11-03T20:29:35Z elapsed_s=8706 batch=RUNNING jobs={"ACTIVE":4,"COMPLETED":57,"FAILED_FINAL":1,"WAITING":2} valid=57 running_stages=6 night_usd=0 month_usd=0 ai_calls=392 data_free_gib=184.4 sys_free_gib=39.9 working_set_gib=9.02 vram_mib=1004
- sample t=2026-11-03T20:34:35Z elapsed_s=9006 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":59,"FAILED_FINAL":1,"WAITING":1} valid=59 running_stages=6 night_usd=0 month_usd=0 ai_calls=406 data_free_gib=184.1 sys_free_gib=39.9 working_set_gib=9.11 vram_mib=11779
- sample t=2026-11-03T20:39:36Z elapsed_s=9307 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":61,"FAILED_FINAL":1,"WAITING":1} valid=61 running_stages=6 night_usd=0 month_usd=0 ai_calls=419 data_free_gib=185.1 sys_free_gib=39.9 working_set_gib=9.10 vram_mib=10471
- sample t=2026-11-03T20:44:36Z elapsed_s=9607 batch=RUNNING jobs={"ACTIVE":4,"COMPLETED":62,"FAILED_FINAL":1,"WAITING":2} valid=62 running_stages=6 night_usd=0 month_usd=0 ai_calls=433 data_free_gib=190.5 sys_free_gib=39.3 working_set_gib=9.17 vram_mib=1002
- sample t=2026-11-03T20:49:36Z elapsed_s=9907 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":65,"FAILED_FINAL":1} valid=65 running_stages=6 night_usd=0 month_usd=0 ai_calls=448 data_free_gib=186.8 sys_free_gib=39.3 working_set_gib=9.21 vram_mib=10465
- sample t=2026-11-03T20:54:36Z elapsed_s=10207 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":68,"FAILED_FINAL":1} valid=68 running_stages=6 night_usd=0 month_usd=0 ai_calls=461 data_free_gib=184.4 sys_free_gib=39.8 working_set_gib=9.31 vram_mib=1065
- sample t=2026-11-03T20:59:37Z elapsed_s=10508 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":69,"FAILED_FINAL":1,"WAITING":1} valid=69 running_stages=6 night_usd=0 month_usd=0 ai_calls=473 data_free_gib=186.8 sys_free_gib=39.8 working_set_gib=9.38 vram_mib=10501
- sample t=2026-11-03T21:04:37Z elapsed_s=10808 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":71,"FAILED_FINAL":1} valid=71 running_stages=6 night_usd=0 month_usd=0 ai_calls=489 data_free_gib=189.7 sys_free_gib=39.8 working_set_gib=9.51 vram_mib=1350
- sample t=2026-11-03T21:09:37Z elapsed_s=11108 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":75,"FAILED_FINAL":1} valid=75 running_stages=6 night_usd=0 month_usd=0 ai_calls=505 data_free_gib=183.0 sys_free_gib=39.8 working_set_gib=9.56 vram_mib=10475
- sample t=2026-11-03T21:14:37Z elapsed_s=11408 batch=RUNNING jobs={"ACTIVE":4,"COMPLETED":75,"FAILED_FINAL":1,"WAITING":2} valid=75 running_stages=6 night_usd=0 month_usd=0 ai_calls=512 data_free_gib=185.0 sys_free_gib=39.8 working_set_gib=9.55 vram_mib=10481
- sample t=2026-11-03T21:19:38Z elapsed_s=11709 batch=RUNNING jobs={"ACTIVE":1,"COMPLETED":77,"FAILED_FINAL":1,"SNAPSHOTTED":1,"WAITING":4} valid=77 running_stages=6 night_usd=0 month_usd=0 ai_calls=522 data_free_gib=189.2 sys_free_gib=39.8 working_set_gib=9.63 vram_mib=1042
- sample t=2026-11-03T21:24:38Z elapsed_s=12009 batch=RUNNING jobs={"ACTIVE":2,"COMPLETED":77,"FAILED_FINAL":1,"WAITING":4} valid=77 running_stages=6 night_usd=0 month_usd=0 ai_calls=528 data_free_gib=189.0 sys_free_gib=39.8 working_set_gib=9.60 vram_mib=1044
- sample t=2026-11-03T21:29:38Z elapsed_s=12309 batch=RUNNING jobs={"ACTIVE":2,"COMPLETED":78,"FAILED_FINAL":1,"WAITING":4} valid=78 running_stages=6 night_usd=0 month_usd=0 ai_calls=536 data_free_gib=188.8 sys_free_gib=39.8 working_set_gib=9.65 vram_mib=1042
- sample t=2026-11-03T21:34:38Z elapsed_s=12609 batch=RUNNING jobs={"ACTIVE":1,"COMPLETED":80,"FAILED_FINAL":1,"SNAPSHOTTED":2,"WAITING":3} valid=80 running_stages=6 night_usd=0 month_usd=0 ai_calls=544 data_free_gib=179.3 sys_free_gib=39.8 working_set_gib=9.75 vram_mib=11549
- sample t=2026-11-03T21:39:38Z elapsed_s=12909 batch=RUNNING jobs={"ACTIVE":4,"COMPLETED":80,"FAILED_FINAL":1,"WAITING":2} valid=80 running_stages=6 night_usd=0 month_usd=0 ai_calls=560 data_free_gib=183.4 sys_free_gib=39.8 working_set_gib=9.75 vram_mib=1295
- sample t=2026-11-03T21:44:39Z elapsed_s=13210 batch=RUNNING jobs={"ACTIVE":3,"COMPLETED":83,"FAILED_FINAL":1,"WAITING":3} valid=83 running_stages=6 night_usd=0 month_usd=0 ai_calls=571 data_free_gib=188.8 sys_free_gib=39.8 working_set_gib=9.74 vram_mib=1006
- sample t=2026-11-03T21:49:39Z elapsed_s=13510 batch=RUNNING jobs={"ACTIVE":3,"COMPLETED":83,"FAILED_FINAL":1,"WAITING":3} valid=83 running_stages=6 night_usd=0 month_usd=0 ai_calls=580 data_free_gib=188.7 sys_free_gib=39.8 working_set_gib=9.80 vram_mib=1026
- sample t=2026-11-03T21:54:39Z elapsed_s=13810 batch=RUNNING jobs={"ACTIVE":4,"COMPLETED":86,"FAILED_FINAL":1,"SNAPSHOTTED":1,"WAITING":1} valid=86 running_stages=5 night_usd=0 month_usd=0 ai_calls=594 data_free_gib=182.9 sys_free_gib=39.8 working_set_gib=9.93 vram_mib=1243
- sample t=2026-11-03T21:59:40Z elapsed_s=14111 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":89,"FAILED_FINAL":1} valid=89 running_stages=6 night_usd=0 month_usd=0 ai_calls=610 data_free_gib=183.8 sys_free_gib=39.8 working_set_gib=9.93 vram_mib=10460
- sample t=2026-11-03T22:04:41Z elapsed_s=14412 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":90,"FAILED_FINAL":1,"WAITING":1} valid=90 running_stages=6 night_usd=0 month_usd=0 ai_calls=619 data_free_gib=182.4 sys_free_gib=39.8 working_set_gib=10.01 vram_mib=10503
- sample t=2026-11-03T22:09:41Z elapsed_s=14712 batch=RUNNING jobs={"ACTIVE":4,"COMPLETED":91,"FAILED_FINAL":1,"SNAPSHOTTED":1,"WAITING":1} valid=91 running_stages=6 night_usd=0 month_usd=0 ai_calls=630 data_free_gib=178.7 sys_free_gib=39.8 working_set_gib=10.10 vram_mib=10759
- sample t=2026-11-03T22:14:41Z elapsed_s=15012 batch=RUNNING jobs={"ACTIVE":4,"COMPLETED":94,"FAILED_FINAL":1,"WAITING":2} valid=94 running_stages=6 night_usd=0 month_usd=0 ai_calls=642 data_free_gib=183.0 sys_free_gib=39.8 working_set_gib=10.19 vram_mib=11602
- sample t=2026-11-03T22:19:42Z elapsed_s=15313 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":94,"FAILED_FINAL":1,"WAITING":1} valid=94 running_stages=6 night_usd=0 month_usd=0 ai_calls=652 data_free_gib=181.7 sys_free_gib=39.8 working_set_gib=10.15 vram_mib=10745
- sample t=2026-11-03T22:24:42Z elapsed_s=15613 batch=RUNNING jobs={"COMPLETED":98,"FAILED_FINAL":1,"WAITING":2} valid=98 running_stages=2 night_usd=0 month_usd=0 ai_calls=659 data_free_gib=187.4 sys_free_gib=39.8 working_set_gib=10.27 vram_mib=1015
- sample t=2026-11-03T22:29:42Z elapsed_s=15913 batch=RUNNING jobs={"ACTIVE":1,"COMPLETED":98,"FAILED_FINAL":1,"WAITING":1} valid=98 running_stages=2 night_usd=0 month_usd=0 ai_calls=662 data_free_gib=187.4 sys_free_gib=39.8 working_set_gib=10.22 vram_mib=1016
- sample t=2026-11-03T22:34:43Z elapsed_s=16213 batch=RUNNING jobs={"COMPLETED":99,"FAILED_FINAL":1,"WAITING":1} valid=99 running_stages=1 night_usd=0 month_usd=0 ai_calls=662 data_free_gib=187.4 sys_free_gib=39.8 working_set_gib=10.23 vram_mib=1020
- sample t=2026-11-03T22:38:57Z elapsed_s=16468 batch=COMPLETED_TARGET jobs={"COMPLETED":100,"FAILED_FINAL":1} valid=100 running_stages=0 night_usd=0 month_usd=0 ai_calls=665 data_free_gib=187.3 sys_free_gib=39.8 working_set_gib=10.27 vram_mib=1017
- budget: night_usd=0 month_usd=0 drive_bytes=2077197203 elapsed_s=16469 deadline_s=44100 stop_reason=target_reached
- seed: launcher_seed_line=\u0110\xe3 n\u1ea1p b\u1ed9 media seed (idempotent). render_config=render_config=[preset/bold-yellow=PUBLISHED preset/output-profile=PUBLISHED policy/quality=PUBLISHED]
- batch: id=875e2e7d concurrency={"default": 6, "max": 10, "min": 1} other_workflows_running=0 not_found_status=404 not_found_source registered=0 existing=0
- cq: batch=875e2e7d videos=100
- cq: layout_valid={"counts":{"DATA_CARD":3,"FULL_BLEED_INSET":13,"HERO_STRIP":41,"MOSAIC_GRID":3,"SPLIT_STACK":40},"distinct":5,"limit":40,"over":{"HERO_STRIP":41}}
- cq: layout_batch={"counts":{"DATA_CARD":3,"FULL_BLEED_INSET":13,"HERO_STRIP":41,"MOSAIC_GRID":3,"SPLIT_STACK":40},"distinct":5,"limit":40,"over":{"HERO_STRIP":41}}
- cq: layout_fallbacks={}
- cq: ai_images={"max":6,"min":0,"n":100,"p50":3,"total":323} videos_with_ai=94
- cq: article_images={"max":7,"min":0,"n":100,"p50":1,"total":114}
- cq: background_only=0 seed_share_max_pct=0.0
- cq: scenes={"max":8,"min":4,"n":100,"p50":6,"total":555} duration_s={"max":73.0,"min":57.6,"n":100,"p50":63.9,"total":6437.1}
- cq: hook_sources={"audio_hook":{"freesound":100},"visual_hook":{"pixabay":100}} not_real=0
- cq: distinct_visual_hooks=23 distinct_audio_hooks=13 distinct_audio_hook_queries=6
- cq: distinct_music=13 videos_without_music=0
- cq: span_s=16465.9 prev_t_target_s=6849 delta_s=+9616.9
- cq: lead_p50_s=756.6 prev=364.6 lead_p95_s=1789.2 prev=748.1
- cq: stage_p50 analyze now=42.4 prev=42.3 delta=+0.1
- cq: stage_p50 script now=94.8 prev=98.3 delta=-3.5
- cq: stage_p50 plan now=81.4 prev=66.7 delta=+14.7
- cq: stage_p50 media_select now=340.9 prev=50.3 delta=+290.6
- cq: stage_p50 tts now=11.4 prev=15.9 delta=-4.5
- cq: stage_p50 align now=7.7 prev=9.9 delta=-2.2
- cq: stage_p50 process now=73.7 prev=27.5 delta=+46.2
- cq: stage_p50 render now=19.7 prev=13.5 delta=+6.2
- cq: stage_p50 qc now=3.1 prev=3.2 delta=-0.1
- cq: stage_p50 sync now=14.5 prev=13.7 delta=+0.8
- cq: stage_p50 complete now=0.0 prev=0.1 delta=-0.1
- cq: failed_final stage=align code=word_coverage_incomplete activity=CreateWordTiming n=1
- diag: batch=875e2e7d jobs=101 failed_final=1
- diag_cause: stage=align code=word_coverage_incomplete activity=CreateWordTiming n=1
- diag_job: job=875e2e7d stage=align attempt=1 status=FAILED_FINAL code=word_coverage_incomplete message=
```

## So sánh với lượt trước

Lô 74e795ef (lượt trước CP7-11), lô lần 1 f132d43a (lịch sử) và lô lần 2 (875e2e7d); chênh lệch của lô lần 2 tính so với 74e795ef.

| Chỉ số | Lô 74e795ef | Lô lần 1 f132d43a | Lô lần 2 875e2e7d (chênh lệch so với 74e795ef) |
| :--- | :--- | :--- | :--- |
| t_target_s | 6849 s | 26641 s | 16469 s (+9620 s) |
| Thời gian pytest | 6906,16 s | 26772,85 s | 16527,58 s (+9621,42 s) |
| lead p50 | 364,6 s | 812,3 s | 756,6 s (+392,0 s) |
| lead p95 | 748,1 s | 2022,7 s | 1789,2 s (+1041,1 s) |
| videos_per_hour | 52,6 | 13,5 | 21,9 (-30,7) |
| Tổng job | 101 | 153 | 101 (0) |
| FAILED_FINAL | 1 | 53 | 1 (0) |
| Tỷ lệ tự hoàn thành | 99,01% | 65,36% | 99,01% (100/101; 0 điểm phần trăm) |

stage_p50 của lô lần 2 (giây; dòng `- cq: stage_p50`, prev là lô 74e795ef):

- analyze: 42,4 (prev 42,3, delta +0,1)
- script: 94,8 (prev 98,3, delta -3,5)
- plan: 81,4 (prev 66,7, delta +14,7)
- media_select: 340,9 (prev 50,3, delta +290,6)
- tts: 11,4 (prev 15,9, delta -4,5)
- align: 7,7 (prev 9,9, delta -2,2)
- process: 73,7 (prev 27,5, delta +46,2)
- render: 19,7 (prev 13,5, delta +6,2)
- qc: 3,1 (prev 3,2, delta -0,1)
- sync: 14,5 (prev 13,7, delta +0,8)
- complete: 0,0 (prev 0,1, delta -0,1)

### FAILED_FINAL theo nguyên nhân

| Lô | stage | code | activity | n |
| :--- | :--- | :--- | :--- | :--- |
| 74e795ef | render | no_illustration_available | resolve_render_package | 1 |
| f132d43a (lần 1) | qc | quality_gates_failed | inspect_output | 51 |
| f132d43a (lần 1) | tts | voice_duration_out_of_range | CreateVoiceTrack | 1 |
| f132d43a (lần 1) | none | none | none | 1 |
| 875e2e7d (lần 2) | align | word_coverage_incomplete | CreateWordTiming | 1 |

Lô lần 2 không còn lỗi qc/quality_gates_failed; có đúng 1 job FAILED_FINAL ở stage align (message rỗng trong diag_job). Nguyên nhân gốc của lỗi align chưa có số đo; GIẢ ĐỊNH chưa kiểm: bản ghi giọng không phủ đủ từ trong căn thời gian.

## Chất lượng hình và tiếng

- **Phân bố bố cục** (100 video, trần 40%): HERO_STRIP 41 video (41%, vượt trần một video, CQ.layout_cap_40: OVER), SPLIT_STACK 40 video (40%), FULL_BLEED_INSET 13 video (13%), DATA_CARD 3 video (3%), MOSAIC_GRID 3 video (3%). Lô dùng đủ 5 bố cục (distinct=5) và MOSAIC_GRID có được chọn; layout_fallbacks rỗng. Hồ sơ cấu hình concurrency={default: 6, max: 10, min: 1}.
- **Ảnh AI mỗi video**: tổng 323 ảnh, p50 3, min 0, max 6; 94/100 video có ảnh AI. Ảnh bài viết: tổng 114, p50 1, min 0, max 7.
- **Video chỉ có ảnh nền**: 0 (background_only=0, seed_share_max_pct=0,0).
- **Nguồn hook**: audio_hook freesound 100 video, visual_hook pixabay 100 video, hook không thật (not_real) 0.
- **Đa dạng**: 23 hook hình khác nhau, 13 hook âm khác nhau (6 truy vấn âm khác nhau), 13 bản nhạc khác nhau, 0 video không nhạc.
- **Thời lượng video**: p50 63,9 s, min 57,6 s, max 73,0 s, tổng 6437,1 s. Số phân cảnh: p50 6, min 4, max 8, tổng 555.

## Open item

- **OI-CP7-11-Q6**: đã có số đo thật của lô lần 2 (875e2e7d-bf7c-438b-ba59-f64928dbc3eb) trên HEAD đã có QC-HOOK-FIX và STAGING-RETENTION. Kết quả: 11/12 mục RG-10 PASS, 1 mục FAIL (failure_isolated, target_runs=0), warn_80_visible NOT_OBSERVED, CQ.no_background_only PASS, CQ.real_hooks PASS, CQ.layout_cap_40 OVER.
- **RG-10.failure_isolated FAIL**: lô không có lượt thu thập nào của nguồn 404 trong cửa sổ (not_found_status=404, registered=0, existing=0), nên không chứng minh được cô lập lỗi. Lỗi này lặp lại từ lô lần 1; Worker không tự sửa vì thuộc mã sản phẩm hoặc dây chuyền ngoài owned paths. Nguyên nhân gốc chưa có số đo; GIẢ ĐỊNH chưa kiểm: nguồn 404 không được đăng ký vào lịch thu thập của lô.
- **CQ.layout_cap_40 OVER**: HERO_STRIP 41/100 và SPLIT_STACK 40/100; Control quyết.
- **Tiến triển so với lô lần 1**: auto_ratio_95 đạt 100/101 = 99,01% (trước 65,36%), working_set_cap đạt 10,27 GiB (trước 21,46 GiB), không còn lỗi qc; thời gian lô giảm từ 26641 s xuống 16469 s nhưng vẫn cao hơn lô 74e795ef (6849 s), chủ yếu do media_select p50 340,9 s.
- **Đề nghị Control quyết định** (Worker không tự quyết): (1) ghi nhận lô 875e2e7d là số đo thật của OI-CP7-11-Q6; (2) quyết định xử lý RG-10.failure_isolated (mở gói sửa riêng cho việc đăng ký và thu thập nguồn 404 trong lô, hoặc chấp nhận bằng chứng khác); (3) quyết định xử lý CQ.layout_cap_40 OVER; (4) xem xét 1 job FAILED_FINAL ở align/word_coverage_incomplete. Các số đo này là cơ sở để Control, Reviewer (Sonnet 5.5) và Auditor (Opus 5.5) điều chỉnh trước mẫu CP7-14.
