# Binding mạch nối giữa phân hệ

Mục đích: Binding là bản khoá máy đọc được của các trường và kiểu dữ liệu tại mỗi mạch nối (seam) giữa hai phân hệ trở lên, được rút trực tiếp từ các hợp đồng chuẩn trong `docs/09-contracts`. Nguồn contract gốc vẫn là tài nguyên dành riêng và không bị sửa.

## Danh sách seam

| Seam | Phân hệ | contract_ref | Tệp nguồn | Mục | Phiên bản |
| --- | --- | --- | --- | --- | --- |
| `a-b-collected-document` | A, B | CONTRACT-SOURCE-CONTENT | docs/09-contracts/04-source-content-contracts.md | CT-SRC-006, CT-CNT-001 | 1.0.0 |
| `b-d-production-snapshot` | B, C, D, G, J | CONTRACT-CREATIVE-AI | docs/09-contracts/06-creative-ai-contracts.md | CT-AI-001 | 1.0.0 |
| `c-d-media-candidates` | C, D | CONTRACT-CONTENT-MEDIA | docs/09-contracts/05-content-media-contracts.md | CT-MED-005 | 1.0.0 |
| `d-e-f-voice-timing` | D, E, F | CONTRACT-MEDIA-PROCESSING | docs/09-contracts/07-media-processing-contracts.md | CT-TTS-001, CT-SUB-001 | 1.0.0 |
| `domain-event-envelope` | A, B, C, D, E, F, G, H, I, J | CONTRACT-DOMAIN-EVENTS | docs/09-contracts/02-domain-events.md | CT-EVT-002, CT-EVT-003 | 1.0.0 |
| `f-render-package` | C, D, E, F, I | CONTRACT-RENDER-QUALITY | docs/09-contracts/08-render-quality-contracts.md | CT-RND-002, CT-RND-003 | 1.0.0 |
| `g-activity-execution` | A, B, C, D, E, F, G, I, J | CONTRACT-WORKFLOW-EXECUTION | docs/09-contracts/03-workflow-and-execution.md | CT-WF-003, CT-WF-006 | 1.0.0 |
| `g-c-i-completion` | C, F, G, I | CONTRACT-ORCHESTRATION | docs/09-contracts/09-orchestration-contracts.md | CT-ORC-008, CT-ORC-009 | 1.0.0 |
| `i-artifact-version` | A, C, E, F, G, I | CONTRACT-STORAGE | docs/09-contracts/10-storage-contracts.md | CT-STO-001 | 1.0.0 |
| `j-provider-route` | D, E, J | CONTRACT-CONFIG-SECURITY | docs/09-contracts/11-configuration-security-contracts.md | CT-AI-ROUTE-001 | 1.0.0 |
| `h-g-control-api` | G, H | CONTRACT-CONTROL-API-STREAM | docs/09-contracts/01-control-api-and-stream.md | CT-API-002, CT-API-005, CT-API-007, CT-API-008 | 1.0.0 |
| `a-b-d-article-event-handoff` | A, B, D | CONTRACT-SOURCE-CONTENT | docs/09-contracts/04-source-content-contracts.md | CT-SRC-006, CT-CNT-003, CT-CNT-005 | 1.0.0 |
| `c-media-registration-and-hooks` | A, C, D, E | CONTRACT-CONTENT-MEDIA | docs/09-contracts/05-content-media-contracts.md | CT-MED-001, CT-MED-003, CT-MED-004, CT-MED-006 | 1.0.0 |
| `d-e-script-text` | D, E | CONTRACT-CREATIVE-AI | docs/09-contracts/06-creative-ai-contracts.md | CT-AI-004 | 1.0.0 |
| `e-processing-audio-bed` | E, F, G | CONTRACT-MEDIA-PROCESSING | docs/09-contracts/07-media-processing-contracts.md | CT-PROC-001, CT-PROC-002, CT-AUD-001 | 1.0.0 |
| `f-g-output-ready` | F, G | CONTRACT-RENDER-QUALITY | docs/09-contracts/08-render-quality-contracts.md | CT-RND-005 | 1.0.0 |
| `d-g-variant-reservation` | D, G | CONTRACT-ORCHESTRATION | docs/09-contracts/09-orchestration-contracts.md | CT-ORC-012 | 1.0.0 |
| `i-storage-output-path` | D, F, G, I | CONTRACT-STORAGE | docs/09-contracts/10-storage-contracts.md | CT-STO-004, CT-STO-006, CT-STO-011 | 1.0.0 |
| `j-config-bundle` | A, B, C, D, E, F, G, H, I, J | CONTRACT-CONFIG-SECURITY | docs/09-contracts/11-configuration-security-contracts.md | CT-CFG-002 | 1.0.0 |
| `j-account-capability` | G, H, J | CONTRACT-CONFIG-SECURITY | docs/09-contracts/11-configuration-security-contracts.md | CT-ACC-001, CT-SEC-001, CT-CAP-002, CT-CAP-003 | 1.0.0 |

## Định dạng contract-binding/v1

Mỗi tệp manifest định dạng JSON tuân thủ schema `contract-binding/v1` với các khoá:
- `schema`: phiên bản schema của manifest (cố định `contract-binding/v1`).
- `seam`: định danh mạch nối viết thường dạng kebab-case khớp tên tệp.
- `binding_id`: mã định danh duy nhất bắt đầu bằng tiền tố `BINDING-`.
- `binding_version`: phiên bản ngữ nghĩa (SemVer) của binding, khởi đầu `1.0.0`.
- `modules`: danh sách các phân hệ tham gia mạch nối (tối thiểu 2 phân hệ, thuộc tập A–J).
- `producer`: phân hệ sinh payload chính.
- `consumers`: danh sách các phân hệ tiêu thụ payload.
- `input_providers`: (tuỳ chọn) các phân hệ cung cấp đầu vào phụ.
- `contract_ref`: mã định danh hợp đồng nguồn trong registry, bắt đầu bằng `CONTRACT-`.
- `source`: đối tượng chỉ định nguồn hợp đồng chuẩn gồm `path` (bắt đầu bằng `docs/09-contracts/`), `sections` (danh sách các mục tương ứng trong văn bản hợp đồng) và `sha256` (mã băm SHA-256 chính xác của tệp hợp đồng nguồn).
- `compatibility`: chính sách tương thích gồm `mode` (`additive_optional_only`) và `breaking_change` (`increment_major_binding_version_via_MIGRATE_bindingRefs`).
- `field_naming`: quy ước đặt tên trường (`snake_case_derived_from_contract_text`).
- `entities`: danh sách các thực thể trao đổi qua mạch nối. Mỗi thực thể khai báo `name`, `section`, danh sách `fields` (mỗi trường gồm `name`, `type`, `required`, tuỳ chọn `items`, `enum`), cùng tuỳ chọn `forbidden_fields` và `constraints`.

Các kiểu dữ liệu hợp lệ: `string`, `integer`, `number`, `boolean`, `object`, `array`, `sha256`, `datetime`.
Ràng buộc `monotonic_word_timings`: áp dụng cho thực thể phụ đề / từ vựng (`WordTiming`), yêu cầu mảng `words` chứa các phần tử có `start_ms` và `end_ms` là số nguyên không âm tăng đơn điệu (`0 <= start_ms < end_ms`), không giảm so với từ trước và kết thúc không vượt quá `voice_duration_ms` (nếu có).

## Cửa sổ tương thích

Trong lúc các phân hệ làm song song, binding chỉ được thêm trường tuỳ chọn; đổi phá vỡ (xoá, đổi tên, đổi kiểu trường, thêm trường bắt buộc, thu hẹp enum) thì tăng phiên bản major của binding và đi qua MIGRATE (bindingRefs).

Consumer bắt buộc bỏ qua các trường lạ chưa biết để đảm bảo khả năng tương thích tiến. Khi consumer gặp phiên bản binding không hỗ trợ, hệ thống phải xử lý fail-closed theo nguyên tắc CT-CMN-012 và `version_policy` được quy định trong `contract-registry.yaml`.

## Phát hiện drift

Giá trị `source.sha256` trong mỗi manifest binding phải khớp chính xác với mã băm SHA-256 hiện tại của tệp hợp đồng nguồn tại `docs/09-contracts/`. Bộ kiểm thử `tests/contract/test_bindings.py` sẽ phát hiện drift và báo lỗi ngay khi có bất kỳ sự thay đổi nào từ phía hợp đồng nguồn. Khi hợp đồng nguồn thay đổi, đội ngũ tích hợp phải mở một slice công việc binding mới để rà soát và cập nhật; tuyệt đối không tự ý sửa hash âm thầm.

## Fixture

Mỗi seam được gán một bộ fixture tương ứng tại `tests/fixtures/contracts/<seam>/payloads.json`. Các phân hệ sử dụng bộ fixture này và cơ chế fake đối tác phụ thuộc để phát triển độc lập cho tới khi gói hội tụ thực hiện kết nối thật.

## Quyết định mặc định (D8)

1. Tên trường `snake_case` được suy diễn trực tiếp từ mô tả nghiệp vụ của contract khi văn bản gốc chưa đặt tên biến cụ thể; đây là GIẢ ĐỊNH đặt tên chuẩn hóa, mọi thay đổi tên sau này phải đi qua quy trình MIGRATE.
2. Các giá trị enum chưa được chốt danh sách đầy đủ trong contract được tạm thời khai báo ở kiểu `string`.
3. Khối `key_interface_boundaries` trong `contract-registry.yaml` chứa một số định nghĩa thực thể tự đặt (như `DocumentPackage`, `ArticleSnapshot`) không chuẩn hoá; các thực thể này được thay thế hoàn toàn bằng các binding mạch nối chuẩn (20 manifest sau CP-2D-REGISTRY) trong thư mục này.


## Ánh xạ seam logic sang manifest (CP-2D-REGISTRY)

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

## Seam còn lại chưa có binding

Các hợp đồng CT-SRC-001..005, CT-SRC-003A, CT-MED-002, CT-MED-007, CT-MED-008, CT-MED-009, CT-HOOK-001, CT-HOOK-002, CT-STO-002, CT-STO-003, CT-STO-005, CT-STO-007..010, CT-SEC-002, CT-COST-001 chưa có binding seam; chỉ dùng trong phạm vi một phân hệ hoặc qua workflow G; cần seam mới thì mở slice binding trước theo nguyên tắc fail-closed.
