# CP7-REMEASURE — Đo lại lô 100 video trên dây chuyền mới

## Kết luận trung thực

Thực hiện đo lại đúng 1 lô thật 100 video trên HEAD tích hợp (đã có ảnh AI Klein, hook thật Pixabay/Freesound, kho nhạc xoay vòng, chuẩn hoá số TTS, năm bố cục và POLISH) theo mục mở **OI-CP7-11-Q6**, bằng chính công cụ và bộ test của CP7-11; công thức và ngưỡng RG-10 giữ nguyên.

**Trạng thái nghiệm thu: CHƯA ĐẠT, cần Control quyết định.** Acceptance yêu cầu các mục RG-10 PASS (warn_80_visible PASS hoặc NOT_OBSERVED), nhưng số đo thật có 3 mục RG-10 FAIL (auto_ratio_95, failure_isolated, working_set_cap) và CQ.layout_cap_40 là OVER. Nguyên nhân nằm ở dây chuyền sản phẩm ngoài owned paths của gói nên Worker (Sonnet 5.5) không sửa được; theo ràng buộc không chạy lô thứ hai, báo cáo này ghi nguyên số đo của lô duy nhất để Control quyết.

`Batch ID: f132d43a-e25d-42c3-afe6-373d1155ecd6`

`HEAD khi chạy: a8a92461a94ed14db71c325bb2b65f96540746ea`

Lô đạt 100 video hợp lệ và đã đồng bộ Drive (valid=100, invalid=0, drive_sample=6) nhưng phải tạo 153 job để có 100 video hợp lệ.

Trạng thái từng mục RG-10 và CQ được ghi nhận trung thực như sau:
- 9 mục RG-10 PASS: drive_quota_ok, valid_synced_100, within_12h (t_target_s=26641 s, khoảng 7 giờ 24 phút, dưới trần 12 giờ), no_vanished_jobs, resume_300s_midrun (ready_seconds=15,8 s; dừng rồi khởi động lại ở mốc 40 video hoàn thành), no_rerun_completed, cost_under_cap (0 USD), stage_metrics, secret_scan. 1 mục NOT_OBSERVED: warn_80_visible (acceptance chấp nhận PASS hoặc NOT_OBSERVED). 3 mục FAIL nêu ngay dưới.
- 3 mục RG-10 không đạt:
  - RG-10.auto_ratio_95: FAIL. Cần 153 job để có 100 video hợp lệ (100/153 = 65,36%, dưới ngưỡng 95%); 53 job FAILED_FINAL: 51 job ở stage qc, code quality_gates_failed (activity inspect_output); 1 job ở stage tts, code voice_duration_out_of_range (activity CreateVoiceTrack); 1 job không rõ stage (stage=none). Lý do cụ thể cổng QC nào không đạt chưa được số đo ghi lại (dòng diag_job có message rỗng); báo cáo không suy đoán, Control cần điều tra.
  - RG-10.failure_isolated: FAIL. target_runs=0: nguồn 404 thử nghiệm không có lượt thu thập nào trong cửa sổ của lô này (batch ghi not_found_source registered=0 existing=0) nên test không chứng minh được cô lập lỗi.
  - RG-10.working_set_cap: FAIL. max_working_set_gib=21,46 (23.046.397.320 bytes) vượt trần 20 GiB (21.474.836.480 bytes) của WORKING_SET_CAP_BYTES. Nguyên nhân chưa được số đo chứng minh; GIẢ ĐỊNH chưa kiểm: nhiều job (153) để lại tệp trung gian trong staging.
- 3 chỉ số chất lượng sáng tạo CQ:
  - CQ.no_background_only: PASS. 0 video chỉ có ảnh nền (background_only=0, seed_share_max_pct=0.0). Toàn bộ 100 video đều có ảnh minh hoạ thật hoặc ảnh AI, đáp ứng tuyệt đối chỉ thị chất lượng.
  - CQ.real_hooks: PASS. 100% video dùng hook thật từ Freesound (audio) và Pixabay (visual), không có hook giữ chỗ template nào (not_real=0).
  - CQ.layout_cap_40: OVER. Phân bố 4 bố cục gồm HERO_STRIP (41 video = 41%), SPLIT_STACK (34 video), FULL_BLEED_INSET (15 video), DATA_CARD (10 video). HERO_STRIP đạt 41/100 video, vượt trần 40% một video. Acceptance cho phép trần có thể vượt tối đa max_concurrent_videos - 1 khi chạy song song (hồ sơ cấu hình in ở dòng concurrency={default: 6, max: 10, min: 1} của mục Chi tiết đo, nên trần có thể vượt tối đa 5 video; mức vượt 1 video của HERO_STRIP nằm trong giới hạn đó) và quy định kết quả là OVER chứ không FAIL; Control quyết.

Danh sách tệp thêm mới của gói: tools/real/cp7_remeasure_quality.py, tests/real/test_cp7_remeasure.py (cả hai chép nguyên văn từ bản tham chiếu Control D:/AIAVC_IMGPROTO/ref/cp7-remeasure/, khớp SHA-256 hoàn toàn) và tệp báo cáo docs/delivery-evidence/cp7-remeasure/report.md. Không sửa đổi bất kỳ tệp nào của CP7-11 hay mã nguồn sản phẩm.

## Lệnh đã chạy

- `HEAD khi chạy: a8a92461a94ed14db71c325bb2b65f96540746ea`
- Interpreter khoá: `C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\8715e538\venv\Scripts\python.exe`
- Lệnh `git diff --check`: exit code `0`
- Lệnh `python -m pytest tests/real/test_cp7_remeasure.py -q -p no:cacheprovider`: exit code `0`, dòng tổng kết nguyên văn `18 passed, 1 skipped in 0.08s`
- Chạy lô thật đúng một lần bằng Start-Process tách tiến trình (CP7_RG10_LIVE=1, PYTHONUTF8=1, PYTEST_DEBUG_TEMPROOT riêng của lane, log ngoài repo): lệnh `python -m pytest tests/real/test_cp7_overnight.py -q -p no:cacheprovider`, exit code `1`, dòng tổng kết nguyên văn `3 failed, 54 passed, 1 skipped in 26772.85s (7:26:12)`
- Đo CQ sau lô (CP7_REMEASURE_BATCH_PREFIX=f132d43a): lệnh `python -m pytest tests/real/test_cp7_remeasure.py -q -p no:cacheprovider -k test_cq -rP`, exit code `0`, dòng tổng kết nguyên văn `1 passed, 18 deselected in 1.20s`
- Chẩn đoán FAILED_FINAL (CP7_DIAG_BATCH_PREFIX=f132d43a): lệnh `python -m pytest tests/real/test_cp7_overnight.py -q -p no:cacheprovider -k test_diag -rP`, exit code `0`, dòng tổng kết nguyên văn `1 passed, 57 deselected in 2.66s`
- Kiểm tra mặc định sau lô, không chạy thật: lệnh `python -m pytest tests/real/test_cp7_overnight.py -q -p no:cacheprovider`, exit code `0`, dòng tổng kết nguyên văn `43 passed, 15 skipped in 0.30s`

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

```text
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
```

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
- media_select: 372,6 s (lô cũ 50,3 s, delta +322,3 s — tăng mạnh; GIẢ ĐỊNH chưa kiểm: do bước sinh ảnh AI Klein và tìm hook thật Pixabay/Freesound)
- tts: 11,1 s (lô cũ 15,9 s, delta -4,8 s)
- align: 7,6 s (lô cũ 9,9 s, delta -2,3 s)
- process: 79,2 s (lô cũ 27,5 s, delta +51,7 s — GIẢ ĐỊNH chưa kiểm: tải và xử lý media đa nguồn)
- render: 19,8 s (lô cũ 13,5 s, delta +6,3 s)
- qc: 3,0 s (lô cũ 3,2 s, delta -0,2 s)
- sync: 15,7 s (lô cũ 13,7 s, delta +2,0 s)
- complete: 0,1 s (lô cũ 0,1 s, delta +0,0 s)

### Phân tích job FAILED_FINAL theo nguyên nhân

- Lô cũ 74e795ef: Chỉ có đúng 1 job thất bại tại stage render, code no_illustration_available (activity resolve_render_package).
- Lô mới f132d43a: Có 53 job thất bại chung cuộc trên 153 job được tạo:
  - Stage qc, code quality_gates_failed, activity inspect_output: **51 job**. Lý do cổng QC nào không đạt chưa được số đo ghi lại (diag_job có message rỗng); Control cần điều tra. Launcher cấp job mới để đủ 100 video hợp lệ (quan sát từ total=153, không phải nguyên nhân).
  - Stage tts, code voice_duration_out_of_range, activity CreateVoiceTrack: **1 job**.
  - Stage none, code none, activity none: **1 job**.

## Chất lượng hình và tiếng

- **Phân bố bố cục (layout_batch)**:
  - HERO_STRIP: 41 video (41,0%, vượt trần 40% quy định 1 video, CQ.layout_cap_40: OVER; Control quyết; hồ sơ in max_concurrent_videos default 6 nên trần có thể vượt tối đa 5 video, mức vượt 1 video của HERO_STRIP nằm trong giới hạn đó).
  - SPLIT_STACK: 34 video (34,0%).
  - FULL_BLEED_INSET: 15 video (15,0%).
  - DATA_CARD: 10 video (10,0%).
  - MOSAIC_GRID: 0 video (0,0%).
  - Mã nguồn (LAYOUT_KEYS) có 5 bố cục: HERO_STRIP, MOSAIC_GRID, FULL_BLEED_INSET, SPLIT_STACK, DATA_CARD. Lô chỉ dùng 4 bố cục (distinct:4), MOSAIC_GRID không được chọn cho video nào. HERO_STRIP chiếm 41%, vượt trần 40% một video. Số đo không cho biết vì sao MOSAIC_GRID không được chọn; báo cáo không suy đoán.
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

- **OI-CP7-11-Q6**: Gói CP7-REMEASURE đã đo lại một lô thật 100 video trên dây chuyền tích hợp mới, kèm số đo hình/tiếng và so sánh với lô 74e795ef. Lô chạy đúng một lần; không chạy lô thứ hai.
- **Chất lượng sáng tạo (CQ)**: CQ.no_background_only PASS (0 video chỉ có ảnh nền); CQ.real_hooks PASS (100 video dùng hook thật Freesound và Pixabay, not_real=0); 375 ảnh AI cho 97/100 video; 11 bản nhạc khác nhau, 0 video không nhạc; CQ.layout_cap_40 OVER (HERO_STRIP 41/100, trần 40).
- **Ngưỡng vận hành (RG-10) chưa đạt**:
  - RG-10.auto_ratio_95 FAIL: 100/153 = 65,36%; 51 job qc/quality_gates_failed, lý do cổng QC chưa xác định.
  - RG-10.working_set_cap FAIL: 21,46 GiB, vượt trần 20 GiB.
  - RG-10.failure_isolated FAIL: target_runs=0 (nguồn 404 không được thu thập trong cửa sổ lô).
  - Thời gian: t_target_s tăng từ 6849 s lên 26641 s; lead p50 từ 364,6 s lên 812,3 s; 13,5 video/giờ so với 52,6; media_select p50 từ 50,3 s lên 372,6 s; RG-10.within_12h vẫn PASS.
- **Đề nghị Control quyết định** (Worker không tự quyết): (1) ghi nhận lô f132d43a là số đo thật của OI-CP7-11-Q6 với 3 RG-10 FAIL và 1 CQ OVER; (2) mở gói sửa sản phẩm riêng, ngoài owned paths của gói này, cho cổng QC quality_gates_failed, working set của staging và kiểm chứng nguồn 404, rồi đo lại ở phạm vi mới; (3) quyết định xử lý CQ.layout_cap_40 OVER. Các số đo này là cơ sở để Control, Reviewer (Sonnet 5.5) và Auditor (Opus 5.5) điều chỉnh trước mẫu CP7-14.
