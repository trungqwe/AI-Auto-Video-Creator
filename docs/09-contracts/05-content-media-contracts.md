# 05. Hợp đồng kho media và hook

> Trạng thái: **Bản thiết kế trước triển khai**  
> Chủ sở hữu catalog: C.  
> Chủ sở hữu byte và location: I.  
> Bên chọn sáng tạo: D.

## 1. Ranh giới trách nhiệm

- B/C ghi mối liên hệ media với article/event và provenance.
- C định danh asset logic, metadata, index, analysis, rendition và usage.
- I định danh artifact byte/version/location và thực hiện materialize/sync/cleanup.
- E tạo analysis/rendition kỹ thuật rồi giao C/I commit.
- D query candidate và quyết định chọn; C không tự quyết định câu chuyện.
- F chỉ dùng các asset revision đã khóa trong `RenderPackage`.

## 2. Nhập media discovery

### CT-MED-001 — `RegisterMediaDiscovery`

Input:

- discovery ID;
- source/article/event refs;
- original locator đã qua safety validation;
- media kind candidate;
- caption/alt/context từ nguồn;
- observed time;
- provenance chain;
- content hash nếu đã tải;
- relation như hero image, inline image, embedded clip, official social clip.

Output:

- media asset ref hiện có hoặc mới;
- disposition `new_asset`, `new_provenance`, `duplicate_observation`, `rejected`;
- artifact acquisition operation nếu cần.

Một byte có thể có nhiều provenance. Một media logic có thể có nhiều artifact version/rendition.

## 3. Media asset và rendition

### CT-MED-002 — `MediaAssetView`

| Nhóm trường | Nội dung |
|---|---|
| Identity | `media_asset_id`, kind, canonical fingerprint |
| Provenance | source/article/event refs, original URL, observed time |
| Semantics | people/entities, topics, scene/action, OCR, language, tags |
| Technical | dimensions, duration, codecs, frame rate, audio presence |
| Safety | assessment state, reasons, model/reviewer revision |
| Rights/risk | known, unknown, disputed; evidence refs |
| Availability | cloud/local/original/processed state |
| Renditions | original, normalized, blurred, recolored, thumbnail, extracted frame |
| Usage | count, recent jobs, role trong video |

Trạng thái quyền không chắc chắn không tự chặn sử dụng theo quyết định user, nhưng phải được lưu và truy vấn được.

### CT-MED-003 — `RegisterRendition`

Input:

- source media ref và artifact version;
- transformation specification revision;
- processor/tool version;
- output artifact ref;
- quality/analysis report;
- safety state;
- lineage.

Output: immutable rendition ref.

Không thay byte của rendition cũ. Cùng transformation và cùng input có thể deduplicate theo fingerprint.

## 4. Hook visual và hook audio

### CT-HOOK-001 — `ImportHook`

Hai loại độc lập:

- `visual_hook`: video do user cung cấp, đã làm mờ chủ thể, không có âm thanh bắt buộc;
- `audio_hook`: audio do user cung cấp, được index riêng.

Input:

- artifact ref/import operation;
- hook kind;
- metadata/tag/index text;
- trạng thái enabled;
- provenance user-imported;
- technical metadata.

Hook visual và audio không cần có quan hệ cặp cố định. D có thể ghép chúng theo ngữ cảnh câu chuyện.

### CT-HOOK-002 — `UpdateHookMetadata`

Cho phép sửa tag, mô tả, ghi chú, trạng thái bật/tắt và metadata quản trị. Không sửa byte tại chỗ. Job đã snapshot tiếp tục dùng hook revision cũ nếu artifact còn hợp lệ.

## 5. Thumbnail và media sau hook

### CT-MED-004 — `ThumbnailCandidate`

Mỗi production plan phải có thumbnail xuất hiện trong khoảng thời gian hook để người xem nhận ra chủ thể/câu chuyện. Candidate có:

- subject/entity refs;
- article/event relation;
- crop focus;
- overlay intent như icon, mũi tên, dấu hỏi, dấu cảm thán;
- safety state;
- source provenance;
- visual similarity fingerprint.

Việc thêm overlay nhằm tạo bố cục sáng tạo được D/F quy định trong plan/preset; C chỉ cung cấp candidate và metadata.

## 6. Query candidate cho AI

### CT-MED-005 — `QueryMediaCandidates`

Input:

- production snapshot ref;
- scene intent/entity/topic/time/context;
- media kinds và role cần tìm;
- required technical constraints;
- safety policy revision;
- recency/diversity preferences;
- excluded recent usage refs;
- page cursor/limit.

Output cho mỗi candidate:

- media/rendition/artifact refs;
- provenance;
- semantic match components;
- technical fitness;
- availability;
- safety/rights risk status;
- recent usage summary;
- reason codes.

C trả điểm thành phần và bằng chứng, không trả một điểm mơ hồ duy nhất. D chịu trách nhiệm quyết định cuối và ghi selection rationale.

### CT-MED-006 — `QueryHookCandidates`

Visual/audio được query độc lập theo:

- topic/emotion/pacing;
- story entities/context;
- duration/technical requirements;
- enabled revision;
- recent usage/exclusion;
- compatibility với preset.

Plan phải chọn ít nhất một visual hook và một audio hook phù hợp, đồng thời có thumbnail trong vùng hook.

## 7. Tải bổ sung theo video

### CT-MED-007 — `RequestSupplementalMedia`

Input:

- job/snapshot/scene intent;
- khoảng trống media đã xác định;
- source/search policy revision;
- resource/time budget;
- existing candidate refs để tránh tải lặp.

Output:

- discovery refs;
- acquisition operations;
- disposition `found`, `not_found`, `partial`, `blocked`.

Đây là tìm bổ sung theo video, không bị giới hạn bởi “mỗi nguồn một lần/ngày” của lượt quét định kỳ. Mọi tài nguyên vẫn phải có provenance.

## 8. Ghi nhận sử dụng

### CT-MED-008 — `RecordMediaUsage`

`MediaUsage` được C ghi qua application port trong cùng unit of work PostgreSQL với completion. G điều phối nhưng không ghi trực tiếp bảng C. Usage chỉ trở thành nhìn thấy khi toàn bộ transaction thành công; rollback completion cũng rollback usage. Bản ghi gồm:

- video output/job refs;
- media/rendition/artifact refs;
- role và time range trong video;
- transform/preset refs;
- selection rationale;
- completion time.

Render thử thất bại có thể có technical usage riêng nhưng không tính là production usage để áp dụng quy tắc biến thể.

## 9. Availability và vô hiệu hóa

### CT-MED-009 — `ResolveRenderableVersion`

Input: media/rendition ref và output constraints.

Output:

- artifact version cụ thể;
- location state;
- hash/size/type;
- materialization requirement;
- safety state;
- `usable`, `usable_with_warning`, `not_usable` cùng reason.

Nguồn bị tắt/xóa không làm media lịch sử mất eligibility. Artifact bị thiếu/hash mismatch thì không được render cho tới khi resolve/recover.

## 10. Acceptance contract

1. Bài trùng có media mới bổ sung được provenance vào bài đại diện.
2. Hook visual/audio được quản lý và chọn độc lập.
3. D chỉ chọn media qua revision/artifact refs có provenance và availability.
4. Media nguồn đã remove vẫn có thể được dùng theo quy tắc cũ.
5. Plan luôn có visual hook, audio hook và thumbnail trong vùng hook.
6. Usage chỉ trở thành lịch sử sản xuất sau completion commit.
