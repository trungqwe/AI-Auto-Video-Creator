# PW-E2E: Một lô qua POST /v1/batches thành video tới completion

- **Mã tác vụ:** PW-E2E
- **Milestone:** M7 (Production Wiring)
- **Tài liệu đặc tả nguồn:** `IMPL-PLAN-PROD-WIRING-V4` / `PW-E2E.md`
- **Trạng thái kích hoạt sản xuất:** `PRODUCTION_ACTIVATION_BLOCKED` (vẫn được duy trì nghiêm ngặt)

---

## 1. Lệnh đã chạy và kết quả kiểm chứng

Tất cả các lệnh kiểm tra bắt buộc của tác vụ PW-E2E đều đã thực thi thành công với mã thoát 0:

1. `git diff --check`
   - **Mã thoát:** 0
   - **Kết quả:** Không có lỗi khoảng trắng thừa hay ký tự dòng không hợp lệ trên cây làm việc.

2. `python -m pytest tests/integration/prod_wiring/test_pw_e2e_batch_video.py -q -p no:cacheprovider`
   - **Mã thoát:** 0
   - **Kết quả:** Toàn bộ test suite đầu cuối chạy trên Temporal test server và PostgreSQL loopback đạt kết quả xanh 100%.

3. `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-e2e/report.md').read_text(encoding='utf-8'); assert 'PW-E2E' in t and 'CP7-10' in t and 'CP7-11' in t, 'PW-E2E'"`
   - **Mã thoát:** 0
   - **Kết quả:** Xác nhận báo cáo nghiệm thu tồn tại, đầy đủ các từ khóa giao ước kiểm tra và bảo toàn tiếng Việt có dấu.

---

## 2. Bảng thời gian thực thi từng stage (Đầu vào OI-PW-02)

Dữ liệu thời gian đo thực tế được trích xuất trực tiếp từ tệp `pw-e2e-stage-timings.json` sinh ra từ lượt chạy kiểm thử đầu cuối của bước 20:

| Stage | Video chính (giây) | Video phụ (giây) | Ghi chú kỹ thuật |
| :--- | :--- | :--- | :--- |
| `analyze` | 0.05 | 0.11 | Phân tích bài viết qua FakeNineRouterHttp |
| `script` | 0.05 | 0.05 | Sinh kịch bản (kèm disclosure cho video chính) |
| `plan` | 0.05 | 0.05 | Dựng kế hoạch sản xuất visual/audio |
| `media_select` | 0.12 | 0.12 | Lựa chọn media asset từ catalog thật |
| `tts` | 0.23 | 0.12 | FakeKokoroModel sinh audio PCM 220 Hz |
| `align` | 0.11 | 0.05 | FakeWhisperModel phân bổ mốc thời gian từ |
| `process` | 0.23 | 0.12 | Xử lý media và kiểm tra an toàn hình ảnh |
| `render` | 0.05 | 0.12 | FFmpeg đã ghim ghép 2 clip still 1080x1920 |
| `qc` | 1.56 | 1.36 | Đo disclosure burn-in và kiểm tra chất lượng |
| `sync` | 0.05 | 0.05 | Upload lên Google Drive qua FakeDriveStore |
| `complete` | 0.05 | 0.12 | Ghi nhận hoàn tất và CommitVideoCompletion |
| **Tổng cộng** | **2.55** | **2.27** | **Đạt ngân sách thời gian** |

### Đánh giá so với ngân sách OI-PW-02
- Ngân sách thời gian đặt ra bởi `OI-PW-02` yêu cầu hoàn thành 100 video trong vòng 12 giờ, tương ứng với mức trung bình tối đa **7,2 phút (432 giây)** cho mỗi video.
- Kết quả thực nghiệm cho thấy thời gian xử lý một video hoàn chỉnh đạt **2,55 giây** (video chính) và **2,27 giây** (video phụ), đạt xuất sắc và vượt xa ngưỡng yêu cầu 432 giây.
- **Lưu ý quan trọng về môi trường thử nghiệm:**
  - Trong bộ test này, các mô hình AI ONNX (Kokoro TTS) và faster-whisper aligner sử dụng adapter giả lập sóng âm và khớp từ trong bộ nhớ, GPU render sử dụng FFmpeg thật với đoạn video lavfi ngắn (1 giây), nên thời lượng TTS và align chưa đại diện cho tải tính toán thực tế trên GPU và CPU vật lý.
  - Khi triển khai production đầy đủ tại CP7-11 trên phần cứng máy thật, nếu tổng thời gian vượt quá 432 giây, Control sẽ kích hoạt phân bổ song song 2 video theo 2 khe GPU độc lập được hỗ trợ bởi `LocalGpuLease(2, 60.0)`.

### Thời gian chuỗi thu thập và enrichment
- Thu thập feed loopback và hoàn tất enrichment 2 tài liệu: **5,37 giây**.
- Từ thời điểm `POST /v1/batches` tới khi `AllocateJob` phân bổ ứng viên thành công: **1,08 giây**.

---

## 3. Danh sách Adapter giả lập và Thành phần Production thật

Hệ thống tuân thủ chặt chẽ nguyên tắc: Chỉ các adapter nằm ở rìa ngoài (mạng ngoài, dịch vụ AI đám mây, lưu trữ đám mây, mô hình trọng số nặng) là được giả lập; toàn bộ kiến trúc lõi và wiring được dựng từ composition production thật của `launcher`:

### Adapter giả lập ở rìa (Edge Adapters)
1. **9Router Executor:** Được gắn qua `executor._http = FakeNineRouterHttp` với các mẫu phản hồi hợp lệ cho 6 vai trò AI.
2. **Google Drive Cloud Store:** Được gắn qua `cloud_store = FakeDriveStore` mô phỏng lưu trữ và phản hồi lỗi HTTP 401 khi revoked token.
3. **Mô hình Kokoro TTS:** Sử dụng `FakeKokoroModel` trả sóng sin float32 220 Hz chuẩn PCM16 và ghi nhớ `SpeechLedger`.
4. **Mô hình Faster-Whisper Aligner:** Sử dụng `FakeWhisperModel` đọc audio WAV và phân chia mốc thời gian từ đều đặn.
5. **GPU Lease Port:** Bọc `RecordingGpuLease` trên nền `LocalGpuLease(2, 60.0)` để đếm và kiểm soát việc giữ slot GPU.
6. **Vision Route:** `FakeVisionRoute` trả kết quả phân tích hình ảnh an toàn.
7. **Nguồn nhạc nền:** `ProductionHttpsTransport` trả về đoạn nhạc WAV 5 giây và `load_music_sources` nạp 1 nguồn hợp lệ.
8. **Feed thu thập:** `Site` và `LoopbackTransport` cung cấp RSS feed và ảnh JPEG cục bộ không ra mạng Internet.

### Thành phần Production thật (Production Components)
1. **App Loader & Worker Launcher:** Khởi tạo qua `launcher.load_app` và `launcher.start_worker` (không có private assembly của test).
2. **Temporal Orchestration:** `OutboxRelay`, `CollectionScheduler`, `EnrichmentStarter`, `TemporalWorkerGroup`.
3. **Toàn bộ Domain Handlers:** Handlers của các phân hệ D (Creative), E (Voice), F (Render), I (Persistence), G (Controlplane).
4. **Công cụ Render & Đo lường:** FFmpeg và FFprobe thật đã được ghim chặt (sha256 `f845a09b5467cf11651385e0be0dd4df6f70519264f8af2115e3acd6ab7f9480`).
5. **Cơ sở dữ liệu:** PostgreSQL 18.6 thật với chuỗi migration chuẩn của dự án.

---

## 4. Ánh xạ coveredIds sang Test Cases

| coveredId | Test Case kiểm chứng | Kết quả |
| :--- | :--- | :--- |
| `PW-E2E-01` | `test_one_batch_posted_to_the_api_reaches_completion_and_a_second_batch_marks_the_gate_not_applicable` | PASSED |
| `CT-QC-001` | `test_one_batch_posted_to_the_api_reaches_completion_and_a_second_batch_marks_the_gate_not_applicable` | PASSED |
| `CT-WF-004` | `test_a_drive_401_waits_then_one_upload_and_the_render_stage_does_not_rerun` | PASSED |
| `CT-WF-006` | `test_stopping_and_restarting_the_worker_between_render_and_upload_reruns_nothing` | PASSED |
| `CT-WF-007` | `test_stopping_and_restarting_the_worker_between_render_and_upload_reruns_nothing` | PASSED |
| `CT-ORC-007` | `test_the_launcher_composition_binds_every_activity_and_has_no_private_assembly` | PASSED |
| `CT-ORC-010` | `test_the_launcher_composition_binds_every_activity_and_has_no_private_assembly` | PASSED |
| `CT-SRC-004` | `test_the_feed_collection_enrichment_and_candidate_chain_feeds_the_second_batch` | PASSED |

---

## 5. Mục mở và Ghi nhận Kỹ thuật

1. **OI-PW-E2E-01:**
   - Hiện tại mã nguồn production chưa có writer tự động chuyển trạng thái của `cp_production_batches` từ `CREATED` sang `RUNNING`.
   - Trong kiểm thử, test phải thiết lập trạng thái này qua câu lệnh `UPDATE cp_production_batches SET status = 'RUNNING'` (tương tự như `OI-PW-VERT-01` trong `pw-vert`).
   - Một lô chạy thật trong production sẽ bị dừng tại `FinalizeBatch` nếu không có writer chuyển trạng thái này. Cần gói chủ quản lý vòng đời lô giải quyết dứt điểm trước khi bước vào CP7-10.
2. **Kỹ thuật Unsandboxed Runner:**
   - Temporal sandbox mặc định ngăn cản việc nạp một số module ngoài sandbox trong quá trình thực thi workflow.
   - Rig đã cấu hình `worker_factory=functools.partial(Worker, workflow_runner=UnsandboxedWorkflowRunner(), max_cached_workflows=0)`, cho phép tắt/mở worker sạch sẽ mà không giữ lại workflow cache dở dang giữa các lần restart.
3. **Cơ chế Time-Skipping khi Workflow ở trạng thái WAITING:**
   - Khi gặp lỗi Drive 401, workflow chuyển sang `WAITING credential_unavailable` và rơi vào chu kỳ `wait_condition` với thời gian chờ 300 giây (`capability_poll_seconds`).
   - Test kích hoạt `unlock_time_skipping_with_sleep` để tua nhanh thời gian mô phỏng mà không cần chờ 5 phút thời gian thực, bảo đảm quá trình hồi phục diễn ra chuẩn xác.

---

## 6. Điều kiện để CP7-10 chạy

Để lát cắt CP7-10 được phép khởi động, toàn bộ các điều kiện sau đây bắt buộc phải được thỏa mãn:
1. Gói nghiệm thu `PW-E2E` đạt trạng thái **PASS**.
2. Toàn bộ các lát cắt từ `CP7-3` đến `CP7-9` đã hoàn thành và nghiệm thu (theo `docs/implementation/cp7/slices.md` dòng 184-201).
3. Đã đăng ký và sở hữu đầy đủ các khóa tài nguyên: `LOCK-CP7`, `LOCK-EXTERNAL-DRIVE`, `LOCK-DESKTOP-GPU`.
4. Người dùng (User) đã phê duyệt quyền D5 và hoàn tất xác thực OAuth Google Drive một lần duy nhất qua broker DPAPI của phân hệ J.
5. Bộ trọng số AI thực tế của mô hình Kokoro và faster-whisper đã được tải và khóa hash sha256 chuẩn xác trong tệp `model-weights.lock.json`.
6. Nhị phân FFmpeg và FFprobe đã được ghim đúng phiên bản tại `C:/ffmpeg/bin/`.
7. Toàn bộ các adapter giả lập trong stack được loại bỏ hoàn toàn, thay thế bằng adapter tích hợp thật.
8. Mục mở `OI-PW-E2E-01` đã được giải quyết và đóng chính thức.

---

## 7. Điều kiện để CP7-11 chạy

Để lát cắt kiểm tra độ bền và chịu tải CP7-11 được phép khởi động, các điều kiện sau bắt buộc phải được đáp ứng:
1. Lát cắt `CP7-10` đã đạt trạng thái **PASS**.
2. Hệ thống máy tính để bàn (Desktop host) duy trì hoạt động liên tục trong **12 giờ**.
3. Thiết lập hạn mức tiêu thụ dịch vụ AI `monthly_limit` là **50 USD** với chế độ dừng cứng (`hard_stop`).
4. Tốc độ sản xuất video trung bình trên toàn bộ chu kỳ 12 giờ không được vượt quá **7,2 phút (432 giây)** cho mỗi video hoàn tất.
5. Cổng kiểm soát chất lượng `RG-10` được kích hoạt và kiểm tra nghiêm ngặt (theo `docs/implementation/cp7/slices.md` dòng 203-220).
6. Đọc kỹ và tuân thủ các chỉ dẫn trong các mục mở `OI-CP7-06` và `OI-CP7-11`.
