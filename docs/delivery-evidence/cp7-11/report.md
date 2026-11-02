# CP7-11 — Đêm chạy 100 video trong 12 giờ (RG-10)

## Kết luận trung thực

- Lượt chạy thật duy nhất đã hoàn tất: 100/100 video hợp lệ đã cloud verified (ledger + location VERIFIED + evidence `drive:` + QC hard gate 0 lỗi), 0 video không hợp lệ, 0 job lỗi hệ thống, 6 video được đối soát md5/sha256 với Drive đều khớp.
- Thời gian từ lúc POST lô tới video hợp lệ thứ 100 là 5827 giây (khoảng 1 giờ 37 phút), trong ngưỡng 12 giờ; thời gian chờ nhà cung cấp `wait_provider_seconds=331`, tính vào tổng thời gian.
- Resume giữa lô (stop rồi start đúng một lần, lúc 41 video đã hoàn tất và 6 video đang chạy) sẵn sàng sau 16,1 giây (ngưỡng 300 giây); không stage SUCCEEDED nào bị chạy lại.
- Chi phí: ledger đêm 0 USD, tháng 0 USD (route 9Router có `route_cost_per_request=0`), 606 lời gọi AI, Drive 534327038 byte; working set tối đa 2,32 GiB.
- **Mục không đạt: `RG-10.failure_isolated` là FAIL.** Nguồn 404 thật đã được đăng ký, trả 404 và có đúng 1 lượt thu thập `FAILED_FINAL` (cảnh báo `HTTP_STATUS_REJECTED`), nhưng trong cửa sổ lô không có lượt thu thập nào của nguồn khác (`others_ok=0`), nên theo định nghĩa của test (`target_failed >= 1` và `others_ok >= 1`) chưa chứng minh được cô lập lỗi bằng sổ thu thập. Việc độc lập (100 video của lô) vẫn hoàn tất bình thường, nhưng đó không phải là bằng chứng mà mục này đòi. Không chạy lại lô và không đổi tiêu chí để ép PASS; cần Control quyết định gói sửa.
- Do mục trên FAIL, probe `python -c` cuối của gói không đạt (đúng như kỳ vọng của quy tắc trung thực).

## Lệnh đã chạy

- Bắt đầu pytest: 2026-11-02T01:09:40Z (08:09:40 giờ Việt Nam); POST lô lúc 01:09:56Z; video thứ 100 lúc 02:47:03Z; kết thúc pytest 02:47:30Z (09:47:30 giờ Việt Nam).
- HEAD lúc chạy: `7fa09bf97eddc072af4a038c154148580fdef7d0` (worktree `lane-cp7-11`, nhánh `trungqwe/lane-cp7-11`).
- Interpreter khoá: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\8715e538\venv\Scripts\python.exe`.
- Lệnh: `python -m pytest tests/real/test_cp7_overnight.py -q -p no:cacheprovider` (đúng một lần), exit code 1.
- Dòng tổng kết pytest: `1 failed, 51 passed in 5869.39s (1:37:49)` (38 test_unit_* đạt, 13 test_rg10_* đạt, 1 test_rg10_* đỏ: `test_rg10_failure_isolated`).
- Trước khi chạy thật: `git diff --check` exit 0; 38 test_unit_* xanh (bước 7 và 17); RED hợp lệ ở bước 4 (15 test thuần đỏ do hàm khung trả `None`) và bước 11 (21 test nhóm C đỏ).
- Stop/start đặt giữa lô (khi đạt 40 video hợp lệ và có job đang chạy) theo quyết định của user ngày 31/10/2026, thay cho giờ thứ 6.
- Số luồng mặc định lấy từ `/v1/batch-settings`: `{"default": 6, "max": 10, "min": 1}`; lô `target_completed_videos=100`, `videos_per_news_per_round=2`.
- Ổ chứa dữ liệu: ổ D: (`AIAVC_DATA_DIR` mức User đã được Control dời sang ổ D theo quyết định 01/11/2026; giá trị được truyền nguyên vẹn vào shell chạy lệnh, không đổi cấu hình).
- Ngưỡng quota Drive dùng 12 GiB + 20% limit: trống 5119,81 GiB, cần 1036,00 GiB, `unlimited=False`.
- Chẩn đoán sau lượt chạy (chỉ đọc DB, không chạy lại lô): `cp_collection_runs` từ 01:09Z trở đi chỉ có 1 dòng, của nguồn 404 (`b9500b***`), trạng thái `FAILED_FINAL`, `run_kind=PERIODIC`, cảnh báo `HTTP_STATUS_REJECTED`; `collection_isolation` cho `{'target_runs': 1, 'target_failed': 1, 'others_ok': 0, 'isolated': False}`.

## Kết quả

RG-10.valid_synced_100: PASS
RG-10.within_12h: PASS
RG-10.auto_ratio_95: PASS
RG-10.no_vanished_jobs: PASS
RG-10.failure_isolated: FAIL
RG-10.resume_300s_midrun: PASS
RG-10.no_rerun_completed: PASS
RG-10.cost_under_cap: PASS
RG-10.working_set_cap: PASS
RG-10.drive_quota_ok: PASS
RG-10.stage_metrics: PASS
RG-10.secret_scan: PASS
RG-10.warn_80_visible: NOT_OBSERVED

## Chuỗi thời gian

```
- sample t=2026-11-02T01:14:56Z elapsed_s=300 batch=RUNNING jobs={"ACTIVE":6} valid=0 running_stages=5 night_usd=0 month_usd=0 ai_calls=36 data_free_gib=266.0 sys_free_gib=57.6 working_set_gib=0.68 vram_mib=997
- sample t=2026-11-02T01:19:56Z elapsed_s=600 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":6} valid=6 running_stages=6 night_usd=0 month_usd=0 ai_calls=70 data_free_gib=265.9 sys_free_gib=57.6 working_set_gib=0.77 vram_mib=1008
- sample t=2026-11-02T01:24:57Z elapsed_s=900 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":12} valid=12 running_stages=6 night_usd=0 month_usd=0 ai_calls=91 data_free_gib=265.9 sys_free_gib=57.6 working_set_gib=0.86 vram_mib=1020
- sample t=2026-11-02T01:29:57Z elapsed_s=1201 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":18} valid=18 running_stages=6 night_usd=0 month_usd=0 ai_calls=123 data_free_gib=265.8 sys_free_gib=57.6 working_set_gib=0.95 vram_mib=1019
- sample t=2026-11-02T01:34:57Z elapsed_s=1501 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":24} valid=24 running_stages=6 night_usd=0 month_usd=0 ai_calls=157 data_free_gib=265.7 sys_free_gib=57.5 working_set_gib=1.05 vram_mib=1021
- sample t=2026-11-02T01:39:57Z elapsed_s=1801 batch=RUNNING jobs={"ACTIVE":2,"COMPLETED":30,"SNAPSHOTTED":4} valid=30 running_stages=5 night_usd=0 month_usd=0 ai_calls=190 data_free_gib=265.5 sys_free_gib=57.5 working_set_gib=1.16 vram_mib=1021
- sample t=2026-11-02T01:44:57Z elapsed_s=2101 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":34,"SNAPSHOTTED":1} valid=34 running_stages=6 night_usd=0 month_usd=0 ai_calls=224 data_free_gib=265.5 sys_free_gib=57.5 working_set_gib=1.24 vram_mib=1019
- sample t=2026-11-02T01:49:58Z elapsed_s=2401 batch=RUNNING jobs={"ACTIVE":3,"COMPLETED":41,"SNAPSHOTTED":3} valid=41 running_stages=6 night_usd=0 month_usd=0 ai_calls=259 data_free_gib=265.4 sys_free_gib=57.5 working_set_gib=1.34 vram_mib=1020
- sample t=2026-11-02T01:54:58Z elapsed_s=2702 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":44} valid=44 running_stages=5 night_usd=0 month_usd=0 ai_calls=291 data_free_gib=265.3 sys_free_gib=57.5 working_set_gib=1.40 vram_mib=1329
- sample t=2026-11-02T01:59:58Z elapsed_s=3002 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":49} valid=49 running_stages=6 night_usd=0 month_usd=0 ai_calls=327 data_free_gib=265.2 sys_free_gib=57.5 working_set_gib=1.48 vram_mib=1026
- sample t=2026-11-02T02:04:58Z elapsed_s=3302 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":55} valid=55 running_stages=6 night_usd=0 month_usd=0 ai_calls=354 data_free_gib=265.1 sys_free_gib=57.5 working_set_gib=1.56 vram_mib=1120
- sample t=2026-11-02T02:09:59Z elapsed_s=3602 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":60,"SNAPSHOTTED":1} valid=60 running_stages=6 night_usd=0 month_usd=0 ai_calls=383 data_free_gib=265.0 sys_free_gib=57.5 working_set_gib=1.67 vram_mib=1039
- sample t=2026-11-02T02:14:59Z elapsed_s=3902 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":66,"SNAPSHOTTED":1} valid=66 running_stages=6 night_usd=0 month_usd=0 ai_calls=415 data_free_gib=264.7 sys_free_gib=57.5 working_set_gib=1.75 vram_mib=1008
- sample t=2026-11-02T02:19:59Z elapsed_s=4203 batch=RUNNING jobs={"ACTIVE":6,"COMPLETED":70} valid=70 running_stages=6 night_usd=0 month_usd=0 ai_calls=448 data_free_gib=264.6 sys_free_gib=57.5 working_set_gib=1.84 vram_mib=1357
- sample t=2026-11-02T02:24:59Z elapsed_s=4503 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":76,"SNAPSHOTTED":1} valid=76 running_stages=6 night_usd=0 month_usd=0 ai_calls=480 data_free_gib=264.5 sys_free_gib=57.4 working_set_gib=1.94 vram_mib=1303
- sample t=2026-11-02T02:30:00Z elapsed_s=4803 batch=RUNNING jobs={"ACTIVE":4,"COMPLETED":81,"SNAPSHOTTED":1,"WAITING":1} valid=81 running_stages=6 night_usd=0 month_usd=0 ai_calls=508 data_free_gib=264.5 sys_free_gib=57.3 working_set_gib=2.02 vram_mib=1475
- sample t=2026-11-02T02:35:00Z elapsed_s=5104 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":86,"SNAPSHOTTED":1} valid=86 running_stages=6 night_usd=0 month_usd=0 ai_calls=545 data_free_gib=264.4 sys_free_gib=57.3 working_set_gib=2.10 vram_mib=1123
- sample t=2026-11-02T02:40:00Z elapsed_s=5404 batch=RUNNING jobs={"ACTIVE":5,"COMPLETED":92,"SNAPSHOTTED":1} valid=92 running_stages=6 night_usd=0 month_usd=0 ai_calls=575 data_free_gib=264.3 sys_free_gib=57.3 working_set_gib=2.20 vram_mib=1149
- sample t=2026-11-02T02:45:01Z elapsed_s=5704 batch=RUNNING jobs={"ACTIVE":4,"COMPLETED":96} valid=96 running_stages=4 night_usd=0 month_usd=0 ai_calls=604 data_free_gib=264.2 sys_free_gib=57.3 working_set_gib=2.28 vram_mib=1703
- sample t=2026-11-02T02:47:03Z elapsed_s=5826 batch=COMPLETED_TARGET jobs={"COMPLETED":100} valid=100 running_stages=0 night_usd=0 month_usd=0 ai_calls=606 data_free_gib=264.2 sys_free_gib=57.3 working_set_gib=2.32 vram_mib=1189
```

## Số liệu theo stage (G02)

```
- stage_metrics: analyze(snapshot) n=100 p50_s=38.1 p95_s=53.0 max_s=463.6 extra_attempts=0
- stage_metrics: script(script_ai) n=100 p50_s=89.1 p95_s=124.5 max_s=152.1 extra_attempts=0
- stage_metrics: plan(plan) n=100 p50_s=58.3 p95_s=76.8 max_s=90.8 extra_attempts=0
- stage_metrics: media_select(media_select) n=100 p50_s=45.1 p95_s=58.1 max_s=65.5 extra_attempts=0
- stage_metrics: tts(tts) n=100 p50_s=12.5 p95_s=25.2 max_s=36.5 extra_attempts=0
- stage_metrics: align(align) n=100 p50_s=10.4 p95_s=53.3 max_s=60.2 extra_attempts=0
- stage_metrics: process(process) n=100 p50_s=39.1 p95_s=55.0 max_s=60.4 extra_attempts=0
- stage_metrics: render(render) n=100 p50_s=11.3 p95_s=18.4 max_s=29.1 extra_attempts=0
- stage_metrics: qc(qc) n=100 p50_s=3.0 p95_s=5.0 max_s=5.6 extra_attempts=0
- stage_metrics: sync(upload_drive_and_verify) n=100 p50_s=6.4 p95_s=8.1 max_s=78.0 extra_attempts=0
- stage_metrics: complete(completion) n=100 p50_s=0.1 p95_s=0.7 max_s=1.5 extra_attempts=0
- lead_time: p50_s=335.1 p95_s=378.5 videos_per_hour=61.8
```

## Chi phí (G03)

- night_usd=0
- month_usd=0
- ai_calls=606
- drive_bytes=534327038
- usd_per_valid_video=0.0000
- route_cost_per_request=0 nên ledger có thể bằng 0.

## Chi tiết đo

- wait_provider_seconds=331
- concurrency={"default": 6, "max": 10, "min": 1}
- Nguồn 404: `not_found_status=404` (kiểm trước khi chạy), registered=1, existing=0; lượt thu thập: 1 lượt `FAILED_FINAL` (`HTTP_STATUS_REJECTED`), nguồn khác 0 lượt trong cửa sổ lô.
- other_workflows_running=0 trước khi bắt đầu; stop_reason=target_reached; elapsed_s=5827 (hạn 44100).
- Working set tối đa 2,32 GiB (trần 20 GiB); ổ dữ liệu trống tối thiểu 264,2 GiB; VRAM tối đa 1703 MiB; 21 mẫu, 0 mẫu lỗi.
- drive_sample=6 video đối soát md5 và sha256 với Drive, đều khớp; valid=100, invalid=0, failed_final=0, manual_actions=0.
- Resume: ready_seconds=16.1, stop_attempts=1, busy_at_stop=6, completed_at_stop=41, jobs_checked=6, reruns=0.
- Render config: preset/bold-yellow, preset/output-profile, policy/quality đều PUBLISHED; media seed đã nạp.
- Mã bí mật trong log và timeline: 0 khớp; không đọc Credentials/, không ghi capability.

## Open item

- `RG-10.failure_isolated: FAIL`: sổ thu thập trong cửa sổ lô không có lượt của nguồn khác nên `others_ok=0`; cần Control quyết định gói sửa (ví dụ ép thêm một lượt thu thập nguồn hợp lệ trong lô, hoặc đổi bằng chứng cô lập sang chỉ dấu khác), rồi chạy lại có thẩm quyền. Gói này không tự đổi tiêu chí.
- `RG-10.warn_80_visible: NOT_OBSERVED` vì ledger tháng 0 USD, không chạm ngưỡng cảnh báo 40 USD; không giả lập.
- OI-CP7-06 (quota Drive): đã kiểm, Drive trống 5119,81 GiB so với cần 1036,00 GiB; không còn chặn.
- OI-CP7-11: lô chạy 6 luồng (mặc định của hồ sơ) nên 100 video xong trong khoảng 1 giờ 37 phút, ngắn hơn nhiều so với kịch bản 12 giờ; số liệu stage ở trên dùng cho G02 và chi phí cho G03.
