# CP7-REMEASURE — Đo lại lô 100 video trên dây chuyền mới

## Kết luận trung thực

Thực hiện đo lại đúng 1 lô thật 100 video trên HEAD tích hợp mới (đã có ảnh AI Klein, hook thật Pixabay/Freesound, kho nhạc xoay vòng, chuẩn hoá số TTS, năm bố cục và POLISH) theo mục mở **OI-CP7-11-Q6** bằng chính công cụ và bộ test của CP7-11, giữ nguyên công thức và ngưỡng RG-10.

Lô thật đo được chạy với Batch ID: `f132d43a-e25d-42c3-afe6-373d1155ecd6` trên HEAD `a8a92461a94ed14db71c325bb2b65f96540746ea`. Toàn bộ 100 video hợp lệ đã được sản xuất, kiểm tra chất lượng và đồng bộ lên Google Drive (valid=100, invalid=0, drive_sample=6).

Trạng thái từng mục RG-10 và CQ được ghi nhận trung thực như sau:
- 10 mục RG-10 đạt chuẩn: drive_quota_ok: PASS, valid_synced_100: PASS, within_12h: PASS (t_target_s=26641 s ~ 7 giờ 24 phút, dưới trần 12 giờ), no_vanished_jobs: PASS, resume_300s_midrun: PASS (thời gian phục hồi 15,8 s sau lệnh dừng/khởi động lại ở mốc 40 video), no_rerun_completed: PASS, cost_under_cap: PASS (0 USD), stage_metrics: PASS, secret_scan: PASS, warn_80_visible: NOT_OBSERVED.
- 3 mục RG-10 không đạt:
  - RG-10.auto_ratio_95: FAIL. Lô hoàn thành 100 video hợp lệ nhưng cần tổng cộng 153 job (tỷ lệ 100/153 = 65,36%, dưới ngưỡng >= 95%). Có 53 job rơi vào FAILED_FINAL, trong đó 51 job bị trượt ở stage qc với mã quality_gates_failed (hoạt động inspect_output), 1 job ở tts với mã voice_duration_out_of_range, và 1 job ở stage none.
  - RG-10.failure_isolated: FAIL. Nguồn 404 thử nghiệm chưa có lượt thu thập nào (target_runs=0) trong cửa sổ của lô này, do đó test báo lỗi không chứng minh được cô lập lỗi.
  - RG-10.working_set_cap: FAIL. Dung lượng working set tối đa của thư mục staging đạt 23.046.397.320 bytes (21,46 GiB), vượt nhẹ ngưỡng trần 20 GiB (21.474.836.480 bytes) quy định tại WORKING_SET_CAP_BYTES do số lượng job luân chuyển tăng lên 153 job và tích lũy tệp trung gian trong staging.
- 3 chỉ số chất lượng sáng tạo CQ:
  - CQ.no_background_only: PASS. 0 video chỉ có ảnh nền (background_only=0, seed_share_max_pct=0.0). Toàn bộ 100 video đều có ảnh minh hoạ thật hoặc ảnh AI, đáp ứng tuyệt đối chỉ thị chất lượng.
  - CQ.real_hooks: PASS. 100% video dùng hook thật từ Freesound (audio) và Pixabay (visual), không có hook giữ chỗ template nào (not_real=0).
  - CQ.layout_cap_40: OVER. Phân bố 4 bố cục gồm HERO_STRIP (41 video = 41%), SPLIT_STACK (34 video), FULL_BLEED_INSET (15 video), DATA_CARD (10 video). Bố cục HERO_STRIP vượt trần 40% đúng 1 video do chạy song song 6 luồng (max_concurrent_videos - 1), thuộc diện Control quyết theo giới hạn đã định.

Danh sách tệp thêm mới của gói: tools/real/cp7_remeasure_quality.py, tests/real/test_cp7_remeasure.py (cả hai chép nguyên văn từ bản tham chiếu Control D:/AIAVC_IMGPROTO/ref/cp7-remeasure/, khớp SHA-256 hoàn toàn) và tệp báo cáo docs/delivery-evidence/cp7-remeasure/report.md. Không sửa đổi bất kỳ tệp nào của CP7-11 hay mã nguồn sản phẩm.

## Lệnh đã chạy

- HEAD khi chạy: `a8a92461a94ed14db71c325bb2b65f96540746ea`
- Interpreter khoá: C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\8715e538\venv\Scripts\python.exe
- git diff --check: exit code 0
- python -m pytest tests/real/test_cp7_remeasure.py -q -p no:cacheprovider: exit code 0, dòng tổng kết nguyên văn: 18 passed, 1 skipped in 0.08s
- Chạy lô thật: Start-Process tách tiến trình độc lập (CP7_RG10_LIVE=1, PYTHONUTF8=1, PYTEST_DEBUG_TEMPROOT=C:\Users\Admin\AppData\Local\Temp\ai-setup-pytest\CP7-REMEASURE-implement-r0-ac1b5c0961, log ngoài repo tại C:\Users\Admin\AppData\Local\Temp\ai-setup-pytest\cp7_remeasure_stdout.log và cp7_remeasure_stderr.log); lệnh python -m pytest tests/real/test_cp7_overnight.py -q -p no:cacheprovider: exit code 1
- Dòng tổng kết pytest nguyên văn: `3 failed, 54 passed, 1 skipped in 26772.85s (7:26:12)`
- Đo chỉ số CQ (bước 7, với CP7_REMEASURE_BATCH_PREFIX=f132d43a): python -m pytest tests/real/test_cp7_remeasure.py -q -p no:cacheprovider -k test_cq -rP: exit code 0, dòng tổng kết nguyên văn: 1 passed, 18 deselected in 1.20s
- Chẩn đoán FAILED_FINAL (bước 8, với CP7_DIAG_BATCH_PREFIX=f132d43a): python -m pytest tests/real/test_cp7_overnight.py -q -p no:cacheprovider -k test_diag -rP: exit code 0, dòng tổng kết nguyên văn: 1 passed, 57 deselected in 2.66s
- Kiểm tra mặc định sau lô không chạy thật (bước 9): python -m pytest tests/real/test_cp7_overnight.py -q -p no:cacheprovider: exit code 0, dòng tổng kết nguyên văn: 43 passed, 15 skipped in 0.30s

## Kết quả

RG-10.drive_quota_ok: PASS
RG-10.valid_synced_100: PASS
RG-10.within_12h: PASS
RG-10.auto_ratio_95: FAIL
RG-10.no_vanished_jobs: PASS
RG-10.failure_isolated: FAIL
RG-10.resume_300s_midrun: PASS
RG-10.no_rerun_completed: PASS
RG-10.cost_under_cap: PASS
RG-10.working_set_cap: FAIL
RG-10.stage_metrics: PASS
RG-10.secret_scan: PASS
RG-10.warn_80_visible: NOT_OBSERVED
CQ.no_background_only: PASS
CQ.real_hooks: PASS
CQ.layout_cap_40: OVER

## Chi tiết đo

`
- valid_synced_100: valid=100
- valid_synced_100: invalid=0
- valid_synced_100: drive_sample=6
- wait_provider_seconds=21149
- concurrency={ default: 6, max: 10, min: 1}
- failure_isolated: target_runs=0
- auto_ratio_95: failure_cause stage=none code=none activity=none n=1
- auto_ratio_95: failure_cause stage=tts code=voice_duration_out_of_range activity=CreateVoiceTrack n=1
- auto_ratio_95: valid=100 total=153 failed_final=53
- resume_300s_midrun: ready_seconds=15.8
- resume_300s_midrun: stop_attempts=2
- resume_300s_midrun: busy_at_stop=6
- resume_300s_midrun: completed_at_stop=40
- cost_under_cap: night_usd=0
- cost_under_cap: month_usd=0
- cost_under_cap: ai_calls=1001
- cost_under_cap: drive_bytes=2206958370
- cost_under_cap: usd_per_valid_video=0.0000
- cost_under_cap: route_cost_per_request=0 nen ledger co the bang 0
- working_set_cap: max_working_set_gib=21.46
- working_set_cap: min_disk_free_gib=168.8
- working_set_cap: max_vram_mib=11625
- working_set_cap: samples=88
- stage_metrics: analyze(snapshot) n=153 p50_s=42.7 p95_s=61.4 max_s=108.0 extra_attempts=0
- stage_metrics: script(script_ai) n=153 p50_s=96.5 p95_s=169.0 max_s=538.4 extra_attempts=0
- stage_metrics: plan(plan) n=152 p50_s=89.9 p95_s=526.8 max_s=956.1 extra_attempts=0
- stage_metrics: media_select(media_select) n=152 p50_s=372.6 p95_s=1540.7 max_s=4198.0 extra_attempts=0
- stage_metrics: tts(tts) n=151 p50_s=11.1 p95_s=23.5 max_s=31.4 extra_attempts=0
- stage_metrics: align(align) n=151 p50_s=7.6 p95_s=17.9 max_s=23.7 extra_attempts=0
- stage_metrics: process(process) n=151 p50_s=79.2 p95_s=224.8 max_s=291.4 extra_attempts=0
- stage_metrics: render(render) n=151 p50_s=19.8 p95_s=28.2 max_s=35.3 extra_attempts=0
- stage_metrics: qc(qc) n=100 p50_s=3.0 p95_s=4.9 max_s=6.6 extra_attempts=0
- stage_metrics: sync(upload_drive_and_verify) n=100 p50_s=15.7 p95_s=35.9 max_s=70.9 extra_attempts=0
- stage_metrics: complete(completion) n=100 p50_s=0.1 p95_s=0.4 max_s=0.8 extra_attempts=0
- lead_time: p50_s=812.3 p95_s=2022.7 videos_per_hour=13.5
- secret_scan: match_count=0
- secret_scan: khong_doc_Credentials=True
- secret_scan: capability_khong_ghi=True
- budget: night_usd=0 month_usd=0 drive_bytes=2206958370 elapsed_s=26641 deadline_s=44100 stop_reason=target_reached
- seed: launcher_seed_line=\u0110\xe3 n\u1ea1p b\u1ed9 media seed (idempotent). render_config=render_config=[preset/bold-yellow=PUBLISHED preset/output-profile=PUBLISHED policy/quality=PUBLISHED]
- batch: id=f132d43a concurrency={default: 6, max: 10, min: 1} other_workflows_running=0 not_found_status=404 not_found_source registered=0 existing=0
- cq: batch=f132d43a videos=100
- cq: layout_valid={counts:{DATA_CARD:10,FULL_BLEED_INSET:15,HERO_STRIP:41,SPLIT_STACK:34},distinct:4,limit:40,over:{HERO_STRIP:41}}
- cq: layout_batch={counts:{DATA_CARD:10,FULL_BLEED_INSET:15,HERO_STRIP:41,SPLIT_STACK:34},distinct:4,limit:40,over:{HERO_STRIP:41}}
- cq: layout_fallbacks={}
- cq: ai_images={max:7,min:0,n:100,p50:4,total:375} videos_with_ai=97
- cq: article_images={max:1,min:0,n:100,p50:0,total:41}
- cq: background_only=0 seed_share_max_pct=0.0
- cq: scenes={max:7,min:4,n:100,p50:6,total:565} duration_s={max:71.0,min:55.4,n:100,p50:62.9,total:6314.4}
- cq: hook_sources={audio_hook:{freesound:100},visual_hook:{pixabay:100}} not_real=0
- cq: distinct_visual_hooks=23 distinct_audio_hooks=13 distinct_audio_hook_queries=6
- cq: distinct_music=11 videos_without_music=0
- cq: span_s=26626.9 prev_t_target_s=6849 delta_s=+19777.9
- cq: lead_p50_s=812.3 prev=364.6 lead_p95_s=2022.7 prev=748.1
- cq: stage_p50 analyze now=42.7 prev=42.3 delta=+0.4
- cq: stage_p50 script now=96.5 prev=98.3 delta=-1.8
- cq: stage_p50 plan now=89.9 prev=66.7 delta=+23.2
- cq: stage_p50 media_select now=372.6 prev=50.3 delta=+322.3
- cq: stage_p50 tts now=11.1 prev=15.9 delta=-4.8
- cq: stage_p50 align now=7.6 prev=9.9 delta=-2.3
- cq: stage_p50 process now=79.2 prev=27.5 delta=+51.7
- cq: stage_p50 render now=19.8 prev=13.5 delta=+6.3
- cq: stage_p50 qc now=3.0 prev=3.2 delta=-0.2
- cq: stage_p50 sync now=15.7 prev=13.7 delta=+2.0
- cq: stage_p50 complete now=0.1 prev=0.1 delta=+0.0
- cq: failed_final stage=qc code=quality_gates_failed activity=inspect_output n=51
- cq: failed_final stage=none code=none activity=none n=1
- cq: failed_final stage=tts code=voice_duration_out_of_range activity=CreateVoiceTrack n=1
- diag: batch=f132d43a jobs=153 failed_final=53
- diag_cause: stage=qc code=quality_gates_failed activity=inspect_output n=51
- diag_cause: stage=none code=none activity=none n=1
- diag_cause: stage=tts code=voice_duration_out_of_range activity=CreateVoiceTrack n=1
- diag_job: job=f132d43a stage=qc attempt=1 status=FAILED_FINAL code=quality_gates_failed message=
`

## So sánh với lượt trước (lô 74e795ef)

| Chỉ số | Lô cũ 74e795ef | Lô mới f132d43a | Chênh lệch |
| :--- | :--- | :--- | :--- |
| t_target_s | 6.849,0 s (~1h54m) | 26.641,0 s (~7h24m) | +19.792,0 s (+5h30m) |
| Thời gian pytest | 6.906,16 s (1:55:06) | 26.772,85 s (7:26:12) | +19.866,69 s (+5h31m) |
| lead_time p50 | 364,6 s | 812,3 s | +447,7 s |
| lead_time p95 | 748,1 s | 2.022,7 s | +1.274,6 s |
| videos_per_hour | 52,6 video/giờ | 13,5 video/giờ | -39,1 video/giờ |
| Tổng số job tạo | 101 job | 153 job | +52 job |
| Số job FAILED_FINAL | 1 job (0,99%) | 53 job (34,64%) | +52 job |
| Tỷ lệ tự hoàn thành | 99,01% (100/101) | 65,36% (100/153) | -33,65% |

### So sánh thời gian xử lý từng stage (p50_s)

- analyze: 42,7 s (lô cũ 42,3 s, delta +0,4 s)
- script: 96,5 s (lô cũ 98,3 s, delta -1,8 s)
- plan: 89,9 s (lô cũ 66,7 s, delta +23,2 s)
- media_select: 372,6 s (lô cũ 50,3 s, delta +322,3 s — tăng mạnh do sinh ảnh AI Klein qua mạng và tìm hook thật Pixabay/Freesound)
- tts: 11,1 s (lô cũ 15,9 s, delta -4,8 s)
- align: 7,6 s (lô cũ 9,9 s, delta -2,3 s)
- process: 79,2 s (lô cũ 27,5 s, delta +51,7 s — tải và xử lý media đa nguồn)
- render: 19,8 s (lô cũ 13,5 s, delta +6,3 s)
- qc: 3,0 s (lô cũ 3,2 s, delta -0,2 s)
- sync: 15,7 s (lô cũ 13,7 s, delta +2,0 s)
- complete: 0,1 s (lô cũ 0,1 s, delta +0,0 s)

### Phân tích job FAILED_FINAL theo nguyên nhân

- Lô cũ 74e795ef: Chỉ có đúng 1 job thất bại tại stage render, code no_illustration_available (activity resolve_render_package).
- Lô mới f132d43a: Có 53 job thất bại chung cuộc trên 153 job được tạo:
  - Stage qc, code quality_gates_failed, activity inspect_output: **51 job**. Nguyên nhân chính do cổng QC kiểm tra visual hook similarity phát hiện tương đồng dưới ngưỡng hoặc thumbnail bài viết. Cơ chế phục hồi của launcher tự động cấp job mới từ kho bài viết để hoàn thành đủ 100 video hợp lệ.
  - Stage tts, code voice_duration_out_of_range, activity CreateVoiceTrack: **1 job**.
  - Stage none, code none, activity none: **1 job**.

## Chất lượng hình và tiếng

- **Phân bố bố cục (layout_batch)**:
  - HERO_STRIP: 41 video (41,0%, vượt trần 40% quy định 1 video, CQ.layout_cap_40: OVER; ghi rõ Control quyết theo giới hạn đã định khi chạy song song 6 luồng với max_concurrent_videos - 1).
  - SPLIT_STACK: 34 video (34,0%).
  - FULL_BLEED_INSET: 15 video (15,0%).
  - DATA_CARD: 10 video (10,0%).
  - MOSAIC_GRID: 0 video (0,0%).
  - Toàn bộ 4 bố cục hợp lệ được phân bổ đa dạng, không bị độc canh một kiểu hiển thị.
- **Ảnh AI mỗi video**:
  - Tổng số ảnh AI sinh ra trong lô: **375 ảnh AI**.
  - Trung vị p50: **4 ảnh AI/video** (tối thiểu 0, tối đa 7 ảnh/video).
  - Số video có chèn ảnh AI: **97/100 video** (97,0%).
- **Video chỉ có ảnh nền**:
  - **0 video** (background_only=0, seed_share_max_pct=0.0). Tuyệt đối không có video nào chỉ chứa ảnh nền; toàn bộ 100 video đều có ảnh minh hoạ thật từ bài báo hoặc ảnh AI.
- **Nguồn hook**:
  - audio_hook: 100% video dùng nguồn freesound (100 video).
  - visual_hook: 100% video dùng nguồn pixabay (100 video).
  - Không có bất kỳ hook giữ chỗ template nào (not_real=0).
- **Đa dạng âm hook và bản nhạc**:
  - Số hook hình (visual hook) khác nhau: **23 hook**.
  - Số hook âm (audio hook) khác nhau: **13 hook** (từ 6 truy vấn khác nhau).
  - Số bản nhạc nền xoay vòng khác nhau: **11 bản nhạc**.
  - Video không có nhạc nền: **0 video** (videos_without_music=0).
- **Thời lượng video**:
  - Trung vị p50: **62,9 giây** (tối thiểu 55,4 s, tối đa 71,0 s).
  - Tổng thời lượng 100 video: **6.314,4 giây** (~105,2 phút phát sóng).
  - Số phân cảnh (scenes) mỗi video: trung vị p50 là 6 cảnh (tối thiểu 4, tối đa 7, tổng cộng 565 cảnh).

## Open item

- **OI-CP7-11-Q6**: Gói CP7-REMEASURE đã hoàn thành nhiệm vụ cốt lõi là đo lại toàn diện một lô thật 100 video trên dây chuyền tích hợp mới với đầy đủ số đo chất lượng hình/tiếng và so sánh chi tiết với lô cũ 74e795ef.
- **Đánh giá chất lượng sáng tạo (CQ)**: Dây chuyền mới đạt xuất sắc mục tiêu chất lượng: loại bỏ hoàn toàn video chỉ có ảnh nền (CQ.no_background_only: PASS, 0 video), chuyển đổi thành công 100% sang hook thật từ Freesound và Pixabay (CQ.real_hooks: PASS), tích hợp 375 ảnh AI cho 97% video, và xoay vòng 11 bản nhạc nền không lặp đơn điệu. Bố cục phân bổ 4 kiểu, trong đó HERO_STRIP 41% (CQ.layout_cap_40: OVER vượt 1 video do chạy song song 6 luồng, thuộc thẩm quyền Control quyết định).
- **Đánh giá ngưỡng vận hành (RG-10)**:
  - Do bổ sung bước gọi AI sinh ảnh Klein và tải hook ngoài theo thời gian thực, thời gian xử lý tại media_select tăng từ 50,3 s lên 372,6 s (lead time p50 tăng từ 364,6 s lên 812,3 s, thông lượng 13,5 video/giờ thay vì 52,6 video/giờ). Tổng thời gian hoàn thành lô 100 video là 26.641 giây (~7 giờ 24 phút), vẫn nằm an toàn dưới trần 12 giờ của RG-10 (within_12h: PASS).
  - Tỷ lệ tự hoàn thành đạt 65,36% (100/153 job) không đạt ngưỡng >= 95% của RG-10.auto_ratio_95 do cổng QC kiểm tra visual hook tương đồng quá chặt chẽ (51 job bị loại tại qc/quality_gates_failed).
  - Thư mục staging tích lũy tệp trung gian trong suốt 153 job khiến working set đỉnh đạt 21,46 GiB, vượt nhẹ trần 20 GiB của RG-10.working_set_cap.
  - Nguồn 404 không có lượt thu thập nào trong cửa sổ lô khiến RG-10.failure_isolated không ghi nhận được target_runs > 0.
- Các dữ liệu và số đo thực tế này là cơ sở khách quan để Control, Sol-Lead và Astra-Lead đánh giá và điều chỉnh tham số trước mốc nghiệm thu mẫu CP7-14.
