# Báo cáo CP-2D-REGISTRY

## Tệp đã tạo hoặc sửa

### Tệp cấu hình phân quyền và hợp đồng (3 tệp)
- `docs/parallel-delivery/ownership-and-locks.yaml`
- `docs/parallel-delivery/contract-registry.yaml`
- `docs/parallel-delivery/acceptance-matrix.yaml`

### Tệp manifest contract binding mới (10 tệp)
- `docs/parallel-delivery/bindings/a-b-d-article-event-handoff.json`
- `docs/parallel-delivery/bindings/c-media-registration-and-hooks.json`
- `docs/parallel-delivery/bindings/d-e-script-text.json`
- `docs/parallel-delivery/bindings/d-g-variant-reservation.json`
- `docs/parallel-delivery/bindings/e-processing-audio-bed.json`
- `docs/parallel-delivery/bindings/f-g-output-ready.json`
- `docs/parallel-delivery/bindings/h-g-control-api.json`
- `docs/parallel-delivery/bindings/i-storage-output-path.json`
- `docs/parallel-delivery/bindings/j-account-capability.json`
- `docs/parallel-delivery/bindings/j-config-bundle.json`

### Tệp fixture payload mới (10 tệp)
- `tests/fixtures/contracts/a-b-d-article-event-handoff/payloads.json`
- `tests/fixtures/contracts/c-media-registration-and-hooks/payloads.json`
- `tests/fixtures/contracts/d-e-script-text/payloads.json`
- `tests/fixtures/contracts/d-g-variant-reservation/payloads.json`
- `tests/fixtures/contracts/e-processing-audio-bed/payloads.json`
- `tests/fixtures/contracts/f-g-output-ready/payloads.json`
- `tests/fixtures/contracts/h-g-control-api/payloads.json`
- `tests/fixtures/contracts/i-storage-output-path/payloads.json`
- `tests/fixtures/contracts/j-account-capability/payloads.json`
- `tests/fixtures/contracts/j-config-bundle/payloads.json`

### Tệp hướng dẫn và fixture cập nhật (2 tệp)
- `docs/parallel-delivery/bindings/README.md`
- `tests/fixtures/contracts/j-provider-route/payloads.json`

### Tệp chiến lược kiểm thử (1 tệp)
- `docs/10-test-strategy.md`

### Tệp tài liệu năng lực các phân hệ (7 tệp)
- `docs/modules/capability-b-ingestion.md`
- `docs/modules/capability-c-storage.md`
- `docs/modules/capability-d-scripting.md`
- `docs/modules/capability-e-voice.md`
- `docs/modules/capability-f-rendering.md`
- `docs/modules/capability-g-orchestration.md`
- `docs/modules/capability-j-providers.md`

### Tệp theo dõi tiến độ và bàn giao (3 tệp)
- `README.md`
- `CHANGELOG.md`
- `HANDOFF.md`

## Lệnh đã chạy

Các lệnh kiểm tra được thực thi bằng interpreter khoá của lane (`C:\Users\Admin\orca\workspaces\AI-Auto-Video-Creator\.local-tools\runtime\33f06a7a\venv\Scripts\python.exe`).

| STT | Mã | Exit code | Kết quả thực tế |
| --- | --- | --- | --- |
| 1 | L1 | 0 | Không có cảnh báo khoảng trắng thừa hay conflict marker. |
| 2 | L2 | 0 | 293 passed in 0.36s |
| 3 | L3 | 0 | Assert qua: `src/controlplane/api/wiring/**` và `tests/integration/catalog/**` có trong ownership-and-locks.yaml. |
| 4 | L4 | 0 | Assert qua: wiring nằm trong PATH-COMPOSITION-ROOT và đủ LOCK-H-01..16. |
| 5 | L5 | 0 | 33 ids [] |
| 6 | L6 | 0 | Assert qua: không fixture nào khai schema_version hoặc recovery_epoch bằng số. |
| 7 | L7 | 0 | 50 passed in 0.06s |
| 8 | L8 | 0 | Assert qua: BL-CV-01/06 PENDING, không có ký tự hỏng hay lệnh bị cắt bằng ba chấm. |
| 9 | L9 | 0 | Không có cảnh báo khoảng trắng thừa hay conflict marker. |

```text
L1: git diff --check
L2: python -m pytest tests/contract/test_bindings.py -q -p no:cacheprovider
L3: python -c "import pathlib; t = pathlib.Path('docs/parallel-delivery/ownership-and-locks.yaml').read_text(encoding='utf-8'); assert 'src/controlplane/api/wiring/**' in t and 'tests/integration/catalog/**' in t"
L4: python -c "import pathlib; t = pathlib.Path('docs/parallel-delivery/ownership-and-locks.yaml').read_text(encoding='utf-8'); a = t.index('id: PATH-COMPOSITION-ROOT'); b = t.index('id: PATH-CONTRACT-SOURCE'); w = t.index('src/controlplane/api/wiring/**'); assert a < w < b, 'wiring must sit in PATH-COMPOSITION-ROOT'; assert t.count('src/controlplane/api/wiring/**') == 1; assert all(('id: LOCK-H-' + str(n).zfill(2)) in t for n in range(1, 17)), 'LOCK-H-01..16'"
L5: python -c "import pathlib, re; c = pathlib.Path('docs/10-test-strategy.md').read_text(encoding='utf-8'); ids = set(); [ids.update(re.findall('TST-[A-Z0-9]+(?:-[A-Z0-9]+)+', p.read_text(encoding='utf-8'))) for p in pathlib.Path('docs/implementation').glob('*/slices.md')]; miss = sorted(i for i in ids if i not in c); print(len(ids), 'ids', miss); assert not miss, miss"
L6: python -c "import pathlib, re; q = chr(34); r = re.compile(q + '(schema_version|recovery_epoch)' + q + ' *: *[0-9]'); bad = [str(p) for p in pathlib.Path('tests/fixtures/contracts').glob('*/payloads.json') if r.search(p.read_text(encoding='utf-8'))]; assert not bad, bad"
L7: python -m pytest tests/unit/config/test_j_route_binding.py -q -p no:cacheprovider
L8: python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/cp-2d-registry/report.md').read_text(encoding='utf-8'); assert 'BL-CV-01: PENDING' in t and 'BL-CV-06: PENDING' in t; assert chr(65533) not in t; assert ' est_' not in t and '| cceptance' not in t and ('a' + chr(96) + 'a-malicious') not in t; assert 'Đính chính' in t; assert t.count('...') == 0, 'truncated command'"
L9: git diff --check
```

## Rebase lên fe206ac

Rebase lên integration head fe206ac52815f87769890b77efc7d8c51807528f: thành công, không có xung đột, cây làm việc sạch.

| STT | Lệnh kiểm | Exit code | Kết quả thực tế |
| --- | --- | --- | --- |
| 2 | `python -m pytest tests/unit -q -p no:cacheprovider` | 1 | 4 failed, 7353 passed, 1 warning, 2416 subtests passed in 11.92s |
| 3 | `python -m pytest tests/contract/test_bindings.py -q -p no:cacheprovider` | 0 | 293 passed in 0.42s |
| 4 | `python -c "import pathlib; t = pathlib.Path('docs/parallel-delivery/ownership-and-locks.yaml').read_text(encoding='utf-8'); assert 'src/controlplane/api/wiring/**' in t and 'tests/integration/catalog/**' in t"` | 0 | Khớp assertion; cả hai mẫu path đều tồn tại trong ownership-and-locks.yaml |
| 5 | `git diff --check` | 0 | Không có lỗi khoảng trắng thừa, ký tự lạ hoặc conflict marker |

Test unit hỏng thuộc tệp ngoài owned paths (DEPENDENCY_GAP): 4 test unit bị FAILED thuộc các tệp ngoài owned paths của CP-2D-REGISTRY:
- `tests/unit/control_ui/test_h_metadata_update.py::test_modules_directory_has_no_init_file` (tệp liên quan: `src/controlplane/api/routes/modules/__init__.py` và `tests/unit/control_ui/test_h_metadata_update.py`)
- `tests/unit/control_ui/test_h_problem_detail.py::test_modules_directory_has_no_init_file` (tệp liên quan: `src/controlplane/api/routes/modules/__init__.py` và `tests/unit/control_ui/test_h_problem_detail.py`)
- `tests/unit/control_ui/test_h_read_only_listing.py::test_modules_directory_has_no_init_file` (tệp liên quan: `src/controlplane/api/routes/modules/__init__.py` và `tests/unit/control_ui/test_h_read_only_listing.py`)
- `tests/unit/creative/test_d01_package_layout.py::PackageLayoutTests::test_package_modules_have_no_forbidden_imports` (tệp liên quan: `src/creative/adapters/real_route_executor.py` và `tests/unit/creative/test_d01_package_layout.py`)
CP-2D-REGISTRY không sửa.

## Ownership

Trích số dòng trong tệp `docs/parallel-delivery/ownership-and-locks.yaml`:
- 13 mẫu path mới được phân quyền chuẩn xác, không trùng lặp với bất kỳ owner nào khác:
  - `tests/integration/ingestion/**`: dòng 131 (thuộc PATH-SRC-INGESTION, Phân hệ B)
  - `tests/integration/catalog/**`: dòng 140 (thuộc PATH-SRC-CATALOG, Phân hệ C)
  - `tests/integration/creative/**`: dòng 149 (thuộc PATH-SRC-CREATIVE, Phân hệ D)
  - `tests/integration/voice/**`: dòng 158 (thuộc PATH-SRC-VOICE, Phân hệ E)
  - `tests/integration/render/**`: dòng 167 (thuộc PATH-SRC-RENDER, Phân hệ F)
  - 7 mẫu path của Phân hệ H (theo yêu cầu YC-HT-H-01) thuộc PATH-SRC-CONTROL-UI:
    - `src/controlplane/application/projections/**`: dòng 188
    - `src/controlplane/application/sse/**`: dòng 189
    - `src/controlplane/api/sse/**`: dòng 190
    - `src/controlplane/api/routes/modules/**`: dòng 191
    - `src/controlplane/infrastructure/db/projections/**`: dòng 192
    - `tests/unit/control_ui/**`: dòng 193
    - `tests/integration/control_ui/**`: dòng 194
  - `src/controlplane/api/wiring/**`: dòng 222 (thuộc PATH-COMPOSITION-ROOT)
- Khai báo khóa tài nguyên Phân hệ H: đủ 16 khóa từ LOCK-H-01 (dòng 572) đến LOCK-H-16 (dòng 662).
- Xác nhận vị trí wiring: mẫu `src/controlplane/api/wiring/**` nằm ở dòng 222 bên trong khối PATH-COMPOSITION-ROOT (dòng 218–225), nằm trước khối PATH-CONTRACT-SOURCE (dòng 226).

## Ánh xạ seam sang manifest

| Manifest | Seam logic | Thực thể |
| --- | --- | --- |
| c-media-registration-and-hooks | A→C, E→C, C→D (CT-MED-004, CT-MED-006; CT-MED-005 vẫn ở c-d-media-candidates) | MediaDiscoveryRegistration, MediaDiscoveryResult, RenditionRegistration, ThumbnailCandidate, HookCandidateQuery |
| a-b-d-article-event-handoff | A→B Tier, B→D | SourceTierView, ArticleRevisionAccepted, EventUpdateEvaluation |
| d-e-script-text | D→E | ScriptTextView |
| e-processing-audio-bed | G→E, E→F | ProcessingRequest, ProcessingResult, AudioBedResult |
| d-g-variant-reservation | D↔G | VariantReservationRequest, VariantReservationResult |
| i-storage-output-path | D→I, F→I, I→F | AllocateOutputPathRequest, AllocateOutputPathResult, PersistVideoOutputResult, MaterializeArtifactSetRequest, MaterializeArtifactSetResult |
| f-g-output-ready | F→G | RenderOutputReady |
| j-config-bundle | J→mọi phân hệ, J→F (preset và tool config) | ConfigurationBundleRequest, ConfigurationBundle |
| h-g-control-api | H↔G | ResourceQuery, ProductionCommand, OperationView, OperationStreamItem |
| j-account-capability | H↔J, J→G | ExternalAccountView, SecretUpdateResult, CapacityReservationHint, CapabilityView |

## Quyết định mặc định bổ sung (D8, CP-2D-REGISTRY)

- (a) seam cùng tệp contract nguồn và cùng contract_ref gộp vào một manifest vì `source.path` là duy nhất cho mỗi manifest, mỗi seam là thực thể có `section` riêng;
- (b) tên trường snake_case và kiểu là GIẢ ĐỊNH theo mục D8 số 1 và 2, enum chưa chốt để `string`;
- (c) `schema_version` và `recovery_epoch` là chuỗi (D8-G-10), manifest mới không khai hai trường này;
- (d) không thực thể nào mang giá trị secret, `UpdateSecret` chỉ có kết quả không chứa giá trị;
- (e) seam đã có binding không tạo lại, `ai_role` là chuỗi mở và fixture `j-provider-route` có thêm vai trò TTS `voice_synthesis` (tên là GIẢ ĐỊNH, J đăng ký vai trò thật).

## Đính chính đã áp dụng

| Tài liệu | Mục đính chính | Vị trí tệp:dòng | Tóm tắt nội dung sửa đổi |
| --- | --- | --- | --- |
| capability-b-ingestion.md | B mục 3 #1 | docs/modules/capability-b-ingestion.md:12, 25 | `DocumentPackage` và CT-SRC-001 thay bằng `CollectedDocumentPackage` (CT-SRC-006) và `CollectedDocumentResolution` (CT-CNT-001), binding `a-b-collected-document`. |
| capability-b-ingestion.md | B mục 3 #2 | docs/modules/capability-b-ingestion.md:25 | Idempotency theo `collected_document_id` + `dedup_policy_revision`, không theo `provenance_hash`. |
| capability-b-ingestion.md | B mục 3 #3 | docs/modules/capability-b-ingestion.md:12, 28 | `ProductionSnapshot` (CT-AI-001) do D sinh, B là input_provider; CT-CNT-002 chỉ là quy tắc bài đại diện. |
| capability-b-ingestion.md | B mục 3 #4 | docs/modules/capability-b-ingestion.md:29 | Sự kiện `ArticleRevisionAccepted`, `DuplicateDocumentResolved`, `EventLinkResolved`, `EventUpdateAccepted` theo envelope CT-EVT-002/003; CT-EVT-001 là ngữ nghĩa chuyển phát. |
| capability-b-ingestion.md | B mục 3 #5 | docs/modules/capability-b-ingestion.md:56 | INV-005 (repost), INV-004 (snapshot giữ refs), INV-006 (EventUpdateAccepted) kèm test ID catalog. |
| capability-b-ingestion.md | B mục 3 #6 | docs/modules/capability-b-ingestion.md:57 | INV-010 và INV-011 không thuộc B; outbox theo CT-EVT-001. |
| capability-b-ingestion.md | B mục 3 #7 | docs/modules/capability-b-ingestion.md:58 | Ngưỡng trùng fingerprint nằm trong dedup policy revision (D8-B-01). |
| capability-b-ingestion.md | B mục 3 #8 | docs/modules/capability-b-ingestion.md:91 | Mỗi collected document một transaction (CT-STATE-003, D8-B-11), không rollback toàn lô. |
| capability-b-ingestion.md | B mục 3 #9 | docs/modules/capability-b-ingestion.md:67 | Thêm `tests/integration/ingestion/**` vào Allowed Paths. |
| capability-b-ingestion.md | B mục 3 #10 | docs/modules/capability-b-ingestion.md:38, 84, 92 | Lệnh pytest theo tệp `tests/unit/ingestion/test_ingestion_resolve_document.py`; schema qua migration REQ-B-CONV-01, không dùng namespace `db:ingestion`. |
| capability-c-storage.md | C mục 2 #1 | docs/modules/capability-c-storage.md:32 | Truy vấn media là CT-MED-005 (binding `c-d-media-candidates`), truy vấn hook là CT-MED-006; CT-HOOK-001 là `ImportHook`. |
| capability-c-storage.md | C mục 2 #2 | docs/modules/capability-c-storage.md:33 | Lượt dùng ghi bằng CT-MED-008 trong UoW của CT-ORC-008/009; CT-STO-002 là `RegisterArtifactLocation` của I. |
| capability-c-storage.md | C mục 2 #3 | docs/modules/capability-c-storage.md:59 | INV-005, INV-008, INV-010, INV-017 (phần C); INV-006 là timeline mode, INV-012 là canary secret. |
| capability-c-storage.md | C mục 2 #4 | docs/modules/capability-c-storage.md:51 | Byte và SHA-256 thuộc artifact version của I (CT-STO-001); `MediaAsset` giữ canonical fingerprint bất biến. |
| capability-c-storage.md | C mục 2 #5 | docs/modules/capability-c-storage.md:53 | C cung cấp truy vấn và candidate độc lập (CT-MED-004, CT-MED-006); ràng buộc hook mỗi plan thuộc D. |
| capability-c-storage.md | C mục 2 #6 | docs/modules/capability-c-storage.md:69, 85 | Thêm `tests/integration/catalog/**` vào Allowed Paths; lệnh pytest `tests/unit/catalog/test_catalog_hooks.py`. |
| capability-c-storage.md | C mục 2 #7 | docs/modules/capability-c-storage.md:96 | CT-STATE-005, CT-STATE-006 và migration là tài nguyên dùng chung của gói hội tụ (CONV-C-07, CONV-C-01). |
| capability-c-storage.md | C mục 2 #8 | docs/modules/capability-c-storage.md:97 | Test ID lấy từ catalog docs/10-test-strategy.md, không dùng `TST-CAT-*`; bằng chứng ở docs/delivery-evidence/<task-id>/report.md. |
| capability-c-storage.md | C mục 2 #9 | docs/modules/capability-c-storage.md:98 | CT-STATE-012 có cạnh `VERIFIED → MISSING`, không có cạnh phục hồi từ MISSING, CORRUPT, OUTCOME_UNKNOWN. |
| capability-d-scripting.md | D mục 2 (a)–(c) | docs/modules/capability-d-scripting.md:12, 26, 49–50, 59–60 | Không có `ArticleSnapshot`: D nhận ref qua CT-AI-001 và CT-CNT-003; INV-014 là tái khai thác, thời lượng kiểm ở F; thumbnail nằm trong time range hook (CT-MED-004, CT-RND-003 điều kiện 3). |
| capability-d-scripting.md | D mục 2 (g) | docs/modules/capability-d-scripting.md:57–58 | INV-004 là snapshot bất biến (`TST-INT-INV-004`), INV-013 là StoryAngle khác nhau (`TST-AI-INV-013`). |
| capability-d-scripting.md | D mục 2 (h) | docs/modules/capability-d-scripting.md:26, 31 | Nội dung bài qua CT-AI-001/CT-CNT-003, không qua CT-CNT-002; D là input_provider của `RenderPackage` (CT-RND-002/003, binding `f-render-package`). |
| capability-d-scripting.md | D mục 2 (i) | docs/modules/capability-d-scripting.md:49 | Bỏ hằng 140–165 từ; tốc độ đọc lấy từ policy. |
| capability-d-scripting.md | D mục 2 (j) | docs/modules/capability-d-scripting.md:69 | Thêm `tests/integration/creative/**` vào Allowed Paths. |
| capability-d-scripting.md | D mục 2 (k) | docs/modules/capability-d-scripting.md:85 | Lệnh pytest `tests/unit/creative/test_d08_script_version.py` thay lệnh unittest cũ. |
| capability-d-scripting.md | D mục 2 (l) | docs/modules/capability-d-scripting.md:92 | Release giữ chỗ biến thể là quyền của G (CT-ORC-012); fallback prompt chỉ qua revision J (CT-AI-ROUTE-002). |
| capability-e-voice.md | E mục 2 (f) | docs/modules/capability-e-voice.md:54–56 | INV-007 (`TST-MEDIA-INV-007`), INV-008 (`TST-INT-INV-008`), INV-019 (`TST-QC-INV-019`) theo catalog; tăng đơn điệu là CT-SUB-001 bất biến 1. |
| capability-e-voice.md | E mục 2 (g) | docs/modules/capability-e-voice.md:46 | 61–70 giây là `DURATION_RANGE` (CT-QC-001) kiểm ở F; E ghi `actual_duration_ms`, không hằng trong mã. |
| capability-e-voice.md | E mục 2 (h) | docs/modules/capability-e-voice.md:47 | Sai số ±100 ms là hằng tự đặt, thuộc ROADMAP-OPEN-008 / TEST-OPEN-006. |
| capability-e-voice.md | E mục 2 (i) | docs/modules/capability-e-voice.md:48 | Bỏ hằng LUFS; loudness lấy từ preset audio policy (CT-AUD-001). |
| capability-e-voice.md | E mục 2 (j) | docs/modules/capability-e-voice.md:24–25 | CT-AUD-001 là `PrepareAudioBed`; gọi TTS qua route J (CT-AI-ROUTE-001, binding `j-provider-route`); `VoiceTrackRequest` không mang văn bản, đọc qua `d-e-script-text` hoặc `ScriptTextPort`. |
| capability-e-voice.md | E mục 2 (k) | docs/modules/capability-e-voice.md:12, 15 | E sở hữu probe, analyze, image safety, transform, normalize, audio bed (CT-PROC-001..008, CT-AUD-001); `ProcessedMedia` gồm ảnh và clip, không có lọc tạp âm. |
| capability-e-voice.md | E mục 2 (l) | docs/modules/capability-e-voice.md:65 | Thêm `tests/integration/voice/**` vào Allowed Paths. |
| capability-e-voice.md | E mục 2 (m) | docs/modules/capability-e-voice.md:81 | Lệnh pytest `tests/unit/voice/test_e09_word_timing.py` thay lệnh unittest cũ. |
| capability-e-voice.md | E mục 2 (n) | docs/modules/capability-e-voice.md:88 | Output bất biến, lỗi ghi thành attempt thất bại; retry và fallback do G, engine dự phòng theo `fallback_order` của J; E không cleanup (CT-PROC-008). |
| capability-e-voice.md | E mục 2 (o) | docs/modules/capability-e-voice.md:37 | Slice dùng WAV của `wave` stdlib và fake; kiểm rò rỉ bộ nhớ với thư viện thật thuộc CP7. |
| capability-f-rendering.md | F mục 2 (f) | docs/modules/capability-f-rendering.md:58–59 | INV-001, INV-002, INV-009, INV-018 theo catalog; kích thước và thời lượng là gate `OUTPUT_PROFILE_VALID` và `DURATION_RANGE` (CT-QC-001); chuyển giao theo CT-RND-005. |
| capability-f-rendering.md | F mục 2 (g) | docs/modules/capability-f-rendering.md:12, 48–49 | Bỏ hằng 1080x1920, 30 fps, H.264, AAC; output profile theo `output_profile_revision`. |
| capability-f-rendering.md | F mục 2 (h) | docs/modules/capability-f-rendering.md:52 | Bỏ hằng lệch tiếng 50 ms; sai số karaoke là ROADMAP-OPEN-008, QUALITY-OPEN-007, TEST-OPEN-006. |
| capability-f-rendering.md | F mục 2 (i) | docs/modules/capability-f-rendering.md:51 | Thumbnail nằm trong time range hook (CT-RND-003 điều kiện 3, gate `THUMBNAIL_PRESENT`), không cố định 3 giây đầu. |
| capability-f-rendering.md | F mục 2 (j) | docs/modules/capability-f-rendering.md:25, 29 | F resolve `RenderPackage` (CT-RND-002); F trả output ready cho G (CT-RND-005, binding `f-g-output-ready`), không gửi thẳng cho I; CT-QC-001 là `InspectOutput`. |
| capability-f-rendering.md | F mục 2 (k) | docs/modules/capability-f-rendering.md:38, 92 | `LOCK-DESKTOP-GPU` do G cấp; RenderAttempt bất biến, F không xóa tệp, cleanup thuộc I. |
| capability-f-rendering.md | F mục 2 (l) | docs/modules/capability-f-rendering.md:37, 69, 74 | ffmpeg/ffprobe thuộc CONV-F-13 và CP7; thêm `tests/integration/render/**`; `src/controlplane/**` chỉ đọc. |
| capability-f-rendering.md | F mục 2 (m) | docs/modules/capability-f-rendering.md:85 | Lệnh pytest `tests/unit/render/test_f09_karaoke_plan.py` thay lệnh unittest cũ. |
| capability-f-rendering.md | F mục 2 (n) | docs/modules/capability-f-rendering.md:60 | Gate `DURATION_RANGE` fail thì không tạo `VideoOutput` ready; F không tự cắt hay kéo video. |
| capability-g-orchestration.md | ERR-G-01 | docs/modules/capability-g-orchestration.md:71–73 | Allowed Paths là `src/controlplane/domain/application/infrastructure/db/orchestration` cùng `tests/unit` và `tests/integration` orchestration. |
| capability-g-orchestration.md | ERR-G-02 | docs/modules/capability-g-orchestration.md:29 | Lệnh của G là CT-API-005; CT-API-001 là quy tắc request; CT-BAT-001..004 thuộc H; không có pause/resume/cancel (PUC-G-03). |
| capability-g-orchestration.md | ERR-G-03 | docs/modules/capability-g-orchestration.md:34 | Completion UoW là CT-ORC-008 và CT-ORC-009; CT-ORC-002 là `AllocateVideoJob`. |
| capability-g-orchestration.md | ERR-G-04 | docs/modules/capability-g-orchestration.md:60–64 | INV-010 completion lặp, INV-017 ledger và MediaUsage cùng commit, INV-016 epoch cũ, INV-018 allocator; một worker mỗi stage là hệ quả của INV-003. |
| capability-g-orchestration.md | ERR-G-05 | docs/modules/capability-g-orchestration.md:86, 89 | Lệnh pytest `tests/unit/orchestration/test_g_fencing.py`; RED hợp lệ là `ACTIVE → COMPLETED` bỏ qua READY_FOR_COMPLETION (CT-STATE-009). |
| capability-g-orchestration.md | ERR-G-06 | docs/modules/capability-g-orchestration.md:12, 15, 20 | `Batch` gọi là `ProductionBatch` (bảng `cp_production_batches`); `stage_type` theo CT-ORC-003. |
| capability-g-orchestration.md | ERR-G-07 | docs/modules/capability-g-orchestration.md:54 | Ngưỡng admission lấy từ cấu hình J (D8-G-07); `schedule-policy.yaml` không phải ngưỡng sản phẩm. |
| capability-g-orchestration.md | ERR-G-08 | docs/modules/capability-g-orchestration.md:53 | I verify ArtifactLocation trước (`cloud_location_verification_ref`); G không ghi ArtifactLocation trong transaction completion. |
| capability-j-providers.md | ERR-J-01 | docs/modules/capability-j-providers.md:56–58 | INV-012, INV-004, INV-020 đúng catalog; INV-013 là StoryAngle, INV-015 là tombstone nguồn, INV-021 không tồn tại; routing bám CT-AI-ROUTE-001/002. |
| acceptance-matrix.yaml | TASK-CAP-E-VOICE (R09, R10) | docs/parallel-delivery/acceptance-matrix.yaml:99–119 | Thêm `contract_refs` (CT-TTS-001, CT-AI-ROUTE-001; CT-SUB-001), trỏ `test_suite` vào `test_e08_voice_track.py` và `test_e09_word_timing.py` có thật, bỏ hằng loudness. |
| acceptance-matrix.yaml | TASK-CAP-F-RENDERING (R11–R13) | docs/parallel-delivery/acceptance-matrix.yaml:121–152 | Thêm `contract_refs` (CT-RND-002/004; CT-SUB-001; CT-QC-001/002, CT-RND-005), trỏ `test_suite` vào `test_f10_render_command_spec.py`, `test_f09_karaoke_plan.py`, `test_f13_technical_gates.py`, bỏ hằng profile và sai số. |

## Catalog test

- Đăng ký TST-SEC-SSRF-001..005 tại docs/10-test-strategy.md mục 35.1 (dòng 1207–1215): loopback (001), dải riêng RFC 1918 (002), endpoint metadata 169.254.169.254 (003), DNS rebinding và redirect nội bộ (004), scheme ngoài http/https (005).
- Quy ước corpus có version tại mục 35.2 (dòng 1217–1232): `tests/fixtures/corpora/<corpus_id>/v<MAJOR>/` kèm `corpus.manifest.json` ghi `corpus_id`, `corpus_version` (SemVer) và sha256 từng tệp; bảng 10 corpus_id, trong đó `a-malicious-url-corpus` dùng cho TST-SEC-SSRF-001..005. Tên quy ước là GIẢ ĐỊNH; corpus thật do slice sở hữu tạo.
- Mục 35.3 (dòng 1234–1236): `TST-UX-*`, `TST-CAT-*`, `TST-CRE-*`, `TST-STO-SYNC-*` chưa slice nào dùng làm oracle nên chưa đăng ký.
- Oracle: lệnh L5 duyệt mọi test ID `TST-..` trong docs/implementation/*/slices.md và xác nhận đều có trong catalog; ghi số ID và danh sách thiếu đúng như output thực tế của bước chạy L5: 33 ids [].

## BL-CV

BL-CV-01: PENDING
BL-CV-06: PENDING

Cổng GATE-CP-2D-REGISTRY do Control thả khi có Auditor PASS cho slice này; Worker KHÔNG tự thả cổng.

## Giới hạn

- `task-dag.yaml` (các task `TASK-CAP-E-VOICE` và `TASK-CAP-F-RENDERING` còn `contract_refs` rỗng) và `docs/parallel-delivery/M4-CI-*.md` nằm ngoài owned paths của task này nên không sửa đổi.
- Corpus thật sẽ do từng slice sở hữu tương ứng tự tạo trong quá trình triển khai chi tiết.
- Chưa đăng ký các test ID `TST-UX-*` (thuộc Phân hệ H).

## Phạm vi

- Xác nhận chỉ thay đổi các tệp nằm trong danh sách owned paths được giao trong brief.
- Tuyệt đối không sửa đổi các tệp trong `docs/09-contracts/**` (mã băm SHA-256 của toàn bộ 13 tệp hợp đồng đã được kiểm tra khớp 100% với registry).
- Tuyệt đối không thay đổi mục `CONTRACT-STATE-MACHINES` trong `docs/parallel-delivery/contract-registry.yaml` (được bảo tồn nguyên vẹn cho gói hội tụ CP-3C-STATE-EDGES).
