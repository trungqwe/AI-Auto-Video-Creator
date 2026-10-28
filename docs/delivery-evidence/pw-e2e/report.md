# PW-E2E: Một lô qua POST /v1/batches thành video tới completion

- **Mã tác vụ:** PW-E2E
- **Milestone:** M7 (Production Wiring)
- **Tài liệu đặc tả nguồn:** `IMPL-PLAN-PROD-WIRING-V4` / `PW-E2E.md`
- **Trạng thái kích hoạt sản xuất:** `PRODUCTION_ACTIVATION_BLOCKED` (vẫn được duy trì nghiêm ngặt)

---

## 1. Lệnh đã chạy và kết quả kiểm chứng

Báo cáo kết quả thực thi các lệnh kiểm tra bắt buộc của tác vụ PW-E2E sau khi đã gỡ bỏ toàn bộ monkeypatch logic production khỏi test rig:

1. `git diff --check`
   - **Mã thoát:** 0
   - **Kết quả:** Không có lỗi khoảng trắng thừa hay ký tự dòng không hợp lệ trên cây làm việc.

2. `python -m pytest tests/integration/prod_wiring/test_pw_e2e_batch_video.py -q -p no:cacheprovider`
   - **Mã thoát:** 1 (FAILED / BLOCKED do khoảng trống mã nguồn production)
   - **Kết quả:** 4 passed, 4 failed, 1 warning trong 1222.27s (20 phút 22 giây).
     - 4 test PASSED: `test_the_launcher_composition_binds_every_activity_and_has_no_private_assembly`, `test_the_support_module_patches_only_edge_adapters`, `test_the_report_lists_stage_timings_and_the_cp7_conditions`, `test_module_docstring_declares_covered_ids`.
     - 4 test FAILED: `test_one_batch_posted_to_the_api_reaches_completion_and_a_second_batch_marks_the_gate_not_applicable`, `test_a_drive_401_waits_then_one_upload_and_the_render_stage_does_not_rerun`, `test_stopping_and_restarting_the_worker_between_render_and_upload_reruns_nothing`, `test_the_feed_collection_enrichment_and_candidate_chain_feeds_the_second_batch`.
     - Cả 4 test thất bại đều do cùng một nguyên nhân gốc ở mã nguồn production ngoài owned paths: `CollectSource` trong `DailyCollectionWorkflow` bị từ chối với lỗi `VALIDATION_ERROR` / `INVALID_ACTIVITY_REQUEST` do thiếu `business_date` (chi tiết tại mục 3b).

3. `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-e2e/report.md').read_text(encoding='utf-8'); assert 'PW-E2E' in t and 'CP7-10' in t and 'CP7-11' in t, 'PW-E2E'"`
   - **Mã thoát:** 0
   - **Kết quả:** Xác nhận báo cáo nghiệm thu tồn tại, đầy đủ các từ khóa giao ước kiểm tra và bảo toàn tiếng Việt có dấu.

---

## 2. Bảng thời gian thực thi từng stage (Đầu vào OI-PW-02)

Trong lượt chạy kiểm thử thật với rig không patch logic, quy trình thu thập `DailyCollectionWorkflow` bị chặn bởi lỗi production G1 (`VALIDATION_ERROR: missing business_date`), do đó workflow video chưa được kích hoạt và không sinh tệp `pw-e2e-stage-timings.json` mới:

| Stage | Video chính (giây) | Video phụ (giây) | Ghi chú kỹ thuật |
| :--- | :--- | :--- | :--- |
| `analyze` | KHÔNG ĐO ĐƯỢC | KHÔNG ĐO ĐƯỢC | Bị chặn do DailyCollectionWorkflow thất bại ở CollectSource |
| `script` | KHÔNG ĐO ĐƯỢC | KHÔNG ĐO ĐƯỢC | Bị chặn do DailyCollectionWorkflow thất bại ở CollectSource |
| `plan` | KHÔNG ĐO ĐƯỢC | KHÔNG ĐO ĐƯỢC | Bị chặn do DailyCollectionWorkflow thất bại ở CollectSource |
| `media_select` | KHÔNG ĐO ĐƯỢC | KHÔNG ĐO ĐƯỢC | Bị chặn do DailyCollectionWorkflow thất bại ở CollectSource |
| `tts` | KHÔNG ĐO ĐƯỢC | KHÔNG ĐO ĐƯỢC | Bị chặn do DailyCollectionWorkflow thất bại ở CollectSource |
| `align` | KHÔNG ĐO ĐƯỢC | KHÔNG ĐO ĐƯỢC | Bị chặn do DailyCollectionWorkflow thất bại ở CollectSource |
| `process` | KHÔNG ĐO ĐƯỢC | KHÔNG ĐO ĐƯỢC | Bị chặn do DailyCollectionWorkflow thất bại ở CollectSource |
| `render` | KHÔNG ĐO ĐƯỢC | KHÔNG ĐO ĐƯỢC | Bị chặn do DailyCollectionWorkflow thất bại ở CollectSource |
| `qc` | KHÔNG ĐO ĐƯỢC | KHÔNG ĐO ĐƯỢC | Bị chặn do DailyCollectionWorkflow thất bại ở CollectSource |
| `sync` | KHÔNG ĐO ĐƯỢC | KHÔNG ĐO ĐƯỢC | Bị chặn do DailyCollectionWorkflow thất bại ở CollectSource |
| `complete` | KHÔNG ĐO ĐƯỢC | KHÔNG ĐO ĐƯỢC | Bị chặn do DailyCollectionWorkflow thất bại ở CollectSource |
| **Tổng cộng** | **KHÔNG ĐO ĐƯỢC** | **KHÔNG ĐO ĐƯỢC** | **Chờ gói chủ đóng khoảng trống production G1** |

*Ghi chú:* Không đo được trong lượt chạy này do quy trình thu thập `DailyCollectionWorkflow` bị từ chối bởi lỗi production G1 (`VALIDATION_ERROR: missing business_date`), workflow chưa tiến vào pipeline render video.

---

## 3. Danh sách giả lập (EDGE_ADAPTERS)

Danh sách đầy đủ và chính xác các adapter giả lập được phép tại ranh giới biên (edge adapters):
1. `build_storage_services`: Thay `cloud_store` bằng `FakeDriveStore` (mô phỏng lưu trữ đám mây và phản hồi mã lỗi HTTP 401 khi token bị vô hiệu hóa).
2. `build_creative_services`: Gán `executor._http = FakeNineRouterHttp` với các kịch bản phản hồi theo schema cho 6 vai trò AI.
3. `build_collection_services`: Thay `fetcher`, `source_adapters`, `media_fetcher` bằng bản đi qua `LoopbackTransport` (cung cấp RSS feed và hình ảnh tĩnh trong môi trường loopback, không gọi ra Internet).
4. `RealKokoroTts` và `RealWhisperAligner`: Nhận `model_factory` giả (`FakeKokoroModel` sinh sóng sin float32 220 Hz chuẩn PCM16 và `FakeWhisperModel` phân chia mốc thời gian từ đều đặn).
5. `voice_wiring.ProductionHttpsTransport` và `load_music_sources`: Cung cấp nguồn nhạc nền giả lập (đoạn nhạc WAV 5 giây và tải danh mục nguồn nhạc hợp lệ).
6. `ProductionRuntime`: Dựng bởi `make_e2e_runtime` với `route_catalog`, `provider_credentials`, `vision_route`, `artifact_source`, `drive_token_broker`, `gpu_lease` giả lập.
7. `launcher.build_runtime`: Trả về `ProductionRuntime` nói trên khi khởi chạy ứng dụng.
8. `temporalio.client.Client`: Bị thay để kết nối trực tiếp vào Temporal test server; `TemporalWorkerGroup` bọc `UnsandboxedWorkflowRunner` và `max_cached_workflows=0`, `STOP_GRACE_SECONDS=30`.
9. `socket.getaddrinfo`: Chặn mọi kết nối mạng ngoài loopback (127.0.0.1 / localhost).
10. `app.services['render'].probe._ffmpeg/_lock`: Gán đường dẫn FFmpeg đã được ghim.
11. `build_temporal_registration`: Sử dụng spy ghi nhận lời gọi cấu hình activity registration (gọi nguyên hàm gốc của production, không thay đổi hành vi).
12. Seed dữ liệu catalog, cấu hình render và prompt: Thực hiện qua các repository thật (`PostgresStorageMetaRepository`, `PostgresMediaAssetRepository`, `PostgresHookHistory`) kèm tệp staging ghi sẵn.
13. `UPDATE cp_production_batches SET status = 'RUNNING'`: Câu lệnh SQL trực tiếp trong `post_batch` nhằm chuyển trạng thái lô (ghi nhận tại `OI-PW-E2E-01`).

**Thành phần nhị phân thật:**
- FFmpeg và FFprobe là nhị phân thật đã được ghim chặt tại `C:\ffmpeg\bin\ffmpeg.exe` (sha256: `f845a09b5467cf11651385e0be0dd4df6f70519264f8af2115e3acd6ab7f9480`).

**Xác nhận xử lý triệt để Finding F1:**
- Toàn bộ các monkeypatch can thiệp vào logic production nội bộ của lượt trước ĐÃ ĐƯỢC GỠ BỎ HOÀN TOÀN khỏi `tests/integration/prod_wiring/pw_e2e_support.py`:
  - Không còn patch `ProductionVariantContext.variant_context` (chèn `output_hash`).
  - Không còn patch `ProductionSelectionInputs.selection_inputs` (ép cờ `rights_cleared = True`).
  - Không còn patch `ProductionRenderSources.resolve_inputs` (tự chèn timeline và artifact giả).
  - Không còn patch `ProductionRenderSources.validation_context` (ép trạng thái `VERIFIED`).
  - Không còn patch `ProductionRenderSources.render_plan` (viết lại kế hoạch render).
  - Không còn patch `RealFfmpegMediaTool._source_path` và `_extension`.
  - Không còn patch `voice_wiring.verify_media_output`.
  - Không còn patch `Client.start_workflow` và `sa_handler.handle_collect_source_activity` (chèn ref `business_date`).
  - Không còn patch `cp_workflow.handle_voice_activity` (trả succeeded giả cho `TransformSensitiveImage`).
  - Không còn patch `storage_wiring.materialize_artifact_set_handler`.
  - Không còn patch `RenderActivityInputs._for_prepare`.
  - Không còn monkeypatch chèn `hashlib` vào `creative_wiring`.
- Test kiểm tra AST `test_the_support_module_patches_only_edge_adapters` đã được bổ sung vào `test_pw_e2e_batch_video.py` và chạy đạt kết quả XANH (PASSED), bảo đảm không có bất kỳ patch logic production nào bị tái đưa vào rig.

---

## 3b. Khoảng trống production (PRODUCTION_GAPS)

Các khoảng trống thực tế trong mã nguồn production ngoài owned paths đã được xác nhận trực tiếp qua kết quả chạy kiểm thử tại bước 7:

- **G1:** `src/controlplane/application/orchestration/workflows/activities.py:146` và `src/source_ingestion/worker/activity_handler.py:159-175`:
  - **Triệu chứng:** `CollectSource` trong `DailyCollectionWorkflow` chỉ truyền `input_refs` chứa `collection_source`, trong khi handler `handle_collect_source_activity` bắt buộc phải có đúng hai ref gồm cả `business_date`. Handler ném `ActivityRequestError(VALIDATION_ERROR, issues)` dẫn đến lỗi `ActivityRejected: INVALID_ACTIVITY_REQUEST` và dừng workflow thu thập.
  - **Test bị chặn:**
    - `test_one_batch_posted_to_the_api_reaches_completion_and_a_second_batch_marks_the_gate_not_applicable`
    - `test_a_drive_401_waits_then_one_upload_and_the_render_stage_does_not_rerun`
    - `test_stopping_and_restarting_the_worker_between_render_and_upload_reruns_nothing`
    - `test_the_feed_collection_enrichment_and_candidate_chain_feeds_the_second_batch`
  - **Gói chủ đề xuất xử lý:** `PW-W1`.

### Nghi vấn chưa xác nhận
Các điểm nghi vấn trong mã nguồn production đã được quan sát qua phân tích tĩnh, nhưng chưa được kích hoạt trong test run này do workflow bị chặn sớm tại G1:
- **B2:** `src/controlplane/api/wiring/creative.py:319` đặt `required_flags=('rights_cleared',)` trong khi các adapter ứng viên media (`src/creative/adapters/media_candidates.py:73`) và hook (`src/creative/adapters/hook_candidates.py:40`) không sinh cờ `rights_cleared`. Gói chủ đề xuất: `PW-W2`.
- **B3:** `src/controlplane/api/wiring/creative.py:410-412` gọi `hashlib` nhưng module chưa import thư viện `hashlib`. Gói chủ đề xuất: `PW-W2`.
- **B4:** `src/controlplane/api/wiring/render.py:336-343` chỉ đánh dấu `VERIFIED` cho các input có `PostgresArtifactInfo.get_asset`, khiến các artifact dạng voice hoặc timing không có asset trong cơ sở dữ liệu bị xem là chưa `VERIFIED`. Gói chủ đề xuất: `PW-W2`.

---

## 4. Ánh xạ coveredIds sang Test Cases

| coveredId | Test Case kiểm chứng | Kết quả |
| :--- | :--- | :--- |
| `PW-E2E-01` | `test_one_batch_posted_to_the_api_reaches_completion_and_a_second_batch_marks_the_gate_not_applicable` | FAILED (Bị chặn bởi G1) |
| `CT-QC-001` | `test_one_batch_posted_to_the_api_reaches_completion_and_a_second_batch_marks_the_gate_not_applicable` | FAILED (Bị chặn bởi G1) |
| `CT-WF-004` | `test_a_drive_401_waits_then_one_upload_and_the_render_stage_does_not_rerun` | FAILED (Bị chặn bởi G1) |
| `CT-WF-006` | `test_stopping_and_restarting_the_worker_between_render_and_upload_reruns_nothing` | FAILED (Bị chặn bởi G1) |
| `CT-WF-007` | `test_stopping_and_restarting_the_worker_between_render_and_upload_reruns_nothing` | FAILED (Bị chặn bởi G1) |
| `CT-ORC-007` | `test_the_launcher_composition_binds_every_activity_and_has_no_private_assembly` | PASSED |
| `CT-ORC-010` | `test_the_launcher_composition_binds_every_activity_and_has_no_private_assembly` | PASSED |
| `CT-SRC-004` | `test_the_feed_collection_enrichment_and_candidate_chain_feeds_the_second_batch` | FAILED (Bị chặn bởi G1) |

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
9. Mọi gap trong PRODUCTION_GAPS đã đóng bởi gói chủ và rig PW-E2E chạy xanh với danh sách EDGE_ADAPTERS ở mục 3.

---

## 7. Điều kiện để CP7-11 chạy

Để lát cắt kiểm tra độ bền và chịu tải CP7-11 được phép khởi động, các điều kiện sau bắt buộc phải được đáp ứng:
1. Lát cắt `CP7-10` đã đạt trạng thái **PASS**.
2. Hệ thống máy tính để bàn (Desktop host) duy trì hoạt động liên tục trong **12 giờ**.
3. Thiết lập hạn mức tiêu thụ dịch vụ AI `monthly_limit` là **50 USD** với chế độ dừng cứng (`hard_stop`).
4. Tốc độ sản xuất video trung bình trên toàn bộ chu kỳ 12 giờ không được vượt quá **7,2 phút (432 giây)** cho mỗi video hoàn tất.
5. Cổng kiểm soát chất lượng `RG-10` được kích hoạt và kiểm tra nghiêm ngặt (theo `docs/implementation/cp7/slices.md` dòng 203-220).
6. Đọc kỹ và tuân thủ các chỉ dẫn trong các mục mở `OI-CP7-06` và `OI-CP7-11`.