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
3. Khối `key_interface_boundaries` trong `contract-registry.yaml` chứa một số định nghĩa thực thể tự đặt (như `DocumentPackage`, `ArticleSnapshot`) không chuẩn hoá; các thực thể này được thay thế hoàn toàn bằng 10 binding mạch nối chuẩn trong thư mục này.

## Seam chưa có binding (follow-up)

Các mạch nối sau đây chưa lập manifest binding trong đợt này và sẽ được bổ sung tiếp:
- H ↔ G: Control API (`CONTRACT-CONTROL-API-STREAM`, trạng thái `active_accepted`, hiện đang được bảo vệ bởi bộ test `tests/m2`).
- A → C: Media discovery (`CT-MED-001`).
- E → C: Rendition (`CT-MED-003`).
- F → I: Video output (`CT-STO-006`).
- J → mọi phân hệ: Configuration bundle (`CT-CFG-002`).

Bất kỳ phân hệ nào cần tương tác với các seam chưa có binding trên đều phải mở một slice binding trước theo nguyên tắc fail-closed.
