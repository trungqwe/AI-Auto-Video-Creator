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

| STT | Lệnh kiểm | Exit code | Kết quả thực tế |
| --- | --- | --- | --- |
| 1 | `git diff --check` | 0 | Không có lỗi khoảng trắng thừa, ký tự lạ hoặc conflict marker. |
| 2 | `python -m pytest tests/contract/test_bindings.py -q -p no:cacheprovider` | 0 | 293 passed in 0.36s (phủ toàn bộ 20 binding manifest và fixtures tương ứng). |
| 3 | `python -c "import pathlib; t = pathlib.Path('docs/parallel-delivery/ownership-and-locks.yaml').read_text(encoding='utf-8'); assert 'src/controlplane/api/wiring/**' in t and 'tests/integration/catalog/**' in t"` | 0 | Khẳng định tồn tại `src/controlplane/api/wiring/**` và `tests/integration/catalog/**` trong ownership-and-locks.yaml. |
| 4 | `python -m pytest tests/unit/config/test_j_route_binding.py tests/unit/voice/test_e14_tts_route_invocation.py tests/unit/creative/test_d04_ai_route_invocation.py -q -p no:cacheprovider` | 0 | 216 passed in 0.23s (phần tử valid thứ hai thêm vào `j-provider-route` không gây hồi quy test hiện có). |
| 5 | Probe (1): Mẫu path mới và LOCK-H (`python -c "import pathlib; t = pathlib.Path('docs/parallel-delivery/ownership-and-locks.yaml').read_text(encoding='utf-8'); p = ['tests/integration/ingestion/**', ...]; assert ..."`) | 0 | Khớp toàn bộ assertions; 13 mẫu mới duy nhất, đủ 16 lock H, wiring nằm trong khối PATH-COMPOSITION-ROOT trước PATH-CONTRACT-SOURCE. |
| 6 | Probe (2): Oracle test ID trong catalog (`python -c "import pathlib, re; c = pathlib.Path('docs/10-test-strategy.md').read_text(encoding='utf-8'); ...; print(len(ids), 'oracle test ids all in catalog')"`) | 0 | Nguyên văn output: 33 oracle test ids all in catalog. |
| 7 | Probe (3): schema_version & recovery_epoch string (`python -c "import json, pathlib; bad = [p.name for p in pathlib.Path('docs/parallel-delivery/bindings').glob('*.json') ...]; assert not bad, bad"`) | 0 | Khớp assertion; không có trường nào mang kiểu số hay kiểu khác string. |
| 8 | Probe (4): Hash contracts & `CONTRACT-STATE-MACHINES` (`python -c "import hashlib, pathlib; r = pathlib.Path('`docs/parallel-delivery/contract-registry.yaml`').read_text(encoding='utf-8'); ..."`) | 0 | Khớp assertion; hash 13 contracts nguyên vẹn, `CONTRACT-STATE-MACHINES` không bị sửa đổi (2cab18e858b2e78eb3a578b5a64568619d20c7cb09fed2cb7766bc0636fb9f28). |

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
- Xác nhận vị trí wiring: mẫu `src/controlplane/api/wiring/**` nằm ở dòng 222 bên trong khối PATH-COMPOSITION-ROOT (dòng 215–224), nằm trước khối PATH-CONTRACT-SOURCE (dòng 226).

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
| capability-b-ingestion.md | B mục 3 (#1) | docs/modules/capability-b-ingestion.md:9-10 | Cập nhật scope, path phân quyền B. |
| capability-b-ingestion.md | B mục 3 (#2) | docs/modules/capability-b-ingestion.md:25-27 | Đính chính port tiếp nhận tài liệu thô CT-SRC-006 và CT-CNT-001. |
| capability-b-ingestion.md | B mục 3 (#3) | docs/modules/capability-b-ingestion.md:30-32 | Đính chính port cung cấp snapshot CT-AI-001 (-d-production-snapshot). |
| capability-b-ingestion.md | B mục 3 (#4) | docs/modules/capability-b-ingestion.md:37-39 | Đính chính port đánh giá cập nhật CT-CNT-005 và EventUpdateEvaluation. |
| capability-b-ingestion.md | B mục 3 (#5) | docs/modules/capability-b-ingestion.md:44-46 | Đính chính gate Implementation Authorized. |
| capability-b-ingestion.md | B mục 3 (#6) | docs/modules/capability-b-ingestion.md:53-54 | DoD bullet 1: provenance và canonical fingerprint bất biến. |
| capability-b-ingestion.md | B mục 3 (#7) | docs/modules/capability-b-ingestion.md:57-58 | DoD bullet 5: snapshot idempotent. |
| capability-b-ingestion.md | B mục 3 (#8) | docs/modules/capability-b-ingestion.md:67 | Thêm path `tests/integration/ingestion/**`.. |
| capability-b-ingestion.md | B mục 3 (#9) | docs/modules/capability-b-ingestion.md:81-82 | Cập nhật lệnh kiểm thử tự động oracle est_article_collector.py. |
| capability-b-ingestion.md | B mục 3 (#10) | docs/modules/capability-b-ingestion.md:87-89 | Đính chính invariant INV-004. |
| capability-c-storage.md | C mục 2 (#1) | docs/modules/capability-c-storage.md:32 | Đính chính port truy vấn media CT-MED-005 và hook CT-MED-006. |
| capability-c-storage.md | C mục 2 (#2) | docs/modules/capability-c-storage.md:33 | Đính chính port ghi nhận lượt dùng CT-MED-008 trong UoW. |
| capability-c-storage.md | C mục 2 (#3) | docs/modules/capability-c-storage.md:61-63 | Invariant INV-005, INV-008, INV-010, INV-017. |
| capability-c-storage.md | C mục 2 (#4) | docs/modules/capability-c-storage.md:51 | DoD bullet 2: Byte và SHA-256 thuộc artifact version của Module I. |
| capability-c-storage.md | C mục 2 (#5) | docs/modules/capability-c-storage.md:53 | DoD bullet 4: C cung cấp truy vấn và candidate độc lập. |
| capability-c-storage.md | C mục 2 (#6) | docs/modules/capability-c-storage.md:70, 85 | Thêm path `tests/integration/catalog/**`. và lệnh pytest est_catalog_hooks.py. |
| capability-c-storage.md | C mục 2 (#7) | docs/modules/capability-c-storage.md:96 | Mục 9: State machine CT-STATE-005, CT-STATE-006 là tài nguyên hội tụ chung. |
| capability-c-storage.md | C mục 2 (#8) | docs/modules/capability-c-storage.md:97 | Mục 9: Test ID lấy từ catalog docs/10-test-strategy.md. |
| capability-c-storage.md | C mục 2 (#9) | docs/modules/capability-c-storage.md:98 | Mục 9: CT-STATE-012 có cạnh VERIFIED → MISSING không phục hồi. |
| capability-d-scripting.md | D (a)–(c) | docs/modules/capability-d-scripting.md:9-10, 26-30 | Đính chính scope, nhận snapshot nội dung CT-AI-001, nhận candidate CT-MED-005 và CT-MED-006. |
| capability-d-scripting.md | D (g)–(l) | docs/modules/capability-d-scripting.md:32-41, 49-70, 85 | Đính chính port CT-AI-004, CT-ORC-012, gate, DoD, path `tests/integration/creative/**`. và lệnh test oracle. |
| capability-e-voice.md | E (f)–(j) | docs/modules/capability-e-voice.md:9-14, 23-39 | Đính chính scope, contract_refs, CT-AI-004, route CT-AI-ROUTE-001, audio bed CT-PROC-001. |
| capability-e-voice.md | E (k)–(o) | docs/modules/capability-e-voice.md:46-57, 65, 78-86 | Đính chính gate, DoD, path `tests/integration/voice/**`., lệnh test oracle và invariants INV-001, INV-004. |
| capability-f-rendering.md | F (f)–(j) | docs/modules/capability-f-rendering.md:9-10, 25-39, 48-50 | Đính chính scope, render package CT-RND-002, timing CT-TTS-001, CT-RND-005, gate. |
| capability-f-rendering.md | F (k)–(n) | docs/modules/capability-f-rendering.md:59-62, 69, 85-91 | Đính chính DoD, path `tests/integration/render/**`., lệnh test oracle và invariants INV-006, INV-010. |
| capability-g-orchestration.md | G ERR-G-01..04 | docs/modules/capability-g-orchestration.md:15-37 | Đính chính scope, contract_refs, port lệnh CT-API-002, phát luồng CT-API-005. |
| capability-g-orchestration.md | G ERR-G-05..08 | docs/modules/capability-g-orchestration.md:53-70, 87-90 | Đính chính gate, DoD UoW atomic completion, idempotent dispatch và invariants INV-009, INV-010. |
| capability-j-providers.md | J ERR-J-01 | docs/modules/capability-j-providers.md:56-57 | Loại bỏ mock giả lập, kiểm thử route chuẩn với fixture j-provider-route. |
| cceptance-matrix.yaml | R09–R13 | docs/parallel-delivery/acceptance-matrix.yaml:102-155 | Cập nhật contract_refs, mô tả và trỏ test_suite thật cho `TASK-CAP-E-VOICE` và `TASK-CAP-F-RENDERING`. |

## Catalog test

- Đăng ký bộ test bảo mật SSRF cho Phân hệ A: TST-SEC-SSRF-001 đến TST-SEC-SSRF-005 tại docs/10-test-strategy.md mục 35.1 (dòng 1207–1215), bao gồm từ chối fail-closed cho loopback, private IPv4/IPv6, link-local, cloud metadata service (169.254.169.254) và DNS rebinding.
- Quy ước corpus có version: mục 35.2 (dòng 1217–1232), cấu trúc thư mục `tests/fixtures/corpora/<corpus-name>/<version>/...` với trường metadata corpus_version (chuỗi dạng SemVer x.y.z), đăng ký corpus ban đầu `a`a-malicious-url-corpus` phiên bản 1.0.0.
- Các test ID giao diện `TST-UX-*` của Phân hệ H được ghi rõ chưa đăng ký tại mục 35.3 (dòng 1234–1236) do H tự khai báo khi triển khai UI.

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
