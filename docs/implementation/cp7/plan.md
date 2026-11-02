# Kế hoạch kiểm trên tài nguyên thật và user nghiệm thu — CP7-REAL-RESOURCES

- **Mã gói**: CP7-REAL-RESOURCES (planning_package)
- **Ngày lập**: 25/10/2026
- **Cơ sở**: HEAD `a9cb0d0a1fbe7e9e6362af86c479d685d1b9547d`; báo cáo đóng `docs/delivery-evidence/m3-milestone-close/report.md`, `m4-milestone-close/report.md`, `m5-milestone-close/report.md`, `m6-milestone-close/report.md`, `m7-milestone-close/report.md` (mục pendingUserCheckpoint); `docs/implementation/adapt/plan.md` mục 8 (CP7-ADAPT-01..11) và mục «Việc cần tài nguyên thật (CP7)» của kế hoạch A đến J.
- **Nguồn quyền**: ủy quyền AI_SETUP (`AI_PM_DELEGATED_AUTHORITY_RULES.md`), chỉ thị user duyệt Phần B ngày 18/10/2026, các quyết định của user ngày 20/10/2026 và quyết định D5 ngày 22/10/2026 (mục 2). `PRODUCTION_ACTIVATION_BLOCKED` còn hiệu lực tới nghiệm thu cuối; không push, không merge.
- **Slice**: `docs/implementation/cp7/slices.md` (14 slice `CP7-1` đến `CP7-14`). **Bằng chứng**: gói kế hoạch ở `docs/delivery-evidence/cp7-real-resources/report.md`; từng slice ở `docs/delivery-evidence/cp7-<số>/report.md`.

## 1. Phạm vi và nguyên tắc

1. CP7 chỉ **kiểm**. Slice chỉ thêm test ở `tests/real/**`, công cụ đo ở `tools/real/**` và báo cáo bằng chứng; không sửa `src/**`, migration, contract, state machine, `ui/dist`, `tests/m1`, `tests/m2`, `docs/milestones/**/evidence/**`. Lỗi phát hiện được ghi thành finding (mã, tệp:dòng, cách tái hiện) để Control lập gói sửa cho chủ phân hệ; slice CP7 không tự vá.
2. Không dùng mock, fake, fixture hay adapter `memory`, `fake_*` để đóng gate Drive/OAuth/AI/render/restore (roadmap §13 Điều cấm). Mọi lần chạy dùng hồ sơ `production` và adapter `real_*`.
3. Bí mật chỉ đi qua secret broker của phân hệ J (`CredentialBroker`, kho DPAPI, J-17). Slice không mở `Credentials/`, không đọc, chép hay in token, client secret, mật khẩu CSDL hay capability. Bằng chứng đã che bí mật và phải qua quét secret (0 lần khớp) trước khi ghi nhận.
4. Mỗi gate nêu tài nguyên dùng, cách kiểm thật, ngưỡng đạt, bằng chứng và rủi ro chi phí (mục 4). Kết quả ghi thành dòng `RG-<mã>.<mục>: PASS|FAIL|BLOCKED|NOT_OBSERVED`; `BLOCKED` và `NOT_OBSERVED` không phải PASS và không bị loại khỏi mẫu số.
5. Chỉ chạy trên máy này: PostgreSQL và Temporal trong Docker (chỉ `127.0.0.1`), một tài khoản Google Drive test, GPU RTX 4070 SUPER 12 GB, AI qua 9Router `http://127.0.0.1:20128/v1` tuyến `ag/gemini-3.8-flash-high`.
6. Không ngoại suy benchmark ngắn thành 12 giờ; không loại video lỗi do hệ thống khỏi mẫu số 95%.

## 2. Quyết định đã có (không mở lại)

| Mã | Quyết định | Hệ quả |
| --- | --- | --- |
| D5-CP7 | User 2026-10-22 (ai-setup decide): «Duyệt trước CP7 với tài nguyên D5: một tài khoản Google Drive test (user làm OAuth một lần khi Dashboard nhắc), GPU máy này, AI qua 9Router tuyến Gemini, chạy thử 12 giờ/100 video, mẫu 10 video để user xem và nghiệm thu cuối. CP7 tự mở khi M3–M7 đóng.» | Tài nguyên coi là sẵn sàng; hai điểm dừng user (mục 6) |
| U1 | User 20/10/2026: v1 chỉ chạy trên máy này; AI qua 9Router không phát sinh chi phí thêm; hết hạn mức thì chờ và tự chạy tiếp | Không cloud; chờ hạn mức là hành vi đúng |
| U2 | User 20/10/2026: đúng một tài khoản Drive thật, OAuth một lần, token chỉ qua broker DPAPI | Điểm dừng user thứ nhất (CP7-3) |
| U4 | User 20/10/2026: một đêm 100 video trong 12 giờ, rồi mẫu 10 video; user xem trên Dashboard khoảng 30 phút và nghiệm thu, gồm checkpoint M2 | CP7-11 và CP7-14; điểm dừng cuối |
| U5 | User 22/10/2026: exit gate roadmap rộng hơn kế hoạch đã duyệt chỉ ghi chú, không FAIL | CP7 đo thêm làm bằng chứng, không đổi kết luận đóng milestone |
| U6 | User 21/10/2026: `test_h36_m1_regression` hoãn sang CP7 | Xử lý ở OI-CP7-05 |

## 3. Đối chiếu pendingUserCheckpoint của các lane đóng M3–M7

Nguồn: mục «pendingUserCheckpoint» và «Đối chiếu exit gate» của năm báo cáo đóng. Mười một mã chờ, không bỏ sót mã nào:

| Lane đóng | Mã chờ | Nội dung | Loại | Gate kế hoạch |
| --- | --- | --- | --- | --- |
| M3-MILESTONE-CLOSE | M3-EG7 | User duyệt phân hệ A-B và R1 Content Alpha | user | R1 |
| M3-MILESTONE-CLOSE | M3-REAL | RSS/web thật; scheduler cloud khi desktop offline | tài nguyên thật | RG-04, R1, OI-CP7-03 |
| M4-MILESTONE-CLOSE | M4-EG5 | Drive/OAuth/integrity phần M4 của G04 trên tài khoản thật | tài nguyên thật | RG-02 |
| M4-MILESTONE-CLOSE | M4-EG6 | User duyệt C-I và R2 Media Alpha | user | R2 |
| M5-MILESTONE-CLOSE-R2 | M5-EG7 | User duyệt D và R3 Creative Alpha | user | R3 |
| M5-MILESTONE-CLOSE-R2 | M5-REAL | AI trả phí thật; mẫu user chấm topic ≥ 90%, event-link ≥ 95%, media/hook ≥ 90%; holdout khóa | tài nguyên và user | RG-03, RG-04, R3 |
| M6-MILESTONE-CLOSE-R2 | M6-EG1 | R4 Video Alpha theo luồng giám sát từ snapshot đến completion | tài nguyên thật | RG-09 |
| M6-MILESTONE-CLOSE-R2 | M6-EG5 | G06 phần TTS/timing/media và G07 phần output/QC có evidence | tài nguyên thật | RG-05, RG-06, RG-07 |
| M6-MILESTONE-CLOSE-R2 | M6-EG6 | User duyệt E-F và 5 preset; nghe mẫu, duyệt hình | user | R4 |
| M7-MILESTONE-CLOSE | M7-R5-EG1 | Batch không giám sát trên workload đại diện với nhà cung cấp thật | tài nguyên thật | RG-10, R5 |
| M7-MILESTONE-CLOSE | M7-R6 | R6 Operational Baseline (G01–G07, 100 video/12 giờ, ≥ 95%, hiệu năng, chất lượng, chi phí, runbook, nghiệm thu) | tài nguyên và user | RG-10 đến RG-13, R6 |

Mục chờ liên quan ngoài năm báo cáo (cũng không bỏ sót):

- `M2-USER-CHECKPOINT-P8-P9` (`pending_user_checkpoint` trong `docs/parallel-delivery/task-dag.yaml`): gộp vào nghiệm thu cuối R6, kèm ngoại lệ `safe-error-modal.spec.ts` của CP-2C (nêu ở nghiệm thu cuối theo ghi chú Control).
- `USER-CKPT-D9-D10` (thư viện và cách dựng lại runtime): CP7 không đóng; nhắc ở R6.
- `tests/m2/test_p7b_hardening.py::test_h36_m1_regression`: hoãn sang CP7 (U6) → RG-08, OI-CP7-05.
- `OI-ADAPT-10` (quyền ảnh tải kèm bài; user đã quyết ngày 25/10/2026 và CLOSURE_NOTE CP7/RG-13 ngày 02/11/2026: ảnh `UNVERIFIED` dùng được sau khi che mờ tối thiểu logo và chi tiết nhạy cảm, không còn chờ) → R2 chỉ trình bằng chứng; `ROADMAP-OPEN-009` (năm preset) → R4; `ROADMAP-OPEN-006`, `ROADMAP-OPEN-007`, `ROADMAP-OPEN-008` (mẫu an toàn ảnh, output profile, sai số word timing) → RG-06, RG-07, RG-05.
- `CP7-ADAPT-01..11` (`docs/implementation/adapt/plan.md` mục 8): 01→RG-02, 02→RG-03, 03 và 04→RG-05, 05→RG-06, 06→RG-07, 07→RG-04, 08→RG-01, 09→RG-10, 10→RG-11 và RG-12, 11→RG-13.

## 4. Gate cần tài nguyên thật

Mỗi gate gồm tài nguyên, cách kiểm thật, ngưỡng đạt, bằng chứng và rủi ro chi phí. Ngưỡng lấy từ roadmap §12–§13, `tools/launcher/prod/profile.json` và quyết định D8 (mục 8); ngưỡng mang nhãn «D8» là mặc định đề xuất, đo xong thì đổi bằng revision cấu hình, không đổi mã.

### RG-01 — Hạ tầng và phiên sản xuất thật (CP7-ADAPT-08; CP7-H-04, CP7-H-05) — CP7-1, CP7-2

- **Tài nguyên**: Docker Desktop (`aiavc-postgres`, `aiavc-temporal`), launcher `python tools/launcher/launcher.py start`, Chromium của Playwright 1.50.1, bí mật tổng hợp `cp7-canary` ghi qua broker (không phải bí mật thật).
- **Cách kiểm thật**: đo FFmpeg, digest image, cổng, GPU, ổ đĩa, 9Router (CP7-1); mở phiên qua `/launch`, kiểm TLS loopback, Host, Origin, CSRF, `/test-driver/*`, quét canary trong DOM, HAR, log và response (CP7-2).
- **Ngưỡng đạt**: sha256 `ffmpeg.exe` = `f845a09b5467cf11651385e0be0dd4df6f70519264f8af2115e3acd6ab7f9480`; digest PostgreSQL và Temporal khớp `tools/runtime/runtime.lock.json`; cổng 57028, 7233, 8443 chỉ bind `127.0.0.1`; ổ đĩa trống ≥ 50 GiB; capability dùng lần hai hoặc sau 60 giây trả 403; `/test-driver/*` trả 404; Host hoặc Origin ngoài danh sách bị từ chối; lệnh ghi thiếu CSRF bị từ chối; canary 0 lần khớp.
- **Bằng chứng**: `docs/delivery-evidence/cp7-1/report.md`, `cp7-2/report.md` (lệnh, mã HTTP, số lần khớp canary đã che).
- **Rủi ro chi phí**: 0 USD; thời gian ≤ 30 phút.

### RG-02 — Drive, OAuth và toàn vẹn (M4-EG5; CP7-ADAPT-01; CP7-I-01, CP7-J-01) — CP7-3

- **Tài nguyên**: một tài khoản Google Drive test (`drive-primary`, phạm vi `drive.file`); khóa `LOCK-EXTERNAL-DRIVE`; OAuth do user làm một lần bằng `python tools/launcher/launcher.py oauth`.
- **Cách kiểm thật**: `DriveObjectStore` qua broker; upload resumable 3 tệp ngẫu nhiên (1 MiB, 9 MiB vượt chunk 8 MiB, 40 MiB); tải lại tính sha256; upload lại với file ID đã cấp (409); URI phiên không tồn tại; bearer không hợp lệ cố định; đọc quota thật.
- **Ngưỡng đạt**: md5 Drive = md5 cục bộ 3/3; sha256 tải lại khớp; 409 không nhân đôi tệp (đúng 1 bản); phiên hỏng thì mở phiên mới và hoàn tất; bearer sai trả 401 và job chuyển chờ credential, không mất; từ chối upload khi dự phóng dung lượng trống dưới 20%; token chỉ có trong kho DPAPI (0 lần xuất hiện ngoài kho); chỉ xóa trong `AI-Auto-Video-Creator/cp7-fixture/<runId>/` và số tệp ngoài thư mục này không đổi.
- **Bằng chứng**: `docs/delivery-evidence/cp7-3/report.md`: kích thước, md5, mã HTTP, 8 hex đầu của băm file ID.
- **Rủi ro chi phí**: 0 USD; ≤ 60 MiB lên Drive; rủi ro dung lượng Drive (OI-CP7-06).

### RG-03 — AI qua 9Router và chi phí (M5-REAL phần máy; CP7-ADAPT-02; CP7-D-01, CP7-D-05, CP7-J-04, CP7-J-05) — CP7-4

- **Tài nguyên**: 9Router `http://127.0.0.1:20128/v1`, tuyến `ag/gemini-3.8-flash-high`; `RoutedInvocationService` (J-18); sổ chi phí của J.
- **Cách kiểm thật**: 6 vai trò (`analysis`, `angle`, `script`, `selection`, `metadata`, `image_safety`) × 10 lời gọi thật; đối chiếu log endpoint; đọc sổ chi phí; ghi độ trễ.
- **Ngưỡng đạt**: ≥ 57/60 lời gọi (95%) trả kết quả qua đúng validator của D hoặc `WAITING_PROVIDER` hợp lệ; 0 request tới host hay cổng khác `127.0.0.1:20128`; 100% lời gọi có bản ghi chi phí; bản ghi và log 0 lần khớp secret; p95 độ trễ ≤ 120 giây; `hard_stop` bật, `monthly_limit` 50 USD, cảnh báo 80% = 40 USD. Mục «hết hạn mức thì chờ rồi tự chạy tiếp» chỉ PASS khi gặp 429 hoặc `BUDGET_BLOCKED` thật, không thì `NOT_OBSERVED` (OI-CP7-08).
- **Bằng chứng**: `docs/delivery-evidence/cp7-4/report.md`.
- **Rủi ro chi phí**: ≤ 60 lời gọi, ledger tăng ≤ 5 USD trong slice.

### RG-04 — Thu thập RSS/web thật và khóa holdout (M3-REAL; M5-REAL phần holdout; CP7-ADAPT-07; CP7-A-01, CP7-A-05) — CP7-5

- **Tài nguyên**: Internet công khai, bảy nguồn trong `tools/launcher/prod/sources.json`; `real_http_transport.py` và `real_feed_source.py` qua `SecureFetcher`.
- **Cách kiểm thật**: mỗi nguồn một lượt thu thập thật gồm feed, ≤ 5 bài và ảnh kèm; một URL 404 thật của chính nguồn; dừng giữa lượt rồi chạy tiếp; khóa manifest holdout (40 cặp bài, chỉ id và sha256) trước khi dùng bài mẫu làm đầu vào prompt.
- **Ngưỡng đạt**: ≥ 6/7 feed trả 200 và parse ≥ 5 mục; ≥ 90% bài mẫu trích ≥ 600 ký tự; 0 redirect tới địa chỉ riêng tư; không quá 4 fetch toàn cục và 1 fetch mỗi host; nguồn 404 không dừng nguồn khác; chạy tiếp từ checkpoint không tạo bài trùng; thời gian lượt được đo (basis MEASURED). Phần «scheduler cloud» là `OUT_OF_V1_SCOPE` (OI-CP7-03).
- **Bằng chứng**: `docs/delivery-evidence/cp7-5/report.md`, `tests/real/fixtures/cp7_holdout_manifest.json`.
- **Rủi ro chi phí**: 0 USD; ≤ 200 MiB tải về; rủi ro nguồn chặn truy cập.

### RG-05 — TTS Kokoro và aligner faster-whisper (M6-EG5 phần TTS/timing; CP7-ADAPT-03, CP7-ADAPT-04; CP7-E-01, CP7-E-02, CP7-E-07, CP7-D-04) — CP7-6

- **Tài nguyên**: GPU máy này (`LOCK-DESKTOP-GPU`); `kokoro-v1.0.onnx`, `voices-v1.0.bin` và faster-whisper `small.en` ngoài cây Git, sha256 do Control ghi (OI-CP7-01); FFmpeg đã ghim.
- **Cách kiểm thật**: 20 đoạn thoại tiếng Anh (15–60 từ) và 5 kịch bản 150–190 từ qua `real_kokoro_tts.py`; aligner chạy trên giọng có nhạc nền −20 dB và SFX; so mốc câu với `silencedetect` của FFmpeg ghim; đo `actual_duration_ms`.
- **Ngưỡng đạt**: 100% WAV hợp lệ (24 kHz, mono, thời lượng > 0); tỷ lệ từ không khớp ≤ 5% ở ≥ 95% đoạn (`aligner.max_unmatched_word_ratio` 0.05); lệch mốc đầu/cuối câu ≤ 150 ms ở ≥ 95% câu (`word_timing_tolerance_ms`); sau hiệu chỉnh `speech_rate_wpm`, ước lượng thời lượng lệch ≤ 10% so với thực tế ở ≥ 90% đoạn (D8); VRAM đỉnh ≤ 11 GiB. User nghe thử giọng ở R4.
- **Bằng chứng**: `docs/delivery-evidence/cp7-6/report.md` (số đo và `speech_rate_wpm` đề xuất để Control ghi revision cấu hình). Nguồn hiệu chỉnh `speech_rate_wpm` là giọng production (15 lượt TTS thật của RG-09, gộp 136 từ/phút, ADAPT-CONFIG-FIX3), không phải corpus RG-05; giá trị 121 do corpus từ dài đề xuất không áp.
- **Rủi ro chi phí**: 0 USD; GPU ≤ 60 phút; `BLOCKED` nếu sha256 trọng số còn `null`.

### RG-06 — An toàn ảnh (M6-EG5 phần media; CP7-ADAPT-05; CP7-E-03; ROADMAP-OPEN-006) — CP7-7

- **Tài nguyên**: Sensitive Image Set thật có quyền sử dụng rõ ràng, đặt ngoài cây Git (OI-CP7-02); tuyến AI `image_safety`; `boxblur` của FFmpeg ghim.
- **Cách kiểm thật**: ≥ 7 nhóm (safe, trẻ em, máu me, vũ khí, uncertain, detector/transform lỗi, không đọc được) × ≥ 5 ảnh qua `real_llm_image_safety.py` và `boxblur` (luma_radius 40, luma_power 3); lỗi detector thật bằng timeout 1 ms trên tuyến thật.
- **Ngưỡng đạt**: 0 ảnh trẻ em, máu me, vũ khí kết thúc ở safe hoặc ở dạng không che; 100% ảnh uncertain, lỗi, không đọc được không bao giờ thành safe; vùng che giảm độ sắc nét ≥ 50% theo `signalstats` (D8); tỷ lệ phát hiện chỉ ghi số đo, không tuyên bố ngưỡng khi chưa đo. User chấm mẫu ở R2 và R4.
- **Bằng chứng**: `docs/delivery-evidence/cp7-7/report.md` (số ảnh và kết quả theo nhóm, không nhúng ảnh nhạy cảm).
- **Rủi ro chi phí**: ≤ 70 lời gọi AI, ledger ≤ 5 USD; `BLOCKED` nếu chưa có bộ ảnh.

### RG-07 — Render, QC và GPU (M6-EG5 phần output/QC; CP7-ADAPT-06; CP7-F-01 đến CP7-F-07; CP7-E-04 đến CP7-E-06; ROADMAP-OPEN-007) — CP7-8

- **Tài nguyên**: GPU RTX 4070 SUPER 12 GB, `LOCK-DESKTOP-GPU` 2 khe; FFmpeg và ffprobe đã ghim; hook và ảnh seed tự sinh; giọng từ CP7-6.
- **Cách kiểm thật**: 5 preset × 2 video qua `real_ffmpeg_renderer.py` bằng NVENC và một video libx264 dự phòng; QC bằng ffprobe, `loudnorm`, `silencedetect`; lỗi thật: kill FFmpeg giữa lượt, cắt cụt output, timeout sau side effect, output hỏng, chốt chặn dung lượng ổ (đọc số đo thật, không lấp đầy đĩa); STT, TTS và render chạy cùng lúc.
- **Ngưỡng đạt**: 1080×1920, 30 fps, H.264, AAC, MP4; thời lượng 61–70 giây; ≤ 157286400 byte; phát được (`-f null` exit 0); hook similarity ≥ 0.85, hook audio ≥ −40 dBFS, visual continuity ≥ 0.6; phụ đề burn-in thấy được ở ≥ 90% mốc lấy mẫu; lệch karaoke ≤ 150 ms ở ≥ 95% từ; loudness −16 LUFS ± 1,5 LU và true peak ≤ −1,5 dBTP (warn_only, ghi số đo); crash hoặc cắt cụt → attempt `failed`, không còn tệp dở; timeout sau side effect → `OUTCOME_UNKNOWN` rồi reconcile bằng probe; output hỏng → QC FAIL; không quá 2 khe GPU cùng lúc, yêu cầu thứ 3 → `WAITING_CAPABILITY`; 0 OOM; VRAM đỉnh ≤ 11 GiB. Ghi render p95 cho G02.
- **Bằng chứng**: `docs/delivery-evidence/cp7-8/report.md`.
- **Rủi ro chi phí**: 0 USD; GPU ≤ 4 giờ; ≤ 5 GiB tạm.

### RG-08 — Runtime thật, ranh giới lỗi và h36 (bằng chứng bổ sung cho M7-R5; CP7-G-03; TST-WF-INV-010, 016, 017, 018; U6) — CP7-9

- **Tài nguyên**: PostgreSQL thật trong Docker (database dùng-một-lần, `LOCK-POSTGRES-TEST-DB`), Temporal thật.
- **Cách kiểm thật**: chạy các bộ test cần PostgreSQL (`tests/integration/convergence/test_cp3_migration_sequence.py`, `test_cp4_queries_postgres.py`, `test_cp5_completion_uow.py`, `tests/integration/orchestration/test_g_commit_completion.py`) trên PostgreSQL thật và đọc lý do skip; `down` rồi `start` giữ volume; chạy `tests/m1` theo OI-CP7-05.
- **Ngưỡng đạt**: 0 skip có lý do DSN hoặc PostgreSQL; commit completion rollback đúng tại trước, trong và sau side effect ngoài (trước commit receipt); số hàng các bảng chính trước và sau `down`/`start` bằng nhau; `tests/m1` trừ `test_live_e3_drive_verification` đạt 92 passed, 0 failed.
- **Bằng chứng**: `docs/delivery-evidence/cp7-9/report.md` (đầu ra pytest có `-rs`).
- **Rủi ro chi phí**: 0 USD; ≤ 40 phút.

### RG-09 — R4 Video Alpha có giám sát (M6-EG1; CP7-G-01, CP7-F-08; CP7-ADAPT-06) — CP7-10

- **Tài nguyên**: toàn bộ ngăn xếp production: Drive, GPU, 9Router, PostgreSQL, Temporal; hook và ảnh seed.
- **Cách kiểm thật**: một lô 1 video qua Control API trên hồ sơ `production`: snapshot → script AI → TTS → align → render → upload Drive → verify → completion; giữa lúc render chạy `launcher stop` rồi `start`.
- **Ngưỡng đạt**: mọi stage SUCCEEDED; 0 adapter `Fake`/`Memory` trong composition production; QC hard gate 100%; chỉ đếm output sau khi cloud verified (md5 khớp); chỉ dọn bản local sau verified; script, góc và media không đổi so với snapshot (băm khớp); sau `start` sẵn sàng ≤ 300 giây và stage đã SUCCEEDED không chạy lại; truy vết đủ snapshot, model, prompt, config.
- **Bằng chứng**: `docs/delivery-evidence/cp7-10/report.md`.
- **Rủi ro chi phí**: ≤ 25 lời gọi AI, ledger ≤ 3 USD; Drive ≤ 200 MiB; ≤ 2 giờ.

### RG-10 — Đêm chạy 100 video trong 12 giờ (M7-R5-EG1, M7-R6; CP7-ADAPT-09; CP7-G-04) — CP7-11

- **Tài nguyên**: toàn bộ ngăn xếp production; máy bật liên tục 12 giờ, Docker chạy; Drive còn đủ dung lượng (OI-CP7-06).
- **Cách kiểm thật**: `batch.target` = 100, `videos_per_news_per_round` = 2, không thao tác sau khi bắt đầu lô; monitor ghi mỗi 5 phút; ở khoảng giờ thứ 6 chạy `launcher stop` rồi `start`; thêm một nguồn URL 404 thật để kiểm lỗi độc lập; kiểm nhất quán sau lô.
- **Ngưỡng đạt**: ≥ 100 video hợp lệ đã cloud verified trong ≤ 12 giờ kể từ lúc bắt đầu lô (thời gian chờ hạn mức tính vào 12 giờ và báo riêng); ≥ 95% video đủ đầu vào hoàn thành không thao tác, không loại lỗi do hệ thống khỏi mẫu số; 0 job biến mất không trạng thái hoặc log (consistency audit 0 finding); lỗi một nguồn hoặc một video không dừng việc độc lập; sau resume ≤ 300 giây và không chạy lại stage đã xong; ledger AI cả đêm ≤ 25 USD và tháng ≤ 50 USD, cảnh báo 80% hiển thị khi chạm; working set ≤ 20 GiB; 0 secret trong log.
- **Bằng chứng**: `docs/delivery-evidence/cp7-11/report.md` (chuỗi thời gian, số liệu theo stage cho G02, chi phí cho G03).
- **Rủi ro chi phí**: cao nhất của CP7 (mục 7); dừng cứng ở 12 giờ 15 phút.

### RG-11 — UI, xoay secret và rollback (M7-R6; CP7-H-01, CP7-H-02; CP7-ADAPT-10 phần xoay; CP7-J-02, CP7-J-06) — CP7-12

- **Tài nguyên**: Chromium Playwright 1.50.1 màn hình 1920×1080; cơ sở dữ liệu sau CP7-11 (≥ 100 video job); bí mật tổng hợp `cp7-rotate` trong broker DPAPI.
- **Cách kiểm thật**: ≥ 30 lần mỗi thao tác (cold và warm riêng) trên màn `jobs`, `batches`, `artifacts`, `cost`; ngắt SSE rồi nối lại; xoay `cp7-rotate` sang version mới; thu hồi credential ngắn hạn của J khi job đang chạy; công bố cấu hình rồi rollback bằng revision mới.
- **Ngưỡng đạt**: p95 thao tác UI ≤ 2000 ms và p95 ACK lệnh ≤ 1000 ms (cold và warm); SSE nối lại không lặp event, cursor ngoài retention thì resync; version cũ của `cp7-rotate` bị từ chối; job chuyển chờ credential khi bị thu hồi, không mất; băm cấu hình sau rollback bằng giá trị trước.
- **Bằng chứng**: `docs/delivery-evidence/cp7-12/report.md` (phân vị; dữ liệu khóa bằng băm bảng đếm).
- **Rủi ro chi phí**: 0 USD; ≤ 90 phút.

### RG-12 — Restore drill (M7-R6; CP7-ADAPT-10; CP7-G-05, CP7-I-04) — CP7-13

- **Tài nguyên**: `launcher backup`, `stop`, `restore`; Drive (`LOCK-EXTERNAL-DRIVE`); Docker.
- **Cách kiểm thật**: backup → upload một output nhỏ lên Drive sau backup → `stop` → `restore --file` → `start`; thử ghi từ worker và kết quả thuộc epoch cũ; đối soát Drive.
- **Ngưỡng đạt**: sha256 `.dump` khớp sidecar; có CSDL mới `controlplane_<yyyymmddHHMMSS>`; `state/recovery-epoch.json` ghi trước khi đổi `state/active-db`; kết quả epoch cũ bị từ chối; CSDL cũ còn nguyên; số hàng bảng chính bằng lúc backup; đối soát phát hiện output Drive mới hơn backup và không cleanup trước khi reconcile xong.
- **Bằng chứng**: `docs/delivery-evidence/cp7-13/report.md`.
- **Rủi ro chi phí**: 0 USD; ≤ 60 phút; `state/active-db` đổi có chủ đích, không xóa dữ liệu nào.

### RG-13 — Mẫu 10 video và gói nghiệm thu (CP7-ADAPT-11; U4) — CP7-14

- **Tài nguyên**: toàn bộ ngăn xếp production sau restore; Dashboard `https://127.0.0.1:8443`.
- **Cách kiểm thật**: lô mẫu `batch.target.sample_run` = 10; sinh gói bằng chứng cho R1–R6 và hai bảng chấm cho user (10 video; 40 cặp holdout), cột nhãn của user để trống.
- **Ngưỡng đạt**: 10 video hợp lệ, cloud verified; mỗi video truy vết đủ; các video cùng lượt của một tin có StoryAngle khác nhau; ảnh `UNVERIFIED` chỉ vào video sau khi che mờ tối thiểu logo và chi tiết nhạy cảm, lấy tối đa ảnh trên trang, không video nào chỉ có ảnh nền, thiếu ảnh thì dùng ảnh AI cùng phong cách với ảnh trong bài (OI-ADAPT-10, CLOSURE_NOTE CP7/RG-13; khoá probe `rights_unverified_excluded` của CP7-14 giữ tên, xét theo quyết định này); gói bằng chứng liệt kê đủ R1–R6 với tệp và băm; không ô nào ghi thay user.
- **Bằng chứng**: `docs/delivery-evidence/cp7-14/report.md`.
- **Rủi ro chi phí**: ≤ 60 lời gọi AI, ledger ≤ 5 USD; Drive ≤ 1,5 GiB; ≤ 3 giờ.

## 5. Gate user nghiệm thu R1–R6

Tách riêng khỏi gate tài nguyên. User chỉ nghiệm thu sau khi các gate tài nguyên liên quan có kết quả và gói `CP7-14` đã chuẩn bị bằng chứng; kế hoạch không ghi thay user. Dashboard ở `https://127.0.0.1:8443`, tên màn theo `src/controlplane/ui/src/features/screens/screenRegistry.ts`.

- **R1 Content Alpha (M3-EG7; M3-REAL)** — User xem: màn `sources` (7 nguồn, trạng thái lượt, stage, lỗi), `articles` và `events` (truy ngược nguồn, fetch evidence, revision cho ≥ 3 mục), `stage-runs`; bằng chứng RG-04. Quyết định cần user: ghi nhận phạm vi v1 không có scheduler cloud (OI-CP7-03). Tiền đề: RG-04.
- **R2 Media Alpha (M4-EG6; M4-EG5)** — User xem: màn `media`, `hooks`, `artifacts` (đủ 5 trạng thái bản gốc, đã xử lý, không chắc chắn, lỗi, không khả dụng; vị trí Drive đã verified) và kết quả ảnh an toàn theo nhóm; bằng chứng RG-02, RG-06. Quyết định của user đã có: quyền dùng ảnh tải kèm bài (OI-ADAPT-10 ngày 25/10/2026; CLOSURE_NOTE CP7/RG-13 ngày 02/11/2026): nhãn `UNVERIFIED` giữ nguyên, ảnh vào video sau khi che mờ tối thiểu; user chỉ xem kết quả. Tiền đề: RG-02, RG-06.
- **R3 Creative Alpha (M5-EG7; M5-REAL)** — User xem: màn `snapshots`, `story-angles`, `scripts` (snapshot, model, prompt, config, input revision của 10 video mẫu); chấm bảng topic và media/hook của 10 video (ngưỡng ≥ 90%) và bảng 40 cặp holdout cho event-link (ngưỡng ≥ 95%); kết quả RG-03, RG-04. Tiền đề: RG-03, RG-04, RG-13.
- **R4 Video Alpha (M6-EG6; M6-EG1; M6-EG5)** — User nghe và xem 10 video mẫu: giọng Kokoro, karaoke, hình, hook, 5 preset (duyệt ROADMAP-OPEN-009), output profile (ROADMAP-OPEN-007) và sai số word timing 150 ms (ROADMAP-OPEN-008); bằng chứng RG-05 đến RG-09. Tiền đề: RG-05, RG-06, RG-07, RG-09, RG-13.
- **R5 Unattended Beta (M7-R5-EG1)** — User xem: báo cáo đêm chạy RG-10 (chuỗi thời gian, số video, lỗi độc lập, resume, 0 job mất) và màn `batches`, `jobs`, `logs`. Tiền đề: RG-08, RG-10.
- **R6 Operational Baseline (M7-R6)** — User xem: bảng G01–G07 (G01: RG-08, RG-10; G02: RG-10; G03: RG-03, RG-10 và màn `cost`; G04: RG-01, RG-02; G05: RG-12; G06: RG-03 đến RG-07; G07: RG-07, RG-11), p95 UI và ACK, runbook kèm kết quả restore và xoay secret; giới hạn đã nêu (OI-CP7-04, OI-CP7-07, OI-CP7-08). Gộp checkpoint M2 (`M2-USER-CHECKPOINT-P8-P9`, kèm ngoại lệ `safe-error-modal.spec.ts` của CP-2C) và nhắc `USER-CKPT-D9-D10`. Tiền đề: mọi RG PASS hoặc ghi rõ BLOCKED/NOT_OBSERVED.

Thời gian user dự kiến: OAuth ≈ 5 phút (điểm dừng 1) + xem mẫu trên Dashboard ≈ 30 phút (U4) + chấm bảng ≈ 10 phút (OI-CP7-10), tổng ≈ 45 phút. Kết luận R1–R6 là của user; `CP7-14` chỉ chuẩn bị bằng chứng.

## 6. Thứ tự, khóa tài nguyên và điểm dừng user

- Thứ tự: `CP7-1` → `CP7-2` → `CP7-3` → `CP7-4` → `CP7-5` → `CP7-6` → `CP7-7` → `CP7-8` → `CP7-9` → `CP7-10` → `CP7-11` → `CP7-12` → `CP7-13` → `CP7-14`. Mọi slice giữ `LOCK-CP7` (một máy, một GPU, một tài khoản Drive nên chạy tuần tự); thêm `LOCK-EXTERNAL-DRIVE` (CP7-3, 10, 11, 13, 14), `LOCK-DESKTOP-GPU` (CP7-1, 6, 8, 10, 11, 14), `LOCK-POSTGRES-TEST-DB` (CP7-9). `LOCK-CP7` chưa có trong `docs/parallel-delivery/ownership-and-locks.yaml`; Control biên dịch trong phong bì policy.
- Điểm dừng user 1: trước CP7-3 user chạy `python tools/launcher/launcher.py oauth` (hết hạn sau 300 giây), Control nhắc theo OI-CP7-09. Chưa có OAuth thì CP7-3 báo `BLOCKED` (`WAITING_USER_OAUTH`).
- Điểm dừng user 2 (cuối): nghiệm thu R1–R6 sau CP7-14 (mục 5).
- Tiền điều kiện do Control chuẩn bị, không phải việc của Worker: sha256 trọng số mô hình (trước CP7-6), Sensitive Image Set (trước CP7-7), máy bật và Docker chạy suốt CP7-11.
- Ngoài hai điểm dừng, không hỏi user; thiếu tài nguyên thì `BLOCKED` kèm evidence.

## 7. Chi phí, trần và cách dừng

AI chỉ qua 9Router tuyến Gemini; `monthly_limit` 50 USD, `hard_stop` bật, cảnh báo 80% (40 USD) luôn hiệu lực. Tổng trần kế hoạch: 5 + 5 + 3 + 25 + 5 = 43 USD, dưới 50 USD; nếu ledger tháng đã ≥ 40 USD thì slice tốn AI kế tiếp báo `BLOCKED` thay vì chạy.

| Slice | Tài nguyên tốn | Trần | Cách dừng |
| --- | --- | --- | --- |
| CP7-4 | AI | ≤ 60 lời gọi; ledger +5 USD | `CostGuard`, `hard_stop`, Ctrl+C; hạn 45 phút |
| CP7-7 | AI thị giác | ≤ 70 lời gọi; ledger +5 USD | như CP7-4; hạn 45 phút |
| CP7-10 | AI, Drive, GPU | ≤ 25 lời gọi; +3 USD; 200 MiB; 2 giờ | `launcher stop`; `Deadline` |
| CP7-11 | AI, Drive, GPU 12 giờ | ledger +25 USD; ≤ 12 GiB Drive; 12 giờ 15 phút | `Deadline` gọi `launcher stop` (dừng worker, việc làm tiếp khi bật lại, không mất dữ liệu); cảnh báo ở 40 USD |
| CP7-14 | AI, Drive, GPU | ≤ 60 lời gọi; +5 USD; 1,5 GiB; 3 giờ | như CP7-10 |

Slice còn lại không tốn tiền (0 USD): tài nguyên là thời gian máy, tối đa 4 giờ GPU (CP7-8) và ≤ 60 MiB Drive (CP7-3). Hết hạn mức AI thì job chờ (`WAITING_PROVIDER`) và tự chạy tiếp khi hạn mức hồi, không phải lỗi.

## 8. Mục mở và quyết định D8

Không mục nào là đã duyệt; mục cần user được ghi ở R1–R6.

| Mã | Nội dung | Mặc định đã chọn | Lý do |
| --- | --- | --- | --- |
| OI-CP7-01 | sha256 trọng số Kokoro và faster-whisper (OI-ADAPT-06) còn `null` và `BLOCKED` trong `tools/launcher/prod/model-weights.lock.json` | Control ghi trước CP7-6; thiếu thì CP7-6 `BLOCKED` | Không bịa hash |
| OI-CP7-02 | Sensitive Image Set thật có quyền sử dụng rõ ràng (ROADMAP-OPEN-006) chưa nằm trong D5 | Đặt ngoài cây Git ở `LOCALAPPDATA/AIAutoVideoCreator/real-fixtures/sensitive/` kèm manifest sha256; chưa có thì CP7-7 `BLOCKED`, không tự sinh ảnh giả để PASS | Roadmap cấm media không rõ quyền và cấm mock đóng gate |
| OI-CP7-03 | M3-REAL gồm «scheduler cloud khi desktop offline» nhưng user 20/10/2026 chốt v1 không dựng cloud | RG-04 kiểm thu thập khi worker bật và tiếp tục từ checkpoint; phần cloud ghi `OUT_OF_V1_SCOPE` và đưa R1 để user ghi nhận | Không tự ghi là đã duyệt |
| OI-CP7-04 | Contract J «desktop không giữ refresh token» áp cho kiến trúc có cloud; v1 chỉ máy này và refresh token nằm trong kho DPAPI | GIẢ ĐỊNH; kiểm token chỉ ở kho DPAPI, 0 lần xuất hiện ngoài kho; user xác nhận ở R6 | U1, U2 |
| OI-CP7-05 | `test_h36_m1_regression` chạy `tests/m1` và đòi 93 passed, 0 skipped; `tests/m1/p3/test_drive_live_probe.py` đọc `Credentials/` trực tiếp (`tests/m1/p3/conftest.py` dòng 12–13) | CP7-9 không chạy h36 nguyên văn, không sửa test M1 và M2 (bất biến); chạy `tests/m1` trừ `test_live_e3_drive_verification` (kỳ vọng 92 passed) và đóng phần Drive thật bằng CP7-3 qua broker; nêu lệch này ở nghiệm thu cuối | Quy tắc broker thắng; thiếu runtime thì `BLOCKED` |
| OI-CP7-06 | Drive tài khoản test có thể chỉ 15 GB trống; 100 video có thể tới vài GiB | Preflight đọc `storageQuota`; yêu cầu trống ≥ 12 GiB cộng 20% dự trữ, thiếu thì CP7-11 `BLOCKED` và báo user, không tự mua dung lượng | Tránh dừng giữa đêm |
| OI-CP7-07 | Thu hồi refresh token thật buộc user OAuth lần hai, trái quyết định «một lần» | Không thu hồi token Drive thật; kiểm revoke bằng bearer không hợp lệ cố định (HTTP 401 thật của Google), thu hồi credential ngắn hạn của J và xoay bí mật tổng hợp `cp7-rotate`; giới hạn nêu ở R6 | Giữ quyết định của user |
| OI-CP7-08 | Không thể chủ động làm hết hạn mức AI thật | Chỉ ghi khi gặp 429 hoặc `BUDGET_BLOCKED` thật; không gặp thì `NOT_OBSERVED`, không PASS, không giả lập; nêu ở R6 | Cấm mock |
| OI-CP7-09 | «Dashboard nhắc OAuth» trong khi UI giữ nguyên (OI-ADAPT-03) | Nhắc bằng console `launcher oauth` và runbook | UI và spec M2 giữ nguyên |
| OI-CP7-10 | Mẫu 10 video chỉ cho phép ≤ 1 sai ở ngưỡng 90%, không phải ước lượng thống kê; event-link ≥ 95% cần mẫu lớn hơn | Event-link đo trên holdout 40 cặp bài khóa trước khi dùng bài làm đầu vào prompt (CP7-5), user gán nhãn bảng rút gọn khoảng 10 phút; thiếu nhãn thì R3 giữ `PENDING` | Không dùng model làm judge duy nhất (T8) |
| OI-CP7-11 | Thời gian chờ hạn mức AI có tính vào 12 giờ không | Có tính; báo riêng `wait_provider_seconds` | Roadmap yêu cầu 100 video đã sync trong 12 giờ |

## 9. Ngoài phạm vi

Sửa mã sản phẩm, migration, contract, state machine, `ui/dist`; scheduler cloud; Gemini TTS, WhisperX, pgvector; thêm thư viện; nhiều hơn một tài khoản Drive; media có bản quyền hoặc không rõ quyền, trừ ảnh bài `UNVERIFIED` đã quyết dùng sau khi che mờ tối thiểu (OI-ADAPT-10, CLOSURE_NOTE CP7/RG-13); kích hoạt sản xuất (`PRODUCTION_ACTIVATION_BLOCKED` giữ tới nghiệm thu cuối của user); push và merge. Kết quả CP7 không tự đổi trạng thái `docs/11-roadmap.md` hay `docs/12-pre-code-checklist.md`; quyền đó thuộc Control và user.
