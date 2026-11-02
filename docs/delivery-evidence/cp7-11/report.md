# CP7-11 — Đêm chạy 100 video trong 12 giờ (RG-10)

## Kết luận trung thực

Lượt 3 (lượt chính thức) đã chạy trọn lô thật và pytest kết thúc với `1 failed, 54 passed in 7305.07s (2:01:45)`, exit code 1. Mục `auto_ratio_95` FAIL thật; 12 mục còn lại có dòng kết quả trong log (11 PASS, `warn_80_visible` NOT_OBSERVED).

- `valid_synced_100`: 100 video hợp lệ, 0 không hợp lệ, 6 video đối soát Drive.
- `within_12h`: `t_target_s=7261` (khoảng 2 giờ 1 phút, rất thấp hơn trần 12 giờ); `wait_provider_seconds=1053`.
- `auto_ratio_95`: FAIL. Test assert `valid=100 total=112`: 100 job hoàn thành trên 112 job của lô, tức khoảng 89,3% (dưới ngưỡng 95%). 12 job ở trạng thái `FAILED_FINAL`. Mẫu số là toàn bộ 112 job của lô theo `docs/10-test-strategy.md:686-688` và `docs/11-roadmap.md:600` (không loại lỗi hệ thống khỏi mẫu số); repo không có reason code loại trừ định nghĩa trước nên không loại job nào và không đổi công thức hay ngưỡng. Nguyên nhân 12 job xem mục `## Phân tích job FAILED_FINAL`.
- `failure_isolated`: `target_runs=1`, `target_failed=1`, `others_ok=1`, `completed_after_failure=100` (lọc theo `business_date` đã khắc phục lỗi của lượt 1).
- `resume_300s_midrun`: `ready_seconds=19.0` (stop 1 lần, 6 video đang chạy và 40 video đã xong tại thời điểm dừng).
- Chi phí: `night_usd=0`, `month_usd=0`, 677 lời gọi AI (route_cost_per_request=0 nên ledger bằng 0).
- Working set tối đa 5,87 GiB (trần 20 GiB), disk trống tối thiểu 222,3 GiB, VRAM tối đa 2778 MiB.

Lô chạy với 6 luồng (mặc định 6, tối đa 10); sau 7261 giây đạt 100 video hợp lệ nhưng tổng 112 job vì 12 job lỗi chung cuộc, nên tỉ lệ tự hoàn thành chưa đạt 95%. Lượt này chưa đạt RG-10 vì `auto_ratio_95` FAIL thật, cần Control mở gói sửa nguyên nhân gốc (ngoài owned paths nếu nằm trong `src/**`) rồi cấp lô thật mới.

## Lịch sử các lượt chạy

- Lượt 1 (2026-11-02 08:09:40–09:47:30 giờ Việt Nam, HEAD 7fa09bf): 100/100 video hợp lệ nhưng `failure_isolated` FAIL do `others_ok=0`: mỗi nguồn chỉ thu thập một lượt mỗi ngày giờ Việt Nam nên lọc theo cửa sổ lô không thấy nguồn khác; bằng chứng đã đổi sang lọc theo `business_date` kèm `completed_after_failure`.
- Lượt 2 (bắt đầu 09:59:26+07:00): bị hệ thống dừng khoảng 10:31 vì thiếu bộ nhớ khi chạy trong tác vụ nền, không có dòng RG-10.* nên không tính.
- Lượt 3 (Control cấp thay lượt 2, kết quả chính thức bên dưới): bắt đầu 2026-11-02 12:08:08+07:00 (lô POST lúc 12:08:23), kết thúc khoảng 14:10 +07:00, chạy tách tiến trình, có dòng tổng kết pytest.

## Lệnh đã chạy

- HEAD khi chạy: `8acce40b3acc14d02ae572478f8785375798288e` (hai tệp test và monitor sửa chưa commit tại thời điểm chạy).
- Interpreter khoá: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\8715e538\venv\Scripts\python.exe`.
- RED đã chứng kiến ở lượt Worker trước: `test_unit_collection_isolation` đỏ trước khi sửa, sau đó 41 test_unit đạt.
- `git diff --check`: exit 0 trước khi chạy lô.
- `python -m pytest tests/real/test_cp7_overnight.py -q -p no:cacheprovider -k test_unit`: `41 passed, 14 deselected in 0.32s`, exit 0.
- RAM trống trước khi chạy lô: 11300896 KB (ngưỡng 8388608 KB).
- Cách chạy lô: `Start-Process` tách tiến trình (PID 96952, `PYTEST_DEBUG_TEMPROOT` riêng, `PYTHONUTF8=1`), log ngoài repo; lệnh `python -m pytest tests/real/test_cp7_overnight.py -q -p no:cacheprovider`.
- Exit code lô thật: 1 (do `test_rg10_auto_ratio_95`).
- Dòng tổng kết pytest nguyên văn: `1 failed, 54 passed in 7305.07s (2:01:45)`.
- `AIAVC_DATA_DIR` (biến môi trường User): `D:\AIAVC_DATA`.
- Số luồng (dòng `concurrency=`): `{"default": 6, "max": 10, "min": 1}`.
- Quota Drive (dòng `drive_quota_ok`): `free_gib=5118.78`, `required_gib=1036.00`, `unlimited=False`.
- Lượt chẩn đoán (lượt 3 sau lô, không chạy lô mới, không khởi động launcher/Docker/Temporal, chỉ truy vấn SELECT): sau khi thêm `failure_causes` và `test_diag_failed_jobs_of_batch`, `git diff --check`: exit 0; `python -m pytest tests/real/test_cp7_overnight.py -q -p no:cacheprovider -k test_unit`: `42 passed, 15 deselected in 0.46s`, exit 0.
- Chẩn đoán chỉ đọc lô `71973394` với `CP7_DIAG_BATCH_PREFIX=71973394`: `python -m pytest tests/real/test_cp7_overnight.py -q -p no:cacheprovider -k test_diag -rP`: `1 passed, 56 deselected in 1.01s`, exit 0.

## Kết quả

RG-10.drive_quota_ok: PASS
RG-10.valid_synced_100: PASS
RG-10.within_12h: PASS
RG-10.auto_ratio_95: FAIL
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
- sample t=2026-11-02T05:08:23Z elapsed_s=0 batch=CREATED jobs={} valid=0 running_stages=0 night_usd=0 month_usd=0 ai_calls=0 data_free_gib=234.1 sys_free_gib=52.9 working_set_gib=4.06 vram_mib=500
- sample t=2026-11-02T05:13:23Z elapsed_s=300 batch=RUNNING jobs={"ACTIVE":6} valid=0 running_stages=6 night_usd=0 month_usd=0 ai_calls=36 data_free_gib=231.5 sys_free_gib=53.0 working_set_gib=4.09 vram_mib=488
- sample t=2026-11-02T05:18:24Z elapsed_s=600 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":6,"WAITING":1} valid=6 running_stages=6 night_usd=0 month_usd=0 ai_calls=60 data_free_gib=228.4 sys_free_gib=52.9 working_set_gib=4.19 vram_mib=481
- sample t=2026-11-02T05:23:24Z elapsed_s=900 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":10,"FAILED_FINAL":1,"WAITING":1} valid=10 running_stages=6 night_usd=0 month_usd=0 ai_calls=86 data_free_gib=226.2 sys_free_gib=52.9 working_set_gib=4.26 vram_mib=482
- sample t=2026-11-02T05:28:24Z elapsed_s=1200 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":16,"FAILED_FINAL":1,"SNAPSHOTTED":1} valid=16 running_stages=6 night_usd=0 month_usd=0 ai_calls=115 data_free_gib=224.2 sys_free_gib=52.8 working_set_gib=4.37 vram_mib=483
- sample t=2026-11-02T05:33:24Z elapsed_s=1500 batch=RUNNING jobs={"ACTIVE":4,"COMPLETED":20,"FAILED_FINAL":1,"SNAPSHOTTED":2} valid=20 running_stages=6 night_usd=0 month_usd=0 ai_calls=144 data_free_gib=222.3 sys_free_gib=52.6 working_set_gib=4.45 vram_mib=956
- sample t=2026-11-02T05:38:24Z elapsed_s=1801 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":24,"FAILED_FINAL":1} valid=24 running_stages=6 night_usd=0 month_usd=0 ai_calls=179 data_free_gib=224.6 sys_free_gib=52.5 working_set_gib=4.53 vram_mib=1235
- sample t=2026-11-02T05:43:25Z elapsed_s=2101 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":29,"FAILED_FINAL":2} valid=29 running_stages=6 night_usd=0 month_usd=0 ai_calls=203 data_free_gib=228.0 sys_free_gib=52.5 working_set_gib=4.63 vram_mib=1867
- sample t=2026-11-02T05:48:25Z elapsed_s=2401 batch=RUNNING jobs={"ACTIVE":4,"COMPLETED":32,"FAILED_FINAL":4,"SNAPSHOTTED":2} valid=32 running_stages=6 night_usd=0 month_usd=0 ai_calls=234 data_free_gib=227.9 sys_free_gib=52.5 working_set_gib=4.70 vram_mib=2778
- sample t=2026-11-02T05:53:25Z elapsed_s=2701 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":36,"FAILED_FINAL":4} valid=36 running_stages=6 night_usd=0 month_usd=0 ai_calls=266 data_free_gib=227.8 sys_free_gib=52.5 working_set_gib=4.77 vram_mib=1318
- sample t=2026-11-02T05:58:25Z elapsed_s=3002 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":40,"FAILED_FINAL":4} valid=40 running_stages=6 night_usd=0 month_usd=0 ai_calls=288 data_free_gib=231.8 sys_free_gib=52.7 working_set_gib=4.84 vram_mib=726
- sample t=2026-11-02T06:03:25Z elapsed_s=3302 batch=RUNNING jobs={"ACTIVE":4,"COMPLETED":46,"FAILED_FINAL":4,"SNAPSHOTTED":2} valid=46 running_stages=6 night_usd=0 month_usd=0 ai_calls=317 data_free_gib=231.7 sys_free_gib=52.6 working_set_gib=4.94 vram_mib=834
- sample t=2026-11-02T06:08:26Z elapsed_s=3602 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":47,"FAILED_FINAL":6} valid=47 running_stages=6 night_usd=0 month_usd=0 ai_calls=348 data_free_gib=226.6 sys_free_gib=52.5 working_set_gib=4.97 vram_mib=1157
- sample t=2026-11-02T06:13:26Z elapsed_s=3903 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":51,"FAILED_FINAL":6,"WAITING":1} valid=51 running_stages=6 night_usd=0 month_usd=0 ai_calls=373 data_free_gib=226.5 sys_free_gib=52.5 working_set_gib=5.03 vram_mib=1134
- sample t=2026-11-02T06:18:27Z elapsed_s=4204 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":55,"FAILED_FINAL":8,"WAITING":1} valid=55 running_stages=6 night_usd=0 month_usd=0 ai_calls=397 data_free_gib=232.1 sys_free_gib=52.8 working_set_gib=5.10 vram_mib=731
- sample t=2026-11-02T06:23:28Z elapsed_s=4504 batch=RUNNING jobs={"ACTIVE":3,"COMPLETED":59,"FAILED_FINAL":9,"SNAPSHOTTED":2,"WAITING":1} valid=59 running_stages=6 night_usd=0 month_usd=0 ai_calls=423 data_free_gib=232.0 sys_free_gib=52.6 working_set_gib=5.18 vram_mib=725
- sample t=2026-11-02T06:28:28Z elapsed_s=4804 batch=RUNNING jobs={"ACTIVE":4,"COMPLETED":63,"FAILED_FINAL":9,"SNAPSHOTTED":2} valid=63 running_stages=6 night_usd=0 month_usd=0 ai_calls=451 data_free_gib=230.4 sys_free_gib=52.3 working_set_gib=5.25 vram_mib=716
- sample t=2026-11-02T06:33:28Z elapsed_s=5104 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":67,"FAILED_FINAL":9} valid=67 running_stages=6 night_usd=0 month_usd=0 ai_calls=485 data_free_gib=229.3 sys_free_gib=52.3 working_set_gib=5.31 vram_mib=717
- sample t=2026-11-02T06:38:28Z elapsed_s=5405 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":72,"FAILED_FINAL":9} valid=72 running_stages=6 night_usd=0 month_usd=0 ai_calls=516 data_free_gib=227.2 sys_free_gib=52.2 working_set_gib=5.41 vram_mib=739
- sample t=2026-11-02T06:43:29Z elapsed_s=5705 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":78,"FAILED_FINAL":9} valid=78 running_stages=6 night_usd=0 month_usd=0 ai_calls=545 data_free_gib=227.1 sys_free_gib=52.1 working_set_gib=5.50 vram_mib=713
- sample t=2026-11-02T06:48:29Z elapsed_s=6005 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":83,"FAILED_FINAL":9} valid=83 running_stages=6 night_usd=0 month_usd=0 ai_calls=573 data_free_gib=227.0 sys_free_gib=52.0 working_set_gib=5.58 vram_mib=716
- sample t=2026-11-02T06:53:29Z elapsed_s=6306 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":87,"FAILED_FINAL":11,"SNAPSHOTTED":1} valid=87 running_stages=6 night_usd=0 month_usd=0 ai_calls=603 data_free_gib=226.9 sys_free_gib=52.0 working_set_gib=5.66 vram_mib=711
- sample t=2026-11-02T06:58:29Z elapsed_s=6606 batch=RUNNING jobs={"ACTIVE":3,"COMPLETED":91,"FAILED_FINAL":11,"SNAPSHOTTED":3} valid=91 running_stages=6 night_usd=0 month_usd=0 ai_calls=632 data_free_gib=228.2 sys_free_gib=51.9 working_set_gib=5.73 vram_mib=705
- sample t=2026-11-02T07:03:30Z elapsed_s=6906 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":94,"FAILED_FINAL":12,"SNAPSHOTTED":1} valid=94 running_stages=6 night_usd=0 month_usd=0 ai_calls=665 data_free_gib=228.2 sys_free_gib=51.9 working_set_gib=5.78 vram_mib=1004
- sample t=2026-11-02T07:08:30Z elapsed_s=7206 batch=RUNNING jobs={"ACTIVE":1,"COMPLETED":99,"FAILED_FINAL":12} valid=99 running_stages=1 night_usd=0 month_usd=0 ai_calls=677 data_free_gib=228.2 sys_free_gib=51.9 working_set_gib=5.86 vram_mib=699
- sample t=2026-11-02T07:09:24Z elapsed_s=7260 batch=COMPLETED_TARGET jobs={"COMPLETED":100,"FAILED_FINAL":12} valid=100 running_stages=0 night_usd=0 month_usd=0 ai_calls=677 data_free_gib=228.1 sys_free_gib=51.9 working_set_gib=5.87 vram_mib=705
```

## Số liệu theo stage (G02)

```
- stage_metrics: analyze(snapshot) n=112 p50_s=42.3 p95_s=62.9 max_s=70.1 extra_attempts=0
- stage_metrics: script(script_ai) n=112 p50_s=96.6 p95_s=129.9 max_s=527.3 extra_attempts=0
- stage_metrics: plan(plan) n=112 p50_s=66.0 p95_s=85.5 max_s=506.9 extra_attempts=0
- stage_metrics: media_select(media_select) n=112 p50_s=51.6 p95_s=67.9 max_s=473.5 extra_attempts=0
- stage_metrics: tts(tts) n=110 p50_s=13.6 p95_s=30.9 max_s=38.3 extra_attempts=0
- stage_metrics: align(align) n=104 p50_s=11.4 p95_s=33.6 max_s=39.8 extra_attempts=0
- stage_metrics: process(process) n=100 p50_s=43.4 p95_s=76.7 max_s=140.0 extra_attempts=0
- stage_metrics: render(render) n=100 p50_s=13.1 p95_s=19.6 max_s=29.9 extra_attempts=0
- stage_metrics: qc(qc) n=100 p50_s=3.3 p95_s=5.4 max_s=8.0 extra_attempts=0
- stage_metrics: sync(upload_drive_and_verify) n=100 p50_s=6.7 p95_s=28.8 max_s=53.3 extra_attempts=0
- stage_metrics: complete(completion) n=100 p50_s=0.1 p95_s=0.6 max_s=0.7 extra_attempts=0
- lead_time: p50_s=368.7 p95_s=474.0 videos_per_hour=49.6
```

## Chi phí (G03)

```
- budget: night_usd=0 month_usd=0 drive_bytes=556255820 elapsed_s=7261 deadline_s=44100 stop_reason=target_reached
- cost_under_cap: night_usd=0
- cost_under_cap: month_usd=0
- cost_under_cap: ai_calls=677
- cost_under_cap: drive_bytes=556255820
- cost_under_cap: usd_per_valid_video=0.0000
- cost_under_cap: route_cost_per_request=0 nen ledger co the bang 0
```

## Chi tiết đo

```
- wait_provider_seconds=1053
- concurrency={"default": 6, "max": 10, "min": 1}
- batch: id=71973394 concurrency={"default": 6, "max": 10, "min": 1} other_workflows_running=0 not_found_status=404 not_found_source registered=0 existing=0
- seed: launcher_seed_line=\u0110\xe3 n\u1ea1p b\u1ed9 media seed (idempotent). render_config=render_config=[preset/bold-yellow=PUBLISHED preset/output-profile=PUBLISHED policy/quality=PUBLISHED]
- failure_isolated: target_runs=1
- failure_isolated: target_failed=1
- failure_isolated: others_ok=1
- failure_isolated: completed_after_failure=100
- failure_isolated: failed_final_jobs=12
- failure_isolated: source=b9500b***
- resume_300s_midrun: ready_seconds=19.0
- resume_300s_midrun: stop_attempts=1
- resume_300s_midrun: busy_at_stop=6
- resume_300s_midrun: completed_at_stop=40
- working_set_cap: max_working_set_gib=5.87
- working_set_cap: min_disk_free_gib=222.3
- working_set_cap: max_vram_mib=2778
- working_set_cap: samples=26
- working_set_cap: sample_errors=0
- secret_scan: match_count=0
- secret_scan: khong_doc_Credentials=True
- secret_scan: capability_khong_ghi=True
- valid_synced_100: valid=100
- valid_synced_100: invalid=0
- valid_synced_100: drive_sample=6
- warn_80_visible: peak_month_usd=0
```

## Phân tích job FAILED_FINAL

```
- diag: batch=71973394 jobs=112 failed_final=12
- diag_cause: stage=align code=word_coverage_incomplete activity=CreateWordTiming n=4
- diag_cause: stage=process code=post_assessment_still_transform_required activity=TransformSensitiveImage n=4
- diag_cause: stage=align code=alignment_unmatched_ratio_exceeded activity=CreateWordTiming n=2
- diag_cause: stage=tts code=voice_duration_out_of_range activity=CreateVoiceTrack n=2
- diag_job: job=71973394 stage=tts attempt=1 status=FAILED_FINAL code=voice_duration_out_of_range message=
- diag_job: job=71973394 stage=align attempt=1 status=FAILED_FINAL code=alignment_unmatched_ratio_exceeded message=
- diag_job: job=71973394 stage=align attempt=1 status=FAILED_FINAL code=word_coverage_incomplete message=
- diag_job: job=71973394 stage=align attempt=1 status=FAILED_FINAL code=alignment_unmatched_ratio_exceeded message=
- diag_job: job=71973394 stage=process attempt=1 status=FAILED_FINAL code=post_assessment_still_transform_required message=
- diag_job: job=71973394 stage=process attempt=1 status=FAILED_FINAL code=post_assessment_still_transform_required message=
- diag_job: job=71973394 stage=process attempt=1 status=FAILED_FINAL code=post_assessment_still_transform_required message=
- diag_job: job=71973394 stage=process attempt=1 status=FAILED_FINAL code=post_assessment_still_transform_required message=
- diag_job: job=71973394 stage=tts attempt=1 status=FAILED_FINAL code=voice_duration_out_of_range message=
- diag_job: job=71973394 stage=align attempt=1 status=FAILED_FINAL code=word_coverage_incomplete message=
- diag_job: job=71973394 stage=align attempt=1 status=FAILED_FINAL code=word_coverage_incomplete message=
- diag_job: job=71973394 stage=align attempt=1 status=FAILED_FINAL code=word_coverage_incomplete message=
```

- Tổng 12 job chia thành 4 nhóm: `align`/`word_coverage_incomplete`/`CreateWordTiming` 4 job; `process`/`post_assessment_still_transform_required`/`TransformSensitiveImage` 4 job; `align`/`alignment_unmatched_ratio_exceeded`/`CreateWordTiming` 2 job; `tts`/`voice_duration_out_of_range`/`CreateVoiceTrack` 2 job. Mọi job lỗi ở lần thử thứ 1 và không có message kèm theo.
- Thời điểm: job lỗi đầu tiên xuất hiện ở `elapsed_s=900`, trước lần stop/start (tại stop `completed_at_stop=40`, khoảng `elapsed_s=3000`, đã có 4 job `FAILED_FINAL`); 8 job còn lại xuất hiện sau lần stop/start (từ 4 lên 12 ở `elapsed_s=3602`–`6906`). Lần chẩn đoán này không in thời điểm theo từng nhóm nên báo cáo không gán từng nhóm vào trước hay sau stop.
- Nhận định: cả bốn nhóm là mã lỗi do chính các stage của hệ thống trả về (căn thời gian từ vựng, đánh giá và làm mờ ảnh nhạy cảm, độ dài giọng đọc), không có nhóm nào là thiếu đầu vào; chỉ dựa trên code và activity đã in, báo cáo không suy đoán thêm nguyên nhân gốc trong `src/**`.
- Nếu một nhóm có thể do tài nguyên ngoài (provider AI hoặc TTS, ví dụ nhóm `tts` và `align`) thì đó vẫn là lỗi hệ thống theo quy tắc không loại khỏi mẫu số, nên cả 12 job vẫn tính vào 112.

## Open item

- `auto_ratio_95` FAIL thật (100/112, 89,3%), nguyên nhân theo mục Phân tích; chặn bởi nguyên nhân gốc ngoài owned paths và cần một lô thật mới do Control cấp; không ghi PASS.
- `failure_isolated` đã xử lý ở lượt 3: PASS (`others_ok=1`, `completed_after_failure=100`).
- `warn_80_visible` NOT_OBSERVED vì ledger tháng bằng 0 (dưới 40 USD); không giả lập.
- OI-CP7-06: quota Drive đạt (`free_gib=5118.78` so với `required_gib=1036.00`, `unlimited=False`).
- OI-CP7-11: thời gian lô 7261 giây (khoảng 2 giờ 1 phút) với 6 luồng, thấp hơn nhiều so với 12 giờ; số luồng mặc định 6 và tối đa 10 cần Control đối chiếu với số đo thật.
