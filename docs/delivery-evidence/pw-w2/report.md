# Báo cáo Nghiệm thu Kỹ thuật: PW-W2

- **Mã tác vụ:** PW-W2
- **Milestone:** M7 (Production Wiring)
- **Tài liệu đặc tả nguồn:** `IMPL-PLAN-PROD-WIRING-V4` / `PW-W2.md`
- **Trạng thái kích hoạt sản xuất:** `PRODUCTION_ACTIVATION_BLOCKED` (vẫn được duy trì nghiêm ngặt)

---

## 1. Phạm vi thực hiện

Danh sách các tệp đã chỉnh sửa và bổ sung trong owned paths:
1. `src/controlplane/api/wiring/creative.py`:
   - Bổ sung `PostgresPromptScope` (đọc `cp_config_revisions` qua `borrow_connection`).
   - Bổ sung `LazyInstructions` kế thừa `Mapping`, trì hoãn truy vấn prompt đến khi stage pipeline thực sự truy cập role, giúp quá trình lắp ráp không truy vấn database khi prompt chưa seed.
   - Bổ sung `creative_settings` trích xuất cấu hình từ profile hoặc tham số.
   - Bổ sung `ProductionSelectionInputs` và `ProductionVariantContext` đọc dữ liệu thật từ catalog và variant registry.
   - Bổ sung hai hàm public `creative_activity_deps` và `creative_activity_handlers` (8 stage activities: `BuildProductionSnapshot`, `AnalyzeContent`, `GenerateStoryAngles`, `GenerateScript`, `SelectCreativeAssets`, `BuildProductionPlan`, `ValidateVariant`, `GenerateOutputMetadata`).
   - Thân hàm `build_creative_services` được giữ nguyên vẹn 100%, bảo đảm không có lớp `Fake*`, `InMemory*`, `Memory*` trong nhánh production theo kiểm tra AST.
2. `src/controlplane/api/wiring/voice.py`:
   - Chuẩn hoá cấu hình Whisper aligner sử dụng đúng `voice_root` (`staging_root / 'voice'`) và `resolve_audio = None`.
   - Kết nối `VoiceArtifactPlacer` dùng chung cùng root với `KokoroConfig.staging_dir`.
   - Bổ sung `ThreadLocalVoiceUow`, `ArtifactRows`, `PlanAudioFromPlans`, `SelectionSeedFallback`, `verify_media_output`, `read_media_image`, `ProductionHttpsTransport`.
   - Bổ sung `voice_activity_deps` và `voice_activity_handlers` (7 stage activities: `CreateVoiceTrack`, `CreateWordTiming`, `ProbeMedia`, `PrepareAudioBed`, `AssessImageSafety`, `TransformSensitiveImage`, `NormalizeMedia`).
3. `src/controlplane/api/wiring/render.py`:
   - Bổ sung `_read_tool_version`, `FreshScope`, `ThreadLocalRenderUow`, `StagingResolvingProbe`, `StagingResolvingInspector`, `StagingResolvingRenderer`.
   - Bổ sung `ProductionRenderSources`, `_build_inspector_settings`.
   - Bổ sung `render_activity_deps` và `render_activity_handlers` (6 stage activities: `resolve_render_package`, `validate_render_package`, `reconcile_render`, `render_video`, `inspect_output`, `prepare_output_ready`).
   - Gắn `renderer.lease = runtime.gpu_lease` bảo đảm chia sẻ duy nhất 1 GPU lease.
4. `tools/launcher/launcher.py`:
   - Bổ sung `build_source_sets(manager, workspace_id)` thoả `SourceSetPort`.
   - Bổ sung `open_hooks(manager)` yield `PostgresHookHistory`.
   - Bổ sung `assemble_dfe_handlers(app, *, manager, workspace_id, profile, runtime, connection_factory, clock)` trả đúng 21 stage activities của D, E, F.
   - Sử dụng `importlib.import_module` nạp động các phân hệ `creative`, `catalog`, `ingestion` trong thân hàm để tuân thủ kiểm tra AST `test_launcher_top_level_imports_stdlib_only`.
   - Trong `start_worker`, gọi `handlers.update(assemble_dfe_handlers(...))` ngay sau `assemble_activity_handlers`.
5. `tests/integration/adapt/launch/test_adapt_launch_cli.py`:
   - Thêm 1 dòng monkeypatch `launcher.assemble_dfe_handlers = lambda *a, **kw: {}` trong test `test_worker_stop_waits_for_the_worker_thread_not_a_lost_future`.
6. `tests/integration/prod_wiring/test_pw_w2_launcher_def.py`:
   - Tạo mới tệp kiểm thử tích hợp gồm 9 test case bao phủ toàn diện các ràng buộc của PW-W2.
7. Tệp `src/controlplane/api/wiring/production.py`:
   - **KHÔNG thay đổi** vì `_build_services` đã trả đầy đủ ba dịch vụ `creative`, `voice`, `render`. Giữ nguyên toàn bộ `api_app.state.module_services[...]`, `compose_sources_module` và `compose_hooks_module`.
8. Tệp `tests/integration/adapt/wire/test_adapt_wire_services.py`:
   - **KHÔNG thay đổi dòng nào** (toàn bộ 113 test case đều đạt).

---

## 2. Thiết kế Kiến trúc & Phân quyền

- **Một thể hiện `ExecutionGrantCurrency` dùng chung:** Được khởi tạo tại `assemble_dfe_handlers` từ `connection_factory`, `workspace_id`, `clock`, và truyền xuyên suốt vào `creative_activity_deps`, `voice_activity_deps`, `render_activity_deps`. Điều này bảo đảm thu hồi grant nguyên tử và nhất quán giữa các phân hệ.
- **Một thể hiện `LocalGpuLease` dùng chung:** Được lấy trực tiếp từ `runtime.gpu_lease` và dùng chung cho cả `render_activity_deps` (`deps.render._lease`), `services.render` (`renderer.lease`), và `build_capability_probes`.
- **Ranh giới Artifact Root của Aligner và Voice:** Whisper aligner chỉ mở audio dưới `voice_root` (`runtime.staging_root / 'voice'`), đồng nhất với vị trí lưu trữ của `VoiceArtifactPlacer` và `KokoroConfig.staging_dir`.
- **Vị trí của `SourceSetPort` và `SelectionInputsPort`:** Đặt tại `tools/launcher/launcher.py` thay vì trong `creative.py` để bảo đảm nguyên tắc ranh giới: `src/controlplane/api/wiring/creative.py` không được phép import chéo sang `ingestion` hay `catalog`, thoả mãn bài test tĩnh `test_wiring_modules_do_not_cross_import_subsystems`.

---

## 3. Bảng các dòng đã đổi trong tệp test nghiệm thu

| Tệp | Dòng | Nội dung cũ | Nội dung mới | Lý do |
| --- | --- | --- | --- | --- |
| 	ests/integration/adapt/launch/test_adapt_launch_cli.py | 459 | *(chưa có)* | monkeypatch.setattr(launcher, "assemble_dfe_handlers", lambda *a, **kw: {}) | start_worker nay gọi ssemble_dfe_handlers cần runtime D, E, F thật mà test này cố ý giả lập; bổ sung mock để test dừng luồng chạy độc lập. |
| 	ests/integration/adapt/wire/test_adapt_wire_services.py | - | *(không đổi)* | *(không đổi dòng nào)* | Toàn bộ 113 test case đều xanh, không cần điều chỉnh dòng nào. |

---

## 4. Bảng nhật ký lệnh thực thi

| Bước | Lệnh thực thi | Exit Code | Kết quả |
| --- | --- | --- | --- |
| Bước 3 | `python -m pytest tests/integration/prod_wiring/test_pw_w2_launcher_def.py -q -p no:cacheprovider -o pythonpath=src` | 1 | RED hợp lệ (thiếu symbol `creative_activity_deps` và các cấu phần liên kết). |
| Bước 15 | `python -m pytest tests/integration/prod_wiring/test_pw_w2_launcher_def.py -q -p no:cacheprovider -o pythonpath=src` | 0 | GREEN: 9 passed in 4.03s. |
| Bước 16 | `python -m pytest tests/integration/prod_wiring/test_pw_w1_launcher_core.py -q -p no:cacheprovider -o pythonpath=src` | 0 | GREEN: 8 passed in 5.84s (hồi quy PW-W1 đạt 100%). |
| Bước 17 | `python -m pytest tests/integration/adapt/prod/test_adapt_prod_app.py tests/integration/adapt/launch/test_adapt_launch_cli.py tests/integration/adapt/wire/test_adapt_wire_services.py -q -p no:cacheprovider -o pythonpath=src` | 1 | Xác định chính xác 2 điểm đỏ trong `test_adapt_launch_cli.py` (top-level import và mock `assemble_dfe_handlers`). |
| Bước 20 | `python -m pytest tests/integration/prod_wiring/test_pw_w2_launcher_def.py tests/integration/adapt/prod/test_adapt_prod_app.py tests/integration/adapt/launch/test_adapt_launch_cli.py tests/integration/adapt/wire/test_adapt_wire_services.py -q -p no:cacheprovider -o pythonpath=src` | 0 | GREEN: 187 passed in 29.84s (toàn bộ 4 tệp test đạt). |
| Probe 1 | `git diff --check` | 0 | Không có lỗi khoảng trắng thừa, ký tự xuống dòng hay xung đột mã hoá. |
| Probe 3 | Quét AST `build_creative_services` trong `creative.py` | 0 | 0 tên `Fake*`, `InMemory*`, `Memory*` trong đường production; không có `from src.`. |
| Probe 4 | Kiểm tra AST `production.py` | 0 | Khối `module_services` cùng `compose_sources_module` và `compose_hooks_module` được bảo toàn nguyên vẹn. |
| Probe 23 | Kiểm tra `coveredIds` và symbol launcher | 0 | Khai báo đủ 3 coveredIds và 3 symbol bắt buộc trong launcher. |

---

## 5. Quyết định mặc định D8 và GIẢ ĐỊNH

1. **GIẢ ĐỊNH D8-01 (Thời gian ân hạn Orphan):** Thời gian chờ dọn dẹp các tiến trình hoặc tài nguyên mồ côi được ấn định là 60 giây.
2. **GIẢ ĐỊNH D8-02 (Cấu hình CreativeSettings):** Khi profile hoặc tham số không quy định cụ thể:
   - `target_range`: min 60.0s, max 70.0s (dựa trên khoảng thời lượng video chuẩn).
   - `language_policy`: ngôn ngữ mặc định 'en', tốc độ đọc 150.0 WPM (2.5 từ/giây).
   - `requested_angle_count`: 2 góc bài viết mỗi vòng tin.
   - `preset_revision_ref`: lấy preset đầu tiên trong cấu hình hoặc mặc định 'preset-default'.
   - `variation_policy_revision`: 'profile-{profile.revision}'.
3. **GIẢ ĐỊNH D8-03 (Cấu hình VoiceSettings):** `duration_policy`: (60000, 70000) ms; `provider_route_ref`: 'kokoro-local'.
4. **GIẢ ĐỊNH D8-04 (Cấu hình SelectionInputs):** `safety_policy` có revision 'safe-r{rev}', `allowed_availability=('AVAILABLE',)`, trọng số chọn lọc: ngữ nghĩa 0.6, kỹ thuật 0.4, phạt dùng gần đây 0.1.

---

## 6. Ánh xạ coveredIds

- **PW-W2-01:** Ráp đầy đủ phụ thuộc production cho D, E, F và đăng ký 21 stage activities qua `creative_handler`, `voice_handler`, `render_handler` vào worker của launcher.
  - *Được kiểm chứng qua test:* `test_every_stage_activity_has_a_bound_handler`, `test_assembly_reads_no_database_row_and_loads_no_model`.
- **CT-WF-004:** Quản lý vòng đời và phân quyền cấp phát thực thi với duy nhất một `ExecutionGrantCurrency`.
  - *Được kiểm chứng qua test:* `test_d_e_f_deps_use_execution_grant_currency`.
- **CT-WF-006:** Quản lý tài nguyên phần cứng chia sẻ một `LocalGpuLease` và cô lập thư mục âm thanh của Whisper aligner.
  - *Được kiểm chứng qua test:* `test_one_local_gpu_lease_is_shared`, `test_aligner_opens_only_the_voice_artifact_root`.

---

## 7. Các hạng mục mở (Open Items) & Trạng thái kích hoạt

- **OI-PW-W2-01 (Nguồn dữ liệu SourceSetPort):** Cần nguồn dữ liệu bài viết thật trong `cp_articles` và `cp_article_revisions` để `build_source_set` giải quyết. Trong môi trường thiếu dữ liệu, hệ thống fail-closed với lỗi `INPUT_NOT_READY`.
- **OI-PW-W2-02 (Nguồn ứng viên Asset Catalog):** Cần thư viện hook và media assets được nạp dữ liệu thật trong catalog C. Khi thiếu seed image hoặc visual hook, hệ thống fail-closed với `INPUT_NOT_READY`.
- **OI-PW-W2-03 (Bảng Variant Reservations):** Cần tích hợp luồng ghi nhận đặt chỗ biến thể thật trên `cp_variant_reservations`.
- **OI-PW-W2-04 (Nguồn Render Package Input):** Phụ thuộc vào việc lưu trữ kết quả chọn lọc tài nguyên của D trong `cp_creative_selections`.
- **Các mục còn treo từ PW-E3:** OI-PW-E3-01, OI-PW-E3-02, OI-PW-E3-04.
- **Ghi chú ranh giới:** Các lớp `InMemory` và `Fake` ở cấp module của `storage.py` và `config_security.py` là hồ sơ test nằm ngoài owned paths của PW-W2, hoàn toàn không được dùng trong đường dẫn runtime production.
- **Khóa an toàn:** Trạng thái PRODUCTION_ACTIVATION_BLOCKED tiếp tục được duy trì cho đến khi hoàn tất nghiệm thu toàn diện cấp hệ thống.
