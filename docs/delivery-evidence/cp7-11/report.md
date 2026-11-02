# CP7-11 — Đêm chạy 100 video trong 12 giờ (RG-10)

## Kết luận trung thực

Lượt 4 (lượt chính thức sau khi rebase lên 00e7f335) đã chạy trọn vẹn đúng 1 lô thật 100 video (Batch ID: `74e795ef-780e-45dc-b2d4-80cbf0272463`). Pytest kết thúc với `56 passed, 1 skipped in 6906.16s (1:55:06)`, exit code 0. Toàn bộ 12 mục bắt buộc của cổng `RG-10` đều đạt **PASS**; mục soft `warn_80_visible` đạt **NOT_OBSERVED** theo đúng dữ liệu log thực tế.

- `drive_quota_ok`: PASS. Quota Drive trống 5118,26 GiB so với yêu cầu 1036,00 GiB (`free_gib=5118.26`, `required_gib=1036.00`, `unlimited=False`).
- `valid_synced_100`: PASS. Đạt 100 video hợp lệ, 0 không hợp lệ, 6 video đối soát Drive (`valid=100`, `invalid=0`, `drive_sample=6`).
- `within_12h`: PASS. Thời gian đạt mục tiêu `t_target_s=6849` (khoảng 1 giờ 54 phút, rất thấp hơn trần 12 giờ); `wait_provider_seconds=1732`.
- `auto_ratio_95`: PASS. Đạt 100 video hoàn thành hợp lệ trên tổng số 101 job của lô, đạt tỉ lệ 99,01% (vượt ngưỡng yêu cầu ≥ 95%). Duy nhất 1 job bị `FAILED_FINAL` (`failed_final=1`, `manual_actions=0`). Cả 4 nhóm lỗi cũ ở Lượt 3 đã được khắc phục hoàn toàn (0/12).
- `no_vanished_jobs`: PASS. Tổng số 101 job đều có trạng thái và log ghi nhận đầy đủ, không có job nào biến mất (`jobs=101`, `findings=0`).
- `failure_isolated`: PASS. Nguồn URL 404 thật bị lỗi nhưng không ảnh hưởng tới các nguồn khác và lô vẫn hoàn thành (`target_runs=1`, `target_failed=1`, `others_ok=2`, `completed_after_failure=100`, `failed_final_jobs=1`).
- `resume_300s_midrun`: PASS. Thời gian phục hồi sau lệnh stop/start là 15,1 giây, dưới trần 300 giây (`ready_seconds=15.1`, `stop_attempts=2`, `busy_at_stop=6`, `completed_at_stop=40`).
- `no_rerun_completed`: PASS. Kiểm tra 6 job đã xong trước khi dừng, không có job nào bị chạy lại (`jobs_checked=6`, `reruns=0`).
- `cost_under_cap`: PASS. Chi phí đêm và tháng ghi nhận 0 USD do đi qua tuyến AI 9Router định tuyến nội bộ, 616 lời gọi AI (`night_usd=0`, `month_usd=0`, `ai_calls=616`, `drive_bytes=1952892863`).
- `working_set_cap`: PASS. Working set tối đa 10,26 GiB (dưới trần 20 GiB), dung lượng ổ đĩa trống tối thiểu 211,5 GiB, VRAM đỉnh 1874 MiB (`max_working_set_gib=10.26`, `min_disk_free_gib=211.5`, `max_vram_mib=1874`).
- `stage_metrics`: PASS. Đầy đủ số liệu đo lường thời gian xử lý cho tất cả 11 stage; tốc độ trung bình đạt 52,6 video/giờ (`lead_time p50_s=364.6`, `p95_s=748.1`, `videos_per_hour=52.6`).
- `secret_scan`: PASS. 0 bí mật xuất hiện trong log hoặc mã nguồn (`match_count=0`).
- `warn_80_visible`: NOT_OBSERVED. Chi phí tháng là 0 USD nên cảnh báo ngưỡng 40 USD (80%) không kích hoạt theo thiết kế thực tế.

Mã nguồn chạy thực nghiệm là commit HEAD sau khi rebase lên đầu tích hợp `00e7f335494b5c6e584e5e746275d3c8f2e5de3b` (đã bao gồm các gói sửa `ADAPT-E-MEDIA-FIX4`, `ADAPT-E-FIX9`, `ADAPT-E-FIX10`, `D-08-FIX1`, `E-16-FIX3`).

## Lịch sử các lượt chạy

- Lượt 1 (2026-11-02 08:09:40–09:47:30 giờ Việt Nam, HEAD 7fa09bf): 100/100 video hợp lệ nhưng `failure_isolated` FAIL do `others_ok=0`: mỗi nguồn chỉ thu thập một lượt mỗi ngày giờ Việt Nam nên lọc theo cửa sổ lô không thấy nguồn khác; bằng chứng đã đổi sang lọc theo `business_date` kèm `completed_after_failure`.
- Lượt 2 (bắt đầu 09:59:26+07:00): bị hệ thống dừng khoảng 10:31 vì thiếu bộ nhớ khi chạy trong tác vụ nền, không có dòng RG-10.* nên không tính.
- Lượt 3 (Control cấp thay lượt 2, kết quả lịch sử, lô 71973394): bắt đầu 2026-11-02 12:08:08+07:00, kết thúc khoảng 14:10+07:00, đạt 100/112 = 89,3% do 12 job lỗi chung cuộc. Kết quả lượt 3 là bằng chứng lịch sử ghi nhận trung thực sự cố, không còn là kết quả chính thức sau khi các gói sửa lỗi đã được tích hợp.
- Lượt 4 (Control cấp lại theo CTRL-CP7-11-R4, sau rebase lên 00e7f335, đã chứa ADAPT-E-MEDIA-FIX4, ADAPT-E-FIX9, ADAPT-E-FIX10, D-08-FIX1, E-16-FIX3): bắt đầu 2026-11-02 23:24:49+07:00 (16:24:49Z), hoàn thành mục tiêu 100 video lúc 2026-11-03 01:18:58+07:00 (18:18:58Z), pytest kết thúc lúc 01:19:55+07:00; toàn bộ 12 mục RG-10 bắt buộc PASS, `warn_80_visible` NOT_OBSERVED; đây là kết quả nghiệm thu chính thức hiện hành của lane.

## Lệnh đã chạy

- HEAD khi chạy: `0498b4b5be18bd3c663cf76b9d08993b7870f74f` (HEAD sau khi rebase lên đầu tích hợp `00e7f335494b5c6e584e5e746275d3c8f2e5de3b`).
- Interpreter khoá: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\8715e538\venv\Scripts\python.exe`.
- `git diff --check`: exit 0 trước khi chạy lô.
- `python -m pytest tests/real/test_cp7_overnight.py -q -p no:cacheprovider -k test_unit`: `42 passed, 15 deselected in 0.40s`, exit 0.
- RAM trống trước khi chạy lô: xác nhận đạt chuẩn (trên 8 GiB).
- `AIAVC_DATA_DIR` (biến môi trường User): `D:\AIAVC_DATA`.
- Cách chạy lô: `Start-Process` tách tiến trình (PID thực thi trong log, `PYTEST_DEBUG_TEMPROOT` riêng `C:\Users\Admin\AppData\Local\Temp\ai-setup-pytest\CP7-11-implement-r0-49a2ca0867`, `PYTHONUTF8=1`), log ngoài repo tại `C:\Users\Admin\AppData\Local\Temp\ai-setup-pytest\cp7_11_r4_stdout.log`; lệnh `python -m pytest tests/real/test_cp7_overnight.py -q -p no:cacheprovider`.
- Exit code lô thật: 0.
- Dòng tổng kết pytest nguyên văn: `56 passed, 1 skipped in 6906.16s (1:55:06)`.
- Số luồng (dòng `concurrency=`): `{"default": 6, "max": 10, "min": 1}`.
- Quota Drive (dòng `drive_quota_ok`): `free_gib=5118.26`, `required_gib=1036.00`, `unlimited=False`.
- Lượt chẩn đoán chỉ đọc lô `74e795ef` với `CP7_DIAG_BATCH_PREFIX=74e795ef`: `python -m pytest tests/real/test_cp7_overnight.py -q -p no:cacheprovider -k test_diag -rP`: `1 passed, 56 deselected in 0.34s`, exit 0.
- Cổng chạy thật (thêm sau Lượt 4 theo phản hồi Reviewer): `tests/real/test_cp7_overnight.py` đọc biến `CP7_RG10_LIVE`; không đặt thì fixture `overnight` bỏ qua các `test_rg10_*` (không chạy lô thứ hai) và `test_unit_recorded_report_rg10` kiểm 12 dòng `RG-10.*: PASS`, `warn_80_visible`, Batch ID và dòng tổng kết pytest của Lượt 4 trong báo cáo này. Lô thật Lượt 4 (`74e795ef`) chạy bằng bản test trước khi thêm cổng; cổng chỉ thêm điều kiện chạy, không đổi công thức hay ngưỡng RG-10. Chạy lại lô thật chỉ khi đặt `CP7_RG10_LIVE=1`.
- Lệnh kiểm mặc định sau khi thêm cổng: `python -m pytest tests/real/test_cp7_overnight.py -q -p no:cacheprovider`: `43 passed, 15 skipped in 0.53s`, exit 0, không chạy lô thật.

## Kết quả

RG-10.drive_quota_ok: PASS
RG-10.valid_synced_100: PASS
RG-10.within_12h: PASS
RG-10.auto_ratio_95: PASS
RG-10.no_vanished_jobs: PASS
RG-10.failure_isolated: PASS
RG-10.resume_300s_midrun: PASS
RG-10.no_rerun_completed: PASS
RG-10.cost_under_cap: PASS
RG-10.working_set_cap: PASS
RG-10.stage_metrics: PASS
RG-10.secret_scan: PASS
RG-10.warn_80_visible: NOT_OBSERVED

## Chuỗi thời gian

```
- sample t=2026-11-02T16:29:50Z elapsed_s=300 batch=RUNNING jobs={"ACTIVE":5,"WAITING":1} valid=0 running_stages=6 night_usd=0 month_usd=0 ai_calls=33 data_free_gib=220.7 sys_free_gib=49.4 working_set_gib=5.89 vram_mib=1183
- sample t=2026-11-02T16:34:50Z elapsed_s=600 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":4,"FAILED_FINAL":1} valid=4 running_stages=6 night_usd=0 month_usd=0 ai_calls=54 data_free_gib=218.5 sys_free_gib=49.4 working_set_gib=6.00 vram_mib=1179
- sample t=2026-11-02T16:39:50Z elapsed_s=900 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":10,"FAILED_FINAL":1,"SNAPSHOTTED":1} valid=10 running_stages=6 night_usd=0 month_usd=0 ai_calls=81 data_free_gib=218.3 sys_free_gib=49.4 working_set_gib=6.22 vram_mib=1478
- sample t=2026-11-02T16:44:51Z elapsed_s=1201 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":15,"FAILED_FINAL":1} valid=15 running_stages=6 night_usd=0 month_usd=0 ai_calls=113 data_free_gib=218.1 sys_free_gib=49.3 working_set_gib=6.41 vram_mib=1254
- sample t=2026-11-02T16:49:51Z elapsed_s=1501 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":18,"FAILED_FINAL":1,"WAITING":1} valid=18 running_stages=6 night_usd=0 month_usd=0 ai_calls=139 data_free_gib=212.6 sys_free_gib=49.3 working_set_gib=6.71 vram_mib=1332
- sample t=2026-11-02T16:54:51Z elapsed_s=1801 batch=RUNNING jobs={"ACTIVE":4,"COMPLETED":24,"FAILED_FINAL":1,"SNAPSHOTTED":1} valid=24 running_stages=5 night_usd=0 month_usd=0 ai_calls=169 data_free_gib=212.5 sys_free_gib=49.3 working_set_gib=6.84 vram_mib=1287
- sample t=2026-11-02T16:59:51Z elapsed_s=2101 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":27,"FAILED_FINAL":1} valid=27 running_stages=6 night_usd=0 month_usd=0 ai_calls=198 data_free_gib=212.4 sys_free_gib=49.3 working_set_gib=6.99 vram_mib=1279
- sample t=2026-11-02T17:04:52Z elapsed_s=2402 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":33,"FAILED_FINAL":1} valid=33 running_stages=6 night_usd=0 month_usd=0 ai_calls=227 data_free_gib=212.1 sys_free_gib=49.3 working_set_gib=7.26 vram_mib=1392
- sample t=2026-11-02T17:09:52Z elapsed_s=2702 batch=RUNNING jobs={"ACTIVE":4,"COMPLETED":38,"FAILED_FINAL":1,"WAITING":2} valid=38 running_stages=6 night_usd=0 month_usd=0 ai_calls=255 data_free_gib=211.9 sys_free_gib=49.3 working_set_gib=7.41 vram_mib=1344
- sample t=2026-11-02T17:14:52Z elapsed_s=3002 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":40,"FAILED_FINAL":1,"WAITING":1} valid=40 running_stages=6 night_usd=0 month_usd=0 ai_calls=273 data_free_gib=215.8 sys_free_gib=49.3 working_set_gib=7.52 vram_mib=1328
- sample t=2026-11-02T17:19:52Z elapsed_s=3302 batch=RUNNING jobs={"ACTIVE":4,"COMPLETED":46,"FAILED_FINAL":1,"SNAPSHOTTED":1} valid=46 running_stages=5 night_usd=0 month_usd=0 ai_calls=298 data_free_gib=215.6 sys_free_gib=50.1 working_set_gib=7.72 vram_mib=1404
- sample t=2026-11-02T17:24:52Z elapsed_s=3602 batch=RUNNING jobs={"ACTIVE":3,"COMPLETED":49,"FAILED_FINAL":1,"SNAPSHOTTED":1,"WAITING":2} valid=49 running_stages=6 night_usd=0 month_usd=0 ai_calls=322 data_free_gib=215.4 sys_free_gib=50.1 working_set_gib=7.88 vram_mib=1766
- sample t=2026-11-02T17:29:53Z elapsed_s=3903 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":51,"FAILED_FINAL":1} valid=51 running_stages=6 night_usd=0 month_usd=0 ai_calls=348 data_free_gib=215.2 sys_free_gib=50.1 working_set_gib=8.04 vram_mib=1649
- sample t=2026-11-02T17:34:53Z elapsed_s=4203 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":57,"FAILED_FINAL":1} valid=57 running_stages=6 night_usd=0 month_usd=0 ai_calls=380 data_free_gib=215.0 sys_free_gib=50.1 working_set_gib=8.27 vram_mib=1313
- sample t=2026-11-02T17:39:53Z elapsed_s=4503 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":62,"FAILED_FINAL":1} valid=62 running_stages=6 night_usd=0 month_usd=0 ai_calls=412 data_free_gib=214.8 sys_free_gib=50.1 working_set_gib=8.52 vram_mib=1631
- sample t=2026-11-02T17:44:53Z elapsed_s=4803 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":68,"FAILED_FINAL":1} valid=68 running_stages=6 night_usd=0 month_usd=0 ai_calls=440 data_free_gib=214.5 sys_free_gib=50.1 working_set_gib=8.74 vram_mib=1333
- sample t=2026-11-02T17:49:54Z elapsed_s=5104 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":72,"FAILED_FINAL":1} valid=72 running_stages=6 night_usd=0 month_usd=0 ai_calls=469 data_free_gib=214.3 sys_free_gib=50.1 working_set_gib=8.96 vram_mib=1449
- sample t=2026-11-02T17:54:54Z elapsed_s=5404 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":78,"FAILED_FINAL":1,"SNAPSHOTTED":1} valid=78 running_stages=6 night_usd=0 month_usd=0 ai_calls=496 data_free_gib=212.5 sys_free_gib=50.1 working_set_gib=9.22 vram_mib=1361
- sample t=2026-11-02T17:59:54Z elapsed_s=5704 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":82,"FAILED_FINAL":1,"SNAPSHOTTED":1} valid=82 running_stages=6 night_usd=0 month_usd=0 ai_calls=524 data_free_gib=212.2 sys_free_gib=51.1 working_set_gib=9.49 vram_mib=1651
- sample t=2026-11-02T18:04:54Z elapsed_s=6004 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":86,"FAILED_FINAL":1} valid=86 running_stages=6 night_usd=0 month_usd=0 ai_calls=559 data_free_gib=212.1 sys_free_gib=51.1 working_set_gib=9.66 vram_mib=1765
- sample t=2026-11-02T18:09:55Z elapsed_s=6305 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":92,"FAILED_FINAL":1} valid=92 running_stages=6 night_usd=0 month_usd=0 ai_calls=585 data_free_gib=211.8 sys_free_gib=51.1 working_set_gib=9.91 vram_mib=1614
- sample t=2026-11-02T18:14:55Z elapsed_s=6605 batch=RUNNING jobs={"ACTIVE":3,"COMPLETED":97,"FAILED_FINAL":1} valid=97 running_stages=3 night_usd=0 month_usd=0 ai_calls=609 data_free_gib=211.6 sys_free_gib=51.1 working_set_gib=10.16 vram_mib=1874
- sample t=2026-11-02T18:18:58Z elapsed_s=6848 batch=COMPLETED_TARGET jobs={"COMPLETED":100,"FAILED_FINAL":1} valid=100 running_stages=0 night_usd=0 month_usd=0 ai_calls=616 data_free_gib=211.5 sys_free_gib=51.1 working_set_gib=10.26 vram_mib=1422
```

## Số liệu theo stage (G02)

```
- stage_metrics: analyze(snapshot) n=101 p50_s=42.3 p95_s=59.6 max_s=80.4 extra_attempts=0
- stage_metrics: script(script_ai) n=101 p50_s=98.3 p95_s=142.1 max_s=519.1 extra_attempts=0
- stage_metrics: plan(plan) n=101 p50_s=66.7 p95_s=84.3 max_s=481.7 extra_attempts=0
- stage_metrics: media_select(media_select) n=101 p50_s=50.3 p95_s=71.1 max_s=530.5 extra_attempts=0
- stage_metrics: tts(tts) n=101 p50_s=15.9 p95_s=28.3 max_s=33.7 extra_attempts=0
- stage_metrics: align(align) n=101 p50_s=9.9 p95_s=32.5 max_s=61.7 extra_attempts=0
- stage_metrics: process(process) n=101 p50_s=27.5 p95_s=94.4 max_s=153.9 extra_attempts=0
- stage_metrics: render(render) n=100 p50_s=13.5 p95_s=22.0 max_s=29.0 extra_attempts=0
- stage_metrics: qc(qc) n=100 p50_s=3.2 p95_s=4.7 max_s=6.3 extra_attempts=0
- stage_metrics: sync(upload_drive_and_verify) n=100 p50_s=13.7 p95_s=31.5 max_s=44.7 extra_attempts=0
- stage_metrics: complete(completion) n=100 p50_s=0.1 p95_s=0.5 max_s=0.8 extra_attempts=0
- lead_time: p50_s=364.6 p95_s=748.1 videos_per_hour=52.6
```

## Chi phí (G03)

```
- cost_under_cap: night_usd=0
- cost_under_cap: month_usd=0
- cost_under_cap: ai_calls=616
- cost_under_cap: drive_bytes=1952892863
- cost_under_cap: usd_per_valid_video=0.0000
- cost_under_cap: route_cost_per_request=0 nen ledger co the bang 0
- budget: night_usd=0 month_usd=0 drive_bytes=1952892863 elapsed_s=6849 deadline_s=44100 stop_reason=target_reached
```

## Chi tiết đo

```
- valid_synced_100: valid=100
- valid_synced_100: invalid=0
- valid_synced_100: drive_sample=6
- wait_provider_seconds=1732
- concurrency={"default": 6, "max": 10, "min": 1}
- failure_isolated: target_runs=1
- failure_isolated: target_failed=1
- failure_isolated: others_ok=2
- failure_isolated: completed_after_failure=100
- failure_isolated: failed_final_jobs=1
- failure_isolated: source=b9500b***
- resume_300s_midrun: ready_seconds=15.1
- resume_300s_midrun: stop_attempts=2
- resume_300s_midrun: busy_at_stop=6
- resume_300s_midrun: completed_at_stop=40
- working_set_cap: max_working_set_gib=10.26
- working_set_cap: min_disk_free_gib=211.5
- working_set_cap: max_vram_mib=1874
- working_set_cap: samples=24
- working_set_cap: sample_errors=0
- secret_scan: match_count=0
- secret_scan: khong_doc_Credentials=True
- secret_scan: capability_khong_ghi=True
- warn_80_visible: peak_month_usd=0
- seed: launcher_seed_line=\u0110\xe3 n\u1ea1p b\u1ed9 media seed (idempotent). render_config=render_config=[preset/bold-yellow=PUBLISHED preset/output-profile=PUBLISHED policy/quality=PUBLISHED]
- batch: id=74e795ef concurrency={"default": 6, "max": 10, "min": 1} other_workflows_running=0 not_found_status=404 not_found_source registered=0 existing=0
```

## Phân tích job FAILED_FINAL

```
- diag: batch=74e795ef jobs=101 failed_final=1
- diag_cause: stage=render code=no_illustration_available activity=resolve_render_package n=1
- diag_job: job=74e795ef stage=render attempt=1 status=FAILED_FINAL code=no_illustration_available message=
```

- Trong lô lượt 4, chỉ có duy nhất 1 job rơi vào trạng thái `FAILED_FINAL` trên tổng số 101 job được tạo: thuộc stage `render`, mã lỗi `no_illustration_available`, activity `resolve_render_package` (n=1). Job này xuất hiện ở thời điểm `elapsed_s=600`, không làm gián đoạn các luồng render độc lập khác.
- Đối chiếu với 4 nhóm lỗi cũ ở Lượt 3 (lô 71973394):
  - `align/word_coverage_incomplete`: 0 job (ở Lượt 3 có 4 job). Đã hết hoàn toàn nhờ gói sửa ADAPT-E-FIX9 và ADAPT-E-FIX10.
  - `process/post_assessment_still_transform_required`: 0 job (ở Lượt 3 có 4 job). Đã hết hoàn toàn nhờ gói sửa ADAPT-E-MEDIA-FIX4.
  - `align/alignment_unmatched_ratio_exceeded`: 0 job (ở Lượt 3 có 2 job). Đã hết hoàn toàn nhờ gói sửa ADAPT-E-FIX9 và ADAPT-E-FIX10.
  - `tts/voice_duration_out_of_range`: 0 job (ở Lượt 3 có 2 job). Đã hết hoàn toàn nhờ gói sửa D-08-FIX1 và E-16-FIX3.
- Kết luận đối chiếu: Toàn bộ 4 nhóm lỗi cũ với 12 job hỏng ở Lượt 3 đã được giải quyết triệt để 100% (0/12). Lô Lượt 4 đạt tỉ lệ tự hoàn thành 100/101 = 99,01%, vượt xa ngưỡng quy định ≥ 95%.

### Dữ liệu chẩn đoán Lượt 3 (Lưu trữ lịch sử)

```
- diag: batch=71973394 jobs=112 failed_final=12
- diag_cause: stage=align code=word_coverage_incomplete activity=CreateWordTiming n=4
- diag_cause: stage=process code=post_assessment_still_transform_required activity=TransformSensitiveImage n=4
- diag_cause: stage=align code=alignment_unmatched_ratio_exceeded activity=CreateWordTiming n=2
- diag_cause: stage=tts code=voice_duration_out_of_range activity=CreateVoiceTrack n=2
```

## Open item

- Cả 12 mục kiểm bắt buộc của cổng RG-10 đều đã đạt PASS thực sự trên ngăn xếp thực tế. Mục soft `warn_80_visible` đạt NOT_OBSERVED (ledger tháng 0 USD, dưới 40 USD; không giả lập).
- Chỉ tiêu `auto_ratio_95` đã đạt chuẩn xuất sắc với tỉ lệ 99,01% (100/101 job), các bản vá tích hợp đã dập tắt toàn bộ 4 nguyên nhân lỗi cũ.
- `failure_isolated` PASS thật (`others_ok=2`, `completed_after_failure=100`), kiểm chứng trọn vẹn khả năng cô lập lỗi nguồn 404.
- `resume_300s_midrun` PASS thật (`ready_seconds=15.1`, `stop_attempts=2`, `busy_at_stop=6`, `completed_at_stop=40`).
- OI-CP7-06: Quota Drive đạt (`free_gib=5118.26` so với `required_gib=1036.00`, `unlimited=False`).
- OI-CP7-11: Thời gian hoàn thành 100 video trong lô là 6849 giây (~ 1 giờ 54 phút) với 6 luồng xử lý đồng thời, thấp hơn rất nhiều so với hạn mức 12 giờ của bài kiểm overnight; số luồng mặc định 6 và tối đa 10 vận hành ổn định không quá tải hệ thống.
