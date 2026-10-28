# PW-E2E: Một lô qua POST /v1/batches thành video tới completion

- **Mã tác vụ:** PW-E2E
- **Milestone:** M7 (Production Wiring)
- **Tài liệu đặc tả nguồn:** `IMPL-PLAN-PROD-WIRING-V4` / `PW-E2E.md`
- **Trạng thái kích hoạt sản xuất:** `PRODUCTION_ACTIVATION_BLOCKED` (vẫn được duy trì nghiêm ngặt)

---

## 1. Lệnh đã chạy và kết quả kiểm chứng

Báo cáo kết quả thực thi các lệnh kiểm tra bắt buộc của tác vụ PW-E2E trên HEAD đã rebase lên `9e67a6ba3d0e64735ffd51dc068107ea0fe0222d`:

1. `git diff --check`
   - **Mã thoát:** 0
   - **Kết quả:** Không có lỗi khoảng trắng thừa hay ký tự dòng không hợp lệ trên cây làm việc.

2. `python -m pytest tests/integration/prod_wiring/test_pw_e2e_batch_video.py -q -p no:cacheprovider`
   - **Mã thoát:** 0
   - **Kết quả:** 10 passed, 1 warning in 137.93s (0:02:17).
     - Toàn bộ 10/10 test PASSED:
       - `test_the_launcher_composition_binds_every_activity_and_has_no_private_assembly` (PASSED)
       - `test_the_support_module_patches_only_edge_adapters` (PASSED)
       - `test_one_batch_posted_to_the_api_reaches_completion_and_a_second_batch_marks_the_gate_not_applicable` (PASSED)
       - `test_a_drive_401_waits_then_one_upload_and_the_render_stage_does_not_rerun` (PASSED)
       - `test_stopping_and_restarting_the_worker_between_render_and_upload_reruns_nothing` (PASSED)
       - `test_the_feed_collection_enrichment_and_candidate_chain_feeds_the_second_batch` (PASSED)
       - `test_the_report_lists_stage_timings_and_the_cp7_conditions` (PASSED)
       - `test_the_seeded_images_resolve_to_verified_versions_through_the_production_lookup` (PASSED)
       - `test_the_seeded_hooks_use_production_refs_and_registered_staged_versions` (PASSED)
       - `test_module_docstring_declares_covered_ids` (PASSED)
     - Không có test nào FAILED (0 failed).
     - Job video đạt trạng thái `COMPLETED`, lô đạt `TARGET_REACHED`, 1 ledger được ghi nhận, tệp mp4 có location `local-staging` và cloud `VERIFIED`.
     - Cổng chất lượng `INFERENCE_DISCLOSURE_PRESENT` đạt `PASSED` ở lô chính (có segment `claim_mode=inference` kèm `disclosure` với dải burn-in đo trên mp4 do FFmpeg render thật) và `NOT_APPLICABLE` ở lô phụ (script chỉ `source_backed`).
     - Dữ liệu hook đã được nạp qua `register_staged_artifact` với ref dạng `seed:<id>:sha256:<sha>`, thông tin `media_sha256` trong `technical_metadata`, hook visual dùng nguồn `testsrc` thật để đo kiểm và ảnh nền `bg-02` kích thước 720x1280 khác 1080x1920 được scale thật bởi pipeline render.
     - Kiểm thử Drive 401 xác nhận job chuyển sang `WAITING credential_unavailable`, đổi token hợp lệ thì chạy tiếp đúng 1 upload và stage render không chạy lại; dừng/bật lại worker giữa render và upload không chạy lại stage đã hoàn thành (`attempt` không tăng).

3. `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-e2e/report.md').read_text(encoding='utf-8'); assert 'PW-E2E' in t and 'CP7-10' in t and 'CP7-11' in t, 'PW-E2E'"`
   - **Mã thoát:** 0
   - **Kết quả:** Xác nhận báo cáo nghiệm thu tồn tại, đầy đủ các từ khóa giao ước kiểm tra và bảo toàn tiếng Việt có dấu.

---

## 2. Bảng thời gian thực thi từng stage (Đầu vào OI-PW-02)

Trong lượt chạy kiểm thử thật trên HEAD đã rebase, quy trình thu thập `DailyCollectionWorkflow` đã chạy thành công, đo được `collect_and_enrich_seconds = 5.64` và `allocate_seconds = 1.09`. Quy trình sản xuất video `VideoProductionWorkflow` đã thực thi hoàn tất cả 11 stage (`analyze`, `script`, `plan`, `media_select`, `tts`, `align`, `process`, `render`, `qc`, `sync`, `complete`) cho cả lô chính và lô phụ:

| Stage | Video chính (giây) | Video phụ (giây) | Ghi chú kỹ thuật |
| :--- | :--- | :--- | :--- |
| `analyze` | 0.12 | 0.12 | Stage phân tích ngữ cảnh và snapshot |
| `script` | 0.11 | 0.05 | Stage sinh kịch bản và segment |
| `plan` | 0.11 | 0.05 | Stage lập kế hoạch sản xuất video |
| `media_select` | 0.05 | 0.05 | Stage lựa chọn media ứng viên từ catalog |
| `tts` | 0.71 | 0.12 | Stage tổng hợp giọng đọc |
| `align` | 0.12 | 0.12 | Stage căn chỉnh phụ đề Whisper |
| `process` | 0.59 | 0.11 | Stage xử lý ảnh và nhạc nền |
| `render` | 0.12 | 0.11 | Stage ghép video và render FFmpeg thật |
| `qc` | 2.10 | 1.97 | Stage kiểm soát chất lượng đầu ra video |
| `sync` | 0.11 | 0.12 | Stage đồng bộ và upload lên lưu trữ đám mây |
| `complete` | 0.12 | 0.13 | Stage hoàn tất và xác nhận commit video |
| **Tổng cộng** | **4.26** | **2.95** | **Hoàn thành trọn vẹn 11 stage cho cả hai lô** |

*Ghi chú:* Số đo quy trình thu thập từ tệp `pw-e2e-stage-timings.json`: `collect_and_enrich_seconds = 5.64`, `allocate_seconds = 1.09` (đây là số liệu đầu vào OI-PW-02). Cả 11 stage đều hoàn thành thành công và được đo lường chính xác từ tệp timings thật. Độ phân giải đo của StageTimer là khoảng 0,1 giây.

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

### Kết luận G2
- G2 là lỗi dữ liệu seed của rig PW-E2E (artifact_id `art-bg-NN` thay vì `media/<sha256>.<ext>`), đã sửa trong `tests/integration/prod_wiring/pw_e2e_support.py` bằng `register_staged_artifact`. Mã production `src/creative/adapters/media_candidates.py` và `src/controlplane/application/storage_meta/handlers.py` (`verified_version_for_sha`) hoạt động hoàn toàn chính xác. Stage `media_select` đã PASSED trong lần chạy kiểm thử này.

### G3 ĐÃ ĐÓNG
- Các gói sửa F-10-FIX1, F-10-FIX2, PW-I1-FIX2, PW-F1-FIX1, ADAPT-SEED-FIX2, PW-W2-FIX4 đã được gộp tại integration head `9e67a6ba3d0e64735ffd51dc068107ea0fe0222d`.
- Rig `tests/integration/prod_wiring/pw_e2e_support.py` nay nạp hook đúng chuẩn production: tệp `media/<sha>.mp4` và `media/<sha>.wav` đăng ký qua `register_staged_artifact`, `import_hook` với `artifact_version_ref` dạng `seed:<id>:sha256:<sha>`, `media_sha256` nằm trong `technical_metadata`, hook visual dùng nguồn `testsrc` (có hình ảnh khác nền phẳng để cổng `VISUAL_HOOK_PRESENT` đo kiểm thật), và ảnh nền `bg-02` có kích thước 720x1280 khác 1080x1920 để pipeline render thực hiện scale thật.
- Toàn bộ các cổng kiểm soát chất lượng tại stage `qc` (gồm `VISUAL_HOOK_PRESENT`, `THUMBNAIL_PRESENT`, `SUBTITLE_BURNED_IN`, `INFERENCE_DISCLOSURE_PRESENT`) đều đạt `PASSED` (hoặc `NOT_APPLICABLE` cho cổng disclosure ở lô phụ).
- Không còn bất kỳ lỗi `quality_gates_failed` nào; khoảng trống G3 chính thức đóng hoàn toàn.

### Ghi nhận các vấn đề trước đây
- Khoảng trống G1 (`missing business_date` trong `CollectSource`) đã được đóng triệt để bởi các gói tích hợp vừa gộp (test `test_the_feed_collection_enrichment_and_candidate_chain_feeds_the_second_batch` đã PASSED).
- Các nghi vấn B2 (`rights_cleared`), B3 (`hashlib`) và B4 (`render input verification`) đã được xử lý trong các gói PW-D3-FIX1, PW-W2-FIX1, PW-W2-FIX3; pipeline đã thực thi qua toàn bộ chuỗi render thật bằng FFmpeg và hoàn thành toàn bộ 11 stage tới `CommitVideoCompletion`.

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

*Ghi chú:* Cả hai test seed bổ sung gồm `test_the_seeded_images_resolve_to_verified_versions_through_the_production_lookup` (xác nhận ảnh seed staging được tra cứu thành công qua `verified_version_for_sha` với kích thước 1080x1920 và 720x1280) và `test_the_seeded_hooks_use_production_refs_and_registered_staged_versions` (xác nhận hook seed sử dụng ref `seed:<id>:sha256:<sha>` và version đã đăng ký ở staging `VERIFIED`) đều đã PASSED.

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
9. Mọi gap trong PRODUCTION_GAPS đã đóng bởi gói chủ và rig PW-E2E chạy xanh với danh sách EDGE_ADAPTERS ở mục 3 (ĐÃ ĐÓNG HOÀN TOÀN).

---

## 7. Điều kiện để CP7-11 chạy

Để lát cắt kiểm tra độ bền và chịu tải CP7-11 được phép khởi động, các điều kiện sau bắt buộc phải được đáp ứng:
1. Lát cắt `CP7-10` đã đạt trạng thái **PASS**.
2. Hệ thống máy tính để bàn (Desktop host) duy trì hoạt động liên tục trong **12 giờ**.
3. Thiết lập hạn mức tiêu thụ dịch vụ AI `monthly_limit` là **50 USD** với chế độ dừng cứng (`hard_stop`).
4. Tốc độ sản xuất video trung bình trên toàn bộ chu kỳ 12 giờ không được vượt quá **7,2 phút (432 giây)** cho mỗi video hoàn tất.
5. Cổng kiểm soát chất lượng `RG-10` được kích hoạt và kiểm tra nghiêm ngặt (theo `docs/implementation/cp7/slices.md` dòng 203-220).
6. Đọc kỹ và tuân thủ các chỉ dẫn trong các mục mở `OI-CP7-06` và `OI-CP7-11`.
