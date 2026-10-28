# PW-E2E: Một lô qua POST /v1/batches thành video tới completion

- **Mã tác vụ:** PW-E2E
- **Milestone:** M7 (Production Wiring)
- **Tài liệu đặc tả nguồn:** `IMPL-PLAN-PROD-WIRING-V4` / `PW-E2E.md`
- **Trạng thái kích hoạt sản xuất:** `PRODUCTION_ACTIVATION_BLOCKED` (vẫn được duy trì nghiêm ngặt)

---

## 1. Lệnh đã chạy và kết quả kiểm chứng

Báo cáo kết quả thực thi các lệnh kiểm tra bắt buộc của tác vụ PW-E2E trên HEAD đã rebase lên `2ab2ddfe4f14d4f73d55d8a4aaa2aec2300ae51d`:

1. `git diff --check`
   - **Mã thoát:** 0
   - **Kết quả:** Không có lỗi khoảng trắng thừa hay ký tự dòng không hợp lệ trên cây làm việc.

2. `python -m pytest tests/integration/prod_wiring/test_pw_e2e_batch_video.py -q -p no:cacheprovider`
   - **Mã thoát:** 1 (FAILED / BLOCKED do khoảng trống mã nguồn production ngoài owned paths tại stage qc)
   - **Kết quả:** 3 failed, 6 passed, 1 warning in 1851.11s (0:30:51).
     - 6 test PASSED: `test_the_launcher_composition_binds_every_activity_and_has_no_private_assembly`, `test_the_support_module_patches_only_edge_adapters`, `test_the_feed_collection_enrichment_and_candidate_chain_feeds_the_second_batch`, `test_the_report_lists_stage_timings_and_the_cp7_conditions`, `test_the_seeded_images_resolve_to_verified_versions_through_the_production_lookup`, `test_module_docstring_declares_covered_ids`.
     - Quy trình thu thập RSS loopback -> trích xuất tài liệu -> enrichment -> candidate lô 2 đã PASSED hoàn toàn trong `test_the_feed_collection_enrichment_and_candidate_chain_feeds_the_second_batch`, xác nhận khoảng trống G1 (`missing business_date`) trước đây đã được đóng triệt để bởi các gói tích hợp.
     - Test mới `test_the_seeded_images_resolve_to_verified_versions_through_the_production_lookup` PASSED, xác nhận ảnh seed staging đã được đăng ký đúng chuẩn production và tra cứu thành công qua `verified_version_for_sha`.
     - 3 test FAILED:
       - `test_one_batch_posted_to_the_api_reaches_completion_and_a_second_batch_marks_the_gate_not_applicable` (FAILED: workflow đã vượt qua 8 stage đầu `analyze`, `script`, `media_select`, `plan`, `tts`, `align`, `process`, `render` nhưng dừng tại stage thứ 9 `qc` do lỗi `quality_gates_failed`: các cổng `VISUAL_HOOK_PRESENT`, `THUMBNAIL_PRESENT`, `SUBTITLE_BURNED_IN`, `INFERENCE_DISCLOSURE_PRESENT` không đạt, khiến job kết thúc ở trạng thái `EXHAUSTED` thay vì `COMPLETED`).
       - `test_a_drive_401_waits_then_one_upload_and_the_render_stage_does_not_rerun` (FAILED: do workflow dừng tại `qc` với lỗi `quality_gates_failed`, job không tiến được tới stage `upload` để kích hoạt tình huống Drive 401).
       - `test_stopping_and_restarting_the_worker_between_render_and_upload_reruns_nothing` (FAILED: do workflow dừng tại `qc`, job không đạt trạng thái chuyển giao giữa render và upload).
     - **Nguyên nhân lỗi trước:** Lượt trước 3 test FAILED vì rig đăng ký ảnh seed với `artifact_id='art-bg-NN'` trong khi `verified_version_for_sha` tìm `media/<sha256>.<ext>`; đã sửa trong `seed_render_and_catalog` bằng `register_staged_artifact`; đây là lỗi dữ liệu của rig, không phải khoảng trống production. Lượt chạy này xác nhận lỗi `seed_media_missing` đã được giải quyết triệt để, stage `media_select` đã PASSED và workflow đã thực thi qua toàn bộ chuỗi render.

3. `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/pw-e2e/report.md').read_text(encoding='utf-8'); assert 'PW-E2E' in t and 'CP7-10' in t and 'CP7-11' in t, 'PW-E2E'"`
   - **Mã thoát:** 0
   - **Kết quả:** Xác nhận báo cáo nghiệm thu tồn tại, đầy đủ các từ khóa giao ước kiểm tra và bảo toàn tiếng Việt có dấu.

---

## 2. Bảng thời gian thực thi từng stage (Đầu vào OI-PW-02)

Trong lượt chạy kiểm thử thật trên HEAD đã rebase, quy trình thu thập `DailyCollectionWorkflow` đã chạy thành công, đo được `collect_and_enrich_seconds = 5.42` và `allocate_seconds = 1.07`. Quy trình sản xuất video `VideoProductionWorkflow` đã thực thi qua 8 stage đầu tiên (`analyze`, `script`, `media_select`, `plan`, `tts`, `align`, `process`, `render`), tuy nhiên bị dừng tại stage thứ 9 (`qc`) do lỗi production ngoài owned paths (`quality_gates_failed`). Do đó, các stage `qc`, `sync`, `complete` chưa đo được số giây hoàn tất:

| Stage | Video chính (giây) | Video phụ (giây) | Ghi chú kỹ thuật |
| :--- | :--- | :--- | :--- |
| `analyze` | 0.10 | 0.10 | Stage phân tích ngữ cảnh và snapshot |
| `script` | 0.10 | 0.10 | Stage sinh kịch bản và segment |
| `plan` | 0.10 | 0.10 | Stage lập kế hoạch sản xuất video |
| `media_select` | 0.10 | 0.10 | Đã PASSED sau khi sửa seed dữ liệu |
| `tts` | 0.10 | 0.10 | Stage tổng hợp giọng đọc |
| `align` | 0.10 | 0.10 | Stage căn chỉnh phụ đề Whisper |
| `process` | 0.10 | 0.10 | Stage xử lý ảnh và nhạc nền |
| `render` | 0.10 | 0.10 | Stage ghép video và render FFmpeg thật |
| `qc` | KHÔNG ĐO ĐƯỢC | KHÔNG ĐO ĐƯỢC | Dừng tại inspect_output do quality_gates_failed |
| `sync` | KHÔNG ĐO ĐƯỢC | KHÔNG ĐO ĐƯỢC | Chưa thực thi do dừng tại qc |
| `complete` | KHÔNG ĐO ĐƯỢC | KHÔNG ĐO ĐƯỢC | Chưa thực thi do dừng tại qc |
| **Tổng cộng** | **KHÔNG ĐO ĐƯỢC** | **KHÔNG ĐO ĐƯỢC** | **Chờ gói chủ đóng khoảng trống production tại qc** |

*Ghi chú:* Số đo quy trình thu thập từ tệp `pw-e2e-stage-timings.json`: `collect_and_enrich_seconds = 5.42`, `allocate_seconds = 1.07` (đây là số liệu đầu vào OI-PW-02). Các stage `qc`, `sync`, `complete` chưa đo được do workflow dừng tại `qc` bởi lỗi production ngoài owned paths (`quality_gates_failed`). Độ phân giải đo của StageTimer là khoảng 0,1 giây.
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

### Khoảng trống phát hiện mới tại Stage qc
- **G3 (Stage `qc` — Quality gates failed):**
  - **Triệu chứng:** Hoạt động `inspect_output` trong stage `qc` bị thất bại do không đạt các cổng kiểm soát chất lượng:
    1. Cổng `VISUAL_HOOK_PRESENT` và `THUMBNAIL_PRESENT`: Tại `src/creative/domain/production_plan.py:236`, `visual_hook_ref` nhận `'vh-01'` và `thumbnail_ref` nhận `'thumb:vh-01'`. Tại `src/render/adapters/postgres_plan_assets.py:126` (`PostgresArtifactInfo.get_asset`), hàm yêu cầu định dạng UUID (`uuid.UUID(artifact_version_id)`). Do `'vh-01'` và `'thumb:vh-01'` không phải UUID, hàm trả về `None`, dẫn đến việc các asset này bị bỏ qua không được đưa vào `package.materialization_manifest`. Sau đó, tại `src/render/adapters/real_output_inspector.py:464, 490`, `_visual_hook` và `_thumbnail` tra cứu `manifest.get('vh-01')` và `manifest.get('thumb:vh-01')`, nhận kết quả `None`, làm trượt hai cổng chất lượng (`visual_hook_not_observed`, `thumbnail_not_observed`).
    2. Cổng `SUBTITLE_BURNED_IN` và `INFERENCE_DISCLOSURE_PRESENT`: Tại `src/render/domain/render_command.py:227`, bộ lọc ghép nối video sử dụng `concat=n=2:v=1:a=0` trên các ảnh đầu vào mà không có cờ loop (`-loop 1`), khiến luồng video xuất ra chỉ dài 2 frame (khoảng 66 ms) trong khi luồng âm thanh dài 30 giây. Luồng video kết thúc ngay ở đầu tệp, không có frame hình ảnh nào tại thời điểm phụ đề karaoke hay disclosure ở segment 2, dẫn tới việc các cổng này bị đánh trượt (`0 frames`, `disclosure_missing:s2`).
  - **Các tệp mã nguồn production bị ảnh hưởng (đã đối chiếu trên HEAD):**
    - `src/controlplane/api/wiring/render.py` (`resolve_inputs`, dòng 296-334 và 395): lấy nguyên `hook_placement` của kế hoạch, chỉ đưa vào manifest các ref là UUID.
    - `src/creative/domain/production_plan.py:236` và `src/creative/adapters/thumbnail_candidates.py:42,51`: `visual_hook_ref`/`audio_hook_ref` là hook_id, `thumbnail_ref` có dạng `thumb:<id>`, không bao giờ là UUID artifact version.
    - `src/render/adapters/postgres_plan_assets.py:109-114,134`: `asset_refs` gom các ref này nhưng `get_asset` bỏ chúng vì không phải UUID.
    - `src/render/adapters/real_output_inspector.py:464,490`: `manifest.get(ref)` trả None nên `VISUAL_HOOK_PRESENT` và `THUMBNAIL_PRESENT` trượt.
    - `src/render/domain/render_command.py:223-233` (`_filter_graph`) và `:289-297` (`build_render_command`): ảnh tĩnh vào `concat` không có `-loop 1 -t <thời lượng segment>`, video ra chỉ vài frame nên `SUBTITLE_BURNED_IN` và `INFERENCE_DISCLOSURE_PRESENT` trượt.
    - `src/creative/adapters/media_candidates.py:41,72`: chỉ nhận `kind=image`, nên production luôn đi qua đường ảnh tĩnh này.
  - **Gói chủ đề xuất xử lý:** `PW-F4` (dây nối `resolve_inputs`, ánh xạ hook/thumbnail sang artifact version đã VERIFIED trong manifest) và `PW-F3`/`PW-W2` (lệnh render ảnh tĩnh có `-loop 1 -t`); Control xác nhận gói chủ.
  - **Test bị chặn:**
    - `test_one_batch_posted_to_the_api_reaches_completion_and_a_second_batch_marks_the_gate_not_applicable`
    - `test_a_drive_401_waits_then_one_upload_and_the_render_stage_does_not_rerun`
    - `test_stopping_and_restarting_the_worker_between_render_and_upload_reruns_nothing`

### Vì sao rig không thể vá phía test
- Ref thumbnail luôn có tiền tố `thumb:` nên không thể thành UUID bằng dữ liệu seed; đổi hook_id sang UUID cũng không cứu được cổng `THUMBNAIL_PRESENT`.
- Seed `MediaAsset` dạng video bị `media_candidates.py:41` loại; ghi mp4 vào `<staging>/<artifact_version_id>` làm sai sha256 đã đăng ký và vi phạm kiểm tra đầu vào render.
- Vá logic production trong rig bị test AST `test_the_support_module_patches_only_edge_adapters` cấm và là phản ví dụ của tiêu chí 1 (assembly riêng của test).

### Điều kiện chạy lại
1. Gói chủ gộp bản sửa `resolve_inputs` và `render_command` vào nhánh tích hợp.
2. Lane rebase lên integration head mới, chạy lại `python -m pytest tests/integration/prod_wiring/test_pw_e2e_batch_video.py -q -p no:cacheprovider`.
3. Cập nhật mục 2, 3, 4 của báo cáo bằng số đo thật; tiêu chí 1, 2, 4 chưa có bằng chứng PASS cho tới lúc đó.

### Ghi nhận các vấn đề trước đây
- Khoảng trống G1 (`missing business_date` trong `CollectSource`) đã được đóng triệt để bởi các gói tích hợp vừa gộp (test `test_the_feed_collection_enrichment_and_candidate_chain_feeds_the_second_batch` đã PASSED).
- Các nghi vấn B2 (`rights_cleared`), B3 (`hashlib`) và B4 (`render input verification`) đã được xử lý trong các gói PW-D3-FIX1, PW-W2-FIX1, PW-W2-FIX3; pipeline đã thực thi qua toàn bộ chuỗi render thật bằng FFmpeg và chỉ dừng tại stage `qc` do lỗi production G3 nêu trên.
---

## 4. Ánh xạ coveredIds sang Test Cases

| coveredId | Test Case kiểm chứng | Kết quả |
| :--- | :--- | :--- |
| `PW-E2E-01` | `test_one_batch_posted_to_the_api_reaches_completion_and_a_second_batch_marks_the_gate_not_applicable` | FAILED (Dừng tại stage qc do quality_gates_failed: thiếu visual hook/thumbnail trong materialization manifest và luồng video ngắn do concat thiếu loop) |
| `CT-QC-001` | `test_one_batch_posted_to_the_api_reaches_completion_and_a_second_batch_marks_the_gate_not_applicable` | FAILED (Các cổng chất lượng tại qc không đạt do lỗi production ngoài owned paths tại postgres_plan_assets và render_command) |
| `CT-WF-004` | `test_a_drive_401_waits_then_one_upload_and_the_render_stage_does_not_rerun` | FAILED (Job dừng tại qc do quality_gates_failed, chưa tiến tới upload để kích hoạt lỗi Drive 401) |
| `CT-WF-006` | `test_stopping_and_restarting_the_worker_between_render_and_upload_reruns_nothing` | FAILED (Job dừng tại qc do quality_gates_failed, chưa tiến tới ranh giới giữa render và upload) |
| `CT-WF-007` | `test_stopping_and_restarting_the_worker_between_render_and_upload_reruns_nothing` | FAILED (Job dừng tại qc do quality_gates_failed, chưa kiểm chứng được attempt==1 giữa render và upload) |
| `CT-ORC-007` | `test_the_launcher_composition_binds_every_activity_and_has_no_private_assembly` | PASSED |
| `CT-ORC-010` | `test_the_launcher_composition_binds_every_activity_and_has_no_private_assembly` | PASSED |
| `CT-SRC-004` | `test_the_feed_collection_enrichment_and_candidate_chain_feeds_the_second_batch` | PASSED |

*Ghi chú:* Test `test_the_seeded_images_resolve_to_verified_versions_through_the_production_lookup` PASSED, bảo vệ dữ liệu seed và xác nhận `verified_version_for_sha` tra cứu thành công các ảnh seed staging.
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